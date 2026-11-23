"""E8 · solapa «Abastecimiento» (Cambio 510 · E-7b #1187, análisis 009 §3.9, RN-009-15 a 22).

* **Reglas puras** (``services.abastecimiento_emergencia``): un test por fórmula (RN-009-16 a 20),
  la cobertura, la urgencia y el orden, y ``presentar_salud`` (RN-009-21).
* **Lecturas y armado** sobre un escenario con números hechos a mano (TC-1187-06 a 27, 36, 38).
* **La vista**: solo con ``?tab=abastecimiento``; sin inicio del evento, sin reglas, sin alojados;
  permisos de «Preparar entrega» y de los nombres de la salud; ubicación reservada; rótulos.
* **Presupuesto** (``--tag performance``, TC-1187-41): ≤ 5 consultas de la solapa y ≤ 26 la vista,
  con un evento anterior sembrado que no cambia ni las consultas ni los resultados.

Todas las personas usan DNIs de prueba (90000001–90000099).
"""

import json
import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal

from django.db import connection, reset_queries
from django.test import SimpleTestCase, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Dispositivo,
    EntregaKit,
    Estadia,
    IntegranteGrupo,
    LineaEntrega,
    SLAEmergencia,
    TipoDispositivo,
    TipoKit,
)
from programas.selectors.emergencia_abastecimiento import (
    ItemDelCatalogo,
    PersonaDelAbastecimiento,
    lecturas_de_abastecimiento,
    lecturas_de_un_dispositivo,
)
from programas.services import abastecimiento_emergencia as reglas
from programas.services import alertas_situacion_emergencia as alertas
from programas.services.abastecimiento_emergencia import (
    CUBRE,
    RESERVADO,
    SIN_CONSUMO,
    SIN_CUBRIR,
    DispositivoDelAbastecimiento,
    Salud,
    Unidades,
    armar_abastecimiento,
    faltantes_de_un_dispositivo,
    presentar_salud,
)
from programas.services.ocupacion import NIVEL_CRITICA, NIVEL_EXIGIDA
from programas.services.situacion_emergencia import sin_dosis_provincial, sin_entrega_reciente
from programas.tests.test_emergencia_base import OPERAR
from programas.tests.test_emergencia_casos import T0
from programas.tests.test_emergencia_situacion import BancoSituacion, BaseSituacion
from programas.tests.test_emergencia_situacion_vista import PRESUPUESTOS, URL, VER_SITUACION

Estado = CasoEmergencia.Estado
EstEntrega = EntregaKit.Estado
Modo = TipoKit.ModoRegla
Por = TipoKit.PorRegla
INICIO = T0 - timedelta(days=2)
SIN_DOSIS = {"medicacion_critica": True, "medicacion_critica_tiene_dosis": False}


def _persona(dispositivo, ingreso, *, egresado=None, orden=1, grupo=1, lactantes=0):
    return PersonaDelAbastecimiento(dispositivo, ingreso, egresado, orden, grupo, lactantes)


def _item(modo, cantidad, por, cada_dias=None, nombre="Ítem", pk=1):
    return ItemDelCatalogo(pk, nombre, "unidad", modo, Decimal(str(cantidad)), por, cada_dias)


# ---------------------------------------------------------------------------
# Reglas puras: un test por fórmula
# ---------------------------------------------------------------------------


class UnidadesTests(SimpleTestCase):
    def test_rn_009_16_personas_familias_y_lactantes_de_hoy(self):
        """Una familia repartida cuenta entera (con sus lactantes) en el dispositivo del integrante de menor orden."""
        personas = [
            _persona(1, INICIO, orden=2, grupo=10, lactantes=2),
            _persona(2, INICIO, orden=1, grupo=10, lactantes=2),
            _persona(2, INICIO, orden=3, grupo=10, lactantes=2),
            _persona(1, INICIO, orden=1, grupo=11),
            _persona(1, INICIO, orden=4, grupo=12, egresado=T0 - timedelta(hours=1)),
        ]
        self.assertEqual(
            reglas.unidades_de_hoy(personas),
            {1: Unidades(personas=2, familias=1, lactantes=0), 2: Unidades(personas=2, familias=1, lactantes=2)},
        )

    def test_el_principal_es_el_de_menor_orden_entre_los_alojados(self):
        personas = [
            _persona(1, INICIO, orden=1, grupo=10, egresado=T0 - timedelta(hours=1)),
            _persona(2, INICIO, orden=2, grupo=10),
        ]
        self.assertEqual(reglas.principales(personas), {10: 2})

    def test_persona_dias_reales_recortados_a_la_primera_recepcion(self):
        """TC-1187-09: 20 personas desde hace 2 días y 20 desde hace 1 → 60 persona-días."""
        personas = [_persona(1, T0 - timedelta(days=2), grupo=n) for n in range(20)]
        personas += [_persona(1, T0 - timedelta(days=1), grupo=100 + n) for n in range(20)]
        personas.append(_persona(1, T0 - timedelta(days=9), egresado=T0 - timedelta(days=3), grupo=999))
        tramos = reglas.presencias(personas, T0)[1][Por.PERSONA]
        self.assertAlmostEqual(reglas.unidades_dia(tramos, T0 - timedelta(days=2), T0), 60)


