"""Siembra de ``edificio.ver`` — ``users/migrations/0048`` (#1165).

La capacidad nueva abre la sección «Edificios» de Dispositivos. La migración la tilda en
todo rol que ya tenga ``dispositivo.ver``, para que nadie que hoy ve Instituciones pierda
la sección, y en ningún otro. La reversa la quita de todos.
"""

import importlib

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from users.models import Capacidad

migracion = importlib.import_module("users.migrations.0048_capacidad_edificio_ver")
# RED-17: los modelos **de entonces**, no los de hoy.
APPS_DE_ENTONCES = estado_historico("users", "0048_capacidad_edificio_ver")


def _capacidades(grupo):
    return set(grupo.permissions.values_list("codename", flat=True))


def _permiso(codename):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get_or_create(content_type=ct, codename=codename, defaults={"name": codename})[0]


def _rol(nombre, *codenames):
    grupo = Group.objects.create(name=nombre)
    grupo.permissions.add(*[_permiso(c) for c in codenames])
    return grupo


class CatalogoTests(TestCase):
    def test_el_codename_y_la_etiqueta_siguen_en_el_catalogo(self):
        """Si alguien la renombra, la siembra quedaría sin efecto en silencio."""

        catalogo = dict(rbac.todas_las_capacidades())
        self.assertEqual(catalogo.get(migracion.CODENAME_NUEVA), migracion.NOMBRE_NUEVA)
        self.assertIn(migracion.CODENAME_ORIGEN, catalogo)
        self.assertIn("edificio.ver", rbac.codigos_de_capacidad())


class SiembraTests(TestCase):
    def setUp(self):
        self.lector = _rol("Lector de dispositivos", "dispositivo_ver")
        self.operador = _rol("Operador", "dispositivo_ver", "dispositivo_admitir")
        self.ajeno = _rol("Solo becas", "becas_segmento_ver")

    def test_la_siembra_va_a_los_roles_que_ven_dispositivos_y_a_ningun_otro(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertIn("edificio_ver", _capacidades(self.lector))
        self.assertIn("edificio_ver", _capacidades(self.operador))
        self.assertNotIn("edificio_ver", _capacidades(self.ajeno))

    def test_no_toca_las_otras_capacidades_del_rol(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(self.operador), {"dispositivo_ver", "dispositivo_admitir", "edificio_ver"})

    def test_correr_dos_veces_es_igual_que_una(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(Permission.objects.filter(codename="edificio_ver").count(), 1)
        self.assertEqual(_capacidades(self.lector), {"dispositivo_ver", "edificio_ver"})

    def test_la_reversa_la_quita_de_todos_los_roles(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)
        tildado_a_mano = _rol("Tildado a mano", "edificio_ver")

        migracion.quitar(APPS_DE_ENTONCES, None)

        for grupo in (self.lector, self.operador, tildado_a_mano):
            self.assertNotIn("edificio_ver", _capacidades(grupo))
        self.assertIn("dispositivo_ver", _capacidades(self.lector))

    def test_la_reversa_sin_la_capacidad_no_falla(self):
        Permission.objects.filter(codename="edificio_ver").delete()

        migracion.quitar(APPS_DE_ENTONCES, None)
