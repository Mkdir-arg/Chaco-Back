"""El cuerpo HTML de una campaña: validación, saneo y texto plano (RNF-007-03, RN-007-07/08/13).

El HTML lo diseña alguien afuera del sistema y lo sube el operador. Se sanea **al
subirlo** con ``nh3`` (el binding de ``ammonia``) y lo que se guarda, se previsualiza y
se envía es siempre la copia saneada:

- fuera ``<script>``, ``<iframe>``, ``<object>``, ``<embed>``, ``<form>`` y sus controles,
  ``<meta>``/``<link>``/``<base>``, los manejadores ``on*`` y los enlaces ``javascript:``;
- se conservan las tablas, los estilos en línea y el ``<style>`` del ``<head>``, que es como
  se arma un correo (los clientes de correo los admiten parcialmente), pero al CSS se le
  sacan ``@import`` y toda declaración con ``url(…)``, ``expression(…)``, ``behavior`` o
  ``-moz-binding``: cargarían recursos o código de afuera;
- las imágenes solo quedan con ``src`` ``http(s)://``: ``cid:``, rutas relativas y ``data:``
  pierden el ``src`` y se cuentan para el aviso de la previsualización.

La vista previa además va en un ``iframe`` con ``sandbox`` vacío y una CSP propia
(``views.campanas.vista_previa_html``): el saneo no es la única barrera.
"""

from __future__ import annotations

import html as html_lib
import re

import nh3
from django.core.exceptions import ValidationError

HTML_MAX_BYTES = 1024 * 1024
EXTENSIONES_HTML = (".html", ".htm")

ETIQUETAS = frozenset(nh3.ALLOWED_TAGS) | {
    "style",
    "font",
    "tfoot",
    "section",
    "main",
    "address",
    "big",
}
#: Se van con todo su contenido: lo de adentro no es texto para la persona.
ETIQUETAS_SIN_CONTENIDO = {"script", "title", "iframe", "object", "embed", "noscript", "applet"}
ATRIBUTOS_GENERICOS = {
    "style",
    "class",
    "id",
    "align",
    "valign",
    "width",
    "height",
    "bgcolor",
    "border",
    "cellpadding",
    "cellspacing",
    "dir",
    "lang",
    "title",
    "role",
}
ATRIBUTOS = {
    "*": ATRIBUTOS_GENERICOS,
    "a": {"href", "target", "name"},
    "img": {"src", "alt"},
    "td": {"colspan", "rowspan", "nowrap"},
    "th": {"colspan", "rowspan", "nowrap", "scope"},
    "font": {"color", "face", "size"},
    "table": {"summary"},
    "ol": {"start", "type"},
    "ul": {"type"},
}
ESQUEMAS_URL = {"http", "https", "mailto", "tel"}

