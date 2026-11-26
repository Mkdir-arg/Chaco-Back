"""Siembra de las capacidades de stock — ``users/migrations/0053`` (análisis 010, PR 1).

La migración declara la lista **entera** de capacidades y las tilda solo en el Administrador protegido. En ECOM el
PM tilda el resto desde Roles. La reversa las quita del Administrador.
"""

import importlib

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from users.models import Capacidad, RolMeta

migracion = importlib.import_module("users.migrations.0053_capacidades_stock")
# RED-17: los modelos **de entonces**, no los de hoy.
APPS_DE_ENTONCES = estado_historico("users", "0053_capacidades_stock", al_final=True)
STOCK = ("stock_ver", "stock_entregar", "stock_ingresar", "stock_ajustar")


def _permiso(codename):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get_or_create(content_type=ct, codename=codename, defaults={"name": codename})[0]


def _codenames(grupo):
    return set(grupo.permissions.values_list("codename", flat=True))


def _administrador():
    grupo = Group.objects.create(name=rbac.ROL_ADMINISTRADOR)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_BACKOFFICE,
        protegido=True,
        activo=True,
        clave=migracion.CLAVE_ADMINISTRADOR,
    )
    grupo.permissions.add(_permiso("dispositivo_ver"))
    return grupo


class CatalogoTests(TestCase):
    def test_los_codenames_y_las_etiquetas_son_los_del_catalogo(self):
        """Si alguien renombra una, la siembra quedaría sin efecto en silencio."""

        catalogo = dict(rbac.todas_las_capacidades())
        self.assertEqual({codename for codename, _ in migracion.CAPACIDADES}, set(STOCK))
        for codename, nombre in migracion.CAPACIDADES:
            self.assertEqual(catalogo.get(codename), nombre)

    def test_la_lista_nueva_es_la_de_la_0052_mas_las_cuatro(self):
        anterior = estado_historico("users", "0052_capacidad_cerrar_reabrir_emergencia", al_final=True)
        antes = {c for c, _ in anterior.get_model("users", "Capacidad")._meta.permissions}
        ahora = {c for c, _ in APPS_DE_ENTONCES.get_model("users", "Capacidad")._meta.permissions}
        self.assertEqual(ahora - antes, set(STOCK))
        self.assertEqual(antes - ahora, set())


class SiembraTests(TestCase):
    def test_el_administrador_recibe_las_cuatro(self):
        admin = _administrador()

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_codenames(admin), {"dispositivo_ver", *STOCK})

    def test_no_toca_a_otros_roles(self):
        _administrador()
        otro = Group.objects.create(name="Dispositivos — Operador / Guardia")
        otro.permissions.add(_permiso("dispositivo_ver"))

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_codenames(otro), {"dispositivo_ver"})

    def test_correr_dos_veces_es_igual_que_una(self):
        admin = _administrador()

        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(Permission.objects.filter(codename="stock_ver").count(), 1)
        self.assertEqual(_codenames(admin), {"dispositivo_ver", *STOCK})

    def test_sin_administrador_no_falla(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertFalse(Permission.objects.filter(codename="stock_ver", group__isnull=False).exists())

    def test_la_reversa_las_quita_del_administrador_y_nada_mas(self):
        admin = _administrador()
        migracion.sembrar(APPS_DE_ENTONCES, None)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertEqual(_codenames(admin), {"dispositivo_ver"})

    def test_la_reversa_no_toca_lo_que_el_pm_tildo_en_otros_roles(self):
        _administrador()
        pm = Group.objects.create(name="Armado por el PM")
        pm.permissions.add(_permiso("stock_ver"))
        migracion.sembrar(APPS_DE_ENTONCES, None)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertEqual(_codenames(pm), {"stock_ver"})

    def test_la_reversa_sin_administrador_no_falla(self):
        migracion.quitar(APPS_DE_ENTONCES, None)
