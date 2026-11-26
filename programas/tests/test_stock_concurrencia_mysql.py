"""Stock, PR 2a (análisis 010, RN-010-19): las carreras del saldo, contra el motor real.

La suite normal corre en SQLite, donde ``select_for_update`` es un no-op: estos tests llevan ``@tag("mysql")`` y los
corre el job «Motor real» (``manage.py test --tag mysql``) contra MariaDB 10.11 / 11 y MySQL 8. Sin motor real se
saltean (``MotorRealMixin``).

Cada test deja a A detenido **con el candado del edificio tomado** —es el que se toma antes que los saldos— y exige
que B esté en ``LOCK WAIT``: si alguien saca el candado, B atraviesa y ``en_paralelo`` lo reporta. Lo que se afirma
después es el invariante del libro (``diferencias_de_saldo() == []``) y el saldo final exacto.
"""

import uuid

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TransactionTestCase, tag

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    LineaEntrega,
    MiembroEquipoDispositivo,
    MovimientoStock,
    OperacionStock,
    Programa,
    SaldoStock,
    TipoDispositivo,
    TipoKit,
)
from programas.selectors import stock as selectores
from programas.services import kits
from programas.services import stock as servicio
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from users.models import RolMeta

EDIFICIO_BLOQUEADO = punto_critico(Edificio, "_preparar")


