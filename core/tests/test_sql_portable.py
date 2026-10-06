"""Guardia: ningún lookup por día sobre un ``DateTimeField`` en el código productivo (DIS-01).

``campo__date``, ``campo__year``/``month``/``day`` y ``TruncDate``/``TruncWeek``/
``TruncMonth`` sobre un ``DateTimeField`` con ``USE_TZ`` se traducen en MySQL y
MariaDB a ``CONVERT_TZ``. La base de ECOM **no tiene cargadas las tablas de zona
horaria**: ``CONVERT_TZ`` devuelve NULL, el filtro no matchea nada y el conteo sale
en cero **solo en producción**. En SQLite —donde corre la suite— el mismo lookup da
bien, así que ningún test de comportamiento lo ve.

``core/tests/test_sql_motor_real.py`` fija la forma del SQL de las consultas que ya
se conocen, una por una; esto recorre **todo** el código productivo, así que también
cubre la consulta que alguien escriba mañana. Lo mismo sobre un ``DateField`` es
seguro (compila a ``DATE_FORMAT``, sin ``CONVERT_TZ``) y por eso no se reporta.

La salida es: usar ``core.utils_fechas`` (rango ``[inicio, fin)`` en hora local) o,
si el caso realmente es inofensivo, dejar ``# sql-portable: ok`` en la línea con el
motivo al lado. Hoy el repo no tiene ninguna excepción y la idea es que siga así.
"""

import ast
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import models
from django.test import SimpleTestCase

#: Lookups que el motor resuelve truncando una fecha (los que generan ``CONVERT_TZ``).
LOOKUPS = ("date", "year", "iso_year", "month", "day", "week", "week_day", "iso_week_day", "quarter", "time")

#: Comparadores que pueden ir colgados del lookup (``fecha__date__gte``).
COMPARADORES = ("gt", "gte", "lt", "lte", "exact", "in", "range", "isnull")

#: El ``-`` inicial de un ``order_by("-creado__date")`` es parte del lookup, no del campo.
LOOKUP_RE = re.compile(
    r"(?:^-?|__)(?P<campo>[a-z_][a-z0-9_]*)__(?:%s)(?:__(?:%s))?$" % ("|".join(LOOKUPS), "|".join(COMPARADORES))
)

#: Funciones de base de datos que truncan o extraen una parte de la fecha.
FUNCIONES_RE = re.compile(r"^(Trunc|Extract)[A-Za-z]*$")

PRAGMA = "sql-portable: ok"

#: Carpetas que no son código productivo.
DIRECTORIOS_IGNORADOS = {"migrations", "tests", "__pycache__", "node_modules", "static", "templates", "fixtures"}


def _es_de_tests(ruta: Path) -> bool:
    return ruta.name.startswith("test_") or ruta.name.endswith("_tests.py") or ruta.name == "conftest.py"


def raices_productivas():
    """Carpetas de código propio: las apps del repo más ``config/``."""
    base = Path(settings.BASE_DIR).resolve()
    raices = {base / "config"}
    for config in apps.get_app_configs():
        ruta = Path(config.path).resolve()
        if base in ruta.parents or ruta == base:
            raices.add(ruta)
    return sorted(ruta for ruta in raices if ruta.is_dir())


def archivos_productivos():
    for raiz in raices_productivas():
        for ruta in sorted(raiz.rglob("*.py")):
            if DIRECTORIOS_IGNORADOS & set(ruta.relative_to(raiz).parts[:-1]) or _es_de_tests(ruta):
                continue
            yield ruta


def tipos_de_campo_por_nombre():
    """``{nombre de campo: {"datetime", "date", ...}}`` sobre los modelos del repo.

    El tipo se resuelve por nombre y no por el modelo del queryset: el nombre es lo
    único que el análisis estático tiene a mano, y alcanza —si **algún** modelo
    declara ese nombre como ``DateTimeField``, el lookup es sospechoso—.
    """
    base = Path(settings.BASE_DIR).resolve()
    tipos: dict[str, set[str]] = {}
    for modelo in apps.get_models():
        if base not in Path(apps.get_app_config(modelo._meta.app_label).path).resolve().parents:
            continue
        for campo in modelo._meta.get_fields():
            if not isinstance(campo, models.Field):
                continue
            if isinstance(campo, models.DateTimeField):
                clase = "datetime"
            elif isinstance(campo, models.DateField):
                clase = "date"
            else:
                continue
            tipos.setdefault(campo.name, set()).add(clase)
    return tipos


def _docstrings(arbol):
    """Nodos que son docstring: ahí un ``campo__date`` es prosa, no una consulta."""
    marcados = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            cuerpo = getattr(nodo, "body", None)
            if cuerpo and isinstance(cuerpo[0], ast.Expr) and isinstance(cuerpo[0].value, ast.Constant):
                marcados.add(id(cuerpo[0].value))
    return marcados


def _cadenas(arbol, saltear):
    """Cada literal de texto del módulo, incluidas las partes fijas de un f-string.

    Un ``f"{prefijo}fecha_ingreso__date__gte"`` llega como pedazos: lo que interesa
    es el pedazo fijo, que es donde está el lookup.
    """
    saltear = set(saltear)
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.JoinedStr):
            for parte in nodo.values:
                if isinstance(parte, ast.Constant) and isinstance(parte.value, str):
                    saltear.add(id(parte))
                    yield nodo, parte.value
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and id(nodo) not in saltear:
            yield nodo, nodo.value


