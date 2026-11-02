"""Contrato de `nodo-sugerencias.js` del lado de los formularios Django (Cambio 415).

Cualquier campo de texto que quiera sugerencias de personas pone `attrs_sugerencias(url)` en
los `attrs` de su widget. Sin la URL no agrega nada y el campo queda como siempre.
"""

#: Lo que dice el desplegable cuando lo tecleado no coincide con nadie.
MENSAJE_SUGERENCIA_SIN_PERSONA = "No encontramos a nadie: dala de alta desde Ingresar persona."
#: El paso «Ingresar persona» ya es la pantalla del alta: no manda a ella.
MENSAJE_SUGERENCIA_SIN_PERSONA_EN_INGRESO = "No encontramos a nadie: buscá el DNI para darla de alta."
MENSAJE_SUGERENCIA_HAY_MAS = "Hay más resultados: escribí más datos."


def attrs_sugerencias(url, vacio=None):
    """Los `data-sugerencias-*` que lee `static/custom/js/nodo-sugerencias.js`, o `{}` sin URL.

    `vacio`: el aviso cuando nadie coincide, si la pantalla necesita otro que el de siempre.
    """

    if not url:
        return {}
    return {
        "data-sugerencias-url": url,
        "data-sugerencias-vacio": vacio or MENSAJE_SUGERENCIA_SIN_PERSONA,
        "data-sugerencias-hay-mas": MENSAJE_SUGERENCIA_HAY_MAS,
    }
