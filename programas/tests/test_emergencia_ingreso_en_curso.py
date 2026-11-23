"""Cambio 535 (L5): el ingreso en curso que no se destraba, las camas ya pedidas y las entregas duplicadas.

* **A** — quien supervisa la mesa cancela un «Ingreso en curso» sin nadie confirmado, con motivo:
  libera las reservas y deja traza. No vence solo: la bandeja y la ficha avisan «Aceptado sin
  movimiento hace N h» con N de E7.
* **B** — el modal de derivar dice cuántas camas ya se pidieron ahí y no las descuenta de las libres.
* **C** — «Crear entrega» de kits es idempotente: el mismo armado dos veces es una sola entrega.
* **D1** — un DNI escrito con espacios encuentra el caso. **D2** — una acción que ya no está en la
  ficha vuelve con el aviso y no con un 400 sin formulario.
"""

import uuid

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import CasoEmergencia, Derivacion, EntregaKit, IntegranteGrupo, TrazaCaso
from programas.selectors import emergencia_mesa as mesa
from programas.selectors.emergencia_derivar import clave_de_grupo, pedidas_pendientes
from programas.services import emergencia as servicio_mesa
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia_alta import UuidEnUso
from programas.services.emergencia_cierre import INGRESO_CON_CONFIRMADAS, cancelar_ingreso_por_la_mesa
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_kits_vistas import BaseVistasKits
from programas.tests.test_emergencia_mesa import URL_BANDEJA, BaseMesa

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


def _ficha(caso):
    return reverse("emergencia:caso_detalle", args=[caso.pk])


# ---------------------------------------------------------------------------
# A · Cancelar un ingreso en curso desde la mesa
# ---------------------------------------------------------------------------


class CancelarIngresoPorLaMesaTests(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado(adultos_f=1, adultos_m=1, menores_f=0, menores_m=0)
        self.url = reverse("emergencia:caso_cancelar_ingreso", args=[self.caso.pk])

    def _cancelar(self, usuario=None, motivo="La familia se fue a lo de un pariente", **extra):
        return cancelar_ingreso_por_la_mesa(caso=self.caso, usuario=usuario or self.supervisor, motivo=motivo, **extra)

    def test_libera_las_camas_cancela_la_derivacion_y_devuelve_el_caso_a_quien_lo_tenia(self):
        self.assertEqual(len(self._reservas(self.derivacion)), 2)

        caso = self._cancelar(derivacion_vista=self.derivacion.pk)

        self.assertEqual(caso.reservas_liberadas, 2)
        self.assertEqual(self._reservas(self.derivacion), [])
        self.assertEqual(self._estado(self.caso), Estado.EN_GESTION)
        derivacion = Derivacion.objects.get(pk=self.derivacion.pk)
        self.assertEqual(
            (derivacion.estado, derivacion.motivo, derivacion.respondida_por, derivacion.clave_vigente),
            (Derivacion.Estado.CANCELADA, "La familia se fue a lo de un pariente", self.supervisor, None),
        )
        traza = self._trazas(self.caso)[-1]
        self.assertEqual(
            (traza.accion, traza.por_supervisor, traza.usuario), (Accion.INGRESO_CANCELADO, True, self.supervisor)
        )
        self.assertIn("cancelado por la mesa: La familia se fue a lo de un pariente", traza.detalle)

    def test_solo_quien_supervisa(self):
        with self.assertRaises(PermissionDenied):
            self._cancelar(usuario=self.operador)
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(self.derivacion)), 2)

    def test_con_una_persona_confirmada_no_se_cancela(self):
        self._confirmar(self.caso, 1, "45000101")

        with self.assertRaises(ValidationError) as error:
            self._cancelar()

        self.assertEqual(error.exception.messages, [INGRESO_CON_CONFIRMADAS])
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(Derivacion.objects.get(pk=self.derivacion.pk).estado, Derivacion.Estado.ACEPTADA)

    def test_el_motivo_es_obligatorio(self):
        with self.assertRaises(ValidationError) as error:
            self._cancelar(motivo="   ")
        self.assertEqual(set(error.exception.error_dict), {"motivo"})
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)

    def test_una_derivacion_que_no_es_la_que_mostro_la_ficha_avisa_que_cambio(self):
        with self.assertRaises(servicio_mesa.EstadoCambio):
            self._cancelar(derivacion_vista=self.derivacion.pk + 999)
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)

    def test_la_ficha_ofrece_el_boton_solo_a_quien_supervisa(self):
        self.client.force_login(self.supervisor)
        respuesta = self.client.get(_ficha(self.caso))
        self.assertContains(respuesta, "Cancelar ingreso")
        self.assertContains(respuesta, f'value="{self.derivacion.pk}"')

        self.client.force_login(self.operador)
        respuesta = self.client.get(_ficha(self.caso))
        self.assertNotIn("form_cancelar_ingreso", respuesta.context)
        self.assertNotContains(respuesta, self.url)

    def test_por_la_vista(self):
        self.client.force_login(self.supervisor)

        respuesta = self.client.post(self.url, {"motivo": "No llegaron", "derivacion": self.derivacion.pk})

        self.assertRedirects(respuesta, _ficha(self.caso), fetch_redirect_response=False)
        self.assertEqual(self._estado(self.caso), Estado.EN_GESTION)
        self.assertEqual(self._reservas(self.derivacion), [])

    def test_por_la_vista_quien_no_supervisa_recibe_403(self):
        self.client.force_login(self.operador)
        respuesta = self.client.post(self.url, {"motivo": "No llegaron", "derivacion": self.derivacion.pk})
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)

    def test_d2_una_accion_que_ya_no_esta_en_la_ficha_vuelve_con_el_aviso_y_no_con_un_400(self):
        """Con alguien confirmado la ficha no tiene el formulario: no hay dónde mostrar el error."""
        self._confirmar(self.caso, 1, "45000101")
        self.client.force_login(self.supervisor)

        respuesta = self.client.post(self.url, {"motivo": "No llegaron", "derivacion": self.derivacion.pk})

        self.assertRedirects(respuesta, _ficha(self.caso), fetch_redirect_response=False)
        avisos = [str(m) for m in respuesta.wsgi_request._messages]
        self.assertIn(INGRESO_CON_CONFIRMADAS, " ".join(avisos))
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)