def _nombre_llamado(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def hallazgos_en(codigo, nombre="<codigo>", tipos=None):
    """Lookups por día sobre un campo que en algún modelo es ``DateTimeField``."""
    tipos = tipos_de_campo_por_nombre() if tipos is None else tipos
    arbol = ast.parse(codigo)
    lineas = codigo.splitlines()
    saltear = _docstrings(arbol)
    encontrados = []

    def _registrar(nodo, campo, texto):
        linea = lineas[nodo.lineno - 1] if 0 < nodo.lineno <= len(lineas) else ""
        if PRAGMA in linea:
            return
        clases = tipos.get(campo)
        if clases == {"date"}:
            return
        motivo = "no es un campo conocido" if not clases else "es DateTimeField"
        encontrados.append((nodo.lineno, f"{nombre}:{nodo.lineno}: {texto} ({campo} {motivo})"))

    def _por_lookup(nodo, texto):
        coincidencia = LOOKUP_RE.search(texto)
        if coincidencia:
            _registrar(nodo, coincidencia.group("campo"), texto)

    for nodo in ast.walk(arbol):
        # ``filter(fecha_ingreso__date=hoy)``: el lookup es el nombre del argumento.
        if isinstance(nodo, ast.keyword) and nodo.arg:
            _por_lookup(nodo.value, nodo.arg)
        elif isinstance(nodo, ast.Call) and FUNCIONES_RE.match(_nombre_llamado(nodo.func)):
            if nodo.args and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str):
                campo = nodo.args[0].value.split("__")[-1]
                _registrar(nodo, campo, f"{_nombre_llamado(nodo.func)}({nodo.args[0].value!r})")

    for nodo, texto in _cadenas(arbol, saltear):
        _por_lookup(nodo, texto)

    vistos, ordenados = set(), []
    for _, hallazgo in sorted(encontrados):
        if hallazgo not in vistos:
            vistos.add(hallazgo)
            ordenados.append(hallazgo)
    return ordenados


class SqlPortableTests(SimpleTestCase):
    """DIS-01: la guardia que impide reintroducir el bug que solo rompe en ECOM."""

    def test_ningun_lookup_por_dia_sobre_un_datetimefield(self):
        """Recorre el código productivo entero, no una lista de consultas conocidas."""
        tipos = tipos_de_campo_por_nombre()
        base = Path(settings.BASE_DIR).resolve()
        hallazgos = []
        for ruta in archivos_productivos():
            codigo = ruta.read_text(encoding="utf-8")
            hallazgos.extend(hallazgos_en(codigo, nombre=str(ruta.relative_to(base)), tipos=tipos))
        self.assertEqual(
            hallazgos,
            [],
            "En ECOM (MariaDB sin tablas de zona horaria) esto compila a CONVERT_TZ y devuelve NULL. "
            "Usá core.utils_fechas (rango [inicio, fin) en hora local):\n" + "\n".join(hallazgos),
        )

    def test_la_guardia_detecta_las_cuatro_formas(self):
        """Pin invertido: sin esto, el test de arriba podría estar mirando nada.

        Son las formas con las que el bug entra: el lookup directo, el que llega por
        un ``Q``/``**kwargs`` armado con un f-string, la función de truncado y el
        ``order_by`` descendente, donde el ``-`` va pegado al campo (y por eso la
        primera versión de la guardia lo dejaba pasar).
        """
        codigo = (
            "from django.db.models.functions import TruncWeek\n"
            "def f(qs, prefijo):\n"
            "    qs.filter(fecha_ingreso__date=hoy)\n"
            '    qs.filter(**{f"{prefijo}fecha_egreso__date__gte": desde})\n'
            '    qs.annotate(semana=TruncWeek("creado"))\n'
            '    qs.order_by("-fecha_contacto__date")\n'
        )
        hallazgos = hallazgos_en(codigo)
        self.assertEqual(len(hallazgos), 4, hallazgos)
        self.assertIn("fecha_ingreso__date", hallazgos[0])
        self.assertIn("fecha_egreso__date__gte", hallazgos[1])
        self.assertIn("TruncWeek", hallazgos[2])
        self.assertIn("-fecha_contacto__date", hallazgos[3])
        self.assertIn("(fecha_contacto es DateTimeField)", hallazgos[3])

    def test_la_guardia_no_molesta_sobre_un_datefield_ni_con_el_pragma(self):
        """``TruncMonth`` sobre un ``DateField`` compila a ``DATE_FORMAT``: es seguro.

        ``fecha_admision`` (``LegajoAtencion``) es el caso real que hay en el repo
        (``legajos/views/dashboard_simple.py``) y no se tiene que reportar.
        """
        codigo = (
            "from django.db.models.functions import TruncMonth\n"
            'qs.annotate(mes=TruncMonth("fecha_admision"))\n'
            "qs.filter(fecha_ingreso__date=hoy)  # sql-portable: ok\n"
        )
        self.assertEqual(hallazgos_en(codigo), [])

    def test_el_recorrido_llega_a_los_servicios_de_dispositivos(self):
        """Si el recorrido dejara de ver archivos, el test de arriba quedaría verde solo."""
        archivos = {ruta.name for ruta in archivos_productivos()}
        for esperado in ("registro_diario.py", "reportes.py", "utils_fechas.py"):
            self.assertIn(esperado, archivos)
