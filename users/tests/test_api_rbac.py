"""La API REST de usuarios y roles queda apagada salvo `me`.

Decisión D-05 de la auditoría oct-2026: `/api/users/` exponía un ABM paralelo al
del backoffice web, sin sus reglas y con permisos propios más flojos. Cierra
SEC-05 (`activate`/`deactivate` abiertos a cualquier usuario con sesión),
SEC-16 (listado del personal con DNI e `is_superuser`) y SEC-17 (PATCH de roles
protegidos, que renombraba `Ciudadanos` y metía ciudadanos al backoffice).

Lo único que sobrevive es `/api/users/me/`, de solo lectura y sobre el propio
usuario. El ABM real vive en el backoffice web (`users/views/admin.py`).
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
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


class ApiUsuariosApagadaTests(TestCase):
    """Fuera de `me`, no queda ninguna ruta bajo `/api/users/`."""

    RUTAS_RETIRADAS = (
        "/api/users/users/",
        "/api/users/users/1/",
        "/api/users/users/1/activate/",
        "/api/users/users/1/deactivate/",
        "/api/users/users/change_password/",
        "/api/users/groups/",
        "/api/users/groups/1/",
        "/api/users/groups/1/users/",
        "/api/users/profiles/",
        "/api/users/profiles/1/",
    )

    def test_api_users_solo_me(self):
        for ruta in self.RUTAS_RETIRADAS:
            with self.subTest(ruta=ruta):
                with self.assertRaises(Resolver404):
                    resolve(ruta)

        self.assertEqual(resolve("/api/users/me/").view_name, "usuario-actual")

    def test_me_con_sesion_de_backoffice_200(self):
        usuario = _usuario_con("usuario.administrar")
        cliente = APIClient()
        cliente.force_authenticate(usuario)

        respuesta = cliente.get("/api/users/me/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["username"], usuario.username)

    def test_me_anonimo_403(self):
        self.assertEqual(APIClient().get("/api/users/me/").status_code, 403)

    def test_me_ciudadano_del_portal_403(self):
        ciudadano = User.objects.create_user("30111222", password="x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        cliente = APIClient()
        cliente.force_authenticate(ciudadano)

        self.assertEqual(cliente.get("/api/users/me/").status_code, 403)

    def test_me_ciudadano_con_sesion_lo_saca_el_middleware(self):
        ciudadano = User.objects.create_user("30111333", password="x")
        ciudadano.groups.add(Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)[0])
        self.client.force_login(ciudadano)

        respuesta = self.client.get("/api/users/me/")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("portal:home"))


class SEC05ActivateDeactivateTests(TestCase):
    """SEC-05 invertido: un usuario plano ya no desactiva a otro por API."""

    def test_usuario_sin_capacidades_no_desactiva_a_otro(self):
        User.objects.create_superuser("root", "r@x.com", "x")
        victima = User.objects.create_user("victima", password="x")
        plano = User.objects.create_user("plano", password="x")
        cliente = APIClient()
        cliente.force_authenticate(plano)

        respuesta = cliente.post(f"/api/users/users/{victima.pk}/deactivate/")

        self.assertEqual(respuesta.status_code, 404)
        victima.refresh_from_db()
        self.assertTrue(victima.is_active)

    def test_activate_tampoco_existe(self):
        inactivo = User.objects.create_user("inactivo", password="x", is_active=False)
        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user("plano", password="x"))

        respuesta = cliente.post(f"/api/users/users/{inactivo.pk}/activate/")

        self.assertEqual(respuesta.status_code, 404)
        inactivo.refresh_from_db()
        self.assertFalse(inactivo.is_active)


class SEC16UsersApiListTests(TestCase):
    """SEC-16 invertido: ya no se lista el personal con DNI e `is_superuser`."""

    def test_no_se_lista_el_personal(self):
        User.objects.create_superuser("root", "r@x.com", "x")
        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user("plano", password="x"))

        self.assertEqual(cliente.get("/api/users/users/?is_staff=true").status_code, 404)

    def test_no_se_listan_los_usuarios_de_un_rol(self):
        rol = Group.objects.create(name="Administrador")
        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user("plano", password="x"))

        self.assertEqual(cliente.get(f"/api/users/groups/{rol.pk}/users/").status_code, 404)

    def test_me_devuelve_solo_al_propio_usuario(self):
        otro = User.objects.create_superuser("root", "r@x.com", "x")
        propio = User.objects.create_user("plano", password="x")
        cliente = APIClient()
        cliente.force_authenticate(propio)

        datos = cliente.get("/api/users/me/").json()

        self.assertEqual(datos["id"], propio.pk)
        self.assertNotEqual(datos["id"], otro.pk)


class SEC17RenombrarCiudadanosTests(TestCase):
    """SEC-17 invertido: `rol.administrar` ya no renombra `Ciudadanos` por API."""

    def test_no_se_renombra_un_rol_protegido(self):
        grupo, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_PORTAL, activo=True, protegido=True)
        cliente = APIClient()
        cliente.force_authenticate(_usuario_con("rol.administrar"))

        respuesta = cliente.patch(f"/api/users/groups/{grupo.pk}/", {"name": "Ciudadanos2"}, format="json")

        self.assertEqual(respuesta.status_code, 404)
        grupo.refresh_from_db()
        self.assertEqual(grupo.name, rbac.GRUPO_CIUDADANO_PORTAL)

    def test_no_se_crean_usuarios_por_api(self):
        cliente = APIClient()
        cliente.force_authenticate(_usuario_con("usuario.administrar"))

        respuesta = cliente.post(
            "/api/users/users/",
            {"username": "nuevo", "password": "clave12345", "password_confirm": "clave12345"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 404)
        self.assertFalse(User.objects.filter(username="nuevo").exists())
