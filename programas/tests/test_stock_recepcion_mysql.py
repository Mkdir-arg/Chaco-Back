"""Stock, PR 3 (análisis 010, RN-010-15/19): la carrera «recibir una entrega sin edificio» contra «inactivar ese edificio».

``select_for_update`` es un no-op en SQLite, así que esto lleva ``@tag("mysql")`` y lo corre el job «Motor real»
(``manage.py test --tag mysql``); sin motor real se saltea (``MotorRealMixin``).

A recibe una entrega que no tenía edificio eligiendo el edificio X y queda detenido **con el Dispositivo y el Edificio
tomados** (``_exigir_edificio_activo``); B intenta inactivar X (pide primero el Dispositivo: ``_bloquear_predio``) y tiene
que esperar. Cuando A commitea, X ya tiene saldo, así que B se rechaza: el edificio sigue activo y el saldo es el de la
recepción. Si alguien saca el candado, B atraviesa y ``en_paralelo`` lo reporta.
"""

import shutil
import tempfile

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings, tag

from core import rbac
from core.tests.test_motor_real import MotorRealMixin
from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    LineaEntrega,
    MiembroEquipoDispositivo,
    Programa,
    SaldoStock,
    TipoDispositivo,
    TipoKit,
)
from programas.selectors import stock as selectores
from programas.services import kits
from programas.services.edificios import inactivar_edificio
from programas.tests.test_dispositivos_concurrencia import _permiso, en_paralelo, punto_critico
from programas.tests.test_emergencia_casos import JPEG
from users.models import RolMeta

EDIFICIO_ELEGIDO = punto_critico(Edificio, "_exigir_edificio_activo")
DISPOSITIVO_DE_INACTIVAR = punto_critico(Dispositivo, "_bloquear_predio")


@tag("mysql")
class CarreraRecibirContraInactivarTests(MotorRealMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        ajuste = override_settings(MEDIA_ROOT=self.media)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="CIS-REC", nombre="CIS", maneja_stock=True)
        self.disp = Dispositivo.objects.create(
            tipo=tipo, codigo="CIS-R1", nombre="CIS 1", estado=Dispositivo.Estado.ACTIVO
        )
        self.edificio = Edificio.objects.create(codigo="ED-R1", nombre="Edificio R1")
        self.edificio.dispositivos.add(self.disp)
        self.colchon = TipoKit.objects.create(nombre="Colchón recepción", unidad="unidad")
        rol = Group.objects.create(name="Rol recibe")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(_permiso("emergencia.recibir_kit"))
        self.guardia = User.objects.create_user(username="guardia_rec")
        self.guardia.groups.add(rol)
        MiembroEquipoDispositivo.objects.create(dispositivo=self.disp, usuario=self.guardia, rol=rol)
        self.admin = User.objects.create_superuser(username="admin_rec", password="x")
        self.entrega = EntregaKit.objects.create(
            numero="2026-K-000001",
            dispositivo=self.disp,
            edificio=None,
            estado=EntregaKit.Estado.EN_CAMINO,
            armada_por=self.admin,
        )
        LineaEntrega.objects.create(
            entrega=self.entrega, item=self.colchon, nombre="Colchón", unidad="unidad", cantidad_enviada=10
        )

    def test_recibir_eligiendo_el_edificio_y_inactivarlo_a_la_vez_deja_el_edificio_activo_con_su_saldo(self):
        def recibir():
            return kits.recibir_entrega(
                EntregaKit.objects.get(pk=self.entrega.pk),
                User.objects.get(pk=self.guardia.pk),
                {self.colchon.pk: 8},
                SimpleUploadedFile("remito.jpg", JPEG, content_type="image/jpeg"),
                edificio=self.edificio.pk,
            )

        def inactivar():
            return inactivar_edificio(edificio=self.edificio, usuario=User.objects.get(pk=self.admin.pk))

        resultados, errores = en_paralelo(
            recibir, inactivar, punto_a=EDIFICIO_ELEGIDO, punto_b=DISPOSITIVO_DE_INACTIVAR
        )

        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(errores), 1)
        self.assertIsInstance(errores[0], ValidationError)
        self.assertIn("stock en 1 insumo", errores[0].message_dict["__all__"][0])
        self.assertTrue(Edificio.objects.get(pk=self.edificio.pk).activo)
        self.assertEqual(SaldoStock.objects.get(edificio=self.edificio, item=self.colchon).cantidad, 8)
        self.assertEqual(selectores.diferencias_de_saldo(), [])
