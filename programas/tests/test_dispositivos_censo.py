"""Censo automático por turno y por día (MVP v2, etapa 3 · #696).

Lo que se verifica, y por qué:

1. **El censo cierra** —inicial + ingresos − egresos = final— y además **cuadra** con la
   existencia que dicen las estadías al fin de cada turno, que se calcula por separado.
2. **Cambio de turno y cambio de día**: la frontera es ``[inicio, fin)`` (las 14:00 en
   punto son de la Tarde), la Noche 22–06 del lunes es del lunes, y una estadía que
   ingresa a las 23:00 y egresa a las 03:00 queda entera en la Noche del lunes.
3. **Hora local, no UTC**: Resistencia está a UTC−3, y un momento del martes en UTC
   todavía es del lunes acá.
4. **Un cambio de plaza no cambia la existencia** del dispositivo.
5. **Sin turnos** el día es de 00:00 a 00:00 local; **con huecos** entre turnos, los
   huecos son tramos sin turno y nada queda afuera.
6. **Un descuadre se ve**, en el turno en que pasó, y no se arrastra.
7. **Tres consultas fijas** para cualquier rango (``--tag performance``).

Todo con reloj fijo: los servicios ven ``timezone.now()`` en el miércoles 09/09/2026 al
mediodía, y los ingresos y egresos son cargas retroactivas de esa semana.

Las clases llevan ``@tag("mysql")``: el job «Motor real» del CI las corre además contra
``mariadb:10.11``, ``mariadb:11`` y ``mysql:8.0`` sin tablas de zona horaria, que es la
base de ECOM.
"""

import json
from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest import mock

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Estadia, MovimientoEstadia, Plaza, Turno
from programas.services.censo import (
    CERRADO,
    DIA_COMPLETO,
    EN_CURSO,
    POR_VENIR,
    SIN_TURNO,
    censo_del_dia,
    censo_en_curso,
    censo_por_dia,
    fecha_operativa_de,
)
from programas.services.estadias import cambiar_plaza, egresar_persona, ingresar_persona
from programas.services.ocupacion import alojada_en
from programas.tests.test_dispositivos_estadias import BaseEstadias

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_censo"

#: El lunes 07/09/2026, en hora de Resistencia.
DOMINGO = date(2026, 9, 6)
LUNES = date(2026, 9, 7)
MARTES = LUNES + timedelta(days=1)
MIERCOLES = LUNES + timedelta(days=2)


def _local(dia, hora, minuto=0, segundo=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto, segundo)))


#: El reloj de todos los tests: el miércoles al mediodía, con la semana ya pasada.
AHORA = _local(MIERCOLES, 12)


def _reloj(momento=AHORA):
    return mock.patch("django.utils.timezone.now", return_value=momento)


def _cifras(tramo):
    return (tramo.nombre, tramo.inicial, tramo.ingresos, tramo.egresos, tramo.final)


class BaseCenso(BaseEstadias):
    """El CIS con los tres turnos del mockup P10 y cuatro plazas en un sector."""

    def setUp(self):
        super().setUp()
        for orden, (nombre, desde, hasta) in enumerate((("Mañana", 6, 14), ("Tarde", 14, 22), ("Noche", 22, 6)), 1):
            Turno.objects.create(
                dispositivo=self.cis, nombre=nombre, hora_desde=time(desde), hora_hasta=time(hasta), orden=orden
            )
        self.p3 = Plaza.objects.create(sector=self.sector, codigo="P3")
        self.p4 = Plaza.objects.create(sector=self.sector, codigo="P4")
        self.tercera = Ciudadano.objects.create(dni="30555666", nombre="Rosa", apellido="Benítez")
        self.cuarta = Ciudadano.objects.create(dni="30777888", nombre="Félix", apellido="Ojeda")

    def _ingresar(self, persona, plaza, momento, dispositivo=None):
        with _reloj():
            return ingresar_persona(
                ciudadano=persona,
                dispositivo=dispositivo or self.cis,
                plaza=plaza,
                usuario=self.operador_cis if dispositivo is None else self.operador_parador,
                fecha_ingreso=momento,
            )

    def _egresar(self, estadia, momento, usuario=None):
        with _reloj():
            return egresar_persona(
                estadia=estadia, usuario=usuario or self.operador_cis, fecha_egreso=momento, motivo="Alta"
            )

    def _cambiar(self, estadia, plaza, momento):
        with _reloj():
            return cambiar_plaza(
                estadia=estadia, plaza=plaza, usuario=self.operador_cis, motivo="Convivencia", momento=momento
            )

    def _semana(self):
        """La semana del caso de la task, con todos los bordes.

        * Ana está desde el domingo en P1 y egresa el lunes a las 14:00 **en punto**.
        * Rosa ingresa el lunes a las 14:00 **en punto** en P3 y a las 16:00 cambia a P4.
        * Juan ingresa el lunes a las 23:00 en P2 y egresa el martes a las 03:00: entera
          en la Noche del lunes.
        * Félix ingresa el martes a las 06:00 **en punto** en P1: Mañana del martes.
        """

        ana = self._ingresar(self.persona, self.plaza, _local(DOMINGO, 10))
        self._egresar(ana, _local(LUNES, 14))
        rosa = self._ingresar(self.tercera, self.p3, _local(LUNES, 14))
        self._cambiar(rosa, self.p4, _local(LUNES, 16))
        juan = self._ingresar(self.otra_persona, self.otra_plaza, _local(LUNES, 23))
        self._egresar(juan, _local(MARTES, 3))
        felix = self._ingresar(self.cuarta, self.plaza, _local(MARTES, 6))
        return ana, rosa, juan, felix


