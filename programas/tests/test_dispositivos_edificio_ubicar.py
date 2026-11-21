"""«Ubicar en el mapa» en el formulario de edificio (Cambio 526; pendiente del Cambio 520).

El modal de la solapa Infraestructura carga las coordenadas del inmueble con la pieza de domicilio con mapa
(`components/_ubicacion_domicilio.html`). Es el punto que lee la distancia de «Derivar» de Emergencia.
"""

from decimal import Decimal

from django.test import override_settings
from django.urls import reverse

from programas.forms_dispositivos import EdificioForm
from programas.models import Edificio
from programas.services.edificios import crear_edificio, editar_edificio
from programas.tests.test_dispositivos_capacidad import BaseCapacidad


class UbicarEdificioTests(BaseCapacidad):
    def _datos(self, **extra):
        return {
            "codigo": "EDI-001",
            "nombre": "Predio Sarmiento",
            "calle": "Av. Sarmiento",
            "numero": "1234",
            "localidad": "Resistencia",
            **extra,
        }

    def _crear(self, **extra):
        return crear_edificio(dispositivo=self.cis, usuario=self.operador_cis, **self._datos(**extra))

    def _editar_url(self, edificio):
        return reverse("dispositivos:edificio_editar", args=[self.cis.pk, edificio.pk])

    def test_el_alta_guarda_el_punto_del_mapa(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(
            reverse("dispositivos:edificio_crear", args=[self.cis.pk]),
            self._datos(latitud="-27.451198", longitud="-58.986695"),
        )

        self.assertEqual(respuesta.status_code, 302)
        edificio = Edificio.objects.get(codigo="EDI-001")
        self.assertEqual((edificio.latitud, edificio.longitud), (Decimal("-27.451198"), Decimal("-58.986695")))

    def test_el_alta_sin_punto_sigue_valiendo(self):
        self.client.force_login(self.operador_cis)

        self.client.post(reverse("dispositivos:edificio_crear", args=[self.cis.pk]), self._datos())

        edificio = Edificio.objects.get(codigo="EDI-001")
        self.assertIsNone(edificio.latitud)
        self.assertIsNone(edificio.longitud)

    def test_la_edicion_mueve_el_punto_y_vaciarlo_lo_borra(self):
        edificio = self._crear(latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695"))
        self.client.force_login(self.operador_cis)

        self.client.post(self._editar_url(edificio), self._datos(latitud="-27.5", longitud="-59.1"))
        edificio.refresh_from_db()
        self.assertEqual((edificio.latitud, edificio.longitud), (Decimal("-27.5"), Decimal("-59.1")))

        self.client.post(self._editar_url(edificio), self._datos(latitud="", longitud=""))
        edificio.refresh_from_db()
        self.assertIsNone(edificio.latitud)
        self.assertIsNone(edificio.longitud)

    def test_un_punto_a_medias_o_fuera_de_rango_se_rechaza_y_no_cambia_nada(self):
        edificio = self._crear(latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695"))
        self.client.force_login(self.operador_cis)
        casos = (
            {"latitud": "-27.5", "longitud": ""},
            {"latitud": "", "longitud": "-59.1"},
            {"latitud": "91", "longitud": "-59.1"},
            {"latitud": "-27.5", "longitud": "181"},
        )

        for punto in casos:
            with self.subTest(punto=punto):
                respuesta = self.client.post(
                    self._editar_url(edificio), self._datos(**punto), headers={"X-Requested-With": "XMLHttpRequest"}
                )

                self.assertEqual(respuesta.status_code, 400)
                self.assertTrue({"latitud", "longitud"} & set(respuesta.json()["errors"]))
                edificio.refresh_from_db()
                self.assertEqual(edificio.latitud, Decimal("-27.451198"))

    def test_una_llamada_que_no_trae_el_punto_no_lo_toca(self):
        edificio = self._crear(latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695"))

        editar_edificio(
            edificio=edificio, dispositivo=self.cis, usuario=self.operador_cis, **self._datos(nombre="Otro")
        )

        edificio.refresh_from_db()
        self.assertEqual(edificio.nombre, "Otro")
        self.assertEqual(edificio.latitud, Decimal("-27.451198"))

    def test_el_formulario_de_edicion_llega_con_el_punto_cargado(self):
        edificio = self._crear(latitud=Decimal("-27.451198"), longitud=Decimal("-58.986695"))

        form = EdificioForm(edificio=edificio)

        self.assertEqual(form.initial["latitud"], Decimal("-27.451198"))
        self.assertEqual(form.initial["longitud"], Decimal("-58.986695"))


@override_settings(GOOGLE_MAPS_API_KEY="clave-de-prueba", GOOGLE_MAPS_MAP_ID="mapa-de-prueba")
class ModalDeEdificioConMapaTests(BaseCapacidad):
    def _modal(self, **query):
        self.client.force_login(self.operador_cis)
        respuesta = self.client.get(
            reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura", **query}
        )
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_el_modal_trae_la_pieza_de_mapa_a_pedido_con_la_altura_aparte(self):
        html = self._modal(edificio="nuevo")

        self.assertIn("data-nodo-ubicacion", html)
        self.assertIn('data-domicilio="id_calle"', html)
        self.assertIn('data-domicilio-extra="id_numero"', html)
        self.assertIn('data-localidad="id_localidad"', html)
        self.assertIn('data-provincia-id="id_provincia"', html)
        self.assertIn("data-a-pedido", html)
        self.assertIn("custom/js/nodo-ubicacion.js", html)
        self.assertIn("custom/css/nodo-ubicacion.css", html)
        self.assertEqual(html.count('name="calle"'), 1)

    def test_al_editar_el_punto_vigente_va_en_los_campos(self):
        edificio = crear_edificio(
            dispositivo=self.cis,
            usuario=self.operador_cis,
            codigo="EDI-002",
            nombre="Predio",
            latitud=Decimal("-27.451198"),
            longitud=Decimal("-58.986695"),
        )

        html = self._modal(edificio=edificio.pk)

        self.assertIn('value="-27.451198"', html)
        self.assertIn('value="-58.986695"', html)

    def test_sin_el_modal_abierto_la_pantalla_no_carga_google(self):
        html = self._modal()

        self.assertNotIn("nodo-ubicacion.js", html)
        self.assertNotIn("maps.googleapis.com", html)

    @override_settings(GOOGLE_MAPS_API_KEY="", GOOGLE_MAPS_MAP_ID="")
    def test_sin_key_el_formulario_sigue_con_los_campos_a_mano(self):
        html = self._modal(edificio="nuevo")

        for nombre in ("calle", "numero", "latitud", "longitud"):
            self.assertIn(f'name="{nombre}"', html)
        self.assertNotIn("maps.googleapis.com", html)
        self.assertIn('data-ubicacion-alerta="sin-mapa"', html)
