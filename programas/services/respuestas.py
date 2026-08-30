"""Respuestas por ítem del diseño y foto de la definición (Cambio 58, fase 4:
tasks #345, #346 y #347).

Un caso guarda **lo que respondió por clave de ítem** (``pg-<pk>``, ``rn-<pk>``,
``cp-…``) y la **foto** de la definición que tenía delante (``{version, canal,
items}``, la misma estructura anidada de ``definicion_formulario``). La revisión
lee la foto, así un caso viejo nunca se reinterpreta con un diseño posterior
(D3).

Puente con lo anterior: la app de campo sigue mandando ``data`` (por pk, bajo
``globales`` / ``requisitos``) y las columnas fijas (celular, correo,
apoderado). ``respuestas_desde_legacy`` las traduce a respuestas por clave al
ingresar, y ``legacy_desde_respuestas`` hace el camino inverso para seguir
escribiendo ``data`` y las columnas fijas mientras haya lectores que las usen.
"""

from __future__ import annotations

from django.db import transaction

from programas.models import OrigenRequisito
from programas.services import condiciones

# Columna fija del caso ↔ (origen, vínculo) del campo protegido del catálogo.
COLUMNAS_FIJAS = {
    "celular": (OrigenRequisito.LEGAJO, "telefono"),
    "email_contacto": (OrigenRequisito.LEGAJO, "email"),
    "apoderado_nombre": (OrigenRequisito.PERSONA_VINCULADA, "nombre"),
    "apoderado_apellido": (OrigenRequisito.PERSONA_VINCULADA, "apellido"),
    "apoderado_dni": (OrigenRequisito.PERSONA_VINCULADA, "dni"),
    "apoderado_genero": (OrigenRequisito.PERSONA_VINCULADA, "genero"),
    "apoderado_fecha_nacimiento": (OrigenRequisito.PERSONA_VINCULADA, "fecha_nacimiento"),
}
# Identidad del titular ↔ clave en ``datos_identificacion`` / campo del legajo.
IDENTIDAD = {
    "nombre": "nombre",
    "apellido": "apellido",
    "dni": "dni",
    "fecha_nacimiento": "fecha_nacimiento",
    "genero": "sexo",
}


# ── Foto ─────────────────────────────────────────────────────────────────────


def foto_definicion(relevamiento, definicion=None):
    """La foto que guarda el caso: versión, canal e ítems anidados."""
    from programas.services.becas import definicion_formulario

    definicion = definicion or definicion_formulario(relevamiento)
    return {
        "version": definicion.get("version", 1),
        "canal": definicion.get("canal"),
        "items": definicion.get("items") or [],
    }


def recorrer(items):
    """Recorre la foto en orden de pantalla: ``(item, grupo)`` para cada grupo
    (``grupo=None``), campo y texto."""
    for grupo in items or []:
        yield grupo, None
        for hijo in grupo.get("items") or []:
            yield hijo, grupo


def campos_de(definicion):
    """Los campos de la foto, en orden."""
    return [item for item, grupo in recorrer((definicion or {}).get("items")) if grupo is not None and _es_campo(item)]


def _es_campo(item):
    return item.get("tipo_item") == "campo" or (
        item.get("tipo") not in ("grupo", "texto") and "clave" in item and "tipo" in item
    )


def planos_de(definicion):
    """Lo que necesita el motor de condiciones: ``clave, tipo, padre, condicion``
    en orden."""
    planos = []
    for item, grupo in recorrer((definicion or {}).get("items")):
        if grupo is None:
            planos.append({"clave": item["clave"], "tipo": "grupo", "padre": None, "condicion": item.get("condicion")})
        elif item.get("tipo") == "texto" and not _es_campo(item):
            planos.append(
                {"clave": item["clave"], "tipo": "texto", "padre": grupo["clave"], "condicion": item.get("condicion")}
            )
        else:
            planos.append(
                {"clave": item["clave"], "tipo": "campo", "padre": grupo["clave"], "condicion": item.get("condicion")}
            )
    return planos


def aplicar(definicion, respuestas, hoy=None):
    """``(visibles, ocultos, efectivas)`` sobre la foto: qué se muestra y qué se
    guarda dadas las respuestas (RN-6). El servidor es la autoridad."""
    return condiciones.aplicar(planos_de(definicion), respuestas or {}, hoy)