class AceptadoSinMovimientoTests(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado(adultos_f=1, adultos_m=1, menores_f=0, menores_m=0)

    def _avisos(self):
        caso = mesa.casos_para_ficha().get(pk=self.caso.pk)
        return [aviso["texto"] for aviso in mesa.avisos_de_la_mesa(caso, sla_vigente(), self.reloj())]

    def test_avisa_desde_las_horas_de_e7_sin_vencer_nada(self):
        self.reloj.avanzar(hours=5, minutes=59)
        self.assertEqual(self._avisos(), [])

        self.reloj.avanzar(hours=1, minutes=31)
        self.assertEqual(self._avisos(), ["Aceptado sin movimiento hace 7 h"])
        self.assertEqual(self._estado(self.caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(self.derivacion)), 2)

    def test_un_movimiento_reinicia_la_cuenta(self):
        self.reloj.avanzar(hours=7)
        self._confirmar(self.caso, 1, "45000101")
        self.assertEqual(self._avisos(), [])

    def test_las_horas_salen_de_e7_y_cero_lo_apaga(self):
        sla = sla_vigente()
        self.reloj.avanzar(hours=3)
        sla.ingreso_sin_movimiento_h = 2
        sla.save(update_fields=["ingreso_sin_movimiento_h"])
        self.assertEqual(self._avisos(), ["Aceptado sin movimiento hace 3 h"])

        sla.ingreso_sin_movimiento_h = 0
        sla.save(update_fields=["ingreso_sin_movimiento_h"])
        self.assertEqual(self._avisos(), [])

    def test_la_bandeja_y_la_ficha_lo_muestran(self):
        self.reloj.avanzar(hours=8)
        self.client.force_login(self.operador)

        self.assertContains(self.client.get(URL_BANDEJA, {"solapa": "abiertos"}), "Aceptado sin movimiento hace 8 h")
        self.assertContains(self.client.get(_ficha(self.caso)), "Aceptado sin movimiento hace 8 h")

    def test_e7_trae_el_campo_con_6_horas_de_fabrica(self):
        self.assertEqual(sla_vigente().ingreso_sin_movimiento_h, 6)
        self.client.force_login(self.supervisor)
        self.assertContains(self.client.get(reverse("emergencia:plazos")), 'name="ingreso_sin_movimiento_h"')


# ---------------------------------------------------------------------------
# B · Camas ya pedidas en el modal de derivar
# ---------------------------------------------------------------------------


class CamasYaPedidasTests(BaseAlojar):
    def test_cuenta_las_pendientes_de_ese_lugar_y_no_las_descuenta_de_las_libres(self):
        self._derivado(plazas=3, adultos_f=1, adultos_m=2, menores_f=0, menores_m=0)
        self._derivado(plazas=2, adultos_f=1, adultos_m=1, menores_f=0, menores_m=0)
        self._derivado(dispositivo=self.escuela, plazas=2, adultos_f=1, adultos_m=1, menores_f=0, menores_m=0)
        self.assertEqual(pedidas_pendientes(self.club.pk, None), (5, 2))

        caso = self._caso_tomado(adultos_f=1, adultos_m=1)
        self.client.force_login(self.operador)
        grupo = clave_de_grupo(None, self.club.pk)
        respuesta = self.client.get(_ficha(caso), {"grupo": grupo, "derivar": self.club.pk})

        confirmar = respuesta.context["confirmar_derivar"]
        self.assertEqual(confirmar["aviso"], "Vas a pedir 2 plazas y hay 9 libres. ¿Seguís?")
        self.assertIn("Ya hay 5 camas pedidas en 2 derivaciones pendientes", confirmar["ya_pedidas"])
        self.assertContains(respuesta, "No se descuentan de las libres")

    def test_sin_pendientes_no_dice_nada(self):
        caso = self._caso_tomado(adultos_f=1, adultos_m=1)
        self.client.force_login(self.operador)
        respuesta = self.client.get(
            _ficha(caso), {"grupo": clave_de_grupo(None, self.club.pk), "derivar": self.club.pk}
        )
        self.assertEqual(respuesta.context["confirmar_derivar"]["ya_pedidas"], "")


# ---------------------------------------------------------------------------
# C · «Crear entrega» idempotente
# ---------------------------------------------------------------------------


class ArmarEntregaIdempotenteTests(BaseVistasKits):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)
        self.url_nueva = f"{self._url('entrega_nueva')}?dispositivo={self.club.pk}"
        self.url_crear = self._url("entrega_nueva")

    def test_abrir_la_pantalla_hace_nacer_el_identificador_y_viaja_en_el_formulario(self):
        respuesta = self.client.get(self.url_nueva)
        armado = respuesta.context["form"].initial["uuid_cliente"]
        self.assertContains(respuesta, f'name="uuid_cliente" value="{armado}"')

    def test_volver_atras_y_reenviar_no_duplica_la_entrega(self):
        armado = self.client.get(self.url_nueva).context["form"].initial["uuid_cliente"]
        datos = {
            **self._cantidades(a=(self.colchon, 10)),
            "uuid_cliente": armado,
            "dispositivo": self.club.pk,
            "salida": "despues",
        }

        primera = self.client.post(self.url_crear, datos)
        segunda = self.client.post(self.url_crear, datos)

        entrega = EntregaKit.objects.get()
        self.assertRedirects(primera, self._url("entrega_detalle", entrega.pk), fetch_redirect_response=False)
        self.assertRedirects(segunda, self._url("entrega_detalle", entrega.pk), fetch_redirect_response=False)
        self.assertIn("ya estaba armada", self._avisos(segunda)[0])
        self.assertEqual(entrega.lineas.count(), 1)

    def test_el_servicio_devuelve_la_misma_y_otro_usuario_no_la_recibe(self):
        armado = uuid.uuid4()
        primera = self._entrega(uuid_cliente=armado)
        segunda = self._entrega(uuid_cliente=str(armado))

        self.assertEqual(segunda.pk, primera.pk)
        self.assertTrue(segunda.ya_existia)
        self.assertFalse(getattr(primera, "ya_existia", False))
        with self.assertRaises(UuidEnUso):
            self._entrega(uuid_cliente=armado, usuario=self.supervisor)
        self.assertEqual(EntregaKit.objects.count(), 1)

    def test_dos_armados_distintos_son_dos_entregas(self):
        self._entrega(uuid_cliente=uuid.uuid4())
        self._entrega(uuid_cliente=uuid.uuid4())
        self._entrega()
        self.assertEqual(EntregaKit.objects.count(), 3)


