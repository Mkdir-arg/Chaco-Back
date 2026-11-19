"""E8 · foto de situación, reglas puras y alertas AE-1 a AE-7 (Cambio 508 · E-4 #1183).

* **Reglas puras** — ``services.situacion_emergencia`` sin base: presión, horas hasta saturar,
  camas cercanas, demanda en alza, ``presentar_perfil`` y los períodos de la ventana.
* **Cada número de la foto** — un escenario con momentos fijos (reloj en ``T0`` = 12/11/2026
  10:00, hora Argentina; día operativo desde las 06:00) contra ``resumen``, ``presion_por_localidad``,
  ``evolucion``, ``capacidad``, ``embudo``, ``perfil``, ``logistica`` y ``puntos_del_mapa``.
* **Cada alerta** — aparece cuando se cumple, no aparece en el borde, y con filtro las provinciales
  dicen «en toda la provincia».
* **Presupuesto** (``--tag performance``) y **SQL sin zona horaria** (``--tag mysql``).

Todas las personas usan DNIs de prueba (90000001–90000099).
"""

import json
import re
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

from django.db import connection
from django.test import SimpleTestCase, tag
from django.test.utils import CaptureQueriesContext

from core.models import Localidad, Municipio, Provincia, UbicacionLocalidad
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntregaKit,
    Estadia,
    GrupoFamiliar,
    IntegranteGrupo,
    LineaEntrega,
    Plaza,
    Sector,
    TipoDispositivo,
    TipoKit,
)
from programas.selectors import emergencia_situacion as situacion
from programas.selectors.emergencia_situacion import FiltrosSituacion, periodos_de_la_ventana
from programas.selectors.emergencia_tablero import ZONA_OPERATIVA, DispositivoDeLaRed
from programas.services import alertas_situacion_emergencia as alertas
from programas.services.emergencia_ficha import sin_dosis
from programas.services.ocupacion import NIVEL_CRITICA, NIVEL_EXIGIDA, NIVEL_NORMAL
from programas.services.situacion_emergencia import (
    MENOS_DE_5,
    NIVEL_SIN_DEMANDA,
    NO_SE_SATURA,
    PROYECCION,
    SALUD_SOLO_PROVINCIAL,
    SATURADA,
    SIN_DATOS,
    camas_cercanas,
    demanda_en_alza,
    horas_hasta_saturar,
    nivel_de_presion,
    presentar_perfil,
)
from programas.tests.test_emergencia_casos import T0
from programas.tests.test_emergencia_tablero import BaseTablero

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen


def _hora(hh, mm=0, dias=0):
    """Un momento del 12/11/2026 (hora Argentina), ``dias`` antes."""
    return T0.replace(hour=hh, minute=mm) - timedelta(days=dias)


# ---------------------------------------------------------------------------
# Reglas puras
# ---------------------------------------------------------------------------


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
        return DispositivoDeLaRed(pk, f"D{pk}", localidad, libres, 0, tipo, latitud, longitud)

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
        lejos = DispositivoDeLaRed(1, "D1", "Resistencia", 3, 0, SimpleNamespace(ubicacion_reservada=False), 10, 10)
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


# ---------------------------------------------------------------------------
# Base de los tests con base de datos
# ---------------------------------------------------------------------------


class BaseSituacion(BaseTablero):
    def setUp(self):
        super().setUp()
        self._dnis = iter(range(90_000_001, 90_000_100))
        self.chaco = Provincia.objects.create(nombre="Chaco")
        self.san_fernando = Municipio.objects.create(nombre="San Fernando", provincia=self.chaco)
        self._ordenes = iter(range(1, 100_000))

    def _loc(self, nombre, latitud=None, longitud=None, departamento="", municipio=None):
        localidad = Localidad.objects.create(nombre=nombre, municipio=municipio or self.san_fernando)
        if latitud is not None:
            UbicacionLocalidad.objects.create(
                localidad=localidad,
                latitud=latitud,
                longitud=longitud,
                departamento=departamento,
                fuente=UbicacionLocalidad.FUENTE_BAHRA_GEOREF,
                id_fuente=f"T{localidad.pk}",
            )
        return localidad

    def _caso(self, estado=Estado.NUEVO, *, grupo=None, necesidades=None, latitud=None, longitud=None, **kwargs):
        caso = self._sembrar(estado, **kwargs)
        if grupo:
            GrupoFamiliar.objects.filter(pk=caso.grupo_id).update(**grupo)
        cambios = {}
        if necesidades:
            cambios["necesidades"] = necesidades
        if latitud is not None:
            cambios.update(latitud=latitud, longitud=longitud)
        if cambios:
            CasoEmergencia.objects.filter(pk=caso.pk).update(**cambios)
        caso.refresh_from_db()
        return caso

    def _lote(self, n, *, estado=Estado.NUEVO, localidad=None, creado=T0, declarado=1, **marcas):
        """``n`` casos iguales con un mismo responsable: un solo DNI para todos."""

        if not hasattr(self, "_responsable"):
            self._responsable = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Rosa", apellido="Lote")
        grupos = GrupoFamiliar.objects.bulk_create(
            [
                GrupoFamiliar(
                    responsable=self._responsable,
                    traslado=GrupoFamiliar.Traslado.BOMBEROS,
                    adultos_f=declarado,
                    total_declarado=declarado,
                )
                for _ in range(n)
            ]
        )
        casos = CasoEmergencia.objects.bulk_create(
            [
                CasoEmergencia(
                    numero=f"2026-L-{next(self._numeros):06d}",
                    grupo=grupo,
                    origen=Origen.TERRITORIO,
                    estado=estado,
                    prioridad=CasoEmergencia.Prioridad.MEDIA,
                    localidad=localidad,
                    direccion="Calle 1",
                    relevado_por=self.agente,
                    relevado_en=creado,
                    **marcas,
                )
                for grupo in grupos
            ]
        )
        CasoEmergencia.objects.filter(pk__in=[caso.pk for caso in casos]).update(creado=creado)
        return casos

    def _alojar(self, caso, dispositivo, personas, *, confirmada_en):
        """Una estadía sin plaza (no toca la ocupación) y un integrante por persona.

        Cada persona: ``{"nacimiento": date, "avisos": {...}, "egresado_en": momento}``.
        """

        responsable = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Estadía")
        estadia = Estadia.objects.create(
            ciudadano=responsable,
            dispositivo=dispositivo,
            fecha_ingreso=confirmada_en,
            clave_alojamiento=Estadia.clave_para(responsable),
        )
        for persona in personas:
            ciudadano = None
            if persona.get("nacimiento"):
                ciudadano = Ciudadano.objects.create(
                    dni=str(next(self._dnis)),
                    nombre="Persona",
                    apellido="Alojada",
                    fecha_nacimiento=persona["nacimiento"],
                )
            IntegranteGrupo.objects.create(
                grupo=caso.grupo,
                orden=next(self._ordenes),
                ciudadano=ciudadano,
                estadia=estadia,
                ficha={"version": 1, "avisos_salud": persona.get("avisos", {})},
                confirmada_en=confirmada_en,
                egresado_en=persona.get("egresado_en"),
            )

    def _foto(self, ahora=T0, **filtros):
        return situacion.foto_de_situacion(self.sla, ahora, FiltrosSituacion(**filtros))

    def _reglas(self, foto):
        return [alerta["regla"] for alerta in alertas.todas_las_alertas(foto)]


