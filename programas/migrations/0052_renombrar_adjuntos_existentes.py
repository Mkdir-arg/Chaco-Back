"""Renombra los archivos ya subidos a un nombre no adivinable.

La ``0051`` cambió el ``upload_to`` para que los adjuntos nuevos lleven un UUID,
pero los que ya estaban en disco conservaban el nombre original del celular
(``dni.jpg``, ``documento.pdf``): son justamente los que un diccionario de cien
entradas encuentra. Esta migración los copia al nombre nuevo, actualiza la fila
y borra el original.

Es tolerante a fallas por diseño: si un archivo no está en el storage —borrado a
mano, migrado a otro bucket— se saltea y sigue. Una migración de datos que
aborta a mitad deja el sistema peor que uno o dos archivos sin renombrar, y el
caso se detecta después con una consulta.
"""

import logging
import uuid
from pathlib import PurePosixPath

from django.core.files.storage import default_storage
from django.db import migrations

logger = logging.getLogger(__name__)


def _nombre_nuevo(ruta_actual, carpeta):
    sufijo = PurePosixPath(ruta_actual).suffix.lower()
    return f"{carpeta}/{uuid.uuid4().hex}{sufijo}"


def _mover(ruta_actual, carpeta):
    """Devuelve la ruta nueva, o ``None`` si no se pudo mover."""
    if not ruta_actual:
        return None
    if not default_storage.exists(ruta_actual):
        logger.warning("Adjunto ausente en el storage, se saltea: %s", ruta_actual)
        return None
    try:
        with default_storage.open(ruta_actual, "rb") as origen:
            # `save` resuelve colisiones solo; con UUID no debería haber.
            nueva = default_storage.save(_nombre_nuevo(ruta_actual, carpeta), origen)
    except Exception:
        logger.exception("No se pudo copiar el adjunto %s", ruta_actual)
        return None
    try:
        default_storage.delete(ruta_actual)
    except Exception:
        # El archivo nuevo ya existe y la fila va a apuntar ahí; el viejo queda
        # huérfano. Es preferible a dejar la fila apuntando a algo que se borró.
        logger.warning("Quedó el original sin borrar: %s", ruta_actual)
    return nueva


def renombrar(apps, schema_editor):
    Adjunto = apps.get_model("programas", "AdjuntoFormulario")
    Relevamiento = apps.get_model("programas", "Relevamiento")

    for adjunto in Adjunto.objects.exclude(archivo="").exclude(archivo__isnull=True).iterator():
        if not adjunto.archivo or not adjunto.archivo.name:
            continue
        # Los que ya tienen nombre de UUID (subidos después de la 0051) se saltean.
        nombre = PurePosixPath(adjunto.archivo.name).stem
        if len(nombre) == 32 and all(c in "0123456789abcdef" for c in nombre):
            continue
        carpeta = str(PurePosixPath(adjunto.archivo.name).parent)
        nueva = _mover(adjunto.archivo.name, carpeta)
        if nueva:
            adjunto.archivo.name = nueva
            adjunto.save(update_fields=["archivo"])

    # ``padron_archivo`` es nullable: ``exclude("")`` no filtra los NULL y el
    # ``.name`` de un FieldFile vacío es ``None`` (rompió el bootstrap en ECOM).
    for relevamiento in (
        Relevamiento.objects.exclude(padron_archivo="").exclude(padron_archivo__isnull=True).iterator()
    ):
        if not relevamiento.padron_archivo or not relevamiento.padron_archivo.name:
            continue
        nombre = PurePosixPath(relevamiento.padron_archivo.name).stem
        if len(nombre) == 32 and all(c in "0123456789abcdef" for c in nombre):
            continue
        nueva = _mover(relevamiento.padron_archivo.name, "becas/padrones")
        if nueva:
            relevamiento.padron_archivo.name = nueva
            relevamiento.save(update_fields=["padron_archivo"])


def revertir(apps, schema_editor):
    """No-op: los nombres originales no se conservan y tampoco hacen falta.

    Volver atrás el código deja los archivos donde están; las filas siguen
    apuntando al nombre correcto.
    """
    return


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0051_adjuntos_nombre_no_adivinable"),
    ]

    operations = [
        migrations.RunPython(renombrar, revertir),
    ]