@tag("mysql")
class CensoPorTurnoTests(BaseCenso):
    def test_cada_turno_cierra_y_cuadra_con_las_estadias(self):
        self._semana()

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)

        self.assertEqual(
            [_cifras(tramo) for tramo in censo.tramos],
            [("Mañana", 1, 0, 0, 1), ("Tarde", 1, 1, 1, 1), ("Noche", 1, 1, 1, 1)],
        )
        for tramo in censo.tramos:
            with self.subTest(tramo=tramo.nombre):
                self.assertEqual(tramo.inicial + tramo.ingresos - tramo.egresos, tramo.final)
                self.assertEqual(tramo.final, tramo.alojadas_al_fin, "el censo no cuadra con las estadías")
                self.assertTrue(tramo.cuadra)
                self.assertEqual(tramo.estado, CERRADO)
        self.assertTrue(censo.con_turnos)
        self.assertTrue(censo.cuadra)

    def test_el_total_del_dia_es_la_suma_de_sus_turnos(self):
        self._semana()

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)

        self.assertEqual((censo.inicial, censo.ingresos, censo.egresos, censo.final), (1, 2, 2, 1))
        self.assertEqual(censo.final, censo.alojadas_al_fin)
        self.assertEqual((censo.inicio, censo.fin), (_local(LUNES, 6), _local(MARTES, 6)))

    def test_los_turnos_de_un_dia_se_encadenan(self):
        """El final de un turno es el inicial del siguiente, y uno empieza donde termina el otro."""

        self._semana()

        tramos = censo_del_dia(self.cis, LUNES, ahora=AHORA).tramos

        for anterior, siguiente in zip(tramos, tramos[1:], strict=False):
            self.assertEqual(anterior.fin, siguiente.inicio)
            self.assertEqual(anterior.final, siguiente.inicial)

    def test_el_borde_exacto_del_turno_es_del_turno_que_empieza(self):
        """`[inicio, fin)`: el egreso y el ingreso de las 14:00 en punto son de la Tarde."""

        self._semana()

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)
        manana, tarde = censo.tramo_de(_local(LUNES, 13, 59, 59)), censo.tramo_de(_local(LUNES, 14))

        self.assertEqual((manana.nombre, manana.ingresos, manana.egresos), ("Mañana", 0, 0))
        self.assertEqual((tarde.nombre, tarde.ingresos, tarde.egresos), ("Tarde", 1, 1))
        # Ana estaba al terminar la Mañana —egresa a las 14:00— y Rosa todavía no.
        self.assertEqual(manana.alojadas_al_fin, 1)

    def test_un_segundo_antes_del_borde_es_del_turno_que_termina(self):
        ana = self._ingresar(self.persona, self.plaza, _local(DOMINGO, 10))
        self._egresar(ana, _local(LUNES, 13, 59, 59))

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)

        self.assertEqual(
            [_cifras(tramo) for tramo in censo.tramos][:2], [("Mañana", 1, 0, 1, 0), ("Tarde", 0, 0, 0, 0)]
        )
        self.assertTrue(censo.cuadra)

    def test_la_estadia_de_23_a_03_queda_entera_en_la_noche_del_lunes(self):
        juan = self._ingresar(self.otra_persona, self.otra_plaza, _local(LUNES, 23))
        self._egresar(juan, _local(MARTES, 3))

        lunes, martes = censo_por_dia(self.cis, LUNES, MARTES, ahora=AHORA)

        noche = lunes.tramos[-1]
        self.assertEqual(_cifras(noche), ("Noche", 0, 1, 1, 0))
        self.assertEqual((noche.inicio, noche.fin), (_local(LUNES, 22), _local(MARTES, 6)))
        self.assertTrue(noche.cuadra)
        self.assertEqual((martes.ingresos, martes.egresos), (0, 0), "el martes 03:00 es de la Noche del lunes")

    def test_a_mitad_de_la_noche_la_existencia_incluye_a_quien_ingreso_a_las_23(self):
        """La regla de `ocupacion` en el medio del tramo, no solo en los bordes."""

        juan = self._ingresar(self.otra_persona, self.otra_plaza, _local(LUNES, 23))
        self._egresar(juan, _local(MARTES, 3))
        estadia = Estadia.objects.get(pk=juan.pk)

        self.assertTrue(alojada_en(estadia.fecha_ingreso, estadia.fecha_egreso, _local(MARTES, 1)))
        self.assertFalse(alojada_en(estadia.fecha_ingreso, estadia.fecha_egreso, _local(LUNES, 23)))
        self.assertTrue(alojada_en(estadia.fecha_ingreso, estadia.fecha_egreso, _local(MARTES, 3)))
        self.assertFalse(alojada_en(estadia.fecha_ingreso, estadia.fecha_egreso, _local(MARTES, 3, 0, 1)))

    def test_un_cambio_de_plaza_no_es_ni_ingreso_ni_egreso(self):
        rosa = self._ingresar(self.tercera, self.p3, _local(DOMINGO, 10))
        self._cambiar(rosa, self.p4, _local(LUNES, 16))
        self._cambiar(rosa, self.plaza, _local(LUNES, 23))

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)

        self.assertEqual(MovimientoEstadia.objects.filter(estadia=rosa).count(), 3)
        self.assertEqual(
            [_cifras(tramo) for tramo in censo.tramos],
            [("Mañana", 1, 0, 0, 1), ("Tarde", 1, 0, 0, 1), ("Noche", 1, 0, 0, 1)],
        )
        self.assertTrue(censo.cuadra)