# ---------------------------------------------------------------------------
# Cada número de la foto
# ---------------------------------------------------------------------------


class EscenarioSituacion(BaseSituacion):
    """Ver los números esperados en cada test; el escenario está armado a mano para que cuadren."""

    def setUp(self):
        super().setUp()
        breñas = Municipio.objects.create(nombre="Las Breñas", provincia=self.chaco)
        self.res = self._loc("Resistencia", -27.4606, -58.9839, "San Fernando")
        self.bar = self._loc("Barranqueras", -27.4833, -58.9333, "San Fernando")
        self.bre = self._loc("Las Breñas", -27.0895, -61.0811, "Nueve de Julio", municipio=breñas)
        self.esp_norte = self._loc(
            "La Esperanza", municipio=Municipio.objects.create(nombre="Norte", provincia=self.chaco)
        )
        self.esp_sur = self._loc("La Esperanza", municipio=Municipio.objects.create(nombre="Sur", provincia=self.chaco))

        reservado = TipoDispositivo.objects.create(
            codigo="PROT", nombre="Protección", tipos_plaza_admitidos=["CAMA"], ubicacion_reservada=True
        )
        # Umbrales del tipo de fábrica: 50 / 80.
        self.club = self._dispositivo("Club Sarmiento", 10, latitud=-27.46, longitud=-58.98, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", 4, latitud=-27.48, longitud=-58.93, localidad="Barranqueras")
        self.refugio = self._dispositivo(
            "Refugio", 6, latitud=-27.47, longitud=-58.97, tipo=reservado, localidad="Resistencia"
        )
        self.hogar = self._dispositivo("Hogar Breñas", 3, localidad="Las Breñas")
        self.ambiguo = self._dispositivo("Escuela Esperanza", 2, localidad="La Esperanza")
        self._ocupar(self.club, 9)
        self._ocupar(self.escuela, 2)

        # Esperando (20 personas, 7 familias; fuera de SLA: c2, c3 y c11).
        self.c1 = self._caso(
            localidad=self.res,
            creado=_hora(9, 50),
            declarado=4,
            grupo={"menores_f": 1, "menores_m": 1, "lactantes": 1},
            necesidades={"mascotas": True, "embarazo": True},
            latitud=-27.4111,
            longitud=-58.9222,
        )
        self.c2 = self._caso(localidad=self.res, creado=_hora(9, 30), declarado=3)
        self.c3 = self._caso(
            Estado.EN_GESTION,
            localidad=self.bar,
            creado=_hora(8),
            tomado_en=_hora(8, 10),
            declarado=5,
            grupo={"mayores_m": 2, "dependientes": 1, "mayores_dependientes": 1},
            necesidades={"electrodependiente": True},
        )
        self.c4 = self._caso(
            localidad=self.bre, creado=_hora(9, 55), declarado=3, necesidades={"medicacion_critica": True}
        )
        self.c5 = self._caso(localidad=self.esp_norte, creado=_hora(9, 58), declarado=2)
        self.c6 = self._caso(creado=_hora(9, 57), declarado=1)
        self.c11 = self._caso(
            Estado.DERIVADO,
            localidad=self.res,
            creado=_hora(6, 30),
            tomado_en=_hora(6, 35),
            derivado_en=_hora(6, 40),
            declarado=2,
        )
        rechazada = self._derivar(self.c11, self.escuela, _hora(7, 40))
        Derivacion.objects.filter(pk=rechazada.pk).update(
            estado=Derivacion.Estado.RECHAZADA, motivo="Sin plazas", clave_vigente=None
        )
        self._derivar(self.c11, self.club, _hora(11))

        # Alojados: c7 (3 personas en el club) y c8 (2 en la escuela, una ya egresó).
        self.c7 = self._caso(
            Estado.ALOJADO,
            localidad=self.res,
            creado=_hora(7),
            tomado_en=_hora(7, 5),
            derivado_en=_hora(7, 10),
            aceptado_en=_hora(7, 30),
            alojado_en=_hora(8),
            declarado=3,
            alojado=3,
        )
        self._alojar(
            self.c7,
            self.club,
            [
                {"nacimiento": date(2015, 1, 1)},
                {
                    "nacimiento": date(1950, 1, 1),
                    "avisos": {"medicacion_critica": True, "medicacion_critica_tiene_dosis": False},
                },
                {"avisos": {"embarazo": True, "medicacion_critica": True, "medicacion_critica_tiene_dosis": True}},
            ],
            confirmada_en=_hora(8),
        )
        self.c8 = self._caso(
            Estado.ALOJADO,
            localidad=self.bar,
            creado=_hora(5),
            tomado_en=_hora(5, 5),
            derivado_en=_hora(5, 10),
            aceptado_en=_hora(5, 20),
            alojado_en=_hora(5, 30),
            declarado=2,
            alojado=2,
        )
        self._alojar(
            self.c8,
            self.escuela,
            [{"avisos": {"discapacidad": True}}, {"egresado_en": _hora(9)}],
            confirmada_en=_hora(5, 30),
        )
        # Salidas del circuito: un cerrado sin alojar y un ingreso directo.
        self.c9 = self._caso(
            Estado.CERRADO, localidad=self.res, creado=_hora(8, 30), tomado_en=_hora(8, 40), cerrado_en=_hora(9)
        )
        CasoEmergencia.objects.filter(pk=self.c9.pk).update(motivo_cierre=CasoEmergencia.MotivoCierre.NO_REQUIERE)
        self.c10 = self._caso(
            Estado.ALOJADO,
            origen=Origen.DISPOSITIVO,
            localidad=self.res,
            creado=_hora(9),
            tomado_en=_hora(9),
            alojado_en=_hora(9, 5),
            declarado=1,
            alojado=1,
        )
        # Un cerrado fuera de la ventana: no entra en nada.
        self._caso(Estado.CERRADO, localidad=self.res, creado=_hora(9, dias=10), cerrado_en=_hora(9, dias=9))

        # Logística: el club recibió hoy; la escuela, hace 71 h (antes de la ventana).
        recibida = self._entrega(self.club, EntregaKit.Estado.RECIBIDA, despachada_en=_hora(6), recibida_en=_hora(8))
        LineaEntrega.objects.filter(entrega=recibida).update(cantidad_recibida=1)
        self._entrega(self.escuela, EntregaKit.Estado.EN_CAMINO, despachada_en=_hora(9))
        self._entrega(
            self.escuela,
            EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS,
            despachada_en=_hora(10, dias=3),
            recibida_en=_hora(11, dias=3),
        )
        self.foto = self._foto()


class ResumenTests(EscenarioSituacion):
    def test_personas_alojadas_dispositivos_y_variacion_del_dia(self):
        alojadas = situacion.resumen(self.foto)["personas_alojadas"]
        self.assertEqual((alojadas["valor"], alojadas["dispositivos"], alojadas["variacion_del_dia"]), (4, 2, 2))

    def test_personas_esperando_familias_y_fuera_de_sla(self):
        esperando = situacion.resumen(self.foto)["personas_esperando"]
        self.assertEqual((esperando["valor"], esperando["familias"], esperando["fuera_de_sla"]), (20, 7, 3))

    def test_tc_1183_09_camas_libres_solo_camas_con_los_reservados(self):
        Sector.objects.create(dispositivo=self.club, nombre="Cupos", capacidad=20)
        Plaza.objects.bulk_create(
            [Plaza(sector=Sector.objects.get(nombre="Cupos"), codigo=f"U{n}", tipo=Plaza.Tipo.CUPO) for n in range(20)]
        )
        camas = situacion.resumen(self._foto())["camas_libres"]
        self.assertEqual(camas["valor"], 1 + 2 + 6 + 3 + 2)
        self.assertEqual((camas["conteo"].operativas, camas["conteo"].ocupadas), (25, 11))
        self.assertEqual((camas["tension"].porcentaje, camas["tension"].nivel), (44, NIVEL_NORMAL))

    def test_horas_hasta_saturar_con_el_ritmo_de_camas_de_6_h(self):
        self.assertEqual(situacion.resumen(self.foto)["saturacion"].estado, NO_SE_SATURA)
        plazas = list(Plaza.objects.filter(sector__dispositivo=self.hogar).order_by("codigo"))
        for plaza in plazas[:2]:
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Nueva")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.hogar,
                plaza=plaza,
                fecha_ingreso=_hora(7),
                clave_alojamiento=Estadia.clave_para(persona),
            )
        saturacion = situacion.resumen(self._foto())["saturacion"]
        self.assertEqual((saturacion.ingresos, saturacion.egresos), (2, 0))
        # 12 libres, 2 ingresos en 6 h: ≈ 36 h.
        self.assertEqual((saturacion.estado, saturacion.horas), (PROYECCION, 36.0))