def clave_por_vinculo(definicion):
    """``{(origen, vinculo): clave}`` de los campos vinculados de la foto."""
    mapa = {}
    for campo in campos_de(definicion):
        origen = campo.get("origen") or OrigenRequisito.PREGUNTA
        if origen != OrigenRequisito.PREGUNTA and campo.get("vinculo"):
            mapa[(origen, campo["vinculo"])] = campo["clave"]
    return mapa


# ── Puente con el contrato anterior ──────────────────────────────────────────


def respuestas_desde_legacy(data, fijos, identidad, definicion):
    """Traduce el contrato anterior a respuestas por clave.

    ``data``: ``{"globales": {pk: v}, "requisitos": {pk: v}}``; ``fijos``: dict
    con las columnas fijas del caso (celular, apoderado_*…); ``identidad``:
    dni, sexo, nombre, apellido, fecha_nacimiento del titular. Solo entran las
    claves que existen en la foto: lo que la app mande de más se ignora.
    """
    data = data or {}
    respuestas = {}
    por_pk = {}
    for campo in campos_de(definicion):
        if campo.get("id") is not None and campo.get("origen", OrigenRequisito.PREGUNTA) == OrigenRequisito.PREGUNTA:
            por_pk[(campo["clave"][:2], str(campo["id"]))] = campo["clave"]
    for prefijo, bolsa in (("pg", data.get("globales") or {}), ("rn", data.get("requisitos") or {})):
        for pk, valor in bolsa.items():
            clave = por_pk.get((prefijo, str(pk)))
            if clave is not None and valor not in (None, "", []):
                respuestas[clave] = valor

    vinculos = clave_por_vinculo(definicion)
    for columna, vinculo in COLUMNAS_FIJAS.items():
        clave = vinculos.get(vinculo)
        valor = (fijos or {}).get(columna)
        if clave is not None and valor not in (None, ""):
            respuestas[clave] = valor.isoformat() if hasattr(valor, "isoformat") else valor
    for vinculo, clave_identidad in IDENTIDAD.items():
        clave = vinculos.get((OrigenRequisito.LEGAJO, vinculo))
        valor = (identidad or {}).get(clave_identidad)
        if clave is not None and valor not in (None, ""):
            respuestas[clave] = valor.isoformat() if hasattr(valor, "isoformat") else valor
    return respuestas


def legacy_desde_respuestas(respuestas, definicion):
    """``(data, fijos)`` para seguir escribiendo el contrato anterior: ``data``
    por pk bajo globales/requisitos (solo campos del catálogo; los propios no
    tienen lugar ahí) y las columnas fijas que la foto pida."""
    data = {"globales": {}, "requisitos": {}}
    fijos = {}
    respuestas = respuestas or {}
    for campo in campos_de(definicion):
        valor = respuestas.get(campo["clave"])
        if valor in (None, "", []):
            continue
        origen = campo.get("origen") or OrigenRequisito.PREGUNTA
        if origen == OrigenRequisito.PREGUNTA and campo.get("id") is not None:
            destino = "globales" if campo["clave"].startswith("pg-") else "requisitos"
            data[destino][str(campo["id"])] = valor
    vinculos = clave_por_vinculo(definicion)
    for columna, vinculo in COLUMNAS_FIJAS.items():
        clave = vinculos.get(vinculo)
        if clave is not None and respuestas.get(clave) not in (None, ""):
            fijos[columna] = respuestas[clave]
    return data, fijos


def identidad_desde_respuestas(respuestas, definicion):
    """Los datos del titular respondidos en los campos vinculados al legajo
    (nombre, apellido, dni, fecha_nacimiento, sexo), para ``datos_identificacion``."""
    vinculos = clave_por_vinculo(definicion)
    identidad = {}
    for vinculo, clave_identidad in IDENTIDAD.items():
        clave = vinculos.get((OrigenRequisito.LEGAJO, vinculo))
        if clave is not None and (respuestas or {}).get(clave) not in (None, ""):
            identidad[clave_identidad] = respuestas[clave]
    return identidad


# ── Puente para casos que entran por el contrato anterior ────────────────────


