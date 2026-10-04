"""Render de proceso masivo con las piezas del sistema (Ola 3, W3-P-M)."""

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from programas.models import CorridaSiis
from programas.tests.test_proceso_masivo import _BaseProcesoTest


class ProcesoMasivoRenderOla3Tests(_BaseProcesoTest):
    def setUp(self):
        super().setUp()
        admin = User.objects.create_superuser("admin_render_masivo", password="x")
        self.client.force_login(admin)
        self.admin = admin
        self.url = reverse("becas:proceso_masivo", args=[self.programa.pk])

    def test_encabezado_tarjeta_y_aviso_del_sistema(self):
        self._caso()
        html = self.client.get(self.url).content.decode()
        self.assertIn('aria-label="Volver a la ficha del programa"', html)
        self.assertNotIn("max-width: 760px", html)
        self.assertNotIn("font-size:28px", html)
        self.assertIn("space-y-5", html)
        self.assertIn("Pendientes de informar", html)
        self.assertIn("fa-hourglass-half", html)
        self.assertIn('role="status"', html)
        self.assertNotIn('role="alert"', html)

    def test_la_pantalla_dice_a_que_siis_se_informa(self):
        """RED-61: antes de mandar miles de altas sin baja, se ve el destino."""
        self._caso()
        with self.settings(SIIS_API_URL="https://siisapi.ecomdev.ar"):
            html = self.client.get(self.url).content.decode()
        self.assertIn("siisapi.ecomdev.ar", html)

    def test_sin_siis_configurado_la_pantalla_lo_dice(self):
        self._caso()
        with self.settings(SIIS_API_URL=""):
            html = self.client.get(self.url).content.decode()
        self.assertIn("SIIS_API_URL", html)

    def test_en_curso_no_usa_alert_y_conserva_la_relectura(self):
        CorridaSiis.objects.create(
            programa=self.programa, solicitada_por=self.admin, total_pedido=10, latido=timezone.now()
        )
        html = self.client.get(self.url).content.decode()
        self.assertNotIn('role="alert"', html)
        self.assertIn("function releer()", html)
        self.assertIn("data-confirmar-frenar", html)
