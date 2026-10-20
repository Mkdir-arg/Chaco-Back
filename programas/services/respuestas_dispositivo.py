"""Respuestas a los formularios de un tipo de dispositivo (P17, carril 2).

El formulario «Crear dispositivo» del tipo se completa en el alta y la edición de la
institución (P3) y se lee en el detalle (P4). Mismo intérprete que el link público de
Becas: la definición sale de ``programas.services.diseno`` (``items_vigentes`` →
``serializar``), las condiciones de ``programas.services.condiciones`` y lo respondido
se guarda con la **foto** de la definición y su versión (``respuestas.foto_definicion``),
así una respuesta vieja nunca se reinterpreta con un diseño posterior.

Las reglas:

- El tipo de cada valor se valida siempre; los **obligatorios** se exigen al enviar a
  validación (:func:`faltantes_formulario_alta`), no al guardar el borrador. Un
  obligatorio oculto por sus condiciones no se exige.
- Una fila por (dispositivo, formulario). Cambiar el tipo deja la fila del tipo
  anterior intacta y abre otra.
- Guardar con un diseño nuevo pasa la foto a la versión vigente y **no borra** las
  claves que el diseño ya no tiene: quedan en ``respuestas`` y su definición en
  ``anteriores``.
"""

from __future__ import annotations

from pathlib import Path

from django.db.models import Exists, OuterRef, Prefetch
from django.utils import timezone

from core.archivos import anotar_archivo_escrito
from core.utils_fechas import fecha_local
from programas.models import (
    AdjuntoRespuestaAlta,
    DisenoFormulario,
    MomentoFormulario,
    RespuestasAltaDispositivo,
)
from programas.services.condiciones import esta_vacio
from programas.services.diseno import items_vigentes, serializar
from programas.services.respuestas import EXTENSIONES_IMAGEN, aplicar, campos_de, foto_definicion, legible

#: Un modelo de respuestas por momento. El que sume un momento lo agrega acá y la baja
#: lógica del formulario (``tiene_respuestas``) lo empieza a contar sola.
MODELOS_DE_RESPUESTAS = (RespuestasAltaDispositivo,)


# ── El formulario vigente ────────────────────────────────────────────────────


def formulario_vigente(tipo_id, momento=MomentoFormulario.CREAR_DISPOSITIVO, tipos=None):
    """El formulario del ``momento`` que hoy pide el tipo, o ``None``: si no lo
    tiene o está dado de baja. ``tipos`` acota a los tipos elegibles (en la misma
    consulta): un tipo fuera de ellos no pide nada."""
    if tipo_id is None:
        return None
    disenos = DisenoFormulario.objects.filter(
        tipo_dispositivo_id=tipo_id, momento=momento, dado_de_baja_en__isnull=True
    )
    if tipos is not None:
        disenos = disenos.filter(tipo_dispositivo__in=tipos)
    return disenos.first()


def foto_vigente(diseno):
    """La foto del diseño como se sirve hoy: ``{version, canal, items, destinos_siis}``,
    la misma forma que guarda un caso de Becas. Un formulario de tipo no se divide por
    canal ni hereda catálogo."""
    definicion = {"version": diseno.version, "canal": None, "items": serializar(items_vigentes(diseno))}
    return foto_definicion(None, definicion)


def tiene_respuestas(diseno):
    """¿Alguien respondió ya este formulario? Con respuestas no se borra: se da de baja."""
    return any(modelo.objects.filter(diseno=diseno).exists() for modelo in MODELOS_DE_RESPUESTAS)


def anotar_tiene_respuestas(queryset):
    """El mismo dato que :func:`tiene_respuestas`, como anotación del queryset de diseños."""
    for posicion, modelo in enumerate(MODELOS_DE_RESPUESTAS):
        queryset = queryset.annotate(
            **{f"_respondido_{posicion}": Exists(modelo.objects.filter(diseno=OuterRef("pk")))}
        )
    return queryset


def respondido(diseno):
    """Lee la anotación de :func:`anotar_tiene_respuestas`."""
    return any(getattr(diseno, f"_respondido_{posicion}", False) for posicion in range(len(MODELOS_DE_RESPUESTAS)))


def faltantes_de(foto, respuestas, hoy=None):
    """Los campos **obligatorios** de la foto que quedaron visibles y sin responder,
    en orden. Un obligatorio oculto por sus condiciones no falta (RN-6)."""
    respuestas = respuestas or {}
    _, ocultos, _ = aplicar(foto, respuestas, hoy)
    return [
        campo
        for campo in campos_de(foto)
        if campo.get("obligatorio") and campo["clave"] not in ocultos and esta_vacio(respuestas.get(campo["clave"]))
    ]


# ── Lectura y guardado del alta ──────────────────────────────────────────────


def respuestas_guardadas(dispositivo, diseno):
    """``{clave: valor}`` que el dispositivo ya respondió en ``diseno`` (vacío si nada)."""
    if dispositivo is None or dispositivo.pk is None or diseno is None:
        return {}
    fila = RespuestasAltaDispositivo.objects.filter(dispositivo=dispositivo, diseno=diseno).only("respuestas").first()
    return dict(fila.respuestas or {}) if fila is not None else {}


