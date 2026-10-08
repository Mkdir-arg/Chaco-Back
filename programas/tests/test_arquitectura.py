"""Ratchets de arquitectura: ciclos de import y aristas vista→vista (RED-79).

Dos cosas que hoy están mal y que no se pueden arreglar de un saque:

1. **Ciclos de import.** Ninguno revienta porque en cada uno hay al menos un
   import **diferido** (adentro de una función) que lo sostiene. Una «limpieza de
   imports» que suba ese import al encabezado —el tipo de cambio que nadie revisa dos
   veces— deja el proyecto sin arrancar.
2. **Aristas de una vista a otra** en `programas/views/`. No son un error: son el
   síntoma de que hay helpers compartidos viviendo en el módulo equivocado.

El PR 5 de la Ola 2 bajó los dos techos: las aristas vista→vista pasaron de nueve a
siete y los ciclos de seis a cinco, moviendo los guards de alcance, el filtro de
RN-P13 y `_programas_qs` a `services/`. Bajarlos es lo que el ratchet mide en la otra
dirección: una entrada que ya no existe tiene que salir de la lista en el mismo PR.

Por eso **no** se escribe «ninguna vista importa de otra»: ese test fallaba en nueve
lugares desde el día uno y lo habrían apagado. Lo que se escribe es un techo: lo medido
hoy queda fijo y solo puede bajar.

El tercer cabo de la ficha —el invariante de alcance escrito tres veces y dos
`_assert_scope` con semánticas distintas— lo fija `GuardsDeAlcanceTests`.
"""

import ast
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]

# Las apps del repo. `config` entra porque settings y urls también participan del grafo.
APPS = (
    "config",
    "configuracion",
    "conversaciones",
    "core",
    "dashboard",
    "healthcheck",
    "legajos",
    "portal",
    "programas",
    "users",
)

# Ciclos medidos hoy, con el import que los sostiene entre paréntesis. Los tres
# primeros son los que nombra la ficha; los dos últimos los agregó la medición de este
# PR (la ficha decía 3, el detector encuentra 5).
CICLOS_CONOCIDOS = {
    # `_alcance_requisito` y `_campo_dict`, privados que cada uno le pide al otro.
    ("programas.services.becas", "programas.services.diseno"),
    # El ciclo `views.configuracion ↔ views.dashboard_becas` lo cerró la Ola 2 (PR 5):
    # `_programas_qs` pasó a `services.autorizacion.programas_siis_visibles`.
    # `_roles_asignables_queryset`, que el form le pide al selector y viceversa.
    ("users.forms", "users.selectors.usuarios"),
    # El modelo le pide al servicio de inscripciones (diferido en el modelo).
    ("programas.models", "programas.services.inscripciones"),
    # BEC-07: `Segmento.clean` cuenta los aprobados con `get_cupo_stats` (diferido
    # en el modelo). La alternativa era copiar el COUNT dentro del modelo, que es
    # la clase de duplicación que `cupo_ocupado` —la columna estática que nadie
    # mantiene— ya causó una vez.
    ("programas.models", "programas.services.cupo"),
    # El proceso masivo importa el envío a SIIS en el encabezado y el envío lo
    # devuelve diferido: el único de los cinco con una pata ya a nivel de módulo.
    ("programas.services.proceso_masivo", "programas.services.siis_envio"),
}

# Aristas vista→vista de `programas/views/`, medidas hoy. `ajax_utils` queda exento:
# es un helper compartido a propósito, no un acoplamiento accidental.
EXENTOS = {"ajax_utils"}
#
# Seis: la Ola 2 (PR 5) bajó el techo de nueve a siete. `dashboard_becas →
# configuracion` se fue con `_programas_qs` (hoy `autorizacion.programas_siis_visibles`)
# y `pausas → relevamientos` con `CAP_RELEVAMIENTO_PUBLICO` (hoy en `autorizacion`).
# `revision → relevamientos` se fue con PERF-02 (Ola 4): `PaginadorConConteo` y la
# hidratación por pk viven en `programas.services.listados`, que es de donde las toman
# las tres vistas que paginan casos.
ARISTAS_CONOCIDAS = {
    ("admisiones", "dispositivos_legajo"),
    ("configuracion", "dashboard_becas"),
    ("configuracion", "diseno"),
    ("reportes", "dispositivos_legajo"),
    ("reportes", "merenderos"),
    ("revision", "cupo"),
}


