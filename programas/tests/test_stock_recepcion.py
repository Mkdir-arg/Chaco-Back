"""Stock, PR 3 (análisis 010, RN-010-06/07/15): la recepción de kits suma al stock del edificio (revierte RN-4.6).

Qué fija este archivo:

* ``recibir_entrega`` suma lo recibido (cada línea mayor que 0) al saldo de (institución, edificio), en la misma
  transacción: si la suma falla, la entrega no queda recibida. Un reenvío idempotente no suma dos veces.
* Una entrega sin edificio (anterior al Cambio 523) en una institución con stock exige elegir uno; se guarda en la
  entrega y tiene que ser vinculado, activo y del alcance de ``recibir_kit``.
* ``crear_entrega`` no envía a una institución con stock que no tiene edificio (decisión 10).
* No se inactiva ni se desvincula un edificio con saldo mayor que 0 (decisión 6, RN-010-15).
* Una institución cuyo tipo no lleva stock no se toca. El orden de candados es entrega → Dispositivo → Edificio → Saldo.

Mutaciones verificadas (romper la regla pone rojo el test que se nombra; ver el cuerpo del PR):

* quitar la guarda de saldo de ``_motivos_de_bloqueo`` → ``test_inactivar_con_saldo_mayor_que_cero_se_rechaza``;
* quitar la guarda de saldo de ``desvincular_edificio`` → ``test_desvincular_con_saldo_mayor_que_cero_se_rechaza``;
* mover la suma a la rama idempotente → ``test_un_reenvio_idempotente_no_suma_dos_veces`` y
  ``test_recibir_8_de_10_sube_el_saldo_en_8``;
* quitar la exigencia de edificio de ``crear_entrega`` → ``test_no_se_envia_a_una_institucion_con_stock_sin_edificio``.
"""

from unittest import mock
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError

from core.tests.candados import orden_de_candados
from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    LineaEntrega,
    MovimientoStock,
    OperacionStock,
    SaldoStock,
    TipoDispositivo,
)
from programas.selectors import stock as selectores
from programas.services import kits as servicio
from programas.services.edificios import desvincular_edificio, inactivar_edificio
from programas.tests.test_emergencia_kits import RECIBIR_KIT, BaseKits
from programas.tests.test_emergencia_kits_vistas import BaseVistasKits


class BaseRecepcionStock(BaseKits):
    def setUp(self):
        super().setUp()
        self.tipo.maneja_stock = True
        self.tipo.save()
        self.edificio = Edificio.objects.create(codigo="ED-CLUB", nombre="Edificio del club")
        self.edificio.dispositivos.add(self.club)

    def _cantidad(self, item, edificio=None, dispositivo=None):
        fila = SaldoStock.objects.filter(
            dispositivo=dispositivo or self.club, edificio=edificio or self.edificio, item=item
        ).first()
        return fila.cantidad if fila else 0

    def _legada_sin_edificio(self, dispositivo=None):
        """Una entrega anterior al Cambio 523: en camino y sin edificio. Se crea a mano, como las que quedaron en la base."""

        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{EntregaKit.objects.count() + 900:06d}",
            dispositivo=dispositivo or self.club,
            edificio=None,
            estado=EntregaKit.Estado.EN_CAMINO,
            armada_por=self.operador,
        )
        for item, cantidad in ((self.colchon, 10), (self.alimentos, 3)):
            LineaEntrega.objects.create(
                entrega=entrega, item=item, nombre=item.nombre, unidad=item.unidad, cantidad_enviada=cantidad
            )
        return entrega

    def _sembrar_saldo(self, item, cantidad, edificio=None, dispositivo=None):
        """Un saldo con su libro, sin pasar por el servicio que se prueba."""

        edificio = edificio or self.edificio
        dispositivo = dispositivo or self.club
        if cantidad:
            operacion = OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.INGRESO_MANUAL,
                dispositivo=dispositivo,
                edificio=edificio,
                usuario=self.operador,
                origen=OperacionStock.Origen.DONACION,
            )
            MovimientoStock.objects.create(
                operacion=operacion,
                tipo=MovimientoStock.Tipo.INGRESO_MANUAL,
                dispositivo=dispositivo,
                edificio=edificio,
                item=item,
                cantidad=cantidad,
                saldo_posterior=cantidad,
            )
        SaldoStock.objects.update_or_create(
            dispositivo=dispositivo, edificio=edificio, item=item, defaults={"cantidad": cantidad}
        )