class FormulasTests(SimpleTestCase):
    def test_rn_009_17_dotacion(self):
        """TC-1187-07: 120 personas, 1 por persona, 102 recibidos → 18; con 10 en camino faltan 8."""
        necesario = reglas.redondear_hacia_arriba(reglas.necesario_dotacion(120, Decimal("1"), 102))
        self.assertEqual(necesario, 18)
        self.assertEqual(reglas.faltan(necesario, 10, 0), 8)

    def test_rn_009_17_la_dotacion_no_se_vuelve_negativa(self):
        """TC-1187-23."""
        self.assertEqual(reglas.necesario_dotacion(20, Decimal("1"), 30), 0)

    def test_rn_009_17_reposicion_consumo_remanente_y_necesario(self):
        """TC-1187-08: agua 0,5 por persona por día, 40 personas desde hace 2 días, 60 bidones hace 2 días."""
        diario = reglas.consumo_diario(40, Decimal("0.5"), 1)
        resto = reglas.remanente(60, Decimal("0.5"), 1, 80)
        self.assertEqual((diario, resto), (20, 20))
        self.assertEqual(reglas.redondear_hacia_arriba(reglas.necesario_reposicion(diario, resto)), 20)
        cobertura = reglas.cobertura(resto, diario, T0)
        self.assertEqual((cobertura.estado, cobertura.horas, cobertura.hasta), (CUBRE, 24, T0 + timedelta(hours=24)))

    def test_rn_009_17_persona_dias_reales_bajan_el_consumo(self):
        """TC-1187-09: con 60 persona-días el consumo es 30 → necesario 10, cubre ≈ 36 h."""
        resto = reglas.remanente(60, Decimal("0.5"), 1, 60)
        self.assertEqual(reglas.necesario_reposicion(20, resto), 10)
        self.assertEqual(reglas.cobertura(resto, 20, T0).horas, 36)

    def test_rn_009_17_redondeo_hacia_arriba(self):
        """TC-1187-20: 4 familias, 1 por familia cada 3 días → 2,67 → 3."""
        diario = reglas.consumo_diario(4, Decimal("1"), 3)
        self.assertEqual(reglas.redondear_hacia_arriba(reglas.necesario_reposicion(diario, 0)), 3)
        self.assertEqual(reglas.redondear_hacia_arriba(20.000000000004), 20)

    def test_rn_009_18_faltan_descuenta_en_camino_y_preparadas(self):
        """TC-1187-10 y 11: 20 en camino o 20 preparadas tapan un necesario de 20."""
        self.assertEqual(reglas.faltan(20, 20, 0), 0)
        self.assertEqual(reglas.faltan(20, 0, 20), 0)
        self.assertEqual(reglas.faltan(20, 5, 5), 10)
        self.assertEqual(reglas.faltan(5, 20, 0), 0)

    def test_cobertura_con_lo_en_camino_y_sin_cubrir(self):
        cubre = reglas.cobertura(0, 24, T0, en_camino=12)
        self.assertEqual((cubre.estado, cubre.horas), (CUBRE, 12))
        sin = reglas.cobertura(0, 24, T0, deficit=13)
        self.assertEqual((sin.estado, sin.horas, sin.hasta), (SIN_CUBRIR, -13, None))

    def test_consumo_diario_cero_no_calcula_cobertura(self):
        """TC-1187-24: un ítem por lactante en un dispositivo sin lactantes."""
        self.assertEqual(reglas.cobertura(0, 0, T0), reglas.Cobertura(SIN_CONSUMO))

    def test_una_regla_a_medias_cuenta_como_sin_regla(self):
        self.assertTrue(reglas.tiene_regla(_item(Modo.DOTACION, 1, Por.PERSONA)))
        self.assertTrue(reglas.tiene_regla(_item(Modo.REPOSICION, 1, Por.PERSONA, 3)))
        self.assertFalse(reglas.tiene_regla(_item(Modo.REPOSICION, 1, Por.PERSONA)))
        self.assertFalse(reglas.tiene_regla(_item("", 1, Por.PERSONA)))


def _fila(pk, urgencia, *, nunca=False, horas=(), personas=10):
    items = tuple(reglas.ItemDelDispositivo(None, 1, 0, 0, 1, h == reglas.NUNCA, None, False, h) for h in horas)
    dispositivo = DispositivoDelAbastecimiento(pk, f"D{pk}", "", False, "ACTIVO")
    return reglas.FilaDispositivo(dispositivo, Unidades(personas=personas), 0, None if nunca else T0, items, urgencia)


class UrgenciaYOrdenTests(SimpleTestCase):
    def _item(self, faltan, critico):
        return reglas.ItemDelDispositivo(None, 1, 0, 0, faltan, False, None, critico, 0)

    def test_rn_009_20_critica_y_exigida(self):
        self.assertEqual(reglas.urgencia(True, ()), NIVEL_CRITICA)
        self.assertEqual(reglas.urgencia(False, (self._item(2, True),)), NIVEL_CRITICA)
        self.assertEqual(reglas.urgencia(False, (self._item(2, False),)), NIVEL_EXIGIDA)
        # Un ítem sin cubrir que lo preparado tapa (faltan 0) no lo vuelve Crítica (§12).
        self.assertEqual(reglas.urgencia(False, (self._item(0, True), self._item(1, False))), NIVEL_EXIGIDA)

    def test_rn_009_20_orden(self):
        """Crítica antes que Exigida; nunca recibió primero; menor cobertura; más personas."""
        filas = [
            _fila(1, NIVEL_EXIGIDA, horas=(29,)),
            _fila(2, NIVEL_EXIGIDA, horas=(5, 20)),
            _fila(3, NIVEL_CRITICA, horas=(0,), personas=120),
            _fila(4, NIVEL_CRITICA, horas=(reglas.NUNCA,), personas=18),
            _fila(5, NIVEL_CRITICA, horas=(reglas.NUNCA,), personas=86),
            _fila(6, NIVEL_CRITICA, nunca=True, horas=(reglas.NUNCA,), personas=12),
            _fila(7, NIVEL_CRITICA, horas=(-13,), personas=200),
        ]
        orden = [fila.dispositivo.id for fila in sorted(filas, key=reglas.clave_de_orden)]
        self.assertEqual(orden, [6, 5, 4, 7, 3, 2, 1])


def _salud(por_dispositivo, lactantes=(), items_de_lactantes=("Pañales",)):
    return Salud(sum(n for _d, n in por_dispositivo), tuple(por_dispositivo), tuple(lactantes), items_de_lactantes)


def _d(pk, reservado=False):
    return DispositivoDelAbastecimiento(pk, f"Dispositivo {pk}", "Resistencia", reservado, "ACTIVO")


