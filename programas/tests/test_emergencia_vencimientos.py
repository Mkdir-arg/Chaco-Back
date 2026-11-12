"""Emergencia — PR 4: los vencimientos de la mesa (RN-2.7, RN-2.8, HU-2.5).

Dos reglas de ``procesar_vencimientos``: la derivación sin respuesta que vence y el caso
en gestión que nadie mueve. Qué fija este archivo:

* **RN-2.7** — vence la ``PENDIENTE`` con el plazo cumplido y ninguna otra; el caso vuelve
  a ``EN_GESTION`` con el mismo operador y se puede volver a derivar.
* **RN-3.3, del lado del cron** — si el dispositivo aceptó entre la consulta y el candado,
  la derivación se saltea sin error.
* **RN-2.8** — el caso inactivo vuelve a ``NUEVO``; con ``sin_avance_min = 0`` no.
* **RN-2.9** — ninguna de las dos toca las marcas de tiempo.
* **RN-5.5** — cambiar la vigencia no mueve el ``vence_en`` de lo ya derivado.
* El comando corre las dos reglas con las de Becas, una fila que falla no frena a las
  demás, y cada ``pendientes()`` tiene su presupuesto de consultas.
* El orden de los candados, caso → derivación, por la secuencia de llamadas.

**Todos los momentos son fijos**: ``timezone.now`` está detenido en ``T0`` (el reloj de
``BaseCasos``) y avanza cuando el test lo dice. La carrera de verdad, con dos conexiones,
es del motor real; acá la ventana entre la consulta y el candado se abre a mano.
"""

import logging
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, tag

from core.services import vencimientos as registro
from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    NumeradorEmergencia,
    Plaza,
    Programa,
    ReservaPlaza,
    TrazaCaso,
)
from programas.services import emergencia as servicio
from programas.services import vencimientos_emergencia as reglas
from programas.services.configuracion_emergencia import guardar_sla
from programas.tests.test_emergencia_casos import T0, BaseCasos

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion

#: Los valores de fábrica de E7, escritos a mano: si cambian, estos tests tienen que enterarse.
VIGENCIA_MIN = 720
SIN_AVANCE_MIN = 60

LOG_REGLAS = "programas.services.vencimientos_emergencia"
REGLA_DERIVACION = "emergencia.derivacion"
REGLA_SIN_AVANCE = "emergencia.caso_sin_avance"


def _correr(*args, **opciones):
    salida = StringIO()
    call_command("procesar_vencimientos", *args, stdout=salida, stderr=StringIO(), **opciones)
    return salida.getvalue()


class BaseVencimientos(BaseCasos):
    def setUp(self):
        super().setUp()
        sla = guardar_sla(self.supervisor)
        self.assertEqual((sla.vigencia_derivacion_min, sla.sin_avance_min), (VIGENCIA_MIN, SIN_AVANCE_MIN))
        self.club = self._dispositivo("Club Sarmiento", camas=40)

    def _derivado(self, por=None):
        """Un caso tomado y derivado ahora. Devuelve ``(caso, derivacion)``."""

        caso = self._caso_tomado(por=por)
        return caso, servicio.derivar_caso(caso, por or self.operador, self.club, 2)

    def _resolver(self, derivacion, estado, estado_del_caso):
        """Deja la derivación como la dejaría la etapa 3 (aceptar, rechazar), que todavía no existe."""

        derivacion = Derivacion.objects.get(pk=derivacion.pk)
        derivacion.estado = estado
        derivacion.save(update_fields=["estado", "modificado"])
        CasoEmergencia.objects.filter(pk=derivacion.caso_id).update(estado=estado_del_caso)

    def _derivacion(self, derivacion):
        return Derivacion.objects.filter(pk=derivacion.pk).values().get()

    def _marcas(self, caso):
        fila = self._fila(caso)
        return {marca: fila[marca] for marca in CasoEmergencia.MARCAS}

    def _vencer_las_pendientes(self):
        return reglas.vencer_derivaciones(reglas.derivaciones_vencidas())

    def _devolver_los_inactivos(self):
        return reglas.devolver_casos_a_bandeja(reglas.casos_sin_avance())


