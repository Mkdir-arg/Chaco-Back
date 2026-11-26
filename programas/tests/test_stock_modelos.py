"""Stock de insumos, PR 1 (análisis 010): esquema, libro inmutable, restricciones y capacidades.

No hay servicios todavía: los tests escriben las tablas directo, que es justo lo que los servicios del PR 2a
tendrán que respetar. Lo que se prueba acá es lo que la base y los modelos garantizan solos.
"""

import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import PROTECT
from django.test import TestCase

from core import rbac
from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    MovimientoStock,
    OperacionStock,
    SaldoStock,
    TipoDispositivo,
    TipoKit,
)
from programas.services import dispositivos as servicio
from programas.services.roles_sembrados import ROLES_DISPOSITIVOS_EMERGENCIA
from programas.tests.test_dispositivos_equipo_410 import BaseEquipo

STOCK = ("stock.ver", "stock.entregar", "stock.ingresar", "stock.ajustar")


class BaseStock(TestCase):
    def setUp(self):
        super().setUp()
        self.tipo = TipoDispositivo.objects.create(codigo="CIS", nombre="CIS", maneja_stock=True)
        self.disp = Dispositivo.objects.create(
            tipo=self.tipo, codigo="CIS-1", nombre="CIS 1", estado=Dispositivo.Estado.ACTIVO
        )
        self.edificio = Edificio.objects.create(codigo="ED-1", nombre="Edificio 1")
        self.edificio.dispositivos.add(self.disp)
        self.item = TipoKit.objects.create(nombre="Colchón", unidad="unidad")
        self.usuario = User.objects.create_user(username="carga", password="x")

    def _operacion(self, **extra):
        datos = {
            "tipo": OperacionStock.Tipo.INGRESO_MANUAL,
            "dispositivo": self.disp,
            "edificio": self.edificio,
            "usuario": self.usuario,
        }
        datos.update(extra)
        return OperacionStock.objects.create(**datos)

    def _movimiento(self, operacion=None, **extra):
        datos = {
            "operacion": operacion or self._operacion(),
            "tipo": MovimientoStock.Tipo.INGRESO_MANUAL,
            "dispositivo": self.disp,
            "edificio": self.edificio,
            "item": self.item,
            "cantidad": 5,
            "saldo_posterior": 5,
        }
        datos.update(extra)
        return MovimientoStock.objects.create(**datos)

    def _saldo(self, cantidad=3):
        return SaldoStock.objects.create(
            dispositivo=self.disp, edificio=self.edificio, item=self.item, cantidad=cantidad
        )

    def _entrega(self, numero="2026-K-000001"):
        return EntregaKit.objects.create(
            numero=numero, dispositivo=self.disp, edificio=self.edificio, armada_por=self.usuario
        )


class TipoDispositivoTests(TestCase):
    def test_lleva_stock_nace_apagado(self):
        tipo = TipoDispositivo.objects.create(codigo="X", nombre="X")
        self.assertFalse(tipo.maneja_stock)
        self.assertFalse(TipoDispositivo.objects.get(pk=tipo.pk).maneja_stock)

    def test_es_independiente_de_las_plazas(self):
        tipo = TipoDispositivo.objects.create(codigo="X", nombre="X", maneja_stock=True)
        self.assertFalse(tipo.maneja_plazas)

    def test_la_columna_tiene_default_real_en_la_base(self):
        """Contrato de migraciones: el código viejo da de alta tipos sin conocer la columna."""

        campo = TipoDispositivo._meta.get_field("maneja_stock")
        self.assertIs(campo.db_default, False)