@tag("mysql")
class CensoPorDiaTests(BaseCenso):
    def test_un_dia_empieza_donde_termino_el_anterior(self):
        self._semana()

        lunes, martes = censo_por_dia(self.cis, LUNES, MARTES, ahora=AHORA)

        self.assertEqual(lunes.fin, martes.inicio)
        self.assertEqual(lunes.final, martes.inicial)
        self.assertEqual(_cifras(martes.tramos[0]), ("Mañana", 1, 1, 0, 2), "Félix entra a las 06:00 del martes")
        self.assertEqual((martes.inicial, martes.ingresos, martes.egresos, martes.final), (1, 1, 0, 2))
        self.assertTrue(lunes.cuadra and martes.cuadra)

    def test_un_rango_da_lo_mismo_que_cada_dia_por_separado(self):
        self._semana()

        rango = censo_por_dia(self.cis, DOMINGO, MIERCOLES, ahora=AHORA)
        sueltos = [censo_del_dia(self.cis, dia, ahora=AHORA) for dia in (DOMINGO, LUNES, MARTES, MIERCOLES)]

        self.assertEqual([c.fecha_operativa for c in rango], [DOMINGO, LUNES, MARTES, MIERCOLES])
        self.assertEqual(rango, sueltos)

    def test_se_cuenta_en_hora_local_y_no_en_utc(self):
        """Martes 00:30 UTC es lunes 21:30 en Resistencia: Tarde del lunes, no Noche ni martes."""

        momento = datetime(2026, 9, 8, 0, 30, tzinfo=dt_timezone.utc)
        self._ingresar(self.persona, self.plaza, momento)

        lunes, martes = censo_por_dia(self.cis, LUNES, MARTES, ahora=AHORA)

        self.assertEqual(_cifras(lunes.tramos[1]), ("Tarde", 0, 1, 0, 1))
        self.assertEqual(martes.ingresos, 0)
        self.assertTrue(lunes.cuadra)

    def test_un_rango_al_reves_no_se_calcula(self):
        with self.assertRaises(ValueError):
            censo_por_dia(self.cis, MARTES, LUNES)


