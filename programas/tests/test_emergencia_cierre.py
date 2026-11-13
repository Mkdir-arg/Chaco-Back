"""Emergencia, etapa 3, paso 3 (``services.emergencia_cierre``): alojar, diferencia, cancelar y egreso.

* **M2-5** — «Familia alojada» con N de N; **RN-3.9** — cerrar con diferencia; cancelar sin
  confirmadas (03 §5).
* **RN-3.12** — el egreso de un integrante y el cierre del caso cuando egresa el último.
* **RN-3.14** — la novedad automática de la bitácora.
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase

from core.tests.candados import orden_de_candados
from legajos.models.contactos import VinculoFamiliar
from programas.models import (
    CasoEmergencia,
    Derivacion,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    ReservaPlaza,
    Sector,
    TrazaCaso,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.estadias import egresar_persona
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion


# ---------------------------------------------------------------------------
# Alojar, diferencia (RN-3.9) y cancelar
# ---------------------------------------------------------------------------


class CerrarElIngresoTests(BaseAlojar):
    def _familia_de(self, personas, **kwargs):
        """Un ingreso aceptado de ``personas`` adultos (1 a 4)."""

        cantidades = {"menores_f": 0, "menores_m": 0, "adultos_f": 1, "adultos_m": personas - 1}
        return self._aceptado(**cantidades, **kwargs)

    def _confirmar_a_todos(self, caso, derivacion):
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

    def test_familia_alojada_con_todas_confirmadas(self):
        self._turno(self.club)
        caso, derivacion = self._familia_de(3)
        self._confirmar_a_todos(caso, derivacion)
        sector = Sector.objects.get(dispositivo=self.club)

        alojado = servicio.alojar_familia(
            caso=caso,
            usuario=self.guardia,
            sector=sector,
            aula="Aula 3",
            tarjeta_entregada=True,
            tarjeta_numero="0042",
            encargado="",
        )

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.ALOJADO)
        self.assertEqual(fila["alojado_en"], T0)
        self.assertEqual(fila["total_alojado"], 3)
        self.assertEqual(
            fila["situacion"]["alojamiento"],
            {
                "sector_id": sector.pk,
                "sector": "General",
                "aula": "Aula 3",
                "tarjeta_entregada": True,
                "tarjeta_numero": "0042",
                "encargado": "guardia_club",
            },
        )
        self.assertFalse(alojado.ingreso_parcial)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.ALOJADO)
        self.assertIn("3 de 3", traza.detalle)
        self.assertIn("Aula 3", traza.detalle)
        self.assertTrue(
            EntradaBitacora.objects.filter(tipo="GENERAL", texto__contains="familia alojada 3 de 3").exists()
        )

    def test_con_una_sola_sin_confirmar_no_se_aloja(self):
        caso, derivacion = self._familia_de(3)
        self._confirmar(caso, 1, "45000101")

        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertIn("Falta confirmar a 2 personas", error.exception.messages[0])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_la_tarjeta_entregada_pide_su_numero_y_el_sector_es_del_dispositivo(self):
        caso, derivacion = self._familia_de(1)
        self._confirmar_a_todos(caso, derivacion)
        ajeno = Sector.objects.get(dispositivo=self.escuela)

        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia, tarjeta_entregada=True)
        self.assertEqual(set(error.exception.error_dict), {"tarjeta_numero"})
        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia, sector=ajeno.pk)
        self.assertEqual(set(error.exception.error_dict), {"sector"})
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_al_alojar_se_sueltan_las_camas_que_la_mesa_pidio_de_mas(self):
        caso, derivacion = self._familia_de(2, plazas=4)
        for orden, reserva in enumerate(self._reservas(derivacion)[:2], start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        alojado = servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertEqual(alojado.reservas_liberadas, 2)
        self.assertEqual(self._reservas(derivacion), [])

    def test_cerrar_con_diferencia_aloja_a_las_que_llegaron_y_suelta_el_resto(self):
        """HU-3.4: 5 de 7."""

        self._turno(self.club)
        caso, derivacion = self._aceptado()
        for orden, reserva in enumerate(self._reservas(derivacion)[:5], start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        cerrado = servicio.cerrar_con_diferencia(
            caso=caso,
            usuario=self.guardia,
            motivo="OTRO",
            observacion="Uno quedó con familiares, otro derivado a salud",
        )

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.ALOJADO)
        self.assertEqual(fila["total_alojado"], 5)
        self.assertEqual(fila["alojado_en"], T0)
        self.assertTrue(cerrado.ingreso_parcial)
        self.assertEqual(cerrado.reservas_liberadas, 2)
        self.assertEqual(self._reservas(derivacion), [])
        self.assertEqual(len(self._reservas(derivacion, ReservaPlaza.Estado.LIBERADA)), 2)
        self.assertEqual(len(self._reservas(derivacion, ReservaPlaza.Estado.CONSUMIDA)), 5)
        self.assertEqual(
            fila["situacion"]["diferencia"],
            {
                "motivo": "OTRO",
                "motivo_texto": "Otro",
                "observacion": "Uno quedó con familiares, otro derivado a salud",
                "confirmadas": 5,
                "declaradas": 7,
            },
        )
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.ALOJADO_CON_DIFERENCIA)
        self.assertIn("5 de 7", traza.detalle)
        self.assertIn("otro derivado a salud", traza.detalle)
        entrada = EntradaBitacora.objects.filter(tipo="GENERAL").order_by("-id").first()
        self.assertIn("ingreso cerrado con diferencia 5 de 7 · otro", entrada.texto)
        self.assertNotIn("familiares", entrada.texto, "la observación libre no va a la bitácora")

    def test_el_responsable_que_no_llega_queda_sin_confirmar(self):
        """03 §10: se confirma a los demás y se cierra con «No llegó al centro»."""

        caso, derivacion = self._familia_de(3)
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000102", plaza=reservas[0].plaza)
        self._confirmar(caso, 3, "45000103", plaza=reservas[1].plaza)

        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")

        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertFalse(IntegranteGrupo.objects.get(grupo=caso.grupo, orden=1).confirmada)
        self.assertFalse(Estadia.objects.filter(ciudadano=caso.grupo.responsable).exists())
        self.assertEqual(VinculoFamiliar.objects.filter(ciudadano_principal=caso.grupo.responsable).count(), 2)

    def test_la_diferencia_pide_motivo_al_menos_una_persona_y_que_falte_alguien(self):
        caso, derivacion = self._familia_de(2)
        for motivo, observacion, campo in (("", "", "motivo"), ("X", "", "motivo"), ("OTRO", "", "observacion")):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo=motivo, observacion=observacion)
            self.assertEqual(set(error.exception.error_dict), {campo})

        with self.assertRaises(ValidationError) as error:
            servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertIn("Todavía no confirmaste a nadie", error.exception.messages[0])

        self._confirmar_a_todos(caso, derivacion)
        with self.assertRaises(ValidationError) as error:
            servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertIn("no hay diferencia", error.exception.messages[0])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_cancelar_el_ingreso_sin_confirmadas_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._aceptado()

        cancelado = servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="La familia no llegó")

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(cancelado.reservas_liberadas, 7)
        derivacion.refresh_from_db()
        self.assertEqual((derivacion.estado, derivacion.motivo), (Derivacion.Estado.RECHAZADA, "La familia no llegó"))
        self.assertEqual(self._reservas(derivacion), [])
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.INGRESO_CANCELADO)
        # Las filas quedan, y una segunda aceptación no las duplica.
        nueva = mesa.derivar_caso(CasoEmergencia.objects.get(pk=caso.pk), self.operador, self.club, 7)
        servicio.aceptar_derivacion(derivacion=nueva, usuario=self.guardia)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 7)

    def test_con_una_persona_confirmada_no_se_cancela(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self.assertRaises(ValidationError) as error:
            servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="Me equivoqué")
        self.assertIn("cerrá el ingreso con diferencia", error.exception.messages[0])
        with self.assertRaises(ValidationError):
            servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo=" ")
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_ninguno_de_los_cierres_se_hace_sin_alcance(self):
        caso, derivacion = self._familia_de(2)
        self._confirmar(caso, 1, "45000101")
        acciones = (
            lambda: servicio.alojar_familia(caso=caso, usuario=self.guardia_escuela),
            lambda: servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia_escuela, motivo="NO_LLEGO"),
            lambda: servicio.cancelar_ingreso(caso=caso, usuario=self.guardia_escuela, motivo="x"),
        )
        for accion in acciones:
            with self.assertRaises(PermissionDenied):
                accion()
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(derivacion)), 1)


# ---------------------------------------------------------------------------
# Egreso (RN-3.12)
# ---------------------------------------------------------------------------


class EgresoTests(BaseAlojar):
    def _alojada(self, personas=2):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=personas - 1)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return servicio.alojar_familia(caso=caso, usuario=self.guardia)

    def _egresar(self, caso, orden):
        estadia = IntegranteGrupo.objects.get(grupo=caso.grupo, orden=orden).estadia
        self.reloj.avanzar(hours=1)
        return egresar_persona(
            estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio"
        )

    def test_el_egreso_de_uno_marca_al_integrante_y_el_caso_sigue_alojado(self):
        """HU-3.7."""

        caso = self._alojada(2)

        self._egresar(caso, 1)

        integrante = IntegranteGrupo.objects.get(grupo=caso.grupo, orden=1)
        self.assertEqual(integrante.egresado_en, T0 + timedelta(hours=1))
        self.assertIsNone(IntegranteGrupo.objects.get(grupo=caso.grupo, orden=2).egresado_en)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        traza = self._trazas(caso)[-1]
        self.assertEqual(
            (traza.accion, traza.detalle), (Accion.INTEGRANTE_EGRESADO, "Egresó la persona 1 de la familia")
        )

    def test_el_egreso_del_ultimo_cierra_el_caso(self):
        caso = self._alojada(2)
        self._egresar(caso, 1)

        self._egresar(caso, 2)

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.CERRADO)
        self.assertEqual(fila["motivo_cierre"], CasoEmergencia.MotivoCierre.TODOS_EGRESADOS)
        self.assertEqual(fila["cerrado_en"], T0 + timedelta(hours=2))
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.CERRADO_POR_EGRESO)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.ALOJADO, Estado.CERRADO))
        self.assertEqual(traza.usuario, self.guardia)

    def test_un_egreso_con_el_ingreso_en_curso_no_cierra_el_caso(self):
        """Lo cierra la guardia; al cerrar con diferencia se vuelve a mirar si quedó alguien."""

        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        self._confirmar(caso, 1, "45000101")
        self._egresar(caso, 1)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")

        self.assertEqual(self._estado(caso), Estado.CERRADO)

    def test_el_egreso_de_una_estadia_ajena_a_emergencia_cuesta_una_consulta_y_no_hace_nada(self):
        """El receptor está en el camino de **todos** los egresos de Dispositivos."""

        self._ocupar(self.club, 1)
        estadia = Estadia.objects.get()
        trazas = TrazaCaso.objects.count()

        with self.assertNumQueries(1):
            servicio.al_egresar_estadia(sender=Estadia, estadia=estadia, usuario=self.guardia)
        with orden_de_candados(caso=CasoEmergencia.objects) as orden:
            egresar_persona(estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio")

        self.assertEqual(orden, [])
        self.assertEqual(TrazaCaso.objects.count(), trazas)
        self.assertFalse(Estadia.objects.get().activa)

    def test_el_receptor_esta_conectado_una_sola_vez(self):
        from programas.senales import estadia_egresada

        servicio.conectar_receptores()
        servicio.conectar_receptores()
        receptores = [r for r in estadia_egresada._live_receivers(Estadia)[0] if r is servicio.al_egresar_estadia]
        self.assertEqual(len(receptores), 1)


class AccionesDelIngresoTests(SimpleTestCase):
    """**La** regla de los cierres: la usan los guardas del servicio y los botones de M2-3."""

    def _acciones(self, confirmadas, total, estado=Estado.INGRESO_EN_CURSO):
        return servicio.acciones_del_ingreso(estado=estado, confirmadas=confirmadas, total=total)

    def test_cada_cierre_segun_cuantas_se_confirmaron(self):
        self.assertEqual(
            self._acciones(0, 3), {"alojar": False, "diferencia": False, "cancelar": True, "agregar": True}
        )
        self.assertEqual(
            self._acciones(2, 3), {"alojar": False, "diferencia": True, "cancelar": False, "agregar": True}
        )
        self.assertEqual(
            self._acciones(3, 3), {"alojar": True, "diferencia": False, "cancelar": False, "agregar": True}
        )

    def test_fuera_del_ingreso_en_curso_no_hay_nada(self):
        for estado in (Estado.DERIVADO, Estado.ALOJADO, Estado.CERRADO):
            self.assertFalse(any(self._acciones(3, 3, estado).values()))
