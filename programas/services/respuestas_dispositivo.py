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
    AdjuntoRespuestaRelevamiento,
    DisenoFormulario,
    InspeccionEdificio,
    MomentoFormulario,
    RespuestasAltaDispositivo,
    RespuestasRelevamiento,
)
from programas.services.condiciones import esta_vacio
from programas.services.diseno import items_vigentes, serializar
from programas.services.respuestas import EXTENSIONES_IMAGEN, aplicar, campos_de, foto_definicion, legible

#: Un modelo de respuestas por momento. El que sume un momento lo agrega acá y la baja
#: lógica del formulario (``tiene_respuestas``) lo empieza a contar sola. Se suma también
#: ``InspeccionEdificio``: un relevamiento ya asignado fija su formulario (``diseno``, PROTECT)
#: antes de que haya una sola respuesta, y ese formulario tampoco se borra.
MODELOS_DE_RESPUESTAS = (RespuestasAltaDispositivo, RespuestasRelevamiento, InspeccionEdificio)


# ── El formulario vigente ────────────────────────────────────────────────────


def formulario_vigente(tipo_id, momento=MomentoFormulario.CREAR_DISPOSITIVO, tipos=None):
    """El formulario del ``momento`` que hoy pide el tipo, o ``None``: si no lo
    tiene o está dado de baja. ``tipos`` acota a los tipos elegibles (en la misma
    consulta): un tipo fuera de ellos no pide nada."""
    if tipo_id is None:
        return None
    disenos = DisenoFormulario.objects.select_related("tipo_dispositivo").filter(
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


def diseno_vigente_de(inspeccion):
    """El formulario «Relevamiento» que hoy pide el relevamiento, o ``None`` (sin formulario o dado de
    baja). Es la única definición de «diseño vigente»; conviene traer ``diseno`` con ``select_related``."""
    diseno = inspeccion.diseno if inspeccion.diseno_id is not None else None
    return diseno if diseno is not None and diseno.dado_de_baja_en is None else None


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


def _secciones(foto, respuestas, adjuntos, hoy):
    """Lo respondido en una foto, listo para pintar: ``[{titulo, campos}]`` con solo lo visible
    según las condiciones (evaluadas al día ``hoy``, el de la respuesta). Lo comparten el detalle
    de la institución y el informe del relevamiento."""
    _, ocultos, _ = aplicar(foto, respuestas, hoy=hoy)
    secciones = []
    for grupo in foto.get("items") or []:
        if grupo["clave"] in ocultos:
            continue
        campos = []
        for item in grupo.get("items") or []:
            if item.get("tipo_item") != "campo" or item["clave"] in ocultos:
                continue
            valor = respuestas.get(item["clave"])
            es_archivo = item.get("tipo") == "ARCHIVO"
            adjunto = adjuntos.get(item["clave"]) if es_archivo else None
            campos.append(
                {
                    "label": item.get("texto", ""),
                    "valor": "" if isinstance(valor, dict) else legible(item, valor),
                    "es_multiple": isinstance(valor, list),
                    "adjunto": adjunto,
                    "es_imagen": bool(
                        adjunto and Path(adjunto.archivo.name or "").suffix.lower() in EXTENSIONES_IMAGEN
                    ),
                    "es_archivo": es_archivo,
                    "obligatorio": bool(item.get("obligatorio")),
                    "falta": bool(es_archivo and item.get("obligatorio") and adjunto is None),
                }
            )
        if campos:
            secciones.append({"titulo": grupo.get("titulo", ""), "campos": campos})
    return secciones


def respuestas_de_versiones_anteriores(foto, respuestas, anteriores, adjuntos):
    """Lo respondido en campos que la foto vigente de la fila ya no tiene, para el bloque plegado
    «De versiones anteriores» de P4: ``[{etiqueta, valor}]``, en el orden en que dejaron de estar.

    Solo cuenta una clave que está en ``anteriores`` (con su definición, de ahí sale la etiqueta
    y el tipo), que la foto **ya no** tiene y cuyo valor no está vacío. Una lista se une con comas.
    Un archivo se muestra por su nombre, **sin enlace**: la sección plegable compartida
    (``_ficha_seccion``) no lleva enlaces y la descarga sigue disponible desde el legajo.
    """
    vigentes = {campo["clave"] for campo in campos_de(foto)}
    campos = []
    for clave, entrada in (anteriores or {}).items():
        if clave in vigentes or clave not in respuestas:
            continue
        campo = (entrada or {}).get("campo") or {}
        adjunto = adjuntos.get(clave) if campo.get("tipo") == "ARCHIVO" else None
        if adjunto is not None:
            valor = Path(adjunto.archivo.name or "").name
        else:
            valor = legible(campo, respuestas[clave])
            if isinstance(valor, list):
                valor = ", ".join(str(parte) for parte in valor)
        if esta_vacio(valor):
            continue
        campos.append({"etiqueta": campo.get("texto") or clave, "valor": valor})
    return campos


def formularios_respondidos(dispositivo):
    """Lo respondido en «Crear dispositivo», para la solapa Datos de P4.

    Una entrada por fila —la del tipo actual primero, después las de tipos anteriores—
    leída **con su foto**: ``{titulo, tipo, version, del_tipo_actual, secciones}``, y
    cada sección ``{titulo, campos}`` con solo lo visible según sus condiciones
    (evaluadas al día en que se respondió), más ``anteriores`` (ver
    :func:`respuestas_de_versiones_anteriores`) y ``id_anteriores`` (id único del bloque
    plegado). Dos consultas, sin importar cuántos campos.
    """
    filas = (
        RespuestasAltaDispositivo.objects.filter(dispositivo=dispositivo)
        .select_related("diseno__tipo_dispositivo")
        .prefetch_related(Prefetch("adjuntos", queryset=AdjuntoRespuestaAlta.objects.order_by("-creado", "-id")))
        .order_by("-modificado", "-id")
    )
    salida = []
    for fila in filas:
        adjuntos = _adjuntos_por_clave(fila)
        secciones = _secciones(
            fila.definicion or {},
            fila.respuestas or {},
            adjuntos,
            fecha_local(fila.modificado) or timezone.localdate(),
        )
        tipo = fila.diseno.tipo_dispositivo
        salida.append(
            {
                "titulo": fila.diseno.get_momento_display(),
                "tipo": tipo.nombre if tipo is not None else "",
                "version": fila.version,
                "del_tipo_actual": fila.diseno.tipo_dispositivo_id == dispositivo.tipo_id,
                "secciones": secciones,
                "anteriores": respuestas_de_versiones_anteriores(
                    fila.definicion or {}, fila.respuestas or {}, fila.anteriores, adjuntos
                ),
                "id_anteriores": f"anteriores-{fila.pk}",
            }
        )
    salida.sort(key=lambda entrada: not entrada["del_tipo_actual"])
    return salida


# ── El formulario «Relevamiento» (app de campo, Cambio 385) ──────────────────


def _observacion_de_version(version_capturada, version):
    """G1-16: la app capturó con otra versión que la que se guardó (``version_capturada`` es
    opcional; sin ella no hay nada que comparar)."""
    if version_capturada is None or version_capturada == version:
        return []
    return [
        f"La carga se hizo con la versión {version_capturada} del formulario y se guardó con la versión "
        f"{version}: el diseño cambió entre la captura y el envío."
    ]


def guardar_respuestas_relevamiento(inspeccion, diseno, foto, respuestas, usuario=None, version_capturada=None):
    """Crea las respuestas del relevamiento con la foto de la definición **vigente** y su versión
    (D4). Va dentro de la transacción de ``registrar_resultado``; ``respuestas`` ya pasó por
    ``validacion_relevamiento.validar_respuestas_de_campo``.

    Las claves que la foto vigente ya no tiene **no se descartan**: se guardan y su entrada en
    ``anteriores`` dice que dejaron de estar (como ``RespuestasDeFormulario``), y la observación
    las nombra. Devuelve la fila.
    """
    claves_vigentes = {campo["clave"] for campo in campos_de(foto)}
    observaciones = _observacion_de_version(version_capturada, foto["version"])
    anteriores = {}
    for clave in sorted(set(respuestas) - claves_vigentes):
        anteriores[clave] = {"campo": {"clave": clave, "texto": clave}, "version": version_capturada or foto["version"]}
        observaciones.append(f"La respuesta «{clave}» ya no pertenece al formulario vigente: se conservó aparte.")
    return RespuestasRelevamiento.objects.create(
        inspeccion=inspeccion,
        diseno=diseno,
        definicion=foto,
        version=foto["version"],
        respuestas=dict(respuestas),
        anteriores=anteriores,
        version_capturada=version_capturada,
        observaciones_carga="\n".join(observaciones),
        actualizado_por=usuario,
    )


def clave_de_archivo_valida(inspeccion, clave):
    """¿``clave`` es un campo ARCHIVO del formulario de este relevamiento? Mira la foto
    vigente y, si ya se respondió, la que quedó guardada: el archivo de un campo que existía
    cuando el territorial capturó entra aunque el diseño haya cambiado después."""
    fotos = []
    diseno = diseno_vigente_de(inspeccion)
    if diseno is not None:
        fotos.append(foto_vigente(diseno))
    guardadas = RespuestasRelevamiento.objects.filter(inspeccion=inspeccion).only("definicion").first()
    if guardadas is not None:
        fotos.append(guardadas.definicion or {})
    return any(
        campo["clave"] == clave and campo.get("tipo") == "ARCHIVO" for foto in fotos for campo in campos_de(foto)
    )


def adjuntos_del_relevamiento(inspeccion):
    """El adjunto más nuevo por clave."""
    adjuntos = {}
    for adjunto in AdjuntoRespuestaRelevamiento.objects.filter(inspeccion=inspeccion).order_by("-creado", "-id"):
        adjuntos.setdefault(adjunto.clave, adjunto)
    return adjuntos


def formulario_del_relevamiento(inspeccion):
    """Lo respondido en el formulario del relevamiento, para su informe (A5), o ``None`` si
    no hay respuestas: ``{titulo, version, version_capturada, observaciones, secciones, faltantes}``.
    ``faltantes`` son los ARCHIVO obligatorios que todavía no llegaron."""
    fila = RespuestasRelevamiento.objects.filter(inspeccion=inspeccion).select_related("diseno").first()
    if fila is None:
        return None
    adjuntos = adjuntos_del_relevamiento(inspeccion)
    # Un archivo recibido cuenta como «adjuntado» para las condiciones, aunque la app no haya mandado el marcador.
    respuestas = {**{clave: {"archivo_adjunto": True} for clave in adjuntos}, **(fila.respuestas or {})}
    secciones = _secciones(
        fila.definicion or {},
        respuestas,
        adjuntos,
        fecha_local(fila.creado) or timezone.localdate(),
    )
    return {
        "titulo": fila.diseno.get_momento_display(),
        "version": fila.version,
        "version_capturada": fila.version_capturada,
        "observaciones": [linea for linea in (fila.observaciones_carga or "").splitlines() if linea],
        "secciones": secciones,
        "faltantes": [campo["label"] for seccion in secciones for campo in seccion["campos"] if campo["falta"]],
    }