@tag("mysql")
class CensoSinTurnosTests(BaseCenso):
    """El Parador no tiene turnos: el día es de 00:00 a 00:00 local, en un solo tramo."""

    def test_sin_turnos_el_dia_es_de_medianoche_a_medianoche_local(self):
        tarde = self._ingresar(self.persona, self.plaza_parador, _local(LUNES, 23, 30), dispositivo=self.parador)
        self._egresar(tarde, _local(MARTES, 0), usuario=self.operador_parador)

        lunes, martes = censo_por_dia(self.parador, LUNES, MARTES, ahora=AHORA)

        self.assertFalse(lunes.con_turnos)
        self.assertEqual(len(lunes.tramos), 1)
        tramo = lunes.tramos[0]
        self.assertIsNone(tramo.turno)
        self.assertEqual(tramo.nombre, DIA_COMPLETO)
        self.assertEqual((tramo.inicio, tramo.fin), (_local(LUNES, 0), _local(MARTES, 0)))
        self.assertEqual(_cifras(tramo), (DIA_COMPLETO, 0, 1, 0, 1))
        # El egreso de las 00:00 en punto es del martes.
        self.assertEqual(_cifras(martes.tramos[0]), (DIA_COMPLETO, 1, 0, 1, 0))
        self.assertTrue(lunes.cuadra and martes.cuadra)

    def test_sin_turnos_la_medianoche_es_la_local_y_no_la_de_utc(self):
        """Lunes 22:00 en Resistencia es martes 01:00 UTC: sigue siendo del lunes."""

        self._ingresar(self.persona, self.plaza_parador, _local(LUNES, 22), dispositivo=self.parador)

        lunes, martes = censo_por_dia(self.parador, LUNES, MARTES, ahora=AHORA)

        self.assertEqual((lunes.ingresos, martes.ingresos), (1, 0))
        self.assertEqual((lunes.final, martes.inicial), (1, 1))

    def test_sin_turnos_la_fecha_operativa_es_la_local(self):
        self.assertEqual(fecha_operativa_de(self.parador, _local(LUNES, 23, 59)), LUNES)
        self.assertEqual(fecha_operativa_de(self.parador, _local(MARTES, 0)), MARTES)


@tag("mysql")
class CensoConHuecosTests(BaseCenso):
    """Turnos que no cubren el día: Mañana 08–12 y Tarde 14–20 en el Parador."""

    def setUp(self):
        super().setUp()
        Turno.objects.create(dispositivo=self.parador, nombre="Mañana", hora_desde=time(8), hora_hasta=time(12))
        Turno.objects.create(dispositivo=self.parador, nombre="Tarde", hora_desde=time(14), hora_hasta=time(20))

    def test_los_huecos_son_tramos_sin_turno_y_nada_queda_afuera(self):
        self._ingresar(self.persona, self.plaza_parador, _local(LUNES, 13), dispositivo=self.parador)

        censo = censo_del_dia(self.parador, LUNES, ahora=AHORA)

        self.assertEqual(
            [(tramo.nombre, tramo.inicio, tramo.fin) for tramo in censo.tramos],
            [
                ("Mañana", _local(LUNES, 8), _local(LUNES, 12)),
                (SIN_TURNO, _local(LUNES, 12), _local(LUNES, 14)),
                ("Tarde", _local(LUNES, 14), _local(LUNES, 20)),
                (SIN_TURNO, _local(LUNES, 20), _local(MARTES, 8)),
            ],
        )
        self.assertEqual(_cifras(censo.tramos[1]), (SIN_TURNO, 0, 1, 0, 1))
        self.assertEqual([tramo.nombre for tramo in censo.turnos], ["Mañana", "Tarde"])
        self.assertEqual((censo.ingresos, censo.final), (1, 1))
        self.assertTrue(censo.cuadra)

    def test_la_madrugada_antes_del_primer_turno_es_del_dia_anterior(self):
        self._ingresar(self.persona, self.plaza_parador, _local(MARTES, 7), dispositivo=self.parador)

        lunes, martes = censo_por_dia(self.parador, LUNES, MARTES, ahora=AHORA)

        self.assertEqual((lunes.ingresos, martes.ingresos), (1, 0))
        self.assertEqual(fecha_operativa_de(self.parador, _local(MARTES, 7)), LUNES)
        self.assertEqual(fecha_operativa_de(self.parador, _local(MARTES, 13)), MARTES)


@tag("mysql")
class DescuadreTests(BaseCenso):
    """Una estadía escrita por afuera de los servicios: sin su movimiento de ingreso."""

    def test_un_descuadre_se_ve_en_el_turno_en_que_paso_y_no_se_arrastra(self):
        self._semana()
        Estadia.objects.create(
            ciudadano=Ciudadano.objects.create(dni="30999000", nombre="Sin", apellido="Movimiento"),
            dispositivo=self.cis,
            fecha_ingreso=_local(LUNES, 15),
            estado=Estadia.Estado.ACTIVA,
            clave_alojamiento="CIU-externa",
        )

        censo = censo_del_dia(self.cis, LUNES, ahora=AHORA)
        manana, tarde, noche = censo.tramos

        self.assertTrue(manana.cuadra)
        self.assertFalse(tarde.cuadra)
        self.assertEqual((tarde.final, tarde.alojadas_al_fin, tarde.diferencia), (1, 2, 1))
        # La Noche arranca de la existencia real —manda la de las estadías— y cuadra.
        self.assertEqual(noche.inicial, 2)
        self.assertTrue(noche.cuadra)
        self.assertFalse(censo.cuadra)
        self.assertEqual(censo.diferencia, 1)


