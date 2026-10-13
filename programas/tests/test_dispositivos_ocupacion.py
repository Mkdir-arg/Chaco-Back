"""El cálculo único de ocupación, disponibilidad y censo (MVP v2, etapas 1 y 2 · #687, #689).

Cuatro cosas se verifican acá, y cada una tiene su motivo:

1. **Las cifras de las plazas** —totales, fuera de servicio y operativas— con sus bordes:
   el dispositivo sin sectores, el sector sin plazas y el sector entero fuera de
   servicio. Son los casos en los que un cálculo apurado devuelve ``None``, explota o
   directamente no aparece.
2. **Las cifras de los movimientos**, que trajo la etapa 2: ``ocupadas`` sale de las
   estadías activas, ``reservadas`` de las reservas y los préstamos **vigentes** —una
   reserva vencida deja de contar sola, sin que nadie la apague— y ``disponibles`` se
   deriva de las dos. Un conteo que las ignorara mostraría un dispositivo libre y
   mandaría a alojar gente sobre plazas tomadas, sin que nada fallara.
3. **Que un conteo armado a mano siga diciendo «no sé» y no «cero»**: la red que protege
   a la cifra que alguien agregue mañana sigue puesta.
4. **Que haya un solo origen**: el total de un dispositivo es exactamente la suma de sus
   sectores. Si el desglose y el total se pueden separar, las pantallas se desincronizan,
   que es justo lo que esta task existe para evitar.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.test import TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Dispositivo, Estadia, Plaza, ReservaPlaza, Sector, TipoDispositivo
from programas.services.ocupacion import Conteo, ocupacion_de_plazas

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_ocupacion_de_plazas"


def _dispositivo(tipo, codigo):
    return Dispositivo.objects.create(tipo=tipo, codigo=codigo, nombre=f"Dispositivo {codigo}")


def _sector(dispositivo, nombre, **extra):
    return Sector.objects.create(dispositivo=dispositivo, nombre=nombre, **extra)


def _plazas(sector, cantidad, estado=Plaza.Estado.OPERATIVA, prefijo="P"):
    motivo = "Refacción" if estado == Plaza.Estado.FUERA_SERVICIO else ""
    return Plaza.objects.bulk_create(
        Plaza(sector=sector, codigo=f"{prefijo}{n}", estado=estado, motivo_fuera_servicio=motivo)
        for n in range(1, cantidad + 1)
    )


class ConteoTests(TestCase):
    """La aritmética del conteo, sin tocar la base."""

    def test_operativas_son_las_totales_menos_las_fuera_de_servicio(self):
        self.assertEqual(Conteo(totales=10, fuera_de_servicio=3).operativas, 7)

    def test_un_conteo_armado_a_mano_sin_las_cifras_dice_que_no_sabe_en_lugar_de_cero(self):
        """No es el que devuelve el servicio —ese las llena siempre—, es el de a mano."""

        conteo = Conteo(totales=10, fuera_de_servicio=3)

        self.assertIsNone(conteo.ocupadas)
        self.assertIsNone(conteo.reservadas)
        self.assertIsNone(conteo.disponibles)
        self.assertEqual(conteo.pendientes, ("ocupadas", "reservadas", "disponibles"))
        self.assertFalse(conteo.completo)

    def test_un_pendiente_no_se_puede_sumar_por_accidente(self):
        """La garantía de fondo: si una pantalla trata el pendiente como número, explota."""

        with self.assertRaises(TypeError):
            Conteo(totales=10).ocupadas + 1

    def test_con_las_dos_cifras_recibidas_lo_derivado_se_completa_solo(self):
        """Lo que la etapa 2 no tuvo que cambiar: alcanzó con pasar los dos enteros."""

        conteo = Conteo(totales=10, fuera_de_servicio=3, ocupadas=4, reservadas=1)

        self.assertEqual(conteo.disponibles, 2)
        self.assertEqual(conteo.pendientes, ())
        self.assertTrue(conteo.completo)

    def test_sumar_un_pendiente_con_un_calculado_sigue_siendo_pendiente(self):
        total = Conteo(totales=4, fuera_de_servicio=1, ocupadas=2, reservadas=0) + Conteo(totales=6)

        self.assertEqual(total.totales, 10)
        self.assertEqual(total.fuera_de_servicio, 1)
        self.assertIsNone(total.ocupadas)
        self.assertIsNone(total.disponibles)


class OcupacionDePlazasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        cls.cis = _dispositivo(cls.tipo, "CIS-3")
        cls.parador = _dispositivo(cls.tipo, "PAR-1")

    def test_las_plazas_se_cuentan_por_sector_y_por_dispositivo(self):
        varones = _sector(self.cis, "Varones", capacidad=8)
        mujeres = _sector(self.cis, "Mujeres", capacidad=4)
        _plazas(varones, 5)
        _plazas(varones, 2, estado=Plaza.Estado.FUERA_SERVICIO, prefijo="FS")
        _plazas(mujeres, 3)

        censo = ocupacion_de_plazas(self.cis)
        ocupacion = censo.de(self.cis)

        self.assertEqual(ocupacion.conteo.totales, 10)
        self.assertEqual(ocupacion.conteo.fuera_de_servicio, 2)
        self.assertEqual(ocupacion.conteo.operativas, 8)
        self.assertEqual([sector.nombre for sector in ocupacion.sectores], ["Mujeres", "Varones"])
        por_nombre = {sector.nombre: sector for sector in ocupacion.sectores}
        self.assertEqual(por_nombre["Varones"].conteo.operativas, 5)
        self.assertEqual(por_nombre["Varones"].conteo.fuera_de_servicio, 2)
        self.assertEqual(por_nombre["Mujeres"].conteo.operativas, 3)
        self.assertEqual(por_nombre["Varones"].capacidad_declarada, 8)
        self.assertEqual(por_nombre["Varones"].sector_id, varones.pk)

    def test_el_total_del_dispositivo_es_exactamente_la_suma_de_sus_sectores(self):
        """El invariante que impide que el desglose y el tablero muestren dos números."""

        for indice in range(4):
            sector = _sector(self.cis, f"Sector {indice}", capacidad=indice)
            _plazas(sector, indice + 1, prefijo=f"S{indice}-")
            _plazas(sector, indice, estado=Plaza.Estado.FUERA_SERVICIO, prefijo=f"S{indice}-FS")

        ocupacion = ocupacion_de_plazas([self.cis]).de(self.cis)

        self.assertEqual(
            ocupacion.conteo.totales,
            sum(sector.conteo.totales for sector in ocupacion.sectores),
        )
        self.assertEqual(
            ocupacion.conteo.fuera_de_servicio,
            sum(sector.conteo.fuera_de_servicio for sector in ocupacion.sectores),
        )
        self.assertEqual(
            ocupacion.conteo.operativas,
            sum(sector.conteo.operativas for sector in ocupacion.sectores),
        )

    def test_un_dispositivo_sin_sectores_llega_en_cero_y_no_falta(self):
        censo = ocupacion_de_plazas([self.cis, self.parador])

        vacio = censo.de(self.parador)
        self.assertEqual(vacio.sectores, ())
        self.assertEqual(vacio.conteo.totales, 0)
        self.assertEqual(vacio.conteo.fuera_de_servicio, 0)
        self.assertEqual(vacio.conteo.operativas, 0)

    def test_un_dispositivo_sin_sectores_no_tiene_plazas_tomadas_y_eso_se_sabe(self):
        """Cero y no pendiente: un ámbito sin plazas no puede tener plazas ocupadas."""

        conteo = ocupacion_de_plazas(self.parador).de(self.parador).conteo

        self.assertEqual(conteo.pendientes, ())
        self.assertEqual(conteo.ocupadas, 0)
        self.assertEqual(conteo.reservadas, 0)
        self.assertEqual(conteo.disponibles, 0)

    def test_un_sector_sin_plazas_aparece_en_cero(self):
        _sector(self.cis, "Sector vacío", capacidad=6)

        ocupacion = ocupacion_de_plazas(self.cis).de(self.cis)

        self.assertEqual(len(ocupacion.sectores), 1)
        self.assertEqual(ocupacion.sectores[0].conteo.totales, 0)
        self.assertEqual(ocupacion.sectores[0].capacidad_declarada, 6)
        self.assertEqual(ocupacion.conteo.operativas, 0)

    def test_con_todas_las_plazas_fuera_de_servicio_no_queda_ninguna_operativa(self):
        sector = _sector(self.cis, "Clausurado")
        _plazas(sector, 4, estado=Plaza.Estado.FUERA_SERVICIO, prefijo="FS")

        conteo = ocupacion_de_plazas(self.cis).de(self.cis).conteo

        self.assertEqual(conteo.totales, 4)
        self.assertEqual(conteo.fuera_de_servicio, 4)
        self.assertEqual(conteo.operativas, 0)

    def test_un_sector_dado_de_baja_no_cuenta_ni_en_el_total_ni_en_el_desglose(self):
        activo = _sector(self.cis, "Activo")
        _plazas(activo, 2)
        de_baja = _sector(self.cis, "De baja", activo=False)
        _plazas(de_baja, 7, prefijo="B")

        ocupacion = ocupacion_de_plazas(self.cis).de(self.cis)

        self.assertEqual([sector.nombre for sector in ocupacion.sectores], ["Activo"])
        self.assertEqual(ocupacion.conteo.totales, 2)

    def test_las_plazas_de_un_dispositivo_no_se_le_cuentan_a_otro(self):
        sector_cis = _sector(self.cis, "Varones")
        _plazas(sector_cis, 3)
        sector_parador = _sector(self.parador, "General")
        _plazas(sector_parador, 5, prefijo="G")

        censo = ocupacion_de_plazas([self.cis, self.parador])

        self.assertEqual(censo.de(self.cis).conteo.totales, 3)
        self.assertEqual(censo.de(self.parador).conteo.totales, 5)
        self.assertEqual(censo.total.totales, 8)

    def test_el_total_del_censo_suma_todos_los_dispositivos_pedidos(self):
        uno = _sector(self.cis, "Varones")
        _plazas(uno, 4)
        _plazas(uno, 1, estado=Plaza.Estado.FUERA_SERVICIO, prefijo="FS")
        otro = _sector(self.parador, "General")
        _plazas(otro, 2, prefijo="G")

        censo = ocupacion_de_plazas([self.cis, self.parador])

        self.assertEqual(censo.total.totales, 7)
        self.assertEqual(censo.total.fuera_de_servicio, 1)
        self.assertEqual(censo.total.operativas, 6)
        self.assertEqual(censo.total.disponibles, 6)

    def test_el_censo_vacio_no_falla(self):
        censo = ocupacion_de_plazas([])

        self.assertEqual(censo.por_dispositivo, {})
        self.assertEqual(censo.total.totales, 0)
        self.assertEqual(censo.total.ocupadas, 0)
        self.assertEqual(censo.total.disponibles, 0)

    def test_acepta_instancia_id_y_queryset(self):
        sector = _sector(self.cis, "Varones")
        _plazas(sector, 3)

        por_instancia = ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales
        por_id = ocupacion_de_plazas(self.cis.pk).de(self.cis.pk).conteo.totales
        por_queryset = ocupacion_de_plazas(Dispositivo.objects.filter(pk=self.cis.pk)).de(self.cis).conteo.totales
        # Un id que llega de la URL es una cadena, y una cadena es iterable: sin tratarla
        # como escalar se recorrería carácter por carácter.
        por_texto = ocupacion_de_plazas(str(self.cis.pk)).de(self.cis).conteo.totales

        self.assertEqual([por_instancia, por_id, por_queryset, por_texto], [3, 3, 3, 3])

    def test_pedir_dos_veces_el_mismo_dispositivo_no_lo_duplica(self):
        sector = _sector(self.cis, "Varones")
        _plazas(sector, 3)

        censo = ocupacion_de_plazas([self.cis, self.cis, self.cis.pk])

        self.assertEqual(list(censo.por_dispositivo), [self.cis.pk])
        self.assertEqual(censo.total.totales, 3)

    def test_preguntar_por_un_dispositivo_que_no_se_pidio_falla_en_vez_de_devolver_cero(self):
        censo = ocupacion_de_plazas([self.cis])

        with self.assertRaises(KeyError):
            censo.de(self.parador)

    def test_un_dispositivo_sin_guardar_no_se_calcula(self):
        with self.assertRaises(ValueError):
            ocupacion_de_plazas(Dispositivo(tipo=self.tipo, codigo="X", nombre="X"))


class OcupacionConMovimientosTests(TestCase):
    """Las cifras que la etapa 2 completó: ocupadas, reservadas y disponibles."""

    @classmethod
    def setUpTestData(cls):
        cls.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        cls.cis = _dispositivo(cls.tipo, "CIS-3")
        cls.sector = _sector(cls.cis, "Varones", capacidad=6)
        cls.plazas = _plazas(cls.sector, 4)
        cls.persona = Ciudadano.objects.create(dni="40111222", nombre="Ana", apellido="Gómez")
        cls.otra = Ciudadano.objects.create(dni="40333444", nombre="Juan", apellido="Pérez")

    def _alojar(self, ciudadano, plaza):
        return Estadia.objects.create(
            ciudadano=ciudadano,
            dispositivo=self.cis,
            plaza=plaza,
            fecha_ingreso=timezone.now(),
            clave_alojamiento=Estadia.clave_para(ciudadano),
        )

    def _conteo(self):
        return ocupacion_de_plazas(self.cis).de(self.cis).conteo

    def test_una_estadia_activa_ocupa_su_plaza_y_descuenta_una_disponible(self):
        self._alojar(self.persona, self.plazas[0])

        conteo = self._conteo()

        self.assertEqual(conteo.totales, 4)
        self.assertEqual(conteo.operativas, 4)
        self.assertEqual(conteo.ocupadas, 1)
        self.assertEqual(conteo.reservadas, 0)
        self.assertEqual(conteo.disponibles, 3)
        self.assertTrue(conteo.completo)

    def test_una_estadia_cerrada_deja_de_ocupar(self):
        estadia = self._alojar(self.persona, self.plazas[0])
        estadia.estado = Estadia.Estado.EGRESADA
        estadia.fecha_egreso = timezone.now()
        estadia.clave_alojamiento = None
        estadia.save()

        self.assertEqual(self._conteo().ocupadas, 0)

    def test_una_estadia_sin_plaza_no_le_descuenta_capacidad_a_ningun_sector(self):
        """Se cuentan plazas tomadas, no personas: sin plaza no hay plaza que restar."""

        Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=self.cis,
            fecha_ingreso=timezone.now(),
            clave_alojamiento=Estadia.clave_para(self.persona),
        )

        self.assertEqual(self._conteo().ocupadas, 0)

    def test_una_reserva_vigente_saca_la_plaza_de_la_disponibilidad(self):
        ReservaPlaza.objects.create(plaza=self.plazas[1], ciudadano=self.persona, desde=timezone.now())

        conteo = self._conteo()

        self.assertEqual(conteo.reservadas, 1)
        self.assertEqual(conteo.disponibles, 3)

    def test_una_reserva_vencida_deja_de_contar_sola(self):
        ahora = timezone.now()
        ReservaPlaza.objects.create(
            plaza=self.plazas[1],
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            desde=ahora - timedelta(days=2),
            hasta=ahora - timedelta(days=1),
        )

        self.assertEqual(self._conteo().reservadas, 0)

    def test_una_reserva_que_todavia_no_empezo_tampoco_cuenta(self):
        ahora = timezone.now()
        ReservaPlaza.objects.create(
            plaza=self.plazas[1],
            ciudadano=self.persona,
            desde=ahora + timedelta(days=1),
            hasta=ahora + timedelta(days=2),
        )

        self.assertEqual(self._conteo().reservadas, 0)

    def test_una_reserva_liberada_no_cuenta(self):
        ReservaPlaza.objects.create(
            plaza=self.plazas[1],
            ciudadano=self.persona,
            desde=timezone.now(),
            estado=ReservaPlaza.Estado.LIBERADA,
        )

        self.assertEqual(self._conteo().reservadas, 0)

    def test_una_plaza_fuera_de_servicio_no_se_cuenta_dos_veces(self):
        """La invariante: ocupadas + reservadas nunca pasa de operativas."""

        Plaza.objects.filter(pk=self.plazas[3].pk).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Refacción"
        )
        self._alojar(self.persona, self.plazas[0])
        ReservaPlaza.objects.create(plaza=self.plazas[1], ciudadano=self.otra, desde=timezone.now())

        conteo = self._conteo()

        self.assertEqual(conteo.operativas, 3)
        self.assertEqual(conteo.ocupadas + conteo.reservadas, 2)
        self.assertEqual(conteo.disponibles, 1)

    def test_el_total_del_dispositivo_sigue_siendo_la_suma_de_sus_sectores(self):
        otro = _sector(self.cis, "Mujeres", capacidad=2)
        plazas_otro = _plazas(otro, 2, prefijo="M")
        self._alojar(self.persona, self.plazas[0])
        self._alojar(self.otra, plazas_otro[0])

        ocupacion = ocupacion_de_plazas(self.cis).de(self.cis)

        self.assertEqual(
            ocupacion.conteo.ocupadas,
            sum(sector.conteo.ocupadas for sector in ocupacion.sectores),
        )
        self.assertEqual(ocupacion.conteo.ocupadas, 2)

    def test_las_estadias_de_un_sector_no_se_le_cuentan_a_otro(self):
        otro = _sector(self.cis, "Mujeres", capacidad=2)
        _plazas(otro, 2, prefijo="M")
        self._alojar(self.persona, self.plazas[0])

        por_nombre = {s.nombre: s for s in ocupacion_de_plazas(self.cis).de(self.cis).sectores}

        self.assertEqual(por_nombre["Varones"].conteo.ocupadas, 1)
        self.assertEqual(por_nombre["Mujeres"].conteo.ocupadas, 0)


@tag("performance")
class OcupacionDePlazasPresupuestoTests(TestCase):
    """El costo del cálculo no puede crecer con los sectores, las plazas ni la red.

    Contar sector por sector es la forma natural de escribir esto y la que mata la
    pantalla: el mapa de plazas de un dispositivo grande son decenas de sectores, y el
    tablero de la red son todos los dispositivos a la vez. El presupuesto vive en
    `scripts/perf_budgets.json` (sección `servicios`), fuera de `budgets`, que tiene que
    coincidir exactamente con el manifiesto de rutas de `scripts/perf_audit.py`.
    """

    @classmethod
    def setUpTestData(cls):
        tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        cls.dispositivos = [_dispositivo(tipo, f"D-{n}") for n in range(6)]
        for indice, dispositivo in enumerate(cls.dispositivos):
            for numero in range(5):
                sector = _sector(dispositivo, f"Sector {numero}", capacidad=10)
                _plazas(sector, 6, prefijo=f"{indice}-{numero}-")
                _plazas(sector, 2, estado=Plaza.Estado.FUERA_SERVICIO, prefijo=f"{indice}-{numero}-FS")

    def _presupuesto(self):
        return json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]

    def test_el_calculo_cuesta_lo_mismo_para_uno_que_para_toda_la_red(self):
        """Tres consultas fijas: las plazas, las estadías activas y las reservas vigentes."""

        techo = self._presupuesto()["consultas_fijas"]

        with CaptureQueriesContext(connection) as una_institucion:
            ocupacion_de_plazas([self.dispositivos[0]])
        with CaptureQueriesContext(connection) as toda_la_red:
            censo = ocupacion_de_plazas(self.dispositivos)

        self.assertEqual(censo.total.totales, 6 * 5 * 8)
        for medida, cuantos in ((una_institucion, "una institución"), (toda_la_red, "seis instituciones")):
            self.assertLessEqual(
                len(medida),
                techo,
                f"{len(medida)} consultas para {cuantos}; el presupuesto de «{CLAVE_PRESUPUESTO}» en "
                f"scripts/perf_budgets.json es {techo}. Subirlo exige justificarlo en el mismo PR.",
            )

    def test_agregar_sectores_y_plazas_no_agrega_consultas(self):
        """La guarda contra el N+1: un `.count()` por sector pasaría todo lo de arriba."""

        dispositivo = self.dispositivos[0]
        with CaptureQueriesContext(connection) as antes:
            ocupacion_de_plazas([dispositivo])

        for numero in range(5, 25):
            sector = _sector(dispositivo, f"Sector {numero}", capacidad=10)
            _plazas(sector, 4, prefijo=f"extra-{numero}-")

        with CaptureQueriesContext(connection) as despues:
            ocupacion = ocupacion_de_plazas([dispositivo]).de(dispositivo)

        self.assertEqual(len(ocupacion.sectores), 25)
        self.assertEqual(len(despues), len(antes))
