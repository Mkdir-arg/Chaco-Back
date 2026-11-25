"""Stock, PR 2a (análisis 010): ingreso manual, ajuste por conteo y suma por recepción de kit.

Cada guarda crítica se verificó por mutación (romperla pone rojo su test); ver el cuerpo del PR.
"""

import uuid
from datetime import date, datetime
from unittest import mock

from django.core.exceptions import ValidationError
from django.utils import timezone

from programas.models import (
    Dispositivo,
    EntregaKit,
    LineaEntrega,
    MovimientoStock,
    OperacionStock,
    SaldoStock,
    TipoDispositivo,
)
from programas.selectors import stock as selectores
from programas.services import kits
from programas.services import stock as servicio
from programas.services.stock import (
    SaldoCambio,
    SaldoInsuficiente,
    StockNoHabilitado,
    UuidEnUso,
)
from programas.tests.base_stock import BaseStock


class IngresoManualTests(BaseStock):
    def _ingresar(self, lineas=None, usuario=None, **extra):
        datos = {"origen": OperacionStock.Origen.DONACION}
        datos.update(extra)
        return servicio.ingresar_manual(
            usuario or self.carga,
            self.disp,
            self.edificio,
            lineas if lineas is not None else {self.colchon.pk: 5, self.frazada.pk: 2},
            **datos,
        )

    def test_suma_cada_linea_y_deja_el_libro_coherente(self):
        operacion = self._ingresar(comprobante=" R-001 ")

        self.assertFalse(operacion.ya_existia)
        self.assertEqual(operacion.tipo, OperacionStock.Tipo.INGRESO_MANUAL)
        self.assertEqual(operacion.comprobante, "R-001")
        self.assertEqual(operacion.usuario, self.carga)
        self.assertEqual(self._cantidad(self.colchon), 5)
        self.assertEqual(self._cantidad(self.frazada), 2)
        movimientos = {m.item_id: m for m in operacion.movimientos.all()}
        self.assertEqual(movimientos[self.colchon.pk].cantidad, 5)
        self.assertEqual(movimientos[self.colchon.pk].saldo_posterior, 5)
        self.assertLibroCoherente()

    def test_un_segundo_ingreso_acumula_y_el_saldo_posterior_lo_refleja(self):
        self._ingresar({self.colchon.pk: 5})
        operacion = self._ingresar({self.colchon.pk: 3})

        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertEqual(operacion.movimientos.get().saldo_posterior, 8)
        self.assertLibroCoherente()

    def test_solo_insumos_activos(self):
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar({self.viejo.pk: 1})

        self.assertIn("lineas", ctx.exception.message_dict)
        self.assertEqual(OperacionStock.objects.count(), 0)

    def test_lineas_invalidas_se_rechazan_sin_escribir_nada(self):
        casos = {
            "sin líneas": {},
            "cero": {self.colchon.pk: 0},
            "negativa": {self.colchon.pk: -1},
            "decimal": {self.colchon.pk: "1.5"},
            "enorme": {self.colchon.pk: servicio.CANTIDAD_MAXIMA + 1},
            "insumo inexistente": {999999: 1},
            "insumo repetido": [(self.colchon.pk, 1), (self.colchon.pk, 2)],
        }
        for nombre, lineas in casos.items():
            with self.subTest(nombre), self.assertRaises(ValidationError) as ctx:
                self._ingresar(lineas)
            self.assertIn("lineas", ctx.exception.message_dict)
        self.assertEqual(OperacionStock.objects.count(), 0)
        self.assertFalse(SaldoStock.objects.exists())

    def test_el_origen_es_de_un_catalogo_y_otro_pide_detalle(self):
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar(origen="REGALO")
        self.assertIn("origen", ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar(origen=OperacionStock.Origen.OTRO, origen_detalle="  ")
        self.assertIn("origen_detalle", ctx.exception.message_dict)
        operacion = self._ingresar(origen=OperacionStock.Origen.OTRO, origen_detalle="Vecinos del barrio")
        self.assertEqual(operacion.origen_detalle, "Vecinos del barrio")

    def test_largos_maximos(self):
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar(comprobante="x" * (servicio.COMPROBANTE_MAXIMO + 1))
        self.assertIn("comprobante", ctx.exception.message_dict)
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar(origen_detalle="x" * (servicio.ORIGEN_DETALLE_MAXIMO + 1))
        self.assertIn("origen_detalle", ctx.exception.message_dict)

    def test_edificio_ajeno_a_la_institucion(self):
        from programas.models import Edificio

        suelto = Edificio.objects.create(codigo="ED-SUELTO", nombre="Sin vincular")
        with self.assertRaises(ValidationError) as ctx:
            servicio.ingresar_manual(
                self.carga, self.disp, suelto, {self.colchon.pk: 1}, origen=OperacionStock.Origen.COMPRA
            )
        self.assertIn("edificio", ctx.exception.message_dict)

    def test_institucion_que_no_lleva_stock(self):
        self.tipo.maneja_stock = False
        self.tipo.save()
        with self.assertRaises(StockNoHabilitado):
            self._ingresar()
        self.assertEqual(OperacionStock.objects.count(), 0)

    def test_el_tipo_se_vuelve_a_leer_de_la_base(self):
        """El objeto que llega puede tener el tipo en memoria de antes de que se destildara."""

        obsoleto = Dispositivo.objects.select_related("tipo").get(pk=self.disp.pk)
        TipoDispositivo.objects.filter(pk=self.tipo.pk).update(maneja_stock=False)
        with self.assertRaises(StockNoHabilitado):
            servicio.ingresar_manual(
                self.carga, obsoleto, self.edificio, {self.colchon.pk: 1}, origen=OperacionStock.Origen.COMPRA
            )


class EstadoDeLaInstitucionYDelEdificioTests(BaseStock):
    """RN-010-14."""

    def _ingresar(self):
        return servicio.ingresar_manual(
            self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, origen=OperacionStock.Origen.DONACION
        )

    def test_institucion_no_activa_no_recibe_ingresos(self):
        for estado in (Dispositivo.Estado.INACTIVO, Dispositivo.Estado.CERRADO):
            with self.subTest(estado):
                Dispositivo.objects.filter(pk=self.disp.pk).update(estado=estado)
                with self.assertRaises(StockNoHabilitado) as ctx:
                    self._ingresar()
                self.assertIn("no está activa", ctx.exception.messages[0])
        self.assertEqual(OperacionStock.objects.count(), 0)

    def test_edificio_inactivo_no_recibe_ingresos(self):
        self.edificio.activo = False
        self.edificio.save()
        with self.assertRaises(StockNoHabilitado) as ctx:
            self._ingresar()
        self.assertIn("inactivo", ctx.exception.messages[0])
        self.assertEqual(OperacionStock.objects.count(), 0)

    def test_el_estado_es_el_de_la_base_y_no_el_del_objeto(self):
        obsoleta = Dispositivo.objects.select_related("tipo").get(pk=self.disp.pk)
        Dispositivo.objects.filter(pk=self.disp.pk).update(estado=Dispositivo.Estado.INACTIVO)
        with self.assertRaises(StockNoHabilitado):
            servicio.ingresar_manual(
                self.carga, obsoleta, self.edificio, {self.colchon.pk: 1}, origen=OperacionStock.Origen.DONACION
            )

    def test_el_ajuste_hacia_abajo_se_permite_con_la_institucion_inactiva_y_hacia_arriba_tambien(self):
        self._sembrar(self.colchon, 5)
        Dispositivo.objects.filter(pk=self.disp.pk).update(estado=Dispositivo.Estado.INACTIVO)

        servicio.ajustar(
            self.carga, self.disp, self.edificio, self.colchon, 0, 5, OperacionStock.MotivoAjuste.PERDIDA_ROBO
        )
        servicio.ajustar(
            self.carga, self.disp, self.edificio, self.colchon, 2, 0, OperacionStock.MotivoAjuste.CONTEO_PERIODICO
        )

        self.assertEqual(self._cantidad(self.colchon), 2)
        self.assertLibroCoherente()

    def test_edificio_inactivo_solo_deja_ajustar_hacia_abajo(self):
        self._sembrar(self.colchon, 5)
        self.edificio.activo = False
        self.edificio.save()

        with self.assertRaises(StockNoHabilitado):
            servicio.ajustar(
                self.carga, self.disp, self.edificio, self.colchon, 9, 5, OperacionStock.MotivoAjuste.CONTEO_PERIODICO
            )
        servicio.ajustar(
            self.carga, self.disp, self.edificio, self.colchon, 1, 5, OperacionStock.MotivoAjuste.ROTURA_VENCIMIENTO
        )
        self.assertEqual(self._cantidad(self.colchon), 1)


class AjusteTests(BaseStock):
    def _ajustar(self, contada, visto, motivo=OperacionStock.MotivoAjuste.CONTEO_PERIODICO, item=None, **extra):
        return servicio.ajustar(
            self.carga, self.disp, self.edificio, item or self.colchon, contada, visto, motivo, **extra
        )

    def test_hacia_abajo_calcula_el_delta_y_deja_el_motivo(self):
        self._sembrar(self.colchon, 10)

        operacion = self._ajustar(7, 10, OperacionStock.MotivoAjuste.ROTURA_VENCIMIENTO, detalle=" Humedad ")

        self.assertEqual(self._cantidad(self.colchon), 7)
        movimiento = operacion.movimientos.get()
        self.assertEqual((movimiento.cantidad, movimiento.saldo_posterior), (-3, 7))
        self.assertEqual(movimiento.tipo, MovimientoStock.Tipo.AJUSTE)
        self.assertEqual(operacion.tipo, OperacionStock.Tipo.AJUSTE)
        self.assertEqual(operacion.motivo, OperacionStock.MotivoAjuste.ROTURA_VENCIMIENTO)
        self.assertEqual(operacion.observacion, "Humedad")
        self.assertLibroCoherente()

    def test_inventario_inicial_sobre_un_insumo_que_nunca_tuvo_saldo(self):
        operacion = self._ajustar(12, 0, OperacionStock.MotivoAjuste.INVENTARIO_INICIAL)

        self.assertEqual(operacion.movimientos.get().cantidad, 12)
        self.assertEqual(self._cantidad(self.colchon), 12)
        self.assertLibroCoherente()

    def test_el_saldo_cambio_se_rechaza_con_el_saldo_actual(self):
        self._sembrar(self.colchon, 10)

        with self.assertRaises(SaldoCambio) as ctx:
            self._ajustar(7, 8)

        self.assertEqual((ctx.exception.saldo_actual, ctx.exception.saldo_visto), (10, 8))
        self.assertEqual(self._cantidad(self.colchon), 10)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.AJUSTE).count(), 0)

    def test_contar_lo_mismo_que_hay_se_rechaza_y_no_deja_movimiento(self):
        self._sembrar(self.colchon, 10)
        antes = MovimientoStock.objects.count()

        with self.assertRaises(ValidationError) as ctx:
            self._ajustar(10, 10)

        self.assertIn("cantidad_contada", ctx.exception.message_dict)
        self.assertEqual(MovimientoStock.objects.count(), antes)

    def test_el_motivo_es_de_un_catalogo_y_otro_y_correccion_piden_detalle(self):
        self._sembrar(self.colchon, 10)
        with self.assertRaises(ValidationError) as ctx:
            self._ajustar(7, 10, "ME_PARECIO")
        self.assertIn("motivo", ctx.exception.message_dict)
        for motivo in (OperacionStock.MotivoAjuste.OTRO, OperacionStock.MotivoAjuste.CORRECCION_CARGA):
            with self.subTest(motivo), self.assertRaises(ValidationError) as ctx:
                self._ajustar(7, 10, motivo, detalle="   ")
            self.assertIn("detalle", ctx.exception.message_dict)
        # Con el detalle, pasa.
        self._ajustar(7, 10, OperacionStock.MotivoAjuste.CORRECCION_CARGA, detalle="Cargué de más")
        self.assertEqual(self._cantidad(self.colchon), 7)

    def test_motivos_que_no_piden_detalle_no_lo_exigen(self):
        self._sembrar(self.colchon, 10)
        self._ajustar(7, 10, OperacionStock.MotivoAjuste.PERDIDA_ROBO)
        self.assertEqual(self._cantidad(self.colchon), 7)

    def test_entradas_invalidas(self):
        self._sembrar(self.colchon, 10)
        casos = {
            "contada negativa": ((-1, 10), "cantidad_contada"),
            "contada decimal": (("2.5", 10), "cantidad_contada"),
            "contada vacía": ((None, 10), "cantidad_contada"),
            "visto vacío": ((7, None), "saldo_visto"),
            "visto negativo": ((7, -1), "saldo_visto"),
        }
        for nombre, ((contada, visto), campo) in casos.items():
            with self.subTest(nombre), self.assertRaises(ValidationError) as ctx:
                self._ajustar(contada, visto)
            self.assertIn(campo, ctx.exception.message_dict)
        self.assertEqual(self._cantidad(self.colchon), 10)

    def test_un_insumo_desactivado_con_saldo_se_ajusta_hacia_abajo_pero_no_hacia_arriba(self):
        self._sembrar(self.viejo, 4)

        self._ajustar(1, 4, item=self.viejo)
        self.assertEqual(self._cantidad(self.viejo), 1)
        with self.assertRaises(ValidationError) as ctx:
            self._ajustar(9, 1, item=self.viejo)
        self.assertIn("item", ctx.exception.message_dict)
        self.assertEqual(self._cantidad(self.viejo), 1)

    def test_insumo_inexistente(self):
        with self.assertRaises(ValidationError) as ctx:
            self._ajustar(1, 0, item=999999)
        self.assertIn("item", ctx.exception.message_dict)

    def test_el_guarda_de_nunca_negativo_levanta_el_error_del_dominio_y_no_deja_rastro(self):
        """RN-010-03: lo que protege el ajuste hacia abajo es la guarda común de ``_asentar``. Se la ejercita con un
        delta que dejaría el saldo en negativo —lo que ``ajustar`` no puede pedir con una cantidad contada válida, pero
        sí la entrega y el traspaso del PR 2b que comparten el asiento—, y se mira que la excepción sea la del dominio
        (no ``IntegrityError``) y que no quede operación ni movimiento."""

        self._sembrar(self.colchon, 3)
        antes = (OperacionStock.objects.count(), MovimientoStock.objects.count())
        saldo = SaldoStock.objects.get(item=self.colchon)

        with self.assertRaises(SaldoInsuficiente) as ctx:
            servicio._asentar(
                usuario=self.carga,
                tipo=OperacionStock.Tipo.AJUSTE,
                dispositivo_id=self.disp.pk,
                edificio_id=self.edificio.pk,
                cambios=[(saldo, -5, MovimientoStock.Tipo.AJUSTE)],
                motivo=OperacionStock.MotivoAjuste.PERDIDA_ROBO,
            )

        self.assertEqual(ctx.exception.saldos_actuales, {self.colchon.pk: 3})
        self.assertEqual(ctx.exception.faltantes, {self.colchon.pk: (5, 3)})
        self.assertEqual((OperacionStock.objects.count(), MovimientoStock.objects.count()), antes)
        self.assertEqual(self._cantidad(self.colchon), 3)

    def test_todo_o_nada_si_una_linea_no_alcanza(self):
        self._sembrar(self.colchon, 3)
        self._sembrar(self.frazada, 9)
        colchon = SaldoStock.objects.get(item=self.colchon)
        frazada = SaldoStock.objects.get(item=self.frazada)
        antes = (OperacionStock.objects.count(), MovimientoStock.objects.count())

        with self.assertRaises(SaldoInsuficiente) as ctx:
            servicio._asentar(
                usuario=self.carga,
                tipo=OperacionStock.Tipo.AJUSTE,
                dispositivo_id=self.disp.pk,
                edificio_id=self.edificio.pk,
                cambios=[
                    (colchon, -4, MovimientoStock.Tipo.AJUSTE),
                    (frazada, -1, MovimientoStock.Tipo.AJUSTE),
                ],
                motivo=OperacionStock.MotivoAjuste.PERDIDA_ROBO,
            )

        self.assertEqual(ctx.exception.saldos_actuales, {self.colchon.pk: 3, self.frazada.pk: 9})
        self.assertEqual(list(ctx.exception.faltantes), [self.colchon.pk])
        self.assertEqual((OperacionStock.objects.count(), MovimientoStock.objects.count()), antes)
        self.assertEqual((self._cantidad(self.colchon), self._cantidad(self.frazada)), (3, 9))