# ---------------------------------------------------------------------------
# Regla 1: la derivación que vence sin respuesta (RN-2.7)
# ---------------------------------------------------------------------------


class DerivacionVencidaTests(BaseVencimientos):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._derivado()
        self.vence = T0 + timedelta(minutes=VIGENCIA_MIN)

    def test_vence_la_pendiente_cuando_llega_su_hora(self):
        """El borde: ``vence_en <= ahora``, con el igual."""
        self.assertEqual(self.derivacion.vence_en, self.vence)
        self.reloj.avanzar(minutes=VIGENCIA_MIN)

        self.assertEqual(self._vencer_las_pendientes(), 1)

        derivacion = self._derivacion(self.derivacion)
        fila = self._fila(self.caso)
        traza = self._trazas(self.caso)[-1]
        self.assertEqual(derivacion["estado"], Derivacion.Estado.VENCIDA)
        self.assertIsNone(derivacion["clave_vigente"])
        # Nadie la respondió: no se le inventa quién ni cuándo.
        self.assertEqual((derivacion["respondida_por_id"], derivacion["respondida_en"]), (None, None))
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.usuario_id, traza.por_supervisor),
            (Accion.DERIVACION_VENCIDA, Estado.DERIVADO, Estado.EN_GESTION, None, False),
        )
        self.assertEqual(traza.detalle, "Derivación vencida sin respuesta (Club Sarmiento)")
        self.assertEqual(traza.creado_en, self.vence)

    def test_no_vence_la_que_todavia_no_llego(self):
        self.reloj.avanzar(minutes=VIGENCIA_MIN - 1)

        self.assertEqual(reglas.derivaciones_vencidas().count(), 0)
        self.assertEqual(self._vencer_las_pendientes(), 0)
        # Ni por el servicio directo: el plazo se vuelve a mirar sobre la fila bloqueada.
        self.assertIsNone(servicio.vencer_derivacion(self.derivacion))
        self.assertEqual(self._derivacion(self.derivacion)["estado"], Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._fila(self.caso)["estado"], Estado.DERIVADO)

    def test_solo_vence_la_pendiente(self):
        """Una aceptada no vence nunca, por más que su ``vence_en`` haya pasado. Las resueltas tampoco."""
        _, aceptada = self._derivado()
        self._resolver(aceptada, Derivacion.Estado.ACEPTADA, Estado.INGRESO_EN_CURSO)
        _, rechazada = self._derivado()
        self._resolver(rechazada, Derivacion.Estado.RECHAZADA, Estado.EN_GESTION)
        _, cancelada = self._derivado()
        servicio.cancelar_derivacion(cancelada, self.operador, "La familia se fue con parientes")
        self.reloj.avanzar(days=3)
        trazas = TrazaCaso.objects.count()

        self.assertEqual(list(reglas.derivaciones_vencidas()), [self.derivacion])
        self.assertEqual(self._vencer_las_pendientes(), 1)

        esperado = {
            aceptada.pk: (Derivacion.Estado.ACEPTADA, Estado.INGRESO_EN_CURSO),
            rechazada.pk: (Derivacion.Estado.RECHAZADA, Estado.EN_GESTION),
            cancelada.pk: (Derivacion.Estado.CANCELADA, Estado.EN_GESTION),
        }
        for derivacion in (aceptada, rechazada, cancelada):
            with self.subTest(estado=esperado[derivacion.pk][0]):
                # Tampoco por el servicio directo, sin pasar por el filtro de la regla.
                self.assertIsNone(servicio.vencer_derivacion(derivacion))
                fila = self._derivacion(derivacion)
                self.assertEqual(
                    (fila["estado"], CasoEmergencia.objects.get(pk=fila["caso_id"]).estado), esperado[derivacion.pk]
                )
        self.assertEqual(TrazaCaso.objects.count(), trazas + 1)

    def test_la_segunda_corrida_no_toca_nada(self):
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)
        self.assertEqual(self._vencer_las_pendientes(), 1)
        antes = (self._derivacion(self.derivacion), self._fila(self.caso), len(self._trazas(self.caso)))
        self.reloj.avanzar(minutes=5)

        self.assertEqual(reglas.derivaciones_vencidas().count(), 0)
        self.assertEqual(self._vencer_las_pendientes(), 0)
        self.assertIsNone(servicio.vencer_derivacion(self.derivacion))
        self.assertEqual(
            (self._derivacion(self.derivacion), self._fila(self.caso), len(self._trazas(self.caso))), antes
        )

    def test_el_caso_vencido_se_puede_volver_a_derivar(self):
        """El ``UNIQUE`` de ``clave_vigente`` quedó libre y el caso sigue siendo del mismo operador."""
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)
        self._vencer_las_pendientes()

        nueva = servicio.derivar_caso(self.caso, self.operador, self.club, 3)

        self.assertEqual((nueva.estado, nueva.clave_vigente), (Derivacion.Estado.PENDIENTE, self.caso.pk))
        self.assertEqual(nueva.vence_en, self.reloj.ahora + timedelta(minutes=VIGENCIA_MIN))
        self.assertEqual(self._fila(self.caso)["estado"], Estado.DERIVADO)
        self.assertEqual(
            list(Derivacion.objects.filter(caso=self.caso).order_by("pk").values_list("estado", flat=True)),
            [Derivacion.Estado.VENCIDA, Derivacion.Estado.PENDIENTE],
        )

    def test_vencer_no_toca_ninguna_marca_de_tiempo(self):
        """RN-2.9: ni al vencer ni al volver a derivar después."""
        antes = self._marcas(self.caso)
        self.assertEqual((antes["tomado_en"], antes["derivado_en"]), (T0, T0))
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        self._vencer_las_pendientes()
        self.assertEqual(self._marcas(self.caso), antes)

        self.reloj.avanzar(minutes=5)
        servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        self.assertEqual(self._marcas(self.caso), antes)

    def test_si_el_dispositivo_acepto_entre_la_consulta_y_el_candado_se_saltea(self):
        """RN-3.3 del lado del cron: gana quien tomó primero el candado del caso.

        La ventana se abre a mano: la consulta del cron ya la vio pendiente y, justo antes
        de que el servicio bloquee el caso, la guardia la acepta. Lo que decide es lo que
        se lee **después** del candado.
        """
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)
        vistas = list(reglas.derivaciones_vencidas())
        self.assertEqual(vistas, [self.derivacion])
        trazas = len(self._trazas(self.caso))
        bloquear = servicio._bloquear_caso

        def acepta_justo_antes(caso):
            self._resolver(self.derivacion, Derivacion.Estado.ACEPTADA, Estado.INGRESO_EN_CURSO)
            return bloquear(caso)

        # Sin aviso: una aceptada que no vence es lo normal, no el «estado que no debería
        # existir». Es además lo que distingue al re-chequeo de la derivación del resguardo
        # sobre el estado del caso, que acá también la frenaría.
        with self.assertNoLogs("programas.services.emergencia", level=logging.WARNING):
            with mock.patch.object(servicio, "_bloquear_caso", acepta_justo_antes):
                # Por pk y no por estado: es la foto vieja, la que ya la había visto pendiente.
                procesadas = reglas.vencer_derivaciones(Derivacion.objects.filter(pk=self.derivacion.pk))

        self.assertEqual(procesadas, 0)
        derivacion = self._derivacion(self.derivacion)
        self.assertEqual(
            (derivacion["estado"], derivacion["clave_vigente"]), (Derivacion.Estado.ACEPTADA, self.caso.pk)
        )
        self.assertEqual(self._fila(self.caso)["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._trazas(self.caso)), trazas)

    def test_si_la_mesa_cancelo_y_volvio_a_derivar_entre_la_consulta_y_el_candado_se_saltea(self):
        """La otra carrera: el caso sigue ``DERIVADO``, pero por **otra** derivación.

        Acá el estado del caso no alcanza para darse cuenta. Sin releer el de la derivación,
        el cron marcaría vencida una cancelada y le sacaría el caso al dispositivo nuevo.
        """
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)
        self.assertEqual(list(reglas.derivaciones_vencidas()), [self.derivacion])
        bloquear = servicio._bloquear_caso
        nuevas = []

        def cancela_y_vuelve_a_derivar_justo_antes(caso):
            servicio.cancelar_derivacion(self.derivacion, self.operador, "Va a otro lugar")
            nuevas.append(servicio.derivar_caso(self.caso, self.operador, self.club, 2))
            return bloquear(caso)

        # Solo la primera vez: lo que hace la mesa adentro también bloquea el caso.
        candado = mock.Mock(side_effect=[cancela_y_vuelve_a_derivar_justo_antes] + [bloquear] * 2)
        with mock.patch.object(servicio, "_bloquear_caso", lambda caso: candado()(caso)):
            procesadas = reglas.vencer_derivaciones(Derivacion.objects.filter(pk=self.derivacion.pk))

        self.assertEqual(procesadas, 0)
        self.assertEqual(self._derivacion(self.derivacion)["estado"], Derivacion.Estado.CANCELADA)
        nueva = self._derivacion(nuevas[0])
        self.assertEqual((nueva["estado"], nueva["clave_vigente"]), (Derivacion.Estado.PENDIENTE, self.caso.pk))
        self.assertEqual(self._fila(self.caso)["estado"], Estado.DERIVADO)
        self.assertEqual(self._trazas(self.caso)[-1].accion, Accion.DERIVADO)

    def test_una_pendiente_de_un_caso_que_no_esta_derivado_no_se_adivina(self):
        """Un estado que no debería existir se avisa y se deja como está."""
        CasoEmergencia.objects.filter(pk=self.caso.pk).update(estado=Estado.EN_GESTION)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        with self.assertLogs("programas.services.emergencia", level=logging.WARNING):
            self.assertEqual(self._vencer_las_pendientes(), 0)

        self.assertEqual(self._derivacion(self.derivacion)["estado"], Derivacion.Estado.PENDIENTE)

    def test_una_fila_que_falla_no_frena_a_las_demas(self):
        """Y lo que se informa son las que se procesaron de verdad."""
        _, segunda = self._derivado()
        _, tercera = self._derivado()
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)
        vencer = servicio.vencer_derivacion

        def falla_en_la_segunda(derivacion):
            if derivacion.pk == segunda.pk:
                raise RuntimeError("se cortó la conexión")
            return vencer(derivacion)

        with mock.patch.object(servicio, "vencer_derivacion", falla_en_la_segunda):
            with self.assertLogs(LOG_REGLAS, level=logging.ERROR) as log:
                self.assertEqual(self._vencer_las_pendientes(), 2)

        self.assertTrue(any("Traceback" in linea and f"id={segunda.pk}" in linea for linea in log.output))
        self.assertEqual(
            {d.pk: d.estado for d in Derivacion.objects.all()},
            {
                self.derivacion.pk: Derivacion.Estado.VENCIDA,
                segunda.pk: Derivacion.Estado.PENDIENTE,
                tercera.pk: Derivacion.Estado.VENCIDA,
            },
        )
        # Sigue pendiente, así que la corrida siguiente la levanta.
        self.assertEqual(self._vencer_las_pendientes(), 1)

    def test_cambiar_la_vigencia_no_mueve_las_derivaciones_ya_creadas(self):
        """RN-5.5: ``vence_en`` se fijó al derivar. La vigencia nueva vale para la próxima."""
        guardar_sla(self.supervisor, vigencia_derivacion_min=30)
        self.assertEqual(self._derivacion(self.derivacion)["vence_en"], self.vence)

        self.reloj.avanzar(minutes=45)
        self.assertEqual(self._vencer_las_pendientes(), 0)
        _, corta = self._derivado()
        self.assertEqual(corta.vence_en, self.reloj.ahora + timedelta(minutes=30))

        self.reloj.avanzar(minutes=30)
        self.assertEqual(list(reglas.derivaciones_vencidas()), [corta])
        self.reloj.ahora = self.vence
        self.assertEqual(set(reglas.derivaciones_vencidas()), {corta, self.derivacion})


