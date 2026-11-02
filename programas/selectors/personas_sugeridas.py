"""Sugerencias de personas del Legajo mientras se escribe (Cambio 415).

Lectura pura: devuelve apellido, nombre y DNI, nunca otro dato. La búsqueda es por
**prefijo** (`LIKE 'texto%'`) sobre columnas indexadas —`dni`, `(apellido, nombre)` y `nombre`—,
sin función sobre la columna: así el motor usa el índice en MySQL y en MariaDB. Siempre `istartswith`
(`LIKE`) y nunca `startswith`: en MySQL/MariaDB este último se traduce a `LIKE BINARY`, que recorre
todo el índice (200k filas: 224 ms contra 0,03 ms).
"""

import re
import unicodedata

from django.db.models import Q

from core.dni import normalizar_dni
from legajos.models import Ciudadano
from users.services.busqueda import normalizar_tecleado, palabras_del_tecleado, q_prefijo_por_palabras

MINIMO_CARACTERES = 3
MAXIMO_RESULTADOS = 10

_SOLO_DNI = re.compile(r"[\d.\s]+")


def _filtros(texto):
    """Los `Q` que se consultan por separado y se unen en Python; lista vacía si no hay qué buscar.

    Números: uno solo, prefijo de DNI. Palabras: la primera es prefijo de apellido **o** de nombre, y cada
    una de las demás también. Ese OR de la primera se parte en dos consultas, una por columna: el
    `OR` entre dos columnas lo resuelve MySQL con `index_merge` y, con un prefijo común (`gar`, `mar`),
    ordena todo lo que coincide antes de cortar en 11 (200k filas: 51 ms contra 0,7 ms por columna).
    """

    if _SOLO_DNI.fullmatch(texto):
        digitos = normalizar_dni(texto)
        return [Q(dni__istartswith=digitos)] if len(digitos) >= MINIMO_CARACTERES else []
    palabras = palabras_del_tecleado(texto)
    if not palabras:
        return []
    resto = q_prefijo_por_palabras(palabras[1:], "apellido", "nombre")
    primera = palabras[0]
    return [Q(apellido__istartswith=primera) & resto, Q(nombre__istartswith=primera) & resto]


def _clave_de_orden(fila):
    """Apellido y nombre como los ordena la base (collation `_ai_ci`: sin tildes ni mayúsculas), y el id.

    Cada consulta ya viene ordenada por el motor; al unir las dos hay que ordenar igual, o «Ávila», «acosta» y
    «Benítez» salen en otro orden y con más de 10 coincidencias cambia quién entra al tope. No se une en la base
    (`union` con `LIMIT` en cada parte) porque SQLite no lo admite.
    """

    def plano(texto):
        return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().casefold()

    return (plano(fila["apellido"]), plano(fila["nombre"]), fila["pk"])


def sugerir_personas(texto):
    """`{"resultados": [{apellido, nombre, dni}], "hay_mas": bool}` para lo que se lleva tecleado.

    Con menos de 3 caracteres devuelve la lista vacía: el padrón no se recorre. Trae uno más
    que el tope para saber si hay más sin contar. Cada `Q` de `_filtros` es una consulta con su
    tope; se unen sin repetir, en el orden de la base (apellido, nombre, id; ver `_clave_de_orden`), y se corta en el tope.
    """

    texto = normalizar_tecleado(texto)
    vacio = {"resultados": [], "hay_mas": False}
    if len(texto) < MINIMO_CARACTERES:
        return vacio
    filas = {}
    for filtro in _filtros(texto):
        consulta = (
            Ciudadano.objects.filter(filtro)
            .order_by("apellido", "nombre", "pk")
            .values("pk", "apellido", "nombre", "dni")[: MAXIMO_RESULTADOS + 1]
        )
        for fila in consulta:
            filas[fila["pk"]] = fila
    ordenadas = sorted(filas.values(), key=_clave_de_orden)
    return {
        "resultados": [{k: f[k] for k in ("apellido", "nombre", "dni")} for f in ordenadas[:MAXIMO_RESULTADOS]],
        "hay_mas": len(ordenadas) > MAXIMO_RESULTADOS,
    }