def _modulos_del_repo():
    """`{nombre_de_modulo: ruta}` de las apps, sin migraciones ni tests."""
    modulos = {}
    for app in APPS:
        for archivo in (RAIZ / app).rglob("*.py"):
            partes = list(archivo.relative_to(RAIZ).parts)
            if "migrations" in partes or "tests" in partes or partes[-1].startswith("test_"):
                continue
            if partes[-1] == "__init__.py":
                nombre = ".".join(partes[:-1])
            else:
                nombre = ".".join(partes)[: -len(".py")]
            modulos[nombre] = archivo
    return modulos


def _es_paquete(nombre):
    return (RAIZ / Path(nombre.replace(".", "/")) / "__init__.py").exists()


def _destinos_del_import(nodo, modulo_actual):
    """Los nombres de módulo a los que apunta un `import` / `from … import`.

    De `from a.b import c` salen dos candidatos (`a.b` y `a.b.c`): sin importar de
    verdad no se puede saber si `c` es un submódulo o un símbolo, así que se devuelven
    los dos y el llamador se queda con el que existe como archivo.
    """
    if isinstance(nodo, ast.Import):
        return [alias.name for alias in nodo.names]
    if not isinstance(nodo, ast.ImportFrom):
        return []
    modulo = nodo.module or ""
    if nodo.level:  # import relativo
        base = modulo_actual.split(".") if _es_paquete(modulo_actual) else modulo_actual.split(".")[:-1]
        base = base[: len(base) - (nodo.level - 1)]
        modulo = ".".join(base + ([modulo] if modulo else []))
    return [modulo] + [f"{modulo}.{alias.name}" for alias in nodo.names]


def _nodos_de_nivel_de_modulo(arbol):
    """Ids de los nodos que corren al importar (incluye los de un `if`/`try` de arriba).

    Lo que queda afuera es el import **diferido**: el que está adentro de una función o
    un método y que hoy es lo único que impide que los ciclos exploten.
    """
    tope = set()

    def marcar(cuerpo):
        for nodo in cuerpo:
            tope.add(id(nodo))
            if isinstance(nodo, (ast.If, ast.Try)):
                marcar(nodo.body)
                marcar(nodo.orelse)
                marcar(getattr(nodo, "finalbody", []))
                for manejador in getattr(nodo, "handlers", []):
                    marcar(manejador.body)

    marcar(arbol.body)
    return tope


@lru_cache(maxsize=1)
def _grafo_de_imports():
    """`{(origen, destino): {"modulo"|"diferido"}}` sobre los módulos del repo.

    Cacheado: parsear las ~700 fuentes del repo lleva un par de segundos y lo piden
    seis tests.
    """
    modulos = _modulos_del_repo()
    conocidos = set(modulos)
    aristas = defaultdict(set)
    for nombre, archivo in modulos.items():
        arbol = ast.parse(archivo.read_text(encoding="utf-8"), str(archivo))
        tope = _nodos_de_nivel_de_modulo(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.Import, ast.ImportFrom)):
                continue
            cuando = "modulo" if id(nodo) in tope else "diferido"
            for destino in _destinos_del_import(nodo, nombre):
                if destino in conocidos and destino != nombre:
                    aristas[(nombre, destino)].add(cuando)
    return dict(aristas)


def _emparentados(uno, otro):
    """Un paquete y su submódulo se importan entre sí por diseño (`models/__init__.py`
    re-exporta `models/base.py`, que importa del paquete). No es un ciclo."""
    return uno.startswith(f"{otro}.") or otro.startswith(f"{uno}.")


def _ciclos_de_hoy():
    aristas = _grafo_de_imports()
    salientes = defaultdict(set)
    for origen, destino in aristas:
        if not _emparentados(origen, destino):
            salientes[origen].add(destino)
    return {
        tuple(sorted((origen, destino)))
        for origen, destinos in salientes.items()
        for destino in destinos
        if origen in salientes.get(destino, ())
    }


