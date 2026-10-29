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

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
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
        patch("programas.views.revision.catalogo_geografico", side_effect=_catalogo).start()
        patch("programas.forms.catalogo", side_effect=_catalogo).start()
        patch("programas.forms.catalogo_geografico", side_effect=_catalogo).start()
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
        patch("programas.forms.catalogo_geografico", side_effect=_catalogo).start()
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


class PadronGeograficoRevisionTests(_BaseAprobacionTest):
    """El modal usa el padrón verificado, no la lista incompleta de la API."""

    def setUp(self):
        super().setUp()
        from programas.models import LocalidadSiis, ProvinciaSiis

        self.chaco = ProvinciaSiis.objects.create(siis_id=1, nombre="CHACO", clave="chaco")
        self.bsas = ProvinciaSiis.objects.create(siis_id=21, nombre="BUENOS AIRES", clave="buenos aires")
        LocalidadSiis.objects.create(provincia=self.chaco, siis_id=1, nombre="RESISTENCIA", clave="resistencia")
        LocalidadSiis.objects.create(provincia=self.bsas, siis_id=1, nombre="LA PLATA", clave="la plata")
        self.api = patch(
            "programas.services.siis.SiisAPIClient.catalogo", side_effect=AssertionError("No usar API")
        ).start()
        patch("programas.forms.catalogo", side_effect=_catalogo).start()
        patch("programas.forms.listar_programas", return_value=[]).start()
        self.addCleanup(patch.stopall)

    def test_endpoint_ofrece_localidades_de_buenos_aires(self):
        respuesta = self.client.get(reverse("becas:siis_localidades"), {"provincia": 21})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"localidades": [{"id": 1, "nombre": "LA PLATA"}]})
        self.api.assert_not_called()

    def test_formulario_ofrece_ids_de_provincia_del_padron(self):
        from programas.forms import DatosSiisForm

        form = DatosSiisForm()
        for campo in ("prov_actual", "prov_nacim"):
            self.assertIn(("21", "BUENOS AIRES"), form.fields[campo].choices)
            self.assertIn(("1", "CHACO"), form.fields[campo].choices)

    def test_ids_repetidos_se_validan_por_provincia_en_ambos_campos(self):
        from programas.forms import DatosSiisForm

        for provincia in (1, 21):
            with self.subTest(provincia=provincia):
                form = DatosSiisForm(
                    {
                        "prov_actual": str(provincia),
                        "loc_actual": "1",
                        "prov_nacim": str(provincia),
                        "loc_nacim": "1",
                    }
                )
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.como_datos_siis()["prov_actual"], provincia)

    def test_localidad_no_se_resuelve_sin_provincia_si_el_id_se_repite(self):
        from programas.forms import DatosSiisForm

        form = DatosSiisForm({"loc_actual": "1", "loc_nacim": "1"})
        self.assertFalse(form.is_valid())
        self.assertIn("prov_actual", form.errors)
        self.assertIn("prov_nacim", form.errors)

    def test_localidad_de_otra_provincia_se_rechaza_en_ambos_campos(self):
        from programas.forms import DatosSiisForm
        from programas.models import LocalidadSiis

        LocalidadSiis.objects.create(provincia=self.chaco, siis_id=64, nombre="CASTELLI", clave="castelli")
        form = DatosSiisForm({"prov_actual": "21", "loc_actual": "64", "prov_nacim": "21", "loc_nacim": "64"})
        self.assertFalse(form.is_valid())
        self.assertIn("no pertenece a la provincia", str(form.errors["loc_actual"]))
        self.assertIn("no pertenece a la provincia", str(form.errors["loc_nacim"]))

    def test_valida_localidades_con_provincias_ya_guardadas(self):
        from programas.forms import DatosSiisForm

        form = DatosSiisForm({"loc_actual": "1", "loc_nacim": "1"}, actuales={"prov_actual": 21, "prov_nacim": 1})
        self.assertTrue(form.is_valid(), form.errors)

    def test_endpoint_sin_padron_informa_como_cargarlo(self):
        from programas.models import LocalidadSiis

        LocalidadSiis.objects.all().delete()
        respuesta = self.client.get(reverse("becas:siis_localidades"), {"provincia": 21})
        self.assertEqual(respuesta.status_code, 503)
        self.assertIn("seed_catalogo_siis", respuesta.json()["error"])

    def test_lectura_repetida_del_padron_no_agrega_consultas(self):
        from programas.services.siis import catalogo_geografico

        for nombre in ("provincias", "localidades"):
            with self.subTest(catalogo=nombre):
                inicial = catalogo_geografico(nombre)
                with self.assertNumQueries(0):
                    self.assertEqual(catalogo_geografico(nombre), inicial)

    def test_seed_invalida_el_padron_ausente_cacheado(self):
        from programas.models import ProvinciaSiis
        from programas.services.siis import SiisCatalogError, catalogo_geografico

        ProvinciaSiis.objects.all().delete()
        for nombre in ("provincias", "localidades"):
            with self.assertRaises(SiisCatalogError):
                catalogo_geografico(nombre)
            with self.assertNumQueries(0), self.assertRaises(SiisCatalogError):
                catalogo_geografico(nombre)
        with self.captureOnCommitCallbacks(execute=True):
            call_command("seed_catalogo_siis", stdout=StringIO())
        self.assertIn({"id": 21, "nombre": "BUENOS AIRES"}, catalogo_geografico("provincias"))
        self.assertIn({"id": 1, "nombre": "LA PLATA", "id_provincia": 21}, catalogo_geografico("localidades"))


class InvalidarPadronGeograficoSinCacheTests(SimpleTestCase):
    """Un cache caído no puede impedir el arranque (bootstrap con ``seed_catalogo_siis``)."""

    def test_cache_caido_no_propaga_y_deja_warning(self):
        from django_redis.exceptions import ConnectionInterrupted

        from core.performance.cache_utils import invalidar_tras_commit
        from programas.services.siis import claves_padron_geografico

        with patch(
            "core.performance.cache_utils.cache.delete_many",
            side_effect=ConnectionInterrupted(connection=None),
        ):
            with self.assertLogs("django", level="WARNING") as capturado:
                invalidar_tras_commit(claves_padron_geografico())
        self.assertIn("No se pudo invalidar cache", capturado.output[0])

    def test_refrescar_catalogos_con_cache_caido_no_propaga(self):
        from django_redis.exceptions import ConnectionInterrupted

        from programas.services.siis import CATALOGOS_MAESTROS, SiisAPIClient, refrescar_catalogos_locales

        with (
            patch("core.performance.cache_utils.cache.delete", side_effect=ConnectionInterrupted(connection=None)),
            patch.object(SiisAPIClient, "catalogo", return_value=[{"id": 1}]),
            self.assertLogs("django", level="WARNING"),
        ):
            actualizados, fallados = refrescar_catalogos_locales()
        self.assertEqual(len(actualizados), len(CATALOGOS_MAESTROS))
        self.assertEqual(fallados, [])
