from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.tests.test_rbac import render_sidebar

_CAPS_OPERADOR = [
    "ciudadano.ver", "programa.ver", "reporte.ver",
    "config.administrar", "usuario.administrar", "rol.administrar",
]


class OperadorBackofficeSeedTests(TestCase):
    """#59 — el seed crea el rol 'Operador de backoffice' idempotente."""

    def test_seed_crea_operador_con_caps_exactas(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        g = Group.objects.get(name="Operador de backoffice")
        self.assertCountEqual(rbac.capacidades_de_grupo(g), _CAPS_OPERADOR)
        self.assertFalse(g.meta.protegido)
        self.assertEqual(g.meta.categoria, rbac.CATEGORIA_BACKOFFICE)

    def test_seed_idempotente(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        g = Group.objects.get(name="Operador de backoffice")  # no duplica
        self.assertCountEqual(rbac.capacidades_de_grupo(g), _CAPS_OPERADOR)


class MenuRestringidoTests(TestCase):
    """#59 — el sidebar se gobierna por capacidades (ítems gateados)."""

    def setUp(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        self.rol = Group.objects.get(name="Operador de backoffice")
        self.user = User.objects.create_user("op", password="x")
        self.user.groups.add(self.rol)

    def test_menu_reducido_para_rol_restringido(self):  # TC-59-01..04
        html = render_sidebar(User.objects.get(pk=self.user.pk))
        # Ve: Ciudadanos (ciudadano.ver) y Administración (usuario.administrar).
        self.assertIn(reverse("legajos:ciudadanos"), html)
        self.assertIn(reverse("users:usuarios"), html)
        # No ve los 2 sub-ítems gateados ni los módulos sin capacidad.
        self.assertNotIn(reverse("legajos:ciudadano_nuevo"), html)       # TC-59-03
        self.assertNotIn(reverse("conversaciones:configurar_cola"), html)  # TC-59-04
        self.assertNotIn(reverse("legajos:dashboard_contactos"), html)   # TC-59-02
        self.assertNotIn(reverse("core:relevamientos"), html)            # TC-59-02

    def test_admin_ve_menu_completo(self):  # TC-59-07
        su = User.objects.create_superuser("root", "root@example.com", "x")
        html = render_sidebar(su)
        self.assertIn(reverse("legajos:ciudadano_nuevo"), html)
        self.assertIn(reverse("conversaciones:configurar_cola"), html)
        self.assertIn(reverse("legajos:dashboard_contactos"), html)
        self.assertIn(reverse("core:relevamientos"), html)

    def test_rol_inactivo_solo_inicio(self):  # TC-59-08
        self.rol.meta.activo = False
        self.rol.meta.save(update_fields=["activo"])
        html = render_sidebar(User.objects.get(pk=self.user.pk))
        self.assertNotIn(reverse("legajos:ciudadanos"), html)
        self.assertNotIn(reverse("users:usuarios"), html)
        self.assertIn(reverse("core:inicio"), html)  # Inicio siempre visible
