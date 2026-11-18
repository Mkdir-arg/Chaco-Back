"""Emergencia: la dirección del Formulario 1 con mapa (Cambio 483, fase 2).

«Nuevo caso» de la mesa y el Formulario 1 de la puerta del dispositivo usan
``components/_ubicacion_domicilio.html`` a pedido (SEC-33). El punto llega a ``crear_caso`` como la
posición del GPS de la app, sin ``precision_m``.
"""

import shutil
import tempfile
from decimal import Decimal

from django.test import override_settings

from programas.forms_emergencia import NuevoCasoMesaForm
from programas.models import CasoEmergencia
from programas.tests.test_emergencia_alojar_vistas import BaseLlegadas
from programas.tests.test_emergencia_mesa import URL_NUEVO, BaseMesa


class MesaConMapaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)

    @override_settings(GOOGLE_MAPS_API_KEY="AIza-prueba", GOOGLE_MAPS_MAP_ID="mapa-chaco")
    def test_nuevo_caso_trae_la_direccion_con_mapa_a_pedido(self):
        respuesta = self.client.get(URL_NUEVO)

        self.assertContains(respuesta, "data-nodo-ubicacion")
        self.assertContains(respuesta, "data-a-pedido")
        self.assertContains(respuesta, 'data-domicilio="id_direccion"')
        self.assertContains(respuesta, 'data-localidad="id_localidad"')
        self.assertContains(respuesta, "custom/js/nodo-ubicacion.js")
        self.assertContains(respuesta, "custom/css/nodo-ubicacion.css")
        html = respuesta.content.decode()
        for nombre in ("direccion", "localidad", "latitud", "longitud", "foto_vivienda", "foto_acceso"):
            self.assertEqual(html.count(f'name="{nombre}"'), 1, nombre)

    def test_el_punto_del_mapa_llega_al_caso_sin_precision(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(latitud="-27.458427", longitud="-58.995889"))

        caso = CasoEmergencia.objects.get()
        self.assertRedirects(respuesta, self._url("caso_detalle", caso))
        self.assertEqual(
            (caso.latitud, caso.longitud, caso.precision_m), (Decimal("-27.458427"), Decimal("-58.995889"), None)
        )

    def test_una_coordenada_fuera_de_rango_vuelve_al_campo_y_abre_la_carga_a_mano(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(latitud="-127.5", longitud="-58.99"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("latitud", respuesta.context["form"].errors)
        self.assertContains(respuesta, "data-manual-abierto", status_code=400)
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_las_coordenadas_son_opcionales(self):
        form = NuevoCasoMesaForm()
        self.assertFalse(form.fields["latitud"].required)
        self.assertFalse(form.fields["longitud"].required)


class PuertaDelDispositivoConMapaTests(BaseLlegadas):
    def test_el_formulario_1_de_la_puerta_trae_la_direccion_con_mapa(self):
        respuesta = self.client.get(self._url("ingreso_directo"))

        self.assertTemplateUsed(respuesta, "programas/emergencia/dispositivo/formulario1.html")
        self.assertContains(respuesta, "data-nodo-ubicacion")
        self.assertContains(respuesta, "data-a-pedido")
        self.assertContains(respuesta, 'id="nodo-mapa-config"')

    def test_avisar_a_la_mesa_guarda_el_punto_de_donde_viene_la_familia(self):
        self.client.post(self._url("avisar"), self._formulario1(latitud="-27.440000", longitud="-58.970000"))

        caso = CasoEmergencia.objects.get()
        self.assertEqual((caso.latitud, caso.longitud), (Decimal("-27.440000"), Decimal("-58.970000")))