class LibroInmutableTests(BaseStock):
    """RN-010-05: las dos tablas del libro no se editan ni se borran, por ninguna vía."""

    def _casos(self):
        return {
            "OperacionStock": (self._operacion(), OperacionStock),
            "MovimientoStock": (self._movimiento(), MovimientoStock),
        }

    def test_update_masivo_levanta(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre), self.assertRaises(ValidationError):
                modelo.objects.filter(pk=fila.pk).update(tipo="AJUSTE")

    def test_delete_masivo_levanta(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre), self.assertRaises(ValidationError):
                modelo.objects.filter(pk=fila.pk).delete()
            self.assertTrue(modelo.objects.filter(pk=fila.pk).exists())

    def test_bulk_update_levanta_desde_el_manager_y_desde_el_queryset(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre):
                with self.assertRaises(ValidationError):
                    modelo.objects.bulk_update([fila], ["tipo"])
                with self.assertRaises(ValidationError):
                    modelo.objects.all().bulk_update([fila], ["tipo"])

    def test_save_sobre_una_fila_existente_levanta(self):
        for nombre, (fila, _modelo) in self._casos().items():
            with self.subTest(modelo=nombre), self.assertRaises(ValidationError):
                fila.save()

    def test_save_de_una_instancia_nueva_con_pk_existente_no_pisa_la_fila(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre):
                copia = modelo(pk=fila.pk, tipo="AJUSTE")
                for campo in modelo._meta.concrete_fields:
                    if campo.name not in ("id", "tipo"):
                        setattr(copia, campo.attname, getattr(fila, campo.attname))
                with self.assertRaises(IntegrityError), transaction.atomic():
                    copia.save()
                self.assertNotEqual(modelo.objects.get(pk=fila.pk).tipo, "AJUSTE")

    def test_save_con_force_update_o_update_fields_levanta(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre):
                nueva = modelo(pk=fila.pk)
                with self.assertRaises(ValidationError):
                    nueva.save(force_update=True)
                with self.assertRaises(ValidationError):
                    nueva.save(update_fields=["tipo"])

    def test_bulk_create_con_update_conflicts_levanta(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre), self.assertRaises(ValidationError):
                modelo.objects.bulk_create(
                    [modelo(pk=fila.pk)], update_conflicts=True, update_fields=["tipo"], unique_fields=["id"]
                )

    def test_delete_de_instancia_levanta(self):
        for nombre, (fila, modelo) in self._casos().items():
            with self.subTest(modelo=nombre), self.assertRaises(ValidationError):
                fila.delete()
            self.assertTrue(modelo.objects.filter(pk=fila.pk).exists())

    def test_update_or_create_levanta(self):
        operacion = self._operacion()
        with self.assertRaises(ValidationError):
            OperacionStock.objects.update_or_create(pk=operacion.pk, defaults={"tipo": "AJUSTE"})

    def test_el_manager_por_defecto_es_el_inmutable(self):
        """Si el `base_manager` fuera el común, `related.all().update()` esquivaría la guarda."""

        operacion = self._operacion()
        self._movimiento(operacion)
        with self.assertRaises(ValidationError):
            operacion.movimientos.update(cantidad=9)
        for modelo in (OperacionStock, MovimientoStock):
            self.assertEqual(modelo._base_manager.__class__, modelo.objects.__class__)
            self.assertEqual(modelo._default_manager.__class__, modelo.objects.__class__)

    def test_insertar_filas_nuevas_funciona(self):
        self.assertEqual(self._movimiento().cantidad, 5)
        self.assertEqual(OperacionStock.objects.count(), 1)


class SaldoStockTests(BaseStock):
    def test_un_update_directo_a_negativo_lo_corta_la_base(self):
        """«Nunca negativo» (RN-010-03) no depende solo del servicio: la base lo respalda."""

        saldo = self._saldo(2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SaldoStock.objects.filter(pk=saldo.pk).update(cantidad=-1)
        saldo.refresh_from_db()
        self.assertEqual(saldo.cantidad, 2)

    def test_crear_con_cantidad_negativa_lo_corta_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._saldo(-1)

    def test_la_clave_es_unica(self):
        self._saldo()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._saldo()

    def test_la_clave_distingue_institucion_edificio_e_insumo(self):
        self._saldo()
        otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="CIS-2", nombre="CIS 2", estado=Dispositivo.Estado.ACTIVO
        )
        otro_item = TipoKit.objects.create(nombre="Frazada", unidad="unidad")
        otro_edificio = Edificio.objects.create(codigo="ED-2", nombre="Edificio 2")
        SaldoStock.objects.create(dispositivo=otra, edificio=self.edificio, item=self.item)
        SaldoStock.objects.create(dispositivo=self.disp, edificio=otro_edificio, item=self.item)
        SaldoStock.objects.create(dispositivo=self.disp, edificio=self.edificio, item=otro_item)
        self.assertEqual(SaldoStock.objects.count(), 4)

    def test_nace_en_cero(self):
        saldo = SaldoStock.objects.create(dispositivo=self.disp, edificio=self.edificio, item=self.item)
        self.assertEqual(saldo.cantidad, 0)
        self.assertIsNone(saldo.ultimo_movimiento_en)

    def test_bulk_create_con_ignore_conflicts_no_pisa_el_saldo_existente(self):
        """El pre-alta de RN-010-19 (PR 2a) no puede tocar un saldo que ya tiene cantidad."""

        self._saldo(7)
        SaldoStock.objects.bulk_create(
            [SaldoStock(dispositivo=self.disp, edificio=self.edificio, item=self.item)], ignore_conflicts=True
        )
        self.assertEqual(SaldoStock.objects.get().cantidad, 7)


