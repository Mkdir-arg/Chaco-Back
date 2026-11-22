"""Hallazgos 15 y 16 de la auditoría de Emergencia: la identidad del responsable en «Nuevo caso».

* «Buscar DNI» de la mesa busca **solo en el legajo** (sin RENAPER ni Personas API), con la autorización del
  alta más ``ciudadano.ver``, y solo devuelve apellido, nombre y DNI.
* «Perdió el documento pero sabe el número» sigue el mismo camino que la puerta del dispositivo.
* La identidad a revisar se ve como aviso en la ficha y como marca en la bandeja, sin consultas por fila.
"""

from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import CasoEmergencia
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_mesa as mesa
from programas.services.configuracion_emergencia import sla_vigente
from programas.tests.test_emergencia_casos import T0
from programas.tests.test_emergencia_mesa import URL_BANDEJA, URL_NUEVO, BaseMesa

CIUDADANO_VER = "ciudadano.ver"
OPERAR = "emergencia.operar"
URL_SUGERIR = "/emergencia/casos/personas-sugeridas/"
AVISO = "Identidad a revisar"


class BaseIdentidad(BaseMesa):
    def setUp(self):
        super().setUp()
        self.con_padron = self._persona_de_mesa("mesa-padron", [OPERAR, CIUDADANO_VER], "Mara", "Gil")

    def _legajo(self, dni="40732122", nombre="Joaquin", apellido="FARIÑA", **extra):
        return Ciudadano.objects.create(dni=dni, nombre=nombre, apellido=apellido, **extra)


class BuscarDniDeLaMesaTests(BaseIdentidad):
    def _buscar(self, usuario, q):
        self.client.force_login(usuario)
        return self.client.get(URL_SUGERIR, {"q": q})

    def test_url_del_buscador(self):
        self.assertEqual(reverse("emergencia:personas_sugeridas"), URL_SUGERIR)

    def test_devuelve_solo_apellido_nombre_y_dni(self):
        self._legajo(telefono="3624111222")

        respuesta = self._buscar(self.con_padron, "40732")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta.json()["resultados"], [{"apellido": "FARIÑA", "nombre": "Joaquin", "dni": "40732122"}]
        )
        self.assertEqual(respuesta["Cache-Control"], "no-store")

    def test_sin_ciudadano_ver_es_403_aunque_opere_la_mesa(self):
        self._legajo()

        respuesta = self._buscar(self.operador, "40732")

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn("FARIÑA", respuesta.content.decode())

    def test_quien_no_trabaja_en_la_mesa_es_403_aunque_vea_personas(self):
        self._legajo()
        solo_padron = self._usuario("solo-padron", [CIUDADANO_VER])
        agente = self._usuario("agente-padron", ["emergencia.relevar", CIUDADANO_VER])

        self.assertEqual(self._buscar(solo_padron, "40732").status_code, 403)
        self.assertEqual(self._buscar(agente, "40732").status_code, 403)

    def test_sin_sesion_va_al_login(self):
        self.assertEqual(self.client.get(URL_SUGERIR, {"q": "40732"}).status_code, 302)

    def test_con_menos_de_tres_caracteres_no_busca(self):
        self._legajo()
        self.assertEqual(self._buscar(self.con_padron, "40").json(), {"resultados": [], "hay_mas": False})

    def test_el_formulario_ofrece_el_buscador_solo_con_ciudadano_ver(self):
        self.client.force_login(self.con_padron)
        html = self.client.get(URL_NUEVO).content.decode()
        self.assertIn(f'data-sugerencias-url="{URL_SUGERIR}"', html)
        self.assertIn('data-sugerencias-completa="nombre:id_nombre,apellido:id_apellido"', html)

        self.client.force_login(self.operador)
        html = self.client.get(URL_NUEVO).content.decode()
        self.assertNotIn("data-sugerencias-url", html)
        self.assertNotIn("data-sugerencias-completa", html)


