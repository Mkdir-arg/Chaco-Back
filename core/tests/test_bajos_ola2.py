"""SEC-36 y G1c-10 · Los dos bajos que no tenían dónde vivir.

SEC-36 · `/configuracion/programas/` estaba con solo `login_required`: el
catálogo institucional —nombre, código, subsecretaría y estado de cada programa
del organismo— lo veía cualquier cuenta de backoffice, incluida una recién creada
y sin rol. Y el ABM de usuarios devolvía `str(exc)` dentro del formulario: lo que
llegaba al operador era el error de base o de correo, con el nombre de la tabla o
el host del SMTP, dibujado como si fuera una validación.

G1c-10 · `/admin/doc/` estaba montado en todos los entornos, y el `UserAdmin` era
el estándar: un `is_staff` con `change_user` se tildaba `is_superuser` desde ahí,
salteando el ABM que sí evalúa alcance (SEC-03). Hoy no existe esa cuenta —ningún
flujo pone `is_staff`—, y de eso justamente deja de depender.
"""

from io import StringIO

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import NoReverseMatch, resolve, reverse

from core import rbac
from users.admin import OptimizedUserAdmin
from users.models import Capacidad, RolMeta

CLAVE = "Clave-Seg-2026x"


def _rol(nombre, capacidades):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_SISTEMA, activo=True)
    tipo = ContentType.objects.get_for_model(Capacidad)
    for codigo in capacidades:
        grupo.permissions.add(Permission.objects.get(content_type=tipo, codename=rbac.codename_de(codigo)))
    return grupo


class CatalogoDeProgramasTests(TestCase):
    """SEC-36 · El listado de programas pide capacidad."""

    URL = "/configuracion/programas/"

    def test_un_usuario_sin_rol_ya_no_lo_ve(self):
        self.client.force_login(User.objects.create_user("sin-rol-sec36", password=CLAVE))

        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse("core:inicio"))

    def test_el_rol_de_configuracion_sembrado_sigue_entrando(self):
        """`config.ver` y `config.administrar` son las del rol «Configuración»."""
        usuario = User.objects.create_user("config-sec36", password=CLAVE)
        usuario.groups.add(_rol("Configuración (test)", ["config.ver", "config.administrar"]))
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.URL).status_code, 200)

    def test_quien_configura_programas_sigue_entrando(self):
        usuario = User.objects.create_user("wizard-sec36", password=CLAVE)
        usuario.groups.add(_rol("Wizard (test)", ["programa.configurar"]))
        self.client.force_login(usuario)

        self.assertEqual(self.client.get(self.URL).status_code, 200)

    def test_el_superusuario_entra(self):
        self.client.force_login(User.objects.create_superuser("root-sec36", "root36@example.test", CLAVE))

        self.assertEqual(self.client.get(self.URL).status_code, 200)

    def test_un_anonimo_va_al_login(self):
        self.assertEqual(self.client.get(self.URL).status_code, 302)

    def test_el_acceso_del_inicio_pregunta_lo_mismo_que_la_vista(self):
        """Ofrecer un acceso que después rebota es peor que no ofrecerlo."""
        sin_rol = User.objects.create_user("sin-rol-inicio", password=CLAVE)
        self.client.force_login(sin_rol)

        self.assertNotContains(self.client.get(reverse("core:inicio")), self.URL)

        con_rol = User.objects.create_user("config-inicio", password=CLAVE)
        con_rol.groups.add(_rol("Configuración inicio (test)", ["config.administrar"]))
        self.client.force_login(con_rol)

        self.assertContains(self.client.get(reverse("core:inicio")), self.URL)


class ErroresInternosDelAbmTests(TestCase):
    """SEC-36 · El operador ve un mensaje; el detalle va al log."""

    def setUp(self):
        # El formulario del alta arma los campos de jerarquía de Becas, que
        # necesitan el programa sembrado.
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_superuser("root-abm", "root-abm@example.test", CLAVE)
        self.client.force_login(self.admin)

    def test_el_alta_no_le_muestra_el_error_interno_al_operador(self):
        from unittest.mock import patch

        datos = {
            "username": "nuevo-usuario",
            "email": "nuevo@example.test",
            "first_name": "Nuevo",
            "last_name": "Usuario",
            "password": "",
            "groups": [str(_rol("Rol del alta (test)", ["config.ver"]).pk)],
        }
        with (
            patch(
                "users.views.admin.UsuariosAdminService.create_user_from_form",
                side_effect=Exception("duplicate entry 'x' for key 'users_profile.telefono'"),
            ),
            self.assertLogs("users.views.admin", level="ERROR"),
        ):
            respuesta = self.client.post(reverse("users:usuario_crear"), datos)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "users_profile")
        self.assertContains(respuesta, "No se pudo guardar el usuario")


class AdminDeDjangoTests(TestCase):
    """G1c-10 · `/admin/doc/` y los campos de privilegio del `UserAdmin`."""

    def test_admin_doc_ya_no_esta_montado(self):
        """El URLconf de `admindocs` no está: lo que queda es el catch-all del
        propio `/admin/`, que para «doc» contesta 404 como para cualquier app
        inexistente."""
        with self.assertRaises(NoReverseMatch):
            reverse("django-admindocs-docroot")

        self.assertNotIn("admindocs", resolve("/admin/doc/").func.__module__)

    def test_el_admin_sigue_montado(self):
        """Lo que se retira es la documentación, no el `/admin/`."""
        self.assertTrue(resolve("/admin/").func)

    def _readonly(self, usuario):
        peticion = type("Peticion", (), {"user": usuario})()
        return OptimizedUserAdmin(User, AdminSite()).get_readonly_fields(peticion)

    def test_un_staff_no_superusuario_no_toca_privilegios(self):
        staff = User.objects.create_user("staff-g1c10", password=CLAVE, is_staff=True)

        solo_lectura = self._readonly(staff)

        for campo in ("is_superuser", "is_staff", "groups", "user_permissions"):
            with self.subTest(campo=campo):
                self.assertIn(campo, solo_lectura)

    def test_el_superusuario_sigue_pudiendo_todo(self):
        root = User.objects.create_superuser("root-g1c10", "root-g1c10@example.test", CLAVE)

        self.assertEqual(self._readonly(root), tuple(OptimizedUserAdmin.readonly_fields))