# ---------------------------------------------------------------------------
# Regla 2: el caso en gestión sin avance (RN-2.8)
# ---------------------------------------------------------------------------


class CasoSinAvanceTests(BaseVencimientos):
    def setUp(self):
        super().setUp()
        self.caso = self._caso_tomado()

    def test_devuelve_a_la_bandeja_el_caso_inactivo(self):
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN, seconds=1)

        self.assertEqual(self._devolver_los_inactivos(), 1)

        fila = self._fila(self.caso)
        traza = self._trazas(self.caso)[-1]
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.NUEVO, None))
        # RN-2.9: el tramo «tomar» sigue corriendo desde la primera vez.
        self.assertEqual(fila["tomado_en"], T0)
        self.assertEqual(
            (traza.accion, traza.estado_anterior, traza.estado_nuevo, traza.usuario_id, traza.por_supervisor),
            (Accion.DEVUELTO_POR_INACTIVIDAD, Estado.EN_GESTION, Estado.NUEVO, None, False),
        )
        self.assertEqual(traza.detalle, "Devuelto a bandeja por inactividad (Ana López)")

    def test_a_los_minutos_justos_todavia_no(self):
        """«Anterior a»: con la última traza exactamente en el límite, el plazo no se cumplió."""
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN)

        self.assertEqual(reglas.casos_sin_avance().count(), 0)
        self.assertIsNone(servicio.devolver_a_bandeja_por_inactividad(self.caso))
        self.assertEqual(self._fila(self.caso)["estado"], Estado.EN_GESTION)

    def test_cualquier_traza_reciente_cuenta_como_avance(self):
        """Lo que se mira es la **última** traza, no cuándo se tomó."""
        self.reloj.avanzar(minutes=50)
        servicio.registrar_contacto(self.caso, self.operador, canal="LLAMADA", resultado="NO_ATENDIO")
        self.reloj.avanzar(minutes=50)

        self.assertEqual(self._devolver_los_inactivos(), 0)
        self.assertEqual(self._fila(self.caso)["tomado_por_id"], self.operador.pk)

        self.reloj.avanzar(minutes=11)
        self.assertEqual(self._devolver_los_inactivos(), 1)

    def test_con_cero_minutos_la_regla_esta_apagada(self):
        guardar_sla(self.supervisor, sin_avance_min=0)
        self.reloj.avanzar(days=5)

        self.assertEqual(reglas.casos_sin_avance().count(), 0)
        self.assertEqual(self._devolver_los_inactivos(), 0)
        self.assertIsNone(servicio.limite_de_inactividad())
        self.assertIsNone(servicio.devolver_a_bandeja_por_inactividad(self.caso))
        self.assertEqual(self._fila(self.caso)["estado"], Estado.EN_GESTION)

    def test_la_segunda_corrida_no_toca_nada(self):
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)
        self.assertEqual(self._devolver_los_inactivos(), 1)
        antes = (self._fila(self.caso), len(self._trazas(self.caso)))
        self.reloj.avanzar(days=1)

        self.assertEqual(reglas.casos_sin_avance().count(), 0)
        self.assertEqual(self._devolver_los_inactivos(), 0)
        self.assertEqual((self._fila(self.caso), len(self._trazas(self.caso))), antes)

    def test_solo_mira_los_casos_en_gestion(self):
        nuevo = self._caso()
        derivado, _ = self._derivado()
        cerrado = servicio.cerrar_sin_alojamiento(self._caso_tomado(), self.operador, "NO_REQUIERE")
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)

        self.assertEqual(list(reglas.casos_sin_avance()), [self.caso])
        self.assertEqual(self._devolver_los_inactivos(), 1)

        for caso, estado in ((nuevo, Estado.NUEVO), (derivado, Estado.DERIVADO), (cerrado, Estado.CERRADO)):
            with self.subTest(estado=estado):
                self.assertIsNone(servicio.devolver_a_bandeja_por_inactividad(caso))
                self.assertEqual(self._fila(caso)["estado"], estado)

    def test_el_caso_devuelto_se_puede_volver_a_tomar(self):
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)
        self._devolver_los_inactivos()

        tomado = servicio.tomar_caso(self.caso, self.otro_operador)

        self.assertEqual(
            (tomado.estado, tomado.tomado_por_id, tomado.tomado_en), (Estado.EN_GESTION, self.otro_operador.pk, T0)
        )

    def test_si_el_operador_hizo_algo_entre_la_consulta_y_el_candado_se_saltea(self):
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)
        self.assertEqual(list(reglas.casos_sin_avance()), [self.caso])
        bloquear = servicio._bloquear_caso

        def contacta_justo_antes(caso):
            TrazaCaso.objects.create(caso=self.caso, usuario=self.operador, accion=Accion.CONTACTO)
            return bloquear(caso)

        with mock.patch.object(servicio, "_bloquear_caso", contacta_justo_antes):
            procesados = reglas.devolver_casos_a_bandeja(CasoEmergencia.objects.filter(pk=self.caso.pk))

        self.assertEqual(procesados, 0)
        fila = self._fila(self.caso)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))

    def test_el_caso_que_vuelve_de_una_derivacion_vencida_no_se_devuelve_en_la_misma_corrida(self):
        """La traza del vencimiento es actividad: el operador tiene un plazo entero para volver a derivar.

        Estuvo doce horas derivado sin una sola traza. Sin la del vencimiento, la segunda
        regla lo mandaría a la bandeja en el mismo minuto en que la primera se lo devuelve.
        """
        derivacion = servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        salida = _correr()

        self.assertIn(f"{REGLA_DERIVACION}: 1 procesado(s)", salida)
        self.assertIn(f"{REGLA_SIN_AVANCE}: sin pendientes.", salida)
        self.assertEqual(self._derivacion(derivacion)["estado"], Derivacion.Estado.VENCIDA)
        fila = self._fila(self.caso)
        self.assertEqual((fila["estado"], fila["tomado_por_id"]), (Estado.EN_GESTION, self.operador.pk))

        # Y con el plazo cumplido desde el vencimiento, sí.
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN, seconds=1)
        self.assertIn(f"{REGLA_SIN_AVANCE}: 1 procesado(s)", _correr())
        self.assertEqual(self._fila(self.caso)["estado"], Estado.NUEVO)

    def test_tampoco_si_las_reglas_corren_en_el_otro_orden(self):
        servicio.derivar_caso(self.caso, self.operador, self.club, 2)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        self.assertEqual(self._devolver_los_inactivos(), 0)
        self.assertEqual(self._vencer_las_pendientes(), 1)
        self.assertEqual(self._devolver_los_inactivos(), 0)

        self.assertEqual(self._fila(self.caso)["estado"], Estado.EN_GESTION)

    def test_una_fila_que_falla_no_frena_a_las_demas(self):
        otro = self._caso_tomado(por=self.otro_operador)
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)
        devolver = servicio.devolver_a_bandeja_por_inactividad

        def falla_en_el_primero(caso):
            if caso.pk == self.caso.pk:
                raise RuntimeError("se cortó la conexión")
            return devolver(caso)

        with mock.patch.object(servicio, "devolver_a_bandeja_por_inactividad", falla_en_el_primero):
            with self.assertLogs(LOG_REGLAS, level=logging.ERROR):
                self.assertEqual(self._devolver_los_inactivos(), 1)

        self.assertEqual(self._fila(self.caso)["estado"], Estado.EN_GESTION)
        self.assertEqual(self._fila(otro)["estado"], Estado.NUEVO)