# ---------------------------------------------------------------------------
# D1 · DNI con espacios en el buscador de la bandeja
# ---------------------------------------------------------------------------


class DniConEspaciosTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.caso = self._caso(dni="30111222", nombre="Rosa", apellido="Benítez")
        self.otro = self._caso(dni="30333444", nombre="Marta", apellido="Acosta")
        persona = Ciudadano.objects.create(dni="40555666", nombre="Lucía", apellido="Gómez")
        IntegranteGrupo.objects.create(grupo=self.caso.grupo, orden=1, ciudadano=persona)
        self.client.force_login(self.operador)

    def _numeros(self, texto):
        respuesta = self.client.get(URL_BANDEJA, {"texto": texto})
        return [fila["caso"].numero for fila in respuesta.context["filas"]]

    def test_un_dni_escrito_con_espacios_encuentra_el_caso(self):
        self.assertEqual(self._numeros("30 111 222"), [self.caso.numero])
        self.assertEqual(self._numeros(" 40 555 666 "), [self.caso.numero])
        self.assertEqual(self._numeros("30 111.222"), [self.caso.numero])

    def test_palabras_que_no_son_un_dni_siguen_exigiendo_todas(self):
        self.assertEqual(self._numeros("Rosa 30333444"), [])
        self.assertEqual(self._numeros("12 34"), [])

    def test_no_suma_consultas(self):
        self.client.get(URL_BANDEJA, {"texto": "30111222"})
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as junto:
            self.client.get(URL_BANDEJA, {"texto": "30111222"})
        with CaptureQueriesContext(connection) as partido:
            self.client.get(URL_BANDEJA, {"texto": "30 111 222"})
        self.assertEqual(len(partido), len(junto))
