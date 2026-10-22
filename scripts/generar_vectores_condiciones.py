"""Genera ``programas/tests/fixtures/condiciones_vectores.json`` (K8).

Los **vectores** son la prueba de que el motor de condiciones del back
(``programas/services/condiciones.py``) y el de la app móvil (``condiciones.js``)
dicen lo mismo. Cada caso trae un formulario chico (``items``, con la forma de
``definicion_formulario.items``), lo respondido, la fecha de referencia para las
edades y **qué claves quedan visibles**.

Lo que se escribe en ``visibles`` NO es criterio de quien arma el caso: lo dicta
el motor real del back, que este script ejecuta. Si un caso da un resultado
raro (operador desconocido, fuente posterior, ``edad_entre`` invertido), se fija
igual: es lo que hace el servidor, y es lo que la app tiene que replicar.

El JSON se copia tal cual a los tests de la app. ``test_condiciones_vectores``
lo vuelve a correr contra el motor, así que si el motor cambia y el archivo no,
el test se pone rojo; en ese caso se regenera con::

    .venv/Scripts/python.exe scripts/generar_vectores_condiciones.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "vectores")
os.environ.setdefault("PYTEST_RUNNING", "1")

import django  # noqa: E402

django.setup()

from programas.services.respuestas import aplicar  # noqa: E402

DESTINO = RAIZ / "programas" / "tests" / "fixtures" / "condiciones_vectores.json"
REFERENCIA = "2026-10-22"


def campo(clave, tipo, condicion=None, **extra):
    return {"tipo_item": "campo", "clave": clave, "tipo": tipo, "texto": clave, "condicion": condicion, **extra}


def texto(clave, condicion=None):
    return {"tipo": "texto", "clave": clave, "texto": clave, "condicion": condicion}


def grupo(clave, items, condicion=None):
    return {"tipo": "grupo", "clave": clave, "titulo": clave, "condicion": condicion, "items": items}


def cond(fuente, op, valor=None, modo="todas", *mas):
    reglas = [{"fuente": fuente, "op": op, "valor": valor}]
    reglas.extend({"fuente": f, "op": o, "valor": v} for f, o, v in mas)
    return {"modo": modo, "reglas": reglas}


def simple(nombre, tipo_fuente, op, valor, respuesta, fecha=REFERENCIA):
    """Una fuente ``a`` y un campo ``b`` condicionado a ella."""
    items = [grupo("g1", [campo("a", tipo_fuente), campo("b", "STRING", cond("a", op, valor))])]
    respuestas = {} if respuesta is None else {"a": respuesta}
    return {"nombre": nombre, "items": items, "respuestas": respuestas, "fecha_referencia": fecha}


CASOS = []


def agregar(*args, **kwargs):
    CASOS.append(simple(*args, **kwargs))


# STRING
agregar("string · vacio con la fuente sin responder", "STRING", "vacio", None, None)
agregar("string · vacio con texto en blanco", "STRING", "vacio", None, "   ")
agregar("string · vacio con texto", "STRING", "vacio", None, "hola")
agregar("string · completo con texto", "STRING", "completo", None, "hola")
agregar("string · completo con la fuente sin responder", "STRING", "completo", None, None)
agregar("string · completo con texto en blanco", "STRING", "completo", None, "  ")

# INT
agregar("int · eq cumple", "INT", "eq", 5, 5)
agregar("int · eq no cumple", "INT", "eq", 5, 6)
agregar("int · eq con valor en texto", "INT", "eq", 5, "5")
agregar("int · ne cumple", "INT", "ne", 5, 6)
agregar("int · ne no cumple", "INT", "ne", 5, 5)
agregar("int · ne con la fuente sin responder", "INT", "ne", 5, None)
agregar("int · lt cumple", "INT", "lt", 10, 3)
agregar("int · lt en el límite", "INT", "lt", 10, 10)
agregar("int · gt cumple", "INT", "gt", 10, 11)
agregar("int · gt en el límite", "INT", "gt", 10, 10)
agregar("int · le en el límite", "INT", "le", 10, 10)
agregar("int · le no cumple", "INT", "le", 10, 11)
agregar("int · ge en el límite", "INT", "ge", 10, 10)
agregar("int · ge no cumple", "INT", "ge", 10, 9)
agregar("int · coma decimal en la respuesta", "INT", "gt", 2, "2,5")
agregar("int · coma decimal en el valor de la regla", "INT", "lt", "2,5", 2)
agregar("int · respuesta no numérica", "INT", "eq", 5, "cinco")
agregar("int · valor de la regla no numérico", "INT", "eq", "x", 5)
agregar("int · cero cuenta como respondido", "INT", "eq", 0, 0)
agregar("int · vacio con cero", "INT", "vacio", None, 0)

# SELECTOR
agregar("selector · es cumple", "SELECTOR", "es", "Sí", "Sí")
agregar("selector · es no cumple", "SELECTOR", "es", "Sí", "No")
agregar("selector · es compara como texto", "SELECTOR", "es", 1, "1")
agregar("selector · es distingue mayúsculas", "SELECTOR", "es", "Sí", "sí")
agregar("selector · no_es cumple", "SELECTOR", "no_es", "Sí", "No")
agregar("selector · no_es no cumple", "SELECTOR", "no_es", "Sí", "Sí")
agregar("selector · no_es con la fuente sin responder", "SELECTOR", "no_es", "Sí", None)
agregar("selector · es_alguno cumple", "SELECTOR", "es_alguno", ["A", "B"], "B")
agregar("selector · es_alguno no cumple", "SELECTOR", "es_alguno", ["A", "B"], "C")
agregar("selector · es_alguno con un valor suelto en la regla", "SELECTOR", "es_alguno", "A", "A")

# SELECTOR_MULTIPLE
agregar("multiple · incluye cumple", "SELECTOR_MULTIPLE", "incluye", "A", ["A", "B"])
agregar("multiple · incluye no cumple", "SELECTOR_MULTIPLE", "incluye", "C", ["A", "B"])
agregar("multiple · incluye con la lista vacía", "SELECTOR_MULTIPLE", "incluye", "A", [])
agregar("multiple · no_incluye cumple", "SELECTOR_MULTIPLE", "no_incluye", "C", ["A", "B"])
agregar("multiple · no_incluye no cumple", "SELECTOR_MULTIPLE", "no_incluye", "A", ["A", "B"])
agregar("multiple · no_incluye con la lista vacía", "SELECTOR_MULTIPLE", "no_incluye", "A", [])
agregar("multiple · incluye_alguno cumple", "SELECTOR_MULTIPLE", "incluye_alguno", ["B", "Z"], ["A", "B"])
agregar("multiple · incluye_alguno no cumple", "SELECTOR_MULTIPLE", "incluye_alguno", ["Y", "Z"], ["A", "B"])
agregar("multiple · vacio con la lista vacía", "SELECTOR_MULTIPLE", "vacio", None, [])
agregar("multiple · completo con una opción", "SELECTOR_MULTIPLE", "completo", None, ["A"])

# DATE · edades contra la fecha de referencia (22-oct-2026)
agregar("fecha · edad_menor cumple", "DATE", "edad_menor", 18, "2010-03-15")
agregar("fecha · edad_menor el día que cumple 18", "DATE", "edad_menor", 18, "2008-10-22")
agregar("fecha · edad_menor el día antes de cumplir 18", "DATE", "edad_menor", 18, "2008-10-23")
agregar("fecha · edad_mayor cumple", "DATE", "edad_mayor", 60, "1950-01-01")
agregar("fecha · edad_mayor en el límite", "DATE", "edad_mayor", 60, "1966-10-22")
agregar("fecha · edad_igual cumple", "DATE", "edad_igual", 16, "2010-03-15")
agregar("fecha · edad_igual no cumple", "DATE", "edad_igual", 17, "2010-03-15")
agregar("fecha · edad_entre dentro del rango", "DATE", "edad_entre", [10, 18], "2010-03-15")
agregar("fecha · edad_entre en el borde inferior", "DATE", "edad_entre", [16, 18], "2010-03-15")
agregar("fecha · edad_entre fuera del rango", "DATE", "edad_entre", [20, 30], "2010-03-15")
agregar("fecha · edad_entre con el rango invertido", "DATE", "edad_entre", [18, 10], "2010-03-15")
agregar("fecha · edad_entre con un solo límite", "DATE", "edad_entre", [18], "2010-03-15")
agregar("fecha · edad con otra fecha de referencia", "DATE", "edad_menor", 18, "2008-10-22", fecha="2026-10-21")
agregar("fecha · edad con una fecha imposible", "DATE", "edad_menor", 18, "2000-02-30")
agregar("fecha · edad con una fecha en formato argentino", "DATE", "edad_menor", 18, "15/03/2010")
agregar("fecha · anterior cumple", "DATE", "anterior", "2000-01-01", "1999-12-31")
agregar("fecha · anterior el mismo día", "DATE", "anterior", "2000-01-01", "2000-01-01")
agregar("fecha · posterior cumple", "DATE", "posterior", "2000-01-01", "2000-01-02")
agregar("fecha · posterior el mismo día", "DATE", "posterior", "2000-01-01", "2000-01-01")
agregar("fecha · posterior con el tope inválido", "DATE", "posterior", "no-es-fecha", "2000-01-02")
agregar("fecha · vacio sin responder", "DATE", "vacio", None, None)
agregar("fecha · edad con la fuente sin responder", "DATE", "edad_menor", 18, None)

# ARCHIVO
agregar("archivo · adjuntado con archivo", "ARCHIVO", "adjuntado", None, "foto.jpg")
agregar("archivo · adjuntado sin archivo", "ARCHIVO", "adjuntado", None, None)
agregar("archivo · no_adjuntado sin archivo", "ARCHIVO", "no_adjuntado", None, None)
agregar("archivo · no_adjuntado con archivo", "ARCHIVO", "no_adjuntado", None, "foto.jpg")

# Operadores raros
agregar("operador desconocido", "STRING", "empieza_con", "ho", "hola")
agregar("operador desconocido con la fuente sin responder", "STRING", "empieza_con", "ho", None)
agregar("operador de otro tipo sobre la fuente (eq sobre un selector)", "SELECTOR", "eq", "5", "5")
agregar("operador ausente", "STRING", None, None, "hola")

# Sin condición, con reglas vacías, modos
CASOS.append(
    {
        "nombre": "condicion null · siempre visible",
        "items": [grupo("g1", [campo("a", "STRING"), campo("b", "STRING", None)])],
        "respuestas": {},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "condicion sin reglas · siempre visible",
        "items": [grupo("g1", [campo("a", "STRING"), campo("b", "STRING", {"modo": "todas", "reglas": []})])],
        "respuestas": {},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "condicion sin modo · vale todas",
        "items": [
            grupo(
                "g1",
                [
                    campo("a", "STRING"),
                    campo("c", "STRING"),
                    campo(
                        "b",
                        "STRING",
                        {
                            "reglas": [
                                {"fuente": "a", "op": "completo", "valor": None},
                                {"fuente": "c", "op": "completo", "valor": None},
                            ]
                        },
                    ),
                ],
            )
        ],
        "respuestas": {"a": "x"},
        "fecha_referencia": REFERENCIA,
    }
)

for modo, respuestas, nombre in (
    ("todas", {"a": "x", "c": "y"}, "modo todas · las dos reglas cumplen"),
    ("todas", {"a": "x"}, "modo todas · cumple una sola"),
    ("alguna", {"a": "x"}, "modo alguna · cumple una"),
    ("alguna", {}, "modo alguna · no cumple ninguna"),
):
    CASOS.append(
        {
            "nombre": nombre,
            "items": [
                grupo(
                    "g1",
                    [
                        campo("a", "STRING"),
                        campo("c", "STRING"),
                        campo("b", "STRING", cond("a", "completo", None, modo, ("c", "completo", None))),
                    ],
                )
            ],
            "respuestas": respuestas,
            "fecha_referencia": REFERENCIA,
        }
    )

# Ocultos
CASOS.append(
    {
        "nombre": "oculto cuenta como vacío para sus dependientes",
        "items": [
            grupo(
                "g1",
                [
                    campo("a", "STRING"),
                    campo("b", "STRING", cond("a", "completo")),
                    campo("c", "STRING", cond("b", "completo")),
                    campo("d", "STRING", cond("b", "vacio")),
                ],
            )
        ],
        "respuestas": {"b": "respondió aunque estaba oculto", "c": "x"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "grupo oculto oculta a sus hijos aunque su propia condición cumpla",
        "items": [
            grupo("g1", [campo("a", "STRING")]),
            grupo("g2", [campo("b", "STRING"), campo("c", "STRING", cond("a", "vacio"))], cond("a", "completo")),
        ],
        "respuestas": {},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "grupo visible con un hijo condicionado",
        "items": [
            grupo("g1", [campo("a", "STRING")]),
            grupo("g2", [campo("b", "STRING"), campo("c", "STRING", cond("a", "completo"))], cond("a", "completo")),
        ],
        "respuestas": {"a": "x"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "el hijo de un grupo oculto no sirve de fuente",
        "items": [
            grupo("g1", [campo("a", "STRING")]),
            grupo("g2", [campo("b", "STRING")], cond("a", "completo")),
            grupo("g3", [campo("c", "STRING", cond("b", "vacio"))]),
        ],
        "respuestas": {"b": "x"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "texto informativo condicionado",
        "items": [grupo("g1", [campo("a", "SELECTOR"), texto("t1", cond("a", "es", "Sí"))])],
        "respuestas": {"a": "Sí"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "texto informativo oculto",
        "items": [grupo("g1", [campo("a", "SELECTOR"), texto("t1", cond("a", "es", "Sí"))])],
        "respuestas": {"a": "No"},
        "fecha_referencia": REFERENCIA,
    }
)

# Orden: la fuente tiene que ser anterior
CASOS.append(
    {
        "nombre": "fuente posterior en el orden · no cuenta como respondida",
        "items": [grupo("g1", [campo("b", "STRING", cond("a", "completo")), campo("a", "STRING")])],
        "respuestas": {"a": "x"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "fuente posterior en el orden · vacio se cumple",
        "items": [grupo("g1", [campo("b", "STRING", cond("a", "vacio")), campo("a", "STRING")])],
        "respuestas": {"a": "x"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "fuente que no existe en el formulario",
        "items": [
            grupo("g1", [campo("b", "STRING", cond("zzz", "completo")), campo("c", "STRING", cond("zzz", "vacio"))])
        ],
        "respuestas": {},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "respuesta a una clave que el formulario no tiene",
        "items": [grupo("g1", [campo("a", "STRING"), campo("b", "STRING", cond("x", "completo"))])],
        "respuestas": {"x": "algo"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "cadena de condiciones de tres pasos",
        "items": [
            grupo(
                "g1",
                [
                    campo("a", "SELECTOR"),
                    campo("b", "SELECTOR", cond("a", "es", "Sí")),
                    campo("c", "STRING", cond("b", "es", "Sí")),
                ],
            )
        ],
        "respuestas": {"a": "Sí", "b": "Sí"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "apoderado: grupo condicionado a edad_menor 18 (menor)",
        "items": [
            grupo("g-datos", [campo("pg-1", "DATE")]),
            grupo("g-apoderado", [campo("pg-2", "STRING")], cond("pg-1", "edad_menor", 18)),
        ],
        "respuestas": {"pg-1": "2012-05-01"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "apoderado: grupo condicionado a edad_menor 18 (mayor)",
        "items": [
            grupo("g-datos", [campo("pg-1", "DATE")]),
            grupo("g-apoderado", [campo("pg-2", "STRING")], cond("pg-1", "edad_menor", 18)),
        ],
        "respuestas": {"pg-1": "1990-05-01"},
        "fecha_referencia": REFERENCIA,
    }
)
CASOS.append(
    {
        "nombre": "apoderado: sin la fecha de nacimiento el grupo no aparece",
        "items": [
            grupo("g-datos", [campo("pg-1", "DATE")]),
            grupo("g-apoderado", [campo("pg-2", "STRING")], cond("pg-1", "edad_menor", 18)),
        ],
        "respuestas": {},
        "fecha_referencia": REFERENCIA,
    }
)


def claves_de(items):
    claves = []
    for g in items:
        claves.append(g["clave"])
        claves.extend(hijo["clave"] for hijo in g["items"])
    return claves


def main():
    salida = []
    for caso in CASOS:
        visibles, _ocultos, _efectivas = aplicar(
            {"items": caso["items"]}, caso["respuestas"], hoy=date.fromisoformat(caso["fecha_referencia"])
        )
        salida.append(
            {
                "nombre": caso["nombre"],
                "items": caso["items"],
                "respuestas": caso["respuestas"],
                "fecha_referencia": caso["fecha_referencia"],
                # En el orden del formulario (grupos y campos), no del `set`.
                "visibles": [clave for clave in claves_de(caso["items"]) if clave in visibles],
            }
        )
    nombres = [c["nombre"] for c in salida]
    assert len(nombres) == len(set(nombres)), "nombres de caso repetidos"
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(salida)} casos -> {DESTINO}")


if __name__ == "__main__":
    main()
