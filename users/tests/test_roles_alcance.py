"""Alcance del rol (Global / De un programa): migración users.0041 y selector del ABM.

El campo ``RolMeta.categoria`` es ahora el «Alcance». Los valores guardados no cambian de
string (``Backoffice`` = Global, ``Programa`` = De un programa); la autorización sigue
saliendo del FK ``programa``, nunca de la categoría. La única diferencia es que la guarda
RN-8 de «programa sin administrador» (``programas_que_administra``,
``RolesAdminService._programa_que_administra``) ahora también cuenta los roles legacy Becas
con programa, como ya los contaba ``usuarios_que_administran_programa``.
"""

import importlib

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from zeal import zeal_ignore

from core import rbac
from programas.models import Programa
from users.forms import _roles_asignables_queryset
from users.forms.roles import RolForm
from users.models import Capacidad, RolMeta

MIGRACION = importlib.import_module("users.migrations.0041_rolmeta_alcance_global_programa")


def _meta(nombre, categoria, programa=None):
    grupo = Group.objects.create(name=nombre)
    # ``update`` evita ``clean()``: simula el dato legacy tal como lo dejó la historia.
    meta = RolMeta.objects.create(grupo=grupo, categoria="Backoffice", activo=True)
    RolMeta.objects.filter(pk=meta.pk).update(categoria=categoria, programa=programa)
    return RolMeta.objects.get(pk=meta.pk)


class MigracionAlcanceTests(TestCase):
    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")

    def _correr(self):
        MIGRACION.reubicar_categorias(django_apps, None)

    def _estado(self):
        return {m.grupo.name: (m.categoria, m.programa_id) for m in RolMeta.objects.select_related("grupo")}

    def test_los_cuatro_casos_y_los_que_no_se_tocan(self):
        _meta("sistema", "Sistema")
        _meta("institucion", "Institución")
        _meta("becas-con-programa", "Becas", self.becas)
        _meta("becas-sin-programa", "Becas")
        _meta("global", "Backoffice")
        _meta("de-programa", "Programa", self.becas)
        _meta("portal", "Portal")

        self._correr()

        self.assertEqual(
            self._estado(),
            {
                "sistema": ("Backoffice", None),
                "institucion": ("Backoffice", None),
                "becas-con-programa": ("Programa", self.becas.pk),
                "becas-sin-programa": ("Backoffice", None),
                "global": ("Backoffice", None),
                "de-programa": ("Programa", self.becas.pk),
                "portal": ("Portal", None),
            },
        )

    def test_es_idempotente(self):
        _meta("sistema", "Sistema")
        _meta("becas-con-programa", "Becas", self.becas)
        _meta("becas-sin-programa", "Becas")
        self._correr()
        despues_de_una = self._estado()
        self._correr()
        self.assertEqual(self._estado(), despues_de_una)

    def test_el_alcance_de_un_rol_becas_con_programa_se_conserva(self):
        meta = _meta("coord", "Becas", self.becas)
        self._correr()
        meta.refresh_from_db()
        self.assertEqual((meta.categoria, meta.programa_id), ("Programa", self.becas.pk))
        meta.clean()  # la regla de coherencia categoría/programa se cumple


class GuardaRN8RolesBecasLegacyTests(TestCase):
    def test_rol_becas_con_programa_cuenta_como_admin_tras_la_migracion(self):
        programa = Programa.objects.create(codigo="BECAS", nombre="Becas")
        meta = _meta("Coord Becas legacy", "Becas", programa)
        ct = ContentType.objects.get_for_model(Capacidad)
        meta.grupo.permissions.add(
            Permission.objects.get(codename=rbac.codename_de("programa.usuario.administrar"), content_type=ct)
        )
        u = User.objects.create_user("legacy-becas", password="x")
        u.groups.add(meta.grupo)
        self.assertEqual(rbac.programas_que_administra(u), set())

        MIGRACION.reubicar_categorias(django_apps, None)

        self.assertEqual(rbac.programas_que_administra(u), {programa.pk})


class MigracionRetirarCapacidadesInstitucionTests(TestCase):
    def test_ida_y_vuelta_restituye_los_roles(self):
        m42 = importlib.import_module("users.migrations.0042_retirar_capacidades_institucion")
        ct = ContentType.objects.get_for_model(Capacidad)
        permiso, _ = Permission.objects.get_or_create(
            content_type=ct, codename="institucion_ver", defaults={"name": "Ver instituciones"}
        )
        grupo = Group.objects.create(name="Rol con institucion")
        grupo.permissions.add(permiso)

        m42.retirar(django_apps, None)
        m42.retirar(django_apps, None)  # idempotente
        self.assertFalse(Permission.objects.filter(content_type=ct, codename="institucion_ver").exists())
        self.assertEqual(grupo.capacidades_revocadas.filter(migracion="users.0042").count(), 1)

        m42.restituir(django_apps, None)
        self.assertEqual(list(grupo.permissions.values_list("codename", flat=True)), ["institucion_ver"])
        self.assertFalse(grupo.capacidades_revocadas.filter(migracion="users.0042").exists())


class SelectorAlcanceTests(TestCase):
    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")

    def test_choices_visibles_son_global_y_de_un_programa(self):
        self.assertEqual(
            list(RolForm().fields["categoria"].choices),
            [("Backoffice", "Global"), ("Programa", "De un programa")],
        )

    def test_portal_lo_acepta_el_modelo_pero_nunca_se_ofrece(self):
        self.assertIn(rbac.CATEGORIA_PORTAL, {v for v, _ in RolMeta._meta.get_field("categoria").choices})
        self.assertNotIn(rbac.CATEGORIA_PORTAL, {v for v, _ in RolForm().fields["categoria"].choices})

    def test_admin_global_ve_ambos_alcances_y_admin_de_programa_solo_uno(self):
        su = User.objects.create_superuser("root-alc", "r@r.com", "x")
        self.assertEqual(
            {v for v, _ in RolForm(operador=su).fields["categoria"].choices},
            {"Backoffice", "Programa"},
        )

        grupo = Group.objects.create(name="Admin Becas alc")
        RolMeta.objects.create(grupo=grupo, categoria="Programa", programa=self.becas, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(
            Permission.objects.get(codename=rbac.codename_de("programa.rol.administrar"), content_type=ct)
        )
        admin = User.objects.create_user("adm-alc", password="x")
        admin.groups.add(grupo)
        self.assertEqual(
            list(RolForm(operador=admin).fields["categoria"].choices),
            [("Programa", "De un programa")],
        )

    def test_listado_filtro_y_badge_muestran_etiquetas(self):
        su = User.objects.create_superuser("root-lst", "r@r.com", "x")
        _meta("Rol global", "Backoffice")
        _meta("Rol prog", "Programa", self.becas)
        self.client.force_login(su)
        with zeal_ignore():
            html = self.client.get(reverse("users:roles")).content.decode()
        self.assertIn(">Global</option>", html)
        self.assertIn(">De un programa</option>", html)
        self.assertNotIn(">Portal (identidad ciudadana)</option>", html)
        self.assertIn(">De un programa</span>", html)


class PortalExcluidoDeRolesAsignablesTests(TestCase):
    def test_ciudadanos_no_es_asignable(self):
        _meta("Ciudadanos", "Portal")
        _meta("Operador", "Backoffice")
        nombres = set(_roles_asignables_queryset().values_list("name", flat=True))
        self.assertIn("Operador", nombres)
        self.assertNotIn("Ciudadanos", nombres)