class PresionPorLocalidadTests(EscenarioSituacion):
    def _filas(self):
        return {fila["localidad_id"]: fila for fila in situacion.presion_por_localidad(self.foto)}

    def test_tc_1183_01_presion_y_camas_cercanas_por_localidad(self):
        filas = self._filas()
        res = filas[self.res.pk]
        self.assertEqual(
            (res["familias"], res["personas"], res["fuera_de_sla"], res["alojadas"], res["cercanas"].total),
            (3, 9, 2, 3, 9),
        )
        self.assertEqual((res["presion"].nivel, res["presion"].cociente), (NIVEL_EXIGIDA, 1.0))
        self.assertEqual(res["cercanas"].reservadas, 6)
        self.assertEqual([d.id for _km, d in res["cercanas"].cercanos], [self.club.pk, self.escuela.pk])
        self.assertEqual(filas[self.bar.pk]["alojadas"], 1)

    def test_tc_1183_11_el_nombre_unico_suma_y_el_ambiguo_no(self):
        filas = self._filas()
        self.assertEqual(filas[self.bre.pk]["cercanas"].total, 3)
        esperanza = filas[self.esp_norte.pk]
        self.assertEqual(esperanza["cercanas"].total, 0)
        self.assertTrue(esperanza["presion"].sin_camas_cercanas)

    def test_orden_y_fila_sin_localidad(self):
        orden = [fila["localidad_id"] for fila in situacion.presion_por_localidad(self.foto)]
        self.assertEqual(orden, [self.esp_norte.pk, self.res.pk, self.bre.pk, self.bar.pk, None])
        sin_localidad = self._filas()[None]
        self.assertEqual(
            (sin_localidad["localidad"], sin_localidad["personas"], sin_localidad["presion"]),
            ("Sin localidad", 1, None),
        )


