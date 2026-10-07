"""Toda capacidad que el código evalúa existe en el `CATALOGO` (RED-44).

`core/rbac.py::puede` resuelve contra el conjunto de códigos que el usuario
tiene: un código **inexistente** no levanta nada, devuelve `False`. Y como
`is_superuser` tiene bypass total, quien suele probar el cambio —el admin— lo ve
todo igual. Renombrar `becas.cupo.ver` en el `CATALOGO` y actualizar cuatro de
los cinco usos hace desaparecer una pantalla para todos los roles sin un solo
error en el log.

El test cruza las dos direcciones:

1. **Todo literal evaluado existe en el catálogo.** Se extraen por AST los
   argumentos posicionales de `requiere(...)`, `puede(...)`, `puede_alguna(...)`,
   `RequiereCapacidad(...)` y lo asignado a `capacidades_requeridas`, resolviendo
   las constantes `CAP_*`/`CAPS_*` del repo; más los tags de template
   (`|puede:"..."`, `{% puede_en user "..." %}`).
2. **Toda capacidad del catálogo se usa**, o está declarada en
   `CAPACIDADES_SIN_USO` con su motivo. Una capacidad que se tilda en el ABM de
   Roles y que nadie evalúa es una promesa que la pantalla no cumple.

Al 07/10/2026 los dos pasan: el test es gratis y lo único que hace es volverse
rojo el día que alguien se equivoque al tipear.
"""

import ast
import difflib
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core import rbac
from programas.services.autorizacion import CAPS_GESTION

RAIZ = Path(settings.BASE_DIR)

# `docs/design-kb/` guarda copias históricas de templates: no son código vivo.
EXCLUIDOS = {".git", ".venv", ".venv312", ".venv-e2e", "node_modules", "staticfiles", "docs", "media", "htmlcov"}

FUNCIONES_DE_CAPACIDAD = {
    "requiere",
    "requiere_alguna",
    "puede",
    "puede_alguna",
    "RequiereCapacidad",
    # Dispositivos resuelve el alcance por su propio programa, pero la capacidad
    # que recibe es del mismo catálogo.
    "puede_en_programa_dispositivos",
    "puede_operar_dispositivo",
}
# Los dos mixins de CBV: `capacidades_requeridas` (core.rbac) y `capacidad_requerida`
# (el de Dispositivos, en singular).
ATRIBUTOS_DE_CAPACIDAD = {"capacidades_requeridas", "capacidad_requerida"}

# Forma de un código de capacidad: `modulo.accion`, `becas.programa.administrar`…
FORMA = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)+$")

# `{% if request.user|puede:"ciudadano.crear" %}`
FILTRO_PUEDE = re.compile(r"""\|\s*puede\s*:\s*(?P<comilla>["'])(?P<codigo>[^"']+)(?P=comilla)""")
# `{% puede_en user "x.y" prog %}`, `{% puede_en_programa_dispositivos user "x.y" as v %}`,
# `{% puede_operar_dispositivo user disp "x.y" as v %}`: la capacidad es el literal
# con forma de código que va adentro del tag.
TAGS_DE_CAPACIDAD = re.compile(
    r"""\{%\s*(?:puede_en|puede_en_programa_dispositivos|puede_operar_dispositivo)\b[^%]*%\}"""
)
LITERAL = re.compile(r"""(?P<comilla>["'])(?P<codigo>[^"']+)(?P=comilla)""")

