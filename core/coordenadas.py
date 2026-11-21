"""Latitud y longitud cargadas en el backoffice: un solo rango y una sola regla de par.

La pieza `components/_ubicacion_domicilio.html` completa las coordenadas desde el mapa, pero
«Cargar coordenadas a mano» deja escribir cualquier cosa, y `DECIMAL(9,6)` admite 999,999999.
Cambio 493: el legajo del ciudadano y el Formulario 1 de Emergencia validan con esto, en vez de
repetir los límites en cada form.
"""

from urllib.parse import quote

from django.core.validators import MaxValueValidator, MinValueValidator

MENSAJE_LATITUD = "La latitud va de -90 a 90."
MENSAJE_LONGITUD = "La longitud va de -180 a 180."
MENSAJE_PAR = "Cargá latitud y longitud, o ninguna de las dos."

VALIDADORES_LATITUD = [MinValueValidator(-90, MENSAJE_LATITUD), MaxValueValidator(90, MENSAJE_LATITUD)]
VALIDADORES_LONGITUD = [MinValueValidator(-180, MENSAJE_LONGITUD), MaxValueValidator(180, MENSAJE_LONGITUD)]


def exigir_par(form, latitud="latitud", longitud="longitud"):
    """Error en ``latitud`` si llegó una sola de las dos: un punto a medias no ubica nada."""

    datos = form.cleaned_data
    if latitud in form.errors or longitud in form.errors:
        return
    if (datos.get(latitud) is None) != (datos.get(longitud) is None):
        form.add_error(latitud, MENSAJE_PAR)


def url_en_google_maps(latitud, longitud):
    """Enlace que abre el punto en Google Maps, fuera del sistema (URL pública de Maps, sin key).

    Es el único lugar que arma el enlace: lo usan `components/_ubicacion.html` (tag `url_google_maps`) y el lugar de
    la toma de Becas. ``None`` si falta alguna de las dos. Va con punto decimal y 6 decimales, nunca con la coma local.
    """

    if latitud is None or longitud is None or latitud == "" or longitud == "":
        return None
    return f"https://www.google.com/maps/search/?api=1&query={float(latitud):.6f},{float(longitud):.6f}"


def url_domicilio_en_google_maps(direccion, localidad="", provincia="Chaco"):
    """Enlace que busca un domicilio escrito (no un punto) en Google Maps, fuera del sistema.

    Para cuando las coordenadas guardadas no son las del domicilio: en un caso de Emergencia la latitud y la
    longitud son de dónde se tomó el caso, y la familia vive en la dirección y la localidad cargadas. Busca
    «dirección, localidad, provincia, Argentina», como la pieza `_ubicacion_domicilio.html`. ``None`` sin dirección.
    """

    direccion = str(direccion or "").strip()
    if not direccion:
        return None
    partes = [direccion, str(localidad or "").strip(), provincia, "Argentina"]
    consulta = ", ".join(parte for parte in partes if parte)
    return f"https://www.google.com/maps/search/?api=1&query={quote(consulta, safe='')}"
