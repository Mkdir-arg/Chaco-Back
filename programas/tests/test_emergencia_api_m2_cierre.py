"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) — cerrar el ingreso y sin derivación (M2-5, M2-6).

«Familia alojada», el cierre con diferencia (RN-3.9), la cancelación del ingreso, y el ingreso
directo y el aviso a la mesa, idempotentes por ``uuid_cliente`` (RU-16).

La base (`BaseApiLlegadas`) y las claves exactas de cada respuesta están en ``base_emergencia_api``.
"""

import uuid
from unittest import mock

from programas.models import (
    CasoEmergencia,
    Derivacion,
    ReservaPlaza,
    Sector,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_alta
from programas.tests.base_emergencia_api import (
    CLAVES_AVISO_A_LA_MESA,
    CLAVES_CASO_RESUMEN,
    CLAVES_CIERRE_DE_INGRESO,
    CLAVES_DERIVACION_DEL_INGRESO,
    CLAVES_INGRESO_DIRECTO,
    BaseApiLlegadas,
    _url,
)
from programas.tests.test_emergencia_alojar_base import GUARDIA

Estado = CasoEmergencia.Estado


# ---------------------------------------------------------------------------
# Cerrar el ingreso (M2-5, RN-3.9)
# ---------------------------------------------------------------------------


class CerrarIngresoApiTests(BaseApiLlegadas):
    def test_alojar_con_todas_confirmadas(self):
        caso, derivacion = self._aceptado(dni="30111222", menores_f=0, menores_m=0, plazas=3)  # 2 personas, 3 camas
        self._confirmar(caso, 1, "30111222")
        self._confirmar(caso, 2, "45111222")
        sector = Sector.objects.filter(dispositivo=self.centro).first()

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-alojar", caso.pk),
            {"sector": sector.pk, "aula": "Aula 3", "tarjeta_entregada": True, "tarjeta_numero": "0042"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(sorted(respuesta.json()), CLAVES_CIERRE_DE_INGRESO)
        self.assertEqual(respuesta.json(), {"estado": Estado.ALOJADO, "total_alojado": 2, "liberadas": 1})
        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).situacion["alojamiento"]["aula"], "Aula 3")

        otra_vez = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")
        self.assertEqual((otra_vez.status_code, otra_vez.json()["estado_actual"]), (409, Estado.ALOJADO))

    def test_alojar_con_alguien_sin_confirmar_es_400(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Falta confirmar", respuesta.json()["detail"])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_cerrar_con_diferencia(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-cerrar-diferencia", caso.pk), {"motivo": "QUEDO_CON_FAMILIARES"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"estado": Estado.ALOJADO, "total_alojado": 1, "liberadas": 6})

    def test_cerrar_con_diferencia_sin_motivo_es_400(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).post(_url("caso-cerrar-diferencia", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_cancelar_el_ingreso_sin_nadie_confirmado(self):
        caso, derivacion = self._aceptado()

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-cancelar-ingreso", caso.pk), {"motivo": "La familia se fue con parientes."}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["estado"], Estado.EN_GESTION)
        self.assertEqual(respuesta.json()["liberadas"], 7)
        self.assertEqual(self._reservas(derivacion), [])

    def test_la_web_cancela_y_la_app_quiere_alojar_409(self):
        caso, _derivacion = self._aceptado()
        servicio.cancelar_ingreso(caso=caso, usuario=self.guardia_centro, motivo="Se fueron.")

        respuesta = self._como(self.guardia_centro).post(_url("caso-alojar", caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.EN_GESTION)

    def _estado(self, caso):
        return CasoEmergencia.objects.values_list("estado", flat=True).get(pk=caso.pk)


# ---------------------------------------------------------------------------
# Cerrar con la derivación vista (Cambio 477)
# ---------------------------------------------------------------------------

MOTIVO = {"motivo": "La familia se fue con parientes."}


class CerrarConLaDerivacionVistaApiTests(BaseApiLlegadas):
    """`derivacion` en los tres cierres: un reintento no actúa sobre un ingreso que la pantalla no vio.

    Tabla de casos de ``…/cancelar-ingreso/`` (contrato §13.9):

    (a) primer envío con la derivación de ``…/integrantes/`` → 200;
    (b) reintento de un cancelar que llegó, sin re-derivación → el 409 de estado (``EN_GESTION``/``NUEVO``):
        la app infiere que se hizo;
    (c) reintento después de que la mesa volvió a derivar y otra guardia aceptó → 409 «cambió», sin cancelar;
    (d) una derivación que no existe o de otro caso → el mismo 409; un valor que no es un id → 400;
    (e) sin el campo (o ``null``) → como antes del Cambio 477.
    """

    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()
        self.otra_guardia = self._guardia("otra_guardia_centro", list(GUARDIA), [self.centro])

    def _cancelar(self, cuerpo, usuario=None):
        return self._como(usuario or self.guardia_centro).post(
            _url("caso-cancelar-ingreso", self.caso.pk), cuerpo, format="json"
        )

    def _volver_a_derivar_y_aceptar(self, aceptar=True):
        """La mesa deriva otra vez al mismo centro y otra guardia acepta: el ingreso nuevo."""
        nueva = mesa.derivar_caso(CasoEmergencia.objects.get(pk=self.caso.pk), self.operador, self.centro, 7, True)
        if aceptar:
            servicio.aceptar_derivacion(derivacion=nueva, usuario=self.otra_guardia)
        return Derivacion.objects.get(pk=nueva.pk)

    def test_integrantes_dice_que_derivacion_se_mira(self):
        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", self.caso.pk))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(sorted(respuesta.json()["derivacion"]), CLAVES_DERIVACION_DEL_INGRESO)
        self.assertEqual(respuesta.json()["derivacion"], {"id": self.derivacion.pk})

    def test_integrantes_trae_la_derivacion_nueva_despues_de_volver_a_derivar(self):
        servicio.cancelar_ingreso(caso=self.caso, usuario=self.guardia_centro, motivo="Se fueron.")
        nueva = self._volver_a_derivar_y_aceptar()

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", self.caso.pk))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["derivacion"], {"id": nueva.pk})
        self.assertNotEqual(nueva.pk, self.derivacion.pk)

    def test_a_primer_envio_con_la_derivacion_vista_cancela(self):
        respuesta = self._cancelar({**MOTIVO, "derivacion": self.derivacion.pk})

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"estado": Estado.EN_GESTION, "total_alojado": None, "liberadas": 7})
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.RECHAZADA)

    def test_b_reintento_de_un_cancelar_que_llego_es_el_409_de_estado(self):
        self.assertEqual(self._cancelar({**MOTIVO, "derivacion": self.derivacion.pk}).status_code, 200)
        antes = self._foto_del_caso(self.caso)

        reintento = self._cancelar({**MOTIVO, "derivacion": self.derivacion.pk})

        self.assertEqual(reintento.status_code, 409)
        self.assertEqual(reintento.json()["estado_actual"], Estado.EN_GESTION)
        self.assertNotIn("cambió", reintento.json()["detail"])
        self.assertIn("se canceló", reintento.json()["detail"])
        self.assertEqual(self._foto_del_caso(self.caso), antes)

    def test_c_reintento_despues_de_volver_a_derivar_y_aceptar_no_cancela_el_ingreso_nuevo(self):
        servicio.cancelar_ingreso(caso=self.caso, usuario=self.guardia_centro, motivo="Se fueron.")
        nueva = self._volver_a_derivar_y_aceptar()
        antes = self._foto_del_caso(self.caso)

        reintento = self._cancelar({**MOTIVO, "derivacion": self.derivacion.pk})

        self.assertEqual(reintento.status_code, 409)
        self.assertEqual(reintento.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertIn("la derivación que viste ya no es la vigente", reintento.json()["detail"])
        self.assertEqual(self._foto_del_caso(self.caso), antes)
        self.assertEqual(Derivacion.objects.get(pk=nueva.pk).estado, Derivacion.Estado.ACEPTADA)

    def test_c_con_la_derivacion_nueva_pendiente_tambien_dice_que_cambio(self):
        """El chequeo va antes del de estado: sin aceptar todavía, el 409 es el de la derivación."""
        servicio.cancelar_ingreso(caso=self.caso, usuario=self.guardia_centro, motivo="Se fueron.")
        self._volver_a_derivar_y_aceptar(aceptar=False)

        reintento = self._cancelar({**MOTIVO, "derivacion": self.derivacion.pk})

        self.assertEqual(reintento.status_code, 409)
        self.assertEqual(reintento.json()["estado_actual"], Estado.DERIVADO)
        self.assertIn("la derivación que viste ya no es la vigente", reintento.json()["detail"])

    def test_e_sin_el_campo_el_reintento_cancela_el_ingreso_nuevo_como_antes(self):
        """Lo que el campo evita: la app publicada, que no lo manda, sigue con el comportamiento de antes."""
        servicio.cancelar_ingreso(caso=self.caso, usuario=self.guardia_centro, motivo="Se fueron.")
        nueva = self._volver_a_derivar_y_aceptar()

        reintento = self._cancelar(MOTIVO)

        self.assertEqual(reintento.status_code, 200, reintento.content)
        self.assertEqual(Derivacion.objects.get(pk=nueva.pk).estado, Derivacion.Estado.RECHAZADA)

    def test_e_con_null_es_como_sin_el_campo(self):
        respuesta = self._cancelar({**MOTIVO, "derivacion": None})

        self.assertEqual(respuesta.status_code, 200, respuesta.content)

    def test_d_una_derivacion_inexistente_o_de_otro_caso_es_409_y_no_escribe(self):
        _otro, de_otro_caso = self._aceptado(dni="30999888", menores_f=0, menores_m=0)
        antes = self._foto_del_caso(self.caso)

        for vista in (de_otro_caso.pk, de_otro_caso.pk + 1000):
            with self.subTest(derivacion=vista):
                respuesta = self._cancelar({**MOTIVO, "derivacion": vista})
                self.assertEqual(respuesta.status_code, 409)
                self.assertEqual(respuesta.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(self._foto_del_caso(self.caso), antes)

    def test_d_un_valor_que_no_es_un_id_es_400(self):
        for vista in ("abc", 0, -3):
            with self.subTest(derivacion=vista):
                respuesta = self._cancelar({**MOTIVO, "derivacion": vista})
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("derivacion", respuesta.json())
        self.assertEqual(self._estado(), Estado.INGRESO_EN_CURSO)

    def test_alojar_y_diferencia_con_una_derivacion_vieja_son_409_y_con_la_vigente_cierran(self):
        self._confirmar(self.caso, 1, "30111222")
        antes = self._foto_del_caso(self.caso)
        cliente = self._como(self.guardia_centro)

        for ruta, cuerpo in (("caso-alojar", {}), ("caso-cerrar-diferencia", {"motivo": "NO_LLEGO"})):
            with self.subTest(ruta=ruta):
                vieja = cliente.post(
                    _url(ruta, self.caso.pk), {**cuerpo, "derivacion": self.derivacion.pk + 1000}, format="json"
                )
                self.assertEqual(vieja.status_code, 409)
                self.assertIn("la derivación que viste ya no es la vigente", vieja.json()["detail"])
        self.assertEqual(self._foto_del_caso(self.caso), antes)

        cerrada = cliente.post(
            _url("caso-cerrar-diferencia", self.caso.pk),
            {"motivo": "NO_LLEGO", "derivacion": self.derivacion.pk},
            format="json",
        )
        self.assertEqual(cerrada.status_code, 200, cerrada.content)
        self.assertEqual(cerrada.json()["estado"], Estado.ALOJADO)

    def _estado(self):
        return CasoEmergencia.objects.values_list("estado", flat=True).get(pk=self.caso.pk)


# ---------------------------------------------------------------------------
# Sin derivación (M2-6)
# ---------------------------------------------------------------------------


class SinDerivacionApiTests(BaseApiLlegadas):
    def _cuerpo_puerta(self, uuid_cliente=None, **cambios):
        cuerpo = self._cuerpo(uuid_cliente=uuid_cliente, **cambios)
        cuerpo.pop("direccion", None)  # en la puerta, la dirección es opcional
        return cuerpo

    def test_ingreso_directo_crea_el_caso_y_es_idempotente(self):
        identificador = uuid.uuid4()
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        primera = cliente.post(url, self._cuerpo_puerta(identificador, adultos_m=2), format="multipart")
        casos, reservas = CasoEmergencia.objects.count(), ReservaPlaza.objects.count()
        segunda = cliente.post(url, self._cuerpo_puerta(identificador, adultos_m=5), format="multipart")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200), primera.content)
        cuerpo = primera.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INGRESO_DIRECTO)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual(cuerpo["caso"]["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual((cuerpo["reservadas"], cuerpo["faltantes"]), (3, 0))
        self.assertEqual(len(cuerpo["integrantes"]), 3)
        self.assertEqual(segunda.json(), cuerpo)
        self.assertEqual((CasoEmergencia.objects.count(), ReservaPlaza.objects.count()), (casos, reservas))
        caso = CasoEmergencia.objects.get(pk=cuerpo["caso"]["id"])
        self.assertEqual(caso.origen, CasoEmergencia.Origen.DISPOSITIVO)

    def test_ingreso_directo_sin_camas_es_400_y_sin_uuid_tambien(self):
        self._ocupar(self.centro, 9)
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        sin_camas = cliente.post(url, self._cuerpo_puerta(), format="multipart")
        cuerpo = self._cuerpo_puerta()
        cuerpo.pop("uuid_cliente")
        sin_uuid = cliente.post(url, cuerpo, format="multipart")

        self.assertEqual(sin_camas.status_code, 400)
        self.assertIn("plazas", sin_camas.json())
        self.assertEqual(sin_uuid.status_code, 400)
        self.assertIn("uuid_cliente", sin_uuid.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_el_uuid_de_otro_usuario_es_409(self):
        identificador = uuid.uuid4()
        self._como(self.guardia_escuela).post(
            _url("dispositivo-ingreso-directo", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        respuesta = self._como(self.guardia_centro).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def _guardia_de_dos(self):
        """Un usuario que admite en el centro y en la escuela, y el ingreso directo que hizo en el centro."""
        usuario = self._guardia("guardia_doble", list(GUARDIA), [self.centro, self.escuela])
        identificador = uuid.uuid4()
        primera = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk),
            self._cuerpo_puerta(identificador, adultos_m=1, dni="33444555", nombre="Marta", apellido="Rios"),
            format="multipart",
        )
        self.assertEqual(primera.status_code, 201, primera.content)
        return usuario, identificador, primera

    def test_reenvio_con_uuid_de_otro_dispositivo_no_devuelve_integrantes(self):
        """E-SEG-01: el mismo uuid en la URL de otro dispositivo no es un reenvío: 409, sin datos del caso."""
        usuario, identificador, _ = self._guardia_de_dos()

        respuesta = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")
        self.assertNotIn("integrantes", respuesta.json())
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_reenvio_con_uuid_de_un_envio_de_m1_es_uuid_en_uso(self):
        """Un caso que no nació de «Ingresar igual» no se devuelve como si fuera uno de este dispositivo."""
        usuario, identificador, _ = self._guardia_de_dos()
        CasoEmergencia.objects.update(origen=CasoEmergencia.Origen.TERRITORIO)

        respuesta = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")

    def test_reenvio_tras_perder_el_alcance_de_la_ultima_derivacion_no_muestra_personas(self):
        """E-SEG-01: la mesa mandó el caso a otro lado; quien sigue en el centro recibe su 200 sin personas."""
        usuario = self._guardia("guardia_centro_2", list(GUARDIA), [self.centro])
        identificador = uuid.uuid4()
        primera = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk),
            self._cuerpo_puerta(identificador, adultos_m=1, dni="33444555", nombre="Marta", apellido="Rios"),
            format="multipart",
        )
        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertTrue(primera.json()["integrantes"])
        caso = CasoEmergencia.objects.get()
        Derivacion.objects.create(
            caso=caso,
            dispositivo=self.escuela,
            estado=Derivacion.Estado.RECHAZADA,
            plazas_pedidas=1,
            vence_en=caso.creado,
            derivada_por=self.operador,
        )

        respuesta = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["caso"]["id"], primera.json()["caso"]["id"])
        self.assertEqual(respuesta.json()["integrantes"], [])

    def test_el_reenvio_legitimo_de_quien_sigue_en_el_equipo_conserva_los_integrantes(self):
        usuario, identificador, primera = self._guardia_de_dos()

        respuesta = self._como(usuario).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), primera.json())
        self.assertTrue(respuesta.json()["integrantes"])

    def test_avisar_a_la_mesa_con_uuid_de_otro_dispositivo_es_uuid_en_uso_en_la_api(self):
        usuario = self._guardia("guardia_doble", list(GUARDIA), [self.centro, self.escuela])
        identificador = uuid.uuid4()
        primera = self._como(usuario).post(
            _url("dispositivo-avisar-mesa", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
        )
        self.assertEqual(primera.status_code, 201, primera.content)

        respuesta = self._como(usuario).post(
            _url("dispositivo-avisar-mesa", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "UUID_EN_USO")

    def test_el_409_sale_por_tipo_aunque_cambie_el_texto_del_mensaje(self):
        """``_ejecutar`` atrapa ``UuidEnUso`` por tipo, no compara el texto (PR #1130).

        **Mutación vista en rojo:** con la comparación de ``errores["uuid_cliente"]`` contra
        ``[UUID_EN_USO]`` de vuelta, el mensaje cambiado sale como 400. Restaurada, verde.
        """
        identificador = uuid.uuid4()
        self._como(self.guardia_escuela).post(
            _url("dispositivo-ingreso-directo", self.escuela.pk), self._cuerpo_puerta(identificador), format="multipart"
        )

        with mock.patch.object(emergencia_alta, "UUID_EN_USO", "Ese identificador ya lo usó otra persona."):
            respuesta = self._como(self.guardia_centro).post(
                _url("dispositivo-avisar-mesa", self.centro.pk), self._cuerpo_puerta(identificador), format="multipart"
            )

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Ese identificador ya lo usó otra persona.", "code": "UUID_EN_USO"}
        )
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_las_reglas_del_formulario_1_en_la_puerta_son_las_del_servicio(self):
        """Mismo serializer que M1: ni tope propio de ``traslado_otro`` ni mínimo propio en las cantidades."""
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-ingreso-directo", self.centro.pk)

        negativa = cliente.post(url, self._cuerpo_puerta(adultos_f=-1, traslado=""), format="multipart")
        largo = cliente.post(url, self._cuerpo_puerta(traslado="OTRA", traslado_otro="G" * 80), format="multipart")

        self.assertEqual(negativa.status_code, 400, negativa.content)
        self.assertEqual(negativa.json()["adultos_f"], ["No puede ser negativo."])
        self.assertIn("traslado", negativa.json())
        self.assertEqual(largo.status_code, 201, largo.content)
        self.assertEqual(CasoEmergencia.objects.get().grupo.traslado_otro, "G" * 80)

    def test_avisar_a_la_mesa_crea_un_caso_nuevo_e_idempotente(self):
        identificador = uuid.uuid4()
        cliente = self._como(self.guardia_centro)
        url = _url("dispositivo-avisar-mesa", self.centro.pk)

        primera = cliente.post(url, self._cuerpo_puerta(identificador), format="multipart")
        segunda = cliente.post(url, self._cuerpo_puerta(identificador), format="multipart")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200), primera.content)
        self.assertEqual(sorted(primera.json()), CLAVES_AVISO_A_LA_MESA)
        self.assertEqual(primera.json(), segunda.json())
        self.assertEqual(primera.json()["caso"]["estado"], Estado.NUEVO)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