class EvolucionTests(EscenarioSituacion):
    def test_bloques_de_la_ventana_de_72_h(self):
        periodos = situacion.evolucion(self.foto)["periodos"]
        actual, madrugada = periodos[-1], periodos[-2]
        self.assertEqual(
            (actual["casos_nuevos"], actual["familias_alojadas"], actual["cerrados_sin_alojar"]), (10, 2, 1)
        )
        self.assertEqual((actual["personas_alojadas_al_cierre"], madrugada["personas_alojadas_al_cierre"]), (4, 2))
        self.assertEqual((madrugada["casos_nuevos"], madrugada["familias_alojadas"]), (1, 1))
        self.assertTrue(actual["en_curso"])
        self.assertEqual(situacion.evolucion(self.foto)["camas_operativas_hoy"], 25)

    def test_tc_1183_14_el_dia_operativo_corta_a_las_06(self):
        dias = situacion.evolucion(self._foto(ventana=situacion.VENTANA_7D))["periodos"]
        # c8 se creó a las 05:00 del 12/11: es del día operativo del 11/11.
        self.assertEqual((dias[-2]["casos_nuevos"], dias[-1]["casos_nuevos"]), (1, 10))


class CapacidadTests(EscenarioSituacion):
    def test_mas_tensionados_por_exceso_sobre_el_umbral_de_su_tipo_y_sin_reservados(self):
        capacidad = situacion.capacidad(self.foto)
        nombres = [fila.dispositivo.nombre for fila in capacidad["mas_tensionados"]]
        self.assertEqual(nombres, ["Club Sarmiento", "Escuela 12", "Escuela Esperanza", "Hogar Breñas"])
        club = capacidad["mas_tensionados"][0]
        self.assertEqual(
            (club.tension.porcentaje, club.tension.nivel, club.derivaciones_pendientes), (90, NIVEL_CRITICA, 1)
        )
        self.assertEqual((capacidad["sin_ubicacion"], capacidad["dispositivos"]), (2, 5))

    def test_tc_1183_13_el_nivel_del_dispositivo_es_el_de_su_tipo(self):
        self.tipo.umbral_ocupacion_rojo = 95
        self.tipo.save()
        club = situacion.capacidad(self._foto())["mas_tensionados"][0]
        self.assertEqual((club.dispositivo.nombre, club.tension.nivel), ("Club Sarmiento", NIVEL_EXIGIDA))


class EmbudoTests(EscenarioSituacion):
    def test_tc_1183_31_cohorte_sin_ingresos_directos(self):
        embudo = situacion.embudo(self.foto)
        self.assertEqual([paso["casos"] for paso in embudo["pasos"]], [10, 5, 3, 2, 2])
        self.assertEqual([paso["conversion"] for paso in embudo["pasos"]], [None, 50, 60, 67, 100])
        self.assertEqual(embudo["ingresos_directos"], 1)
        self.assertEqual(embudo["cerrados_sin_alojar"], {"total": 1, "por_motivo": {"No requiere alojamiento": 1}})

    def test_tc_1183_32_derivado_rechazado_y_vuelto_a_derivar(self):
        embudo = situacion.embudo(self.foto)
        self.assertEqual(embudo["pasos"][2]["casos"], 3)
        self.assertEqual(embudo["rechazadas"], {"total": 1, "por_motivo": {"Sin plazas": 1}})
        self.assertEqual(embudo["vencidas"], 0)

    def test_mediana_y_p90_de_los_tramos_de_la_cohorte(self):
        tramos = {tramo["tramo"]: tramo for tramo in situacion.embudo(self.foto)["tramos"]}
        # Tomar: c3 10, c7 5, c8 5, c9 10, c11 5 minutos.
        self.assertEqual(
            (tramos["tomar"]["casos"], tramos["tomar"]["mediana_min"], tramos["tomar"]["p90_min"]), (5, 5, 10)
        )
        self.assertEqual(tramos["tomar"]["objetivo_min"], self.sla.objetivo_tomar_min)


class PerfilTests(EscenarioSituacion):
    def test_tc_1183_27_alojados_y_esperando_exactos(self):
        perfil = situacion.perfil(self.foto)
        self.assertEqual(
            perfil["alojados"],
            {
                "personas": 4,
                "menores": 1,
                "mayores": 1,
                "edad_sin_dato": 2,
                "embarazo": 1,
                "discapacidad": 1,
                "electrodependiente": 0,
                "medicacion_critica": 2,
                "sin_dosis": 1,
            },
        )
        self.assertEqual(
            perfil["esperando"],
            {
                "personas": 20,
                "familias": 7,
                "menores": 2,
                "mayores": 2,
                "lactantes": 1,
                "dependientes": 1,
                "mayores_dependientes": 1,
                "familias_embarazo": 1,
                "familias_electrodependencia": 1,
                "familias_medicacion_critica": 1,
                "familias_mascotas": 1,
            },
        )

    def test_tc_1183_26_con_filtro_el_perfil_presentado_no_trae_salud(self):
        for filtros in ({"localidad_id": self.res.pk}, {"departamento": "San Fernando"}):
            foto = self._foto(**filtros)
            presentado = presentar_perfil(situacion.perfil(foto), foto.filtrado)
            self.assertNotIn("sin_dosis", presentado["alojados"])
            self.assertNotIn("dependientes", presentado["esperando"])
            self.assertEqual(presentado["nota"], SALUD_SOLO_PROVINCIAL)


