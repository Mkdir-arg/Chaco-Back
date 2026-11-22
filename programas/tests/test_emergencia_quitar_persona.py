"""Emergencia · «Quitar persona» de la puerta (Cambio 537; relevamiento del 22/11/2026, hallazgo 12).

«Agregar persona» no tenía vuelta atrás. Ahora se quita **solo** a quien la guardia sumó en la puerta (su
``orden`` pasa lo declarado en el Formulario 1) y todavía no se confirmó. Nunca al responsable, a un integrante
original ni a una persona ya confirmada. Cubre el servicio, la pantalla del backoffice y la API de la app.

Cambio 539 (MINOR de la auditoría del #1313): el pedido identifica a la **fila** (``id``), no solo su número; quitar
libera la reserva que la derivación retiene de más; la regla vive en ``IntegranteGrupo.se_puede_quitar``.

Mutaciones verificadas (cada una pone en rojo al menos un test de acá): sacar de ``se_puede_quitar`` el chequeo
``agregada_en_la_puerta``; sacar el de ``confirmada``; devolver el error en vez del resultado idempotente cuando la
fila ya no está; sacar el chequeo de alcance de ``_exigir_alcance``; sacar el decremento de ``total_declarado``;
dejar ``_asegurar_filas`` contando números en vez de filas; sacar de ``quitar_integrante`` la comparación de
``fila_id``; contestar ``ya_estaba`` sin buscar la traza; sacar ``_liberar_la_sobrante``.
"""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from programas.models import CasoEmergencia, IntegranteGrupo, ReservaPlaza, TrazaCaso
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia_alojar as servicio
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_confirmacion import SOLO_SE_QUITA_LA_DE_LA_PUERTA
from programas.services.emergencia_ingreso_comun import _asegurar_filas
from programas.tests import test_emergencia_alojar_alcance_edificio as edificios
from programas.tests.base_emergencia_api import BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_base import ficha_minima


class BaseQuitar(edificios.BaseEdificios):
    """Una familia de 3 (el responsable y dos del Formulario 1) derivada al edificio B y aceptada por su guardia."""

    def setUp(self):
        super().setUp()
        self.guardia_a = edificios._con_alcance_edificios(self._guardia("guardia_a", self.club), self.club, self.edif_a)
        _caso, derivacion = self._derivado_a(self.edif_b, plazas=3, menores_f=1, menores_m=0)
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_b)
        self.caso, self.derivacion = resultado.caso, resultado.derivacion

    def _agregar(self, cantidad=1):
        return [servicio.agregar_integrante(caso=self.caso, usuario=self.guardia_b).orden for _ in range(cantidad)]

    def _confirmar_agregada(self, orden):
        servicio.confirmar_integrante(
            caso=self.caso,
            orden=orden,
            usuario=self.guardia,
            ficha=ficha_minima(f"4500{orden:04d}"),
            plaza=self._cama_libre(),
        )

    def _filas(self):
        return list(IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id).order_by("orden"))

    def _total(self):
        self.caso.grupo.refresh_from_db()
        return self.caso.grupo.total_declarado

    def _rechazado(self, orden, usuario=None):
        with self.assertRaises(ValidationError) as error:
            servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=usuario or self.guardia_b)
        return error.exception.message_dict["orden"]