class PresentarSaludTests(SimpleTestCase):
    def test_tc_1187_28_y_29_nombres_sin_numero_solo_con_operar(self):
        salud = _salud([(_d(1), 3), (_d(2), 2), (_d(3), 2), (_d(4), 2)])
        autoridad, mesa = presentar_salud(salud, False), presentar_salud(salud, True)
        self.assertEqual((autoridad.sin_dosis, autoridad.dispositivos, autoridad.nombres), (9, 4, ()))
        self.assertEqual([d.id for d in mesa.nombres], [1, 2, 3, 4])
        self.assertEqual(
            alertas.linea_de_sin_dosis(mesa), "9 personas con medicación crítica sin dosis en 4 dispositivos"
        )

    def test_tc_1187_30_conteo_deducible_sin_nombres(self):
        for salud in (_salud([(_d(1), 2)]), _salud([(_d(1), 1), (_d(2), 1), (_d(3), 1)])):
            with self.subTest(salud=salud):
                self.assertEqual(presentar_salud(salud, True).nombres, ())

    def test_tc_1187_31_unico_reservado_no_dice_en_1_dispositivo(self):
        salud = presentar_salud(_salud([(_d(1, reservado=True), 3)]), True)
        self.assertEqual(alertas.linea_de_sin_dosis(salud), "3 personas con medicación crítica sin dosis")
        reservado_entre_otros = presentar_salud(_salud([(_d(1, reservado=True), 3), (_d(2), 1)]), True)
        self.assertEqual([d.id for d in reservado_entre_otros.nombres], [2])

    def test_tc_1187_32_lactantes_numero_solo_desde_5(self):
        salud = presentar_salud(_salud([], lactantes=[(_d(1), 6), (_d(2), 3), (_d(3, reservado=True), 9)]), False)
        self.assertEqual([(d.id, n) for d, n in salud.lactantes], [(1, 6), (2, None), (3, None)])
        pañales, leche = (
            _item(Modo.REPOSICION, 1, Por.LACTANTE, 2, "Pañales"),
            _item(Modo.REPOSICION, 1, Por.LACTANTE, 1, "Leche"),
        )
        alerta = alertas.lactantes_sin_su_item(salud._replace(items_de_lactantes=(pañales, leche)))[0]
        self.assertEqual(alerta["titulo"], "Lactantes sin cubrir: Pañales y Leche")
        self.assertEqual(
            alerta["texto"],
            f"Dispositivo 1 · Resistencia (6 lactantes), Dispositivo 2 · Resistencia y {RESERVADO}.",
        )


def _con_nombre(pk, nombre):
    return DispositivoDelAbastecimiento(pk, nombre, "Resistencia", False, "ACTIVO")


class OrdenDeLaSaludTests(SimpleTestCase):
    """RN-009-21 b: el orden de los nombres no puede decir cuántas personas hay en cada uno."""

    def test_sin_dosis_por_nombre_y_no_por_conteo(self):
        """3 personas en 2 dispositivos: el que tiene 2 es el último alfabéticamente y va último."""
        dispositivos = {1: _con_nombre(1, "Zapallar"), 2: _con_nombre(2, "Avellaneda")}
        salud = reglas._salud(3, Counter({1: 2, 2: 1}), dispositivos, {}, [])
        self.assertEqual([d.nombre for d, _n in salud.sin_dosis_por_dispositivo], ["Avellaneda", "Zapallar"])
        mesa = presentar_salud(salud, True)
        self.assertEqual([d.nombre for d in mesa.nombres], ["Avellaneda", "Zapallar"])
        self.assertEqual(
            alertas.sin_dosis_en_dispositivos(mesa)[0]["texto"], "En Avellaneda · Resistencia y Zapallar · Resistencia."
        )

    def test_lactantes_por_nombre_y_no_por_cantidad(self):
        item = _item(Modo.REPOSICION, 1, Por.LACTANTE, 2, "Pañales")
        filas = {
            pk: reglas.FilaDispositivo(
                _con_nombre(pk, nombre),
                Unidades(personas=10, familias=1, lactantes=lactantes),
                0,
                T0,
                (reglas.ItemDelDispositivo(item, 1, 0, 0, 1, True, None, True, reglas.NUNCA),),
            )
            for pk, nombre, lactantes in ((1, "Zapallar", 9), (2, "Avellaneda", 2))
        }
        salud = reglas._salud(0, Counter(), {}, filas, [item])
        self.assertEqual([(d.nombre, n) for d, n in salud.lactantes], [("Avellaneda", 2), ("Zapallar", 9)])


class LactantesNuncaRecibidoTests(SimpleTestCase):
    """RN-009-20: el ítem «por lactante» nunca recibido es Crítico aunque haya algo en camino."""

    def _item(self, por, lactantes):
        item = _item(Modo.REPOSICION, 1, por, 2, "Pañales")
        tramos = {Por.PERSONA: [], Por.FAMILIA: [], Por.LACTANTE: []}
        unidades = Unidades(personas=10, familias=1, lactantes=lactantes)
        return reglas._item_del_dispositivo(item, unidades, tramos, None, 1, 0, T0)

    def test_por_lactante_nunca_recibido_con_algo_en_camino_es_critico(self):
        panales = self._item(Por.LACTANTE, 3)
        self.assertEqual((panales.necesario, panales.en_camino, panales.faltan), (3, 1, 2))
        self.assertEqual(panales.cobertura.estado, CUBRE)
        self.assertTrue(panales.critico)
        self.assertEqual(panales.horas_para_ordenar, reglas.NUNCA)
        self.assertEqual(reglas.urgencia(False, (panales,)), NIVEL_CRITICA)

    def test_otro_item_nunca_recibido_con_algo_en_camino_ordena_primero_pero_no_es_critico(self):
        agua = self._item(Por.PERSONA, 0)
        self.assertFalse(agua.critico)
        self.assertEqual(agua.horas_para_ordenar, reglas.NUNCA)
        self.assertEqual(reglas.urgencia(False, (agua,)), NIVEL_EXIGIDA)

    def test_sin_lactantes_no_es_critico(self):
        sin = self._item(Por.LACTANTE, 0)
        self.assertEqual((sin.necesario, sin.critico, sin.cobertura.estado), (0, False, SIN_CONSUMO))


# ---------------------------------------------------------------------------
# Lecturas y armado sobre un escenario
# ---------------------------------------------------------------------------


