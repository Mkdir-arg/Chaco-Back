"""Configuración de Google Maps: CSP condicionada a la key, `core.W005` y capacidades del mapa."""

from django.test import SimpleTestCase, override_settings

from config.middlewares.security_headers import _politica
from core import rbac
from core.checks import google_maps_con_map_id


def _directiva(politica, nombre):
    for parte in politica.split("; "):
        if parte.split(" ", 1)[0] == nombre:
            return parte
    raise AssertionError(f"La política no tiene {nombre}: {politica}")


class CspGoogleMapsTests(SimpleTestCase):
    @override_settings(GOOGLE_MAPS_API_KEY="", GTM_CONTAINER_ID="", CSP_EXTRA_SOURCES={})
    def test_sin_key_la_politica_no_se_abre_a_google_maps(self):
        politica = _politica()

        # `www.google.com` y `www.gstatic.com` siguen: son del reCAPTCHA de la política base.
        self.assertNotIn("googleapis.com", politica)
        self.assertNotIn("https://*.gstatic.com", politica)
        self.assertNotIn("blob:", _directiva(politica, "script-src"))

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba", GTM_CONTAINER_ID="", CSP_EXTRA_SOURCES={})
    def test_con_key_suma_los_hosts_de_la_guia_de_google(self):
        politica = _politica()

        script = _directiva(politica, "script-src")
        for host in ("https://*.googleapis.com", "https://*.gstatic.com", "https://*.google.com", "blob:"):
            self.assertIn(host, script)
        self.assertIn("https://*.gstatic.com", _directiva(politica, "img-src"))
        self.assertIn("https://*.googleapis.com", _directiva(politica, "connect-src"))
        self.assertIn("https://fonts.gstatic.com", _directiva(politica, "font-src"))
        self.assertIn("https://fonts.googleapis.com", _directiva(politica, "style-src"))
        # Lo que la política base cierra sigue cerrado.
        self.assertEqual(_directiva(politica, "frame-ancestors"), "frame-ancestors 'none'")
        self.assertEqual(_directiva(politica, "object-src"), "object-src 'none'")

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba", GTM_CONTAINER_ID="", CSP_EXTRA_SOURCES={})
    def test_ningun_host_de_google_va_por_http_ni_sin_esquema(self):
        for valores in _politica().split("; "):
            for fuente in valores.split(" ")[1:]:
                if "google" in fuente or "gstatic" in fuente or "ggpht" in fuente:
                    self.assertTrue(fuente.startswith("https://"), fuente)


class MapIdEnAmbienteServidoTests(SimpleTestCase):
    @override_settings(ENVIRONMENT="prd", GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="")
    def test_key_sin_map_id_en_produccion_avisa(self):
        self.assertEqual([m.id for m in google_maps_con_map_id(None)], ["core.W005"])

    @override_settings(ENVIRONMENT="qa", GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="DEMO_MAP_ID")
    def test_el_map_id_de_demo_en_un_ambiente_servido_avisa(self):
        self.assertEqual([m.id for m in google_maps_con_map_id(None)], ["core.W005"])

    @override_settings(ENVIRONMENT="prd", GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="abc123")
    def test_con_map_id_propio_no_avisa(self):
        self.assertEqual(google_maps_con_map_id(None), [])

    @override_settings(ENVIRONMENT="prd", GOOGLE_MAPS_API_KEY="", GOOGLE_MAPS_MAP_ID="")
    def test_sin_key_no_avisa(self):
        self.assertEqual(google_maps_con_map_id(None), [])

    @override_settings(ENVIRONMENT="dev", GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="DEMO_MAP_ID")
    def test_en_desarrollo_el_demo_alcanza(self):
        self.assertEqual(google_maps_con_map_id(None), [])


class CapacidadesMapaTests(SimpleTestCase):
    def test_el_catalogo_trae_ver_y_editar_globales(self):
        modulo = next(m for m in rbac.CATALOGO if m["modulo"] == "mapa")

        self.assertEqual([c for c, _ in modulo["capacidades"]], ["mapa.ver", "mapa.editar"])
        self.assertNotIn("alcance", modulo)
        self.assertEqual(rbac.perm_de("mapa.ver"), "users.mapa_ver")