def guardar_respuestas_alta(dispositivo, diseno, foto, respuestas, archivos=(), usuario=None):
    """Guarda lo respondido en «Crear dispositivo», con la foto y la versión vigentes.

    Va **dentro** de la transacción del alta o la edición del legajo, decorada por
    afuera con ``core.archivos.archivos_atomicos``: un archivo escrito se borra si
    después algo falla. ``respuestas`` son las visibles y respondidas
    (``RespuestasDisenoForm.respuestas``); ``archivos``, ``[(clave, archivo)]`` nuevos.

    Las claves del diseño que quedaron sin responder (u ocultas) se quitan; las que el
    diseño ya no tiene se conservan, con su definición en ``anteriores``.
    """
    fila = RespuestasAltaDispositivo.objects.select_for_update().filter(dispositivo=dispositivo, diseno=diseno).first()
    if fila is None:
        fila = RespuestasAltaDispositivo(dispositivo=dispositivo, diseno=diseno, respuestas={}, anteriores={})
    claves_vigentes = {campo["clave"] for campo in campos_de(foto)}
    campos_anteriores = {campo["clave"]: campo for campo in campos_de(fila.definicion)}
    anteriores = dict(fila.anteriores or {})
    conservadas = {}
    for clave, valor in (fila.respuestas or {}).items():
        if clave in claves_vigentes:
            continue
        conservadas[clave] = valor
        if clave not in anteriores and clave in campos_anteriores:
            anteriores[clave] = {"campo": campos_anteriores[clave], "version": fila.version}
    nuevas = {**conservadas, **{clave: valor for clave, valor in respuestas.items() if clave in claves_vigentes}}
    if fila.pk is None and not nuevas and not archivos:
        return None  # nada respondido: sin fila, el formulario se sigue pudiendo borrar
    if fila.pk is not None and nuevas == fila.respuestas and fila.version == foto["version"] and not archivos:
        return fila
    fila.definicion = foto
    fila.version = foto["version"]
    fila.respuestas = nuevas
    fila.anteriores = anteriores
    fila.actualizado_por = usuario
    fila.save()
    for clave, archivo in archivos:
        adjunto = AdjuntoRespuestaAlta(respuestas=fila, clave=clave, archivo=archivo)
        adjunto.save()
        anotar_archivo_escrito(adjunto.archivo, asignado=archivo)
    return fila


def faltantes_formulario_alta(dispositivo):
    """Los textos de los obligatorios de «Crear dispositivo» que el dispositivo todavía
    no respondió, contra el formulario **vigente** de su tipo. Vacío si el tipo no lo
    pide. Es lo que exige ``enviar_a_validacion``."""
    diseno = formulario_vigente(dispositivo.tipo_id)
    if diseno is None:
        return []
    return [
        campo.get("texto", "")
        for campo in faltantes_de(foto_vigente(diseno), respuestas_guardadas(dispositivo, diseno))
    ]


# ── Lectura para el detalle (P4) ─────────────────────────────────────────────


def _adjuntos_por_clave(fila):
    """El adjunto más nuevo por clave (el prefetch viene ordenado del más nuevo)."""
    adjuntos = {}
    for adjunto in fila.adjuntos.all():
        adjuntos.setdefault(adjunto.clave, adjunto)
    return adjuntos


def formularios_respondidos(dispositivo):
    """Lo respondido en «Crear dispositivo», para la solapa Datos de P4.

    Una entrada por fila —la del tipo actual primero, después las de tipos anteriores—
    leída **con su foto**: ``{titulo, tipo, version, del_tipo_actual, secciones}``, y
    cada sección ``{titulo, campos}`` con solo lo visible según sus condiciones
    (evaluadas al día en que se respondió). Dos consultas, sin importar cuántos campos.
    """
    filas = (
        RespuestasAltaDispositivo.objects.filter(dispositivo=dispositivo)
        .select_related("diseno__tipo_dispositivo")
        .prefetch_related(Prefetch("adjuntos", queryset=AdjuntoRespuestaAlta.objects.order_by("-creado", "-id")))
        .order_by("-modificado", "-id")
    )
    salida = []
    for fila in filas:
        foto = fila.definicion or {}
        respuestas = fila.respuestas or {}
        _, ocultos, _ = aplicar(foto, respuestas, hoy=fecha_local(fila.modificado) or timezone.localdate())
        adjuntos = _adjuntos_por_clave(fila)
        secciones = []
        for grupo in foto.get("items") or []:
            if grupo["clave"] in ocultos:
                continue
            campos = []
            for item in grupo.get("items") or []:
                if item.get("tipo_item") != "campo" or item["clave"] in ocultos:
                    continue
                valor = respuestas.get(item["clave"])
                adjunto = adjuntos.get(item["clave"]) if item.get("tipo") == "ARCHIVO" else None
                campos.append(
                    {
                        "label": item.get("texto", ""),
                        "valor": legible(item, valor),
                        "es_multiple": isinstance(valor, list),
                        "adjunto": adjunto,
                        "es_imagen": bool(
                            adjunto and Path(adjunto.archivo.name or "").suffix.lower() in EXTENSIONES_IMAGEN
                        ),
                    }
                )
            if campos:
                secciones.append({"titulo": grupo.get("titulo", ""), "campos": campos})
        tipo = fila.diseno.tipo_dispositivo
        salida.append(
            {
                "titulo": fila.diseno.get_momento_display(),
                "tipo": tipo.nombre if tipo is not None else "",
                "version": fila.version,
                "del_tipo_actual": fila.diseno.tipo_dispositivo_id == dispositivo.tipo_id,
                "secciones": secciones,
            }
        )
    salida.sort(key=lambda entrada: not entrada["del_tipo_actual"])
    return salida
