from django.test import SimpleTestCase

from core.coordenadas import url_domicilio_en_google_maps


class UrlDomicilioTests(SimpleTestCase):
    def test_busca_direccion_localidad_y_provincia(self):
        self.assertEqual(
            url_domicilio_en_google_maps("Av. Sarmiento 1200", "Resistencia", "Chaco"),
            "https://www.google.com/maps/search/?api=1&query=Av.%20Sarmiento%201200%2C%20Resistencia%2C%20Chaco%2C%20Argentina",
        )

    def test_sin_localidad_no_deja_comas_vacias(self):
        self.assertEqual(
            url_domicilio_en_google_maps(" Barrio 100 Viviendas ", "", "Chaco"),
            "https://www.google.com/maps/search/?api=1&query=Barrio%20100%20Viviendas%2C%20Chaco%2C%20Argentina",
        )

    def test_sin_direccion_no_hay_enlace(self):
        for vacia in (None, "", "   "):
            self.assertIsNone(url_domicilio_en_google_maps(vacia, "Resistencia", "Chaco"))

    def test_codifica_lo_que_rompe_la_url(self):
        url = url_domicilio_en_google_maps("Calle 5 & 8 #3", "Fontana", "Chaco")
        self.assertNotIn("&query=Calle 5 &", url)
        self.assertIn("Calle%205%20%26%208%20%233", url)