def _aristas_entre_vistas_de_hoy():
    paquete = "programas.views"
    aristas = set()
    for (origen, destino), _cuando in _grafo_de_imports().items():
        if not origen.startswith(f"{paquete}.") or not destino.startswith(f"{paquete}."):
            continue
        corto_origen = origen.rsplit(".", 1)[1]
        corto_destino = destino.rsplit(".", 1)[1]
        if corto_destino in EXENTOS or corto_origen == "__init__":
            continue
        aristas.add((corto_origen, corto_destino))
    return aristas


class ImportsTests(SimpleTestCase):
    def test_el_detector_ve_el_grafo(self):
        """Control del andamio: con el grafo vacío los ratchets pasarían solos."""
        aristas = _grafo_de_imports()

        self.assertGreater(len(aristas), 500)
        self.assertIn(("programas.services.diseno", "programas.services.becas"), aristas)

    def test_no_hay_ciclos_nuevos(self):
        nuevos = sorted(_ciclos_de_hoy() - CICLOS_CONOCIDOS)

        self.assertEqual(
            nuevos,
            [],
            f"ciclos de import nuevos: {nuevos}. Sostenerlos con un import diferido "
            "funciona hasta que alguien lo sube al encabezado y el proyecto no arranca. "
            "Si el ciclo es inevitable, agregarlo acá con el motivo.",
        )

    def test_los_ciclos_resueltos_salen_de_la_lista(self):
        """Un ratchet que no se aprieta deja de medir. Si un ciclo se arregló, el techo
        baja en el mismo PR."""
        resueltos = sorted(CICLOS_CONOCIDOS - _ciclos_de_hoy())

        self.assertEqual(
            resueltos,
            [],
            f"ciclos que ya no existen: {resueltos}. Sacarlos de CICLOS_CONOCIDOS.",
        )

    def test_cada_ciclo_conocido_tiene_al_menos_un_import_diferido(self):
        """Lo que los mantiene vivos. Si los dos lados pasan a importarse a nivel de
        módulo, el proyecto no arranca: eso no llega a este test, lo frena el import
        de la suite. El test cubre el caso contrario: que no se pierda la razón por la
        que hoy funcionan.
        """
        aristas = _grafo_de_imports()
        for uno, otro in sorted(CICLOS_CONOCIDOS):
            with self.subTest(ciclo=(uno, otro)):
                cuando = aristas.get((uno, otro), set()) | aristas.get((otro, uno), set())
                self.assertIn("diferido", cuando)


class CapasTests(SimpleTestCase):
    def test_no_crecen_las_dependencias_entre_vistas(self):
        nuevas = sorted(_aristas_entre_vistas_de_hoy() - ARISTAS_CONOCIDAS)

        self.assertEqual(
            nuevas,
            [],
            f"aristas vista→vista nuevas: {nuevas}. Una vista que le pide algo a otra "
            "vista es un helper en el módulo equivocado: va a `services/`, a "
            "`selectors/` o a `ajax_utils`.",
        )

    def test_las_aristas_resueltas_salen_de_la_lista(self):
        resueltas = sorted(ARISTAS_CONOCIDAS - _aristas_entre_vistas_de_hoy())

        self.assertEqual(
            resueltas,
            [],
            f"aristas que ya no existen: {resueltas}. Sacarlas de ARISTAS_CONOCIDAS "
            "(es lo que la Ola 2, PR 5, tiene que hacer con las que resuelva).",
        )

    def test_ajax_utils_sigue_siendo_el_unico_exento(self):
        """La exención es chica a propósito: si mañana hay tres módulos exentos, el
        ratchet dejó de medir nada."""
        self.assertEqual(EXENTOS, {"ajax_utils"})


