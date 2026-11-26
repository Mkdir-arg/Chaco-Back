"""Stock, PR 2a (análisis 010, RN-010-13): cada función del servicio exige su capacidad **adentro**.

Todos los tests llaman al servicio directo, no a una vista: la vista no es la única barrera. Cada guarda se verificó
por mutación (sacar el ``_exigir`` de ``ingresar_manual`` o de ``ajustar`` pone rojo su test).
"""

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied

from core import rbac
from programas.models import MiembroEquipoDispositivo, MovimientoStock, OperacionStock
from programas.services import dispositivos as dispositivos_servicio
from programas.services import stock as servicio
from programas.tests.base_stock import BaseStock

Alcance = MiembroEquipoDispositivo.Alcance


class _Acciones:
    """Las dos escrituras de este PR, con argumentos válidos, para correrlas con cada usuario."""

    def ingresar(self, usuario, edificio=None):
        return servicio.ingresar_manual(
            usuario, self.disp, edificio or self.edificio, {self.colchon.pk: 1}, origen=OperacionStock.Origen.DONACION
        )

    def ajustar(self, usuario, edificio=None, visto=5):
        return servicio.ajustar(
            usuario,
            self.disp,
            edificio or self.edificio,
            self.colchon,
            0,
            visto,
            OperacionStock.MotivoAjuste.PERDIDA_ROBO,
        )


class PermisoDelServicioTests(_Acciones, BaseStock):
    def test_sin_stock_ingresar_el_ingreso_manual_levanta_permission_denied(self):
        usuario = self._usuario_con("solo_ver_y_ajusta", ("stock.ver", "stock.ajustar", "stock.entregar"))

        with self.assertRaises(PermissionDenied):
            self.ingresar(usuario)

        self.assertFalse(OperacionStock.objects.exists())
        self.assertFalse(MovimientoStock.objects.exists())

    def test_sin_stock_ajustar_el_ajuste_levanta_permission_denied(self):
        self._sembrar(self.colchon, 5)
        usuario = self._usuario_con("sin_ajuste", ("stock.ver", "stock.ingresar", "stock.entregar"))

        with self.assertRaises(PermissionDenied):
            self.ajustar(usuario)

        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_cada_accion_exige_ademas_stock_ver(self):
        self._sembrar(self.colchon, 5)
        sin_ver = self._usuario_con("sin_ver", ("stock.ingresar", "stock.ajustar", "stock.entregar"))

        with self.assertRaises(PermissionDenied):
            self.ingresar(sin_ver)
        with self.assertRaises(PermissionDenied):
            self.ajustar(sin_ver)
        self.assertEqual(self._cantidad(self.colchon), 5)

    def test_con_la_capacidad_y_stock_ver_pasa(self):
        ingresa = self._usuario_con("ingresa", ("stock.ver", "stock.ingresar"))
        ajusta = self._usuario_con("ajusta", ("stock.ver", "stock.ajustar"))

        self.ingresar(ingresa)
        self.ajustar(ajusta, visto=1)

        self.assertEqual(self._cantidad(self.colchon), 0)

    def test_un_usuario_sin_ningun_rol_o_anonimo_no_puede(self):
        sin_rol = self._fresco(self._otro_usuario("sin_rol"))

        for usuario in (sin_rol, AnonymousUser(), None):
            with self.subTest(usuario), self.assertRaises(PermissionDenied):
                self.ingresar(usuario)
        self.assertFalse(OperacionStock.objects.exists())

    def test_quien_no_es_del_equipo_de_esa_institucion_no_puede(self):
        rol = self._rol("Stock de la otra", ("dispositivo.ver", "stock.ver", "stock.ingresar", "stock.ajustar"))
        ajeno = self._miembro_con(rol, "de_la_otra", dispositivo=self.disp_b)

        with self.assertRaises(PermissionDenied):
            self.ingresar(ajeno)

    def test_un_rol_inactivo_o_de_otro_programa_no_habilita(self):
        capacidades = ("dispositivo.ver", "stock.ver", "stock.ingresar")
        inactivo = self._miembro_con(self._rol("Inactivo", capacidades, activo=False), "rol_inactivo")
        de_becas = self._miembro_con(self._rol("De becas", capacidades, programa=self.becas), "rol_becas")

        for usuario in (inactivo, de_becas):
            with self.subTest(usuario.username), self.assertRaises(PermissionDenied):
                self.ingresar(usuario)

    def test_el_superusuario_y_el_admin_del_programa_pueden(self):
        superusuario = User.objects.create_superuser(username="super", password="x")
        self.ingresar(self._fresco(superusuario))
        admin = self._usuario_con(
            "admin_programa", ("stock.ver", "stock.ingresar", dispositivos_servicio.CAP_CONFIGURAR)
        )
        self.ingresar(admin)
        self.assertEqual(self._cantidad(self.colchon), 2)

    def test_ver_todos_lee_el_stock_de_la_red_pero_no_opera(self):
        """RN-010-13 y decisión 9: ``dispositivo.ver_todos`` amplía ``stock.ver`` a toda la red, nunca las de operar."""

        rol = self._rol(
            "Supervisión", ("dispositivo.ver", "dispositivo.ver_todos", "stock.ver", "stock.ingresar", "stock.ajustar")
        )
        supervisor = self._fresco(self._usuario("supervisor", rol))

        self.assertTrue(servicio.puede_ver_stock(supervisor, self.disp, self.edificio.pk))
        self.assertTrue(servicio.puede_ver_stock(supervisor, self.disp_b, self.edificio.pk))
        for puede in (servicio.puede_ingresar, servicio.puede_ajustar, servicio.puede_entregar):
            self.assertFalse(puede(supervisor, self.disp, self.edificio.pk))
        with self.assertRaises(PermissionDenied):
            self.ingresar(supervisor)
        with self.assertRaises(PermissionDenied):
            self.ajustar(supervisor)

    def test_ver_todos_sin_stock_ver_no_ve_el_stock(self):
        rol = self._rol("Solo dispositivos", ("dispositivo.ver", "dispositivo.ver_todos"))
        usuario = self._fresco(self._usuario("sin_stock_ver", rol))

        self.assertFalse(servicio.puede_ver_stock(usuario, self.disp, self.edificio.pk))


