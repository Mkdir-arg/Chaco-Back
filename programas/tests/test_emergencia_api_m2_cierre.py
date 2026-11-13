"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) — cerrar el ingreso y sin derivación (M2-5, M2-6).

«Familia alojada», el cierre con diferencia (RN-3.9), la cancelación del ingreso, y el ingreso
directo y el aviso a la mesa, idempotentes por ``uuid_cliente`` (RU-16).

La base (`BaseApiLlegadas`) y las claves exactas de cada respuesta están en ``base_emergencia_api``.
"""

import uuid
from unittest import mock

from programas.models import (
    CasoEmergencia,
    ReservaPlaza,
    Sector,
)
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_alta
from programas.tests.base_emergencia_api import (
    CLAVES_AVISO_A_LA_MESA,
    CLAVES_CASO_RESUMEN,
    CLAVES_CIERRE_DE_INGRESO,
    CLAVES_INGRESO_DIRECTO,
    BaseApiLlegadas,
    _url,
)

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
