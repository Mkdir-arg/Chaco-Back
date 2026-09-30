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
        self.assertIn("Elegí primero la convocatoria: el territorial se crea dentro de su segmento.", self.html)

    def test_territorial_usa_aria_disabled_no_disabled(self):
        # RONDA 2, hallazgo MINOR #4: con aria-disabled el botón sigue enfocable y el
        # lector de pantalla llega a la ayuda vía aria-describedby; disabled lo sacaría
        # del orden de tabulación. El click se bloquea a mano en el handler.
        self.assertIn("aria-disabled", self.html)
        self.assertNotIn("button.disabled = falta", self.html)
        self.assertIn("button.getAttribute('aria-disabled') === 'true'", self.html)

    def test_respuesta_no_json_avisa_con_toast(self):
        self.assertIn("window.toast('error'", self.html)
        self.assertIn("becasModal.bind", self.html)

    def test_submit_se_deshabilita_mientras_envia(self):
        self.assertIn("submit.disabled = true", self.html)

    def test_cierre_propio_no_depende_de_becas_modal(self):
        # RONDA 2, hallazgo MAJOR #1: X, Cancelar y backdrop llevan data-quick-user-close
        # y el modal escucha esos clics y Escape por su cuenta, sin pasar por
        # window.becasModal (que puede no llegar a cargar).
        # 3 controles con el atributo (backdrop, X, Cancelar) + 1 uso en el selector JS.
        self.assertEqual(self.html.count("data-quick-user-close"), 4)
        self.assertIn("modal.addEventListener('click'", self.html)
        self.assertIn("[data-quick-user-close]", self.html)
        self.assertIn("document.addEventListener('keydown'", self.html)
        self.assertIn("'Escape'", self.html)

    def test_error_hace_scroll_y_foco_al_campo(self):
        # RONDA 2, hallazgo MINOR #2: el error puede quedar fuera de vista en pantallas
        # chicas (está al final del cuerpo desplazable).
        self.assertIn("error.scrollIntoView(", self.html)
        self.assertIn("form.elements.namedItem(primerCampo)", self.html)
        self.assertIn('tabindex="-1"', self.html)

    def test_no_duplica_la_carga_de_becas_modal(self):
        # RONDA 2, hallazgo MINOR #3: si la página ya trae su propio <script
        # src=…becas-modal.js…>, no se inyecta una segunda copia.
        self.assertIn("document.querySelector('script[src*=\"becas-modal.js\"]')", self.html)
        self.assertIn("s.dataset.quickUserAutoload", self.html)