class AlcanceDeEdificiosTests(_Acciones, BaseStock):
    def _miembro_de_edificios(self, nombre, edificios, capacidades=("stock.ver", "stock.ingresar", "stock.ajustar")):
        rol = self._rol(f"Rol {nombre}", ("dispositivo.ver", *capacidades))
        usuario = self._usuario(nombre, rol)
        miembro = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.disp, usuario=usuario, rol=rol, alcance=Alcance.EDIFICIOS
        )
        miembro.edificios.set(edificios)
        return self._fresco(usuario)

    def test_con_alcance_de_un_edificio_opera_ese_y_no_el_otro(self):
        de_uno = self._miembro_de_edificios("de_uno", [self.edificio])

        self.ingresar(de_uno, self.edificio)
        with self.assertRaises(PermissionDenied):
            self.ingresar(de_uno, self.otro_edificio)
        self._sembrar(self.colchon, 5, edificio=self.otro_edificio)
        with self.assertRaises(PermissionDenied):
            servicio.ajustar(
                de_uno, self.disp, self.otro_edificio, self.colchon, 1, 5, OperacionStock.MotivoAjuste.PERDIDA_ROBO
            )
        self.assertEqual(self._cantidad(self.colchon, edificio=self.otro_edificio), 5)

    def test_alcance_edificios_sin_edificios_no_alcanza_nada(self):
        """Fail-closed: un conjunto vacío nunca equivale a «toda la institución»."""

        de_ninguno = self._miembro_de_edificios("de_ninguno", [])

        with self.assertRaises(PermissionDenied):
            self.ingresar(de_ninguno)

    def test_la_capacidad_de_ver_de_un_edificio_no_da_la_de_operar_en_otro(self):
        ve_uno = self._miembro_de_edificios("ve_uno", [self.edificio], capacidades=("stock.ver",))
        self.assertTrue(servicio.puede_ver_stock(ve_uno, self.disp, self.edificio.pk))
        self.assertFalse(servicio.puede_ver_stock(ve_uno, self.disp, self.otro_edificio.pk))
        self.assertFalse(servicio.puede_ingresar(ve_uno, self.disp, self.edificio.pk))


class EntregarExigeCiudadanoVerTests(BaseStock):
    def test_entregar_exige_ciudadano_ver_ademas_de_stock_entregar(self):
        sin_ciudadano = self._usuario_con("sin_ciudadano", ("stock.ver", "stock.entregar"))
        con_ciudadano = self._usuario_con("con_ciudadano", ("stock.ver", "stock.entregar", "ciudadano.ver"))
        solo_ciudadano = self._usuario_con("solo_ciudadano", ("stock.ver", "ciudadano.ver"))

        self.assertFalse(servicio.puede_entregar(sin_ciudadano, self.disp, self.edificio.pk))
        self.assertTrue(servicio.puede_entregar(con_ciudadano, self.disp, self.edificio.pk))
        self.assertFalse(servicio.puede_entregar(solo_ciudadano, self.disp, self.edificio.pk))
        self.assertTrue(rbac.puede(con_ciudadano, "ciudadano.ver"))