class SumaAlRecibirTests(BaseRecepcionStock):
    def test_recibir_8_de_10_sube_el_saldo_en_8(self):
        entrega = self._en_camino()
        self.assertEqual(entrega.edificio, self.edificio)

        recibida = self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 3})

        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertEqual(self._cantidad(self.alimentos), 3)
        operacion = OperacionStock.objects.get(entrega_kit=recibida)
        self.assertEqual(operacion.tipo, OperacionStock.Tipo.INGRESO_KIT)
        self.assertEqual(operacion.usuario, self.guardia)
        self.assertEqual(selectores.diferencias_de_saldo(), [])

    def test_suma_lo_recibido_y_no_lo_enviado(self):
        entrega = self._en_camino()

        self._recibir(entrega, {self.colchon.pk: 12, self.alimentos.pk: 1})

        self.assertEqual((self._cantidad(self.colchon), self._cantidad(self.alimentos)), (12, 1))

    def test_se_acumula_sobre_lo_que_ya_hay(self):
        self._sembrar_saldo(self.colchon, 5)

        self._recibir(self._en_camino(), {self.colchon.pk: 8, self.alimentos.pk: 3})

        self.assertEqual(self._cantidad(self.colchon), 13)
        self.assertEqual(selectores.diferencias_de_saldo(), [])

    def test_una_linea_en_cero_no_deja_movimiento(self):
        self._recibir(self._en_camino(), {self.colchon.pk: 0, self.alimentos.pk: 3})

        self.assertFalse(MovimientoStock.objects.filter(item=self.colchon).exists())
        self.assertEqual(MovimientoStock.objects.count(), 1)

    def test_todo_en_cero_recibe_sin_operacion_de_stock(self):
        recibida = self._recibir(self._en_camino(), {self.colchon.pk: 0, self.alimentos.pk: 0})

        self.assertEqual(recibida.estado, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertFalse(OperacionStock.objects.exists())

    def test_un_reenvio_idempotente_no_suma_dos_veces(self):
        entrega = self._en_camino()
        envio = uuid4()
        cantidades = {self.colchon.pk: 8, self.alimentos.pk: 3}

        primera = self._recibir(entrega, cantidades, uuid_cliente=envio)
        segunda = self._recibir(entrega, cantidades, uuid_cliente=envio)

        self.assertFalse(primera.ya_existia)
        self.assertTrue(segunda.ya_existia)
        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertEqual(OperacionStock.objects.count(), 1)
        self.assertEqual(selectores.diferencias_de_saldo(), [])

    def test_si_la_suma_falla_la_entrega_no_queda_recibida(self):
        entrega = self._en_camino()

        with (
            mock.patch("programas.services.stock.sumar_recepcion_de_kit", side_effect=ValidationError("falla")),
            self.assertRaises(ValidationError),
        ):
            self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 3})

        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, EntregaKit.Estado.EN_CAMINO)
        self.assertIsNone(entrega.recibida_en)
        self.assertFalse(LineaEntrega.objects.filter(entrega=entrega, cantidad_recibida__isnull=False).exists())

    def test_una_entrega_a_una_institucion_sin_stock_no_toca_el_stock(self):
        tipo = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock")
        sin_stock = self._dispositivo("Sin stock", tipo=tipo)
        guardia = self._guardia("guardia_sin_stock", [RECIBIR_KIT], [sin_stock])
        entrega = servicio.marcar_en_camino(self._entrega(dispositivo=sin_stock), self.operador)

        recibida = self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 3}, usuario=guardia)

        self.assertEqual(recibida.estado, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertFalse(
            SaldoStock.objects.exists() or OperacionStock.objects.exists() or MovimientoStock.objects.exists()
        )

    def test_el_orden_de_candados_es_entrega_dispositivo_edificio_saldo(self):
        entrega = self._en_camino()

        with orden_de_candados(
            compartido="institucion",
            entrega=EntregaKit.objects,
            dispositivo=Dispositivo.objects,
            edificio=Edificio.objects,
            saldo=SaldoStock.objects,
        ) as orden:
            self._recibir(entrega, {self.colchon.pk: 8, self.alimentos.pk: 3})

        primeros = list(dict.fromkeys(orden))
        self.assertEqual(primeros[0], "entrega")
        # El Dispositivo (compartido o exclusivo) va antes que el Edificio, y el Edificio antes que el Saldo.
        self.assertLess(
            min(i for i, c in enumerate(orden) if c in ("institucion", "dispositivo")), orden.index("edificio")
        )
        self.assertLess(orden.index("edificio"), orden.index("saldo"))
        self.assertLess(orden.index("entrega"), orden.index("saldo"))
        self.assertNotIn("entrega", orden[orden.index("saldo") :])


class EntregaSinEdificioTests(BaseRecepcionStock):
    def _datos(self):
        return {self.colchon.pk: 8, self.alimentos.pk: 3}

    def test_exige_elegir_un_edificio_y_no_cambia_nada(self):
        entrega = self._legada_sin_edificio()

        with self.assertRaises(ValidationError) as ctx:
            self._recibir(entrega, self._datos())

        self.assertIn("edificio", ctx.exception.message_dict)
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, EntregaKit.Estado.EN_CAMINO)
        self.assertIsNone(entrega.edificio_id)
        self.assertFalse(OperacionStock.objects.exists())

    def test_con_el_edificio_elegido_lo_guarda_en_la_entrega_y_suma(self):
        entrega = self._legada_sin_edificio()

        recibida = self._recibir(entrega, self._datos(), edificio=self.edificio)

        self.assertEqual(recibida.edificio_id, self.edificio.pk)
        entrega.refresh_from_db()
        self.assertEqual(entrega.edificio_id, self.edificio.pk)
        self.assertEqual(self._cantidad(self.colchon), 8)
        self.assertEqual(selectores.diferencias_de_saldo(), [])

    def test_acepta_el_pk(self):
        entrega = self._legada_sin_edificio()

        self._recibir(entrega, self._datos(), edificio=self.edificio.pk)

        self.assertEqual(self._cantidad(self.colchon), 8)

    def test_un_edificio_no_vinculado_se_rechaza(self):
        suelto = Edificio.objects.create(codigo="ED-SUELTO", nombre="Sin vincular")
        entrega = self._legada_sin_edificio()

        with self.assertRaises(ValidationError) as ctx:
            self._recibir(entrega, self._datos(), edificio=suelto)

        self.assertIn("edificio", ctx.exception.message_dict)
        self.assertFalse(OperacionStock.objects.exists())

    def test_un_edificio_de_otra_institucion_se_rechaza(self):
        ajeno = Edificio.objects.create(codigo="ED-ESC", nombre="De la escuela")
        ajeno.dispositivos.add(self.escuela)
        entrega = self._legada_sin_edificio()

        with self.assertRaises(ValidationError) as ctx:
            self._recibir(entrega, self._datos(), edificio=ajeno)

        self.assertIn("edificio", ctx.exception.message_dict)

    def test_un_edificio_inactivo_se_rechaza(self):
        Edificio.objects.filter(pk=self.edificio.pk).update(activo=False)
        entrega = self._legada_sin_edificio()

        with self.assertRaises(ValidationError) as ctx:
            self._recibir(entrega, self._datos(), edificio=self.edificio)

        self.assertIn("edificio", ctx.exception.message_dict)
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, EntregaKit.Estado.EN_CAMINO)

    def test_sin_alcance_de_recibir_en_el_dispositivo_es_permission_denied(self):
        entrega = self._legada_sin_edificio()

        with self.assertRaises(PermissionDenied):
            self._recibir(entrega, self._datos(), edificio=self.edificio, usuario=self.guardia_escuela)

        self.assertFalse(OperacionStock.objects.exists())

    def test_una_institucion_sin_stock_ignora_el_edificio_y_la_deja_sin_edificio(self):
        tipo = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock")
        sin_stock = self._dispositivo("Sin stock", tipo=tipo)
        guardia = self._guardia("guardia_sin_stock", [RECIBIR_KIT], [sin_stock])
        entrega = self._legada_sin_edificio(sin_stock)

        # Se pasa un edificio —vinculado a OTRA institución— para probar que se ignora de verdad.
        recibida = self._recibir(entrega, self._datos(), usuario=guardia, edificio=self.edificio)

        self.assertEqual(recibida.estado, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS)
        self.assertIsNone(recibida.edificio_id)
        entrega.refresh_from_db()
        self.assertIsNone(entrega.edificio_id)
        self.assertFalse(OperacionStock.objects.exists())

    def test_sin_edificios_activos_dice_que_falta_vincular_uno(self):
        Edificio.objects.filter(pk=self.edificio.pk).update(activo=False)
        entrega = self._legada_sin_edificio()

        with self.assertRaises(ValidationError) as ctx:
            self._recibir(entrega, self._datos())

        self.assertEqual(
            ctx.exception.message_dict["edificio"],
            [servicio.SIN_EDIFICIO_PARA_EL_STOCK.format(nombre=self.club.nombre)],
        )

    def test_con_edificios_activos_y_sin_elegir_pide_elegir(self):
        with self.assertRaises(ValidationError) as ctx:
            self._recibir(self._legada_sin_edificio(), self._datos())

        self.assertEqual(ctx.exception.message_dict["edificio"], [servicio.ELEGI_EL_EDIFICIO_DE_LA_RECEPCION])

    def test_el_orden_de_candados_con_edificio_elegido(self):
        """La rama de la entrega sin edificio toma Dispositivo y Edificio ANTES de escribir el saldo (M4)."""

        entrega = self._legada_sin_edificio()

        with orden_de_candados(
            compartido="institucion",
            entrega=EntregaKit.objects,
            dispositivo=Dispositivo.objects,
            edificio=Edificio.objects,
            saldo=SaldoStock.objects,
        ) as orden:
            self._recibir(entrega, self._datos(), edificio=self.edificio)

        self.assertEqual(orden[0], "entrega")
        self.assertLess(
            min(i for i, c in enumerate(orden) if c in ("institucion", "dispositivo")), orden.index("edificio")
        )
        self.assertLess(orden.index("edificio"), orden.index("saldo"))

    def test_el_reenvio_idempotente_no_pide_edificio_ni_suma(self):
        entrega = self._legada_sin_edificio()
        envio = uuid4()
        self._recibir(entrega, self._datos(), edificio=self.edificio, uuid_cliente=envio)

        repetida = self._recibir(entrega, self._datos(), uuid_cliente=envio)

        self.assertTrue(repetida.ya_existia)
        self.assertEqual(self._cantidad(self.colchon), 8)


