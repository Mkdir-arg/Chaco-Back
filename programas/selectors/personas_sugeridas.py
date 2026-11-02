"""Sugerencias de personas del Legajo mientras se escribe (Cambio 415).

Lectura pura: devuelve apellido, nombre y DNI, nunca otro dato. La búsqueda es por
**prefijo** (`LIKE 'texto%'`) sobre columnas indexadas —`dni`, `(apellido, nombre)` y `nombre`—,
sin función sobre la columna: así el motor usa el índice en MySQL y en MariaDB. Siempre `istartswith`
(`LIKE`) y nunca `startswith`: en MySQL/MariaDB este último se traduce a `LIKE BINARY`, que recorre
todo el índice (200k filas: 224 ms contra 0,03 ms).
"""

import re

from django.db.models import Q

from core.dni import normalizar_dni
from legajos.models import Ciudadano

MINIMO_CARACTERES = 3
MAXIMO_RESULTADOS = 10
#: Lo que se lee de lo tecleado: más largo que cualquier nombre o DNI, para no armar un WHERE enorme.
MAXIMO_CARACTERES = 100
MAXIMO_PALABRAS = 5

_SOLO_DNI = re.compile(r"[\d.\s]+")


def _filtro(texto):
    """El `Q` del texto: prefijo de DNI si son números, y si no, cada palabra contra apellido o nombre."""

    if _SOLO_DNI.fullmatch(texto):
        digitos = normalizar_dni(texto)
        return Q(dni__istartswith=digitos) if len(digitos) >= MINIMO_CARACTERES else None
    filtro = Q()
    for palabra in texto.replace(",", " ").split()[:MAXIMO_PALABRAS]:
        filtro &= Q(apellido__istartswith=palabra) | Q(nombre__istartswith=palabra)
    return filtro


def sugerir_personas(texto):
    """`{"resultados": [{apellido, nombre, dni}], "hay_mas": bool}` para lo que se lleva tecleado.

    Con menos de 3 caracteres devuelve la lista vacía: el padrón no se recorre. Trae uno más
    que el tope para saber si hay más sin contar.
    """

    texto = (texto or "").strip()[:MAXIMO_CARACTERES].strip()
    vacio = {"resultados": [], "hay_mas": False}
    if len(texto) < MINIMO_CARACTERES:
        return vacio
    filtro = _filtro(texto)
    if filtro is None:
        return vacio
    filas = list(
        Ciudadano.objects.filter(filtro)
        .order_by("apellido", "nombre", "pk")
        .values("apellido", "nombre", "dni")[: MAXIMO_RESULTADOS + 1]
    )
    return {"resultados": filas[:MAXIMO_RESULTADOS], "hay_mas": len(filas) > MAXIMO_RESULTADOS}