def _identidad_de(formulario):
    """dni, sexo, nombre, apellido y fecha de nacimiento del titular, del legajo
    si ya está vinculado o de ``datos_identificacion`` si todavía no."""
    identidad = dict(formulario.datos_identificacion or {})
    ciudadano = formulario.ciudadano if formulario.ciudadano_id else None
    if ciudadano is not None:
        identidad.update(
            {
                "dni": ciudadano.dni,
                "nombre": ciudadano.nombre,
                "apellido": ciudadano.apellido,
                "fecha_nacimiento": ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else "",
                "sexo": ciudadano.genero or identidad.get("sexo", ""),
            }
        )
    return identidad


@transaction.atomic
def sincronizar_desde_legacy(formulario, relevamiento=None):
    """Un caso que entró (o se editó) por el contrato anterior —la app de campo,
    la edición de contacto/apoderado en revisión— actualiza sus respuestas por
    clave y, si no la tenía, guarda la foto de la definición vigente.

    Solo se reescriben las claves que el contrato anterior puede expresar (las
    del catálogo y las columnas fijas); lo demás (campos propios) se conserva.
    """
    if not formulario.definicion:
        formulario.definicion = foto_definicion(relevamiento or formulario.relevamiento)
    definicion = formulario.definicion
    fijos = {columna: getattr(formulario, columna) for columna in COLUMNAS_FIJAS}
    nuevas = respuestas_desde_legacy(formulario.data, fijos, _identidad_de(formulario), definicion)
    expresables = {campo["clave"] for campo in campos_de(definicion) if not campo["clave"].startswith("cp-")}
    respuestas = {clave: valor for clave, valor in (formulario.respuestas or {}).items() if clave not in expresables}
    respuestas.update(nuevas)
    formulario.respuestas = respuestas
    formulario.save(update_fields=["respuestas", "definicion", "modificado"])
    return respuestas


# ── Lectura para la revisión ─────────────────────────────────────────────────

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


def respuestas_legibles(formulario, definicion=None, adjuntos=None):
    """La foto del caso con cada campo resuelto, en orden de pantalla:
    ``[{grupo, oculto, items: [fila]}]``. Cada fila de campo trae ``label``,
    ``valor``, ``es_multiple``, ``es_archivo``, ``adjunto``, ``es_imagen`` y
    ``oculto`` (por sus condiciones: no se muestra como vacío, se marca). Sin
    foto (caso anterior al Cambio 58) devuelve ``None`` y el lector cae al
    camino viejo por pk."""
    from pathlib import Path

    definicion = definicion or formulario.definicion
    if not definicion:
        return None
    respuestas = formulario.respuestas or {}
    _, ocultos, _ = aplicar(definicion, respuestas)
    adjuntos = adjuntos if adjuntos is not None else _adjuntos_por_clave(formulario)
    bloques = []
    for grupo in definicion.get("items") or []:
        bloque = {"grupo": grupo, "oculto": grupo["clave"] in ocultos, "items": []}
        for item in grupo.get("items") or []:
            fila = {"clave": item["clave"], "oculto": item["clave"] in ocultos or bloque["oculto"]}
            if _es_campo(item):
                valor = respuestas.get(item["clave"])
                adjunto = adjuntos.get(item["clave"])
                fila.update(
                    {
                        "tipo": "campo",
                        "label": item.get("texto", ""),
                        "valor": "" if valor in (None, [], "") else valor,
                        "es_multiple": isinstance(valor, list),
                        "es_archivo": item.get("tipo") == "ARCHIVO",
                        "adjunto": adjunto,
                        "es_imagen": bool(
                            adjunto and Path(adjunto.archivo.name or "").suffix.lower() in EXTENSIONES_IMAGEN
                        ),
                        "origen": item.get("origen"),
                        "vinculo": item.get("vinculo", ""),
                    }
                )
            else:
                fila.update({"tipo": "texto", "texto": item.get("texto", "")})
            bloque["items"].append(fila)
        bloques.append(bloque)
    return bloques


def _adjuntos_por_clave(formulario):
    """Los adjuntos del caso por clave de ítem (``pg-<pk>`` / ``rn-<pk>``)."""
    adjuntos = {}
    for adjunto in formulario.adjuntos.all():
        if adjunto.pregunta_global_id:
            adjuntos[f"pg-{adjunto.pregunta_global_id}"] = adjunto
        elif adjunto.requisito_nativo_id:
            adjuntos[f"rn-{adjunto.requisito_nativo_id}"] = adjunto
    return adjuntos
