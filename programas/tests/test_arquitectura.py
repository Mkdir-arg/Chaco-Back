"""Ratchets de arquitectura: ciclos de import y aristas vista→vista (RED-79).

Dos cosas que hoy están mal y que no se pueden arreglar de un saque:

1. **Cinco ciclos de import.** Ninguno revienta porque en cada uno hay al menos un
   import **diferido** (adentro de una función) que lo sostiene. Una «limpieza de
   imports» que suba ese import al encabezado —el tipo de cambio que nadie revisa dos
   veces— deja el proyecto sin arrancar.
2. **Nueve aristas de una vista a otra** en `programas/views/`. No son un error: son el
   síntoma de que hay helpers compartidos viviendo en el módulo equivocado. Lo
   silencioso es que SEC-21 (Ola 2) va a mover `_assert_scope_formulario` a
   `autorizacion.py`, que ya está en un ciclo, y nadie se lo señalaría.

Por eso **no** se escribe «ninguna vista importa de otra»: ese test falla en nueve
lugares desde el día uno y termina apagado. Lo que se escribe es un techo: lo medido
hoy queda fijo y solo puede bajar. Bajarlo cuesta sacar la entrada de la lista, que es
exactamente el registro que la Ola 2 tiene que dejar.

El tercer cabo de la ficha —el mismo invariante de alcance escrito tres veces y dos
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
    # `_programas_qs` vive en la vista de Configuración y lo usa el dashboard.
    ("programas.views.configuracion", "programas.views.dashboard_becas"),
    # `_roles_asignables_queryset`, que el form le pide al selector y viceversa.
    ("users.forms", "users.selectors.usuarios"),
    # El modelo le pide al servicio de inscripciones (diferido en el modelo).
    ("programas.models", "programas.services.inscripciones"),
    # El proceso masivo importa el envío a SIIS en el encabezado y el envío lo
    # devuelve diferido: el único de los cinco con una pata ya a nivel de módulo.
    ("programas.services.proceso_masivo", "programas.services.siis_envio"),
}

# Aristas vista→vista de `programas/views/`, medidas hoy. `ajax_utils` queda exento:
# es un helper compartido a propósito, no un acoplamiento accidental.
EXENTOS = {"ajax_utils"}
ARISTAS_CONOCIDAS = {
    ("admisiones", "dispositivos_legajo"),
    ("configuracion", "dashboard_becas"),
    ("configuracion", "diseno"),
    ("dashboard_becas", "configuracion"),
    ("pausas", "relevamientos"),
    ("reportes", "dispositivos_legajo"),
    ("reportes", "merenderos"),
    ("revision", "cupo"),
    ("revision", "relevamientos"),
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


class GuardsDeAlcanceTests(SimpleTestCase):
    """El mismo invariante de alcance, escrito en tres lugares, más dos homónimos.

    `relevamientos._assert_scope`, `revision._assert_scope_relevamiento` y
    `revision._assert_scope_formulario` comprueban lo mismo —relevamiento público sin
    la capacidad, segmento gestionable, convocatoria visible— con tres cuerpos
    distintos. Y hay **dos** funciones llamadas `_assert_scope` con semánticas
    diferentes: la de `relevamientos` mira un relevamiento, la de `configuracion` mira
    un segmento. Leer una por la otra es gratis.

    SEC-21 (Ola 2, PR 5) unifica esto en `autorizacion.assert_alcance_relevamiento` /
    `assert_alcance_formulario` y renombra `configuracion._assert_scope` a
    `_assert_scope_segmento`. Hasta entonces, este test deja escrito dónde está cada
    copia: cuando se muevan, se pone rojo y hay que actualizarlo, que es justamente el
    aviso que la ficha pide que nadie se pierda.
    """

    def test_las_tres_copias_del_guard_siguen_donde_estaban(self):
        from programas.views import relevamientos, revision

        self.assertTrue(callable(relevamientos._assert_scope))
        self.assertTrue(callable(revision._assert_scope_relevamiento))
        self.assertTrue(callable(revision._assert_scope_formulario))

    def test_hay_dos_assert_scope_con_semanticas_distintas(self):
        from programas.views import configuracion, relevamientos

        self.assertIsNot(configuracion._assert_scope, relevamientos._assert_scope)
        # El segundo parámetro dice qué mira cada una: ahí está el homónimo peligroso.
        self.assertEqual(configuracion._assert_scope.__code__.co_varnames[1], "segmento")
        self.assertEqual(relevamientos._assert_scope.__code__.co_varnames[1], "relevamiento")

    def test_el_filtro_de_publicos_esta_duplicado_entre_dos_vistas(self):
        """`_sin_formularios_publicos_si_no_puede` está escrita dos veces, con el mismo
        efecto y distinto camino a la capacidad. Se unifica con el resto en SEC-21."""
        from programas.views import relevamientos, revision

        self.assertIsNot(
            relevamientos._sin_formularios_publicos_si_no_puede,
            revision._sin_formularios_publicos_si_no_puede,
        )

    def test_la_constante_de_la_capacidad_publica_tiene_un_solo_dueno(self):
        """`CAP_RELEVAMIENTO_PUBLICO` la define `relevamientos` y la importan `pausas` y
        `revision`: dos de las nueve aristas. Mover la constante a `autorizacion.py`
        (Ola 2) las borra a las dos."""
        from programas.views import pausas, relevamientos, revision

        self.assertEqual(relevamientos.CAP_RELEVAMIENTO_PUBLICO, "becas.relevamiento.publico")
        self.assertIs(pausas.CAP_RELEVAMIENTO_PUBLICO, relevamientos.CAP_RELEVAMIENTO_PUBLICO)
        self.assertIs(revision.CAP_RELEVAMIENTO_PUBLICO, relevamientos.CAP_RELEVAMIENTO_PUBLICO)