# Capacidades del catálogo que hoy nadie evalúa, con el motivo. Que estén acá es
# una decisión, no un olvido: el ABM de Roles las sigue ofreciendo.
CAPACIDADES_SIN_USO = {
    # OPS-14 (Ola 7): el borrado de ciudadanos no está implementado en ninguna
    # vista; la capacidad quedó sembrada esperando esa pantalla.
    "ciudadano.eliminar": "no hay pantalla de borrado de ciudadanos (OPS-14, Ola 7)",
    # Las cuatro siguientes las midió este test el 07/10/2026 (la ficha RED-44
    # solo esperaba `ciudadano.eliminar`): están en el catálogo, el ABM de Roles
    # las ofrece y tildarlas no habilita nada. Qué hacer con cada una lo decide
    # la Ola 7 (OPS-14): o se usan, o salen del catálogo.
    "config.ver": "todo /configuracion/ exige `config.administrar`; nadie evalúa el «ver» (OPS-14)",
    "relevamiento.ver": "Becas usa `becas.relevamiento.ver`; el módulo genérico quedó sin consumidores (OPS-14)",
    "institucion.ver": "no existe el módulo de Instituciones: no hay vista ni URL que la evalúe (OPS-14)",
    "institucion.administrar": "ídem `institucion.ver` (OPS-14)",
}


def _archivos(extension):
    for ruta in RAIZ.rglob(f"*{extension}"):
        if EXCLUIDOS.isdisjoint(parte for parte in ruta.relative_to(RAIZ).parts):
            yield ruta


def _cadenas(nodo, constantes):
    """Strings alcanzables desde `nodo`, resolviendo las constantes del repo."""
    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
        return {nodo.value}
    if isinstance(nodo, (ast.List, ast.Tuple, ast.Set)):
        return set().union(*(_cadenas(e, constantes) for e in nodo.elts)) if nodo.elts else set()
    if isinstance(nodo, ast.Starred):
        return _cadenas(nodo.value, constantes)
    if isinstance(nodo, ast.Name):
        return set(constantes.get(nodo.id, ()))
    if isinstance(nodo, ast.Attribute):
        return set(constantes.get(nodo.attr, ()))
    if isinstance(nodo, ast.BinOp):  # `A + B`, como CAPS_ADMIN_PROGRAMA
        return _cadenas(nodo.left, constantes) | _cadenas(nodo.right, constantes)
    return set()


def _constantes_del_repo(arboles):
    """`{nombre: {códigos}}` de las constantes de módulo con forma de capacidad.

    Se arma global y no por archivo a propósito: `CAP_SEGMENTO_EDITAR` se define
    en `programas/views/configuracion.py` y se importa desde varios módulos.
    Dos pasadas, porque una constante se arma con otra (`CAPS_ENTRADA_ABM_ROLES`).
    """
    constantes = {}
    for _ruta, arbol in arboles:
        for _ in range(2):
            for nodo in arbol.body:
                if not isinstance(nodo, ast.Assign):
                    continue
                codigos = {c for c in _cadenas(nodo.value, constantes) if FORMA.match(c)}
                if not codigos:
                    continue
                for destino in nodo.targets:
                    if isinstance(destino, ast.Name):
                        constantes.setdefault(destino.id, set()).update(codigos)
    return constantes


def _literales_de_python(arboles, constantes):
    """`{código: [archivo:línea, ...]}` de todo literal evaluado como capacidad."""
    usos = {}

    def anotar(codigos, ruta, linea):
        for codigo in codigos:
            if FORMA.match(codigo):
                usos.setdefault(codigo, []).append(f"{ruta.relative_to(RAIZ).as_posix()}:{linea}")

    for ruta, arbol in arboles:
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Call):
                nombre = getattr(nodo.func, "id", None) or getattr(nodo.func, "attr", None)
                if nombre in FUNCIONES_DE_CAPACIDAD:
                    # Solo posicionales: `redirect_to="configuracion:programas"`
                    # no es una capacidad.
                    for argumento in nodo.args:
                        anotar(_cadenas(argumento, constantes), ruta, nodo.lineno)
            elif isinstance(nodo, (ast.Assign, ast.AnnAssign)):
                destinos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
                if any(getattr(d, "id", None) in ATRIBUTOS_DE_CAPACIDAD for d in destinos) and nodo.value is not None:
                    anotar(_cadenas(nodo.value, constantes), ruta, nodo.lineno)
    return usos


