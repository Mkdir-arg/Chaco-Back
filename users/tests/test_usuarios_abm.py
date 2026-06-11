from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse

from core import rbac
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import Capacidad, RolMeta
from users.services.admin import UsuariosAdminService


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _admin(username):
    g, _ = Group.objects.get_or_create(name="Admins")
    RolMeta.objects.get_or_create(
        grupo=g, defaults={"categoria": "Sistema", "activo": True}
    )
    g.permissions.add(_perm("usuario.administrar"), _perm("rol.administrar"))
    u = User.objects.create_user(username, password="x")
    u.groups.add(g)
    return u


class UsuarioAccesoTests(TestCase):
    def test_sin_capacidad_redirige(self):
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)

    def test_con_capacidad_entra(self):
        self.client.force_login(_admin("admin1"))
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 200)

    def test_no_existe_borrado_fisico(self):
        with self.assertRaises(NoReverseMatch):
            reverse("users:usuario_eliminar", args=[1])


class RolPortalNoAsignableTests(TestCase):
    def test_rol_categoria_portal_no_aparece_en_selector(self):
        portal = Group.objects.create(name="Ciudadanos")
        RolMeta.objects.create(grupo=portal, categoria="Portal", activo=True)
        backoffice = Group.objects.create(name="Operador")
        RolMeta.objects.create(grupo=backoffice, categoria="Backoffice", activo=True)

        roles = list(UserCreationForm().fields["groups"].queryset)
        self.assertIn(backoffice, roles)
        self.assertNotIn(portal, roles)  # el marcador de portal no es asignable


class UsuarioToggleTests(TestCase):
    def setUp(self):
        self.admin = _admin("admin1")
        _admin("admin2")  # segundo admin, para que nunca quede sin administradores
        self.client.force_login(self.admin)

    def test_desactivar_y_reactivar(self):
        target = User.objects.create_user("target", password="x")
        self.client.post(reverse("users:usuario_toggle", args=[target.pk]))
        target.refresh_from_db()
        self.assertFalse(target.is_active)

        self.client.post(reverse("users:usuario_toggle", args=[target.pk]))
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_no_puede_autodesactivarse(self):
        self.client.post(reverse("users:usuario_toggle", args=[self.admin.pk]))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_usuario_desactivado_no_inicia_sesion(self):
        target = User.objects.create_user("t2", password="secret")
        self.client.post(reverse("users:usuario_toggle", args=[target.pk]))
        self.assertFalse(Client().login(username="t2", password="secret"))


class UsuarioAutoProteccionTests(TestCase):
    def test_quitarse_el_ultimo_rol_admin_revierte(self):
        admin = _admin("solo")  # único administrador (no superusuario)
        form = CustomUserChangeForm(
            data={
                "username": "solo",
                "email": "",
                "password": "",
                "groups": [],
                "first_name": "",
                "last_name": "",
            },
            instance=admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(rbac.SinAdministradorError):
            UsuariosAdminService.update_user_from_form(form)

        admin.refresh_from_db()
        self.assertTrue(admin.groups.filter(name="Admins").exists())

    def test_editar_email_del_unico_admin_no_se_bloquea(self):
        admin = _admin("solo2")
        form = CustomUserChangeForm(
            data={
                "username": "solo2",
                "email": "nuevo@example.com",
                "password": "",
                "groups": [str(admin.groups.first().pk)],
                "first_name": "",
                "last_name": "",
            },
            instance=admin,
        )
        self.assertTrue(form.is_valid(), form.errors)
        UsuariosAdminService.update_user_from_form(form)  # no debe lanzar
        admin.refresh_from_db()
        self.assertEqual(admin.email, "nuevo@example.com")
