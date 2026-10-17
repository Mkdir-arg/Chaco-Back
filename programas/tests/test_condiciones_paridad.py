"""Paridad del motor de condiciones: navegador vs servidor (#895).

``programas/services/condiciones.py`` decide qué se exige y qué se guarda; su espejo
``static/custom/js/nodo-condiciones.js`` decide qué ve la persona mientras completa
(paso 2 del link y vista previa del constructor). Si divergen, la pantalla muestra un
formulario distinto del que el servidor reclama. Los dos corren acá sobre la **misma**
tabla de casos (``condiciones_paridad.json``), con una fecha de referencia fija, y se
compara visible/oculto por clave. La tabla además fija lo que el servidor tiene que
decidir: si los dos motores se corren juntos para el mismo lado, también se ve.
"""

import json
import subprocess
from datetime import date
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import NODE, requiere_node
from programas.services.condiciones import MODOS, OPERADORES_POR_TIPO, aplicar, validar_coherencia

TABLA = Path(__file__).with_name("condiciones_paridad.json")
RUNNER = Path(__file__).parent / "js" / "paridad_condiciones.cjs"
MOTOR_JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-condiciones.js"


def _tabla():
    return json.loads(TABLA.read_text(encoding="utf-8"))


def _variantes(tabla):
    """``(id, caso, variante)`` por cada variante, con el id que usa el runner de JS."""
    for caso in tabla["casos"]:
        for n, variante in enumerate(caso["variantes"]):
            yield f"{caso['caso']}#{n}", caso, variante


def _reglas(condicion):
    return (condicion or {}).get("reglas") or []


class TablaDeParidadTests(SimpleTestCase):
    """La tabla misma: que cubra lo que promete y que sus diseños sean reales."""

    def test_cubre_todos_los_operadores_de_cada_tipo_y_los_dos_modos(self):
        tabla = _tabla()
        usados, modos = set(), set()
        for caso in tabla["casos"]:
            tipos = {item["clave"]: item.get("tipo_campo") for item in caso["items"]}
            for item in caso["items"]:
                condicion = item.get("condicion") or {}
                if _reglas(condicion):
                    modos.add(condicion.get("modo"))
                for regla in _reglas(condicion):
                    if regla["fuente"] in tipos:
                        usados.add((tipos[regla["fuente"]], regla["op"]))

        esperados = {(str(tipo), op) for tipo, ops in OPERADORES_POR_TIPO.items() for op in ops}
        self.assertEqual(esperados - usados, set(), "operadores de OPERADORES_POR_TIPO sin caso en la tabla")
        self.assertTrue(set(MODOS) <= modos, f"modos sin caso: {set(MODOS) - modos}")

    def test_los_disenos_son_coherentes_salvo_la_fuente_fuera_del_diseno(self):
        for caso in _tabla()["casos"]:
            with self.subTest(caso=caso["caso"]):
                errores = validar_coherencia(caso["items"])
                if caso.get("fuera_del_diseno"):
                    self.assertTrue(errores, "el caso dice que la fuente falta, pero el diseño es coherente")
                else:
                    self.assertEqual(errores, {})

    def test_la_fecha_de_referencia_es_fija(self):
        self.assertEqual(date.fromisoformat(_tabla()["hoy"]), date(2026, 8, 28))


class ServidorTests(SimpleTestCase):
    """El servidor —la autoridad— decide lo que dice la tabla."""

    def test_el_servidor_decide_lo_que_dice_la_tabla(self):
        tabla = _tabla()
        hoy = date.fromisoformat(tabla["hoy"])
        for id_, caso, variante in _variantes(tabla):
            with self.subTest(variante=id_, nota=variante.get("nota", "")):
                visibles, ocultos, _ = aplicar(caso["items"], variante["respuestas"], hoy)
                self.assertEqual(visibles | ocultos, {item["clave"] for item in caso["items"]})
                self.assertEqual(ocultos, set(variante["ocultos"]))


@requiere_node
class NavegadorTests(SimpleTestCase):
    """``nodo-condiciones.js`` decide lo mismo que el servidor, clave por clave."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        proceso = subprocess.run(
            [NODE, str(RUNNER), str(MOTOR_JS), str(TABLA)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
        if proceso.returncode != 0:
            raise AssertionError(f"node falló:\n{proceso.stderr}")
        cls.navegador = json.loads(proceso.stdout)

    def test_el_navegador_decide_lo_mismo_que_el_servidor(self):
        tabla = _tabla()
        hoy = date.fromisoformat(tabla["hoy"])
        for id_, caso, variante in _variantes(tabla):
            with self.subTest(variante=id_, nota=variante.get("nota", ""), respuestas=variante["respuestas"]):
                visibles, ocultos, _ = aplicar(caso["items"], variante["respuestas"], hoy)
                js = self.navegador[id_]
                self.assertEqual(
                    {"visibles": set(js["visibles"]), "ocultos": set(js["ocultos"])},
                    {"visibles": visibles, "ocultos": ocultos},
                    "el navegador (primero) decide distinto que el servidor (segundo)",
                )

    def test_corre_todas_las_variantes(self):
        self.assertEqual(set(self.navegador), {id_ for id_, _, _ in _variantes(_tabla())})
