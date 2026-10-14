"""El cuerpo de una campaña subido como .zip: el HTML y sus imágenes (Cambios 285 y 292).

A los operadores les llega el mailing como una **carpeta**: ``mailing.html`` + ``img/*.png``
con ``src="img/foto.jpg"``. Subido solo el HTML, esas imágenes no existen en ningún servidor y
no se ven. Acá se abre el .zip, se elige el HTML, se resuelve cada ``src`` relativo contra los
archivos del paquete, se validan las imágenes con Pillow y se reescribe cada ``src`` a
``cid:<nombre>@datanach``: la imagen **viaja incrustada en cada correo**
(:mod:`notificaciones.services.incrustadas`). El saneo viene después, en
:func:`notificaciones.services.html.procesar_texto`: el orden es extraer → reescribir → sanear,
y el saneo admite el esquema ``cid`` solo para las imágenes de este paquete.

Hasta el Cambio 292 el ``src`` era una URL pública de DATAÑACH: el WAF de ECOM la bloquea desde
internet y el proxy de imágenes de Gmail no podía bajarlas.

Lo que se rechaza con error (el .zip no se acepta):

- más de :data:`ZIP_MAX_BYTES` comprimido, más de :data:`DESCOMPRIMIDO_MAX_BYTES` descomprimido
  en total o un archivo que necesitamos leer más grande que su tope (la bomba de compresión: el
  tamaño se controla con lo declarado **y** leyendo con techo, porque el encabezado puede mentir);
- una entrada con ``..``, ruta absoluta, unidad de Windows, enlace simbólico o cifrada;
- más de :data:`MAX_IMAGENES` imágenes o más de :data:`MAX_ENTRADAS` archivos;
- ningún HTML, o más de uno sin un ``index.html`` en la raíz del paquete;
- imágenes publicables que, ya recodificadas, pesan más de ``incrustadas.TOPE_BYTES`` (2 MB) en
  total: cada correo las lleva todas.

Lo que no se publica pero no frena (va a los avisos de la previsualización): una imagen que el
HTML nombra y no vino (**faltante**) y una que vino pero no es PNG, JPG, GIF ni WEBP de verdad
—SVG incluido, que puede llevar scripts— (**rechazada**), igual que una de más de
:data:`MAX_PIXELES` píxeles. Las imágenes del paquete que el HTML no nombra se ignoran.

Lo que se publica **no son los bytes que vinieron**: cada imagen se vuelve a codificar con Pillow
en su mismo formato (:func:`_recodificar`). Así no sale a internet nada que no sea la imagen: ni
el EXIF de la cámara (la ubicación GPS, el aparato, la fecha), ni XMP, ni los textos de un PNG o
el comentario de un GIF, ni lo que un archivo políglota traiga pegado atrás. Se conserva el
perfil de color ICC (no identifica a nadie y sin él los colores cambian), la transparencia y la
animación de GIF y WEBP. JPEG se recodifica con calidad 90 y aplicando antes la orientación del
EXIF, para que la foto no quede girada al perderlo.
"""

from __future__ import annotations

import html as html_lib
import io
import posixpath
import re
import secrets
import stat
import warnings
import zipfile
from dataclasses import dataclass, field
from urllib.parse import unquote

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

from notificaciones.services import incrustadas

ZIP_MAX_BYTES = 10 * 1024 * 1024
DESCOMPRIMIDO_MAX_BYTES = 20 * 1024 * 1024
IMAGEN_MAX_BYTES = 5 * 1024 * 1024
MAX_IMAGENES = 50
#: Píxeles por imagen (ancho × alto). Un PNG de pocos KB puede declarar 100.000 × 100.000: se
#: corta antes de decodificarlo. 25 millones es una foto de cámara de 25 MP, más que cualquier
#: correo.
MAX_PIXELES = 25_000_000
#: Calidad de la recodificación de JPEG (y de WEBP con pérdida).
CALIDAD = 90
MAX_ENTRADAS = 500
EXTENSIONES_ZIP = (".zip",)
EXTENSIONES_HTML = (".html", ".htm")
#: Extensiones que cuentan como imagen para el tope (SVG incluido: cuenta, aunque no se publique).
EXTENSIONES_IMAGEN = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff")
#: Formato real (``Image.format``) → tipo y extensión con que se publica.
FORMATOS = {
    "PNG": ("image/png", "png"),
    "JPEG": ("image/jpeg", "jpg"),
    "GIF": ("image/gif", "gif"),
    "WEBP": ("image/webp", "webp"),
}
#: Basura de los sistemas operativos: no es contenido del mailing.
_IGNORADOS = {".ds_store", "thumbs.db", "desktop.ini"}
_UNIDAD_WINDOWS = re.compile(r"^[A-Za-z]:")
_IMG_SRC = re.compile(r"(<img\b[^>]*?\ssrc\s*=\s*)(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)
_NO_RELATIVAS = ("http://", "https://", "//", "cid:", "data:", "mailto:", "javascript:", "about:", "blob:")
_SEGMENTO_URL = re.compile(r"[^A-Za-z0-9_-]+")

MOTIVO_SVG = "SVG no se admite"
MOTIVO_NO_IMAGEN = "no es una imagen PNG, JPG, GIF o WEBP válida"
MOTIVO_GRANDE = f"supera {IMAGEN_MAX_BYTES // (1024 * 1024)} MB"
MOTIVO_PIXELES = f"supera {MAX_PIXELES // 1_000_000} millones de píxeles"


@dataclass
class ImagenExtraida:
    """Una imagen del paquete que el HTML usa y que se va a publicar."""

    nombre: str
    ruta_original: str
    contenido: bytes
    content_type: str

    @property
    def tamano(self):
        return len(self.contenido)


@dataclass
class PaqueteLeido:
    """El HTML del paquete con los ``src`` ya reescritos, y lo que hay que publicar y avisar."""

    html: str
    nombre_html: str
    token: str
    imagenes: list[ImagenExtraida] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)
    rechazadas: list[str] = field(default_factory=list)
    #: ``<img>`` que apuntan a una faltante o a una rechazada: ya se avisan por nombre, así que
    #: no se cuentan otra vez como «no visibles».
    referencias_sin_publicar: int = 0


