from django.contrib.auth.models import AnonymousUser, Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from core import rbac
from legajos.models_programas import Programa
from users.models import Capacidad, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def render_sidebar(user):
    """Renderiza el sidebar del backoffice para ``user`` de forma aislada.

    Evita falsos positivos: el cuerpo de las páginas (p. ej. ``core:inicio``)
    puede contener enlaces/textos que en el menú están gateados por capacidad.
    """
    req = RequestFactory().get("/")
    req.user = user
    req.resolver_match = None
    return render_to_string(
        "includes/sidebar/opciones.html", {"request": req, "branding": {}}
    )


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


class MotorPuedeProgramaTests(TestCase):
    """#65 — puede()/puede_alguna() con alcance de Programa (retrocompatible)."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.nachec = Programa.objects.create(codigo="NACHEC", nombre="Ñachec")
        self.rol = Group.objects.create(name="Territorial Becas")
        RolMeta.objects.create(
            grupo=self.rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.rol.permissions.add(_perm("relevamiento.gestionar"))
        self.user = User.objects.create_user("terri", password="x")
        self.user.groups.add(self.rol)

    def _u(self):
        return User.objects.get(pk=self.user.pk)  # limpia el cache de permisos

    def test_alcance_correcto(self):  # TC-65-01
        self.assertTrue(rbac.puede(self._u(), "relevamiento.gestionar", programa=self.becas))

    def test_otro_programa_false(self):  # TC-65-02
        self.assertFalse(rbac.puede(self._u(), "relevamiento.gestionar", programa=self.nachec))

    def test_sin_alcance_retrocompat(self):  # TC-65-03
        self.assertTrue(rbac.puede(self._u(), "relevamiento.gestionar"))

    def test_capacidad_global_ignora_alcance(self):  # TC-65-04
        rol_g = Group.objects.create(name="Ve ciudadanos")
        RolMeta.objects.create(grupo=rol_g, categoria="Backoffice", activo=True)
        rol_g.permissions.add(_perm("ciudadano.ver"))
        u = User.objects.create_user("verciu", password="x")
        u.groups.add(rol_g)
        u = User.objects.get(pk=u.pk)
        self.assertTrue(rbac.puede(u, "ciudadano.ver", programa=self.becas))
        self.assertTrue(rbac.puede(u, "ciudadano.ver", programa=self.nachec))

    def test_rol_programa_inactivo(self):  # TC-65-05
        self.rol.meta.activo = False
        self.rol.meta.save(update_fields=["activo"])
        self.assertFalse(rbac.puede(self._u(), "relevamiento.gestionar", programa=self.becas))

    def test_superuser_bypass_scoped(self):  # TC-65-06
        su = User.objects.create_superuser("root", "root@example.com", "x")
        self.assertTrue(rbac.puede(su, "relevamiento.gestionar", programa=self.becas))

    def test_global_mas_programa_se_unen(self):  # TC-65-07
        rol_g = Group.objects.create(name="Ve ciudadanos")
        RolMeta.objects.create(grupo=rol_g, categoria="Backoffice", activo=True)
        rol_g.permissions.add(_perm("ciudadano.ver"))
        self.user.groups.add(rol_g)
        u = self._u()
        self.assertTrue(rbac.puede(u, "ciudadano.ver"))
        self.assertTrue(rbac.puede(u, "relevamiento.gestionar", programa=self.becas))
        self.assertFalse(rbac.puede(u, "relevamiento.gestionar", programa=self.nachec))

    def test_usuario_inactivo(self):  # TC-65-08
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertFalse(rbac.puede(self._u(), "relevamiento.gestionar", programa=self.becas))

    def test_template_tag_puede_en(self):  # TC-65-09
        from core.templatetags.rbac import puede_en
        u = self._u()
        self.assertTrue(puede_en(u, "relevamiento.gestionar", programa=self.becas))
        self.assertFalse(puede_en(u, "relevamiento.gestionar", programa=self.nachec))

    def test_rol_global_con_capacidad_de_programa_cuenta(self):  # RN-3
        rol_g = Group.objects.create(name="Admin total")
        RolMeta.objects.create(grupo=rol_g, categoria="Sistema", activo=True, programa=None)
        rol_g.permissions.add(_perm("relevamiento.gestionar"))
        u = User.objects.create_user("global", password="x")
        u.groups.add(rol_g)
        u = User.objects.get(pk=u.pk)
        self.assertTrue(rbac.puede(u, "relevamiento.gestionar", programa=self.becas))
        self.assertTrue(rbac.puede(u, "relevamiento.gestionar", programa=self.nachec))

    def test_no_falso_positivo_por_rol_global_ajeno(self):
        # Regresión: un rol global (programa=null) con la cap, al que el usuario NO
        # pertenece, no debe otorgársela en un programa donde no la tiene.
        glob = Group.objects.create(name="Admin total ajeno")
        RolMeta.objects.create(grupo=glob, categoria="Sistema", activo=True, programa=None)
        glob.permissions.add(_perm("relevamiento.gestionar"))  # el user NO está en glob
        u = self._u()
        self.assertTrue(rbac.puede(u, "relevamiento.gestionar", programa=self.becas))
        self.assertFalse(rbac.puede(u, "relevamiento.gestionar", programa=self.nachec))

    def test_no_falso_positivo_por_cap_en_otro_programa(self):
        # Regresión: la cap del user está en Becas; que un rol AJENO de Ñachec tenga
        # la misma cap no debe hacer que puede(..., programa=ñachec) dé True.
        otro = Group.objects.create(name="Territorial Ñachec ajeno")
        RolMeta.objects.create(
            grupo=otro, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.nachec, activo=True
        )
        otro.permissions.add(_perm("relevamiento.gestionar"))  # el user NO está en otro
        u = self._u()
        self.assertFalse(rbac.puede(u, "relevamiento.gestionar", programa=self.nachec))


class AutoProteccionProgramaTests(TestCase):
    """#68 — asegurar_admin_restante(programa) (RN-8) + superusuario cuenta."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.rol = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas, activo=True
        )
        self.rol.permissions.add(_perm("programa.configurar"))
        self.maria = User.objects.create_user("maria", password="x")
        self.maria.groups.add(self.rol)

    def test_con_admin_no_lanza(self):  # TC-68-03 (base)
        rbac.asegurar_admin_restante(programa=self.becas)

    def test_programa_sin_admin_lanza(self):
        otro = Programa.objects.create(codigo="OTRO", nombre="Otro")
        with self.assertRaises(rbac.SinAdministradorProgramaError):
            rbac.asegurar_admin_restante(programa=otro)

    def test_rol_configurar_inactivo_no_cuenta(self):  # TC-68-08
        self.rol.meta.activo = False
        self.rol.meta.save(update_fields=["activo"])
        with self.assertRaises(rbac.SinAdministradorProgramaError):
            rbac.asegurar_admin_restante(programa=self.becas)

    def test_usuario_inactivo_no_cuenta(self):
        self.maria.is_active = False
        self.maria.save(update_fields=["is_active"])
        with self.assertRaises(rbac.SinAdministradorProgramaError):
            rbac.asegurar_admin_restante(programa=self.becas)

    def test_superusuario_cuenta(self):  # decisión PM: el superuser cuenta
        self.maria.delete()
        User.objects.create_superuser("root", "root@example.com", "x")
        rbac.asegurar_admin_restante(programa=self.becas)  # no lanza

    def test_es_subclase_de_sin_administrador_error(self):
        self.assertTrue(
            issubclass(rbac.SinAdministradorProgramaError, rbac.SinAdministradorError)
        )

    def test_check_global_retrocompatible_sin_programa(self):
        # Sin programa sigue siendo el check global (no hay admin global → lanza).
        with self.assertRaises(rbac.SinAdministradorError):
            rbac.asegurar_admin_restante()


class CatalogoProgramaTests(TestCase):
    """#64 — el catálogo distingue módulos 'de programa' de los globales."""

    def test_modulos_de_programa_cerrados(self):  # TC-64-05
        de_programa = {m["modulo"] for m in rbac.CATALOGO if m.get("alcance") == "programa"}
        self.assertEqual(de_programa, {"programas", "relevamientos"})

    def test_codigos_y_helper_de_programa(self):
        cods = rbac.codigos_de_programa()
        self.assertIn("relevamiento.gestionar", cods)
        self.assertIn("programa.configurar", cods)
        self.assertNotIn("ciudadano.ver", cods)
        self.assertTrue(rbac.es_codigo_de_programa("relevamiento.gestionar"))
        self.assertFalse(rbac.es_codigo_de_programa("ciudadano.ver"))
