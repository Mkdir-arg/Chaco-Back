from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.forms.roles import RolForm
from users.models import Capacidad, RolMeta
from users.services.roles import RolesAdminService, RolProtegidoError


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol_admin(nombre="Admins"):
    """Crea un rol activo con capacidades de administración + un usuario activo."""
    g = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=g, categoria="Sistema", activo=True)
    g.permissions.add(_perm("usuario.administrar"), _perm("rol.administrar"))
    u = User.objects.create_user(f"admin-{nombre}", password="x")
    u.groups.add(g)
    return g, u


class RolFormTests(TestCase):
    def test_nombre_duplicado_invalido(self):
        Group.objects.create(name="Repetido")
        form = RolForm(data={"name": "repetido", "categoria": "Backoffice"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_arbol_capacidades_marca_iniciales(self):
        g = Group.objects.create(name="R")
        RolMeta.objects.create(grupo=g, categoria="Backoffice")
        g.permissions.add(_perm("ciudadano.ver"))
        form = RolForm(instance=g)
        arbol = form.arbol_capacidades()
        ciudadanos = next(m for m in arbol if m["modulo"] == "ciudadanos")
        marcadas = {c["codigo"] for c in ciudadanos["capacidades"] if c["checked"]}
        self.assertEqual(marcadas, {"ciudadano.ver"})


class RolesServiceTests(TestCase):
    def test_crear_rol_con_capacidades(self):
        form = RolForm(
            data={
                "name": "Operador legajos",
                "categoria": "Backoffice",
                "descripcion": "Ve y crea ciudadanos",
                "capacidades": ["ciudadano.ver", "ciudadano.crear"],
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        group = RolesAdminService.crear(form)

        self.assertEqual(group.meta.categoria, "Backoffice")
        self.assertFalse(group.meta.protegido)
        self.assertCountEqual(
            rbac.capacidades_de_grupo(group), ["ciudadano.ver", "ciudadano.crear"]
        )

    def test_editar_rol_actualiza_capacidades(self):
        _rol_admin()  # garantiza que quede al menos un admin
        g = Group.objects.create(name="Edit")
        RolMeta.objects.create(grupo=g, categoria="Backoffice")
        g.permissions.add(_perm("ciudadano.ver"))

        form = RolForm(
            data={"name": "Edit", "categoria": "Backoffice", "capacidades": ["dashboard.ver"]},
            instance=g,
        )
        self.assertTrue(form.is_valid(), form.errors)
        RolesAdminService.actualizar(form, g)
        self.assertCountEqual(rbac.capacidades_de_grupo(g), ["dashboard.ver"])

    def test_editar_rol_protegido_bloqueado(self):
        g = Group.objects.create(name="Administrador")
        RolMeta.objects.create(grupo=g, categoria="Sistema", protegido=True)
        form = RolForm(data={"name": "Administrador", "categoria": "Sistema"}, instance=g)
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(RolProtegidoError):
            RolesAdminService.actualizar(form, g)

    def test_eliminar_rol_desvincula_usuarios(self):
        _rol_admin()  # otro admin para no disparar la auto-protección
        g = Group.objects.create(name="Temporal")
        RolMeta.objects.create(grupo=g, categoria="Backoffice")
        u = User.objects.create_user("user-temp", password="x")
        u.groups.add(g)

        RolesAdminService.eliminar(g)

        self.assertFalse(Group.objects.filter(name="Temporal").exists())
        self.assertEqual(u.groups.count(), 0)

    def test_eliminar_rol_protegido_bloqueado(self):
        g = Group.objects.create(name="Administrador")
        RolMeta.objects.create(grupo=g, categoria="Sistema", protegido=True)
        with self.assertRaises(RolProtegidoError):
            RolesAdminService.eliminar(g)

    def test_toggle_activo(self):
        g = Group.objects.create(name="Tog")
        RolMeta.objects.create(grupo=g, categoria="Backoffice", activo=True)
        self.assertFalse(RolesAdminService.toggle_activo(g))
        g.meta.refresh_from_db()
        self.assertFalse(g.meta.activo)
        self.assertTrue(RolesAdminService.toggle_activo(g))

    def test_auto_bloqueo_al_quitar_capacidad_del_unico_rol_admin(self):
        g, _u = _rol_admin()  # único rol con administración
        form = RolForm(
            data={"name": g.name, "categoria": "Sistema", "capacidades": ["ciudadano.ver"]},
            instance=g,
        )
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(rbac.SinAdministradorError):
            RolesAdminService.actualizar(form, g)
        # La transacción se revierte: el rol conserva la capacidad de administración
        g.refresh_from_db()
        self.assertIn("usuario.administrar", rbac.capacidades_de_grupo(g))


class RolesAccesoTests(TestCase):
    def test_sin_capacidad_redirige(self):
        u = User.objects.create_user("plano", password="x")
        self.client.force_login(u)
        resp = self.client.get(reverse("users:roles"))
        self.assertEqual(resp.status_code, 302)

    def test_con_capacidad_entra(self):
        _g, u = _rol_admin("RolAcceso")
        self.client.force_login(u)
        resp = self.client.get(reverse("users:roles"))
        self.assertEqual(resp.status_code, 200)

    def test_superuser_entra(self):
        su = User.objects.create_superuser("root", "root@example.com", "x")
        self.client.force_login(su)
        resp = self.client.get(reverse("users:roles"))
        self.assertEqual(resp.status_code, 200)
