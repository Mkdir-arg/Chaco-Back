"""E8 · reglas puras de la foto de situación y orden de las alertas (Cambio 508 · E-4 #1183).

``services.situacion_emergencia`` sin base: presión, horas hasta saturar, camas cercanas, demanda en
alza, ``presentar_perfil``, ``sin_dosis``, los períodos de la ventana y el orden y tope de las
alertas. Los números de la foto y cada alerta sobre datos están en ``test_emergencia_situacion``.
"""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from programas.selectors import emergencia_situacion as situacion
from programas.selectors.emergencia_situacion import periodos_de_la_ventana
from programas.selectors.emergencia_tablero import ZONA_OPERATIVA, DispositivoDeLaRed
from programas.services import alertas_situacion_emergencia as alertas
from programas.services.emergencia_ficha import sin_dosis
from programas.services.ocupacion import NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL, Conteo
from programas.services.situacion_emergencia import (
    MENOS_DE_5,
    NIVEL_SIN_DEMANDA,
    NO_SE_SATURA,
    PROYECCION,
    SALUD_SOLO_PROVINCIAL,
    SATURADA,
    camas_cercanas,
    demanda_en_alza,
    horas_hasta_saturar,
    nivel_de_presion,
    presentar_perfil,
)
from programas.tests.test_emergencia_casos import T0


def _hora(hh, mm=0, dias=0):
    """Un momento del 12/11/2026 (hora Argentina), ``dias`` antes."""
    return T0.replace(hour=hh, minute=mm) - timedelta(days=dias)


class PresionTests(SimpleTestCase):
    def test_tc_1183_05_ejemplo_de_la_task(self):
        presion = nivel_de_presion(esperando=12, camas_cercanas=5)
        self.assertEqual((presion.nivel, presion.cociente), (NIVEL_CRITICA, 2.4))

    def test_tc_1183_02_el_borde_de_1_es_exigida(self):
        self.assertEqual(nivel_de_presion(10, 10).nivel, NIVEL_EXIGIDA)
        self.assertEqual(nivel_de_presion(11, 10).nivel, NIVEL_CRITICA)

    def test_tc_1183_03_los_bordes_de_0_5(self):
        self.assertEqual(nivel_de_presion(50, 100).nivel, NIVEL_EXIGIDA)
        self.assertEqual(nivel_de_presion(49, 100).nivel, NIVEL_NORMAL)

    def test_tc_1183_04_sin_camas_cercanas_y_sin_demanda(self):
        sin_camas = nivel_de_presion(3, 0)
        self.assertEqual(
            (sin_camas.nivel, sin_camas.cociente, sin_camas.sin_camas_cercanas), (NIVEL_CRITICA, None, True)
        )
        self.assertEqual(nivel_de_presion(0, 7).nivel, NIVEL_SIN_DEMANDA)
        self.assertEqual(nivel_de_presion(0, 0).nivel, NIVEL_SIN_DEMANDA)

    def test_los_tonos_son_los_de_la_tension(self):
        self.assertEqual(nivel_de_presion(3, 0).tono, "danger")
        self.assertEqual(nivel_de_presion(6, 10).tono, "warning")
        self.assertEqual(nivel_de_presion(1, 10).tono, "success")
        self.assertEqual(nivel_de_presion(0, 10).etiqueta, "Sin demanda")


class HorasHastaSaturarTests(SimpleTestCase):
    def test_tc_1183_06_ritmo_positivo(self):
        resultado = horas_hasta_saturar(disponibles=40, ingresos=12, egresos=2, horas=6)
        self.assertEqual((resultado.estado, resultado.horas), (PROYECCION, 24.0))
        self.assertEqual(horas_hasta_saturar(163, 132, 41).horas_redondeadas, 11)

    def test_tc_1183_07_ritmo_cero_o_negativo_no_satura(self):
        self.assertEqual(horas_hasta_saturar(40, 3, 5).estado, NO_SE_SATURA)
        self.assertEqual(horas_hasta_saturar(40, 5, 5).estado, NO_SE_SATURA)

    def test_tc_1183_08_sin_camas_libres_esta_saturada(self):
        self.assertEqual(horas_hasta_saturar(0, 1, 0).estado, SATURADA)
        self.assertEqual(horas_hasta_saturar(0, 0, 4).estado, SATURADA)