class OperacionYMovimientoTests(BaseStock):
    def test_un_movimiento_en_cero_lo_corta_la_base(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._movimiento(cantidad=0, saldo_posterior=0)

    def test_el_movimiento_admite_delta_negativo(self):
        self.assertEqual(self._movimiento(cantidad=-2, saldo_posterior=3).cantidad, -2)

    def test_una_entrega_de_kit_se_suma_una_sola_vez(self):
        """RN-010-06: el UNIQUE de `entrega_kit` corta una doble suma."""

        entrega = self._entrega()
        self._operacion(tipo=OperacionStock.Tipo.INGRESO_KIT, entrega_kit=entrega)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._operacion(tipo=OperacionStock.Tipo.INGRESO_KIT, entrega_kit=entrega)

    def test_varias_operaciones_sin_entrega_conviven(self):
        self._operacion()
        self._operacion()
        self.assertEqual(OperacionStock.objects.filter(entrega_kit__isnull=True).count(), 2)

    def test_el_uuid_del_cliente_es_unico_y_admite_varios_nulos(self):
        identificador = uuid.uuid4()
        self._operacion(uuid_cliente=identificador)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._operacion(uuid_cliente=identificador)
        self._operacion()
        self._operacion()
        self.assertEqual(OperacionStock.objects.filter(uuid_cliente__isnull=True).count(), 2)

    def test_los_textos_opcionales_nacen_vacios(self):
        operacion = self._operacion()
        for campo in ("origen", "origen_detalle", "comprobante", "motivo", "observacion"):
            self.assertEqual(getattr(operacion, campo), "", campo)

    def test_los_textos_opcionales_nacen_vacios_en_un_motor_sin_returning(self):
        """MySQL 8 no devuelve columnas en el INSERT: sin `default`, queda un `DatabaseDefault` en memoria."""

        with mock.patch.object(connection.features, "can_return_columns_from_insert", False):
            operacion = self._operacion()
        for campo in ("origen", "origen_detalle", "comprobante", "motivo", "observacion"):
            self.assertEqual(getattr(operacion, campo), "", campo)
            self.assertEqual(OperacionStock._meta.get_field(campo).default, "", campo)

    def test_los_catalogos_son_los_de_la_decision_4(self):
        self.assertEqual(
            [valor for valor, _ in OperacionStock.Origen.choices],
            ["DONACION", "MUNICIPIO", "COMPRA", "OTRO_PROGRAMA", "OTRO"],
        )
        self.assertEqual(
            [etiqueta for _, etiqueta in OperacionStock.MotivoAjuste.choices],
            [
                "Inventario inicial",
                "Conteo periódico",
                "Rotura o vencimiento",
                "Pérdida o robo",
                "Corrección de carga",
                "Otro",
            ],
        )

    def test_el_libro_protege_sus_referencias(self):
        """Toda FK de las tres tablas es `PROTECT`: ni un borrado en cascada se lleva el libro ni los saldos.

        Se mira la declaración y no un `delete()` real: `Edificio`, `TipoKit` y `Dispositivo` ya tienen su propia
        guarda y levantan `ValidationError` antes de llegar al collector.
        """

        for modelo in (SaldoStock, OperacionStock, MovimientoStock):
            for campo in modelo._meta.get_fields():
                if campo.concrete and campo.is_relation:
                    with self.subTest(campo=f"{modelo.__name__}.{campo.name}"):
                        self.assertIs(campo.remote_field.on_delete, PROTECT)


class CapacidadesCatalogoTests(TestCase):
    def test_las_cuatro_estan_en_el_catalogo_y_son_de_programa(self):
        for codigo in STOCK:
            with self.subTest(codigo=codigo):
                self.assertIn(codigo, rbac.codigos_de_capacidad())
                self.assertIn(codigo, rbac.codigos_de_programa())

    def test_son_de_dispositivos_y_no_valen_en_otro_programa(self):
        fuera = rbac.capacidades_fuera_del_programa(rbac.CODIGO_PROGRAMA_DISPOSITIVOS)
        self.assertFalse(set(STOCK) & set(fuera))
        for programa in (rbac.CODIGO_PROGRAMA_EMERGENCIA, "BECAS"):
            self.assertLessEqual(set(STOCK), set(rbac.capacidades_fuera_del_programa(programa)), programa)

    def test_las_constantes_del_servicio_son_las_del_catalogo(self):
        self.assertEqual(
            (
                servicio.CAP_STOCK_VER,
                servicio.CAP_STOCK_ENTREGAR,
                servicio.CAP_STOCK_INGRESAR,
                servicio.CAP_STOCK_AJUSTAR,
            ),
            STOCK,
        )


class RolesSembradosTests(TestCase):
    def _caps(self, clave):
        return next(r for r in ROLES_DISPOSITIVOS_EMERGENCIA if r.clave == clave).capacidades

    def _de_stock(self, clave):
        return {c for c in self._caps(clave) if c.startswith("stock.")}

    def test_decision_5_reparto_por_rol(self):
        self.assertTrue(set(STOCK) <= set(self._caps("dispositivos.administrador")))
        self.assertTrue(set(STOCK) <= set(self._caps("dispositivos.coordinador")))
        self.assertEqual(self._de_stock("dispositivos.operador"), {"stock.ver", "stock.entregar"})
        for clave in ("dispositivos.consulta", "dispositivos.supervision_red"):
            self.assertEqual(self._de_stock(clave), {"stock.ver"}, clave)

    def test_quien_entrega_puede_ver_personas(self):
        """Entregar exige `ciudadano.ver` (RN-010-13): un rol sembrado que entrega sin eso no podría usarla."""

        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            if "stock.entregar" in rol.capacidades:
                self.assertIn("ciudadano.ver", rol.capacidades, rol.clave)

    def test_quien_opera_el_stock_lo_puede_ver(self):
        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            if any(c in rol.capacidades for c in STOCK[1:]):
                self.assertIn("stock.ver", rol.capacidades, rol.clave)

    def test_los_roles_de_emergencia_no_reciben_stock(self):
        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            if rol.clave.startswith("emergencia."):
                self.assertFalse([c for c in rol.capacidades if c.startswith("stock.")], rol.clave)


class VerTodosTests(BaseEquipo):
    """RN-010-13 / decisión 9: `dispositivo.ver_todos` amplía `stock.ver` y **nunca** las de operar."""

    def _lector(self, *capacidades):
        rol = self._rol("Lector red", list(capacidades))
        return self._fresco(self._usuario("lector_red", rol))

    def test_ver_todos_da_stock_ver_en_toda_la_red(self):
        usuario = self._lector("stock.ver", "dispositivo.ver_todos")
        self.assertTrue(servicio.puede_operar_dispositivo(usuario, self.disp_a, "stock.ver"))
        self.assertTrue(servicio.puede_operar_dispositivo(usuario, self.disp_b, "stock.ver"))

    def test_ver_todos_no_da_stock_entregar(self):
        usuario = self._lector("stock.ver", "stock.entregar", "dispositivo.ver_todos")
        self.assertFalse(servicio.puede_operar_dispositivo(usuario, self.disp_a, "stock.entregar"))

    def test_ver_todos_no_da_ingresar_ni_ajustar(self):
        usuario = self._lector(*STOCK, "dispositivo.ver_todos")
        for capacidad in ("stock.ingresar", "stock.ajustar"):
            self.assertFalse(servicio.puede_operar_dispositivo(usuario, self.disp_a, capacidad), capacidad)

    def test_ver_todos_sin_stock_ver_no_da_nada(self):
        usuario = self._lector("dispositivo.ver_todos")
        self.assertFalse(servicio.puede_operar_dispositivo(usuario, self.disp_a, "stock.ver"))

    def test_sin_ver_todos_stock_ver_exige_ser_del_equipo(self):
        rol = self._rol("Con stock", ["stock.ver"])
        usuario = self._usuario("miembro", rol)
        self._miembro(self.disp_a, usuario, rol)
        usuario = self._fresco(usuario)
        self.assertTrue(servicio.puede_operar_dispositivo(usuario, self.disp_a, "stock.ver"))
        self.assertFalse(servicio.puede_operar_dispositivo(usuario, self.disp_b, "stock.ver"))

    def test_la_lista_de_lectura_de_la_red_es_exactamente_esa(self):
        self.assertEqual(
            servicio._CAPS_LECTURA_RED,
            {servicio.CAP_VER, servicio.CAP_VER_EDIFICIOS, servicio.CAP_STOCK_VER},
        )