class CrearEntregaConStockTests(BaseRecepcionStock):
    def test_no_se_envia_a_una_institucion_con_stock_sin_edificio(self):
        self.edificio.dispositivos.remove(self.club)

        with self.assertRaises(ValidationError) as ctx:
            self._entrega()

        mensaje = ctx.exception.message_dict["edificio"][0]
        self.assertIn("vinculale", mensaje)
        self.assertFalse(EntregaKit.objects.exists())

    def test_una_institucion_sin_stock_sigue_pudiendo_recibir_sin_edificio(self):
        tipo = TipoDispositivo.objects.create(codigo="SIN-STOCK", nombre="Sin stock")
        sin_stock = self._dispositivo("Sin stock", tipo=tipo)
        guardia = self._guardia("guardia_sin_stock_2", [RECIBIR_KIT], [sin_stock])

        entrega = servicio.marcar_en_camino(self._entrega(dispositivo=sin_stock), self.operador)
        recibida = self._recibir(entrega, usuario=guardia)

        self.assertIsNone(entrega.edificio_id)
        self.assertEqual(recibida.estado, EntregaKit.Estado.RECIBIDA)
        self.assertIsNone(recibida.edificio_id)

    def test_reponer_hereda_el_edificio_y_exige_que_siga_vinculado(self):
        original = self._recibida_con_faltante()
        self.edificio.dispositivos.remove(self.club)

        with self.assertRaises(ValidationError) as ctx:
            self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertEqual(ctx.exception.message_dict["edificio"], [servicio.EDIFICIO_NO_ES_DEL_DISPOSITIVO])
        original.refresh_from_db()
        self.assertEqual(original.estado, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS)

    def test_reponer_con_el_edificio_vinculado_funciona(self):
        original = self._recibida_con_faltante()

        reposicion = self._entrega(lineas=[(self.colchon, 2)], repone_a=original)

        self.assertEqual(reposicion.edificio_id, self.edificio.pk)

    def test_con_un_edificio_activo_queda_fijo(self):
        self.assertEqual(self._entrega().edificio, self.edificio)