class LogisticaTests(EscenarioSituacion):
    def test_entregas_de_la_ventana_e_items(self):
        logistica = situacion.logistica(self.foto)
        self.assertEqual(
            (logistica["despachadas"], logistica["recibidas"], logistica["con_diferencias"], logistica["en_camino"]),
            (2, 1, 0, 1),
        )
        self.assertEqual(logistica["transito_mediano_min"], 120)
        (item,) = logistica["por_item"]
        self.assertEqual((item.item, item.enviado, item.recibido, item.diferencia), ("Ítem 0", 1, 1, 0))

    def test_sin_entrega_en_48_h(self):
        (fila,) = situacion.logistica(self.foto)["sin_entrega_48h"]
        self.assertEqual((fila["nombre"], fila["personas"], fila["horas"]), ("Escuela 12", 1, 71))


class FiltroTests(EscenarioSituacion):
    def test_el_departamento_acota_la_demanda_y_no_la_capacidad(self):
        foto = self._foto(departamento="San Fernando")
        resumen = situacion.resumen(foto)
        self.assertEqual((resumen["personas_esperando"]["valor"], resumen["personas_esperando"]["familias"]), (14, 4))
        self.assertEqual(resumen["personas_alojadas"]["valor"], 4)
        self.assertEqual(resumen["camas_libres"]["valor"], 14)
        self.assertEqual(
            {fila["localidad_id"] for fila in situacion.presion_por_localidad(foto)}, {self.res.pk, self.bar.pk}
        )

    def test_una_localidad_fuera_del_departamento_se_ignora_y_se_avisa(self):
        foto = self._foto(departamento="Nueve de Julio", localidad_id=self.res.pk)
        self.assertTrue(foto.localidad_ignorada)
        self.assertEqual(foto.localidades_del_filtro, frozenset({self.bre.pk}))

    def test_el_filtro_no_agrega_consultas(self):
        with CaptureQueriesContext(connection) as sin_filtro:
            self._foto()
        with CaptureQueriesContext(connection) as con_filtro:
            self._foto(departamento="San Fernando")
        self.assertEqual(len(con_filtro), len(sin_filtro))


class PuntosDelMapaTests(EscenarioSituacion):
    def test_tc_1183_33_sin_reservados_ni_coordenadas_de_casos(self):
        puntos = situacion.puntos_del_mapa(self.foto)
        self.assertNotIn(self.refugio.pk, [d["id"] for d in puntos["dispositivos"]])
        self.assertEqual([d["id"] for d in puntos["dispositivos"]], [self.club.pk, self.escuela.pk])
        self.assertEqual(
            {loc["localidad_id"] for loc in puntos["localidades"]}, {self.res.pk, self.bar.pk, self.bre.pk}
        )
        crudo = json.dumps(puntos)
        self.assertNotIn("-27.4111", crudo)
        self.assertNotIn("-58.9222", crudo)
        self.assertNotIn("-58.97", crudo)
        self.assertEqual(
            (puntos["dispositivos_sin_ubicacion"], puntos["dispositivos_reservados"], puntos["casos_sin_ubicacion"]),
            (2, 1, 2),
        )


class AlertasDelEscenarioTests(EscenarioSituacion):
    def test_las_alertas_vigentes_y_su_orden(self):
        self.assertEqual(self._reglas(self.foto), ["AE-7", "AE-5", "AE-6"])
        (ae5,) = [a for a in alertas.todas_las_alertas(self.foto) if a["regla"] == "AE-5"]
        self.assertEqual(
            ae5["titulo"], "Club Sarmiento (Resistencia) está en nivel Crítica (90 %) y tiene 1 derivación pendiente"
        )
        self.assertEqual((ae5["tono"], ae5["icono"]), ("danger", "triangle-exclamation"))

    def test_tc_1183_29_y_37_con_filtro_las_provinciales_no_cambian_y_lo_dicen(self):
        sin_filtro = {a["regla"]: a for a in alertas.todas_las_alertas(self.foto)}
        con_filtro = {a["regla"]: a for a in alertas.todas_las_alertas(self._foto(localidad_id=self.bre.pk))}
        self.assertEqual(set(con_filtro), {"AE-7", "AE-5", "AE-6"})
        for regla in ("AE-7", "AE-5", "AE-6"):
            self.assertEqual(con_filtro[regla]["titulo"], f"{sin_filtro[regla]['titulo']}, en toda la provincia")
        self.assertTrue(con_filtro["AE-7"]["titulo"].startswith("1 persona alojada"))


# ---------------------------------------------------------------------------
# Cada alerta, en su borde
# ---------------------------------------------------------------------------