@tag("mysql")
class CensoEnCursoTests(BaseCenso):
    def test_a_las_tres_del_martes_el_dia_en_curso_es_el_lunes_y_rige_la_noche(self):
        self._semana()
        ahora = _local(MARTES, 3, 30)

        with _reloj(ahora):
            censo = censo_en_curso(self.cis)

        self.assertEqual(censo.fecha_operativa, LUNES)
        self.assertEqual([tramo.estado for tramo in censo.tramos], [CERRADO, CERRADO, EN_CURSO])
        self.assertEqual(censo.tramo_en_curso.nombre, "Noche")
        # El ingreso y el egreso de Juan ya pasaron; Félix (06:00) todavía no.
        self.assertEqual(_cifras(censo.tramo_en_curso), ("Noche", 1, 1, 1, 1))

    def test_a_la_manana_los_turnos_que_faltan_estan_por_venir(self):
        ana = self._ingresar(self.persona, self.plaza, _local(DOMINGO, 10))

        censo = censo_del_dia(self.cis, LUNES, ahora=_local(LUNES, 9))

        self.assertEqual([tramo.estado for tramo in censo.tramos], [EN_CURSO, POR_VENIR, POR_VENIR])
        self.assertEqual(censo.final, 1)
        self.assertTrue(Estadia.objects.get(pk=ana.pk).activa)


@tag("performance")
class CensoPresupuestoTests(BaseCenso):
    """El costo no crece con los días, los turnos, las personas ni los movimientos.

    Contar turno por turno —o persona por persona— es la forma natural de escribir el
    censo y la que mata la pantalla. El presupuesto vive en `scripts/perf_budgets.json`
    (sección `servicios`).
    """

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]

    def test_tres_consultas_para_un_dia_y_para_una_semana(self):
        techo = self._presupuesto()["consultas_fijas"]
        self._semana()

        with CaptureQueriesContext(connection) as un_dia:
            censo_del_dia(self.cis, LUNES, ahora=AHORA)
        with CaptureQueriesContext(connection) as una_semana:
            semana = censo_por_dia(self.cis, LUNES, LUNES + timedelta(days=6), ahora=AHORA)

        self.assertEqual(len(semana), 7)
        for medida, cuanto in ((un_dia, "un día"), (una_semana, "una semana")):
            self.assertLessEqual(
                len(medida),
                techo,
                f"{len(medida)} consultas para {cuanto}; el presupuesto de «{CLAVE_PRESUPUESTO}» en "
                f"scripts/perf_budgets.json es {techo}. Subirlo exige justificarlo en el mismo PR.",
            )

    def test_mas_personas_y_movimientos_no_agregan_consultas(self):
        """La guarda contra el N+1: una consulta por persona o por turno pasaría lo de arriba."""

        self._semana()
        with CaptureQueriesContext(connection) as antes:
            censo_por_dia(self.cis, LUNES, MARTES, ahora=AHORA)

        plazas = [Plaza.objects.create(sector=self.sector, codigo=f"X{n}") for n in range(12)]
        for numero, plaza in enumerate(plazas):
            persona = Ciudadano.objects.create(dni=f"40{numero:06d}", nombre="Persona", apellido=f"N{numero}")
            estadia = self._ingresar(persona, plaza, _local(LUNES, 7 + numero))
            if numero % 2:
                self._egresar(estadia, _local(MARTES, 1 + numero % 5))

        with CaptureQueriesContext(connection) as despues:
            lunes, _ = censo_por_dia(self.cis, LUNES, MARTES, ahora=AHORA)

        self.assertEqual(lunes.ingresos, 2 + 12)
        self.assertEqual(len(despues), len(antes))

    def test_con_los_turnos_ya_leidos_son_dos(self):
        from programas.services.bitacora import turnos_activos

        turnos = turnos_activos(self.cis)
        with CaptureQueriesContext(connection) as medida:
            censo_del_dia(self.cis, LUNES, turnos=turnos, ahora=AHORA)

        self.assertEqual(len(medida), 2)