# ---------------------------------------------------------------------------
# El comando y el registro
# ---------------------------------------------------------------------------


class ComandoTests(BaseVencimientos):
    def test_las_dos_reglas_estan_registradas_despues_de_las_de_becas(self):
        slugs = [regla.slug for regla in registro.REGLAS]

        self.assertEqual(
            [slug for slug in slugs if slug.startswith(("becas.", "emergencia."))],
            ["becas.convocatoria", "becas.relevamiento", REGLA_DERIVACION, REGLA_SIN_AVANCE],
        )
        por_slug = {regla.slug: regla for regla in registro.REGLAS}
        # Una transacción por fila: el comando no las envuelve en una sola.
        self.assertFalse(por_slug[REGLA_DERIVACION].transaccion_unica)
        self.assertFalse(por_slug[REGLA_SIN_AVANCE].transaccion_unica)
        self.assertTrue(por_slug["becas.convocatoria"].transaccion_unica)
        self.assertTrue(por_slug["becas.relevamiento"].transaccion_unica)

    def test_el_comando_corre_las_dos_reglas_junto_con_las_de_becas(self):
        _, derivacion = self._derivado()
        inactivo = self._caso_tomado(por=self.otro_operador)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        salida = _correr()

        self.assertIn("becas.convocatoria: sin pendientes.", salida)
        self.assertIn("becas.relevamiento: sin pendientes.", salida)
        self.assertIn(f"{REGLA_DERIVACION}: 1 procesado(s)", salida)
        self.assertIn(f"{REGLA_SIN_AVANCE}: 1 procesado(s)", salida)
        self.assertIn("Listo. 2 registro(s) procesado(s).", salida)
        self.assertEqual(self._derivacion(derivacion)["estado"], Derivacion.Estado.VENCIDA)
        self.assertEqual(self._fila(inactivo)["estado"], Estado.NUEVO)

        self.assertIn("Listo. 0 registro(s) procesado(s).", _correr())

    def test_dry_run_cuenta_y_no_toca(self):
        _, derivacion = self._derivado()
        inactivo = self._caso_tomado(por=self.otro_operador)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        salida = _correr("--dry-run")

        self.assertIn(f"[dry-run] {REGLA_DERIVACION}: 1 pendiente(s)", salida)
        self.assertIn(f"[dry-run] {REGLA_SIN_AVANCE}: 1 pendiente(s)", salida)
        self.assertEqual(self._derivacion(derivacion)["estado"], Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._fila(inactivo)["estado"], Estado.EN_GESTION)

    def test_solo_corre_la_regla_pedida(self):
        _, derivacion = self._derivado()
        inactivo = self._caso_tomado(por=self.otro_operador)
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        salida = _correr(solo=REGLA_SIN_AVANCE)

        self.assertNotIn(REGLA_DERIVACION, salida)
        self.assertEqual(self._derivacion(derivacion)["estado"], Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._fila(inactivo)["estado"], Estado.NUEVO)