class QuitarIntegranteServicioTests(BaseQuitar):
    def test_quita_a_la_agregada_sin_confirmar(self):
        (orden,) = self._agregar()
        self.assertEqual((orden, self._total()), (4, 4))

        quitada = servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_b)

        self.assertEqual((quitada.orden, quitada.total_declarado, quitada.ya_estaba), (4, 3, False))
        self.assertEqual([fila.orden for fila in self._filas()], [1, 2, 3])
        self.assertEqual(self._total(), 3)
        traza = TrazaCaso.objects.filter(caso=self.caso).order_by("id").last()
        self.assertEqual(traza.accion, TrazaCaso.Accion.INTEGRANTE_QUITADO)
        self.assertEqual(traza.usuario, self.guardia_b)
        self.assertIn("Quitada la persona 4", traza.detalle)

    def test_quitar_dos_veces_es_idempotente(self):
        (orden,) = self._agregar()
        servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_b)
        trazas = TrazaCaso.objects.filter(caso=self.caso).count()

        otra = servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_b)

        self.assertTrue(otra.ya_estaba)
        self.assertEqual((self._total(), TrazaCaso.objects.filter(caso=self.caso).count()), (3, trazas))

    def test_no_quita_al_responsable_ni_a_un_integrante_original(self):
        for orden in (1, 2, 3):
            with self.subTest(orden=orden):
                self.assertEqual(self._rechazado(orden), [SOLO_SE_QUITA_LA_DE_LA_PUERTA])
        self.assertEqual((len(self._filas()), self._total()), (3, 3))

    def test_no_quita_a_una_agregada_ya_confirmada(self):
        (orden,) = self._agregar()
        self._confirmar_agregada(orden)

        self.assertEqual(self._rechazado(orden), [SOLO_SE_QUITA_LA_DE_LA_PUERTA])
        self.assertEqual(self._total(), 4)

    def test_una_fila_original_que_no_existe_es_error_y_no_un_reenvio(self):
        IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id, orden=3).delete()

        self.assertIn("no es de esta familia", self._rechazado(3)[0])

    def test_la_guardia_de_otro_edificio_no_tiene_acceso(self):
        (orden,) = self._agregar()

        with self.assertRaises(PermissionDenied):
            servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_a)
        with self.assertRaises(PermissionDenied):
            servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_escuela)

        self.assertEqual((len(self._filas()), self._total()), (4, 4))

    def test_la_guardia_de_la_institucion_tambien_puede(self):
        (orden,) = self._agregar()

        servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia)

        self.assertEqual(self._total(), 3)

    def test_solo_con_el_ingreso_en_curso(self):
        caso, _derivacion = self._derivado_a(self.edif_a, plazas=1, dni="30999888")

        with self.assertRaises(EstadoCambio):
            servicio.quitar_integrante(caso=caso, orden=2, usuario=self.guardia)

    def _id_de(self, orden):
        return IntegranteGrupo.objects.get(grupo_id=self.caso.grupo_id, orden=orden).pk

    def test_un_reenvio_con_el_id_de_la_fila_vieja_no_borra_a_la_que_reuso_el_numero(self):
        (orden,) = self._agregar()
        id_viejo = self._id_de(orden)
        servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_b, fila_id=id_viejo)
        (nueva,) = self._agregar()
        self.assertEqual(nueva, orden)
        self.assertNotEqual(self._id_de(nueva), id_viejo)
        trazas = TrazaCaso.objects.filter(caso=self.caso).count()

        reenvio = servicio.quitar_integrante(caso=self.caso, orden=orden, usuario=self.guardia_b, fila_id=id_viejo)

        self.assertTrue(reenvio.ya_estaba)
        self.assertEqual([fila.orden for fila in self._filas()], [1, 2, 3, 4])
        self.assertEqual((self._total(), TrazaCaso.objects.filter(caso=self.caso).count()), (4, trazas))

    def test_con_el_id_de_la_fila_actual_si_quita(self):
        (orden,) = self._agregar()

        quitada = servicio.quitar_integrante(
            caso=self.caso, orden=orden, usuario=self.guardia_b, fila_id=self._id_de(orden)
        )

        self.assertFalse(quitada.ya_estaba)
        self.assertEqual(self._total(), 3)

    def test_un_numero_que_nunca_existio_es_error(self):
        self.assertIn("no es de esta familia", self._rechazado(99)[0])
        self.assertEqual(self._total(), 3)

    def test_quitar_libera_la_reserva_que_la_derivacion_retiene_de_mas(self):
        self._agregar()  # la 4: la derivación reservó 3 camas
        self._confirmar_agregada(2)  # en una cama libre: las 3 reservas siguen, faltan 3 por confirmar
        abiertas = ReservaPlaza.objects.abiertas().filter(derivacion_id=self.derivacion.pk)
        self.assertEqual(abiertas.count(), 3)

        servicio.quitar_integrante(caso=self.caso, orden=4, usuario=self.guardia_b)

        self.assertEqual(abiertas.count(), 2)  # faltan 2 por confirmar: sobraba una

    def test_quitar_sin_reserva_de_mas_no_libera_ninguna(self):
        self._agregar()
        abiertas = ReservaPlaza.objects.abiertas().filter(derivacion_id=self.derivacion.pk)
        self.assertEqual(abiertas.count(), 3)

        servicio.quitar_integrante(caso=self.caso, orden=4, usuario=self.guardia_b)

        self.assertEqual(abiertas.count(), 3)

    def test_la_propiedad_se_puede_quitar_es_la_regla_unica(self):
        agregada, otra = self._agregar(2)
        self._confirmar_agregada(otra)
        filas = {fila.orden: fila.se_puede_quitar for fila in self._filas()}

        self.assertEqual(filas, {1: False, 2: False, 3: False, agregada: True, otra: False})

    def test_el_hueco_de_la_numeracion_no_crea_una_persona_fantasma(self):
        self._agregar(2)  # 4 y 5
        servicio.quitar_integrante(caso=self.caso, orden=4, usuario=self.guardia_b)

        filas = _asegurar_filas(self.caso.grupo)

        self.assertEqual(sorted(fila.orden for fila in filas), [1, 2, 3, 5])
        self.assertEqual((len(filas), self._total()), (4, 4))

    def test_la_fila_trae_la_bandera_solo_si_es_de_la_puerta_y_esta_sin_confirmar(self):
        agregada, otra = self._agregar(2)
        self._confirmar_agregada(otra)

        caso = CasoEmergencia.objects.select_related("grupo").get(pk=self.caso.pk)
        banderas = {f["n"]: f["puede_quitarse"] for f in selectores.integrantes_de(caso)["integrantes"]}

        self.assertEqual(banderas, {1: False, 2: False, 3: False, agregada: True, otra: False})