class EscenarioAbastecimiento(BaseSituacion):
    """Inicio del evento: hace 2 días (10/11 10:00). Ahora: 12/11 10:00.

    ==============  ========  =====================================================================
    Dispositivo     Personas  Qué se espera
    ==============  ========  =====================================================================
    Escuela         40        agua: 60 hace 2 días, 20 personas desde hace 1 día → necesario 10,
                              10 preparadas → cubierto (y una CANCELADA de 20 que no cuenta)
    Salón           12        nunca recibió en el evento (30 colchones antes del inicio) → Crítica
    Reservado       3         de ubicación reservada, nunca recibió → Crítica, sin nombre
    Suspendido      2         fuera de la red (INACTIVO), nunca recibió → Crítica, sin «Preparar»
    EES             6         6 lactantes, nunca recibió pañales → Crítica
    Club            10 (+3)   colchones: 7 recibidos, 1 preparado → faltan 2 (dotación) → Crítica
    Gimnasio        8         agua cubre ≈ 36 h → Exigida (8 personas)
    Hogar           4         agua cubre ≈ 36 h con 1 en camino → Exigida (4 personas)
    ==============  ========  =====================================================================
    """

    def setUp(self):
        super().setUp()
        SLAEmergencia.objects.filter(pk=self.sla.pk).update(inicio_evento=INICIO)
        self.sla.refresh_from_db()
        self.colchon = self._kit("Colchones", 1, Modo.DOTACION, "1", Por.PERSONA)
        self.agua = self._kit("Agua (bidón 6 l)", 2, Modo.REPOSICION, "0.5", Por.PERSONA, 1)
        self.higiene = self._kit("Kit de higiene", 3, Modo.REPOSICION, "1", Por.FAMILIA, 3)
        self.panales = self._kit("Pañales", 4, Modo.REPOSICION, "1", Por.LACTANTE, 2)
        self.repelente = TipoKit.objects.create(nombre="Repelente", unidad="unidad", orden=5)
        self.viejo = self._kit("Ítem viejo", 6, Modo.DOTACION, "1", Por.PERSONA)
        TipoKit.objects.filter(pk=self.viejo.pk).update(activo=False)

        reservado = TipoDispositivo.objects.create(
            codigo="PROT", nombre="Protección", tipos_plaza_admitidos=["CAMA"], ubicacion_reservada=True
        )
        self.escuela = self._dispositivo("Escuela", 1, localidad="Resistencia")
        self.salon = self._dispositivo("Salón Parroquial", 1, localidad="Charata")
        self.reservado = self._dispositivo("Refugio Secreto", 1, tipo=reservado, localidad="Lugar Secreto")
        self.suspendido = self._dispositivo(
            "Escuela Suspendida", 1, localidad="Quitilipi", estado=Dispositivo.Estado.INACTIVO
        )
        self.ees = self._dispositivo("EES N.° 9", 1, localidad="Barranqueras")
        self.club = self._dispositivo("Club Atlético Sarmiento", 1, localidad="Resistencia")
        self.gimnasio = self._dispositivo("Gimnasio Provincial", 1, localidad="Sáenz Peña")
        self.hogar = self._dispositivo("Hogar San José", 1, localidad="Resistencia")

        hace = lambda **kw: T0 - timedelta(**kw)  # noqa: E731
        self._grupo(self.escuela, 20, hace(days=2))
        self._grupo(self.escuela, 20, hace(days=1))
        for lactantes in (3, 0, 0, 0):
            self._grupo(self.salon, 3, hace(days=1), lactantes=lactantes)
        self._grupo(self.reservado, 3, hace(days=1), sin_dosis=1)
        self._grupo(self.suspendido, 2, hace(days=1))
        self._grupo(self.ees, 6, hace(days=1), lactantes=6, sin_dosis=1)
        self._grupo(self.club, 7, hace(days=2), sin_dosis=2)
        self._grupo(self.club, 3, hace(hours=1))
        self._grupo(self.gimnasio, 8, hace(days=1), sin_dosis=1)
        self._grupo(self.hogar, 4, hace(days=1))
        # Un egresado del evento anterior: no cambia nada (TC-1187-38).
        self._grupo(self.escuela, 5, hace(days=9), egresado_en=hace(days=4))

        ayer, antes = hace(days=1), hace(days=2)
        self._entrega(self.escuela, EstEntrega.RECIBIDA, {self.agua: 60, self.colchon: 40, self.higiene: 10}, antes)
        self._entrega(self.escuela, EstEntrega.PREPARADA, {self.agua: 10})
        self._entrega(self.escuela, EstEntrega.CANCELADA, {self.agua: 20})
        self._entrega(self.salon, EstEntrega.RECIBIDA, {self.colchon: 30}, hace(days=5))
        self._entrega(self.ees, EstEntrega.RECIBIDA, {self.colchon: 6, self.agua: 12, self.higiene: 5}, ayer)
        self._entrega(self.club, EstEntrega.RECIBIDA, {self.colchon: 7, self.agua: 40, self.higiene: 10}, ayer)
        self._entrega(self.club, EstEntrega.PREPARADA, {self.colchon: 1})
        self._entrega(
            self.gimnasio,
            EstEntrega.RECIBIDA_CON_DIFERENCIAS,
            {self.colchon: (9, 8), self.higiene: 5, self.agua: 10},
            ayer,
        )
        self._entrega(self.gimnasio, EstEntrega.RECIBIDA, {self.viejo: 3}, ayer)
        self._entrega(self.hogar, EstEntrega.RECIBIDA, {self.colchon: 4, self.agua: 4, self.higiene: 5}, ayer)
        self._entrega(self.hogar, EstEntrega.EN_CAMINO, {self.agua: 1})

    def _kit(self, nombre, orden, modo, cantidad, por, cada_dias=None):
        return TipoKit.objects.create(
            nombre=nombre,
            unidad="unidad",
            orden=orden,
            regla_modo=modo,
            regla_cantidad=Decimal(cantidad),
            regla_por=por,
            regla_cada_dias=cada_dias,
        )

    def _grupo(self, dispositivo, personas, ingreso, *, lactantes=0, sin_dosis=0, egresado_en=None):
        caso = self._caso(
            Estado.ALOJADO, creado=ingreso, alojado_en=ingreso, declarado=personas, grupo={"lactantes": lactantes}
        )
        responsable = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Estadía")
        estadia = Estadia.objects.create(
            ciudadano=responsable,
            dispositivo=dispositivo,
            fecha_ingreso=ingreso,
            clave_alojamiento=None if egresado_en else Estadia.clave_para(responsable),
            estado=Estadia.Estado.EGRESADA if egresado_en else Estadia.Estado.ACTIVA,
            fecha_egreso=egresado_en,
        )
        IntegranteGrupo.objects.bulk_create(
            [
                IntegranteGrupo(
                    grupo=caso.grupo,
                    orden=next(self._ordenes),
                    estadia=estadia,
                    ficha={"version": 1, "avisos_salud": SIN_DOSIS if n < sin_dosis else {}},
                    confirmada_en=ingreso,
                    egresado_en=egresado_en,
                )
                for n in range(personas)
            ]
        )

    def _entrega(self, dispositivo, estado, lineas, recibida_en=None):
        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{next(self._numeros):06d}",
            dispositivo=dispositivo,
            estado=estado,
            armada_por=self.operador,
            despachada_en=recibida_en,
        )
        if recibida_en is not None:
            EntregaKit.objects.filter(pk=entrega.pk).update(recibida_en=recibida_en)
        for item, cantidad in lineas.items():
            enviada, recibida = cantidad if isinstance(cantidad, tuple) else (cantidad, cantidad)
            LineaEntrega.objects.create(
                entrega=entrega,
                item=item,
                unidad="unidad",
                cantidad_enviada=enviada,
                cantidad_recibida=recibida if recibida_en is not None else None,
            )
        return entrega

    def _armar(self):
        foto = self._foto()
        return armar_abastecimiento(lecturas_de_abastecimiento(foto, self.sla.inicio_evento), foto, T0), foto


