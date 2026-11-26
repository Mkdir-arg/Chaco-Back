"""Stock, PR 2b (análisis 010, RN-010-19): la entrega a una persona y el traspaso, contra el motor real.

Igual que ``test_stock_concurrencia_mysql``: ``@tag("mysql")`` y se saltea sin motor real. A queda detenido con el
candado del edificio tomado y B tiene que esperar (``LOCK WAIT``); si alguien saca el candado, B atraviesa y
``en_paralelo`` lo reporta. Después se afirma el saldo exacto y el invariante del libro.
"""

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TransactionTestCase, tag

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from legajos.models import Ciudadano
from programas.models import (
    Dispositivo,
    Edificio,
    MiembroEquipoDispositivo,
    MovimientoStock,
    OperacionStock,
    Programa,
    SaldoStock,
    TipoDispositivo,
    TipoKit,
)
from programas.selectors import stock as selectores
from programas.services import stock as servicio
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from users.models import RolMeta

EDIFICIO_BLOQUEADO = punto_critico(Edificio, "_preparar")
CAPACIDADES = ("dispositivo.ver", "stock.ver", "stock.entregar", "stock.ingresar", "ciudadano.ver")


@tag("mysql")
class EntregaYTraspasoConcurrentesTests(MotorRealMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="CIS-ENT", nombre="CIS", maneja_stock=True)
        self.disp_a = self._dispositivo(tipo, "CIS-EA", "CIS A")
        self.disp_b = self._dispositivo(tipo, "CIS-EB", "CIS B")
        self.edificio_a = self._edificio("ED-EA", self.disp_a)
        self.edificio_b = self._edificio("ED-EB", self.disp_b)
        self.colchon = TipoKit.objects.create(nombre="Colchón entrega", unidad="unidad")
        self.juana = self._usuario("juana_ent", self.disp_a, self.disp_b)
        self.pedro = self._usuario("pedro_ent", self.disp_a, self.disp_b)
        self.ana = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Paz")
        self.beto = Ciudadano.objects.create(dni="30111333", nombre="Beto", apellido="Ruiz")
        self._sembrar(self.disp_a, self.edificio_a, 1)
        self._sembrar(self.disp_b, self.edificio_b, 1)

    def _dispositivo(self, tipo, codigo, nombre):
        return Dispositivo.objects.create(tipo=tipo, codigo=codigo, nombre=nombre, estado=Dispositivo.Estado.ACTIVO)

    def _edificio(self, codigo, dispositivo):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(dispositivo)
        return edificio

    def _usuario(self, nombre, *dispositivos):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(c) for c in CAPACIDADES])
        usuario = User.objects.create_user(username=nombre)
        usuario.groups.add(rol)
        for dispositivo in dispositivos:
            MiembroEquipoDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, rol=rol)
        return usuario

    def _fresco(self, usuario):
        """``rbac`` memoiza las capacidades en el objeto, y cada hilo necesita el suyo."""

        return User.objects.get(pk=usuario.pk)

    def _sembrar(self, dispositivo, edificio, cantidad):
        servicio.ingresar_manual(
            self._fresco(self.juana), dispositivo, edificio, {self.colchon.pk: cantidad}, origen="COMPRA"
        )

    def _saldo(self, dispositivo, edificio):
        return SaldoStock.objects.get(dispositivo=dispositivo, edificio=edificio, item=self.colchon).cantidad

    def _entregar(self, usuario, persona):
        def operacion():
            return servicio.entregar_a_persona(
                self._fresco(usuario), self.disp_a, self.edificio_a, persona.dni, {self.colchon.pk: 1}
            )

        return operacion

    def _traspasar(self, usuario, origen, destino):
        def operacion():
            return servicio.traspasar(
                self._fresco(usuario), origen[0], origen[1], destino[0], destino[1], {self.colchon.pk: 1}
            )

        return operacion

    def assertInvarianteDelLibro(self):
        self.assertEqual(selectores.diferencias_de_saldo(), [])
        total = sum(MovimientoStock.objects.filter(item=self.colchon).values_list("cantidad", flat=True))
        self.assertEqual(total, sum(SaldoStock.objects.filter(item=self.colchon).values_list("cantidad", flat=True)))

    def test_dos_entregas_del_ultimo_insumo_una_pasa_y_la_otra_no_tiene_saldo(self):
        resultados, errores = en_paralelo(
            self._entregar(self.juana, self.ana), self._entregar(self.pedro, self.beto), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], servicio.SaldoInsuficiente)
        self.assertEqual(self._saldo(self.disp_a, self.edificio_a), 0)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.ENTREGA_PERSONA).count(), 1)
        self.assertInvarianteDelLibro()

    def test_la_entrega_que_pierde_no_deja_un_legajo_a_medio_crear(self):
        """B es una persona **sin legajo**: si pierde por saldo, su legajo no puede haberse creado.

        Lo garantiza que el saldo se rechaza **antes** del alta (``_exigir_saldo`` va antes de ``dar_de_alta``); sin el
        ``atomic`` este test cae por ``TransactionManagementError``, no por el legajo. Mover el alta antes del saldo lo
        detecta ``test_stock_ronda2``."""

        resultados, errores = en_paralelo(
            self._entregar(self.juana, self.ana),
            self._entregar_a_nueva(self.pedro, "30999888"),
            punto_a=EDIFICIO_BLOQUEADO,
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], servicio.SaldoInsuficiente)
        self.assertFalse(Ciudadano.objects.filter(dni="30999888").exists())
        self.assertInvarianteDelLibro()

    def _entregar_a_nueva(self, usuario, dni):
        def operacion():
            return servicio.entregar_a_persona(
                self._fresco(usuario),
                self.disp_a,
                self.edificio_a,
                dni,
                {self.colchon.pk: 1},
                sexo="F",
                nombre="Nueva",
                apellido="Persona",
            )

        return operacion

    def test_dos_traspasos_cruzados_no_se_interbloquean_y_los_dos_se_aplican(self):
        """A→B y B→A a la vez piden las mismas filas en el mismo orden: ninguno espera al otro en círculo."""

        a, b = (self.disp_a, self.edificio_a), (self.disp_b, self.edificio_b)

        resultados, errores = en_paralelo(
            self._traspasar(self.juana, a, b), self._traspasar(self.pedro, b, a), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(errores, [])
        self.assertEqual(len(resultados), 2)
        self.assertEqual(self._saldo(*a), 1)
        self.assertEqual(self._saldo(*b), 1)
        self.assertEqual(OperacionStock.objects.filter(tipo=OperacionStock.Tipo.TRASPASO).count(), 2)
        self.assertInvarianteDelLibro()

    def test_dos_traspasos_del_ultimo_insumo_desde_el_mismo_origen_uno_solo_sale(self):
        a, b = (self.disp_a, self.edificio_a), (self.disp_b, self.edificio_b)

        resultados, errores = en_paralelo(
            self._traspasar(self.juana, a, b), self._traspasar(self.pedro, a, b), punto_a=EDIFICIO_BLOQUEADO
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], servicio.SaldoInsuficiente)
        self.assertEqual(self._saldo(*a), 0)
        self.assertEqual(self._saldo(*b), 2)
        self.assertInvarianteDelLibro()