@tag("mysql")
class CarreraDelSaldoTests(MotorRealMixin, TransactionTestCase):
    """``TransactionTestCase`` y no ``TestCase``: lo que se prueba son transacciones que commitean."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="CIS-CONC", nombre="CIS", maneja_stock=True)
        self.disp = Dispositivo.objects.create(
            tipo=tipo, codigo="CIS-C1", nombre="CIS 1", estado=Dispositivo.Estado.ACTIVO
        )
        self.edificio = Edificio.objects.create(codigo="ED-C1", nombre="Edificio C1")
        self.edificio.dispositivos.add(self.disp)
        self.colchon = TipoKit.objects.create(nombre="Colchón carrera", unidad="unidad")
        self.ana = self._usuario("ana_stock")
        self.juan = self._usuario("juan_stock")
        # Saldo inicial 10, con su libro coherente, ya commiteado.
        servicio.ingresar_manual(
            self._fresco(self.ana), self.disp, self.edificio, {self.colchon.pk: 10}, origen="COMPRA"
        )

    def _usuario(self, nombre):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(c) for c in ("dispositivo.ver", "stock.ver", "stock.ingresar", "stock.ajustar")])
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        MiembroEquipoDispositivo.objects.create(dispositivo=self.disp, usuario=usuario, rol=rol)
        return usuario

    def _fresco(self, usuario):
        """``rbac`` memoiza las capacidades en el objeto, y cada hilo necesita el suyo."""

        return User.objects.get(pk=usuario.pk)

    def _saldo(self):
        return SaldoStock.objects.get(dispositivo=self.disp, edificio=self.edificio, item=self.colchon).cantidad

    def _ajustar(self, usuario, contada, visto, envio=None):
        def operacion():
            return servicio.ajustar(
                self._fresco(usuario),
                self.disp,
                self.edificio,
                self.colchon,
                contada,
                visto,
                "CONTEO_PERIODICO",
                uuid_cliente=envio,
            )

        return operacion

    def _ingresar(self, usuario, cantidad, envio=None):
        def operacion():
            return servicio.ingresar_manual(
                self._fresco(usuario),
                self.disp,
                self.edificio,
                {self.colchon.pk: cantidad},
                origen="DONACION",
                uuid_cliente=envio,
            )

        return operacion

    def _recibir_kit(self, cantidad):
        """La recepción de un kit de ``cantidad`` colchones (lo que hará ``kits.recibir_entrega`` en el PR 3)."""

        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{EntregaKit.objects.count() + 1:06d}",
            dispositivo=self.disp,
            edificio=self.edificio,
            estado=kits.Estado.RECIBIDA,
            armada_por=self.ana,
        )
        LineaEntrega.objects.create(
            entrega=entrega,
            item=self.colchon,
            nombre="Colchón",
            unidad="unidad",
            cantidad_enviada=cantidad,
            cantidad_recibida=cantidad,
        )

        def operacion():
            return servicio.sumar_recepcion_de_kit(EntregaKit.objects.get(pk=entrega.pk), self._fresco(self.juan))

        return operacion

    def assertInvarianteDelLibro(self):
        self.assertEqual(selectores.diferencias_de_saldo(), [])
        total = sum(MovimientoStock.objects.filter(item=self.colchon).values_list("cantidad", flat=True))
        self.assertEqual(total, self._saldo())

    def test_un_ajuste_y_una_suma_a_la_vez_dejan_el_saldo_exacto(self):
        """A (el ajuste) cuenta 7 sobre 10 (−3) y retiene el candado; B suma 5 y espera. Entran en ese orden: el saldo
        final es 7 + 5 = 12, ninguna de las dos pisa a la otra."""

        resultados, errores = en_paralelo(
            self._ajustar(self.ana, 7, 10), self._recibir_kit(5), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(len(resultados), 2)
        self.assertEqual(self._saldo(), 12)
        self.assertInvarianteDelLibro()

    def test_una_suma_y_un_ajuste_a_la_vez_con_la_suma_primero(self):
        resultados, errores = en_paralelo(
            self._recibir_kit(5), self._ajustar(self.ana, 7, 10), punto_a=EDIFICIO_BLOQUEADO
        )

        # B (el ajuste) esperó la suma de A y después vio 15, no 10: SaldoCambio, y el saldo es el de la suma.
        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], servicio.SaldoCambio)
        self.assertEqual(errores[0].saldo_actual, 15)
        self.assertEqual(self._saldo(), 15)
        self.assertInvarianteDelLibro()

    def test_dos_ajustes_a_la_vez_sobre_el_mismo_saldo_visto_gana_uno(self):
        resultados, errores = en_paralelo(
            self._ajustar(self.ana, 6, 10), self._ajustar(self.juan, 4, 10), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], servicio.SaldoCambio)
        self.assertEqual(self._saldo(), 6)
        self.assertEqual(OperacionStock.objects.filter(tipo="AJUSTE").count(), 1)
        self.assertInvarianteDelLibro()

    def test_dos_ingresos_a_la_vez_suman_los_dos(self):
        resultados, errores = en_paralelo(
            self._ingresar(self.ana, 3), self._ingresar(self.juan, 4), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(len(resultados), 2)
        self.assertEqual(self._saldo(), 17)
        self.assertEqual(sorted(m.saldo_posterior for m in MovimientoStock.objects.all()), [10, 13, 17])
        self.assertInvarianteDelLibro()

    def test_el_mismo_envio_dos_veces_a_la_vez_se_aplica_una_sola_vez(self):
        envio = uuid.uuid4()

        resultados, errores = en_paralelo(
            self._ingresar(self.ana, 3, envio), self._ingresar(self.ana, 3, envio), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(sorted(operacion.ya_existia for operacion in resultados), [False, True])
        self.assertEqual(self._saldo(), 13)
        self.assertEqual(OperacionStock.objects.filter(uuid_cliente=envio).count(), 1)
        self.assertInvarianteDelLibro()

    def test_dos_recepciones_de_la_misma_entrega_a_la_vez_suman_una_sola_vez(self):
        suma = self._recibir_kit(5)
        entrega = EntregaKit.objects.latest("pk")

        def otra_vez():
            return servicio.sumar_recepcion_de_kit(EntregaKit.objects.get(pk=entrega.pk), self._fresco(self.juan))

        resultados, errores = en_paralelo(suma, otra_vez, punto_a=EDIFICIO_BLOQUEADO)

        self.assertEqual(errores, [])
        self.assertEqual(sorted(operacion.ya_existia for operacion in resultados), [False, True])
        self.assertEqual(self._saldo(), 15)
        self.assertEqual(OperacionStock.objects.filter(entrega_kit=entrega).count(), 1)
        self.assertInvarianteDelLibro()
