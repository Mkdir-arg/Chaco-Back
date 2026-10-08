"""Capacidades, rol «Comunicaciones» y archivos de `/media/` del módulo (RNF-007-01/02)."""

import importlib
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase

from core import rbac
from core.tests.historico import estado_historico
from core.views.media import _autorizar
from notificaciones.tests.utils import ConMediaTemporal, crear_campana, usuario_con

migracion = importlib.import_module("users.migrations.0030_rol_comunicaciones")
APPS_DE_ENTONCES = estado_historico("users", "0030_rol_comunicaciones")
CAPS = {"notificacion.ver", "notificacion.gestionar", "notificacion.enviar"}


class CatalogoTests(TestCase):
    def test_modulo_global_con_las_tres_capacidades(self):
        modulo = next(m for m in rbac.CATALOGO if m["modulo"] == "notificaciones")
        self.assertNotIn("alcance", modulo)
        self.assertEqual({c for c, _ in modulo["capacidades"]}, CAPS)

    def test_la_migracion_usa_los_codenames_del_catalogo(self):
        self.assertEqual({codename for codename, _ in migracion.CAPACIDADES}, {rbac.codename_de(c) for c in CAPS})


class SeedComunicacionesTests(TestCase):
    def test_seed_crea_el_rol_con_las_tres(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        grupo = Group.objects.get(name="Comunicaciones")
        self.assertEqual(set(rbac.capacidades_de_grupo(grupo)), CAPS)
        self.assertEqual(grupo.meta.categoria, rbac.CATEGORIA_BACKOFFICE)
        self.assertFalse(grupo.meta.protegido)
        administrador = Group.objects.get(name=rbac.ROL_ADMINISTRADOR)
        self.assertTrue(CAPS <= set(rbac.capacidades_de_grupo(administrador)))

    def test_seed_no_pisa_un_rol_editado(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        grupo = Group.objects.get(name="Comunicaciones")
        grupo.permissions.clear()
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        self.assertEqual(rbac.capacidades_de_grupo(grupo), [])


class MigracionRolComunicacionesTests(TestCase):
    def test_crea_el_rol_y_suma_al_administrador(self):
        administrador = Group.objects.create(name="Administrador")
        migracion.sembrar(APPS_DE_ENTONCES, None)
        grupo = Group.objects.get(name="Comunicaciones")
        self.assertEqual(set(rbac.capacidades_de_grupo(grupo)), CAPS)
        self.assertTrue(CAPS <= set(rbac.capacidades_de_grupo(administrador)))

    def test_no_toca_un_rol_comunicaciones_que_ya_existia(self):
        grupo = Group.objects.create(name="Comunicaciones")
        migracion.sembrar(APPS_DE_ENTONCES, None)
        self.assertEqual(rbac.capacidades_de_grupo(grupo), [])

    def test_reversa_saca_las_capacidades_y_borra_el_rol_sin_usuarios(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)
        migracion.quitar(APPS_DE_ENTONCES, None)
        self.assertFalse(Group.objects.filter(name="Comunicaciones").exists())

    def test_reversa_conserva_el_rol_con_usuarios(self):
        migracion.sembrar(APPS_DE_ENTONCES, None)
        User.objects.create_user("com", password="x").groups.add(Group.objects.get(name="Comunicaciones"))
        migracion.quitar(APPS_DE_ENTONCES, None)
        self.assertEqual(rbac.capacidades_de_grupo(Group.objects.get(name="Comunicaciones")), [])


class MediaDeCampanasTests(ConMediaTemporal):
    def test_los_archivos_de_una_campana_los_baja_quien_ve_campanas(self):
        campana = crear_campana()
        ve = usuario_con("notificacion.ver", username="ve")
        nadie = usuario_con("reporte.ver", username="nadie")
        for ruta in (campana.archivo_excel.name, campana.archivo_html.name):
            with self.subTest(ruta=ruta):
                self.assertTrue(ruta.startswith("notificaciones/"))
                self.assertTrue(_autorizar(ve, ruta))
                self.assertFalse(_autorizar(nadie, ruta))
        self.assertIsNone(_autorizar(ve, "notificaciones/excel/no-existe.xlsx"))