class ArmadoTests(EscenarioAbastecimiento):
    def setUp(self):
        super().setUp()
        self.armado, self.foto = self._armar()
        self.filas = {fila.dispositivo.id: fila for fila in self.armado.dispositivos}

    def _item(self, dispositivo, item):
        fila = self.filas[dispositivo.pk]
        return next(i for i in fila.items if i.item.id == item.pk)

    def test_tc_1187_06_franja(self):
        a = self.armado
        self.assertEqual(
            (a.con_gente, a.sin_cobertura, a.nunca_recibieron, a.sin_entrega_48h, a.personas_con_faltantes),
            (8, 7, 3, 3, 45),
        )

    def test_tc_1187_21_orden_y_urgencia(self):
        orden = [(fila.dispositivo.id, fila.urgencia) for fila in self.armado.dispositivos]
        C, E = NIVEL_CRITICA, NIVEL_EXIGIDA
        self.assertEqual(
            orden,
            [
                (self.salon.pk, C),
                (self.reservado.pk, C),
                (self.suspendido.pk, C),
                (self.ees.pk, C),
                (self.club.pk, C),
                (self.gimnasio.pk, E),
                (self.hogar.pk, E),
            ],
        )

    def test_tc_1187_08_a_12_la_escuela_queda_cubierta(self):
        """Persona-días reales (30 de consumo), 10 preparadas y una CANCELADA que no cuenta."""
        self.assertNotIn(self.escuela.pk, self.filas)
        lecturas = lecturas_de_abastecimiento(self.foto, INICIO)
        self.assertEqual(lecturas.abiertas.get((self.escuela.pk, self.agua.pk, EstEntrega.PREPARADA)), 10)
        self.assertNotIn(EstEntrega.CANCELADA, {clave[2] for clave in lecturas.abiertas})

    def test_tc_1187_13_se_cuenta_lo_recibido(self):
        lecturas = lecturas_de_abastecimiento(self.foto, INICIO)
        self.assertEqual(lecturas.recibido[(self.gimnasio.pk, self.colchon.pk)].cantidad, 8)

    def test_tc_1187_14_y_36_sin_regla_al_final_e_inactivo_afuera(self):
        nombres = [(fila.item.nombre, fila.con_regla) for fila in self.armado.por_item]
        self.assertEqual(
            nombres,
            [
                ("Colchones", True),
                ("Agua (bidón 6 l)", True),
                ("Kit de higiene", True),
                ("Pañales", True),
                ("Repelente", False),
            ],
        )

    def test_tc_1187_15_y_16_nunca_recibio_en_el_evento(self):
        salon = self.filas[self.salon.pk]
        self.assertTrue(salon.nunca_recibio)
        self.assertEqual(self._item(self.salon, self.colchon).necesario, 12)
        self.assertEqual(self._item(self.salon, self.agua).necesario, 12)

    def test_tc_1187_20_redondeo_por_dispositivo(self):
        self.assertEqual(self._item(self.salon, self.higiene).necesario, 3)

    def test_tc_1187_22_familia_que_ingresa_hoy(self):
        club = self.filas[self.club.pk]
        colchon = self._item(self.club, self.colchon)
        self.assertEqual((club.unidades.personas, club.ingresaron_hoy), (10, 3))
        self.assertEqual((colchon.necesario, colchon.preparadas, colchon.faltan), (3, 1, 2))

    def test_cobertura_y_empate_por_personas(self):
        gimnasio, hogar = self._item(self.gimnasio, self.agua), self._item(self.hogar, self.agua)
        self.assertEqual((gimnasio.necesario, gimnasio.faltan), (2, 2))
        self.assertAlmostEqual(gimnasio.cobertura.horas, 36)
        self.assertEqual((hogar.necesario, hogar.en_camino, hogar.faltan), (2, 1, 1))
        self.assertAlmostEqual(hogar.cobertura.horas, 36)

    def test_tc_1187_19_tabla_por_item(self):
        por_item = {fila.item.nombre: fila for fila in self.armado.por_item if fila.con_regla}
        colchones, agua = por_item["Colchones"], por_item["Agua (bidón 6 l)"]
        self.assertEqual(
            (colchones.necesario, colchones.en_camino, colchones.preparadas, colchones.faltan), (20, 0, 1, 19)
        )
        self.assertEqual((agua.necesario, agua.en_camino, agua.preparadas, agua.faltan), (31, 1, 10, 20))

    def test_cambio_586_lo_en_camino_hace_mas_de_48_h_va_aparte_y_no_descuenta_el_faltante(self):
        """Una entrega en camino hace 60 h no cuenta como «en camino»: se muestra «Demorado» y el faltante no baja."""
        antes = self._item(self.gimnasio, self.agua)
        entrega = EntregaKit.objects.create(
            numero="2026-K-900001",
            dispositivo=self.gimnasio,
            estado=EstEntrega.EN_CAMINO,
            armada_por=self.operador,
            despachada_en=T0 - timedelta(hours=60),
        )
        LineaEntrega.objects.create(entrega=entrega, item=self.agua, unidad="unidad", cantidad_enviada=5)
        reciente = EntregaKit.objects.create(
            numero="2026-K-900002",
            dispositivo=self.gimnasio,
            estado=EstEntrega.EN_CAMINO,
            armada_por=self.operador,
            despachada_en=T0 - timedelta(hours=47),
        )
        LineaEntrega.objects.create(entrega=reciente, item=self.agua, unidad="unidad", cantidad_enviada=1)

        armado, _foto = self._armar()
        fila = next(f for f in armado.dispositivos if f.dispositivo.id == self.gimnasio.pk)
        despues = next(i for i in fila.items if i.item.id == self.agua.pk)

        self.assertEqual(despues.demoradas, 5)
        # Solo la de 47 h suma a «en camino»; la de 60 h no descuenta nada.
        self.assertEqual(despues.en_camino, antes.en_camino + 1)
        self.assertEqual(despues.faltan, max(antes.faltan - 1, 0))

    def test_tc_1187_27_fuera_de_la_red_con_su_estado(self):
        suspendido = self.filas[self.suspendido.pk].dispositivo
        self.assertEqual((suspendido.estado, suspendido.activo), (Dispositivo.Estado.INACTIVO, False))

    def test_tc_1187_32_lactantes_sin_su_item(self):
        lactantes = [(d.id, n) for d, n in self.armado.salud.lactantes]
        self.assertEqual(lactantes, [(self.ees.pk, 6), (self.salon.pk, 3)])

    def test_tc_1187_18_sin_entrega_en_48_h_es_la_misma_lista_que_ae_6(self):
        ids = {fila["id"] for fila in sin_entrega_reciente(self.foto)}
        self.assertEqual(ids, {self.salon.pk, self.reservado.pk, self.suspendido.pk})
        self.assertEqual(self.armado.sin_entrega_48h, len(ids))
        ae_6 = alertas.dispositivos_sin_entrega(self.foto)[0]["titulo"]
        self.assertTrue(ae_6.startswith(f"{len(ids)} dispositivos con gente no recibieron"), ae_6)

    def test_tc_1187_34_ae_9_da_el_mismo_numero_que_ae_7(self):
        self.assertEqual(self.armado.salud.sin_dosis, sin_dosis_provincial(self.foto))
        self.assertEqual(self.armado.salud.sin_dosis, 5)
        self.assertEqual(len(self.armado.salud.sin_dosis_por_dispositivo), 4)

    def test_tc_1187_33_ae_8(self):
        salud = presentar_salud(self.armado.salud, False)
        reglas_ = [
            (a["regla"], a["severidad"], a["titulo"]) for a in alertas.alertas_de_abastecimiento(self.armado, salud)
        ]
        self.assertEqual(
            reglas_[0], ("AE-8", alertas.ALTA, "7 dispositivos sin cobertura para las próximas 48 h: 45 personas")
        )
        self.assertEqual([r for r, _s, _t in reglas_], ["AE-8", "AE-9", "AE-10"])

    def test_tc_1187_17_mover_el_inicio_recalcula(self):
        SLAEmergencia.objects.filter(pk=self.sla.pk).update(inicio_evento=T0 - timedelta(days=6))
        self.sla.refresh_from_db()
        armado, _foto = self._armar()
        filas = {fila.dispositivo.id: fila for fila in armado.dispositivos}
        colchon = next(i for i in filas[self.salon.pk].items if i.item.id == self.colchon.pk)
        self.assertEqual(colchon.necesario, 0)

    def test_tc_1187_37_cambiar_la_regla_recalcula(self):
        TipoKit.objects.filter(pk=self.agua.pk).update(regla_cantidad=Decimal("1"))
        armado, _foto = self._armar()
        agua = next(f for f in armado.por_item if f.item.id == self.agua.pk)
        self.assertGreater(agua.necesario, 31)