class IdempotenciaTests(BaseStock):
    def setUp(self):
        super().setUp()
        self.envio = uuid.uuid4()

    def _ingresar(self, usuario=None, envio=None, cantidad=4, **extra):
        return servicio.ingresar_manual(
            usuario or self.carga,
            self.disp,
            self.edificio,
            {self.colchon.pk: cantidad},
            origen=OperacionStock.Origen.DONACION,
            uuid_cliente=envio or self.envio,
            **extra,
        )

    def test_el_mismo_usuario_recibe_la_misma_operacion_sin_mover_nada(self):
        primera = self._ingresar()
        segunda = self._ingresar()

        self.assertFalse(primera.ya_existia)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(self._cantidad(self.colchon), 4)
        self.assertEqual(MovimientoStock.objects.count(), 1)
        self.assertLibroCoherente()

    def test_acepta_el_uuid_como_texto_con_o_sin_guiones(self):
        self._ingresar(envio=str(self.envio))
        repetida = self._ingresar(envio=self.envio.hex)

        self.assertTrue(repetida.ya_existia)
        self.assertEqual(self._cantidad(self.colchon), 4)

    def test_otro_usuario_con_el_mismo_uuid_es_uuid_en_uso(self):
        self._ingresar()
        otro = self._miembro_con(self.rol_completo, "otro_carga")

        with self.assertRaises(UuidEnUso) as ctx:
            self._ingresar(usuario=otro)

        self.assertEqual(ctx.exception.code, "UUID_EN_USO")
        self.assertEqual(self._cantidad(self.colchon), 4)

    def test_otro_tipo_de_operacion_con_el_mismo_uuid_es_uuid_en_uso(self):
        self._ingresar()
        with self.assertRaises(UuidEnUso):
            servicio.ajustar(
                self.carga,
                self.disp,
                self.edificio,
                self.colchon,
                1,
                4,
                OperacionStock.MotivoAjuste.PERDIDA_ROBO,
                uuid_cliente=self.envio,
            )
        self.assertEqual(self._cantidad(self.colchon), 4)

    def test_otro_edificio_con_el_mismo_uuid_es_uuid_en_uso(self):
        self._ingresar()
        with self.assertRaises(UuidEnUso):
            servicio.ingresar_manual(
                self.carga,
                self.disp,
                self.otro_edificio,
                {self.colchon.pk: 4},
                origen=OperacionStock.Origen.DONACION,
                uuid_cliente=self.envio,
            )

    def test_un_uuid_mal_formado_es_un_error_de_validacion(self):
        with self.assertRaises(ValidationError) as ctx:
            self._ingresar(envio="no-es-un-uuid")
        self.assertIn("uuid_cliente", ctx.exception.message_dict)

    def test_un_ajuste_reenviado_no_se_aplica_dos_veces(self):
        self._sembrar(self.colchon, 10)
        envio = uuid.uuid4()
        args = (self.carga, self.disp, self.edificio, self.colchon, 6, 10, OperacionStock.MotivoAjuste.PERDIDA_ROBO)

        primera = servicio.ajustar(*args, uuid_cliente=envio)
        # El reintento llega con el mismo `saldo_visto` (el de la pantalla vieja): no es un SaldoCambio, es el mismo envío.
        segunda = servicio.ajustar(*args, uuid_cliente=envio)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(self._cantidad(self.colchon), 6)
        self.assertLibroCoherente()

    def test_el_uuid_ya_usado_vuelve_a_leerse_con_los_candados_tomados(self):
        """Dos envíos a la vez: el segundo pasa la primera lectura, espera los candados y encuentra la operación del
        primero. Se lo simula inyectando la operación entre la primera lectura y los candados."""

        original = servicio._preparar
        primera = {}

        def preparar_y_colar(pares):
            # Justo antes de bloquear, «el otro envío» ya terminó.
            if not primera:
                primera["op"] = servicio.OperacionStock.objects.create(
                    tipo=OperacionStock.Tipo.INGRESO_MANUAL,
                    dispositivo=self.disp,
                    edificio=self.edificio,
                    usuario=self.carga,
                    origen=OperacionStock.Origen.DONACION,
                    uuid_cliente=self.envio,
                )
            return original(pares)

        from unittest import mock

        with mock.patch.object(servicio, "_preparar", preparar_y_colar):
            resultado = self._ingresar()

        self.assertTrue(resultado.ya_existia)
        self.assertEqual(resultado.pk, primera["op"].pk)
        self.assertEqual(MovimientoStock.objects.count(), 0)