class GuardasDeEdificioConSaldoTests(BaseRecepcionStock):
    def setUp(self):
        super().setUp()
        self.admin = self._admin_del_programa()

    def _admin_del_programa(self):
        from django.contrib.auth.models import User

        return User.objects.create_superuser(username="super_stock", password="x")

    def test_inactivar_con_saldo_mayor_que_cero_se_rechaza(self):
        self._sembrar_saldo(self.colchon, 3)

        with self.assertRaises(ValidationError) as ctx:
            inactivar_edificio(edificio=self.edificio, usuario=self.admin)

        self.assertIn("stock en 1 insumo", ctx.exception.message_dict["__all__"][0])
        self.assertTrue(Edificio.objects.get(pk=self.edificio.pk).activo)

    def test_inactivar_con_saldo_en_cero_pasa(self):
        self._sembrar_saldo(self.colchon, 0)

        inactivar_edificio(edificio=self.edificio, usuario=self.admin)

        self.assertFalse(Edificio.objects.get(pk=self.edificio.pk).activo)

    def test_inactivar_cuenta_el_stock_de_cualquier_institucion_del_predio(self):
        self.edificio.dispositivos.add(self.escuela)
        self._sembrar_saldo(self.alimentos, 2, dispositivo=self.escuela)

        with self.assertRaises(ValidationError):
            inactivar_edificio(edificio=self.edificio, usuario=self.admin)

    def test_el_stock_de_otro_edificio_no_bloquea(self):
        otro = Edificio.objects.create(codigo="ED-OTRO", nombre="Otro")
        otro.dispositivos.add(self.club)
        self._sembrar_saldo(self.colchon, 3, edificio=otro)

        inactivar_edificio(edificio=self.edificio, usuario=self.admin)

        self.assertFalse(Edificio.objects.get(pk=self.edificio.pk).activo)

    def test_desvincular_con_saldo_mayor_que_cero_se_rechaza(self):
        self._sembrar_saldo(self.colchon, 3)

        with self.assertRaises(ValidationError) as ctx:
            desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertIn("tiene stock en el edificio", ctx.exception.message_dict["__all__"][0])
        self.assertTrue(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_desvincular_con_saldo_en_cero_pasa(self):
        self._sembrar_saldo(self.colchon, 0)

        desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertFalse(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_desvincular_con_una_entrega_por_recibir_hacia_el_edificio_se_rechaza(self):
        self._entrega()  # PREPARADA

        with self.assertRaises(ValidationError) as ctx:
            desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        mensaje = ctx.exception.message_dict["__all__"][0]
        self.assertIn("1 entrega de kits por recibir", mensaje)
        self.assertIn("Recibí la entrega", mensaje)
        self.assertTrue(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_desvincular_con_una_entrega_en_camino_hacia_el_edificio_se_rechaza(self):
        self._en_camino()

        with self.assertRaises(ValidationError) as ctx:
            desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertIn("1 entrega de kits por recibir", ctx.exception.message_dict["__all__"][0])
        self.assertTrue(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_desvincular_con_la_entrega_ya_recibida_pasa(self):
        self._recibir(self._en_camino(), {self.colchon.pk: 0, self.alimentos.pk: 0})

        desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertFalse(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_la_entrega_a_otro_edificio_o_a_otra_institucion_no_impide_desvincular(self):
        otro = Edificio.objects.create(codigo="ED-OTRO2", nombre="Otro 2")
        otro.dispositivos.add(self.club)
        self._entrega(edificio=otro)
        self.edificio.dispositivos.add(self.escuela)
        self._entrega(dispositivo=self.escuela, edificio=self.edificio)

        desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertFalse(self.edificio.dispositivos.filter(pk=self.club.pk).exists())

    def test_el_saldo_de_otra_institucion_no_impide_desvincular_a_esta(self):
        self.edificio.dispositivos.add(self.escuela)
        self._sembrar_saldo(self.alimentos, 2, dispositivo=self.escuela)

        desvincular_edificio(edificio=self.edificio, dispositivo=self.club, usuario=self.admin)

        self.assertFalse(self.edificio.dispositivos.filter(pk=self.club.pk).exists())


class RecepcionWebConStockTests(BaseVistasKits):
    """La pantalla de recibir (``emergencia:dispositivo_kit_recibir``): el desplegable de edificio y la línea del stock."""

    def setUp(self):
        super().setUp()
        self.tipo.maneja_stock = True
        self.tipo.save()
        self.edificio = Edificio.objects.create(codigo="ED-CLUB", nombre="Edificio del club")
        self.edificio.dispositivos.add(self.club)
        self.client.force_login(self.guardia)

    def _legada(self):
        entrega = EntregaKit.objects.create(
            numero="2026-K-000990",
            dispositivo=self.club,
            edificio=None,
            estado=EntregaKit.Estado.EN_CAMINO,
            armada_por=self.operador,
        )
        for item, cantidad in ((self.colchon, 10), (self.alimentos, 3)):
            LineaEntrega.objects.create(
                entrega=entrega, item=item, nombre=item.nombre, unidad=item.unidad, cantidad_enviada=cantidad
            )
        return entrega

    def _cuerpo(self, **extra):
        cantidades = {f"cantidad_{self.colchon.pk}": 8, f"cantidad_{self.alimentos.pk}": 3}
        return {**cantidades, "remito": self._remito_http(), **extra}

    def _url_recibir(self, entrega):
        return self._url("dispositivo_kit_recibir", self.club.pk, entrega.pk)

    def test_una_entrega_con_edificio_muestra_la_linea_y_no_pide_elegir(self):
        respuesta = self.client.get(self._url_recibir(self._en_camino()))

        self.assertContains(respuesta, "Lo recibido se suma al stock del edificio.")
        self.assertNotIn("edificio", respuesta.context["form"].fields)

    def test_una_entrega_sin_edificio_pide_elegirlo(self):
        respuesta = self.client.get(self._url_recibir(self._legada()))

        self.assertContains(respuesta, 'name="edificio"')
        self.assertContains(respuesta, "Edificio del club")
        self.assertContains(respuesta, "Lo recibido se suma al stock del edificio.")

    def test_el_desplegable_solo_ofrece_edificios_activos_de_la_institucion(self):
        inactivo = Edificio.objects.create(codigo="ED-INA", nombre="Edificio inactivo", activo=False)
        inactivo.dispositivos.add(self.club)
        ajeno = Edificio.objects.create(codigo="ED-AJE", nombre="Edificio ajeno")
        ajeno.dispositivos.add(self.escuela)

        respuesta = self.client.get(self._url_recibir(self._legada()))

        self.assertContains(respuesta, "Edificio del club")
        self.assertNotContains(respuesta, "Edificio inactivo")
        self.assertNotContains(respuesta, "Edificio ajeno")

    def test_recibir_eligiendo_el_edificio_suma_al_stock(self):
        entrega = self._legada()

        respuesta = self.client.post(self._url_recibir(entrega), self._cuerpo(edificio=self.edificio.pk))

        self.assertEqual(respuesta.status_code, 302)
        entrega.refresh_from_db()
        self.assertEqual(entrega.edificio_id, self.edificio.pk)
        saldo = SaldoStock.objects.get(dispositivo=self.club, edificio=self.edificio, item=self.colchon)
        self.assertEqual(saldo.cantidad, 8)

    def test_recibir_sin_elegir_el_edificio_vuelve_con_el_error_y_no_recibe(self):
        entrega = self._legada()

        respuesta = self.client.post(self._url_recibir(entrega), self._cuerpo())

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.context["form"].errors)
        entrega.refresh_from_db()
        self.assertEqual(entrega.estado, EntregaKit.Estado.EN_CAMINO)
        self.assertFalse(OperacionStock.objects.exists())

    def test_un_edificio_ajeno_en_el_post_se_rechaza(self):
        ajeno = Edificio.objects.create(codigo="ED-AJE", nombre="Edificio ajeno")
        ajeno.dispositivos.add(self.escuela)
        entrega = self._legada()

        respuesta = self.client.post(self._url_recibir(entrega), self._cuerpo(edificio=ajeno.pk))

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(OperacionStock.objects.exists())

    def test_una_institucion_sin_stock_no_muestra_la_linea_ni_el_desplegable(self):
        self.tipo.maneja_stock = False
        self.tipo.save()

        respuesta = self.client.get(self._url_recibir(self._legada()))

        self.assertNotContains(respuesta, "se suma al stock")
        self.assertNotContains(respuesta, 'name="edificio"')