class AE1Tests(BaseSituacion):
    def _ingresos(self, dispositivo, cuantos):
        for plaza in Plaza.objects.filter(sector__dispositivo=dispositivo).order_by("codigo")[:cuantos]:
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Nueva")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=dispositivo,
                plaza=plaza,
                fecha_ingreso=_hora(8),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_tc_1183_16_proyeccion_bajo_12_h_alerta_y_desde_12_h_no(self):
        self._caso(creado=_hora(9))
        club = self._dispositivo("Club", 30)
        self._ingresos(club, 12)  # 18 libres, 2 camas/h: 9 h
        (ae1,) = alertas.saturacion_de_la_red(self._foto())
        self.assertEqual(ae1["titulo"], "La red se satura en ≈ 9 h al ritmo actual")
        self.assertEqual(
            ae1["texto"], "En las últimas 6 h ingresaron 12 personas y egresaron 0. Quedan 18 camas libres."
        )
        self._dispositivo("Otro", 6)  # 24 libres: 12 h justas, ya no alerta
        self.assertEqual(alertas.saturacion_de_la_red(self._foto()), [])

    def test_tc_1183_08_red_en_nivel_critica_o_saturada(self):
        self._caso(creado=_hora(9))
        club = self._dispositivo("Club", 10)
        self._ocupar(club, 8)
        (ae1,) = alertas.saturacion_de_la_red(self._foto())
        self.assertEqual(ae1["titulo"], "La red está en nivel Crítica (80 % de ocupación)")
        self._dispositivo("Vacío")
        Dispositivo.objects.filter(pk=club.pk).update(estado=Dispositivo.Estado.INACTIVO)
        (ae1,) = alertas.saturacion_de_la_red(self._foto())
        self.assertEqual(ae1["titulo"], "La red está saturada: no quedan camas libres")

    def test_tc_1183_36_sin_casos_no_hay_proyeccion_ni_alerta(self):
        self._dispositivo("Club", 10)
        foto = self._foto()
        self.assertEqual(situacion.resumen(foto)["saturacion"].estado, SIN_DATOS)
        self.assertEqual(situacion.resumen(foto)["personas_esperando"]["valor"], 0)
        self.assertEqual(alertas.todas_las_alertas(foto), [])
        self.assertFalse(situacion.embudo(foto)["hay_casos"])


class AE2Tests(BaseSituacion):
    def test_tc_1183_17_cuenta_las_criticas_con_10_o_mas_y_nombra_3(self):
        for nombre, personas in (("Alfa", 133), ("Beta", 26), ("Gama", 104), ("Delta", 52), ("Eta", 7), ("Iota", 3)):
            self._caso(localidad=self._loc(nombre), creado=_hora(9), declarado=personas)
        (ae2,) = alertas.localidades_criticas(self._foto())
        self.assertEqual(ae2["titulo"], "Presión crítica en 4 localidades: Alfa, Gama y Delta, y 1 más")
        self.assertEqual(ae2["texto"], "Alfa: 133 personas esperan y no hay camas libres a menos de 25 km.")

    def test_9_personas_no_alcanzan(self):
        self._caso(localidad=self._loc("Alfa"), creado=_hora(9), declarado=9)
        self.assertEqual(alertas.localidades_criticas(self._foto()), [])


class AE3Tests(BaseSituacion):
    def _historia(self, actual, anteriores, localidad=None):
        self._lote(actual, localidad=localidad, creado=_hora(9))
        for n, cantidad in enumerate(anteriores, start=1):
            self._lote(cantidad, localidad=localidad, creado=_hora(9, dias=n))

    def test_tc_1183_20_26_contra_20_alerta_y_25_no(self):
        self._historia(26, (20, 20, 20))
        (ae3,) = alertas.demanda_creciente(self._foto())
        self.assertEqual(
            ae3["texto"], "26 casos nuevos en las últimas 24 h, 30 % más que el promedio de las tres 24 h anteriores."
        )
        CasoEmergencia.objects.filter(pk=CasoEmergencia.objects.filter(creado=_hora(9)).first().pk).update(
            creado=_hora(9, dias=5)
        )
        self.assertEqual(alertas.demanda_creciente(self._foto()), [])

    def test_sin_casos_en_las_72_h_anteriores_el_texto_no_tiene_porcentaje(self):
        self._historia(22, (0, 0, 0))
        (ae3,) = alertas.demanda_creciente(self._foto())
        self.assertEqual(ae3["texto"], "22 casos nuevos en las últimas 24 h; en las 72 h anteriores no hubo.")

    def test_tc_1183_37_con_filtro_cuenta_la_demanda_de_la_localidad(self):
        alfa = self._loc("Alfa")
        self._historia(25, (15, 15, 15), localidad=alfa)
        self._historia(0, (40, 40, 40))
        self.assertNotIn("AE-3", self._reglas(self._foto()))
        self.assertIn("AE-3", self._reglas(self._foto(localidad_id=alfa.pk)))


class AE4Tests(BaseSituacion):
    def _aceptados(self, n, minutos, localidad=None):
        """``n`` casos alojados hoy cuyo tramo «aceptar» duró ``minutos``; los otros tramos, cortos."""

        aceptado = _hora(1, 10) + timedelta(minutes=minutos)
        self._lote(
            n,
            estado=Estado.ALOJADO,
            localidad=localidad,
            creado=_hora(1),
            tomado_en=_hora(1),
            derivado_en=_hora(1, 10),
            aceptado_en=aceptado,
            alojado_en=aceptado + timedelta(minutes=30),
        )

    def test_tc_1183_21_p90_por_encima_del_doble_del_objetivo(self):
        self._aceptados(20, 250)
        (ae4,) = alertas.tramos_trabados(self._foto())
        self.assertEqual(ae4["titulo"], "El tramo «aceptar» está trabado")

    def test_tc_1183_21_p90_igual_al_doble_no_alerta(self):
        self._aceptados(20, 2 * self.sla.objetivo_aceptar_min)
        self.assertEqual(alertas.tramos_trabados(self._foto()), [])

    def test_tc_1183_38_con_menos_de_20_casos_no_alerta_con_y_sin_filtro(self):
        alfa = self._loc("Alfa")
        self._aceptados(2, 300, localidad=alfa)
        self._aceptados(17, 60)
        self.assertEqual(alertas.tramos_trabados(self._foto()), [])
        self.assertEqual(alertas.tramos_trabados(self._foto(localidad_id=alfa.pk)), [])
        self._aceptados(18, 300, localidad=alfa)
        self.assertEqual(len(alertas.tramos_trabados(self._foto(localidad_id=alfa.pk))), 1)


