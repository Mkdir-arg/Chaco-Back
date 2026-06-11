from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core import rbac
from users.models import Capacidad, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


class TraduccionCapacidadTests(TestCase):
    def test_codename_y_perm(self):
        self.assertEqual(rbac.codename_de("ciudadano.ver"), "ciudadano_ver")
        self.assertEqual(rbac.perm_de("ciudadano.ver"), "users.ciudadano_ver")

    def test_catalogo_capacidades_sin_duplicados(self):
        codigos = rbac.codigos_de_capacidad()
        self.assertEqual(len(codigos), len(set(codigos)))
        self.assertIn("usuario.administrar", codigos)
        self.assertIn("reporte.ver", codigos)


class MotorPuedeTests(TestCase):
    def setUp(self):
        self.rol = Group.objects.create(name="Operador ciudadanos")
        RolMeta.objects.create(grupo=self.rol, categoria="Backoffice", activo=True)
        self.rol.permissions.add(_perm("ciudadano.ver"))

    def test_puede_por_rol(self):
        user = User.objects.create_user("op", password="x")
        user.groups.add(self.rol)
        user = User.objects.get(pk=user.pk)  # limpia cache de permisos
        self.assertTrue(rbac.puede(user, "ciudadano.ver"))
        self.assertFalse(rbac.puede(user, "ciudadano.crear"))

    def test_superuser_activo_bypass(self):
        su = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertTrue(rbac.puede(su, "ciudadano.ver"))
        self.assertTrue(rbac.puede(su, "rol.administrar"))

    def test_superuser_inactivo_no_pasa(self):
        su = User.objects.create_superuser("root2", "root2@example.com", "x")
        su.is_active = False
        su.save()
        su = User.objects.get(pk=su.pk)
        self.assertFalse(rbac.puede(su, "ciudadano.ver"))

    def test_usuario_inactivo_no_pasa(self):
        user = User.objects.create_user("op2", password="x")
        user.groups.add(self.rol)
        user.is_active = False
        user.save()
        user = User.objects.get(pk=user.pk)
        self.assertFalse(rbac.puede(user, "ciudadano.ver"))

    def test_anonimo_no_pasa(self):
        self.assertFalse(rbac.puede(AnonymousUser(), "ciudadano.ver"))
        self.assertFalse(rbac.puede(None, "ciudadano.ver"))


class IdentidadCiudadanoPortalTests(TestCase):
    def test_es_ciudadano_portal(self):
        ciudadanos = Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        ciudadano = User.objects.create_user("juan", password="x")
        ciudadano.groups.add(ciudadanos)
        operador = User.objects.create_user("ope", password="x")

        self.assertTrue(rbac.es_ciudadano_portal(User.objects.get(pk=ciudadano.pk)))
        self.assertFalse(rbac.es_ciudadano_portal(User.objects.get(pk=operador.pk)))


class SeedRbacTests(TestCase):
    def test_seed_idempotente_y_administrador_completo(self):
        Group.objects.create(name="GrupoPrevio")  # sin RolMeta

        call_command("seed_rbac", verbosity=0)
        call_command("seed_rbac", verbosity=0)  # 2da corrida: no debe duplicar

        ct = ContentType.objects.get_for_model(Capacidad)
        total_caps = len(rbac.todas_las_capacidades())
        self.assertEqual(Permission.objects.filter(content_type=ct).count(), total_caps)

        admin = Group.objects.get(name=rbac.ROL_ADMINISTRADOR)
        self.assertTrue(admin.meta.protegido)
        self.assertEqual(admin.meta.categoria, rbac.CATEGORIA_SISTEMA)
        self.assertEqual(admin.permissions.count(), total_caps)

        # RolMeta creada para el grupo preexistente
        self.assertTrue(RolMeta.objects.filter(grupo__name="GrupoPrevio").exists())

    def test_seed_asigna_rol_a_superusuario(self):
        su = User.objects.create_superuser("root", "root@example.com", "x")
        call_command("seed_rbac", verbosity=0)
        su = User.objects.get(pk=su.pk)
        self.assertTrue(su.groups.filter(name=rbac.ROL_ADMINISTRADOR).exists())
        self.assertTrue(rbac.puede(su, "usuario.administrar"))


