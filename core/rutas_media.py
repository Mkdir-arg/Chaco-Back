"""Rutas de `media/`: un prefijo por superficie y un nombre no adivinable.

Dos cosas viven acá porque son la misma decisión vista de los dos lados:

1. **El prefijo** con el que se guarda cada tipo de archivo. Es lo que
   :mod:`core.views.media` usa para saber **de quién** es un archivo y qué
   capacidad pedir (SEC-09 etapa 2): `/media/adjuntos/…` se resuelve contra
   ``legajos.Adjunto``, `/media/becas/padrones/…` contra la convocatoria, etc.
   Si un modelo cambia su prefijo sin tocar esta tabla, su archivo pasa a ser un
   prefijo desconocido y deja de poder bajarse.
2. **El nombre**, que desde el Cambio 188 es un UUID en todos los campos de
   archivo. Django conservaba el nombre original (`dni.jpg`, `acta.pdf`), así que
   la ruta se adivinaba con un diccionario de cien entradas y el nombre que
   eligió quien sube llegaba al disco. El UUID corta las dos cosas; la
   trazabilidad la da la fila, no el nombre.

Los archivos **ya guardados no se renombran**: la migración de estos ``upload_to``
es solo de estado y la resolución del dueño es por el nombre que tiene la fila,
así que un `adjuntos/dni.pdf` de 2025 se sigue bajando igual.

No confundir con :mod:`core.archivos`, que es otra cosa: el borrado de los
archivos que escribió una operación que después falló (RED-35).
"""

import uuid
from pathlib import Path

from django.utils import timezone

#: Adjuntos genéricos del ciudadano y del legajo (``legajos.Adjunto``).
PREFIJO_ADJUNTO_LEGAJO = "adjuntos/"
#: Foto de perfil del ciudadano (``legajos.Ciudadano.foto``).
PREFIJO_FOTO_CIUDADANO = "ciudadanos/fotos/"
#: Grabación/foto/documento de un contacto (``legajos.HistorialContacto``).
PREFIJO_CONTACTO = "contactos/"
#: Campo ARCHIVO del F-00 de Dispositivos (``programas.ArchivoAdmision``).
PREFIJO_F00 = "admisiones/f00/"
#: Documentación respaldatoria de una solicitud (``programas.SolicitudMerendero``).
PREFIJO_SOLICITUD_MERENDERO = "merenderos/solicitudes/"
#: Adjuntos de un caso de Becas (``programas.AdjuntoFormulario``).
PREFIJO_ADJUNTO_BECAS = "becas/adjuntos/"
#: Excel del padrón de habilitados (convocatoria y relevamiento).
PREFIJO_PADRON_BECAS = "becas/padrones/"
#: Excel de destinatarios y HTML del cuerpo de una campaña (``notificaciones.Campana``).
PREFIJO_NOTIFICACIONES = "notificaciones/"


def nombre_opaco(filename):
    """`dni.JPG` -> `3f2a….jpg`: sin el nombre que eligió quien subió el archivo."""
    return f"{uuid.uuid4().hex}{Path(filename or '').suffix.lower()}"


def ruta_adjunto_legajo(instance, filename):
    return f"{PREFIJO_ADJUNTO_LEGAJO}{nombre_opaco(filename)}"


def ruta_foto_ciudadano(instance, filename):
    return f"{PREFIJO_FOTO_CIUDADANO}{nombre_opaco(filename)}"


def ruta_contacto(instance, filename):
    return f"{PREFIJO_CONTACTO}{nombre_opaco(filename)}"


def ruta_archivo_admision(instance, filename):
    return f"{PREFIJO_F00}{nombre_opaco(filename)}"


def ruta_solicitud_merendero(instance, filename):
    """Conserva el `%Y/%m` que ya tenía: son muchas solicitudes por año."""
    return f"{PREFIJO_SOLICITUD_MERENDERO}{timezone.now():%Y/%m}/{nombre_opaco(filename)}"


def ruta_notificacion_excel(instance, filename):
    """La lista de destinatarios de una campaña: correos de personas, nombre opaco."""
    return f"{PREFIJO_NOTIFICACIONES}excel/{nombre_opaco(filename)}"


def ruta_notificacion_html(instance, filename):
    """El HTML **original** que subió el operador; lo que se envía es la copia saneada."""
    return f"{PREFIJO_NOTIFICACIONES}html/{nombre_opaco(filename)}"
