"""Stock, PR 2a (análisis 010, RN-010-19): el orden de candados es uno solo.

    entrega de kits (si la hay) → Dispositivo → Edificio → SaldoStock por (dispositivo, edificio, item) ascendente

Dos caminos que bloquean las mismas filas tienen que pedirlas en el mismo orden, o InnoDB corta uno con ``ERROR 1213``.
En SQLite no hay candados, así que el orden se prueba por la secuencia de llamadas (patrón de
``test_dispositivos_bloqueo_institucion``); la carrera de verdad está en ``test_stock_concurrencia_mysql``.

Mutaciones verificadas: tomar el edificio antes que el dispositivo en ``_preparar``, o el saldo antes que el edificio,
pone rojo ``test_el_orden_es_dispositivo_edificio_saldo``; cambiar el ``order_by`` de ``saldos_bloqueados`` pone rojo
``test_los_saldos_se_bloquean_por_dispositivo_edificio_item``; sustituir el ``bulk_create(ignore_conflicts=True)`` por
``get_or_create`` pone rojo ``test_los_saldos_se_crean_antes_de_bloquearlos_y_sin_get_or_create``.
"""

from unittest import mock

from django.db import connection
from django.test.utils import CaptureQueriesContext

from core.tests.candados import orden_de_candados
from programas.models import Edificio, EntregaKit, LineaEntrega, OperacionStock, SaldoStock
from programas.services import kits
from programas.services import stock as servicio
from programas.tests.base_stock import BaseStock


def _orden():
    return orden_de_candados(compartido="institucion", edificio=Edificio.objects, saldo=SaldoStock.objects)


def _sin_repetir(orden):
    """El orden en que cada tipo de fila se pide **por primera vez**."""

    return list(dict.fromkeys(orden))


class OrdenDeLosCandadosTests(BaseStock):
    ESPERADO = ["institucion", "edificio", "saldo"]

    def test_el_orden_es_dispositivo_edificio_saldo_en_el_ingreso_manual(self):
        with _orden() as orden:
            servicio.ingresar_manual(
                self.carga, self.disp, self.edificio, {self.colchon.pk: 2, self.frazada.pk: 1}, origen="DONACION"
            )

        self.assertEqual(_sin_repetir(orden), self.ESPERADO)
        self.assertEqual(orden.count("institucion"), 1)

    def test_el_orden_es_dispositivo_edificio_saldo_en_el_ajuste(self):
        self._sembrar(self.colchon, 5)
        with _orden() as orden:
            servicio.ajustar(self.carga, self.disp, self.edificio, self.colchon, 1, 5, "PERDIDA_ROBO")

        self.assertEqual(_sin_repetir(orden), self.ESPERADO)

    def test_el_orden_es_dispositivo_edificio_saldo_al_sumar_una_recepcion(self):
        entrega = EntregaKit.objects.create(
            numero="2026-K-000900",
            dispositivo=self.disp,
            edificio=self.edificio,
            estado=kits.Estado.RECIBIDA,
            armada_por=self.carga,
        )
        LineaEntrega.objects.create(
            entrega=entrega,
            item=self.colchon,
            nombre="Colchón",
            unidad="unidad",
            cantidad_enviada=4,
            cantidad_recibida=4,
        )
        with _orden() as orden:
            servicio.sumar_recepcion_de_kit(entrega, self.carga)

        self.assertEqual(_sin_repetir(orden), self.ESPERADO)

    def test_una_operacion_que_se_rechaza_antes_de_los_candados_no_toma_ninguno(self):
        with _orden() as orden, self.assertRaises(Exception):  # noqa: B017 - el tipo no importa, sí que no bloqueó
            servicio.ingresar_manual(self.carga, self.disp, self.edificio, {}, origen="DONACION")

        self.assertEqual(orden, [])

    def test_un_rechazo_por_permiso_no_toma_ningun_candado(self):
        sin_permiso = self._usuario_con("sin_permiso", ("stock.ver",))
        with _orden() as orden, self.assertRaises(Exception):  # noqa: B017
            servicio.ingresar_manual(sin_permiso, self.disp, self.edificio, {self.colchon.pk: 1}, origen="DONACION")

        self.assertEqual(orden, [])


class SaldosBloqueadosTests(BaseStock):
    def _claves(self):
        d, e = self.disp.pk, self.edificio.pk
        return [(d, e, self.frazada.pk), (d, self.otro_edificio.pk, self.colchon.pk), (d, e, self.colchon.pk)]

    def test_los_saldos_se_bloquean_por_dispositivo_edificio_item(self):
        from django.db import transaction

        claves = self._claves()
        with transaction.atomic(), CaptureQueriesContext(connection) as consultas:
            saldos = servicio.saldos_bloqueados(claves)

        self.assertEqual(list(saldos), sorted(claves))
        seleccion = next(q["sql"] for q in consultas if q["sql"].startswith("SELECT") and "stock" in q["sql"].lower())
        orden = seleccion[seleccion.index("ORDER BY") :]
        posiciones = [orden.index(columna) for columna in ("dispositivo_id", "edificio_id", "item_id")]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_los_saldos_se_crean_antes_de_bloquearlos_y_sin_get_or_create(self):
        from django.db import transaction

        llamadas = []
        crear = SaldoStock.objects.bulk_create

        def bulk_create(objs, **kwargs):
            llamadas.append(("bulk_create", kwargs.get("ignore_conflicts")))
            return crear(objs, **kwargs)

        with (
            mock.patch.object(SaldoStock.objects, "bulk_create", bulk_create),
            mock.patch.object(SaldoStock.objects, "get_or_create", side_effect=AssertionError("get_or_create")),
            orden_de_candados(saldo=SaldoStock.objects) as orden,
            transaction.atomic(),
        ):
            servicio.saldos_bloqueados(self._claves())

        self.assertEqual(llamadas, [("bulk_create", True)])
        self.assertEqual(orden, ["saldo"])
        self.assertEqual(SaldoStock.objects.count(), 3)
        self.assertEqual(set(SaldoStock.objects.values_list("cantidad", flat=True)), {0})

    def test_un_saldo_que_ya_existia_no_se_pisa(self):
        from django.db import transaction

        self._sembrar(self.colchon, 7)
        with transaction.atomic():
            saldos = servicio.saldos_bloqueados([(self.disp.pk, self.edificio.pk, self.colchon.pk)])

        self.assertEqual(next(iter(saldos.values())).cantidad, 7)
        self.assertEqual(SaldoStock.objects.count(), 1)

    def test_sin_claves_no_hace_nada(self):
        self.assertEqual(servicio.saldos_bloqueados([]), {})


class NadaQuedaSiLaOperacionFallaTests(BaseStock):
    def test_un_rechazo_despues_de_los_candados_deja_la_base_como_estaba(self):
        """El saldo en cero que se pre-crea vive en la misma transacción: si la operación se rechaza, se deshace."""

        self.edificio.activo = False
        self.edificio.save()

        with self.assertRaises(Exception):  # noqa: B017
            servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, origen="DONACION")

        self.assertFalse(SaldoStock.objects.exists())
        self.assertFalse(OperacionStock.objects.exists())
