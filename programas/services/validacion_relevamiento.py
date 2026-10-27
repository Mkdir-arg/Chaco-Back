"""Validación de lo que la app manda en ``respuestas`` del resultado de un relevamiento (A4).

Vive aparte de ``respuestas_dispositivo`` porque reusa el field del alta de la institución
(``forms_dinamicos``), que a su vez importa ese módulo: así no hay ciclo.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date

from programas.forms_dinamicos import _field_para_campo
from programas.services.condiciones import esta_vacio
from programas.services.respuestas import aplicar, campos_de
from programas.services.respuestas_dispositivo import faltantes_de


def _es_fecha_iso(valor):
    try:
        return isinstance(valor, str) and parse_date(valor.strip()) is not None
    except ValueError:
        return False


def _valor_de_campo(campo, valor):
    """``(valor_a_guardar, problema)`` de un valor de la app contra su campo, con el **mismo** field
    que el alta de la institución (``forms_dinamicos._field_para_campo``), sin exigirlo. El valor se
    guarda como llegó, salvo la fecha, que queda en ISO. Una fecha solo se acepta ``AAAA-MM-DD``: es
    el formato del contrato."""
    etiqueta = campo.get("texto") or campo["clave"]
    if campo.get("tipo") == "DATE" and not _es_fecha_iso(valor):
        return valor, f"«{etiqueta}» tiene que ser una fecha válida (AAAA-MM-DD)."
    campo_django = _field_para_campo({**campo, "obligatorio": False, "opciones": campo.get("opciones") or []})
    try:
        limpio = campo_django.clean(valor)
    except ValidationError as error:
        return valor, f"«{etiqueta}»: {error.messages[0]}"
    return (limpio.isoformat() if campo.get("tipo") == "DATE" else valor), None


def validar_respuestas_de_campo(foto, respuestas, hoy=None):
    """Valida lo que mandó la app contra la foto vigente, con el mismo motor que el alta.

    Devuelve ``(efectivas, errores)``: ``efectivas`` son las respuestas visibles según las
    condiciones (RN-6: lo oculto se descarta y no se exige) y ``errores``, ``{clave: texto}``
    de los valores de tipo inválido y de los **obligatorios** que quedaron sin responder.

    Los campos ARCHIVO **no se exigen ni se validan** (el archivo llega después, por el endpoint de
    adjuntos), pero **su presencia cuenta** para las condiciones ``adjuntado`` / ``no_adjuntado``:
    cualquier valor no vacío —la app manda ``{"archivo_adjunto": true, "nombre": ...}``, como en
    Becas— significa «lo adjunté» y se conserva tal cual. Una clave que la foto no conoce no es un
    error: el diseño pudo cambiar entre la sincronización y el envío; se conserva (ver
    :func:`guardar_respuestas_relevamiento`).
    """
    respuestas = dict(respuestas or {})
    campos = {campo["clave"]: campo for campo in campos_de(foto)}
    archivos = {clave for clave, campo in campos.items() if campo.get("tipo") == "ARCHIVO"}
    errores = {}
    _, ocultos, _ = aplicar(foto, respuestas, hoy)
    valores = {}
    for clave, valor in respuestas.items():
        campo = campos.get(clave)
        if campo is None or clave in ocultos or esta_vacio(valor):
            continue
        if clave in archivos:
            valores[clave] = valor
            continue
        guardado, problema = _valor_de_campo(campo, valor)
        if problema:
            errores[clave] = problema
        else:
            valores[clave] = guardado
    for campo in faltantes_de(foto, respuestas, hoy):
        if campo.get("tipo") != "ARCHIVO" and campo["clave"] not in errores:
            errores[campo["clave"]] = f"«{campo.get('texto') or campo['clave']}» es obligatorio."
    efectivas = {
        clave: valor
        for clave, valor in respuestas.items()
        if clave not in ocultos and not esta_vacio(valor) and clave not in errores
    }
    efectivas.update(valores)
    return {clave: efectivas[clave] for clave in respuestas if clave in efectivas}, errores