class AE5Tests(BaseSituacion):
    def test_tc_1183_22_una_por_dispositivo_ordenadas_y_sin_reservados(self):
        reservado = TipoDispositivo.objects.create(
            codigo="PROT", nombre="Protección", tipos_plaza_admitidos=["CAMA"], ubicacion_reservada=True
        )
        sarmiento = self._dispositivo("Club Atlético Sarmiento", 10, localidad="Resistencia")
        ees = self._dispositivo("EES N.° 9", 10, localidad="Barranqueras")
        polideportivo = self._dispositivo("Polideportivo Municipal", 10, localidad="Fontana")
        refugio = self._dispositivo("Refugio", 10, tipo=reservado, localidad="Resistencia")
        for dispositivo, ocupadas in ((sarmiento, 10), (ees, 9), (polideportivo, 9), (refugio, 10)):
            self._ocupar(dispositivo, ocupadas)
        for dispositivo, pendientes in ((sarmiento, 2), (ees, 1), (refugio, 1)):
            for _ in range(pendientes):
                self._derivar(self._caso(Estado.DERIVADO, creado=_hora(9)), dispositivo, _hora(11))
        titulos = [a["titulo"] for a in alertas.dispositivos_criticos_con_pendientes(self._foto())]
        self.assertEqual(
            titulos,
            [
                "Club Atlético Sarmiento (Resistencia) está lleno y tiene 2 derivaciones pendientes",
                "EES N.° 9 (Barranqueras) está en nivel Crítica (90 %) y tiene 1 derivación pendiente",
            ],
        )


class AE6Tests(BaseSituacion):
    def test_tc_1183_23_con_gente_y_sin_entrega_recibida_en_48_h(self):
        caso = self._caso(Estado.ALOJADO, creado=_hora(1), alojado_en=_hora(2), alojado=1)
        for nombre, horas in (("Escuela 1031", 61), ("Salón Parroquial", None), ("Gimnasio", 52), ("Club", 47)):
            dispositivo = self._dispositivo(nombre)
            self._alojar(caso, dispositivo, [{}], confirmada_en=_hora(2))
            if horas is not None:
                self._entrega(
                    dispositivo,
                    EntregaKit.Estado.RECIBIDA,
                    despachada_en=T0 - timedelta(hours=horas + 1),
                    recibida_en=T0 - timedelta(hours=horas),
                )
        self._dispositivo("Sin gente")
        foto = self._foto()
        filas = situacion.sin_entrega_reciente(foto)
        self.assertEqual(
            [(f["nombre"], f["horas"]) for f in filas],
            [("Salón Parroquial", None), ("Escuela 1031", 61), ("Gimnasio", 52)],
        )
        (ae6,) = alertas.dispositivos_sin_entrega(foto)
        self.assertEqual(ae6["titulo"], "3 dispositivos con gente no recibieron ninguna entrega en las últimas 48 h")
        self.assertEqual(ae6["severidad"], "media")


class AE7Tests(BaseSituacion):
    def test_tc_1183_24_el_numero_sin_nombres_y_nada_con_cero(self):
        caso = self._caso(Estado.ALOJADO, creado=_hora(1), alojado_en=_hora(2), alojado=3)
        club = self._dispositivo("Club")
        sin = {"medicacion_critica": True, "medicacion_critica_tiene_dosis": False}
        self._alojar(
            caso,
            club,
            [{"avisos": sin}, {"avisos": sin}, {"avisos": {"medicacion_critica": True}}],
            confirmada_en=_hora(2),
        )
        (ae7,) = alertas.medicacion_sin_dosis(self._foto())
        self.assertEqual(ae7["titulo"], "2 personas alojadas con medicación crítica no tienen dosis")
        self.assertEqual(ae7["severidad"], "alta")
        IntegranteGrupo.objects.update(ficha={"version": 1, "avisos_salud": {}})
        self.assertEqual(alertas.medicacion_sin_dosis(self._foto()), [])


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


# ---------------------------------------------------------------------------
# Presupuesto y SQL
# ---------------------------------------------------------------------------


#: La foto en consultas fijas (RNF-009-03 pide ≤ 15 para selectores y alertas).
PRESUPUESTO_FOTO = 12


