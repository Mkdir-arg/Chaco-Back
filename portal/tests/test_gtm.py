"""Google Tag Manager en las pantallas públicas de inscripción (Cambio 68).

El contenedor se renderiza solo con ``GTM_CONTAINER_ID`` configurado, y en ese
caso la CSP abre únicamente los hosts de Google que GTM y GA4 necesitan. El
evento de conversión se emite una sola vez por envío.
"""

from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from config.middlewares.security_headers import _politica, parsear_fuentes_extra
from programas.models import Convocatoria, Relevamiento, Segmento


class _Base(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Futuro Chaco 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.rel = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=1),
        )

    def _url(self, nombre):
        return reverse(f"portal:{nombre}", kwargs={"token": self.rel.token_publico})

    def _sembrar_comprobante(self):
        session = self.client.session
        session[f"inscripcion_ok_{self.rel.pk}"] = {"numero": 7, "email": "m***@correo.com", "correo_enviado": False}
        session.save()


@override_settings(GTM_CONTAINER_ID="GTM-TEST123")
class GtmActivoTests(_Base):
    def test_el_paso_1_carga_el_contenedor_y_el_datalayer(self):
        resp = self.client.get(self._url("inscripcion_paso1"))
        html = resp.content.decode()
        self.assertIn("googletagmanager.com/gtm.js", html)
        self.assertIn("'dataLayer','GTM-TEST123'", html)
        self.assertIn("ns.html?id=GTM-TEST123", html)
        # El dataLayer arranca con la pantalla y la convocatoria, nunca con datos de la persona.
        self.assertIn('"pantalla": "inscripcion_paso1"', html)
        self.assertIn('"convocatoria": "Futuro Chaco 2026"', html)
        self.assertIn(f'"convocatoria_id": "{self.convocatoria.pk}"', html)

    def test_la_csp_abre_google_y_conserva_lo_demas(self):
        resp = self.client.get(self._url("inscripcion_paso1"))
        csp = resp.headers.get("Content-Security-Policy", "")
        script_src = next(parte for parte in csp.split(";") if parte.strip().startswith("script-src"))
        connect_src = next(parte for parte in csp.split(";") if parte.strip().startswith("connect-src"))
        frame_src = next(parte for parte in csp.split(";") if parte.strip().startswith("frame-src"))
        self.assertIn("https://*.googletagmanager.com", script_src)
        self.assertIn("https://*.google-analytics.com", connect_src)
        self.assertIn("https://*.analytics.google.com", connect_src)
        self.assertIn("https://www.googletagmanager.com", frame_src)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("form-action 'self'", csp)

    def test_la_confirmacion_emite_la_conversion_una_sola_vez(self):
        self._sembrar_comprobante()
        primera = self.client.get(self._url("inscripcion_confirmacion")).content.decode()
        self.assertIn('"event": "inscripcion_enviada"', primera)
        self.assertIn('"convocatoria": "Futuro Chaco 2026"', primera)
        # Un refresh del comprobante no cuenta dos veces.
        segunda = self.client.get(self._url("inscripcion_confirmacion")).content.decode()
        self.assertNotIn('"event": "inscripcion_enviada"', segunda)
        self.assertIn("Formulario Nº 7", segunda)

    def test_las_pantallas_de_corte_tambien_lo_llevan(self):
        self.rel.fecha_hasta = timezone.now() - timedelta(hours=1)
        self.rel.save(update_fields=["fecha_hasta"])
        html = self.client.get(self._url("inscripcion_paso1")).content.decode()
        self.assertIn("googletagmanager.com/gtm.js", html)

    def test_el_portal_ciudadano_no_lleva_el_contenedor(self):
        html = self.client.get(reverse("portal:home")).content.decode()
        self.assertNotIn("googletagmanager.com", html)


class GtmInactivoTests(_Base):
    @override_settings(GTM_CONTAINER_ID="")
    def test_sin_contenedor_no_se_renderiza_ni_se_abre_la_csp(self):
        resp = self.client.get(self._url("inscripcion_paso1"))
        self.assertNotIn("googletagmanager", resp.content.decode())
        self.assertNotIn("googletagmanager", resp.headers.get("Content-Security-Policy", ""))
        self._sembrar_comprobante()
        self.assertNotIn("inscripcion_enviada", self.client.get(self._url("inscripcion_confirmacion")).content.decode())

    @override_settings(GTM_CONTAINER_ID="GTM-X'\"><script>alert(1)</script>")
    def test_un_id_que_no_tiene_forma_de_contenedor_se_descarta(self):
        html = self.client.get(self._url("inscripcion_paso1")).content.decode()
        self.assertNotIn("googletagmanager", html)
        self.assertNotIn("alert(1)", html)


class FuentesExtraTests(SimpleTestCase):
    def test_parsea_directivas_y_hosts_desde_la_variable(self):
        self.assertEqual(
            parsear_fuentes_extra(
                "connect-src=https://connect.facebook.net https://www.facebook.com; img-src=https://www.facebook.com"
            ),
            {
                "connect-src": ["https://connect.facebook.net", "https://www.facebook.com"],
                "img-src": ["https://www.facebook.com"],
            },
        )
        self.assertEqual(parsear_fuentes_extra(""), {})
        self.assertEqual(parsear_fuentes_extra("basura sin igual;=sin-directiva;script-src="), {})

    @override_settings(CSP_EXTRA_SOURCES={"connect-src": ["https://connect.facebook.net"]}, GTM_CONTAINER_ID="")
    def test_las_fuentes_extra_entran_a_la_politica(self):
        self.assertIn("connect-src 'self' https://connect.facebook.net", _politica())
