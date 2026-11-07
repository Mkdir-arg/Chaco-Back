"""Cómo se nombra una plaza en un texto que se guarda o se muestra.

Desde el Cambio 430 el código de una plaza se repite entre sectores (cada sector numera desde
1), así que `01` solo no dice de qué plaza se habla: se escribe «plaza 01 (Pabellón A)», el mismo
formato que ya usa la auditoría. Es el único lugar donde se arma; no se copia en cada servicio.

El sector se lee de `plaza.sector`. Quien ya lo tiene a mano (o lo leyó antes de releer la plaza
con `select_for_update`, que no trae el JOIN) pasa `sector_nombre` y no cuesta ninguna consulta.
"""

import re

_TRAMOS = re.compile(r"(\d+)")


def plaza_con_sector(plaza, sector_nombre=None):
    """«01 (Pabellón A)»: el código y entre paréntesis el sector."""

    if sector_nombre is None:
        sector_nombre = plaza.sector.nombre
    return f"{plaza.codigo} ({sector_nombre})"


def nombre_de_plaza(plaza, sector_nombre=None):
    """«plaza 01 (Pabellón A)»; en minúscula, para insertarlo en una frase."""

    return f"plaza {plaza_con_sector(plaza, sector_nombre)}"


def clave_natural(codigo):
    """Clave de orden natural del código: `98` y `99` van antes que `100`, `B-9` antes que `B-10`.

    Ordenar el texto a secas pondría «100» antes que «98». Los tramos numéricos se comparan como
    números y los demás sin distinguir mayúsculas; el texto va primero para que la tupla sea
    comparable aunque un código empiece con dígitos y otro no.
    """

    return tuple(
        (1, int(tramo), "") if tramo.isdigit() else (0, 0, tramo.casefold()) for tramo in _TRAMOS.split(codigo) if tramo
    )
