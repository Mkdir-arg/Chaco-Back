from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models_programas import Programa
from users.forms.roles import RolForm
from users.models import Capacidad, RolMeta
from users.selectors.roles import roles_visibles_para
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


class RolProgramaFormTests(TestCase):
    """#64 — categoría 'Programa' + FK programa con validación cruzada RN-1."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")

    def test_alta_rol_programa_valido(self):  # TC-64-01
        form = RolForm(data={
            "name": "Coordinador Becas",
            "categoria": rbac.CATEGORIA_PROGRAMA,
            "programa": self.becas.pk,
            "capacidades": ["relevamiento.gestionar"],
        })
        self.assertTrue(form.is_valid(), form.errors)
        group = RolesAdminService.crear(form)
        self.assertEqual(group.meta.categoria, rbac.CATEGORIA_PROGRAMA)
        self.assertEqual(group.meta.programa_id, self.becas.pk)

    def test_alta_rol_global_sin_programa(self):  # TC-64-02
        form = RolForm(data={
            "name": "Operador legajos",
            "categoria": "Backoffice",
            "capacidades": ["ciudadano.ver"],
        })
        self.assertTrue(form.is_valid(), form.errors)
        group = RolesAdminService.crear(form)
        self.assertIsNone(group.meta.programa_id)

    def test_categoria_programa_sin_programa_invalida(self):  # TC-64-03
        form = RolForm(data={"name": "Rol X", "categoria": rbac.CATEGORIA_PROGRAMA})
        self.assertFalse(form.is_valid())
        self.assertIn("programa", form.errors)

    def test_categoria_no_programa_con_programa_invalida(self):  # TC-64-04
        form = RolForm(data={
            "name": "Rol Y", "categoria": "Backoffice", "programa": self.becas.pk,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("programa", form.errors)

    def test_modelo_clean_valida_rn1(self):
        from django.core.exceptions import ValidationError
        g = Group.objects.create(name="Rol Z")
        meta = RolMeta(grupo=g, categoria=rbac.CATEGORIA_PROGRAMA, programa=None)
        with self.assertRaises(ValidationError):
            meta.full_clean()


class RolAlcanceTests(TestCase):
    """#66 — ABM de Roles con alcance de Programa."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.nachec = Programa.objects.create(codigo="NACHEC", nombre="Ñachec")

        # Rol administrador de Becas (programa.configurar) + su usuario.
        self.rol_admin_becas = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol_admin_becas, categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas, activo=True,
        )
        self.rol_admin_becas.permissions.add(_perm("programa.configurar"))
        self.admin_becas = User.objects.create_user("adm-becas", password="x")
        self.admin_becas.groups.add(self.rol_admin_becas)

        # Otro rol de Becas, un rol de Ñachec y un rol global.
        self.rol_becas = Group.objects.create(name="Territorial Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas, categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas, activo=True,
        )
        self.rol_nachec = Group.objects.create(name="Territorial Ñachec")
        RolMeta.objects.create(
            grupo=self.rol_nachec, categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.nachec, activo=True,
        )
        self.rol_global = Group.objects.create(name="Backoffice X")
        RolMeta.objects.create(grupo=self.rol_global, categoria="Backoffice", activo=True)

        self.su = User.objects.create_superuser("root", "root@example.com", "x")

    # --- Listado / agrupación ---
    def test_listado_global_ve_todo(self):  # TC-66-01 / TC-66-10
        data = roles_visibles_para(self.su)
        cats = {c for c, _ in data["categorias"]}
        self.assertIn("Backoffice", cats)
        progs = {p.nombre for p, _ in data["programas"]}
        self.assertEqual(progs, {"Becas", "Ñachec"})

    def test_listado_admin_programa_solo_su_subseccion(self):  # TC-66-02
        data = roles_visibles_para(self.admin_becas)
        self.assertEqual(data["categorias"], [])
        progs = {p.nombre for p, _ in data["programas"]}
        self.assertEqual(progs, {"Becas"})
        nombres = {it["group"].name for _, items in data["programas"] for it in items}
        self.assertEqual(nombres, {"Admin Becas", "Territorial Becas"})

    def test_programa_sin_roles_no_subseccion(self):  # TC-66-11
        Programa.objects.create(codigo="VACIO", nombre="Vacío")
        progs = {p.nombre for p, _ in roles_visibles_para(self.su)["programas"]}
        self.assertNotIn("Vacío", progs)

    # --- Formulario ---
    def test_form_admin_programa_fija_programa_y_arbol(self):  # TC-66-03
        form = RolForm(operador=self.admin_becas)
        self.assertFalse(form.es_admin_global)
        self.assertEqual(form.programa_fijo, self.becas)
        modulos = {m["modulo"] for m in form.arbol_capacidades()}
        self.assertEqual(modulos, {"programas", "relevamientos"})

    def test_form_admin_programa_guarda_en_su_programa(self):  # TC-66-03
        form = RolForm(
            data={"name": "Coord Becas", "capacidades": ["relevamiento.gestionar"]},
            operador=self.admin_becas,
        )
        self.assertTrue(form.is_valid(), form.errors)
        g = RolesAdminService.crear(form)
        self.assertEqual(g.meta.categoria, rbac.CATEGORIA_PROGRAMA)
        self.assertEqual(g.meta.programa_id, self.becas.pk)

    def test_form_admin_programa_descarta_caps_globales(self):  # seguridad
        form = RolForm(
            data={"name": "Coord Becas 2", "capacidades": ["relevamiento.gestionar", "ciudadano.ver"]},
            operador=self.admin_becas,
        )
        self.assertFalse(form.is_valid())  # ciudadano.ver no está en las choices acotadas

    def test_form_global_programa_combo(self):  # TC-66-04
        form = RolForm(
            data={"name": "Rol Ñachec", "categoria": rbac.CATEGORIA_PROGRAMA,
                  "programa": self.nachec.pk, "capacidades": ["relevamiento.gestionar"]},
            operador=self.su,
        )
        self.assertTrue(form.is_valid(), form.errors)
        g = RolesAdminService.crear(form)
        self.assertEqual(g.meta.programa_id, self.nachec.pk)

    def test_form_global_no_programa_arbol_completo(self):  # TC-66-05
        form = RolForm(operador=self.su)
        self.assertTrue(form.es_admin_global)
        modulos = {m["modulo"] for m in form.arbol_capacidades()}
        self.assertIn("ciudadanos", modulos)
        self.assertIn("conversaciones", modulos)

    # --- Acceso por objeto ---
    def test_acceso_directo_a_rol_de_otro_programa_redirige(self):  # TC-66-06
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:rol_editar", args=[self.rol_nachec.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_acceso_directo_a_rol_global_redirige(self):  # TC-66-07
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:rol_editar", args=[self.rol_global.pk]))
        self.assertEqual(resp.status_code, 302)

    def test_admin_programa_edita_su_rol(self):
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:rol_editar", args=[self.rol_becas.pk]))
        self.assertEqual(resp.status_code, 200)

    def test_configurar_inactivo_sin_acceso(self):  # TC-66-09
        self.rol_admin_becas.meta.activo = False
        self.rol_admin_becas.meta.save(update_fields=["activo"])
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:roles"))
        self.assertEqual(resp.status_code, 302)

    def test_superuser_lista_entra(self):  # TC-66-10
        self.client.force_login(self.su)
        self.assertEqual(self.client.get(reverse("users:roles")).status_code, 200)


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
