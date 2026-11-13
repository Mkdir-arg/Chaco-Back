"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) — buscar, aceptar y rechazar (M2-1, M2-2).

La guardia busca a la familia por DNI y acepta o rechaza la derivación con la misma función que
la pantalla E6; el 409 cuando la web se adelantó y el tope de la búsqueda (``emergencia_buscar``).

La base (`BaseApiLlegadas`) y las claves exactas de cada respuesta están en ``base_emergencia_api``.
"""

import uuid
from unittest import mock

from django.core.cache import cache
from django.urls import reverse

from programas.api.views import ConsultaPersonasThrottle
from programas.api.views_emergencia_llegadas import BuscarFamiliaThrottle
from programas.models import (
    CasoEmergencia,
    Derivacion,
    ReservaPlaza,
)
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import (
    CLAVES_ACEPTACION,
    CLAVES_BUSQUEDA,
    CLAVES_CASO_RESUMEN,
    CLAVES_DERIVACION_LLEGADA,
    CLAVES_ESTADO_CAMBIO,
    CLAVES_FIJAS_DEL_400,
    CLAVES_GRUPO_DE_LA_DERIVACION,
    CLAVES_INTEGRANTE,
    CLAVES_RECHAZO,
    CLAVES_RESPONSABLE,
    BaseApiLlegadas,
    _url,
)

Estado = CasoEmergencia.Estado


# ---------------------------------------------------------------------------
# Buscar (M2-1)
# ---------------------------------------------------------------------------


class BuscarFamiliaApiTests(BaseApiLlegadas):
    def _buscar(self, dni, usuario=None, dispositivo=None):
        return self._como(usuario or self.guardia_centro).get(
            _url("dispositivo-buscar", (dispositivo or self.centro).pk), {"dni": dni}
        )

    def test_con_derivacion_trae_la_tarjeta_con_claves_exactas(self):
        caso, derivacion = self._derivado(embarazo=True, telefono="3624000000")

        respuesta = self._buscar("30.111.222")

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_BUSQUEDA)
        self.assertEqual((cuerpo["resultado"], cuerpo["dni"], cuerpo["plazas_libres"]), ("DERIVACION", "30111222", 9))
        tarjeta = cuerpo["derivacion"]
        self.assertEqual(sorted(tarjeta), CLAVES_DERIVACION_LLEGADA)
        self.assertEqual(sorted(tarjeta["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual(sorted(tarjeta["responsable"]), CLAVES_RESPONSABLE)
        self.assertEqual(sorted(tarjeta["grupo"]), CLAVES_GRUPO_DE_LA_DERIVACION)
        self.assertEqual((tarjeta["id"], tarjeta["estado"], tarjeta["plazas_pedidas"]), (derivacion.pk, "PENDIENTE", 7))
        self.assertEqual(tarjeta["caso"]["id"], caso.pk)
        self.assertEqual(tarjeta["responsable"], {"nombre": "Rosa", "apellido": "Benítez", "dni": "30111222"})
        self.assertEqual(tarjeta["necesidades"], ["embarazo"])
        self.assertEqual(tarjeta["derivada_por"], "Ana López")
        self.assertIs(tarjeta["vencida"], False)
        self.assertEqual((cuerpo["alojada_aca"], cuerpo["alojada_en"], cuerpo["alojada_desde"]), (None, "", None))

    def test_la_derivacion_a_otro_dispositivo_es_sin_derivacion_y_no_lo_nombra(self):
        self._derivado(dispositivo=self.escuela)

        respuesta = self._buscar("30111222")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["resultado"], "SIN_DERIVACION")
        self.assertIsNone(respuesta.json()["derivacion"])
        self.assertNotIn("Escuela", respuesta.content.decode())

    def test_alojada_aca(self):
        caso, _derivacion = self._aceptado()
        self._confirmar_con_el_servicio(caso, 1, "30111222")
        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia_centro, motivo="NO_LLEGO")

        cuerpo = self._buscar("30111222").json()

        self.assertEqual(
            (cuerpo["resultado"], cuerpo["alojada_aca"], cuerpo["alojada_en"]), ("ALOJADA", True, "Centro Norte")
        )

    def test_un_dni_invalido_es_400(self):
        respuesta = self._buscar("12")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertIn("dni", respuesta.json())


class TopeDeLaBusquedaApiTests(BaseApiLlegadas):
    """La búsqueda por DNI tiene tope por usuario (``emergencia_buscar``).

    Dice si un DNI está derivado o alojado en la red: sin tope, un token perdido enumera DNIs.
    **Mutación vista en rojo**: sin ``throttle_classes`` en ``BuscarFamiliaView``, la tercera
    búsqueda da 200 y ``test_pasado_el_tope_contesta_429`` falla.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    def _buscar(self, usuario, dni="30111222"):
        dispositivo = self.centro if usuario == self.guardia_centro else self.escuela
        return self._como(usuario).get(_url("dispositivo-buscar", dispositivo.pk), {"dni": dni})

    def test_la_tasa_configurada_es_holgada_y_propia(self):
        self.assertEqual(BuscarFamiliaThrottle().rate, "300/hour")
        self.assertNotEqual(BuscarFamiliaThrottle.scope, ConsultaPersonasThrottle.scope)

    @mock.patch.object(BuscarFamiliaThrottle, "get_rate", return_value="2/hour")
    def test_pasado_el_tope_contesta_429(self, _rate):
        self.assertEqual(self._buscar(self.guardia_centro, "30111222").status_code, 200)
        self.assertEqual(self._buscar(self.guardia_centro, "30111223").status_code, 200)
        respuesta = self._buscar(self.guardia_centro, "30111224")

        self.assertEqual(respuesta.status_code, 429)
        self.assertIn("Retry-After", respuesta)

    @mock.patch.object(BuscarFamiliaThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_por_usuario(self, _rate):
        self.assertEqual(self._buscar(self.guardia_centro).status_code, 200)
        self.assertEqual(self._buscar(self.guardia_centro).status_code, 429)
        self.assertEqual(self._buscar(self.guardia_escuela).status_code, 200)

    @mock.patch.object(BuscarFamiliaThrottle, "get_rate", return_value="1/hour")
    def test_quien_no_admite_no_gasta_la_cubeta(self, _rate):
        """El permiso corre antes que el throttle: el agente abre el módulo, no admite, y no gasta búsquedas."""
        for _ in range(3):
            respuesta = self._como(self.agente).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})
            self.assertEqual(respuesta.status_code, 403)