def es_zip(archivo):
    return (getattr(archivo, "name", "") or "").lower().endswith(EXTENSIONES_ZIP)


def _mb(n):
    return f"{n // (1024 * 1024)} MB"


# ---------------------------------------------------------------------------
# Entradas del .zip
# ---------------------------------------------------------------------------
def _nombre_normalizado(info):
    """La ruta de la entrada con ``/``, o ``ValidationError`` si sale del paquete."""
    crudo = info.filename
    if "\x00" in crudo:
        raise ValidationError("El .zip trae un nombre de archivo inválido.")
    nombre = crudo.replace("\\", "/")
    partes = [p for p in nombre.split("/") if p not in ("", ".")]
    if nombre.startswith("/") or _UNIDAD_WINDOWS.match(nombre) or ".." in partes:
        raise ValidationError(
            f"El .zip trae una ruta no permitida: «{crudo[:120]}». Comprimí solo la carpeta del correo."
        )
    return "/".join(partes)


def _es_symlink(info):
    return stat.S_ISLNK(info.external_attr >> 16)


def _ignorado(nombre):
    partes = nombre.split("/")
    return partes[0].lower() == "__macosx" or partes[-1].lower() in _IGNORADOS or partes[-1].startswith("._")


def _entradas(zf):
    """``{ruta normalizada: ZipInfo}`` de los archivos que importan, con los topes del paquete."""
    infos = zf.infolist()
    if len(infos) > MAX_ENTRADAS:
        raise ValidationError(f"El .zip trae más de {MAX_ENTRADAS} archivos: comprimí solo la carpeta del correo.")
    entradas = {}
    declarado = 0
    imagenes = 0
    for info in infos:
        if info.is_dir():
            continue
        nombre = _nombre_normalizado(info)
        if not nombre or _ignorado(nombre):
            continue
        if _es_symlink(info):
            raise ValidationError(f"El .zip trae un enlace simbólico («{nombre[:120]}»): no se admite.")
        if info.flag_bits & 0x1:
            raise ValidationError("El .zip está protegido con contraseña: subilo sin cifrar.")
        declarado += info.file_size
        if declarado > DESCOMPRIMIDO_MAX_BYTES:
            raise ValidationError(f"El contenido del .zip descomprimido supera {_mb(DESCOMPRIMIDO_MAX_BYTES)}.")
        if nombre.lower().endswith(EXTENSIONES_IMAGEN):
            imagenes += 1
            if imagenes > MAX_IMAGENES:
                raise ValidationError(f"El .zip trae más de {MAX_IMAGENES} imágenes.")
        entradas[nombre] = info
    return entradas


def _leer(zf, info, tope, mensaje):
    """Los bytes de la entrada, leyendo con techo: el tamaño declarado puede mentir."""
    if info.file_size > tope:
        raise ValidationError(mensaje)
    try:
        with zf.open(info) as fuente:
            datos = fuente.read(tope + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError, EOFError) as exc:
        raise ValidationError("no se pudo leer del .zip") from exc
    if len(datos) > tope:
        raise ValidationError(mensaje)
    return datos


# ---------------------------------------------------------------------------
# El HTML
# ---------------------------------------------------------------------------
def _carpeta_raiz(nombres):
    """La carpeta que contiene todo el paquete («mailing/» al comprimir la carpeta), o ``""``."""
    primeras = {n.split("/", 1)[0] for n in nombres}
    if len(primeras) == 1 and all("/" in n for n in nombres):
        return primeras.pop() + "/"
    return ""


