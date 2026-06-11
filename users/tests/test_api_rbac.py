from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from core import rbac
from users.models import Capacidad, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _usuario_con(*codigos):
    g, _ = Group.objects.get_or_create(name="RolAPI")
    RolMeta.objects.get_or_create(grupo=g, defaults={"categoria": "Sistema", "activo": True})
    for c in codigos:
        g.permissions.add(_perm(c))
    u = User.objects.create_user(f"u-{'-'.join(codigos)}", password="x")
    u.groups.add(g)
    return u


class ApiUsuariosRbacTests(TestCase):
    def test_crear_usuario_sin_capacidad_devuelve_403(self):
        c = APIClient()
        c.force_authenticate(User.objects.create_user("plano", password="x"))
        resp = c.post("/api/users/users/", {"username": "nuevo", "password": "clave12345", "password_confirm": "clave12345"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_crear_usuario_con_capacidad_ok(self):
        c = APIClient()
        c.force_authenticate(_usuario_con("usuario.administrar"))
        resp = c.post(
            "/api/users/users/",
            {"username": "nuevo", "password": "clave12345", "password_confirm": "clave12345"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username="nuevo").exists())

    def test_borrado_fisico_deshabilitado_405(self):
        admin = _usuario_con("usuario.administrar")
        target = User.objects.create_user("target", password="x")
        c = APIClient()
        c.force_authenticate(admin)
        resp = c.delete(f"/api/users/users/{target.pk}/")
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(User.objects.filter(pk=target.pk).exists())

    def test_deactivate_no_propio_usuario(self):
        admin = _usuario_con("usuario.administrar")
        c = APIClient()
        c.force_authenticate(admin)
        resp = c.post(f"/api/users/users/{admin.pk}/deactivate/")
        self.assertEqual(resp.status_code, 400)
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)


class ApiRolesRbacTests(TestCase):
    def test_crear_rol_sin_capacidad_403(self):
        c = APIClient()
        c.force_authenticate(_usuario_con("usuario.administrar"))  # no tiene rol.administrar
        resp = c.post("/api/users/groups/", {"name": "X"}, format="json")
        self.assertEqual(resp.status_code, 403)

    def test_eliminar_rol_protegido_400(self):
        admin = _usuario_con("rol.administrar")
        protegido = Group.objects.create(name="Protegido")
        RolMeta.objects.create(grupo=protegido, categoria="Sistema", protegido=True)
        c = APIClient()
        c.force_authenticate(admin)
        resp = c.delete(f"/api/users/groups/{protegido.pk}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Group.objects.filter(pk=protegido.pk).exists())