class PerdioElDocumentoTests(BaseIdentidad):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_en_una_persona_nueva_queda_sin_documento_fisico(self):
        respuesta = self.client.post(URL_NUEVO, self._formulario1(dni="31000111", documento_extraviado="on"))

        self.assertEqual(respuesta.status_code, 302)
        caso = CasoEmergencia.objects.select_related("grupo__responsable").get()
        self.assertEqual(caso.grupo.responsable.dni_fisico, Ciudadano.DniFisico.NO_TIENE)
        self.assertTrue(caso.situacion["documento_extraviado"])

    def test_sin_la_casilla_no_se_toca_el_documento(self):
        self.client.post(URL_NUEVO, self._formulario1(dni="31000111"))

        caso = CasoEmergencia.objects.select_related("grupo__responsable").get()
        self.assertNotEqual(caso.grupo.responsable.dni_fisico, Ciudadano.DniFisico.NO_TIENE)
        self.assertNotIn("documento_extraviado", caso.situacion)

    def test_a_quien_ya_tiene_legajo_no_se_le_cambia_nada(self):
        legajo = self._legajo()
        antes = legajo.dni_fisico

        self.client.post(
            URL_NUEVO, self._formulario1(dni="40732122", nombre="", apellido="", documento_extraviado="on")
        )

        legajo.refresh_from_db()
        self.assertEqual(legajo.dni_fisico, antes)


class IdentidadARevisarEnLaMesaTests(BaseIdentidad):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self._legajo()

    def _caso_a_revisar(self):
        self.client.post(
            URL_NUEVO,
            self._formulario1(dni="40732122", nombre="Pedro", apellido="Gómez", identidad_en_conflicto="on"),
        )
        return CasoEmergencia.objects.get()

    def _marcas(self):
        respuesta = self.client.get(URL_BANDEJA)
        return [marca["texto"] for fila in respuesta.context["filas"] for marca in fila["marcas"]]

    def _textos_de_la_ficha(self, caso):
        return [aviso["texto"] for aviso in self._ficha(caso).context["avisos"]]

    def test_la_ficha_avisa_con_lo_declarado_y_lo_del_legajo(self):
        caso = self._caso_a_revisar()

        respuesta = self._ficha(caso)

        aviso = next(a for a in respuesta.context["avisos"] if a["texto"] == AVISO)
        self.assertEqual(aviso["tono"], "warning")
        self.assertIn("«Gómez, Pedro»", aviso["detalle"])
        self.assertIn("«FARIÑA, Joaquin»", aviso["detalle"])
        self.assertContains(respuesta, AVISO)

    def test_la_bandeja_la_marca(self):
        self._caso_a_revisar()
        self.assertIn(AVISO, self._marcas())

    def test_un_caso_sin_conflicto_no_lleva_el_aviso(self):
        self.client.post(URL_NUEVO, self._formulario1(dni="40732122", nombre="", apellido=""))
        caso = CasoEmergencia.objects.get()

        self.assertNotIn(AVISO, self._marcas())
        self.assertNotIn(AVISO, self._textos_de_la_ficha(caso))

    def test_revisada_ya_no_avisa(self):
        caso = self._caso_a_revisar()
        caso.situacion = {
            **caso.situacion,
            CasoEmergencia.SITUACION_IDENTIDAD_REVISADA: {"por_id": self.operador.pk, "en": "x", "observacion": ""},
        }
        caso.save(update_fields=["situacion"])

        self.assertNotIn(AVISO, self._marcas())
        self.assertNotIn(AVISO, self._textos_de_la_ficha(caso))

    def test_el_aviso_no_cuesta_consultas(self):
        caso = self._caso_a_revisar()
        anotado = selectores.bandeja({"solapa": "abiertos"}).get(pk=caso.pk)
        sla = sla_vigente()

        with self.assertNumQueries(0):
            textos = [aviso["texto"] for aviso in mesa.avisos_de_la_mesa(anotado, sla, T0)]

        self.assertIn(AVISO, textos)