class SinProgramaEmergenciaTests(TestCase):
    """Una base sin el módulo (la de los tests de Becas, un ambiente viejo) no tiene nada que vencer.

    El cron es uno solo para todas las reglas: las de Emergencia no pueden hacerlo terminar
    en error por un programa que esa base no tiene.
    """

    def test_el_comando_no_se_pone_rojo(self):
        cache.clear()
        self.assertFalse(Programa.objects.filter(codigo="EMERGENCIA").exists())

        salida = _correr()

        self.assertIn(f"{REGLA_DERIVACION}: sin pendientes.", salida)
        self.assertIn(f"{REGLA_SIN_AVANCE}: sin pendientes.", salida)
        self.assertIn("Listo. 0 registro(s) procesado(s).", salida)


# ---------------------------------------------------------------------------
# Presupuesto de consultas y orden de los candados
# ---------------------------------------------------------------------------


@tag("performance")
class PresupuestoDePendientesTests(BaseVencimientos):
    """``pendientes()`` cuesta lo mismo con un caso que con veinte: no hay consulta por fila."""

    def setUp(self):
        super().setUp()
        for _ in range(10):
            self._derivado()
            self._caso_tomado()
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

    def test_derivaciones_vencidas_es_una_consulta(self):
        with self.assertNumQueries(1):
            self.assertEqual(len(reglas.derivaciones_vencidas()), 10)
        with self.assertNumQueries(1):
            self.assertEqual(reglas.derivaciones_vencidas().count(), 10)

    def test_casos_sin_avance_es_una_sola_consulta_sobre_los_casos(self):
        """Más la de leer el SLA, que no depende de cuántos casos haya (el programa sale del cache)."""
        with self.assertNumQueries(2):
            self.assertEqual(len(reglas.casos_sin_avance()), 10)
        with self.assertNumQueries(2):
            self.assertEqual(reglas.casos_sin_avance().count(), 10)

    def test_apagada_no_consulta_los_casos(self):
        guardar_sla(self.supervisor, sin_avance_min=0)
        with self.assertNumQueries(1):
            self.assertEqual(len(reglas.casos_sin_avance()), 0)


