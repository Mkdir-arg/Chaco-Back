"""Cambio 486: el DNI ya registrado con otro nombre en la API de la app de campo.

Fija el 400 con ``persona_registrada`` en los tres extremos que crean casos (M1, ingreso directo
y aviso a la mesa), el envío con ``identidad_en_conflicto`` y la marca que ve la guardia en la
búsqueda de llegada (§13.2) y en la ficha de la persona 1 (§13.6).
"""

import uuid
from unittest import mock

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.api.views import ConsultaPersonasThrottle
from programas.models import CasoEmergencia, Derivacion, GrupoFamiliar
from programas.tests.base_emergencia_api import (
    CLAVES_DNI_REGISTRADO,
    CLAVES_IDENTIDAD_DECLARADA,
    CLAVES_INTEGRANTE_DETALLE,
    URL_CASOS,
    BaseApiLlegadas,
    _url,
)

DECLARADA = {"nombre": "Pedro", "apellido": "Gómez"}


class DniRegistradoApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.legajo = Ciudadano.objects.create(dni="40732122", nombre="Joaquin", apellido="FARIÑA", genero="M")

    def _urls(self):
        return [
            (URL_CASOS, self.agente),
            (_url("dispositivo-ingreso-directo", self.centro.pk), self.guardia_centro),
            (_url("dispositivo-avisar-mesa", self.centro.pk), self.guardia_centro),
        ]

    def _cuerpo_conflicto(self, url, **cambios):
        cuerpo = self._cuerpo(dni="40.732.122", nombre="Pedro", apellido="Gómez", **cambios)
        if url != URL_CASOS:
            cuerpo.pop("direccion", None)
        return cuerpo

    def test_los_tres_extremos_rechazan_con_persona_registrada(self):
        for url, usuario in self._urls():
            with self.subTest(url=url):
                respuesta = self._como(usuario).post(url, self._cuerpo_conflicto(url), format="multipart")

                self.assertEqual(respuesta.status_code, 400, respuesta.content)
                cuerpo = respuesta.json()
                self.assertEqual(sorted(cuerpo), CLAVES_DNI_REGISTRADO)
                self.assertEqual(cuerpo["code"], "VALIDACION")
                self.assertEqual(cuerpo["persona_registrada"], {"apellido": "FARIÑA", "nombre": "Joaquin"})
                self.assertTrue(cuerpo["dni"][0].startswith("Ese DNI ya está registrado como FARIÑA, Joaquin."))
        self.assertEqual(CasoEmergencia.objects.count(), 0)
        self.assertEqual(GrupoFamiliar.objects.count(), 0)

    def test_con_identidad_en_conflicto_los_tres_extremos_crean_el_caso_marcado(self):
        for url, usuario in self._urls():
            # Es la misma familia en los tres extremos: el caso anterior se cierra para que el siguiente se abra
            # (una familia no tiene dos casos abiertos, Cambio 579) y acá se prueba la identidad, no el duplicado.
            Derivacion.objects.update(estado=Derivacion.Estado.VENCIDA, clave_vigente=None)
            CasoEmergencia.objects.update(estado=CasoEmergencia.Estado.CERRADO, cerrado_en=timezone.now())
            with self.subTest(url=url):
                respuesta = self._como(usuario).post(
                    url, self._cuerpo_conflicto(url, identidad_en_conflicto="true"), format="multipart"
                )

                self.assertEqual(respuesta.status_code, 201, respuesta.content)
        for caso in CasoEmergencia.objects.select_related("grupo"):
            self.assertEqual(caso.grupo.responsable_id, self.legajo.pk)
            self.assertEqual(caso.situacion["identidad_a_revisar"], DECLARADA)
        self.legajo.refresh_from_db()
        self.assertEqual((self.legajo.nombre, self.legajo.apellido), ("Joaquin", "FARIÑA"))

    def test_reenviar_sin_nombre_con_el_mismo_uuid_crea_el_caso(self):
        envio = uuid.uuid4()
        rechazo = self._enviar(uuid_cliente=envio, dni="40732122", nombre="Pedro", apellido="Gómez")

        aceptado = self._enviar(uuid_cliente=envio, dni="40732122", nombre="", apellido="")

        self.assertEqual((rechazo.status_code, aceptado.status_code), (400, 201), aceptado.content)
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual(caso.grupo.responsable_id, self.legajo.pk)
        self.assertIsNone(caso.identidad_a_revisar)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_el_rechazo_cuenta_como_consulta_de_identidad_y_agotada_es_429_sin_el_nombre(self, _rate):
        """SEC-25: el nombre de la persona no se puede enumerar por el envío salteando el tope."""
        cache.clear()
        self.addCleanup(cache.clear)

        primera = self._enviar(dni="40732122", nombre="Pedro", apellido="Gómez")
        segunda = self._enviar(dni="40732122", nombre="Pedro", apellido="Gómez")

        self.assertEqual(primera.status_code, 400)
        self.assertEqual(segunda.status_code, 429, segunda.content)
        self.assertNotIn("FARIÑA", segunda.content.decode())
        self.assertIn("Retry-After", segunda.headers)
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_la_misma_que_la_de_la_consulta_de_identidad(self, _rate):
        cache.clear()
        self.addCleanup(cache.clear)
        self._como(self.agente).post(
            reverse("emergencia_api:personas-consultar"), {"dni": "30111222", "sexo": "F"}, format="json"
        )

        respuesta = self._enviar(dni="40732122", nombre="Pedro", apellido="Gómez")

        self.assertEqual(respuesta.status_code, 429)

    def test_ningun_otro_400_trae_persona_registrada(self):
        respuesta = self._enviar(direccion="", adultos_f=0, adultos_m=0)

        self.assertEqual(respuesta.status_code, 400)
        self.assertNotIn("persona_registrada", respuesta.json())


class MarcaParaLaGuardiaApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        Ciudadano.objects.create(dni="40732122", nombre="Joaquin", apellido="FARIÑA")

    def _marcado(self, aceptar=False):
        datos = {"dni": "40732122", **DECLARADA, "identidad_en_conflicto": True}
        return self._aceptado(**datos) if aceptar else self._derivado(**datos)

    def _revisar(self, caso):
        situacion = {
            **caso.situacion,
            "identidad_revisada": {"por_id": self.operador.pk, "en": "", "observacion": "Ok"},
        }
        CasoEmergencia.objects.filter(pk=caso.pk).update(situacion=situacion)

    def _buscar(self):
        return self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "40732122"})

    def test_la_busqueda_de_llegada_trae_la_marca_pendiente(self):
        self._marcado()

        responsable = self._buscar().json()["derivacion"]["responsable"]

        self.assertEqual(sorted(responsable["identidad_a_revisar"]), CLAVES_IDENTIDAD_DECLARADA)
        self.assertEqual(responsable["identidad_a_revisar"], DECLARADA)
        self.assertEqual((responsable["apellido"], responsable["nombre"]), ("FARIÑA", "Joaquin"))

    def test_revisada_la_busqueda_trae_null(self):
        caso, _derivacion = self._marcado()
        self._revisar(caso)

        self.assertIsNone(self._buscar().json()["derivacion"]["responsable"]["identidad_a_revisar"])

    def test_la_ficha_de_la_persona_1_trae_la_marca_y_las_demas_null(self):
        caso, _derivacion = self._marcado(aceptar=True)
        cliente = self._como(self.guardia_centro)

        primera = cliente.get(_url("caso-integrante", caso.pk, 1))
        segunda = cliente.get(_url("caso-integrante", caso.pk, 2))

        self.assertEqual(primera.status_code, 200, primera.content)
        self.assertEqual(sorted(primera.json()), CLAVES_INTEGRANTE_DETALLE)
        self.assertEqual(primera.json()["identidad_a_revisar"], DECLARADA)
        self.assertIsNone(segunda.json()["identidad_a_revisar"])

    def test_revisada_la_ficha_trae_null(self):
        caso, _derivacion = self._marcado(aceptar=True)
        self._revisar(caso)

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrante", caso.pk, 1))

        self.assertIsNone(respuesta.json()["identidad_a_revisar"])