class AutoProteccionTests(TestCase):
    def test_asegurar_admin_restante(self):
        # Sin administradores -> lanza
        with self.assertRaises(rbac.SinAdministradorError):
            rbac.asegurar_admin_restante()

        # Con un rol que administra y un usuario activo -> no lanza
        rol = Group.objects.create(name="Admins")
        RolMeta.objects.create(grupo=rol, categoria="Sistema", activo=True)
        rol.permissions.add(_perm("usuario.administrar"))
        user = User.objects.create_user("admin1", password="x")
        user.groups.add(rol)

        rbac.asegurar_admin_restante()  # no debe lanzar
        self.assertIn(user, list(rbac.usuarios_que_administran()))

    def test_superusuario_cuenta_como_admin(self):
        User.objects.create_superuser("root", "root@example.com", "x")
        rbac.asegurar_admin_restante()  # el superusuario alcanza


class RolInactivoTests(TestCase):
    def test_rol_inactivo_no_otorga_capacidad(self):
        rol = Group.objects.create(name="Operador")
        meta = RolMeta.objects.create(grupo=rol, categoria="Backoffice", activo=True)
        rol.permissions.add(_perm("ciudadano.ver"))
        user = User.objects.create_user("op", password="x")
        user.groups.add(rol)

        # Rol activo -> otorga la capacidad
        self.assertTrue(rbac.puede(User.objects.get(pk=user.pk), "ciudadano.ver"))

        # Rol desactivado -> deja de otorgarla (aunque el usuario lo conserve)
        meta.activo = False
        meta.save(update_fields=["activo"])
        recargado = User.objects.get(pk=user.pk)
        self.assertFalse(rbac.puede(recargado, "ciudadano.ver"))
        self.assertTrue(recargado.groups.filter(name="Operador").exists())  # sigue asignado


class VistasProtegidasPorCapacidadTests(TestCase):
    """Las vistas (no solo el sidebar) exigen la capacidad por URL directa."""

    def _user_con(self, *codigos):
        g = Group.objects.create(name="Rol-" + "-".join(codigos or ["sin"]))
        RolMeta.objects.create(grupo=g, categoria="Backoffice", activo=True)
        for c in codigos:
            g.permissions.add(_perm(c))
        u = User.objects.create_user("u-" + "-".join(codigos or ["sin"]), password="x")
        u.groups.add(g)
        return u

    def test_listado_ciudadanos_sin_capacidad_redirige(self):
        self.client.force_login(User.objects.create_user("plano", password="x"))
        self.assertEqual(self.client.get(reverse("legajos:ciudadanos")).status_code, 302)

    def test_listado_ciudadanos_con_capacidad_entra(self):
        self.client.force_login(self._user_con("ciudadano.ver"))
        self.assertEqual(self.client.get(reverse("legajos:ciudadanos")).status_code, 200)

    def test_dashboard_sin_capacidad_redirige(self):
        self.client.force_login(self._user_con("ciudadano.ver"))  # no tiene dashboard.ver
        self.assertEqual(
            self.client.get(reverse("legajos:dashboard_contactos")).status_code, 302
        )


class PortalCiudadanoSinLegajoTests(TestCase):
    """Un usuario con el marcador de portal pero sin legajo no debe romper (500)."""

    def test_portal_sin_legajo_redirige_sin_500(self):
        g = Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        RolMeta.objects.create(grupo=g, categoria="Portal", activo=True)
        u = User.objects.create_user("laura", password="x")
        u.groups.add(g)
        self.client.force_login(u)

        resp = self.client.get(reverse("portal:ciudadano_mi_perfil"))
        self.assertEqual(resp.status_code, 302)  # degrada al login, no 500
