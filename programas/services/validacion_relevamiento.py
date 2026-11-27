"""Validación de lo que la app manda en ``respuestas`` del resultado de un relevamiento (A4).

Vive aparte de ``respuestas_dispositivo`` porque reusa el field del alta de la institución
(``forms_dinamicos``), que a su vez importa ese módulo: así no hay ciclo.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_date

from programas.forms_dinamicos import _field_para_campo, es_adjunto
from programas.models import TipoCampo
from programas.services.condiciones import esta_vacio
from programas.services.firma import errores_del_firmante, normalizar_firmante
from programas.services.respuestas import aplicar, campos_de
from programas.services.respuestas_dispositivo import faltantes_de


class RespuestasInvalidas(ValidationError):
    """Las respuestas de un formulario no pasan el motor: tipo inválido u obligatorio sin responder.
    ``por_clave`` es ``{clave: texto}``; la API lo devuelve aparte."""

    def __init__(self, por_clave):
        super().__init__({"respuestas": list(por_clave.values())})
        self.por_clave = dict(por_clave)


def requiere_archivo(foto):
    """¿La foto tiene un campo de archivo o firma **obligatorio**? Ese formulario no se completa desde la app."""
    return any(campo.get("obligatorio") and es_adjunto(campo) for campo in campos_de(foto))


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
    if campo.get("tipo") == TipoCampo.FIRMA:
        # De la firma llega quién firmó; la imagen viaja como un archivo. La fecha la pone el servidor.
        errores = errores_del_firmante(valor)
        if errores:
            return valor, f"«{etiqueta}»: {errores[0]}"
        return normalizar_firmante(valor), None
    if campo.get("tipo") == "DATE" and not _es_fecha_iso(valor):
        return valor, f"«{etiqueta}» tiene que ser una fecha válida (AAAA-MM-DD)."
    campo_django = _field_para_campo({**campo, "obligatorio": False, "opciones": campo.get("opciones") or []})
    try:
        limpio = campo_django.clean(valor)
    except ValidationError as error:
        return valor, f"«{etiqueta}»: {error.messages[0]}"
    return (limpio.isoformat() if campo.get("tipo") == "DATE" else valor), None


def _avisos_de_archivos(archivos_faltantes, adjuntadas):
    return [
        f"Falta adjuntar «{campo.get('texto') or campo['clave']}», que es obligatorio."
        for campo in archivos_faltantes
        if campo["clave"] not in adjuntadas
    ]


def avisos_de_archivos_obligatorios(foto, respuestas, adjuntadas=(), hoy=None):
    """Un texto por cada campo ARCHIVO obligatorio y visible que ni el envío ni un adjunto ya recibido traen.

    Es un **aviso, no un error**: el archivo llega después por el endpoint de adjuntos, así que
    la validación no lo exige y el resultado se cierra igual. Pero quien lo manda tiene que
    enterarse de lo que falta (lo ve la app en la respuesta del resultado; el informe del
    relevamiento lo marca después). Mira el mismo marcador que las condiciones ``adjuntado`` /
    ``no_adjuntado`` (un valor no vacío en la clave) y descuenta las claves de ``adjuntadas``,
    las que ya tienen un archivo recibido. Es la misma lectura que usa el reenvío idempotente,
    sobre las respuestas guardadas.
    """

    archivos = [campo for campo in faltantes_de(foto, respuestas, hoy) if campo.get("tipo") == "ARCHIVO"]
    return _avisos_de_archivos(archivos, set(adjuntadas))


def validar_respuestas_de_campo(foto, respuestas, hoy=None):
    """``(efectivas, errores)``: ver :func:`validar_respuestas_con_avisos`, que además trae los avisos."""

    efectivas, errores, _ = validar_respuestas_con_avisos(foto, respuestas, hoy)
    return efectivas, errores


def validar_respuestas_con_avisos(foto, respuestas, hoy=None, adjuntadas=()):
    """Valida lo que mandó la app contra la foto vigente, con el mismo motor que el alta.

    Devuelve ``(efectivas, errores, avisos)``: ``avisos`` son los ARCHIVO obligatorios sin enviar
    (:func:`avisos_de_archivos_obligatorios`, del mismo recorrido de los obligatorios, sin las
    claves de ``adjuntadas``). ``efectivas`` son las respuestas visibles según las
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
    archivos_faltantes = []
    for campo in faltantes_de(foto, respuestas, hoy):
        if campo.get("tipo") == "ARCHIVO":
            archivos_faltantes.append(campo)
        elif campo["clave"] not in errores:
            errores[campo["clave"]] = f"«{campo.get('texto') or campo['clave']}» es obligatorio."
    efectivas = {
        clave: valor
        for clave, valor in respuestas.items()
        if clave not in ocultos and not esta_vacio(valor) and clave not in errores
    }
    efectivas.update(valores)
    return (
        {clave: efectivas[clave] for clave in respuestas if clave in efectivas},
        errores,
        _avisos_de_archivos(archivos_faltantes, set(adjuntadas)),
    )
