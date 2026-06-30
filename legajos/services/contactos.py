from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from ..models import Adjunto

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png"]


class ContactosFilesError(ValueError):
    pass


def _validate_archivo(archivo):
    if archivo.size > MAX_FILE_SIZE:
        raise ContactosFilesError(f"El archivo {archivo.name} es muy grande (máx. 10MB)")

    nombre_archivo = archivo.name.lower()
    if not any(nombre_archivo.endswith(extension) for extension in ALLOWED_EXTENSIONS):
        raise ContactosFilesError(f"Formato no permitido: {archivo.name}")


def subir_archivos_para_objeto(instance, archivos, etiqueta=""):
    if not archivos:
        raise ContactosFilesError("No se seleccionaron archivos")

    content_type = ContentType.objects.get_for_model(type(instance))
    archivos_subidos = []
    for archivo in archivos:
        _validate_archivo(archivo)
        adjunto = Adjunto.objects.create(
            content_type=content_type,
            object_id=instance.id,
            archivo=archivo,
            etiqueta=etiqueta or archivo.name,
        )
        archivos_subidos.append(
            {
                "id": adjunto.id,
                "nombre": archivo.name,
                "etiqueta": adjunto.etiqueta,
            }
        )
    return archivos_subidos


def eliminar_archivo_por_id(archivo_id):
    archivo = get_object_or_404(Adjunto, id=archivo_id)
    archivo.delete()
    return True
