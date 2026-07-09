import json

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import NoReverseMatch, reverse

from core import rbac
from programas.models import Programa
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import Capacidad, RolMeta
from users.selectors.usuarios import (
    alcance_roles_ids,
    usuarios_visibles_para,
)
from users.services import UsuariosService
from users.services.admin import UsuariosAdminService
from users.tests.test_rbac import render_sidebar


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _admin(username):
    g, _ = Group.objects.get_or_create(name="Admins")
    RolMeta.objects.get_or_create(grupo=g, defaults={"categoria": "Sistema", "activo": True})
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


class UsuarioFiltrosTests(TestCase):
    """#122 — filtros avanzados visibles en el listado de Usuarios."""

    def setUp(self):
        self.admin = _admin("admin-filtros")
        self.client.force_login(self.admin)

    def _filters(self, *items, logic="AND"):
        return json.dumps({"logic": logic, "items": list(items)})

    def test_vista_expone_toolbar_de_filtros(self):
        resp = self.client.get(reverse("users:usuarios"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'id="filters-form"')
        self.assertContains(resp, "usuarios-filters-config")
        self.assertContains(resp, "advanced_filters.js")

    def test_filtro_estado_inactivo(self):
        User.objects.create_user("activo", password="x", is_active=True)
        User.objects.create_user("inactivo", password="x", is_active=False)

        resp = self.client.get(
            reverse("users:usuarios"),
            {"filters": self._filters({"field": "estado", "op": "eq", "value": "false"})},
        )

        self.assertEqual(resp.status_code, 200)
        nombres = {user.username for user in resp.context["users"]}
        self.assertEqual(nombres, {"inactivo"})
        self.assertTrue(resp.context["hay_filtros_activos"])

    def test_filtro_por_rol_no_duplica_usuarios(self):
        rol_uno = Group.objects.create(name="Operador Becas")
        RolMeta.objects.create(grupo=rol_uno, categoria=rbac.CATEGORIA_PROGRAMA, activo=True)
        rol_dos = Group.objects.create(name="Supervisor Becas")
        RolMeta.objects.create(grupo=rol_dos, categoria=rbac.CATEGORIA_PROGRAMA, activo=True)
        user = User.objects.create_user("multi-becas", password="x")
        user.groups.add(rol_uno, rol_dos)

        qs = UsuariosService.get_filtered_usuarios(
            {"filters": self._filters({"field": "rol", "op": "contains", "value": "Becas"})}
        )

        self.assertEqual(list(qs), [user])


class UsuarioAlcanceProgramaTests(TestCase):
    """#67 â€” ABM de Usuarios con alcance de Programa."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.nachec = Programa.objects.create(codigo="NACHEC", nombre="Ã‘achec")

        # Admin de programa Becas (programa.configurar).
        self.rol_admin_becas = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol_admin_becas,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas,
            activo=True,
        )
        self.rol_admin_becas.permissions.add(_perm("programa.configurar"))
        self.admin_becas = User.objects.create_user("adm-becas", password="x")
        self.admin_becas.groups.add(self.rol_admin_becas)

        # Roles operativos por programa + un rol global.
        self.rol_becas = Group.objects.create(name="Operador Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.rol_nachec = Group.objects.create(name="Operador Ã‘achec")
        RolMeta.objects.create(
            grupo=self.rol_nachec, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.nachec, activo=True
        )
        self.rol_global = Group.objects.create(name="Backoffice X")
        RolMeta.objects.create(grupo=self.rol_global, categoria="Backoffice", activo=True)

        # Superusuario: admin global presente para que la auto-protecciÃ³n global no salte.
        self.su = User.objects.create_superuser("root", "root@example.com", "x")

    def test_listado_filtrado_por_programa(self):  # TC-67-01 / TC-67-09
        u_becas = User.objects.create_user("u-becas", password="x")
        u_becas.groups.add(self.rol_becas)
        u_nachec = User.objects.create_user("u-nachec", password="x")
        u_nachec.groups.add(self.rol_nachec)
        u_sin = User.objects.create_user("u-sin", password="x")

        visibles = set(usuarios_visibles_para(self.admin_becas))
        self.assertIn(u_becas, visibles)
        self.assertIn(self.admin_becas, visibles)  # tiene rol de Becas
        self.assertNotIn(u_nachec, visibles)
        self.assertNotIn(u_sin, visibles)

    def test_alta_selector_solo_roles_de_su_programa(self):  # TC-67-02
        roles = set(UserCreationForm(operador=self.admin_becas).fields["groups"].queryset)
        self.assertEqual(roles, {self.rol_admin_becas, self.rol_becas})

    def test_edicion_selector_oculta_roles_de_otro_programa(self):  # TC-67-03
        user = User.objects.create_user("multi", password="x")
        user.groups.add(self.rol_becas, self.rol_nachec)
        form = CustomUserChangeForm(operador=self.admin_becas, instance=user)
        roles = set(form.fields["groups"].queryset)
        self.assertIn(self.rol_becas, roles)
        self.assertNotIn(self.rol_nachec, roles)  # el rol de Ã‘achec no aparece

    def test_guardar_no_pierde_roles_fuera_de_alcance(self):  # TC-67-05 (crÃ­tico)
        user = User.objects.create_user("multi2", password="x")
        user.groups.add(self.rol_becas, self.rol_nachec)
        form = CustomUserChangeForm(
            data={"username": "multi2", "email": "", "password": "", "groups": [], "first_name": "", "last_name": ""},
            instance=user,
            operador=self.admin_becas,
        )
        self.assertTrue(form.is_valid(), form.errors)
        UsuariosAdminService.update_user_from_form(form, alcance_group_ids=alcance_roles_ids(self.admin_becas))
        nombres = set(user.groups.values_list("name", flat=True))
        self.assertIn("Operador Ã‘achec", nombres)  # rol fuera de alcance preservado
        self.assertNotIn("Operador Becas", nombres)  # rol en alcance, deseleccionado

    def test_editar_datos_generales_afecta_la_cuenta(self):  # TC-67-04
        user = User.objects.create_user("multi3", password="x")
        user.groups.add(self.rol_becas, self.rol_nachec)
        form = CustomUserChangeForm(
            data={
                "username": "multi3",
                "email": "nuevo@x.com",
                "password": "",
                "groups": [str(self.rol_becas.pk)],
                "first_name": "N",
                "last_name": "A",
            },
            instance=user,
            operador=self.admin_becas,
        )
        self.assertTrue(form.is_valid(), form.errors)
        UsuariosAdminService.update_user_from_form(form, alcance_group_ids=alcance_roles_ids(self.admin_becas))
        user.refresh_from_db()
        self.assertEqual(user.email, "nuevo@x.com")
        self.assertTrue(user.groups.filter(name="Operador Ã‘achec").exists())

    def test_acceso_directo_a_usuario_fuera_de_alcance_redirige(self):  # TC-67-06
        u_nachec = User.objects.create_user("solo-nachec", password="x")
        u_nachec.groups.add(self.rol_nachec)
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:usuario_editar", args=[u_nachec.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_admin_global_ve_todos(self):  # TC-67-07
        u_nachec = User.objects.create_user("u-nachec", password="x")
        u_nachec.groups.add(self.rol_nachec)
        visibles = set(usuarios_visibles_para(self.su))
        self.assertIn(u_nachec, visibles)
        self.assertIn(self.admin_becas, visibles)

    def test_configurar_inactivo_sin_acceso(self):  # TC-67-08
        self.rol_admin_becas.meta.activo = False
        self.rol_admin_becas.meta.save(update_fields=["activo"])
        self.client.force_login(self.admin_becas)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)

    def test_usuario_con_rol_de_programa_inactivo_no_visible(self):
        # Consistencia de alcance: un usuario cuyo Ãºnico vÃ­nculo con Becas es un rol
        # INACTIVO no debe ser visible ni gestionable por el admin de Becas.
        inactivo = Group.objects.create(name="Becas inactivo")
        RolMeta.objects.create(grupo=inactivo, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=False)
        u = User.objects.create_user("solo-inactivo", password="x")
        u.groups.add(inactivo)
        self.assertNotIn(u, set(usuarios_visibles_para(self.admin_becas)))
        from users.selectors.usuarios import puede_gestionar_usuario

        self.assertFalse(puede_gestionar_usuario(self.admin_becas, u))

    def test_filtro_por_rol_no_amplia_alcance_de_admin_programa(self):
        u_becas = User.objects.create_user("visible-becas", password="x")
        u_becas.groups.add(self.rol_becas)
        u_nachec = User.objects.create_user("oculto-nachec", password="x")
        u_nachec.groups.add(self.rol_nachec)

        filtrados = UsuariosService.get_filtered_usuarios(
            {
                "filters": json.dumps(
                    {
                        "logic": "AND",
                        "items": [{"field": "rol", "op": "contains", "value": "Ñachec"}],
                    }
                )
            },
            operador=self.admin_becas,
        )

        self.assertNotIn(u_nachec, set(filtrados))
        self.assertEqual(list(filtrados), [])


class ProgramaSinAdminTests(TestCase):
    """#68 â€” no dejar un programa sin administrador (flujos de Usuarios)."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        # Admin global NO superusuario: hace pasar el check global, deja ver el scoped.
        self.rol_global = Group.objects.create(name="Administrador")
        RolMeta.objects.create(grupo=self.rol_global, categoria="Sistema", activo=True)
        self.rol_global.permissions.add(_perm("usuario.administrar"), _perm("rol.administrar"))
        self.jefe = User.objects.create_user("jefe", password="x")
        self.jefe.groups.add(self.rol_global)
        # MarÃ­a, Ãºnica administradora de Becas.
        self.rol_becas = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.rol_becas.permissions.add(_perm("programa.configurar"))
        self.maria = User.objects.create_user("maria", password="x")
        self.maria.groups.add(self.rol_becas)

    def _form_sin_roles(self, user):
        return CustomUserChangeForm(
            data={
                "username": user.username,
                "email": "",
                "password": "",
                "groups": [],
                "first_name": "",
                "last_name": "",
            },
            instance=user,
        )

    def test_quitar_ultimo_admin_de_programa_bloquea(self):  # TC-68-01
        form = self._form_sin_roles(self.maria)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(rbac.SinAdministradorProgramaError):
            UsuariosAdminService.update_user_from_form(form)
        self.maria.refresh_from_db()
        self.assertTrue(self.maria.groups.filter(name="Admin Becas").exists())  # revertido

    def test_permite_si_queda_otro_admin_de_programa(self):  # TC-68-03
        juan = User.objects.create_user("juan", password="x")
        juan.groups.add(self.rol_becas)
        form = self._form_sin_roles(self.maria)
        self.assertTrue(form.is_valid(), form.errors)
        UsuariosAdminService.update_user_from_form(form)  # no lanza
        self.maria.refresh_from_db()
        self.assertFalse(self.maria.groups.filter(name="Admin Becas").exists())

    def test_desactivar_ultimo_admin_de_programa_bloquea(self):  # TC-68-02
        self.client.force_login(self.jefe)
        self.client.post(reverse("users:usuario_toggle", args=[self.maria.pk]))
        self.maria.refresh_from_db()
        self.assertTrue(self.maria.is_active)  # la operaciÃ³n se revierte


class SidebarAdministracionTests(TestCase):
    """#68 â€” la secciÃ³n AdministraciÃ³n del sidebar respeta programa.configurar."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol_becas = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.rol_becas.permissions.add(_perm("programa.configurar"))
        self.maria = User.objects.create_user("maria", password="x")
        self.maria.groups.add(self.rol_becas)

    def test_admin_programa_ve_administracion(self):  # TC-68-04
        html = render_sidebar(User.objects.get(pk=self.maria.pk))
        self.assertIn(reverse("users:usuarios"), html)  # secciÃ³n AdministraciÃ³n visible
        self.assertIn(reverse("users:roles"), html)

    def test_sin_capacidades_no_ve_administracion(self):  # TC-68-05
        plano = User.objects.create_user("plano", password="x")
        html = render_sidebar(plano)
        self.assertNotIn(reverse("users:usuarios"), html)
        self.assertNotIn(reverse("users:roles"), html)


class UsuarioAutoProteccionTests(TestCase):
    def test_quitarse_el_ultimo_rol_admin_revierte(self):
        admin = _admin("solo")  # Ãºnico administrador (no superusuario)
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
