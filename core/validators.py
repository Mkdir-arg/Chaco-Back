"""Validadores de archivos compartidos por las superficies que aceptan uploads.

La extensión la elige quien sube el archivo: no dice nada sobre el contenido.
Donde el upload es **anónimo** —el link público de Becas (SIIS-16)— eso alcanza
para dejar HTML o un script en ``media/``, que después se sirve desde el
backoffice. La firma de los primeros bytes sí es del archivo, y es barata.

Los tres formatos que acepta el trámite son los que la gente saca con el
teléfono o descarga de un organismo: JPG, PNG y PDF. SEC-15 (Ola 2) reusa esto
para F-00 y la solicitud de merendero, que hoy tampoco miran el contenido.
"""

from pathlib import Path

from django.forms import ValidationError

#: Lista blanca de los adjuntos del backoffice y de la app de campo. Nació en la
#: API de campo (Cambio 46) y vive acá desde SEC-15 para que haya **una sola**:
#: la usan el serializer de `/api/becas/`, el F-00 de Dispositivos y la solicitud
#: de merendero. Lo que importa que quede afuera es el contenido interpretable
#: (`.html`, `.svg`, `.js`): `media/` se sirve same-origin.
#:
#: **Angostar esta tupla es un cambio con consecuencias en el teléfono:** ante un
#: 4xx la app instalada marca la operación `FAILED_PERMANENT` y no la reintenta
#: nunca, así que rechazar algo que hoy manda se lleva puesta la captura.
#: `.doc`/`.docx` quedan afuera por D-15 (el F-00 necesita PDF e imagen).
ADJUNTO_EXTENSIONES = (".jpg", ".jpeg", ".png", ".pdf", ".heic", ".heif", ".webp")
ADJUNTO_MAX_BYTES = 5 * 1024 * 1024

MENSAJE_ADJUNTO_FORMATO = "Solo se aceptan archivos JPG, PNG, WEBP, HEIC o PDF."
MENSAJE_ADJUNTO_TAMANIO = "El archivo no puede superar los 5 MB."

#: Firma (magic bytes) por extensión. Las variantes de JPEG comparten los tres
#: primeros bytes; el cuarto marca el *segment* (JFIF, Exif…) y varía.
FIRMAS = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}

#: Lo que hay que leer para decidir. Ninguna firma de las de arriba es más larga.
BYTES_DE_FIRMA = 8


class MaxSizeFileValidator:
    def __init__(self, max_file_size=5):
        self.max_file_size = max_file_size

    def __call__(self, value):
        size = value.size
        max_size = self.max_file_size * 1048576

        if size > max_size:
            raise ValidationError(f"Tamaño maximo archivo: {self.max_file_size}MB")

        return value


def cabecera(archivo, cantidad=BYTES_DE_FIRMA):
    """Los primeros bytes del archivo subido, dejándolo donde estaba.

    El form puede validar el mismo archivo más de una vez y después el storage
    lo escribe desde el principio: leer sin rebobinar guardaría un archivo
    truncado.
    """
    posicion = archivo.tell() if hasattr(archivo, "tell") else 0
    try:
        archivo.seek(0)
        return archivo.read(cantidad) or b""
    finally:
        archivo.seek(posicion)


def firma_coincide(archivo, extension):
    """``True`` si el contenido es de verdad del tipo que dice la extensión.

    Una extensión que no está en :data:`FIRMAS` no se puede verificar y se deja
    pasar: quien decide qué extensiones acepta es el formulario, no esto.
    """
    esperadas = FIRMAS.get((extension or "").lower())
    if not esperadas:
        return True
    inicio = cabecera(archivo)
    return any(inicio.startswith(firma) for firma in esperadas)


def validar_firma(archivo, extension, mensaje=None):
    """Levanta ``ValidationError`` si el contenido no es el que promete el nombre."""
    if not firma_coincide(archivo, extension):
        raise ValidationError(mensaje or f"El archivo no es un {extension.lstrip('.').upper()} válido.")


def validar_adjunto(archivo, extensiones=ADJUNTO_EXTENSIONES, max_bytes=ADJUNTO_MAX_BYTES):
    """Extensión, tamaño y firma de un archivo **que se está subiendo** (SEC-15).

    Pensado para ir en ``validators=[...]`` de un ``FileField``: con eso lo
    aplican el ModelForm, el admin y cualquier ``full_clean()``, sin repetir la
    regla en cada formulario.

    **Lo ya guardado no se revalida.** Un ``FieldFile`` que viene del storage
    llega con ``_committed = True``; ahí se sale sin mirar nada. Si no, guardar
    cualquier otro campo de una fila vieja —una solicitud de merendero de 2025
    con un `.docx` adjunto— fallaría con un error sobre un archivo que el
    usuario no tocó, y encima ``.size`` iría al storage a preguntar. Los
    archivos legacy se siguen viendo y descargando; la lista blanca aplica a lo
    que entra de acá en adelante.
    """
    if archivo is None or getattr(archivo, "_committed", False):
        return archivo

    nombre = (getattr(archivo, "name", "") or "").lower()
    extension = Path(nombre).suffix
    if extension not in extensiones:
        raise ValidationError(MENSAJE_ADJUNTO_FORMATO)
    if (getattr(archivo, "size", 0) or 0) > max_bytes:
        raise ValidationError(MENSAJE_ADJUNTO_TAMANIO)
    validar_firma(archivo, extension, MENSAJE_ADJUNTO_FORMATO)
    return archivo