class QuitarIntegrantePantallaTests(BaseQuitar):
    def _url(self, nombre, *args):
        return reverse(f"dispositivos:emergencia_{nombre}", args=[self.club.pk, self.caso.pk, *args])

    def test_la_fila_agregada_ofrece_quitar_y_las_otras_no(self):
        self._agregar()
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("integrantes"))

        urls = {fila["n"]: fila["url_quitar"] for fila in respuesta.context["filas"]}
        con_id = self._url("quitar", 4) + f"?id={self._id_de(4)}"
        self.assertEqual(urls[4], con_id)
        self.assertEqual([urls[n] for n in (1, 2, 3)], ["", "", ""])
        self.assertContains(respuesta, 'data-confirm-url="' + con_id + '"')
        self.assertNotContains(respuesta, 'data-confirm-url="' + self._url("quitar", 2))

    def _id_de(self, orden):
        return IntegranteGrupo.objects.get(grupo_id=self.caso.grupo_id, orden=orden).pk

    def test_el_reenvio_de_la_pestana_vieja_no_borra_a_la_que_reuso_el_numero(self):
        self._agregar()
        id_viejo = self._id_de(4)
        self.client.force_login(self.guardia_b)
        self.client.post(self._url("quitar", 4) + f"?id={id_viejo}", follow=True)
        self._agregar()  # la nueva es otra vez la 4

        respuesta = self.client.post(self._url("quitar", 4) + f"?id={id_viejo}", follow=True)

        self.assertEqual(edificios._mensajes(respuesta), ["La persona 4 ya estaba quitada."])
        self.assertEqual((len(self._filas()), self._total()), (4, 4))

    def test_un_id_que_no_es_numero_se_ignora_y_actua_sobre_el_numero(self):
        self._agregar()
        self.client.force_login(self.guardia_b)

        self.client.post(self._url("quitar", 4) + "?id=abc", follow=True)

        self.assertEqual(self._total(), 3)

    def test_quita_y_vuelve_a_la_lista_con_el_aviso(self):
        self._agregar()
        self.client.force_login(self.guardia_b)

        respuesta = self.client.post(self._url("quitar", 4), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(edificios._mensajes(respuesta), ["Persona 4 quitada. La familia queda en 3."])
        self.assertEqual(self._total(), 3)

    def test_el_doble_envio_no_da_500(self):
        self._agregar()
        self.client.force_login(self.guardia_b)

        self.client.post(self._url("quitar", 4), follow=True)
        segunda = self.client.post(self._url("quitar", 4), follow=True)

        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(edificios._mensajes(segunda), ["La persona 4 ya estaba quitada."])
        self.assertEqual(self._total(), 3)

    def test_al_responsable_no_lo_quita(self):
        self.client.force_login(self.guardia_b)

        respuesta = self.client.post(self._url("quitar", 1), follow=True)

        self.assertIn(SOLO_SE_QUITA_LA_DE_LA_PUERTA, edificios._mensajes(respuesta)[0])
        self.assertEqual(self._total(), 3)

    def test_la_guardia_de_otro_edificio_no_quita(self):
        self._agregar()
        self.client.force_login(self.guardia_a)

        respuesta = self.client.post(self._url("quitar", 4))

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._total(), 4)

    def test_solo_por_post(self):
        self.client.force_login(self.guardia_b)

        self.assertEqual(self.client.get(self._url("quitar", 4)).status_code, 405)


class QuitarIntegranteApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()  # 7 personas
        self.cliente = self._como(self.guardia_centro)

    def _agregar(self):
        respuesta = self.cliente.post(
            _url("caso-integrantes", self.caso.pk), {"uuid_cliente": str(uuid.uuid4())}, format="json"
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        return respuesta.json()["integrante"]

    def _quitar(self, n, cliente=None):
        return (cliente or self.cliente).post(_url("caso-integrante-quitar", self.caso.pk, n), format="json")

    def _quitar_con_id(self, n, fila_id):
        return self.cliente.post(_url("caso-integrante-quitar", self.caso.pk, n), {"id": fila_id}, format="json")

    def _total(self):
        self.caso.grupo.refresh_from_db()
        return self.caso.grupo.total_declarado

    def test_la_lista_marca_solo_a_la_agregada_sin_confirmar(self):
        agregada = self._agregar()

        filas = self.cliente.get(_url("caso-integrantes", self.caso.pk)).json()["integrantes"]

        self.assertTrue(agregada["puede_quitarse"])
        self.assertEqual({f["n"]: f["puede_quitarse"] for f in filas}, {**{n: False for n in range(1, 8)}, 8: True})
        self.assertEqual(agregada["id"], next(f["id"] for f in filas if f["n"] == 8))
        self.assertEqual(len({f["id"] for f in filas}), 8)

    def test_el_reenvio_con_el_id_de_la_fila_vieja_no_borra_a_la_nueva(self):
        id_viejo = self._agregar()["id"]
        quitada = self._quitar_con_id(8, id_viejo)
        self.assertEqual(quitada.json()["ya_estaba_quitada"], False)
        nueva = self._agregar()
        self.assertEqual((nueva["n"], nueva["id"] != id_viejo), (8, True))

        reenvio = self._quitar_con_id(8, id_viejo)

        self.assertEqual(reenvio.status_code, 200, reenvio.content)
        self.assertEqual(reenvio.json(), {"n": 8, "total_declarado": 8, "ya_estaba_quitada": True})
        self.assertEqual(self._total(), 8)

    def test_con_el_id_de_la_fila_actual_quita(self):
        agregada = self._agregar()

        respuesta = self._quitar_con_id(8, agregada["id"])

        self.assertEqual(respuesta.json(), {"n": 8, "total_declarado": 7, "ya_estaba_quitada": False})

    def test_un_id_que_no_es_entero_es_400(self):
        self._agregar()

        respuesta = self._quitar_con_id(8, "abc")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(self._total(), 8)

    def test_un_numero_que_nunca_existio_es_400(self):
        respuesta = self._quitar(99)

        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn("orden", respuesta.json())

    def test_quita_y_la_respuesta_trae_el_total(self):
        self._agregar()

        respuesta = self._quitar(8)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"n": 8, "total_declarado": 7, "ya_estaba_quitada": False})
        self.assertEqual(self._total(), 7)

    def test_el_reenvio_es_200_y_no_toca_nada(self):
        self._agregar()
        self._quitar(8)

        respuesta = self._quitar(8)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"n": 8, "total_declarado": 7, "ya_estaba_quitada": True})

    def test_rechaza_al_responsable_a_un_original_y_a_una_confirmada(self):
        agregada = self._agregar()
        self._confirmar(self.caso, agregada["n"], "45000999", plaza=selectores.camas_libres(self.centro)[0])
        for n in (1, 5, agregada["n"]):
            with self.subTest(n=n):
                respuesta = self._quitar(n)
                self.assertEqual(respuesta.status_code, 400, respuesta.content)
                self.assertIn("orden", respuesta.json())
        self.assertEqual(self._total(), 8)

    def test_una_guardia_de_otro_dispositivo_no_la_ve(self):
        self._agregar()

        respuesta = self._quitar(8, self._como(self.guardia_escuela))

        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(self._total(), 8)

    def test_sin_el_ingreso_en_curso_es_409(self):
        caso, _derivacion = self._derivado(dni="30222333")

        respuesta = self.cliente.post(_url("caso-integrante-quitar", caso.pk, 8), format="json")

        self.assertEqual(respuesta.status_code, 409)