@tag("performance")
class PresupuestoSituacionTests(BaseSituacion):
    """TC-1183-34: 5.000 casos, 3.000 alojados, 50 dispositivos y 500 entregas."""

    CASOS = 5000
    ALOJADOS = 3000
    DISPOSITIVOS = 50
    ENTREGAS = 500

    def setUp(self):
        super().setUp()
        localidades = [
            self._loc(f"Localidad {n}", -27.0 - n / 10, -59.0, "San Fernando" if n % 2 else "Otro") for n in range(10)
        ]
        dispositivos = Dispositivo.objects.bulk_create(
            [
                Dispositivo(
                    tipo=self.tipo,
                    codigo=f"P-{n:03d}",
                    nombre=f"Dispositivo {n}",
                    estado=Dispositivo.Estado.ACTIVO,
                    localidad=f"Localidad {n % 10}",
                    latitud=-27.0 - n / 100 if n % 5 else None,
                    longitud=-59.0 if n % 5 else None,
                )
                for n in range(self.DISPOSITIVOS)
            ]
        )
        sectores = Sector.objects.bulk_create(
            [Sector(dispositivo=d, nombre="General", capacidad=10) for d in dispositivos]
        )
        Plaza.objects.bulk_create([Plaza(sector=s, codigo=f"C{n:03d}") for s in sectores for n in range(10)])
        estados = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.ALOJADO, Estado.CERRADO)
        for n, estado in enumerate(estados):
            marcas = {"tomado_en": _hora(6)} if estado != Estado.NUEVO else {}
            if estado == Estado.CERRADO:
                marcas["cerrado_en"] = _hora(8)
            if estado == Estado.ALOJADO:
                marcas.update(derivado_en=_hora(6), aceptado_en=_hora(7), alojado_en=_hora(8))
            for k, localidad in enumerate(localidades):
                self._lote(
                    self.CASOS // len(estados) // len(localidades),
                    estado=estado,
                    localidad=localidad,
                    creado=_hora(5) - timedelta(hours=k + n),
                    **marcas,
                )
        alojados = list(CasoEmergencia.objects.filter(estado=Estado.ALOJADO).select_related("grupo"))
        derivados = CasoEmergencia.objects.filter(estado=Estado.DERIVADO)[: self.DISPOSITIVOS]
        Derivacion.objects.bulk_create(
            [
                Derivacion(
                    caso=caso,
                    dispositivo=dispositivos[n],
                    plazas_pedidas=1,
                    vence_en=_hora(11),
                    derivada_por=self.operador,
                    clave_vigente=caso.pk,
                )
                for n, caso in enumerate(derivados)
            ]
        )
        responsables = [
            Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="R", apellido="E") for _ in dispositivos
        ]
        estadias = Estadia.objects.bulk_create(
            [
                Estadia(
                    ciudadano=persona,
                    dispositivo=d,
                    fecha_ingreso=_hora(7),
                    clave_alojamiento=Estadia.clave_para(persona),
                )
                for persona, d in zip(responsables, dispositivos)
            ]
        )
        sin = {"medicacion_critica": True, "medicacion_critica_tiene_dosis": False}
        IntegranteGrupo.objects.bulk_create(
            [
                IntegranteGrupo(
                    grupo=alojados[n % len(alojados)].grupo,
                    orden=n,
                    estadia=estadias[n % len(estadias)],
                    ficha={"version": 1, "avisos_salud": sin if n % 7 == 0 else {}},
                    confirmada_en=_hora(8),
                )
                for n in range(self.ALOJADOS)
            ]
        )
        item, _creado = TipoKit.objects.get_or_create(nombre="Kit", defaults={"unidad": "kit"})
        entregas = EntregaKit.objects.bulk_create(
            [
                EntregaKit(
                    numero=f"2026-K-{n + 1:06d}",
                    dispositivo=dispositivos[n % self.DISPOSITIVOS],
                    estado=EntregaKit.Estado.EN_CAMINO if n % 2 else EntregaKit.Estado.RECIBIDA,
                    armada_por=self.operador,
                    despachada_en=T0 - timedelta(minutes=10 * n),
                    recibida_en=None if n % 2 else T0 - timedelta(minutes=10 * n - 5),
                )
                for n in range(self.ENTREGAS)
            ]
        )
        LineaEntrega.objects.bulk_create(
            [
                LineaEntrega(entrega=e, item=item, unidad="kit", cantidad_enviada=5, cantidad_recibida=5)
                for e in entregas
            ]
        )

    def _medir(self, **filtros):
        with CaptureQueriesContext(connection) as capturadas:
            foto = self._foto(**filtros)
            for derivado in (
                situacion.resumen,
                situacion.presion_por_localidad,
                situacion.evolucion,
                situacion.capacidad,
                situacion.embudo,
                situacion.perfil,
                situacion.logistica,
                situacion.puntos_del_mapa,
            ):
                derivado(foto)
            resultado = alertas.alertas_de_situacion(foto)
        return foto, resultado, capturadas

    def test_tc_1183_34_foto_derivados_y_alertas_en_consultas_fijas(self):
        foto, resultado, capturadas = self._medir()
        self.assertEqual(len(capturadas), PRESUPUESTO_FOTO, [q["sql"][:120] for q in capturadas.captured_queries])
        self.assertLessEqual(len(capturadas), 15)
        self.assertEqual(len(foto.casos), self.CASOS)
        self.assertEqual(len(foto.alojados_ahora), self.ALOJADOS)
        self.assertIn("AE-7", [a["regla"] for a in alertas.todas_las_alertas(foto)])
        self.assertGreaterEqual(resultado["total"], 1)

    def test_con_filtro_de_departamento_las_mismas_consultas(self):
        _foto, _resultado, capturadas = self._medir(departamento="San Fernando")
        self.assertEqual(len(capturadas), PRESUPUESTO_FOTO)


#: Lo que no puede aparecer en el SQL de E8 (RNF-009-05): la base de ECOM no tiene tablas de zona horaria.
SQL_PROHIBIDO = re.compile(r"convert_tz|trunc|cast\([^)]*\bas\s+date\b", re.IGNORECASE)


@tag("mysql")
class SinZonaHorariaEnLaBaseTests(EscenarioSituacion):
    """TC-1183-35. En SQLite esas funciones no aparecen: el que vale es el job de motor real."""

    def test_el_sql_de_la_foto_y_la_evolucion_no_usa_zona_horaria(self):
        with CaptureQueriesContext(connection) as capturadas:
            for ventana in (situacion.VENTANA_72H, situacion.VENTANA_7D):
                foto = self._foto(ventana=ventana)
                situacion.evolucion(foto)
                alertas.todas_las_alertas(foto)
        sql = [consulta["sql"] for consulta in capturadas.captured_queries]
        self.assertTrue(sql)
        self.assertEqual([s for s in sql if SQL_PROHIBIDO.search(s)], [])

    def test_la_seccion_avisos_salud_se_lee_igual_en_cada_motor(self):
        """RNF-009-06: la transformación de clave ``ficha__avisos_salud`` en MySQL y MariaDB."""

        perfil = situacion.perfil(self.foto)["alojados"]
        self.assertEqual((perfil["sin_dosis"], perfil["embarazo"], perfil["discapacidad"]), (1, 1, 1))