class SumarRecepcionDeKitTests(BaseStock):
    def _entrega(self, edificio="default", recibido=((None, 8), (None, 0)), dispositivo=None):
        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{EntregaKit.objects.count() + 1:06d}",
            dispositivo=dispositivo or self.disp,
            edificio=self.edificio if edificio == "default" else edificio,
            estado=kits.Estado.RECIBIDA,
            armada_por=self.carga,
        )
        items = (self.colchon, self.frazada)
        for item, (_, cantidad) in zip(items, recibido, strict=False):
            LineaEntrega.objects.create(
                entrega=entrega,
                item=item,
                nombre=item.nombre,
                unidad=item.unidad,
                cantidad_enviada=10,
                cantidad_recibida=cantidad,
            )
        return entrega

    def test_suma_lo_recibido_y_una_linea_en_cero_no_deja_movimiento(self):
        entrega = self._entrega()

        operacion = servicio.sumar_recepcion_de_kit(entrega, self.carga)

        self.assertEqual(operacion.tipo, OperacionStock.Tipo.INGRESO_KIT)
        self.assertEqual(operacion.entrega_kit, entrega)
        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertEqual(operacion.movimientos.count(), 1)
        self.assertFalse(MovimientoStock.objects.filter(item=self.frazada).exists())
        self.assertLibroCoherente()

    def test_lo_enviado_no_suma_solo_lo_recibido(self):
        entrega = self._entrega(recibido=((None, 3), (None, 10)))

        servicio.sumar_recepcion_de_kit(entrega, self.carga)

        self.assertEqual((self._cantidad(self.colchon), self._cantidad(self.frazada)), (3, 10))

    def test_una_entrega_suma_una_sola_vez(self):
        entrega = self._entrega()

        primera = servicio.sumar_recepcion_de_kit(entrega, self.carga)
        segunda = servicio.sumar_recepcion_de_kit(entrega, self.carga)

        self.assertFalse(primera.ya_existia)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertLibroCoherente()

    def test_sin_nada_recibido_no_hay_operacion(self):
        entrega = self._entrega(recibido=((None, 0), (None, 0)))

        self.assertIsNone(servicio.sumar_recepcion_de_kit(entrega, self.carga))
        self.assertFalse(OperacionStock.objects.exists())

    def test_una_institucion_que_no_lleva_stock_no_se_toca(self):
        otro_tipo = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock")
        sin_stock = Dispositivo.objects.create(
            tipo=otro_tipo, codigo="SS-1", nombre="Sin stock 1", estado=Dispositivo.Estado.ACTIVO
        )
        entrega = self._entrega(dispositivo=sin_stock)

        self.assertIsNone(servicio.sumar_recepcion_de_kit(entrega, self.carga))
        self.assertFalse(OperacionStock.objects.exists())
        self.assertFalse(SaldoStock.objects.exists())

    def test_una_entrega_sin_edificio_se_rechaza(self):
        entrega = self._entrega(edificio=None)

        with self.assertRaises(ValidationError) as ctx:
            servicio.sumar_recepcion_de_kit(entrega, self.carga)

        self.assertIn("edificio", ctx.exception.message_dict)
        self.assertFalse(OperacionStock.objects.exists())

    def test_no_pide_capacidad_de_stock_ni_estado_activo(self):
        """RN-010-13 y RN-010-14: la suma es consecuencia de la recepción."""

        sin_caps = self._usuario_con("solo_recibe", ())
        Dispositivo.objects.filter(pk=self.disp.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.edificio.activo = False
        self.edificio.save()

        servicio.sumar_recepcion_de_kit(self._entrega(), sin_caps)

        self.assertEqual(self._cantidad(self.colchon), 8)


class SelectoresTests(BaseStock):
    def test_saldos_de_ordena_por_nombre_y_oculta_el_inactivo_en_cero(self):
        self._sembrar(self.frazada, 2)
        self._sembrar(self.colchon, 5)
        self._sembrar(self.viejo, 0)

        filas = list(selectores.saldos_de(self.disp, self.edificio))

        self.assertEqual([f.item_id for f in filas], [self.colchon.pk, self.frazada.pk])
        self._sembrar(self.viejo, 3)
        self.assertEqual(len(list(selectores.saldos_de(self.disp, self.edificio))), 3)

    def test_movimientos_de_filtra_y_ordena_del_mas_nuevo_al_mas_viejo(self):
        servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 5}, origen="DONACION")
        servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.frazada.pk: 2}, origen="DONACION")
        servicio.ajustar(self.carga, self.disp, self.edificio, self.colchon, 1, 5, "PERDIDA_ROBO")

        todos = list(selectores.movimientos_de(self.disp, self.edificio))
        self.assertEqual([m.tipo for m in todos], ["AJUSTE", "INGRESO_MANUAL", "INGRESO_MANUAL"])
        solo_colchon = selectores.movimientos_de(self.disp, self.edificio, {"item": self.colchon.pk})
        self.assertEqual(solo_colchon.count(), 2)
        solo_ajustes = selectores.movimientos_de(self.disp, self.edificio, {"tipo": MovimientoStock.Tipo.AJUSTE})
        self.assertEqual(solo_ajustes.count(), 1)
        self.assertEqual(selectores.movimientos_de(self.disp, self.otro_edificio).count(), 0)

    def test_movimientos_de_filtra_por_dia_local_con_los_bordes_inclusivos(self):
        """``desde``/``hasta`` son días locales, inclusivos, y se traducen a un rango de ``datetime`` (nada de
        ``__date``: en ECOM compila a CONVERT_TZ y devuelve NULL)."""

        zona = timezone.get_current_timezone()
        momentos = {
            "antes": datetime(2026, 11, 10, 23, 59, 59),
            "inicio": datetime(2026, 11, 11, 0, 0, 0),
            "fin": datetime(2026, 11, 11, 23, 59, 59),
            "despues": datetime(2026, 11, 12, 0, 0, 0),
        }
        for momento in momentos.values():
            with mock.patch("django.utils.timezone.now", return_value=timezone.make_aware(momento, zona)):
                servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 1}, origen="DONACION")

        dia = date(2026, 11, 11)
        del_dia = selectores.movimientos_de(self.disp, self.edificio, {"desde": dia, "hasta": dia})
        self.assertEqual(sorted(m.saldo_posterior for m in del_dia), [2, 3])
        self.assertEqual(selectores.movimientos_de(self.disp, self.edificio, {"desde": dia}).count(), 3)
        self.assertEqual(selectores.movimientos_de(self.disp, self.edificio, {"hasta": dia}).count(), 3)

    def test_resumen_por_edificio_es_una_consulta_agrupada(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.frazada, 2)
        self._sembrar(self.viejo, 0)
        self._sembrar(self.colchon, 1, edificio=self.otro_edificio)

        with self.assertNumQueries(1):
            resumen = selectores.resumen_por_edificio(self.disp, [self.edificio.pk, self.otro_edificio.pk])

        self.assertEqual(
            resumen,
            {
                self.edificio.pk: {"insumos": 2, "unidades": 7},
                self.otro_edificio.pk: {"insumos": 1, "unidades": 1},
            },
        )

    def test_stock_por_dispositivo_e_item_suma_los_edificios_en_una_consulta(self):
        self._sembrar(self.colchon, 5)
        self._sembrar(self.colchon, 4, edificio=self.otro_edificio)
        self._sembrar(self.frazada, 0)

        with self.assertNumQueries(1):
            resultado = selectores.stock_por_dispositivo_e_item([self.disp.pk, self.disp_b.pk])

        self.assertEqual(resultado, {self.disp.pk: {self.colchon.pk: 9}})

    def test_diferencias_de_saldo_detecta_un_saldo_tocado_a_mano(self):
        servicio.ingresar_manual(self.carga, self.disp, self.edificio, {self.colchon.pk: 5}, origen="DONACION")
        self.assertEqual(selectores.diferencias_de_saldo(), [])

        SaldoStock.objects.filter(item=self.colchon).update(cantidad=6)

        diferencias = selectores.diferencias_de_saldo()
        self.assertEqual(len(diferencias), 1)
        self.assertEqual((diferencias[0]["saldo"], diferencias[0]["suma"], diferencias[0]["ultimo"]), (6, 5, 5))

    def test_diferencias_de_saldo_detecta_un_movimiento_sin_saldo(self):
        self._sembrar(self.colchon, 5)
        SaldoStock.objects.all().delete()

        diferencias = selectores.diferencias_de_saldo()

        self.assertEqual([(d["saldo"], d["suma"]) for d in diferencias], [(None, 5)])