# ---------------------------------------------------------------------------
# La vista
# ---------------------------------------------------------------------------

URL_SOLAPA = f"{URL}?tab=abastecimiento"


def _panel(html):
    """El panel de la solapa, de su ``id`` al cierre de «Cómo se calcula»."""
    inicio = html.index('id="panel-abastecimiento"')
    return html[inicio : html.index("</details>", inicio)]


IR_A_PLAZOS = "Ir a Plazos de atención"
IR_A_INSUMOS = "Ir a Insumos"


class LeFaltaDeLaEntregaNuevaTests(EscenarioAbastecimiento):
    """«Le falta (estimado)» de «Nueva entrega» sale de las mismas reglas que la solapa (Cambio 586)."""

    def _propios(self, dispositivo_id):
        lecturas = lecturas_de_un_dispositivo(dispositivo_id, INICIO, T0)
        return faltantes_de_un_dispositivo(lecturas, dispositivo_id, T0)

    def test_cada_dispositivo_da_lo_mismo_en_las_dos_pantallas(self):
        armado, _foto = self._armar()

        self.assertTrue(armado.dispositivos)
        for fila in armado.dispositivos:
            propios = self._propios(fila.dispositivo.id)
            for item in fila.items:
                with self.subTest(dispositivo=fila.dispositivo.nombre, item=item.item.nombre):
                    self.assertEqual(propios[item.item.id], item)

    def test_un_egreso_entre_el_inicio_y_la_primera_recepcion_del_dispositivo_cuenta_igual(self):
        """El corte de los egresados es la primera recepción de **toda la red** (la solapa), no la del dispositivo: el
        Club recibió ayer, pero la Escuela recibió al inicio del evento y desde ahí cuentan los que se fueron.
        Mutación: cortar por la primera recepción del propio dispositivo deja este test en rojo."""
        self._grupo(self.club, 6, T0 - timedelta(days=2), egresado_en=T0 - timedelta(hours=36))
        foto = self._foto()
        de_la_solapa = lecturas_de_abastecimiento(foto, INICIO)
        propias = lecturas_de_un_dispositivo(self.club.pk, INICIO, T0)

        def del_club(lecturas):
            return sorted(
                ((p.ingreso, p.egresado_en) for p in lecturas.personas if p.dispositivo_id == self.club.pk),
                key=lambda par: (par[0], par[1] or T0),
            )

        self.assertIn(T0 - timedelta(hours=36), [egreso for _ingreso, egreso in del_club(propias)])
        self.assertEqual(del_club(propias), del_club(de_la_solapa))

    def test_sin_gente_alojada_no_hay_nada_que_estimar(self):
        self.assertEqual(self._propios(self._dispositivo("Vacío", 1, localidad="Resistencia").pk), {})


