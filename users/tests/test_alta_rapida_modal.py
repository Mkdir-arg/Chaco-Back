"""El alta rápida de usuario usa el modal del sistema y no alert() (POP-2)."""

import re

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase


class AltaRapidaModalTests(SimpleTestCase):
    def setUp(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        self.html = render_to_string("user/_alta_rapida_modal.html", {}, request=request)

    def test_sin_alert_nativo(self):
        self.assertNotIn("alert(", self.html)

    def test_panel_es_dialogo_nombrado(self):
        self.assertIn('role="dialog"', self.html)
        self.assertIn('aria-modal="true"', self.html)
        self.assertIn('aria-labelledby="quick-user-titulo"', self.html)
        self.assertIn('id="quick-user-titulo"', self.html)

    def test_cierre_con_x_accesible_y_altura_maxima(self):
        self.assertIn('aria-label="Cerrar"', self.html)
        self.assertNotIn(">Cerrar</button>", self.html)
        self.assertIn("max-h-[90vh]", self.html)
        self.assertIn("overflow-y-auto", self.html)

    def test_cada_campo_tiene_label_asociado(self):
        campos = re.findall(r'<(?:input|textarea)[^>]*id="([^"]+)"[^>]*name="(?!tipo|segmento_id)', self.html)
        self.assertGreaterEqual(len(campos), 9)
        for campo in campos:
            self.assertIn(f'<label for="{campo}"', self.html)

    def test_territorial_sin_segmento_se_deshabilita_con_ayuda(self):
        self.assertIn("button.disabled = falta", self.html)
        self.assertIn("Elegí primero la convocatoria: el territorial se crea dentro de su segmento.", self.html)

    def test_respuesta_no_json_avisa_con_toast(self):
        self.assertIn("window.toast('error'", self.html)
        self.assertIn("becasModal.bind", self.html)

    def test_submit_se_deshabilita_mientras_envia(self):
        self.assertIn("submit.disabled = true", self.html)
