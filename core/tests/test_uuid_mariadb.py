"""Las búsquedas por un UUID de origen externo no pueden usar el lookup del ORM (RED-09).

En MariaDB 10.7+ Django 5 trata el ``UUIDField`` como UUID nativo y manda el valor
**con guiones**; en MySQL y SQLite lo manda en hex de 32. Como en las columnas de
origen externo conviven las dos formas —una base restaurada de un motor al otro, o
filas cargadas antes de las migraciones a ``char(36)``—, un ``filter(client_uuid=valor)``
encuentra solo la mitad de las filas, sin error y sin que ningún test lo note: en
SQLite las dos formas coinciden. La única búsqueda correcta es ``q_uuid_en_texto``,
que compara contra las dos como texto plano y sin funciones sobre la columna (RED-08).

Este módulo es un lint de AST, no un test de comportamiento: la conducta no se puede
probar sin MariaDB (eso es TST-01, ``--tag mysql``). Lo que se fija acá es que nadie
vuelva a escribir el lookup directo en el código de las apps.
"""

import ast
from pathlib import Path

from django.apps import apps
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent.parent

#: Columnas UUID cuyo valor entra desde afuera (la app de campo, el link público) y
#: por lo tanto pueden existir en las dos representaciones.
CAMPOS_UUID_EXTERNOS = frozenset({"client_uuid", "token_publico"})

#: Métodos de queryset que comparan contra la columna. ``create``/``update`` quedan
#: afuera a propósito: escribir el UUID por kwarg es correcto, el problema es buscarlo.
METODOS_DE_BUSQUEDA = frozenset({"filter", "exclude", "get", "get_or_create", "update_or_create"})

#: Lookups que no comparan el valor del UUID y por lo tanto no sufren el problema.
LOOKUPS_INOCUOS = frozenset({"isnull"})

#: Pragma de línea para la excepción justificada.
PRAGMA = "# uuid-externo: ok"


def _modulos_de_dominio():
    """Todo el código de las apps del proyecto, menos tests y migraciones.

    El barrido sale del registro de apps (así cubre las que se agreguen) y no de una
    lista de carpetas: el bug del Cambio 91 vivió en ``programas/api/views.py``, que
    no es ni ``services/`` ni ``views/``.
    """
    rutas = set()
    for config in apps.get_app_configs():
        carpeta = Path(config.path).resolve()
        if RAIZ not in carpeta.parents and carpeta != RAIZ:
            continue  # app de una dependencia (django.contrib, DRF, …)
        for ruta in carpeta.rglob("*.py"):
            partes = set(ruta.relative_to(carpeta).parts)
            if partes & {"tests", "migrations"} or ruta.name.startswith("test_"):
                continue
            rutas.add(ruta)
    return sorted(rutas)


def _campo_de_lookup(kwarg):
    """``client_uuid__exact`` → ``("client_uuid", "exact")``; ``dni`` → ``("dni", "")``."""
    campo, _, lookup = kwarg.partition("__")
    return campo, lookup


class BusquedasUUIDTests(SimpleTestCase):
    """RED-09: ratchet sobre las búsquedas por UUID externo. La lista solo baja."""

    def test_las_busquedas_por_uuid_usan_el_helper(self):
        infracciones = []
        for ruta in _modulos_de_dominio():
            fuente = ruta.read_text(encoding="utf-8")
            lineas = fuente.splitlines()
            for nodo in ast.walk(ast.parse(fuente, filename=str(ruta))):
                if not isinstance(nodo, ast.Call) or not isinstance(nodo.func, ast.Attribute):
                    continue
                if nodo.func.attr not in METODOS_DE_BUSQUEDA:
                    continue
                for kwarg in nodo.keywords:
                    if kwarg.arg is None:
                        continue
                    campo, lookup = _campo_de_lookup(kwarg.arg)
                    if campo not in CAMPOS_UUID_EXTERNOS or lookup in LOOKUPS_INOCUOS:
                        continue
                    if PRAGMA in lineas[kwarg.value.lineno - 1]:
                        continue
                    infracciones.append(
                        f"{ruta.relative_to(RAIZ).as_posix()}:{kwarg.value.lineno} → .{nodo.func.attr}({kwarg.arg}=…)"
                    )

        self.assertEqual(
            sorted(infracciones),
            [],
            "Búsqueda por un UUID externo con el lookup del ORM: en MariaDB no encuentra las filas "
            "guardadas en la otra forma. Usar q_uuid_en_texto (programas/services/becas.py) o, si el "
            f"caso está justificado, dejar «{PRAGMA}» en la línea. Infracciones: " + ", ".join(sorted(infracciones)),
        )

    def test_el_lint_detecta_el_lookup_directo(self):
        """Pin invertido: el lint tiene que reconocer la forma que busca prohibir."""
        fuente = "Formulario.objects.filter(relevamiento=rel, client_uuid=valor)"
        encontrados = [
            kwarg.arg
            for nodo in ast.walk(ast.parse(fuente))
            if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
            for kwarg in nodo.keywords
            if nodo.func.attr in METODOS_DE_BUSQUEDA
            and kwarg.arg
            and _campo_de_lookup(kwarg.arg)[0] in CAMPOS_UUID_EXTERNOS
        ]
        self.assertEqual(encontrados, ["client_uuid"])