class VistaAbastecimientoTests(EscenarioAbastecimiento):
    def setUp(self):
        super().setUp()
        self.autoridad = self._usuario("autoridad", [VER_SITUACION])
        self.mesa = self._usuario("mesa", [OPERAR, VER_SITUACION])

    def _html(self, usuario, url=URL_SOLAPA):
        self.client.force_login(usuario)
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_tc_1187_01_sin_la_solapa_no_calcula_y_ofrece_calcular_con_los_filtros(self):
        html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando")
        self.assertIn("El abastecimiento se calcula cuando lo pedís", html)
        self.assertIn("departamento=San+Fernando&amp;tab=abastecimiento", html)
        self.assertNotIn("Dispositivos con faltantes", html)

    def test_tc_1187_02_sin_inicio_del_evento(self):
        SLAEmergencia.objects.filter(pk=self.sla.pk).update(inicio_evento=None)
        autoridad, supervisor = self._html(self.autoridad), self._html(self.supervisor)
        for html in (autoridad, supervisor):
            self.assertIn("Para estimar el abastecimiento falta la fecha de inicio del evento", html)
        self.assertNotIn(IR_A_PLAZOS, autoridad)
        self.assertIn(IR_A_PLAZOS, supervisor)
        self.assertIn(reverse("emergencia:plazos"), supervisor)

    def test_tc_1187_03_sin_reglas_y_sin_alojados(self):
        TipoKit.objects.update(regla_modo="", regla_cantidad=None, regla_por="", regla_cada_dias=None)
        html = self._html(self.supervisor)
        self.assertIn("Ningún ítem tiene regla de consumo: se configuran en Insumos", html)
        self.assertIn(IR_A_INSUMOS, html)
        self.assertIn(reverse("emergencia:insumos"), html)
        self.assertNotIn(IR_A_INSUMOS, self._html(self.autoridad))
        TipoKit.objects.filter(pk=self.colchon.pk).update(
            regla_modo=Modo.DOTACION, regla_cantidad=1, regla_por=Por.PERSONA
        )
        IntegranteGrupo.objects.update(egresado_en=T0 - timedelta(hours=1))
        self.assertIn("Todavía no hay personas alojadas por la emergencia", self._html(self.autoridad))

    def test_el_encabezado_de_demorado_dice_las_horas_de_la_regla(self):
        self.assertIn(f"Demorado (más de {EntregaKit.HORAS_PARA_DEMORADA} h)", _panel(self._html(self.autoridad)))

    def test_tc_1187_04_y_05_nota_provincial_y_los_filtros_no_la_acotan(self):
        sin_filtro = _panel(self._html(self.autoridad))
        con_filtro = _panel(self._html(self.autoridad, f"{URL_SOLAPA}&departamento=San+Fernando&ventana=7d"))
        nota = (
            "Red provincial · próximas 48 h · desde el inicio del evento (10/11 10:00) · estimado con la regla de "
            "consumo de cada ítem; no es un inventario"
        )
        self.assertIn(nota, sin_filtro)
        self.assertIn("<strong>19</strong>", sin_filtro)
        self.assertEqual(con_filtro, sin_filtro)

    def test_tc_1187_14_configurar_un_item_sin_regla_solo_con_supervisar(self):
        self.assertIn("Sin regla de consumo", _panel(self._html(self.autoridad)))
        self.assertNotIn("Configurar", _panel(self._html(self.autoridad)))
        self.assertIn("Configurar", _panel(self._html(self.supervisor)))

    def test_tc_1187_25_reservado_nunca_nombrado(self):
        html = self._html(self.mesa)
        self.assertIn(RESERVADO, html)
        self.assertNotIn("Refugio Secreto", html)
        self.assertNotIn("Lugar Secreto", html)

    def test_tc_1187_26_y_27_preparar_entrega_solo_con_operar_y_activo(self):
        autoridad = self._html(self.autoridad)
        self.assertNotIn("/emergencia/entregas/nueva/", autoridad)
        self.assertNotIn("Preparar entrega", autoridad)
        for usuario in (self.mesa, self.supervisor):
            html = self._html(usuario)
            self.assertIn(f"/emergencia/entregas/nueva/?dispositivo={self.salon.pk}", html)
            self.assertIn(f"/emergencia/entregas/nueva/?dispositivo={self.reservado.pk}", html)
            self.assertNotIn(f"/emergencia/entregas/nueva/?dispositivo={self.suspendido.pk}", html)
            inicio = html.index("Escuela Suspendida · Quitilipi")
            self.assertIn("Inactivo", html[inicio : html.index("</tr>", inicio)])

    def test_tc_1187_28_y_29_salud_nombres_solo_con_la_mesa(self):
        linea = "5 personas con medicación crítica sin dosis en 4 dispositivos"
        autoridad, mesa = self._html(self.autoridad), self._html(self.mesa)
        self.assertIn(linea, autoridad)
        self.assertNotIn("En Club Atlético Sarmiento", autoridad)
        self.assertIn(linea, mesa)
        self.assertIn(
            "En Club Atlético Sarmiento · Resistencia, EES N.° 9 · Barranqueras y Gimnasio Provincial · Sáenz Peña.",
            mesa,
        )

    def test_tc_1187_32_lactantes_para_todos(self):
        html = self._html(self.autoridad)
        self.assertIn("EES N.° 9 · Barranqueras (6 lactantes) y Salón Parroquial · Charata.", html)

    def test_tc_1187_35_el_resumen_enlaza_ae_6_con_los_filtros_y_no_trae_las_de_abastecimiento(self):
        html = self._html(self.autoridad, f"{URL}?departamento=San+Fernando")
        enlace = re.search(r'href="([^"]*)"[^>]*>Ver el abastecimiento<', html).group(1)
        self.assertEqual(enlace, f"{URL}?departamento=San+Fernando&amp;tab=abastecimiento")
        self.assertNotIn("sin cobertura para las próximas 48 h", html)
        self.assertNotIn("Lactantes sin", html)

    def test_tc_1187_39_rotulos(self):
        panel = _panel(self._html(self.supervisor)).lower()
        self.assertNotIn("stock", panel)
        self.assertEqual(panel.count("inventario"), panel.count("no es un inventario"))
        self.assertIn("(estimado)", panel)

    def test_tc_1187_40_la_solapa_no_se_imprime(self):
        html = self._html(self.autoridad)
        self.assertIn('id="panel-abastecimiento" aria-labelledby="tab-abastecimiento" class="nodo-no-imprimir', html)


