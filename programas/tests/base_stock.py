"""Base común de los tests del servicio de stock (análisis 010, PR 2a): una institución que lleva stock con un edificio
vinculado, dos insumos activos y uno desactivado, y usuarios con cada combinación de capacidades de stock."""

from django.contrib.auth.models import User

from programas.models import Edificio, MovimientoStock, OperacionStock, SaldoStock, TipoKit
from programas.selectors import stock as selectores
from programas.tests.test_dispositivos_equipo_410 import BaseEquipo

TODAS_LAS_DE_STOCK = ("dispositivo.ver", "stock.ver", "stock.entregar", "stock.ingresar", "stock.ajustar")


class BaseStock(BaseEquipo):
    def setUp(self):
        super().setUp()
        self.tipo.maneja_stock = True
        self.tipo.save()
        self.disp = self.disp_a
        self.edificio = Edificio.objects.create(codigo="ED-S1", nombre="Edificio stock")
        self.edificio.dispositivos.add(self.disp)
        self.otro_edificio = Edificio.objects.create(codigo="ED-S2", nombre="Otro edificio")
        self.otro_edificio.dispositivos.add(self.disp)
        self.colchon = TipoKit.objects.create(nombre="Colchón stock", unidad="unidad")
        self.frazada = TipoKit.objects.create(nombre="Frazada stock", unidad="unidad")
        self.viejo = TipoKit.objects.create(nombre="Insumo viejo", unidad="unidad", activo=False)
        rol = self._rol("Stock completo", TODAS_LAS_DE_STOCK)
        self.rol_completo = rol
        self.carga = self._miembro_con(rol, "carga")

    def _miembro_con(self, rol, nombre, dispositivo=None):
        usuario = self._usuario(nombre, rol)
        self._miembro(dispositivo or self.disp, usuario, rol)
        return self._fresco(usuario)

    def _usuario_con(self, nombre, capacidades, dispositivo=None):
        """Un miembro del equipo cuyo rol tiene **solo** ``capacidades`` (más ``dispositivo.ver``)."""

        rol = self._rol(f"Rol {nombre}", ("dispositivo.ver", *capacidades))
        return self._miembro_con(rol, nombre, dispositivo)

    def _cantidad(self, item, edificio=None, dispositivo=None):
        fila = SaldoStock.objects.filter(
            dispositivo=dispositivo or self.disp, edificio=edificio or self.edificio, item=item
        ).first()
        return fila.cantidad if fila else 0

    def _sembrar(self, item, cantidad, edificio=None, dispositivo=None):
        """Deja un saldo con su libro coherente, sin pasar por el servicio que se prueba."""

        edificio = edificio or self.edificio
        dispositivo = dispositivo or self.disp
        if cantidad:
            operacion = OperacionStock.objects.create(
                tipo=OperacionStock.Tipo.INGRESO_MANUAL,
                dispositivo=dispositivo,
                edificio=edificio,
                usuario=self.carga,
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

    def assertLibroCoherente(self):
        """RN-010-05: saldo == Σ movimientos == saldo_posterior del último, para cada clave."""

        self.assertEqual(selectores.diferencias_de_saldo(), [])

    def _otro_usuario(self, nombre="otro"):
        return User.objects.create_user(username=nombre, password="x")