def _elegir_html(entradas):
    """Exactamente un HTML; con varios, el ``index.html`` de la raíz del paquete."""
    htmls = sorted(n for n in entradas if n.lower().endswith(EXTENSIONES_HTML))
    if not htmls:
        raise ValidationError("El .zip no trae ningún archivo .html.")
    if len(htmls) == 1:
        return htmls[0]
    raiz = _carpeta_raiz(list(entradas))
    indices = [n for n in htmls if n.lower() == f"{raiz}index.html".lower()]
    if len(indices) == 1:
        return indices[0]
    muestra = ", ".join(posixpath.basename(n) for n in htmls[:5])
    raise ValidationError(
        f"El .zip trae {len(htmls)} archivos HTML ({muestra}). Tiene que traer uno solo, "
        "o un index.html en la raíz de la carpeta."
    )


def _decodificar(crudo):
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("El HTML del .zip tiene que estar guardado en UTF-8.") from exc
    if not texto.strip():
        raise ValidationError("El HTML del .zip está vacío.")
    return texto


# ---------------------------------------------------------------------------
# Las imágenes
# ---------------------------------------------------------------------------
def _ruta_relativa(src):
    """El ``src`` como ruta del paquete (sin resolver), o ``None`` si no es relativo."""
    valor = html_lib.unescape(src or "").strip()
    if not valor or valor.lower().startswith(_NO_RELATIVAS):
        return None
    valor = valor.split("#", 1)[0].split("?", 1)[0]
    valor = unquote(valor).replace("\\", "/")
    return valor or None


def _resolver(relativa, carpeta_html, raiz):
    """La ruta del paquete a la que apunta ``relativa``, o ``None`` si se sale del paquete."""
    if relativa.startswith("/"):
        # «/img/x.png»: la raíz del sitio del diseñador es la raíz del paquete.
        base, relativa = raiz, relativa.lstrip("/")
    else:
        base = carpeta_html
    destino = posixpath.normpath(posixpath.join(base, relativa)) if base else posixpath.normpath(relativa)
    if destino in (".", "..") or destino.startswith("../") or destino.startswith("/"):
        return None
    return destino


def _buscar(destino, entradas, sin_mayusculas):
    """La entrada exacta y, si no, la misma ruta sin distinguir mayúsculas (diseño en Windows)."""
    if destino in entradas:
        return destino
    return sin_mayusculas.get(destino.casefold())


