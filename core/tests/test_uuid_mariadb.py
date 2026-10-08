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
from django.db import models
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parent.parent.parent

#: Columnas UUID cuyo valor entra desde afuera (la app de campo, el link público) y
#: por lo tanto pueden existir en las dos representaciones.
CAMPOS_UUID_EXTERNOS = frozenset({"client_uuid", "token_publico"})

#: Métodos de queryset que comparan contra la columna. ``create``/``update`` quedan
#: afuera a propósito: escribir el UUID por kwarg es correcto, el problema es buscarlo.
#: ``Q(...)`` se reconoce aparte, porque puede armarse lejos del ``filter`` que lo usa.
METODOS_DE_BUSQUEDA = frozenset({"filter", "exclude", "get", "get_or_create", "update_or_create"})

#: Lookups registrados en el ORM, para distinguir `campo__exact` de una travesía
#: `relacion__campo`. Sale de Django, no de una lista a mano que envejezca.
LOOKUPS_CONOCIDOS = frozenset(models.CharField.get_lookups()) | frozenset(models.UUIDField.get_lookups())

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
    """Separa el campo del lookup, aguantando travesías por relaciones.

    ``client_uuid`` → ``("client_uuid", "")`` · ``client_uuid__exact`` →
    ``("client_uuid", "exact")`` · ``relevamiento__formularios__client_uuid`` →
    ``("client_uuid", "")``. Lo que importa es el **último segmento significativo**:
    en una travesía la columna comparada es la del final del camino.
    """
    segmentos = kwarg.split("__")
    if len(segmentos) > 1 and segmentos[-1] in LOOKUPS_CONOCIDOS:
        return segmentos[-2], segmentos[-1]
    return segmentos[-1], ""


def _es_llamada_de_busqueda(nodo):
    """``qs.filter(...)``/``.get(...)``… o un ``Q(...)`` (incluido ``models.Q(...)``)."""
    if isinstance(nodo.func, ast.Attribute):
        return nodo.func.attr in METODOS_DE_BUSQUEDA or nodo.func.attr == "Q"
    return isinstance(nodo.func, ast.Name) and nodo.func.id == "Q"


def _nombre_de_llamada(nodo):
    return nodo.func.attr if isinstance(nodo.func, ast.Attribute) else nodo.func.id


def _kwargs_de(nodo):
    """``(nombre, nodo_de_valor)`` de cada kwarg, resolviendo ``**{"campo": v}`` literal.

    Un ``**variable`` que no sea un dict literal no se puede resolver estáticamente y
    se deja pasar: el lint no adivina.
    """
    for kwarg in nodo.keywords:
        if kwarg.arg is not None:
            yield kwarg.arg, kwarg.value
        elif isinstance(kwarg.value, ast.Dict):
            for clave, valor in zip(kwarg.value.keys, kwarg.value.values):
                if isinstance(clave, ast.Constant) and isinstance(clave.value, str):
                    yield clave.value, valor


def infracciones_en(fuente, etiqueta="<fuente>"):
    """Búsquedas por un UUID externo sin ``q_uuid_en_texto``, como texto legible."""
    lineas = fuente.splitlines()
    infracciones = []
    for nodo in ast.walk(ast.parse(fuente, filename=etiqueta)):
        if not isinstance(nodo, ast.Call) or not _es_llamada_de_busqueda(nodo):
            continue
        for nombre, valor in _kwargs_de(nodo):
            campo, lookup = _campo_de_lookup(nombre)
            if campo not in CAMPOS_UUID_EXTERNOS or lookup in LOOKUPS_INOCUOS:
                continue
            if PRAGMA in lineas[valor.lineno - 1]:
                continue
            infracciones.append(f"{etiqueta}:{valor.lineno} → {_nombre_de_llamada(nodo)}({nombre}=…)")
    return infracciones


class BusquedasUUIDTests(SimpleTestCase):
    """RED-09: ratchet sobre las búsquedas por UUID externo. La lista solo baja."""

    def test_las_busquedas_por_uuid_usan_el_helper(self):
        infracciones = []
        for ruta in _modulos_de_dominio():
            infracciones += infracciones_en(ruta.read_text(encoding="utf-8"), ruta.relative_to(RAIZ).as_posix())

        self.assertEqual(
            sorted(infracciones),
            [],
            "Búsqueda por un UUID externo con el lookup del ORM: en MariaDB no encuentra las filas "
            "guardadas en la otra forma. Usar q_uuid_en_texto (core/db.py) o, si el "
            f"caso está justificado, dejar «{PRAGMA}» en la línea. Infracciones: " + ", ".join(sorted(infracciones)),
        )

    def test_el_lint_detecta_las_cuatro_formas_de_escribir_la_busqueda(self):
        """Pin invertido sobre fuente sintética: las cuatro formas tienen que caer.

        Sin esto el ratchet puede quedar verde para siempre por no reconocer la forma
        que alguien escribió, que es peor que no tenerlo.
        """
        casos = {
            "kwarg directo": "Formulario.objects.filter(relevamiento=rel, client_uuid=valor)",
            "Q explícito": "Formulario.objects.filter(Q(client_uuid=valor) | Q(numero=1))",
            "doble asterisco literal": 'Formulario.objects.get(**{"client_uuid": valor})',
            "travesía por relación": "Relevamiento.objects.filter(formularios__client_uuid=valor)",
        }
        for etiqueta, fuente in casos.items():
            with self.subTest(forma=etiqueta):
                self.assertEqual(len(infracciones_en(fuente, etiqueta)), 1, infracciones_en(fuente, etiqueta))

    def test_el_lint_no_marca_lo_que_es_correcto(self):
        """Escribir el UUID, preguntar por NULL o usar el helper no son infracciones."""
        casos = {
            "escritura": 'Formulario.objects.create(client_uuid=valor, numero="1")',
            "isnull": "Formulario.objects.filter(client_uuid__isnull=True)",
            "helper": 'relevamiento.formularios.filter(q_uuid_en_texto("client_uuid", valor))',
            "doble asterisco opaco": "Formulario.objects.filter(**filtros)",
            "otro campo": "Formulario.objects.filter(dni_titular=valor)",
            "pragma": f"Formulario.objects.filter(client_uuid=valor)  {PRAGMA}",
        }
        for etiqueta, fuente in casos.items():
            with self.subTest(forma=etiqueta):
                self.assertEqual(infracciones_en(fuente, etiqueta), [])