class DemandaEnAlzaTests(SimpleTestCase):
    def test_tc_1183_18_porcentaje_sobre_el_promedio(self):
        alza = demanda_en_alza(96, [70, 68, 71])
        self.assertEqual((alza.alerta, alza.porcentaje), (True, 38))

    def test_tc_1183_19_menos_de_20_no_alerta(self):
        self.assertFalse(demanda_en_alza(19, [5, 5, 5]).alerta)

    def test_tc_1183_20_el_borde_de_1_3_alerta(self):
        self.assertTrue(demanda_en_alza(26, [20, 20, 20]).alerta)
        self.assertFalse(demanda_en_alza(25, [20, 20, 20]).alerta)

    def test_promedio_cero_alerta_sin_porcentaje(self):
        alza = demanda_en_alza(22, [0, 0, 0])
        self.assertEqual((alza.alerta, alza.porcentaje), (True, None))


class PresentarPerfilTests(SimpleTestCase):
    """TC-1183-30: salud solo provincial; no sensibles con «menos de 5» de 1 a 4."""

    PERFIL = {
        "alojados": {
            "personas": 40,
            "menores": 3,
            "mayores": 0,
            "edad_sin_dato": 5,
            "embarazo": 2,
            "discapacidad": 7,
            "electrodependiente": 1,
            "medicacion_critica": 4,
            "sin_dosis": 1,
        },
        "esperando": {
            "personas": 12,
            "familias": 4,
            "menores": 2,
            "mayores": 0,
            "lactantes": 5,
            "dependientes": 1,
            "mayores_dependientes": 1,
            "familias_embarazo": 1,
            "familias_electrodependencia": 1,
            "familias_medicacion_critica": 0,
            "familias_mascotas": 2,
        },
    }

    def test_sin_filtro_todo_exacto_con_porcentaje(self):
        original = json.dumps(self.PERFIL, sort_keys=True)
        presentado = presentar_perfil(self.PERFIL, filtrado=False)
        self.assertTrue(presentado["salud_visible"])
        self.assertEqual(presentado["alojados"]["menores"].texto, "3")
        self.assertEqual(presentado["alojados"]["menores"].porcentaje, 8)
        self.assertEqual(presentado["alojados"]["embarazo"].valor, 2)
        self.assertEqual(presentado["esperando"]["familias_mascotas"].valor, 2)
        self.assertEqual(json.dumps(self.PERFIL, sort_keys=True), original)

    def test_con_filtro_no_hay_salud_y_1_a_4_dice_menos_de_5(self):
        original = json.dumps(self.PERFIL, sort_keys=True)
        presentado = presentar_perfil(self.PERFIL, filtrado=True)
        self.assertFalse(presentado["salud_visible"])
        self.assertEqual(presentado["nota"], SALUD_SOLO_PROVINCIAL)
        for salud in ("embarazo", "discapacidad", "electrodependiente", "medicacion_critica", "sin_dosis"):
            self.assertNotIn(salud, presentado["alojados"])
        for salud in ("dependientes", "mayores_dependientes", "familias_embarazo", "familias_electrodependencia"):
            self.assertNotIn(salud, presentado["esperando"])
        menores = presentado["alojados"]["menores"]
        self.assertEqual((menores.valor, menores.texto, menores.porcentaje), (None, MENOS_DE_5, None))
        self.assertEqual(presentado["alojados"]["mayores"].texto, "0")
        self.assertEqual(presentado["alojados"]["edad_sin_dato"].valor, 5)
        self.assertEqual(presentado["esperando"]["lactantes"].valor, 5)
        self.assertEqual(presentado["esperando"]["familias_mascotas"].texto, MENOS_DE_5)
        # Los totales operativos no se suprimen, y nada lleva porcentaje.
        self.assertEqual(presentado["esperando"]["familias"].valor, 4)
        self.assertTrue(all(c.porcentaje is None for g in ("alojados", "esperando") for c in presentado[g].values()))
        self.assertEqual(json.dumps(self.PERFIL, sort_keys=True), original)


class SinDosisTests(SimpleTestCase):
    def test_solo_con_medicacion_y_dosis_respondida_en_falso(self):
        self.assertTrue(sin_dosis({"medicacion_critica": True, "medicacion_critica_tiene_dosis": False}))
        self.assertFalse(sin_dosis({"medicacion_critica": True, "medicacion_critica_tiene_dosis": True}))
        self.assertFalse(sin_dosis({"medicacion_critica": True}))
        self.assertFalse(sin_dosis({"medicacion_critica": False, "medicacion_critica_tiene_dosis": False}))
        self.assertFalse(sin_dosis(None))