# ---------------------------------------------------------------------------
# Presupuesto (TC-1187-41)
# ---------------------------------------------------------------------------

CLAVE_PRESUPUESTO = "emergencia_situacion_abastecimiento"
PRESUPUESTO_SOLAPA = 5


@tag("performance")
class PresupuestoAbastecimientoTests(BancoSituacion):
    """50 dispositivos, 30 ítems, 2.000 entregas y 3.000 alojados; después, un evento anterior."""

    ITEMS = 30
    ENTREGAS_NUEVAS = 1500

    def setUp(self):
        super().setUp()
        SLAEmergencia.objects.filter(pk=self.sla.pk).update(inicio_evento=T0 - timedelta(days=5))
        self.sla.refresh_from_db()
        modos = (
            {"regla_modo": Modo.DOTACION, "regla_cantidad": 1, "regla_por": Por.PERSONA},
            {
                "regla_modo": Modo.REPOSICION,
                "regla_cantidad": Decimal("0.5"),
                "regla_por": Por.PERSONA,
                "regla_cada_dias": 1,
            },
            {"regla_modo": Modo.REPOSICION, "regla_cantidad": 1, "regla_por": Por.FAMILIA, "regla_cada_dias": 3},
            {"regla_modo": Modo.REPOSICION, "regla_cantidad": 1, "regla_por": Por.LACTANTE, "regla_cada_dias": 2},
            {},
        )
        self.items = TipoKit.objects.bulk_create(
            [
                TipoKit(nombre=f"Ítem {n}", unidad="unidad", orden=n, **modos[n % len(modos)])
                for n in range(self.ITEMS - 1)
            ]
        )
        self.dispositivos = list(Dispositivo.objects.order_by("id"))
        estados = (EstEntrega.RECIBIDA, EstEntrega.PREPARADA, EstEntrega.EN_CAMINO)
        self._sembrar_entregas(self.ENTREGAS_NUEVAS, estados, T0 - timedelta(hours=30), prefijo="N")

    def _sembrar_entregas(self, cuantas, estados, recibida_en, prefijo):
        entregas = EntregaKit.objects.bulk_create(
            [
                EntregaKit(
                    numero=f"2026-{prefijo}-{n + 1:06d}",
                    dispositivo=self.dispositivos[n % len(self.dispositivos)],
                    estado=estados[n % len(estados)],
                    armada_por=self.operador,
                    despachada_en=recibida_en,
                    recibida_en=recibida_en if estados[n % len(estados)] in EntregaKit.ESTADOS_RECIBIDOS else None,
                )
                for n in range(cuantas)
            ]
        )
        LineaEntrega.objects.bulk_create(
            [
                LineaEntrega(
                    entrega=e,
                    item=self.items[n % len(self.items)],
                    unidad="unidad",
                    cantidad_enviada=4,
                    cantidad_recibida=4 if e.recibida_en else None,
                )
                for n, e in enumerate(entregas)
            ]
        )

    def _evento_anterior(self):
        """2.000 entregas recibidas y 3.000 egresados antes del inicio del evento."""
        antes = self.sla.inicio_evento - timedelta(days=3)
        self._sembrar_entregas(2000, (EstEntrega.RECIBIDA,), antes, prefijo="V")
        estadias = list(Estadia.objects.order_by("id"))
        grupos = list(CasoEmergencia.objects.filter(estado=Estado.ALOJADO).values_list("grupo_id", flat=True)[:50])
        IntegranteGrupo.objects.bulk_create(
            [
                IntegranteGrupo(
                    grupo_id=grupos[n % len(grupos)],
                    orden=50_000 + n,
                    estadia=estadias[n % len(estadias)],
                    ficha={"version": 1},
                    confirmada_en=antes - timedelta(days=2),
                    egresado_en=antes,
                )
                for n in range(3000)
            ]
        )

    def _solapa(self):
        foto = self._foto()
        reset_queries()  # el sembrado llena el registro de consultas (tope 9.000) y la cuenta se corre
        with CaptureQueriesContext(connection) as capturadas:
            armado = armar_abastecimiento(lecturas_de_abastecimiento(foto, self.sla.inicio_evento), foto, T0)
            salud = presentar_salud(armado.salud, True)
            alertas.alertas_de_abastecimiento(armado, salud)
        return armado, [consulta["sql"] for consulta in capturadas.captured_queries]

    def _vista(self, url, usuario=None):
        # Un cliente por usuario, siempre el mismo: la sesión única de backoffice echa al que se loguea de nuevo.
        if usuario is None:
            cliente = self.client
            if not cliente.session.get("_auth_user_id"):
                cliente.force_login(self.supervisor)
        else:
            cliente = self.client_class()
            cliente.force_login(usuario)
        cliente.get(url)
        reset_queries()
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = cliente.get(url)
        self.assertEqual(respuesta.status_code, 200)
        # `captured_queries` lee el registro de la conexión: se copia antes del próximo `reset_queries`.
        return [consulta["sql"] for consulta in capturadas.captured_queries]

    def test_tc_1187_41_consultas_fijas_y_un_evento_anterior_no_cambia_nada(self):
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]
        self.assertLessEqual(techo, 26)
        antes, solapa = self._solapa()
        vista = self._vista(URL_SOLAPA)
        sin_solapa = self._vista(URL)
        self.assertLessEqual(len(solapa), PRESUPUESTO_SOLAPA, solapa)
        self.assertLessEqual(len(vista), techo, vista)
        self.assertLessEqual(len(sin_solapa), 21)
        # La solapa suma exactamente sus lecturas (A5 no corre: todos los dispositivos con gente son de la red).
        self.assertEqual(len(vista) - len(sin_solapa), len(solapa))
        self.assertEqual(len(self._vista(URL_SOLAPA, self._usuario("autoridad", [VER_SITUACION]))), len(vista))
        self.assertTrue(antes.dispositivos)
        self.assertGreater(antes.con_gente, 0)

        self._evento_anterior()
        despues, solapa_despues = self._solapa()
        self.assertEqual(len(solapa_despues), len(solapa))
        self.assertEqual(len(self._vista(URL_SOLAPA)), len(vista))
        self.assertEqual(despues, antes)