# ---------------------------------------------------------------------------
# Aceptar y rechazar (M2-2)
# ---------------------------------------------------------------------------


class AceptarYRechazarApiTests(BaseApiLlegadas):
    def test_aceptar_reserva_y_devuelve_las_filas(self):
        caso, derivacion = self._derivado(plazas=7)
        self._ocupar(self.centro, 4)  # quedan 5 libres de 9

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-aceptar", derivacion.pk), {"uuid_cliente": str(uuid.uuid4())}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_ACEPTACION)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual((cuerpo["reservadas"], cuerpo["faltantes"]), (5, 2))
        self.assertEqual(cuerpo["mensaje"], "Reservé 5 de 7 · faltan 2 camas")
        self.assertEqual(cuerpo["caso"]["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual([fila["n"] for fila in cuerpo["integrantes"]], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual([sorted(fila) for fila in cuerpo["integrantes"]], [CLAVES_INTEGRANTE] * 7)
        self.assertEqual(len(self._reservas(derivacion)), 5)

    def test_la_web_acepta_y_despues_la_app_recibe_409(self):
        """§10 de 03: dos guardias, una en el backoffice y otra en la app, sobre el mismo caso."""
        caso, derivacion = self._derivado()
        self.client.force_login(self.guardia_centro)
        web = self.client.post(reverse("dispositivos:emergencia_aceptar", args=[self.centro.pk, derivacion.pk]))
        self.assertEqual(web.status_code, 302)
        reservas = ReservaPlaza.objects.count()

        respuesta = self._como(self.guardia_centro).post(_url("derivacion-aceptar", derivacion.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_ESTADO_CAMBIO)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertIn("ya la aceptó", respuesta.json()["detail"])
        self.assertEqual(ReservaPlaza.objects.count(), reservas)

    def test_sin_camas_libres_es_400_en_plazas(self):
        _caso, derivacion = self._derivado()
        self._ocupar(self.centro, 9)

        respuesta = self._como(self.guardia_centro).post(_url("derivacion-aceptar", derivacion.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(CLAVES_FIJAS_DEL_400 <= set(respuesta.json()))
        self.assertIn("plazas", respuesta.json())
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_rechazar_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._derivado()

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-rechazar", derivacion.pk), {"motivo": "NO_CUMPLE_PERFIL"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()), CLAVES_RECHAZO)
        self.assertEqual(respuesta.json(), {"caso_estado": Estado.EN_GESTION})
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.RECHAZADA)

    def test_rechazar_sin_motivo_o_con_otro_sin_observacion_es_400(self):
        _caso, derivacion = self._derivado()
        cliente = self._como(self.guardia_centro)

        for cuerpo, campo in (({}, "motivo"), ({"motivo": "INVENTADO"}, "motivo"), ({"motivo": "OTRO"}, "observacion")):
            with self.subTest(cuerpo=cuerpo):
                respuesta = cliente.post(_url("derivacion-rechazar", derivacion.pk), cuerpo, format="json")
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json())
        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.PENDIENTE)

    def test_rechazar_una_ya_aceptada_es_409(self):
        _caso, derivacion = self._aceptado()

        respuesta = self._como(self.guardia_centro).post(
            _url("derivacion-rechazar", derivacion.pk), {"motivo": "SIN_PLAZAS"}, format="json"
        )

        self.assertEqual((respuesta.status_code, respuesta.json()["estado_actual"]), (409, Estado.INGRESO_EN_CURSO))
