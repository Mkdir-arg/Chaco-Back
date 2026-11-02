"""Sugerencias de agentes del paso «Buscar agente» mientras se escribe (Cambio 416).

Lectura pura. Busca entre **los mismos usuarios** que el buscador completo (`universo_buscar_agente`), pero
solo por **nombre**: cada palabra es prefijo de nombre o de apellido (`istartswith`, `LIKE 'x%'`, nunca
`startswith`, que en MySQL/MariaDB es `LIKE BINARY`). El DNI y el correo siguen siendo búsqueda **exacta**
en el buscador completo —así no se puede barrer el padrón de usuarios de a pedazos—, y acá no se ofrecen.

Cada sugerencia lleva apellido, nombre y DNI **enmascarado** (`12.***.678`); nunca correo, teléfono ni usuario.
"""

from django.db.models import Q

from programas.services.buscador_agentes import universo_buscar_agente
from users.services.busqueda import MIN_CARACTERES, TOPE_RESULTADOS, enmascarar_dni

#: Lo que se lee de lo tecleado: más largo que cualquier nombre, para no armar un WHERE enorme.
MAXIMO_CARACTERES = 100
MAXIMO_PALABRAS = 5


def sugerir_agentes(texto):
    """`{"resultados": [{apellido, nombre, dni, valor}], "hay_mas": bool}` para lo que se lleva tecleado.

    `valor` es lo que el campo de búsqueda recibe al elegir: nombre y apellido, que el buscador completo
    encuentra por palabras. Con menos de 3 caracteres la lista va vacía; un DNI o un correo no es prefijo de ningún nombre, así que tampoco devuelve nada.
    """

    texto = (texto or "").strip()[:MAXIMO_CARACTERES].strip()
    vacio = {"resultados": [], "hay_mas": False}
    if len(texto) < MIN_CARACTERES:
        return vacio
    filtro = Q()
    for palabra in texto.replace(",", " ").split()[:MAXIMO_PALABRAS]:
        filtro &= Q(first_name__istartswith=palabra) | Q(last_name__istartswith=palabra)
    filas = list(
        universo_buscar_agente()
        .filter(filtro)
        .order_by("last_name", "first_name", "pk")
        .values("last_name", "first_name", "profile__dni")[: TOPE_RESULTADOS + 1]
    )
    return {
        "resultados": [
            {
                "apellido": fila["last_name"],
                "nombre": fila["first_name"],
                "dni": enmascarar_dni(fila["profile__dni"] or ""),
                "valor": f"{fila['first_name']} {fila['last_name']}".strip(),
            }
            for fila in filas[:TOPE_RESULTADOS]
        ],
        "hay_mas": len(filas) > TOPE_RESULTADOS,
    }