def _literales_de_templates():
    usos = {}
    for ruta in _archivos(".html"):
        texto = ruta.read_text(encoding="utf-8", errors="replace")
        nombre = ruta.relative_to(RAIZ).as_posix()

        def anotar(codigo, posicion, _texto=texto, _nombre=nombre):
            if FORMA.match(codigo):
                usos.setdefault(codigo, []).append(f"{_nombre}:{_texto.count(chr(10), 0, posicion) + 1}")

        for coincidencia in FILTRO_PUEDE.finditer(texto):
            anotar(coincidencia.group("codigo"), coincidencia.start())
        for tag in TAGS_DE_CAPACIDAD.finditer(texto):
            for literal in LITERAL.finditer(tag.group(0)):
                anotar(literal.group("codigo"), tag.start())
    return usos


def _arboles():
    arboles = []
    for ruta in _archivos(".py"):
        try:
            arboles.append((ruta, ast.parse(ruta.read_text(encoding="utf-8"))))
        except SyntaxError:  # pragma: no cover - no hay ninguno hoy
            raise AssertionError(f"no se pudo parsear {ruta}")
    return arboles


class CapacidadesEvaluadasTests(SimpleTestCase):
    """RED-44: un código mal tipeado no se puede distinguir de «no tiene permiso»."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        arboles = _arboles()
        constantes = _constantes_del_repo(arboles)
        cls.usos = _literales_de_python(arboles, constantes)
        for codigo, donde in _literales_de_templates().items():
            cls.usos.setdefault(codigo, []).extend(donde)
        cls.catalogo = set(rbac.codigos_de_capacidad())

    def test_el_barrido_encuentra_capacidades(self):
        """Si el extractor deja de ver literales, los dos tests pasarían vacíos."""
        self.assertGreater(len(self.usos), 30, "el extractor de capacidades se rompió")

    def test_toda_capacidad_evaluada_existe_en_el_catalogo(self):
        huerfanas = {}
        for codigo, donde in sorted(self.usos.items()):
            if codigo in self.catalogo:
                continue
            parecidas = difflib.get_close_matches(codigo, sorted(self.catalogo), n=3)
            huerfanas[codigo] = f"{donde[:3]} — ¿quisiste decir {parecidas}?"

        self.assertEqual(
            huerfanas,
            {},
            "capacidades evaluadas que NO están en core.rbac.CATALOGO (devuelven False "
            f"en silencio para todos menos el superusuario): {huerfanas}",
        )

    def test_toda_capacidad_del_catalogo_se_usa_o_esta_declarada_sin_uso(self):
        # `CAPS_GESTION` se calcula del propio catálogo en tiempo de import
        # (`programas/services/autorizacion.py`): las capacidades finas de Becas
        # se evalúan por ahí, no como literal.
        usadas = set(self.usos) | set(CAPS_GESTION) | set(rbac.CAPS_ADMIN_PROGRAMA)

        sin_uso = sorted(self.catalogo - usadas - set(CAPACIDADES_SIN_USO))

        self.assertEqual(
            sin_uso,
            [],
            "capacidades del CATALOGO que nadie evalúa: el ABM de Roles las ofrece y "
            f"tildarlas no habilita nada. Declaralas en CAPACIDADES_SIN_USO con su motivo: {sin_uso}",
        )

    def test_lo_declarado_sin_uso_sigue_sin_usarse(self):
        """Ratchet: cuando la pantalla llega, la entrada sale de la lista."""
        usadas = set(self.usos) | set(CAPS_GESTION) | set(rbac.CAPS_ADMIN_PROGRAMA)

        sobrantes = sorted(c for c in CAPACIDADES_SIN_USO if c in usadas or c not in self.catalogo)

        self.assertEqual(sobrantes, [], f"entradas de CAPACIDADES_SIN_USO que hay que borrar: {sobrantes}")
