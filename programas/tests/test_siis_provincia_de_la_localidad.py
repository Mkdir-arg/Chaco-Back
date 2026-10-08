"""SIIS-18 · Una sola lectura de «de qué provincia es esta localidad del catálogo».

El catálogo de SIIS no tiene una sola forma de decirlo: hay ítems con
`id_provincia`, con `provincia_id`, con `prov_id` y con `provincia` como objeto
anidado. `Catalogos._provincia_de` (el armado del payload) las conoce a las
cuatro; el select dependiente de la revisión y la validación cruzada del modal
miraban solo dos, cada uno las suyas.

Lo que pasaba con las otras dos formas:

* el `<select>` de localidad del modal «Completar datos para SIIS» mostraba la
  localidad de **cualquier** provincia (el `or provincia` del filtro hacía que un
  ítem sin la clave esperada se diera por bueno), y
* la validación cruzada del form dejaba pasar esa misma elección.

Esa localidad va a SIIS adentro del alta, que no tiene baja.
"""

from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from programas.services.siis_envio import provincia_de
from programas.tests.test_becas_revision import _BaseAprobacionTest

#: Las cuatro formas del catálogo, más un ítem sin provincia y uno ilegible.
LOCALIDADES = [
    {"id": 1, "nombre": "Castelli", "id_provincia": 22},
    {"id": 2, "nombre": "Sáenz Peña", "provincia_id": 22},
    {"id": 3, "nombre": "Resistencia", "provincia": {"id": 22, "nombre": "Chaco"}},
    {"id": 4, "nombre": "Goya", "prov_id": 18},
    {"id": 5, "nombre": "Sin provincia"},
    {"id": 6, "nombre": "Provincia ilegible", "id_provincia": "veintidós"},
]


def _catalogo(nombre):
    return {
        "localidades": LOCALIDADES,
        "provincias": [{"id": 22, "nombre": "Chaco"}, {"id": 18, "nombre": "Corrientes"}],
        "estados-civiles": [{"id": 1, "nombre": "Soltero/a"}],
        "jurisdicciones": [{"id": 28, "nombre": "Ministerio de Desarrollo Humano"}],
    }[nombre]


class ProvinciaDeUnItemTests(SimpleTestCase):
    """La función pública: una sola definición, la del armado del payload."""

    def test_reconoce_las_cuatro_formas_del_catalogo(self):
        self.assertEqual([provincia_de(item) for item in LOCALIDADES[:4]], [22, 22, 22, 18])

    def test_un_item_sin_provincia_no_se_inventa_una(self):
        self.assertIsNone(provincia_de(LOCALIDADES[4]))

    def test_una_provincia_ilegible_tampoco(self):
        self.assertIsNone(provincia_de(LOCALIDADES[5]))


class LocalidadesDelSelectTests(_BaseAprobacionTest):
    """SIIS-18: el endpoint que llena el select dependiente de provincia."""

    def setUp(self):
        super().setUp()
        patch("programas.views.revision.catalogo", side_effect=_catalogo).start()
        patch("programas.forms.catalogo", side_effect=_catalogo).start()
        self.addCleanup(patch.stopall)

    def _ids(self, provincia):
        respuesta = self.client.get(reverse("becas:siis_localidades") + f"?provincia={provincia}")
        self.assertEqual(respuesta.status_code, 200)
        return sorted(item["id"] for item in respuesta.json()["localidades"])

    def test_vuelven_las_de_la_provincia_en_sus_cuatro_formas(self):
        self.assertEqual(self._ids(22), [1, 2, 3])

    def test_no_vuelve_la_de_otra_provincia(self):
        self.assertEqual(self._ids(18), [4])

    def test_los_items_sin_provincia_quedan_afuera(self):
        """Antes entraban en **todas**: `i.get(...) or provincia` los daba por buenos."""
        for provincia in (22, 18):
            with self.subTest(provincia=provincia):
                self.assertNotIn(5, self._ids(provincia))
                self.assertNotIn(6, self._ids(provincia))

    def test_sin_provincia_en_la_query_vuelven_todas(self):
        respuesta = self.client.get(reverse("becas:siis_localidades"))

        self.assertEqual(len(respuesta.json()["localidades"]), len(LOCALIDADES))

    def test_anonimo_no_llega_al_endpoint(self):
        self.client.logout()

        respuesta = self.client.get(reverse("becas:siis_localidades") + "?provincia=22")

        self.assertIn(respuesta.status_code, (302, 403))


class LocalidadCruzadaConLaProvinciaTests(_BaseAprobacionTest):
    """SIIS-18 en el form: la validación cruzada usa la misma lectura."""

    def setUp(self):
        super().setUp()
        patch("programas.forms.catalogo", side_effect=_catalogo).start()
        patch("programas.forms.listar_programas", return_value=[{"id": 79, "nombre": "Ñachec"}]).start()
        self.addCleanup(patch.stopall)

    def _form(self, datos, actuales=None):
        from programas.forms import DatosSiisForm

        return DatosSiisForm(data=datos, actuales=actuales or {})

    def test_una_localidad_de_otra_provincia_se_rechaza_en_las_cuatro_formas(self):
        for localidad in (1, 2, 3):
            with self.subTest(localidad=localidad):
                form = self._form({"prov_actual": "18", "loc_actual": str(localidad)})

                self.assertFalse(form.is_valid())
                self.assertIn("no pertenece a la provincia", str(form.errors["loc_actual"]))

    def test_la_localidad_de_la_provincia_elegida_pasa(self):
        form = self._form({"prov_actual": "22", "loc_actual": "3"})

        self.assertTrue(form.is_valid(), form.errors)

    def test_una_localidad_sin_provincia_en_el_catalogo_no_bloquea(self):
        """No se puede afirmar que no corresponda: se deja pasar, como antes."""
        form = self._form({"prov_actual": "22", "loc_actual": "5"})

        self.assertTrue(form.is_valid(), form.errors)