class CeldaSeguraTests(SimpleTestCase):
    """`celda_segura` es transversal y vive en `core` (revisión de la ronda 1 del #626).

    `legajos/views/ciudadanos.py` y `legajos/views/dashboard_simple.py` importaban
    `programas.services.exportacion_reportes` **solo** por esta función: dos CSV que no
    tienen nada que ver con Becas quedaban colgados del paquete de Becas. En `programas`
    queda la re-exportación, que es lo que usan sus propias vistas y sus tests.
    """

    def test_la_definicion_vive_en_core(self):
        from core.exportacion import celda_segura
        from programas.services import exportacion_reportes

        self.assertIs(exportacion_reportes.celda_segura, celda_segura)
        self.assertEqual(celda_segura.__module__, "core.exportacion")

    def test_legajos_no_importa_el_paquete_de_becas_por_una_celda(self):
        aristas = _grafo_de_imports()
        destino = "programas.services.exportacion_reportes"

        culpables = sorted(origen for origen, otro in aristas if otro == destino and origen.startswith("legajos."))

        self.assertEqual(
            culpables, [], f"importan `{destino}`: {culpables}. `celda_segura` está en `core.exportacion`."
        )


class GuardsDeAlcanceTests(SimpleTestCase):
    """El invariante de alcance, ahora en un solo lugar (SEC-21 + RED-79, Ola 2 PR 5).

    Estaba escrito tres veces —`relevamientos._assert_scope`,
    `revision._assert_scope_relevamiento` y `revision._assert_scope_formulario`, tres
    cuerpos para la misma regla— y había **dos** funciones `_assert_scope` con
    semánticas distintas (una miraba un relevamiento, la otra un segmento). Hoy la
    regla vive en `services.autorizacion` y las vistas la llaman.

    Este test es la otra mitad del ratchet: si alguien vuelve a escribir una copia
    privada en una vista, acá queda registrado que no debería estar.
    """

    def test_el_guard_vive_en_autorizacion_y_las_vistas_no_tienen_copia(self):
        from programas.services import autorizacion
        from programas.views import configuracion, cupo, relevamientos, revision

        self.assertTrue(callable(autorizacion.assert_alcance_relevamiento))
        self.assertTrue(callable(autorizacion.assert_alcance_formulario))
        for modulo in (relevamientos, revision, configuracion, cupo):
            for nombre in ("_assert_scope", "_assert_scope_relevamiento", "_assert_scope_formulario"):
                with self.subTest(modulo=modulo.__name__, funcion=nombre):
                    self.assertFalse(hasattr(modulo, nombre))

    def test_el_homonimo_peligroso_quedo_con_nombre_propio(self):
        """`configuracion._assert_scope` miraba un segmento y se leía igual que el de
        relevamientos, que miraba un relevamiento."""
        from programas.views import configuracion

        self.assertEqual(configuracion._assert_scope_segmento.__code__.co_varnames[1], "segmento")

    def test_el_filtro_de_publicos_tiene_un_solo_dueno(self):
        """Estaba escrito dos veces, con el mismo efecto y distinto camino a la capacidad."""
        from programas.services import autorizacion
        from programas.views import relevamientos, revision

        self.assertTrue(callable(autorizacion.sin_formularios_publicos_si_no_puede))
        self.assertFalse(hasattr(relevamientos, "_sin_formularios_publicos_si_no_puede"))
        self.assertFalse(hasattr(relevamientos, "_sin_publicos_si_no_puede"))
        self.assertFalse(hasattr(revision, "_sin_formularios_publicos_si_no_puede"))

    def test_la_constante_de_la_capacidad_publica_tiene_un_solo_dueno(self):
        """`CAP_RELEVAMIENTO_PUBLICO` la definía `relevamientos` y la importaban `pausas`
        y `revision`: dos de las nueve aristas vista→vista. Hoy es de `autorizacion`."""
        from programas.services import autorizacion
        from programas.views import pausas, relevamientos, revision

        self.assertEqual(autorizacion.CAP_RELEVAMIENTO_PUBLICO, "becas.relevamiento.publico")
        for modulo in (relevamientos, pausas, revision):
            with self.subTest(modulo=modulo.__name__):
                self.assertFalse(hasattr(modulo, "CAP_RELEVAMIENTO_PUBLICO"))
