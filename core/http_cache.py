"""Cabeceras de caché de las respuestas con datos personales."""


def sin_cache(respuesta):
    """Deja ``Cache-Control: no-store`` (exactamente eso) en la respuesta y la devuelve.

    Para los JSON que llevan nombres o DNI: ni el navegador ni un intermediario los guardan.
    """
    respuesta["Cache-Control"] = "no-store"
    return respuesta
