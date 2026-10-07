"""Guardia: una sola regla de «DNI válido» en el código productivo (RED-48).

Antes de este cambio «DNI válido» estaba escrito **ocho** veces con **cuatro** reglas
de largo distintas. La diferencia no la veía nadie, porque las dos puntas callan: el
padrón descartaba la fila en silencio (la contaba en `rechazadas`) y `siis_envio`
mandaba a SIIS —que no tiene baja— lo que los formularios rechazaban.

`programas/tests/test_padron.py::DniValidoTests` prueba que las puertas de hoy se
comportan igual. Esto es la otra mitad: recorre el código productivo con `ast` y falla
cuando aparece una **novena** regla escrita a mano, que es el modo real de que esto se
vuelva a abrir —nadie va a cambiar las ocho, alguien va a agregar la novena—.

Qué marca: una comparación de largo (`len(...)`) contra 6, 7, 8, 9 o 10 en una línea
que habla de un DNI. La salida es usar `core.dni.dni_valido`; si de verdad hace falta
otra cosa, se deja `# regla-dni: ok` en la línea con el motivo al lado. Hoy el repo no
tiene ninguna excepción y la idea es que siga así.
"""

import ast
import re
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test import SimpleTestCase

#: Los largos con los que se compara un documento. 11 queda afuera a propósito: es el
#: CUIT, que no es un DNI.
LARGOS_SOSPECHOSOS = {6, 7, 8, 9, 10}

PRAGMA = "regla-dni: ok"

#: Cómo se nombra un DNI en este repo. Sin `\b` al final: `dni_apoderado` y `dni_limpio`
#: son el mismo dato. `cuit` entra porque de ahí se extrae uno; del falso positivo lo
#: salva el largo (11 no está en LARGOS_SOSPECHOSOS).
NOMBRE_DNI = re.compile(r"dni|documento|cuit", re.IGNORECASE)

DIRECTORIOS_IGNORADOS = {"migrations", "tests", "__pycache__", "node_modules", "static", "templates", "fixtures"}

#: La casa de la regla: acá los largos son la definición, no una copia.
EXCEPTUADOS = {"core/dni.py"}


def _es_de_tests(ruta: Path) -> bool:
    return ruta.name.startswith("test_") or ruta.name.endswith("_tests.py") or ruta.name == "conftest.py"


def raices_productivas():
    """Carpetas de código propio: las apps del repo más `config/` y `scripts/`."""
    base = Path(settings.BASE_DIR).resolve()
    raices = {base / "config"}
    for config in apps.get_app_configs():
        ruta = Path(config.path).resolve()
        if base in ruta.parents or ruta == base:
            raices.add(ruta)
    return sorted(ruta for ruta in raices if ruta.is_dir())


def archivos_productivos():
    base = Path(settings.BASE_DIR).resolve()
    for raiz in raices_productivas():
        for ruta in sorted(raiz.rglob("*.py")):
            if DIRECTORIOS_IGNORADOS & set(ruta.relative_to(raiz).parts[:-1]) or _es_de_tests(ruta):
                continue
            if ruta.relative_to(base).as_posix() in EXCEPTUADOS:
                continue
            yield ruta


def _es_len(nodo):
    return isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "len" and nodo.args


def _enteros_sospechosos(nodos):
    for nodo in nodos:
        if isinstance(nodo, ast.Constant) and nodo.value in LARGOS_SOSPECHOSOS:
            yield nodo.value
        elif isinstance(nodo, (ast.Tuple, ast.List, ast.Set)):
            yield from _enteros_sospechosos(nodo.elts)


def _sentencias_que_hablan_de_dni(arbol):
    """Las sentencias cuyo texto —condición y cuerpo— nombra un documento.

    Hace falta porque no toda regla usa una variable que se llame `dni`: el form
    dinámico del portal medía `len(valor)` adentro de la rama
    `if item["vinculo"] == "dni"`, y el mensaje de error es el que dice de qué se
    está hablando.
    """
    marcadas = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.If, ast.While, ast.Assert, ast.Return, ast.Expr, ast.Assign)) and NOMBRE_DNI.search(
            ast.unparse(nodo)
        ):
            for interno in ast.walk(nodo):
                marcadas.add(id(interno))
    return marcadas


def hallazgos_en(codigo, nombre="<codigo>"):
    """Comparaciones de largo de un DNI contra un número, fuera de `core.dni`."""
    arbol = ast.parse(codigo)
    lineas = codigo.splitlines()
    de_dni = _sentencias_que_hablan_de_dni(arbol)
    encontrados = []

    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Compare):
            continue
        partes = [nodo.left, *nodo.comparators]
        if not any(_es_len(parte) for parte in partes):
            continue
        if not (NOMBRE_DNI.search(ast.unparse(nodo)) or id(nodo) in de_dni):
            continue
        largos = sorted(set(_enteros_sospechosos(partes)))
        if not largos:
            continue
        linea = lineas[nodo.lineno - 1] if 0 < nodo.lineno <= len(lineas) else ""
        if PRAGMA in linea:
            continue
        encontrados.append(f"{nombre}:{nodo.lineno}: {ast.unparse(nodo)} (largos {largos})")
    return encontrados


class UnaSolaReglaDeDniTests(SimpleTestCase):
    def test_ningun_modulo_productivo_escribe_su_propia_regla(self):
        base = Path(settings.BASE_DIR).resolve()
        hallazgos = []
        for ruta in archivos_productivos():
            hallazgos += hallazgos_en(ruta.read_text(encoding="utf-8"), ruta.relative_to(base).as_posix())

        self.assertEqual(
            hallazgos,
            [],
            "regla de DNI escrita a mano:\n  "
            + "\n  ".join(hallazgos)
            + "\nUsar `core.dni.dni_valido` (RED-48). Si el caso es realmente distinto, "
            f"dejar `# {PRAGMA}` en la línea con el motivo.",
        )

    def test_el_detector_encuentra_las_cuatro_formas_que_habia_en_el_repo(self):
        """Las reglas reales que este PR retiró, para que la guardia no sea decorativa."""
        casos = [
            "if len(dni) not in (7, 8):\n    pass\n",
            "if not 7 <= len(dni) <= 8:\n    pass\n",
            "if len(dni) < 6 or len(dni) > 9:\n    pass\n",
            "if dni and len(dni) <= 10:\n    pass\n",
            "return dni if len(dni) == 8 else None\n",
            "if len(dni_apoderado) not in (7, 8):\n    pass\n",
        ]
        for codigo in casos:
            with self.subTest(codigo=codigo.splitlines()[0]):
                self.assertTrue(hallazgos_en(codigo), f"no detectó: {codigo!r}")

    def test_el_pragma_y_lo_que_no_es_un_dni_no_se_reportan(self):
        self.assertEqual(hallazgos_en("if len(dni) == 8:  # regla-dni: ok motivo\n    pass\n"), [])
        self.assertEqual(hallazgos_en("if len(celular) == 10:\n    pass\n"), [])
        self.assertEqual(hallazgos_en("if len(cuit_limpio) != 11:\n    pass\n"), [])

    def test_la_regla_canonica_es_la_que_dice_la_ficha(self):
        from core.dni import LARGOS_DNI_VALIDOS

        self.assertEqual(LARGOS_DNI_VALIDOS, (7, 8))
