"""Recorrido de la foto de un formulario (grupos, campos y textos), sin dependencias.

Vive aparte de ``respuestas`` para que ``becas`` lo use sin importar a ``respuestas``,
que ya importa de ``becas`` (ciclo medido por ``test_arquitectura``).
"""


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
