"""RED-62 · El gate que exige justificar un presupuesto de performance que sube.

Los números de `scripts/perf_budgets.json` eran autodeclarados: el job falla «16 → 61»,
el autor sube el techo a 61 en el mismo PR y pasa. Acá se prueban las dos puntas —un caso
rojo y uno verde— sobre documentos sintéticos, más la corrida real contra el árbol base.

Un detalle que el script tiene que sostener y los tests fijan: **bajar** un presupuesto
nunca pide nada, y una ruta **nueva** tampoco —no hay techo que aflojar—. Si cualquiera
de las dos pidiera justificación, el gate se volvería ruido y lo primero que haría la
gente es escribir una justificación de trámite.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

from check_perf_budgets import main, resolver_base, sin_justificar, subidas  # noqa: E402

BASE = {
    "_meta": {
        "adjustments": {"viejo": "becas_revision 15→16: la lectura del sidebar."},
        "timing": {"reference_total_ms": 1000.0},
    },
    "budgets": {
        "becas_revision": {"route": "becas:revision", "max_queries": 16, "max_duplicate_queries": 1},
        "inicio": {"route": "core:inicio", "max_queries": 20, "max_duplicate_queries": 0},
    },
    "servicios": {
        "export": {"consultas_fijas": 12, "casos_por_consulta": 2000},
    },
}


def _con(cambios):
    """Copia de BASE con `cambios` aplicados por ruta `a.b.c`."""
    nuevo = copy.deepcopy(BASE)
    for ruta, valor in cambios.items():
        destino = nuevo
        partes = ruta.split(".")
        for parte in partes[:-1]:
            destino = destino[parte]
        destino[partes[-1]] = valor
    return nuevo


class CasoRojoTests(SimpleTestCase):
    def test_subir_max_queries_sin_justificacion_es_un_hallazgo(self):
        ahora = _con({"budgets.becas_revision.max_queries": 61})

        pendientes = sin_justificar(BASE, ahora)

        self.assertEqual([h.presupuesto for h in pendientes], ["becas_revision"])
        self.assertEqual((pendientes[0].antes, pendientes[0].ahora), (16, 61))

    def test_subir_las_duplicadas_tambien_cuenta(self):
        ahora = _con({"budgets.inicio.max_duplicate_queries": 3})

        self.assertEqual([h.campo for h in sin_justificar(BASE, ahora)], ["max_duplicate_queries"])

    def test_un_servicio_que_consulta_mas_seguido_cuenta(self):
        """`casos_por_consulta` baja = una consulta cada menos filas: el techo afloja
        aunque el número del archivo sea **menor**."""
        ahora = _con({"servicios.export.casos_por_consulta": 100})

        self.assertEqual([h.campo for h in sin_justificar(BASE, ahora)], ["casos_por_consulta"])

    def test_un_servicio_con_mas_consultas_fijas_cuenta(self):
        ahora = _con({"servicios.export.consultas_fijas": 20})

        self.assertEqual([h.campo for h in sin_justificar(BASE, ahora)], ["consultas_fijas"])

    def test_correr_la_alarma_de_tiempo_mas_del_margen_cuenta(self):
        ahora = _con({"_meta.timing.reference_total_ms": 1100.0})

        self.assertEqual([h.campo for h in sin_justificar(BASE, ahora)], ["reference_total_ms"])

    def test_aflojar_el_multiplicador_de_la_alarma_cuenta(self):
        """La puerta de atrás: dejar `reference_total_ms` quieta y subir el multiplicador
        corre el techo de tiempo sin que se note en el diff."""
        ahora = _con({"_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 3.0}})
        base = _con({"_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 2.0}})

        self.assertEqual([h.campo for h in sin_justificar(base, ahora)], ["failure_multiplier"])

    def test_una_justificacion_que_no_nombra_el_presupuesto_no_alcanza(self):
        """Desvío (más estricto) respecto de la ficha: pedía «una clave nueva en
        `adjustments`», y con eso una sola entrada tapaba cualquier cantidad de subidas
        en el mismo PR. Tiene que nombrar el presupuesto que sube."""
        ahora = _con(
            {
                "budgets.becas_revision.max_queries": 61,
                "_meta.adjustments": {**BASE["_meta"]["adjustments"], "otra": "se optimizó el inicio."},
            }
        )

        self.assertEqual(len(sin_justificar(BASE, ahora)), 1)

    def test_editar_una_justificacion_vieja_no_habilita_la_subida(self):
        """Revisión de #648. Con «nueva **o modificada**», tocar un carácter de una entrada
        histórica que ya nombra varios presupuestos —`perf_core_legajos_conversaciones`
        nombra `login`, `portal_perfil` y `conversaciones_lista`— habilitaba subirles el
        techo a todos sin escribir una justificación. La entrada tiene que ser nueva."""
        ahora = _con(
            {
                "budgets.becas_revision.max_queries": 18,
                "_meta.adjustments": {"viejo": "becas_revision 16→18: ahora además hidrata por pk."},
            }
        )

        self.assertEqual([h.presupuesto for h in sin_justificar(BASE, ahora)], ["becas_revision"])

    def test_una_clave_corta_nombrada_por_casualidad_no_alcanza(self):
        """Revisión de #648. El match era por substring sobre el texto concatenado, así que
        un presupuesto de nombre corto quedaba «nombrado» por una palabra ajena que lo
        contiene."""
        base = copy.deepcopy(BASE)
        base["budgets"]["login"] = {"route": "users:login", "max_queries": 21, "max_duplicate_queries": 1}
        ahora = copy.deepcopy(base)
        ahora["budgets"]["login"]["max_queries"] = 30
        ahora["_meta"]["adjustments"]["otra"] = "se revisó portal_perfil_login y no se tocó nada."

        self.assertEqual([h.presupuesto for h in sin_justificar(base, ahora)], ["login"])


class CasoVerdeTests(SimpleTestCase):
    def test_sin_cambios_no_hay_nada_que_justificar(self):
        self.assertEqual(subidas(BASE, copy.deepcopy(BASE)), [])

    def test_bajar_un_presupuesto_nunca_pide_justificacion(self):
        self.assertEqual(subidas(BASE, _con({"budgets.becas_revision.max_queries": 12})), [])

    def test_una_ruta_nueva_no_es_una_subida(self):
        ahora = copy.deepcopy(BASE)
        ahora["budgets"]["ruta_nueva"] = {"route": "becas:nueva", "max_queries": 40, "max_duplicate_queries": 2}

        self.assertEqual(subidas(BASE, ahora), [])

    def test_la_justificacion_que_nombra_el_presupuesto_lo_habilita(self):
        ahora = _con(
            {
                "budgets.becas_revision.max_queries": 18,
                "_meta.adjustments": {
                    **BASE["_meta"]["adjustments"],
                    "perf99": "becas_revision 16→18: dos lecturas por índice que evitan una materialización.",
                },
            }
        )

        self.assertEqual(len(subidas(BASE, ahora)), 1)
        self.assertEqual(sin_justificar(BASE, ahora), [])

    def test_la_clave_de_la_entrada_nueva_puede_ser_el_presupuesto(self):
        """«Como palabra o clave exacta»: si la entrada se llama igual que el presupuesto,
        el texto no tiene que repetirlo."""
        ahora = _con(
            {
                "budgets.becas_revision.max_queries": 18,
                "_meta.adjustments": {
                    **BASE["_meta"]["adjustments"],
                    "becas_revision": "dos lecturas por índice que evitan una materialización.",
                },
            }
        )

        self.assertEqual(sin_justificar(BASE, ahora), [])

    def test_la_alarma_de_tiempo_se_justifica_nombrandola_timing(self):
        """`_meta.timing` lleva punto: vale el nombre entero y también su último segmento,
        que es como se lo nombra en prosa."""
        base = _con({"_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 2.0}})
        ahora = _con(
            {
                "_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 3.0},
                "_meta.adjustments": {
                    **BASE["_meta"]["adjustments"],
                    "perf99": "el runner cambió de máquina: se afloja el timing mientras se remide.",
                },
            }
        )

        self.assertEqual(sin_justificar(base, ahora), [])

    def test_mover_la_alarma_de_tiempo_dentro_del_margen_no_cuenta(self):
        self.assertEqual(subidas(BASE, _con({"_meta.timing.reference_total_ms": 1040.0})), [])

    def test_bajar_el_multiplicador_de_la_alarma_no_cuenta(self):
        """Es lo que hace este mismo PR: `failure_multiplier` 3.0 → 2.0."""
        base = _con({"_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 3.0}})
        ahora = _con({"_meta.timing": {"reference_total_ms": 1000.0, "failure_multiplier": 2.0}})

        self.assertEqual(subidas(base, ahora), [])


class ElJobLoCorreTests(SimpleTestCase):
    """Un gate que no está cableado al workflow no es un gate.

    El script se probó con un caso rojo y uno verde más arriba; lo que falta verificar es
    que el job lo ejecute, porque eso no se puede correr desde acá (necesita Actions).
    """

    def test_el_workflow_de_performance_corre_el_script_contra_la_base_del_pr(self):
        workflow = (RAIZ / ".github" / "workflows" / "pr-performance.yml").read_text(encoding="utf-8")

        self.assertIn("python scripts/check_perf_budgets.py --base", workflow)
        # Sin historia completa, `git show <base>:...` no resuelve y el paso no compara
        # nada: el checkout del job tiene que traerla.
        self.assertIn("fetch-depth: 0", workflow)
        # Y el fallback para el disparo por `push`, donde no hay PR del que sacar la base.
        self.assertIn('base="$(git rev-parse HEAD^)"', workflow)

    def test_el_disparo_por_push_compara_contra_todo_el_rango(self):
        """Revisión de #648: con `HEAD^` como única base, un push directo de N commits a
        `development` dejaba sin comparar los N-1 primeros. `github.event.before` es el
        estado anterior al push entero; `HEAD^` queda solo para el primer push de una rama
        y para `workflow_dispatch`, donde `before` no existe o son 40 ceros."""
        workflow = (RAIZ / ".github" / "workflows" / "pr-performance.yml").read_text(encoding="utf-8")

        self.assertIn("github.event.before", workflow)
        self.assertIn("0000000000000000000000000000000000000000", workflow)


class BaseDeComparacionTests(SimpleTestCase):
    """Revisión de #648: se compara contra el merge-base, no contra el tip de la base.

    En el CI da lo mismo (el SHA base del PR ya es antepasado del merge commit), pero en
    un worktree cuyo `origin/development` avanzó más allá de una **bajada** de presupuesto
    el diff contra el tip la lee como subida y el gate sale rojo sin que el PR toque el
    JSON. Reproducido en la revisión con `--base HEAD` contra el JSON de `development`.
    """

    def _merge_base(self):
        resultado = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/development"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            self.skipTest("no hay origin/development en este checkout")
        return resultado.stdout.strip()

    def test_resolver_base_devuelve_el_punto_de_bifurcacion(self):
        self.assertEqual(resolver_base("origin/development"), self._merge_base())

    def test_una_ref_que_no_resuelve_se_devuelve_tal_cual(self):
        """Sin historia común no hay merge-base: el comportamiento vuelve a ser el de
        antes en vez de reventar."""
        self.assertEqual(resolver_base("no-existe-esta-ref"), "no-existe-esta-ref")


class ArchivoRealTests(SimpleTestCase):
    """El script corrido de punta a punta, con `git`, igual que en el CI."""

    def _base(self):
        resultado = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "origin/development"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
            check=False,
        )
        if resultado.returncode != 0:
            self.skipTest("no hay origin/development en este checkout")
        # El tip a propósito: `main()` lo resuelve al merge-base, que es justo lo que
        # hace verde esta corrida en un worktree desactualizado.
        return resultado.stdout.strip()

    def test_el_json_del_repo_se_puede_comparar_consigo_mismo(self):
        ruta = RAIZ / "scripts" / "perf_budgets.json"
        config = json.loads(ruta.read_text(encoding="utf-8"))

        self.assertEqual(subidas(config, config), [])

    def test_el_presupuesto_del_pr_no_sube_nada_sin_justificar(self):
        """Verde de verdad: el mismo comando que corre el job, sobre este PR."""
        self.assertEqual(main(["--base", self._base()]), 0)

    def test_inflar_un_presupuesto_del_repo_devuelve_1(self):
        """Rojo de verdad: se sube un techo del archivo real, sin tocar `adjustments`,
        y el proceso sale con error —que es lo que pone el job en rojo—."""
        import tempfile

        config = json.loads((RAIZ / "scripts" / "perf_budgets.json").read_text(encoding="utf-8"))
        ruta = next(iter(config["budgets"]))
        config["budgets"][ruta]["max_queries"] += 45

        with tempfile.TemporaryDirectory() as carpeta:
            inflado = Path(carpeta) / "perf_budgets.json"
            inflado.write_text(json.dumps(config), encoding="utf-8")

            self.assertEqual(main(["--base", self._base(), "--archivo", str(inflado)]), 1)