def _abrir(datos):
    """La imagen abierta, con las alarmas de bomba de descompresión convertidas en error."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        return Image.open(io.BytesIO(datos))


def _recodificar(imagen, formato):
    """Los bytes de la imagen vueltos a codificar, sin metadatos (ver el docstring del módulo)."""
    animada = formato in ("GIF", "WEBP") and getattr(imagen, "is_animated", False)
    opciones = {"format": formato}
    icc = imagen.info.get("icc_profile")
    if icc and formato != "GIF":
        opciones["icc_profile"] = icc
    if formato == "JPEG":
        imagen = ImageOps.exif_transpose(imagen)
        if imagen.mode not in ("RGB", "L", "CMYK"):
            imagen = imagen.convert("RGB")
        opciones.update(quality=CALIDAD, optimize=True)
    elif formato == "PNG":
        imagen = ImageOps.exif_transpose(imagen)
        if "transparency" in imagen.info:
            opciones["transparency"] = imagen.info["transparency"]
        opciones["optimize"] = True
    elif formato == "GIF":
        opciones.update(save_all=animada, comment=b"")
    elif formato == "WEBP":
        opciones.update(save_all=animada, quality=CALIDAD, exif=b"", xmp=b"")
    # Lo que Pillow leyó y podría volver a escribir por su cuenta.
    for clave in ("exif", "xmp", "XML:com.adobe.xmp", "comment", "extension"):
        imagen.info.pop(clave, None)
    salida = io.BytesIO()
    imagen.save(salida, **opciones)
    return salida.getvalue()


def _limpiar_imagen(nombre, datos):
    """``(bytes recodificados, content_type, extensión), None`` si se publica; si no, ``None, motivo``.

    PNG/JPG/GIF/WEBP de verdad (por contenido, no por extensión), hasta :data:`MAX_PIXELES`.
    """
    if nombre.lower().endswith(".svg") or datos.lstrip()[:5].lower() in (b"<?xml", b"<svg ", b"<svg>"):
        return None, MOTIVO_SVG
    try:
        with _abrir(datos) as imagen:
            formato = imagen.format
            ancho, alto = imagen.size
            if formato not in FORMATOS:
                return None, MOTIVO_NO_IMAGEN
            if ancho * alto > MAX_PIXELES:
                return None, MOTIVO_PIXELES
            imagen.verify()
        # ``verify`` deja la imagen inutilizable: se vuelve a abrir para recodificarla.
        with _abrir(datos) as imagen:
            limpia = _recodificar(imagen, formato)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return None, MOTIVO_PIXELES
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError, TypeError):
        return None, MOTIVO_NO_IMAGEN
    if len(limpia) > IMAGEN_MAX_BYTES:
        return None, MOTIVO_GRANDE
    content_type, extension = FORMATOS[formato]
    return (limpia, content_type, extension), None


def _nombre_publicado(orden, ruta, extension):
    base = posixpath.splitext(posixpath.basename(ruta))[0]
    limpio = _SEGMENTO_URL.sub("-", base).strip("-")[:60] or "imagen"
    return f"{orden:02d}-{limpio}.{extension}"


def leer_paquete(archivo):
    """Abre el .zip subido y devuelve el :class:`PaqueteLeido`. Levanta ``ValidationError``."""
    from notificaciones.services.html import HTML_MAX_BYTES

    if (getattr(archivo, "size", 0) or 0) > ZIP_MAX_BYTES:
        raise ValidationError(f"El .zip no puede superar {_mb(ZIP_MAX_BYTES)}.")
    archivo.seek(0)
    try:
        zf = zipfile.ZipFile(archivo)
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        raise ValidationError("El archivo .zip está dañado o no es un .zip.") from exc
    try:
        entradas = _entradas(zf)
        nombre_html = _elegir_html(entradas)
        texto = _decodificar(
            _leer(zf, entradas[nombre_html], HTML_MAX_BYTES, "El HTML del .zip no puede superar 1 MB.")
        )
        token = secrets.token_urlsafe(24)
        carpeta_html = posixpath.dirname(nombre_html)
        raiz = _carpeta_raiz(list(entradas)).rstrip("/")
        sin_mayusculas = {}
        for nombre in sorted(entradas):
            sin_mayusculas.setdefault(nombre.casefold(), nombre)

        paquete = PaqueteLeido(html="", nombre_html=nombre_html, token=token)
        publicadas = {}  # ruta del paquete → src «cid:»
        avisadas = set()

        def reescribir(match):
            src = next((g for g in match.groups()[1:] if g is not None), "")
            relativa = _ruta_relativa(src)
            if relativa is None:
                return match.group(0)
            destino = _resolver(relativa, carpeta_html, raiz)
            encontrada = _buscar(destino, entradas, sin_mayusculas) if destino else None
            if encontrada is None:
                paquete.referencias_sin_publicar += 1
                if relativa not in avisadas:
                    avisadas.add(relativa)
                    paquete.faltantes.append(relativa)
                return match.group(0)
            if encontrada not in publicadas:
                publicadas[encontrada] = _publicar(zf, entradas[encontrada], encontrada, paquete)
            url = publicadas[encontrada]
            if url is None:
                paquete.referencias_sin_publicar += 1
                return match.group(0)
            return f'{match.group(1)}"{url}"'

        paquete.html = _IMG_SRC.sub(reescribir, texto)
        _controlar_peso(paquete)
        return paquete
    finally:
        zf.close()


def _publicar(zf, info, ruta, paquete):
    """Valida la imagen y la suma al paquete. Devuelve su ``src`` «cid:» o ``None`` si no va."""
    try:
        datos = _leer(zf, info, IMAGEN_MAX_BYTES, MOTIVO_GRANDE)
    except ValidationError as exc:
        # Una imagen grande o ilegible no tumba el paquete: no se publica y se avisa.
        paquete.rechazadas.append(f"{ruta} ({exc.messages[0]})")
        return None
    limpia, motivo = _limpiar_imagen(ruta, datos)
    if limpia is None:
        paquete.rechazadas.append(f"{ruta} ({motivo})")
        return None
    contenido, content_type, extension = limpia
    nombre = _nombre_publicado(len(paquete.imagenes) + 1, ruta, extension)
    paquete.imagenes.append(
        ImagenExtraida(nombre=nombre, ruta_original=ruta[:255], contenido=contenido, content_type=content_type)
    )
    return incrustadas.src_de(nombre)


def _controlar_peso(paquete):
    """Las imágenes publicables, sumadas, no pasan el tope: cada correo las lleva todas."""
    total = sum(imagen.tamano for imagen in paquete.imagenes)
    if total > incrustadas.TOPE_BYTES:
        raise ValidationError(
            f"Las imágenes del .zip pesan {total / (1024 * 1024):.1f} MB en total y viajan dentro de cada "
            f"correo: el tope es {incrustadas.TOPE_BYTES // (1024 * 1024)} MB. Achicalas o sacá alguna."
        )
