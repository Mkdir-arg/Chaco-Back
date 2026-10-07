"""FE-25 · `alertas_websocket.js` deja de tener su propio sistema de avisos.

El archivo se carga en **todo** el backoffice cuando `WEBSOCKETS_ENABLED` está en
verdadero, y traía dos piezas paralelas a las canónicas:

- una pila `alert-toast` propia, con markup e `innerHTML` propios, sin rol ARIA ni live
  region, apilada en el mismo lugar que los toasts del shell;
- un modal de alerta crítica armado a mano, con `bg-gray-200`/`bg-red-600` (clases que el
  build no genera), sin foco atrapado ni Escape, y con un enlace a `/legajos/<id>/`, ruta
  que no existe (FE-09).

Ahora los avisos salen por `window.toast` y el modal por `ModernModal`, las dos piezas
del shell. El destino de «Ver» lo arma el shell con `{% url %}`.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import correr_script_pagina, requiere_node

JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "alertas_websocket.js"
SHELL = Path(settings.BASE_DIR) / "templates" / "includes" / "base.html"

ALERTA = {
    "id": 1,
    "prioridad": "CRITICA",
    "ciudadano": "Mirta Pérez",
    "ciudadano_id": 7,
    "mensaje": "Riesgo de vida",
    "fecha": "01/09/2026",
    "legajo_id": 4,
}

#: Reemplaza las piezas del shell por espías. Van en las *acciones* (después del
#: script) a propósito: el archivo las resuelve recién al llamarlas.
_ESPIAS = """
__log.toasts = [];
__log.modales = [];
__log.navegacion = [];
var __ultimoModal = null;
window.toast = function (tipo, mensaje, opciones) { __log.toasts.push([tipo, mensaje, opciones || null]); };
window.ModernModal = {show: function (o) { __ultimoModal = o; __log.modales.push({type: o.type, title: o.title, message: o.message, confirmText: o.confirmText || null}); }};
window.location = {assign: function (url) { __log.navegacion.push(url); }};
window.alertasConfig = {ciudadanoDetalleUrlTemplate: '/legajos/ciudadanos/0/'};
var __ws = Object.create(AlertasWebSocket.prototype);
var __alerta = %(alerta)s;
"""


@requiere_node
class AvisosPorElSistemaDelShellTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = JS.read_text(encoding="utf-8")

    def correr(self, acciones, alerta=None):
        espias = _ESPIAS % {"alerta": json.dumps(alerta or ALERTA)}
        return correr_script_pagina(self.script, espias + acciones)

    def test_el_toast_lo_dibuja_window_toast(self):
        log = self.correr("__ws.showToast(__alerta);")
        self.assertEqual(len(log["toasts"]), 1)
        tipo, mensaje, _ = log["toasts"][0]
        self.assertEqual(tipo, "error")
        self.assertIn("Mirta Pérez", mensaje)
        self.assertIn("Riesgo de vida", mensaje)

    def test_una_alerta_no_critica_avisa_como_advertencia(self):
        log = self.correr("__ws.showToast(__alerta);", alerta={**ALERTA, "prioridad": "ALTA"})
        self.assertEqual(log["toasts"][0][0], "warning")

    def test_el_toast_no_arma_markup_propio(self):
        log = self.correr("__ws.showToast(__alerta);")
        self.assertEqual(log["html"], {}, "showToast no puede escribir innerHTML")

    def test_el_modal_critico_es_el_del_shell(self):
        log = self.correr("__ws.showCriticalModal(__alerta);")
        self.assertEqual(len(log["modales"]), 1)
        modal = log["modales"][0]
        self.assertEqual(modal["type"], "warning")
        self.assertEqual(modal["confirmText"], "Ver")
        self.assertIn("Mirta Pérez", modal["message"])
        self.assertEqual(log["html"], {}, "showCriticalModal no puede escribir innerHTML")

    def test_ver_lleva_al_detalle_del_ciudadano(self):
        log = self.correr("__ws.showCriticalModal(__alerta);\n__ultimoModal.onConfirm();")
        self.assertEqual(log["navegacion"], ["/legajos/ciudadanos/7/"])

    def test_sin_plantilla_de_url_el_modal_no_ofrece_ver(self):
        log = self.correr("window.alertasConfig = null;\n__ws.showCriticalModal(__alerta);")
        self.assertIsNone(log["modales"][0]["confirmText"])

    def test_sin_ciudadano_el_modal_no_ofrece_ver(self):
        log = self.correr("__ws.showCriticalModal(__alerta);", alerta={**ALERTA, "ciudadano_id": None})
        self.assertIsNone(log["modales"][0]["confirmText"])


class SinPiezasParalelasTests(SimpleTestCase):
    """Lo que ya no puede volver al archivo."""

    def setUp(self):
        self.texto = JS.read_text(encoding="utf-8")

    def assertAusente(self, aguja):
        self.assertFalse(aguja in self.texto, f"alertas_websocket.js todavía nombra {aguja!r}")

    def test_no_queda_la_pila_de_avisos_propia(self):
        self.assertAusente("alert-" + "toast")

    def test_no_queda_el_overlay_de_modal_armado_a_mano(self):
        self.assertAusente("fixed inset-0 z-50")

    def test_no_queda_la_ruta_de_legajo_que_no_existe(self):
        self.assertAusente("/legajos/${")

    def test_no_quedan_clases_que_el_build_no_genera(self):
        for clase in ("bg-gray-200", "hover:bg-gray-300", "hover:bg-gray-50", "border-gray-100"):
            with self.subTest(clase=clase):
                self.assertAusente(clase)

    def test_el_destino_del_ver_no_es_una_url_literal(self):
        self.assertTrue("ciudadanoDetalleUrlTemplate" in self.texto)


class PlantillaDeUrlEnElShellTests(TestCase):
    """El shell publica la plantilla con `{% url %}`; el JS no sabe rutas."""

    def test_el_shell_declara_la_plantilla(self):
        self.assertIn("ciudadanoDetalleUrlTemplate", SHELL.read_text(encoding="utf-8"))

    def test_la_plantilla_llega_renderizada_y_resuelve(self):
        User = get_user_model()
        User.objects.create_user(username="ana", password="x" * 14)
        self.client.login(username="ana", password="x" * 14)
        html = self.client.get(reverse("core:inicio")).content.decode()
        esperado = reverse("legajos:ciudadano_detalle", args=[0])
        self.assertIn(f'ciudadanoDetalleUrlTemplate: "{esperado}"', html)
        self.assertEqual(esperado.replace("/0/", "/7/"), reverse("legajos:ciudadano_detalle", args=[7]))