class OrdenDeLosCandadosDelCronTests(BaseVencimientos):
    """El cron pide los candados en el orden del módulo: **caso → derivación**, y nada más.

    Aceptar (etapa 3), cancelar y vencer compiten por las mismas dos filas. Si el cron las
    pidiera al revés, InnoDB cortaría a uno con ``ERROR 1213`` en vez de dejar que gane el
    primero. En SQLite ``select_for_update()`` es un no-op, así que se prueba por la
    secuencia de llamadas, igual que ``OrdenDeLosCandadosEmergenciaTests``.
    """

    def _orden(self):
        return orden_de_candados(
            caso=CasoEmergencia.objects,
            derivacion=Derivacion.objects,
            plaza=Plaza.objects,
            reserva=ReservaPlaza.objects,
            persona=Ciudadano.objects,
            numerador=NumeradorEmergencia.objects,
        )

    def test_vencer_una_derivacion_toma_primero_el_caso(self):
        _, derivacion = self._derivado()
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        with self._orden() as orden:
            self.assertIsNotNone(servicio.vencer_derivacion(derivacion))

        self.assertEqual(orden, ["caso", "derivacion"])

    def test_la_regla_repite_ese_orden_por_cada_derivacion(self):
        for _ in range(3):
            self._derivado()
        self.reloj.avanzar(minutes=VIGENCIA_MIN + 5)

        with self._orden() as orden:
            self.assertEqual(self._vencer_las_pendientes(), 3)

        self.assertEqual(orden, ["caso", "derivacion"] * 3)

    def test_tambien_cuando_se_saltea(self):
        """El orden no depende de cómo termine: la que ya no está pendiente bloquea igual las dos."""
        _, derivacion = self._derivado()
        servicio.cancelar_derivacion(derivacion, self.operador, "Error de carga")

        with self._orden() as orden:
            self.assertIsNone(servicio.vencer_derivacion(derivacion))

        self.assertEqual(orden, ["caso", "derivacion"])

    def test_devolver_por_inactividad_bloquea_el_caso_y_nada_mas(self):
        caso = self._caso_tomado()
        self.reloj.avanzar(minutes=SIN_AVANCE_MIN + 5)

        with self._orden() as orden:
            self.assertEqual(self._devolver_los_inactivos(), 1)

        self.assertEqual(orden, ["caso"])
        self.assertEqual(self._fila(caso)["estado"], Estado.NUEVO)
