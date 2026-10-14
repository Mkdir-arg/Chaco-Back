"""Imágenes del .zip incrustadas en cada correo (Cambio 292, plan B del 14/10/2026).

El Cambio 285 publicaba las imágenes del .zip en una URL pública de DATAÑACH y el correo las
pedía de ahí. En testing el WAF de ECOM (FortiWeb) bloquea esa ruta desde internet —y PRD tiene
el mismo WAF—, así que el proxy de imágenes de Gmail no las podía bajar y el correo llegaba con
las imágenes rotas. Ahora las imágenes **viajan dentro de cada correo**:

- el HTML guardado referencia cada imagen alojada como ``cid:<nombre>@datanach`` (el nombre
  publicado es único dentro de la campaña), sin ``<>``, que es la forma que entiende Gmail;
- el correo es ``multipart/related [ multipart/alternative [texto, html], imagen1, … ]``: cada
  imagen una sola vez, con ``Content-ID: <nombre@datanach>``, ``Content-Disposition: inline``
  y su tipo real (:func:`partes_mime`);
- la vista previa no puede pedir esas imágenes a una ruta con login (el ``iframe sandbox`` es
  de origen opaco y no manda cookies), así que la respuesta de la vista previa cambia cada
  ``cid:`` por un ``data:`` con la imagen (:func:`html_para_vista_previa`), solo ahí y después
  del saneo.

Los archivos siguen en ``media/notificaciones/imagenes/`` detrás de login (``notificacion.ver``):
no hay ninguna ruta pública.
"""

from __future__ import annotations

import base64
import logging
import re
from email.mime.image import MIMEImage

logger = logging.getLogger(__name__)

#: Dominio de los Content-ID: no tiene que resolver a nada, solo hacerlos únicos y legibles.
DOMINIO_CID = "datanach"
#: Tope del peso total de las imágenes incrustadas de una campaña (ya recodificadas). Cada correo
#: lleva todas: 2 MB de imágenes son ~2,7 MB por correo en base64.
TOPE_BYTES = 2 * 1024 * 1024

#: Sin distinguir mayúsculas, igual que el saneo (``html.quitar_cid_ajenos``), que además deja
#: cada ``cid:`` propio escrito con el nombre exacto.
_SRC_CID = re.compile(r'(\ssrc=")cid:([^"@\s]+)@' + re.escape(DOMINIO_CID) + '(")', re.IGNORECASE)


def cid_de(nombre):
    """El Content-ID de una imagen, sin ``<>``: ``01-logo.png@datanach``."""
    return f"{nombre}@{DOMINIO_CID}"


def src_de(nombre):
    """Lo que va en el ``src`` del HTML guardado: ``cid:01-logo.png@datanach``."""
    return f"cid:{cid_de(nombre)}"


def nombres_referenciados(html):
    """Los nombres publicados que el HTML usa como ``cid:``, sin repetir y en orden de aparición."""
    return list(dict.fromkeys(m.group(2) for m in _SRC_CID.finditer(html or "")))


def imagenes_referenciadas(campana):
    """Las ``ImagenCampana`` de la campaña que el HTML guardado usa, en orden de aparición."""
    nombres = nombres_referenciados(campana.html_sanitizado)
    if not nombres:
        return []
    por_nombre = {imagen.nombre.lower(): imagen for imagen in campana.imagenes.all()}
    vistas = {}
    for nombre in nombres:
        imagen = por_nombre.get(nombre.lower())
        if imagen is not None:
            vistas.setdefault(imagen.pk, imagen)
    return list(vistas.values())


def _bytes_de(imagen):
    """Los bytes guardados de una imagen, o ``None`` si el archivo no está (se loguea)."""
    try:
        imagen.archivo.open("rb")
        try:
            return imagen.archivo.read()
        finally:
            imagen.archivo.close()
    except (FileNotFoundError, OSError, ValueError):
        logger.exception("Campaña %s: no se encontró la imagen %s", imagen.campana_id, imagen.nombre)
        return None


class PartesMime(list):
    """Las partes de imagen de un correo, con los nombres de las que faltan en el disco."""

    def __init__(self, *args):
        super().__init__(*args)
        self.faltantes = []

    @property
    def aviso(self):
        """El aviso para el operador si falta alguna imagen en el servidor, o ``""``."""
        if not self.faltantes:
            return ""
        cantidad = len(self.faltantes)
        return (
            f"Falta{'n' if cantidad > 1 else ''} en el servidor {cantidad} "
            f"{'imágenes' if cantidad > 1 else 'imagen'}: {', '.join(self.faltantes)}; los correos salen sin ellas."
        )


def partes_mime(campana):
    """Una ``MIMEImage`` por imagen referenciada, lista para adjuntar a cada correo.

    Se arma **una vez por corrida** y se reusa en todos los correos: la imagen se lee del disco
    y se pasa a base64 una sola vez, no una por destinatario. Una imagen que falta en el disco no
    frena el envío: ese correo sale sin esa imagen, queda en el log y en ``faltantes``, que el
    envío masivo deja en ``campana.mensaje`` y la prueba en su aviso (:attr:`PartesMime.aviso`).
    """
    partes = PartesMime()
    for imagen in imagenes_referenciadas(campana):
        contenido = _bytes_de(imagen)
        if contenido is None:
            partes.faltantes.append(imagen.nombre)
            continue
        parte = MIMEImage(contenido, _subtype=imagen.content_type.split("/", 1)[1])
        parte.add_header("Content-ID", f"<{cid_de(imagen.nombre)}>")
        parte.add_header("Content-Disposition", "inline", filename=imagen.nombre)
        partes.append(parte)
    return partes


def html_para_vista_previa(campana):
    """El HTML saneado con cada ``cid:`` propio cambiado por un ``data:`` de la imagen.

    Solo para la respuesta de la vista previa (su CSP admite ``img-src data:``). En el HTML que
    sube el operador ``data:`` sigue prohibido: lo quita el saneo.
    """
    html = campana.html_sanitizado
    datos = {}
    for imagen in imagenes_referenciadas(campana):
        contenido = _bytes_de(imagen)
        if contenido is not None:
            datos[imagen.nombre.lower()] = (
                f"data:{imagen.content_type};base64,{base64.b64encode(contenido).decode('ascii')}"
            )

    def reemplazo(match):
        uri = datos.get(match.group(2).lower())
        return f"{match.group(1)}{uri}{match.group(3)}" if uri else match.group(0)

    return _SRC_CID.sub(reemplazo, html)


def peso_aproximado(campana):
    """Bytes aproximados de cada correo: HTML + texto + las imágenes referenciadas en base64."""
    from notificaciones.services.html import documento

    imagenes = sum(-(-imagen.tamano // 3) * 4 for imagen in imagenes_referenciadas(campana))
    return len(documento(campana.html_sanitizado).encode("utf-8")) + len(campana.texto_plano.encode("utf-8")) + imagenes
