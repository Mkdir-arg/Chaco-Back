"""Cambio 482: el DNI ya registrado con otro nombre en el backoffice.

«Nuevo caso» de la mesa y «Ingresar igual» / «Avisar a la mesa» del dispositivo muestran el
rechazo de ``crear_caso`` bajo el DNI, conservan lo cargado y ofrecen la casilla de identidad
a revisar, que antes del rechazo no aparece.
"""

from legajos.models import Ciudadano
from programas.models import CasoEmergencia
from programas.tests.test_emergencia_alojar_vistas import BaseLlegadas
from programas.tests.test_emergencia_mesa import URL_NUEVO, BaseMesa

CASILLA = 'name="identidad_en_conflicto"'


class _Conflicto:
    def _url_formulario(self):
        raise NotImplementedError

    def _legajo(self):
        return Ciudadano.objects.create(dni="40732122", nombre="Joaquin", apellido="FARIÑA")

    def _en_conflicto(self, **cambios):
        return self._formulario1(**{"dni": "40732122", "nombre": "Pedro", "apellido": "Gómez", **cambios})

    def test_sin_conflicto_la_casilla_no_aparece(self):
        self.assertNotContains(self.client.get(self._url_formulario()), CASILLA)

    def test_el_conflicto_vuelve_el_formulario_con_el_error_bajo_el_dni_y_la_casilla(self):
        self._legajo()

        respuesta = self.client.post(self._url_formulario(), self._en_conflicto())

        self.assertEqual(respuesta.status_code, 400)
        form = respuesta.context["form"]
        self.assertTrue(form.errors["dni"][0].startswith("Ese DNI ya está registrado como FARIÑA, Joaquin."))
        self.assertContains(respuesta, CASILLA, status_code=400)
        self.assertContains(respuesta, 'value="Pedro"', status_code=400)
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_sin_nombre_ni_apellido_crea_el_caso_con_la_persona_registrada(self):
        legajo = self._legajo()

        respuesta = self.client.post(self._url_formulario(), self._en_conflicto(nombre="", apellido=""))

        self.assertEqual(respuesta.status_code, 302)
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual(caso.grupo.responsable_id, legajo.pk)
        self.assertIsNone(caso.identidad_a_revisar)

    def test_con_la_casilla_crea_el_caso_marcado_y_lo_avisa(self):
        legajo = self._legajo()

        respuesta = self.client.post(self._url_formulario(), self._en_conflicto(identidad_en_conflicto="on"))

        self.assertEqual(respuesta.status_code, 302)
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual(caso.grupo.responsable_id, legajo.pk)
        self.assertEqual(caso.identidad_a_revisar, {"nombre": "Pedro", "apellido": "Gómez"})
        self.assertIn("Quedó con identidad a revisar", " ".join(self._avisos(respuesta)))
        legajo.refresh_from_db()
        self.assertEqual((legajo.nombre, legajo.apellido), ("Joaquin", "FARIÑA"))


class NuevoCasoDniRegistradoTests(_Conflicto, BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _url_formulario(self):
        return URL_NUEVO


class IngresoDirectoDniRegistradoTests(_Conflicto, BaseLlegadas):
    def _url_formulario(self):
        return self._url("ingreso_directo")


class AvisarALaMesaDniRegistradoTests(_Conflicto, BaseLlegadas):
    def _url_formulario(self):
        return self._url("avisar")
