"""Las alertas en tiempo real muestran nombre y mensaje como texto (Cambio 95).

``static/custom/js/alertas_websocket.js`` (se carga en todo el backoffice cuando hay
websockets) armaba el toast, el modal de alerta crítica y la vista previa del menú con
``innerHTML`` y el nombre del ciudadano sin escapar. Se ejecuta el archivo real con
``node`` sobre un DOM simulado.
"""

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import atributos_de, correr_script_pagina, requiere_node

MARCADO = '<img src=x onerror="window.__inyectado=1">'
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

    def test_toast(self):
        self.assertSinMarcadoInyectado(self._html_de("__ws.showToast(__alerta);", "document.createElement()"))

    def test_modal_de_alerta_critica(self):
        html = self._html_de("__ws.showCriticalModal(__alerta);", "document.createElement()")
        self.assertSinMarcadoInyectado(html)
        self.assertIn('href="/legajos/4/"', html)

    def test_vista_previa_del_menu(self):
        acciones = (
            f"__respuestas['/legajos/alertas/preview/'] = {json.dumps({'results': [ALERTA]})};\n"
            "__ws.loadAlertasPreview();\n"
        )
        self.assertSinMarcadoInyectado(self._html_de(acciones, "document.querySelector()"))