class CamasCercanasTests(SimpleTestCase):
    CENTRO = (-27.45, -58.98)
    #: Grados de latitud por kilómetro (radio de 6371 km).
    GRADO_POR_KM = 1 / 111.195

    def _d(self, pk, libres, *, km_al_norte=None, localidad="", reservado=False):
        latitud = None if km_al_norte is None else self.CENTRO[0] + km_al_norte * self.GRADO_POR_KM
        longitud = None if km_al_norte is None else self.CENTRO[1]
        tipo = SimpleNamespace(ubicacion_reservada=reservado)
        return DispositivoDeLaRed(pk, f"D{pk}", localidad, libres, 0, tipo, Conteo(), latitud, longitud)

    def test_tc_1183_10_el_radio_es_25_km(self):
        red = [self._d(1, 5, km_al_norte=24), self._d(2, 7, km_al_norte=26)]
        cercanas = camas_cercanas(*self.CENTRO, "resistencia", red, frozenset())
        self.assertEqual(cercanas.total, 5)
        self.assertEqual([d.id for _km, d in cercanas.cercanos], [1])

    def test_tc_1183_11_sin_coordenadas_solo_por_un_nombre_unico(self):
        red = [self._d(1, 4, localidad="Las Breñas"), self._d(2, 3, localidad="La Esperanza")]
        ambiguos = frozenset({"la esperanza"})
        self.assertEqual(camas_cercanas(None, None, "las brenas", red, ambiguos).total, 4)
        self.assertEqual(camas_cercanas(None, None, "la esperanza", red, ambiguos).total, 0)

    def test_tc_1183_12_el_reservado_suma_sin_nombrarse(self):
        red = [self._d(1, 2, km_al_norte=1), self._d(2, 6, km_al_norte=2, reservado=True)]
        cercanas = camas_cercanas(*self.CENTRO, "resistencia", red, frozenset())
        self.assertEqual((cercanas.total, cercanas.reservadas), (8, 6))
        self.assertEqual([d.id for _km, d in cercanas.cercanos], [1])

    def test_una_coordenada_fuera_del_chaco_cuenta_como_sin_ubicacion(self):
        tipo = SimpleNamespace(ubicacion_reservada=False)
        lejos = DispositivoDeLaRed(1, "D1", "Resistencia", 3, 0, tipo, Conteo(), 10, 10)
        self.assertEqual(camas_cercanas(*self.CENTRO, "resistencia", [lejos], frozenset()).total, 3)


class PeriodosTests(SimpleTestCase):
    def test_tc_1183_15_bloques_de_6_h_alineados_a_las_06(self):
        periodos = periodos_de_la_ventana(T0, situacion.VENTANA_72H)
        self.assertEqual(len(periodos), 12)
        self.assertEqual({desde.astimezone(ZONA_OPERATIVA).hour for desde, _hasta in periodos}, {0, 6, 12, 18})
        self.assertEqual(periodos[-1], (_hora(6), _hora(12)))
        self.assertEqual(periodos[0][0], _hora(12, dias=3))

    def test_7_dias_operativos(self):
        periodos = periodos_de_la_ventana(T0, situacion.VENTANA_7D)
        self.assertEqual(len(periodos), 7)
        self.assertEqual(periodos[-1], (_hora(6), _hora(6) + timedelta(days=1)))
        self.assertEqual(periodos[0][0], _hora(6, dias=6))

    def test_antes_de_las_06_el_bloque_es_el_de_la_madrugada(self):
        periodos = periodos_de_la_ventana(_hora(5, 59), situacion.VENTANA_72H)
        self.assertEqual(periodos[-1], (_hora(0), _hora(6)))


class OrdenYTopeTests(SimpleTestCase):
    """TC-1183-25 y la decisión del PM sobre el orden (PR #1191)."""

    def test_alta_antes_que_media_red_antes_que_ae5_y_tope_de_6(self):
        def regla(codigo, severidad, n=1):
            return lambda foto: [alertas._alerta(codigo, severidad, f"{codigo} {k}") for k in range(n)]

        reglas = (
            regla("AE-6", "media"),
            regla("AE-5", "alta", 2),
            regla("AE-3", "media"),
            regla("AE-7", "alta"),
            regla("AE-1", "alta"),
            regla("AE-2", "alta"),
            regla("AE-4", "media"),
        )
        with mock.patch.object(alertas, "REGLAS", reglas):
            resultado = alertas.alertas_de_situacion(foto=None)
        self.assertEqual(resultado["total"], 8)
        self.assertEqual(
            [a["titulo"] for a in resultado["alertas"]],
            ["AE-1 0", "AE-2 0", "AE-7 0", "AE-5 0", "AE-5 1", "AE-3 0"],
        )