# Lo que el saneo quita y conviene contarle al operador (el mock-up: «se quitó 1 bloque
# <script>»). Se cuenta sobre el original, antes de sanear.
_PELIGROSOS = re.compile(r"<\s*(script|iframe|object|embed|form|applet)\b", re.IGNORECASE)
_EVENTOS = re.compile(r"<[^>]*?\son[a-z]+\s*=", re.IGNORECASE)
_JAVASCRIPT = re.compile(r"(?:href|src)\s*=\s*[\"']?\s*javascript:", re.IGNORECASE)
_IMG_SRC = re.compile(r"<img\b[^>]*?\ssrc\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)

# CSS: lo que carga recursos o código de afuera. Se descarta la declaración entera.
_CSS_COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_IMPORT = re.compile(r"@import\b[^;]*;?", re.IGNORECASE)
_CSS_PELIGROSO = re.compile(
    r"[^;{}]*(?:\burl\s*\(|\bexpression\s*\(|\bbehavior\s*:|-moz-binding)[^;{}]*;?", re.IGNORECASE
)
_ATRIBUTO_STYLE = re.compile(r'style="([^"]*)"')
_BLOQUE_STYLE = re.compile(r"(<style\b[^>]*>)(.*?)(</style>)", re.IGNORECASE | re.DOTALL)

# Para el texto plano: los cortes de bloque pasan a salto de línea y los enlaces llevan
# su dirección entre paréntesis, que es lo que el lector de texto plano necesita.
_CORTES = re.compile(r"<\s*(br|/p|/div|/tr|/h[1-6]|/li|/table|/blockquote|hr)\b[^>]*>", re.IGNORECASE)
_ENLACE = re.compile(r"<a\b[^>]*?\shref=\"([^\"]+)\"[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)


def leer_html(archivo):
    """Valida el archivo subido y devuelve su texto (RN-007-07).

    ``.html``/``.htm``, hasta 1 MB y UTF-8 (con o sin BOM). Levanta ``ValidationError``.
    """
    nombre = (getattr(archivo, "name", "") or "").lower()
    if not nombre.endswith(EXTENSIONES_HTML):
        raise ValidationError("El cuerpo del correo tiene que ser un archivo .html.")
    if (getattr(archivo, "size", 0) or 0) > HTML_MAX_BYTES:
        raise ValidationError("El archivo HTML no puede superar 1 MB.")
    archivo.seek(0)
    crudo = archivo.read()
    archivo.seek(0)
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValidationError("El archivo HTML tiene que estar guardado en UTF-8.") from exc
    if not texto.strip():
        raise ValidationError("El archivo HTML está vacío.")
    return texto


def limpiar_css(css):
    """El CSS sin ``@import`` ni declaraciones que carguen algo (``url(``, ``expression(``…).

    Se sacan antes los comentarios y las barras invertidas, que son la forma de esconder
    esas palabras (``ur/**/l(``, ``u\\72l(``); un correo no las necesita.
    """
    css = _CSS_COMENTARIO.sub("", css).replace("\\", "")
    css = _CSS_IMPORT.sub("", css)
    return _CSS_PELIGROSO.sub("", css)


def _limpiar_atributo_style(match):
    limpio = limpiar_css(html_lib.unescape(match.group(1)))
    return f'style="{html_lib.escape(limpio, quote=True)}"'


def _limpiar_bloque_style(match):
    return f"{match.group(1)}{limpiar_css(match.group(2))}{match.group(3)}"


def sanitizar(html):
    """El HTML sin nada que ejecute código ni cargue contenido incrustado."""
    limpio = nh3.clean(
        html,
        tags=set(ETIQUETAS),
        clean_content_tags=set(ETIQUETAS_SIN_CONTENIDO),
        attributes={etiqueta: set(attrs) for etiqueta, attrs in ATRIBUTOS.items()},
        url_schemes=set(ESQUEMAS_URL),
        strip_comments=True,
    )
    # El CSS se limpia sobre la salida de nh3, que siempre escribe los atributos con
    # comillas dobles y deja el contenido de <style> como texto crudo.
    limpio = _ATRIBUTO_STYLE.sub(_limpiar_atributo_style, limpio)
    limpio = _BLOQUE_STYLE.sub(_limpiar_bloque_style, limpio)
    return limpio.strip()


def contar_quitados(html_original):
    """Cuántas cosas inseguras traía el original (etiquetas, eventos ``on*`` y ``javascript:``)."""
    return (
        len(_PELIGROSOS.findall(html_original))
        + len(_EVENTOS.findall(html_original))
        + len(_JAVASCRIPT.findall(html_original))
    )


def contar_imagenes_no_visibles(html_original):
    """Imágenes cuyo ``src`` no es una URL absoluta ``http(s)://`` (RN-007-08).

    Relativas, ``cid:`` y ``data:``: el saneo les saca el ``src`` (no se adjuntan archivos
    y ``data:`` no está entre los esquemas permitidos), así que no le llegan a nadie y la
    previsualización lo avisa.
    """
    total = 0
    for match in _IMG_SRC.finditer(html_original):
        src = next((g for g in match.groups() if g is not None), "").strip().lower()
        if not src.startswith(("https://", "http://")):
            total += 1
    return total


def a_texto(html_sanitizado):
    """La alternativa en texto plano del correo, derivada del HTML ya saneado."""
    con_enlaces = _ENLACE.sub(lambda m: f"{m.group(2)} ({m.group(1)})", html_sanitizado)
    con_cortes = _CORTES.sub("\n", con_enlaces)
    plano = nh3.clean(con_cortes, tags=set(), clean_content_tags={"style", "script", "title"})
    plano = html_lib.unescape(plano)
    lineas = [" ".join(linea.split()) for linea in plano.splitlines()]
    texto = "\n".join(lineas)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def documento(html_sanitizado):
    """El documento completo que se envía y se previsualiza.

    El saneo trabaja sobre un fragmento (descarta ``<html>``, ``<head>`` y ``<body>``),
    así que se vuelve a envolver con la codificación declarada.
    """
    return (
        '<!DOCTYPE html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n'
        f"<body>\n{html_sanitizado}\n</body>\n</html>\n"
    )


def procesar(archivo):
    """Lee, valida y sanea el HTML subido. Devuelve el dict que se guarda en la campaña."""
    original = leer_html(archivo)
    saneado = sanitizar(original)
    if not saneado:
        raise ValidationError("Después de quitar el contenido inseguro, el HTML quedó vacío.")
    return {
        "html_sanitizado": saneado,
        "texto_plano": a_texto(saneado),
        "elementos_quitados": contar_quitados(original),
        "imagenes_no_visibles": contar_imagenes_no_visibles(original),
    }
