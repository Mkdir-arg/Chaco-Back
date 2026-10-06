from django.contrib.contenttypes.models import ContentType
from django.db import transaction
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
    """Sube la tanda entera o ninguno de sus archivos (LEG-05).

    Validar y crear en el mismo bucle dejaba a medias las subidas múltiples: con
    ``dni.pdf`` válido y ``foto.heic`` inválido, el primero quedaba guardado y el
    usuario solo veía «Formato no permitido». Ahora se valida todo antes de tocar la
    base, y si la creación falla igual se revierten las filas **y los blobs**: el
    storage no participa de la transacción, así que hay que borrarlos a mano.

    El registro del blob va en un ``finally`` **alrededor del ``save()``**, no después:
    ``FileField.pre_save`` escribe el archivo en el storage *adentro* de ese ``save()``,
    antes del INSERT. Si el INSERT falla, el blob ya está en ``media/`` y la fila no
    existe nunca; anotarlo recién con el objeto ya creado dejaba justo a ese huérfano
    —el único que nadie puede encontrar después— fuera de la limpieza.
    """
    if not archivos:
        raise ContactosFilesError("No se seleccionaron archivos")

    for archivo in archivos:
        _validate_archivo(archivo)

    content_type = ContentType.objects.get_for_model(type(instance))
    archivos_subidos = []
    escritos = []
    try:
        with transaction.atomic():
            for archivo in archivos:
                adjunto = Adjunto(
                    content_type=content_type,
                    object_id=instance.id,
                    archivo=archivo,
                    etiqueta=etiqueta or archivo.name,
                )
                subido = archivo.name
                try:
                    adjunto.save()
                finally:
                    # Antes de `pre_save` el `FieldFile` todavía se llama como el
                    # archivo subido (`dni.pdf`); después lleva la ruta que devolvió
                    # el storage (`adjuntos/dni.pdf`). Que sean distintos es la señal
                    # de que el blob llegó a escribirse.
                    guardado = adjunto.archivo.name
                    if guardado and guardado != subido:
                        escritos.append((adjunto.archivo.storage, guardado))
                archivos_subidos.append(
                    {
                        "id": adjunto.id,
                        "nombre": archivo.name,
                        "etiqueta": adjunto.etiqueta,
                    }
                )
    except Exception:
        for storage, nombre in escritos:
            storage.delete(nombre)
        raise
    return archivos_subidos


def eliminar_archivo_de_objeto(instance, archivo_id):
    """Borra un adjunto **de ese objeto**, con su archivo físico.

    Reemplaza a ``eliminar_archivo_por_id``, que hacía
    ``get_object_or_404(Adjunto, id=…).delete()`` sin mirar de quién era el
    adjunto: cualquier cuenta de backoffice borraba el documento de cualquier
    ciudadano, sin papelera ni auditoría (SEC-10, auditoría oct-2026). El dueño
    ahora viaja en la URL y acota el ``filter``: un id de otro ciudadano no
    existe para esta vista y contesta 404.

    ``archivo.delete()`` borra la fila pero **no** el blob: el ``FileField`` de
    Django no tiene borrado en cascada desde la 1.3. Por eso el borrado explícito
    del storage — pero **después del commit**, no antes: el storage no participa
    de la transacción, así que borrar el blob primero y que la transacción se
    revierta después deja la fila apuntando a un archivo que ya no existe (el
    daño irreversible, justo el que esta ficha vino a evitar). Al revés, si lo que
    falla es el ``on_commit``, queda un blob huérfano: molesto, pero recuperable.
    """
    content_type = ContentType.objects.get_for_model(type(instance))
    archivo = get_object_or_404(
        Adjunto,
        pk=archivo_id,
        content_type=content_type,
        object_id=instance.id,
    )
    storage, nombre = archivo.archivo.storage, archivo.archivo.name
    archivo.delete()
    if nombre:
        transaction.on_commit(lambda: storage.delete(nombre))
    return True
