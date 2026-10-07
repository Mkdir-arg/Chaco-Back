"""Las alertas en tiempo real muestran nombre y mensaje como texto (Cambio 95).

``static/custom/js/alertas_websocket.js`` (se carga en todo el backoffice cuando hay
websockets) armaba el toast, el modal de alerta crítica y la vista previa del menú con
``innerHTML`` y el nombre del ciudadano sin escapar. Se ejecuta el archivo real con
``node`` sobre un DOM simulado.

Desde FE-25 el aviso y el modal son los del shell (``window.toast`` y ``ModernModal``),
que escriben con ``textContent``: ahí el nombre ya **no** se escapa a mano, y lo que hay
que verificar es que no vuelva a aparecer un ``innerHTML``. La vista previa del menú
sigue siendo markup propio y sigue escapando (su migración es FE-11/FE-12).

Desde RED-42 la ruta de la vista previa **no está escrita en el script**: la pone el
template en ``#alertas-campana`` (``templates/includes/navbar.html``) como
``data-url-preview``, así que el harness tiene que ofrecer esa campana para que el
script consulte algo.
"""

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import atributos_de, correr_script_pagina, requiere_node

MARCADO = '<img src=x onerror="window.__inyectado=1">'

# La campana del navbar, que es de donde el script saca las dos rutas (RED-42).
# Se intercepta solo ese selector: el resto sigue cayendo en el stub del harness,
# que es el que registra el `innerHTML` bajo la clave `document.querySelector()`.
CAMPANA = (
    "var __qs = document.querySelector;\n"
    "document.querySelector = function (sel) {\n"
    "  if (sel === '#alertas-campana') {\n"
    "    return {dataset: {urlCount: '/legajos/alertas/count/', urlPreview: '/legajos/alertas/preview/'}};\n"
    "  }\n"
    "  return __qs(sel);\n"
    "};\n"
)
ALERTA = {
    "id": 1,
    "prioridad": "CRITICA",
    "ciudadano": MARCADO,
    "ciudadano_nombre": MARCADO,
    "mensaje": MARCADO,
    "fecha": "01/09/2026",
    "legajo_id": 4,
    "creado": "2026-09-01T10:00:00",
}


@requiere_node
class AlertasWebSocketEscapeTests(SimpleTestCase):
    def setUp(self):
        self.script = (Path(settings.BASE_DIR) / "static" / "custom" / "js" / "alertas_websocket.js").read_text(
            encoding="utf-8"
        )

    def _html_de(self, acciones, ruta):
        log = correr_script_pagina(
            self.script,
            f"var __ws = Object.create(AlertasWebSocket.prototype);\nvar __alerta = {json.dumps(ALERTA)};\n{acciones}",
        )
        return log["html"][ruta]

    def assertSinMarcadoInyectado(self, html):
        self.assertNotIn("img", [tag for tag, _ in atributos_de(html)], html)
        self.assertIn("&lt;img src=x", html)

    def _log_de(self, acciones):
        espias = (
            "window.toast = function (t, m) { __log.toast = [t, m]; };\n"
            "window.ModernModal = {show: function (o) { __log.modal = o.message; }};\n"
            "window.alertasConfig = {ciudadanoDetalleUrlTemplate: '/legajos/ciudadanos/0/'};\n"
        )
        return correr_script_pagina(
            self.script,
            f"{espias}var __ws = Object.create(AlertasWebSocket.prototype);\n"
            f"var __alerta = {json.dumps(ALERTA)};\n{acciones}",
        )

    def test_toast(self):
        # El aviso va por la pieza del shell, que escribe con textContent: el marcado
        # llega crudo al sumidero seguro y el script no toca ningún innerHTML.
        log = self._log_de("__ws.showToast(__alerta);")
        self.assertIn(MARCADO, log["toast"][1])
        self.assertEqual(log["html"], {})

    def test_modal_de_alerta_critica(self):
        log = self._log_de("__ws.showCriticalModal(__alerta);")
        self.assertIn(MARCADO, log["modal"])
        self.assertEqual(log["html"], {})

    def test_vista_previa_del_menu(self):
        acciones = (
            CAMPANA
            + f"__respuestas['/legajos/alertas/preview/'] = {json.dumps({'results': [ALERTA]})};\n"
            + "__ws.loadAlertasPreview();\n"
        )
        self.assertSinMarcadoInyectado(self._html_de(acciones, "document.querySelector()"))

    def test_la_ruta_de_la_vista_previa_sale_del_template(self):
        """RED-42: el script no escribe la ruta, la lee de `#alertas-campana`."""
        log = correr_script_pagina(
            self.script,
            CAMPANA + "var __ws = Object.create(AlertasWebSocket.prototype);\n__ws.loadAlertasPreview();\n",
        )

        self.assertEqual(log["fetches"], ["/legajos/alertas/preview/"])

    def test_sin_la_campana_del_navbar_no_consulta_nada(self):
        """Sin la capacidad, el navbar no dibuja la campana y no hay a dónde pegarle."""
        log = correr_script_pagina(
            self.script,
            "document.querySelector = function () { return null; };\n"
            "var __ws = Object.create(AlertasWebSocket.prototype);\n"
            "__ws.loadAlertasPreview();\n__ws.updateAlertasCounter();\n",
        )

        self.assertEqual(log["fetches"], [])
