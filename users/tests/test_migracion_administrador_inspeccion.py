"""Siembra al Administrador — ``users/migrations/0040``.

El rol protegido «Administrador» no recibió ``inspeccion.asignar`` ni
``becas.revision.identidad`` (las migraciones que las declararon delegaron la siembra al
``seed_rbac``, que en ECOM no corre) y no veía «Relevamientos» de Dispositivos. La
migración se las da a él y a ningún otro rol, y **no** le da ``inspeccion.relevar``.
"""

import importlib

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from core.tests.historico import estado_historico
from programas.services.dispositivos import puede_en_programa_dispositivos
from programas.tests.test_dispositivos_inspecciones import BaseInspecciones
from users.models import Capacidad, RolMeta

migracion = importlib.import_module("users.migrations.0040_administrador_inspeccion_e_identidad")
# RED-17: los modelos **de entonces**, no los de hoy.
APPS_DE_ENTONCES = estado_historico("users", "0040_administrador_inspeccion_e_identidad")

ASIGNAR = "inspeccion_asignar"
IDENTIDAD = "becas_revision_identidad"
LAS_DOS = {ASIGNAR, IDENTIDAD}


def _capacidades(grupo):
    return set(grupo.permissions.values_list("codename", flat=True))


def _permiso(codename):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get_or_create(content_type=ct, codename=codename, defaults={"name": codename})[0]


def _rol(nombre, *codenames):
    grupo = Group.objects.create(name=nombre)
    grupo.permissions.add(*[_permiso(c) for c in codenames])
    return grupo


def _administrador(nombre="Administrador", clave=migracion.CLAVE_ADMINISTRADOR, *codenames):
    grupo = _rol(nombre, *codenames)
    RolMeta.objects.create(
        grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, protegido=True, activo=True, programa=None, clave=clave
    )
    return grupo


class CatalogoTests(TestCase):
    def test_los_codenames_y_etiquetas_siguen_en_el_catalogo(self):
        """Si alguien renombra una, la siembra quedaría sin efecto en silencio."""

        catalogo = dict(rbac.todas_las_capacidades())
        for codename, nombre in migracion.CAPACIDADES:
            self.assertEqual(catalogo.get(codename), nombre)
        self.assertEqual({c for c, _ in migracion.CAPACIDADES}, LAS_DOS)
        self.assertEqual(
            {rbac.codename_de("inspeccion.asignar"), rbac.codename_de("becas.revision.identidad")}, LAS_DOS
        )

    def test_el_nombre_canonico_es_el_del_rbac(self):
        self.assertEqual(migracion.ROL_ADMINISTRADOR, rbac.ROL_ADMINISTRADOR)


class SembrarTests(TestCase):
    def test_el_administrador_recibe_las_dos_y_conserva_las_previas(self):
        admin = _administrador("Administrador", migracion.CLAVE_ADMINISTRADOR, "dispositivo_ver", "programa_configurar")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(admin), LAS_DOS | {"dispositivo_ver", "programa_configurar"})

    def test_sin_clave_se_lo_encuentra_por_el_nombre(self):
        admin = _rol("Administrador", "dispositivo_ver")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(admin), LAS_DOS | {"dispositivo_ver"})

    def test_la_clave_gana_sobre_el_nombre(self):
        renombrado = _administrador("Admin del sistema", migracion.CLAVE_ADMINISTRADOR)
        homonimo = _rol("Administrador")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(renombrado), LAS_DOS)
        self.assertEqual(_capacidades(homonimo), set())

    def test_no_toca_a_otros_roles(self):
        _administrador()
        backoffice = _rol("Backoffice", "dispositivo_ver", "ciudadano_ver")
        programa = _rol("Operador", "dispositivo_admitir")
        vacio = _rol("Vacio")

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(backoffice), {"dispositivo_ver", "ciudadano_ver"})
        self.assertEqual(_capacidades(programa), {"dispositivo_admitir"})
        self.assertEqual(_capacidades(vacio), set())

    def test_no_le_da_inspeccion_relevar(self):
        admin = _administrador()

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertNotIn(rbac.codename_de("inspeccion.relevar"), _capacidades(admin))

    def test_es_idempotente(self):
        admin = _administrador()

        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        for codename in LAS_DOS:
            self.assertEqual(admin.permissions.filter(codename=codename).count(), 1)
            self.assertEqual(Permission.objects.filter(codename=codename).count(), 1)

    def test_sin_administrador_no_falla_ni_crea_roles(self):
        antes = Group.objects.count()

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(Group.objects.count(), antes)
        self.assertFalse(Group.objects.filter(name=migracion.ROL_ADMINISTRADOR).exists())

    def test_si_faltan_las_filas_de_permission_las_crea_con_la_etiqueta_del_catalogo(self):
        admin = _administrador()
        Permission.objects.filter(codename__in=LAS_DOS).delete()

        migracion.sembrar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(admin), LAS_DOS)
        catalogo = dict(rbac.todas_las_capacidades())
        for codename in LAS_DOS:
            self.assertEqual(Permission.objects.get(codename=codename).name, catalogo[codename])


class QuitarTests(TestCase):
    def test_la_reversa_saca_las_dos_solo_del_administrador(self):
        admin = _administrador("Administrador", migracion.CLAVE_ADMINISTRADOR, "dispositivo_ver")
        coordinador_becas = _rol("Coordinador de Becas", IDENTIDAD, "becas_revision_ver")
        dispositivos = _rol("Coordinador de Dispositivos", ASIGNAR)
        migracion.sembrar(APPS_DE_ENTONCES, None)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(admin), {"dispositivo_ver"})
        self.assertEqual(_capacidades(coordinador_becas), {IDENTIDAD, "becas_revision_ver"})
        self.assertEqual(_capacidades(dispositivos), {ASIGNAR})
        self.assertEqual(Permission.objects.filter(codename__in=LAS_DOS).count(), 2)

    def test_la_reversa_sin_administrador_no_falla(self):
        otro = _rol("Otro", ASIGNAR)

        migracion.quitar(APPS_DE_ENTONCES, None)

        self.assertEqual(_capacidades(otro), {ASIGNAR})


class PuntaAPuntaTests(BaseInspecciones):
    def test_el_administrador_global_pasa_a_ver_y_abrir_relevamientos(self):
        admin = _administrador("Administrador", migracion.CLAVE_ADMINISTRADOR, "dispositivo_ver", "programa_configurar")
        usuario = User.objects.create_user(username="admin_sistema", password="x")
        usuario.groups.add(admin)
        url = reverse("dispositivos:relevamientos")
        href = f'href="{url}"'

        antes = self._fresco(usuario)
        self.assertFalse(puede_en_programa_dispositivos(antes, "inspeccion.asignar"))
        self.client.force_login(antes)
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.assertNotIn(href, self.client.get(reverse("dispositivos:lista")).content.decode())

        migracion.sembrar(APPS_DE_ENTONCES, None)

        despues = self._fresco(usuario)  # `rbac` memoiza las capacidades en el objeto
        self.assertTrue(puede_en_programa_dispositivos(despues, "inspeccion.asignar"))
        self.client.force_login(despues)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertIn(href, self.client.get(reverse("dispositivos:lista")).content.decode())
