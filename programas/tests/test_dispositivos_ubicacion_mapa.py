"""Legajo de Dispositivos: el bloque «Ubicación» usa el domicilio con mapa (Cambio 490, fase 2)."""

from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from programas.models import Dispositivo
from programas.tests.test_dispositivos_equipo_ui_411 import BaseUI


class UbicacionConMapaTests(BaseUI):
    def setUp(self):
        super().setUp()
        self.par_admin = f"{self.admin.pk}:{self.rol_admin.pk}"

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="mapa-chaco")
    def test_el_alta_trae_la_pieza_y_el_cargador(self):
        self._entrar(self.admin)
        respuesta = self.client.get(reverse("dispositivos:crear"))

        self.assertContains(respuesta, "data-nodo-ubicacion")
        self.assertContains(respuesta, 'data-localidad="id_localidad"')
        self.assertContains(respuesta, 'id="nodo-mapa-config"')
        self.assertContains(respuesta, "custom/js/nodo-ubicacion.js")
        self.assertContains(respuesta, "custom/css/nodo-ubicacion.css")
        self.assertIn("https://*.googleapis.com", respuesta.headers["Content-Security-Policy"])
        # Una sola vez cada campo, aunque la grilla ya no los recorra con el bucle.
        html = respuesta.content.decode()
        for nombre in ("localidad", "domicilio", "latitud", "longitud"):
            self.assertEqual(html.count(f'name="{nombre}"'), 1, nombre)

    def test_las_coordenadas_que_completa_el_mapa_se_guardan(self):
        self._entrar(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:crear"),
            {
                "codigo": "MAPA-1",
                "tipo": self.tipo.pk,
                "nombre": "Con mapa",
                "domicilio": "Av. Sarmiento 1250",
                "latitud": "-27.458427",
                "longitud": "-58.995889",
                "responsables": [self.par_admin],
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        nuevo = Dispositivo.objects.get(codigo="MAPA-1")
        self.assertEqual((nuevo.latitud, nuevo.longitud), (Decimal("-27.458427"), Decimal("-58.995889")))

    def test_un_error_en_la_latitud_deja_abiertos_los_campos_a_mano(self):
        self._entrar(self.admin)
        respuesta = self.client.post(
            reverse("dispositivos:crear"),
            {
                "codigo": "MAPA-2",
                "tipo": self.tipo.pk,
                "nombre": "X",
                "latitud": "abc",
                "responsables": [self.par_admin],
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "data-manual-abierto")
