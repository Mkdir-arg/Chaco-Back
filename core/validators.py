"""Validadores de archivos compartidos por las superficies que aceptan uploads.

La extensión la elige quien sube el archivo: no dice nada sobre el contenido.
Donde el upload es **anónimo** —el link público de Becas (SIIS-16)— eso alcanza
para dejar HTML o un script en ``media/``, que después se sirve desde el
backoffice. La firma de los primeros bytes sí es del archivo, y es barata.

Los tres formatos que acepta el trámite son los que la gente saca con el
teléfono o descarga de un organismo: JPG, PNG y PDF. SEC-15 (Ola 2) reusa esto
para F-00 y la solicitud de merendero, que hoy tampoco miran el contenido.
"""

from django.forms import ValidationError

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
