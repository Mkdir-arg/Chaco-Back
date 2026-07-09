from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from programas.models import Programa
from users.forms.roles import RolForm
from users.models import Capacidad, RolMeta
from users.selectors.roles import roles_filtrados_para, roles_lista_para, roles_visibles_para
from users.services.roles import RolesAdminService, RolProtegidoError


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol_admin(nombre="Admins"):
    """Crea un rol activo con capacidades de administraciÃ³n + un usuario activo."""
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
        self.assertCountEqual(rbac.capacidades_de_grupo(group), ["ciudadano.ver", "ciudadano.crear"])

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
        _rol_admin()  # otro admin para no disparar la auto-protecciÃ³n
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
        g, _u = _rol_admin()  # Ãºnico rol con administraciÃ³n
        form = RolForm(
            data={"name": g.name, "categoria": "Sistema", "capacidades": ["ciudadano.ver"]},
            instance=g,
        )
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(rbac.SinAdministradorError):
            RolesAdminService.actualizar(form, g)
        # La transacciÃ³n se revierte: el rol conserva la capacidad de administraciÃ³n
        g.refresh_from_db()
        self.assertIn("usuario.administrar", rbac.capacidades_de_grupo(g))


class RolCategoriaFormTests(TestCase):
    """Categoria del rol: sin restriccion de FK programa (RN-1 eliminada)."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")

    def test_categoria_programa_en_selector_global(self):
        choices = {value for value, _label in RolForm().fields["categoria"].choices}
        self.assertIn(rbac.CATEGORIA_PROGRAMA, choices)

    def test_alta_rol_becas_con_programa(self):  # TC-64-01
        form = RolForm(
            data={
                "name": "Coordinador Becas",
                "categoria": rbac.CATEGORIA_BECAS,
                "programa": self.becas.pk,
                "capacidades": ["relevamiento.gestionar"],
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        group = RolesAdminService.crear(form)
        self.assertEqual(group.meta.categoria, rbac.CATEGORIA_BECAS)
        self.assertEqual(group.meta.programa_id, self.becas.pk)

    def test_alta_rol_global_sin_programa(self):  # TC-64-02
        form = RolForm(
            data={
                "name": "Operador legajos",
                "categoria": "Backoffice",
                "capacidades": ["ciudadano.ver"],
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        group = RolesAdminService.crear(form)
        self.assertIsNone(group.meta.programa_id)

    def test_categoria_becas_sin_programa_valida(self):  # RN-1 eliminada: ya no requiere FK
        form = RolForm(data={"name": "Rol Becas", "categoria": rbac.CATEGORIA_BECAS})
        self.assertTrue(form.is_valid(), form.errors)

    def test_categoria_backoffice_con_programa_valida(self):  # RN-1 eliminada: FK es libre
        form = RolForm(
            data={
                "name": "Rol Backoffice",
                "categoria": "Backoffice",
                "programa": self.becas.pk,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_modelo_sin_constraint_programa(self):
        g = Group.objects.create(name="Rol Z")
        meta = RolMeta(grupo=g, categoria=rbac.CATEGORIA_NACHEC, programa=None)
        meta.full_clean()  # no debe levantar excepción

    def test_modelo_acepta_categoria_programa(self):
        g = Group.objects.create(name="Rol Programa")
        meta = RolMeta(grupo=g, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.becas)
        meta.full_clean()


class RolAlcanceTests(TestCase):
    """#66 â€" ABM de Roles con alcance de Programa."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.nachec = Programa.objects.create(codigo="NACHEC", nombre="Ã‘achec")

        # Rol administrador de Becas (programa.configurar) + su usuario.
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

        # Otro rol de Becas, un rol de Ã‘achec y un rol global.
        self.rol_becas = Group.objects.create(name="Territorial Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas,
            activo=True,
        )
        self.rol_nachec = Group.objects.create(name="Territorial Ã‘achec")
        RolMeta.objects.create(
            grupo=self.rol_nachec,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.nachec,
            activo=True,
        )
        self.rol_global = Group.objects.create(name="Backoffice X")
        RolMeta.objects.create(grupo=self.rol_global, categoria="Backoffice", activo=True)

        self.su = User.objects.create_superuser("root", "root@example.com", "x")

    # --- Listado / agrupaciÃ³n ---
    def test_listado_global_ve_todo(self):  # TC-66-01 / TC-66-10
        data = roles_visibles_para(self.su)
        cats = {c for c, _ in data["categorias"]}
        self.assertIn("Backoffice", cats)
        progs = {p.nombre for p, _ in data["programas"]}
        self.assertEqual(progs, {"Becas", "Ã‘achec"})

    def test_listado_admin_programa_solo_su_subseccion(self):  # TC-66-02
        data = roles_visibles_para(self.admin_becas)
        self.assertEqual(data["categorias"], [])
        progs = {p.nombre for p, _ in data["programas"]}
        self.assertEqual(progs, {"Becas"})
        nombres = {it["group"].name for _, items in data["programas"] for it in items}
        self.assertEqual(nombres, {"Admin Becas", "Territorial Becas"})

    def test_listado_admin_programa_incluye_categorias_programaticas(self):
        rol_becas_categoria = Group.objects.create(name="Coordinador Becas")
        RolMeta.objects.create(
            grupo=rol_becas_categoria,
            categoria=rbac.CATEGORIA_BECAS,
            programa=self.becas,
            activo=True,
        )

        data = roles_visibles_para(self.admin_becas)
        nombres = {it["group"].name for _, items in data["programas"] for it in items}
        self.assertIn("Coordinador Becas", nombres)

    def test_programa_sin_roles_no_subseccion(self):  # TC-66-11
        Programa.objects.create(codigo="VACIO", nombre="VacÃ­o")
        progs = {p.nombre for p, _ in roles_visibles_para(self.su)["programas"]}
        self.assertNotIn("VacÃ­o", progs)

    # --- Formulario ---
    def test_form_admin_programa_fija_programa_y_arbol(self):  # TC-66-03
        form = RolForm(operador=self.admin_becas)
        self.assertFalse(form.es_admin_global)
        self.assertEqual(form.programa_fijo, self.becas)
        modulos = {m["modulo"] for m in form.arbol_capacidades()}
        self.assertEqual(
            modulos,
            {
                "programas",
                "relevamientos",
                "becas_admin",
                "becas_segmentos",
                "becas_subsegmentos",
                "becas_requisitos",
                "becas_preguntas",
                "becas_coordinadores",
                "becas_convocatorias",
                "becas_relevamientos",
                "becas_revision",
                "becas_cupo",
                "becas_beneficiarios",
                "becas_campo",
            },
        )

    def test_form_admin_programa_incluye_categoria_programa(self):
        form = RolForm(operador=self.admin_becas)
        choices = {value for value, _label in form.fields["categoria"].choices}
        self.assertIn(rbac.CATEGORIA_PROGRAMA, choices)

    def test_form_admin_programa_guarda_en_su_programa(self):  # TC-66-03
        form = RolForm(
            data={"name": "Coord Becas", "categoria": rbac.CATEGORIA_BECAS, "capacidades": ["relevamiento.gestionar"]},
            operador=self.admin_becas,
        )
        self.assertTrue(form.is_valid(), form.errors)
        g = RolesAdminService.crear(form)
        self.assertEqual(g.meta.categoria, rbac.CATEGORIA_BECAS)
        self.assertEqual(g.meta.programa_id, self.becas.pk)

    def test_form_admin_programa_descarta_caps_globales(self):  # seguridad
        form = RolForm(
            data={"name": "Coord Becas 2", "capacidades": ["relevamiento.gestionar", "ciudadano.ver"]},
            operador=self.admin_becas,
        )
        self.assertFalse(form.is_valid())  # ciudadano.ver no estÃ¡ en las choices acotadas

    def test_form_global_programa_combo(self):  # TC-66-04
        form = RolForm(
            data={
                "name": "Rol Ñachec",
                "categoria": rbac.CATEGORIA_NACHEC,
                "programa": self.nachec.pk,
                "capacidades": ["relevamiento.gestionar"],
            },
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


class RolesFiltrosTests(TestCase):
    """#120 — filtros por querystring del listado de Roles (selector)."""

    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.nachec = Programa.objects.create(codigo="NACHEC", nombre="Ñachec")

        self.rol_admin_becas = Group.objects.create(name="Admin Becas")
        RolMeta.objects.create(
            grupo=self.rol_admin_becas,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas,
            activo=True,
        )
        self.rol_admin_becas.permissions.add(_perm("programa.configurar"))
        self.admin_becas = User.objects.create_user("adm-becas-filtros", password="x")
        self.admin_becas.groups.add(self.rol_admin_becas)

        self.rol_becas = Group.objects.create(name="Territorial Becas")
        RolMeta.objects.create(
            grupo=self.rol_becas,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas,
            activo=True,
            descripcion="Rol territorial de campo",
        )

        self.rol_becas_inactivo = Group.objects.create(name="Territorial Becas Inactivo")
        RolMeta.objects.create(
            grupo=self.rol_becas_inactivo,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.becas,
            activo=False,
            descripcion="Rol territorial inactivo",
        )

        self.rol_nachec = Group.objects.create(name="Territorial Ñachec")
        RolMeta.objects.create(
            grupo=self.rol_nachec,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.nachec,
            activo=True,
        )

        self.rol_global = Group.objects.create(name="Backoffice X")
        RolMeta.objects.create(
            grupo=self.rol_global,
            categoria="Backoffice",
            activo=True,
            descripcion="Rol de backoffice global",
        )
        self.rol_global.permissions.add(_perm("dashboard.ver"))

        self.su = User.objects.create_superuser("root-filtros", "root-filtros@example.com", "x")

    def test_filtros_combinados(self):  # (1) filtros combinados funcionan
        items = roles_filtrados_para(
            self.su,
            {
                "q": "territorial",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(self.becas.pk),
                "estado": "activo",
            },
        )
        nombres = {it["group"].name for it in items}
        self.assertEqual(nombres, {"Territorial Becas"})

    def test_filtro_categoria_becas(self):
        rol_becas_categoria = Group.objects.create(name="Coordinador Becas")
        RolMeta.objects.create(
            grupo=rol_becas_categoria,
            categoria=rbac.CATEGORIA_BECAS,
            programa=self.becas,
            activo=True,
        )

        items = roles_filtrados_para(self.su, {"categoria": rbac.CATEGORIA_BECAS})
        nombres = {it["group"].name for it in items}
        self.assertEqual(nombres, {"Coordinador Becas"})

    def test_filtro_estado_inactivo(self):
        items = roles_filtrados_para(self.su, {"estado": "inactivo"})
        nombres = {it["group"].name for it in items}
        self.assertIn("Territorial Becas Inactivo", nombres)
        self.assertNotIn("Admin Becas", nombres)

    def test_filtro_programa_valido(self):
        items = roles_filtrados_para(self.su, {"programa": str(self.becas.pk)})
        nombres = {it["group"].name for it in items}
        self.assertEqual(nombres, {"Admin Becas", "Territorial Becas", "Territorial Becas Inactivo"})

    def test_admin_programa_no_ve_roles_ajenos_forzando_programa(self):  # (2)
        items = roles_filtrados_para(self.admin_becas, {"programa": str(self.nachec.pk)})
        nombres = {it["group"].name for it in items}
        # El filtro de un programa que el operador no administra se ignora
        # (no amplía su alcance ni lo vacía): sigue viendo solo sus propios roles.
        self.assertEqual(nombres, {"Admin Becas", "Territorial Becas", "Territorial Becas Inactivo"})
        self.assertNotIn("Territorial Ñachec", nombres)

    def test_valores_invalidos_se_ignoran(self):  # (3)
        items = roles_filtrados_para(
            self.su,
            {"categoria": "NoExiste", "programa": "no-es-un-numero", "estado": "quien-sabe"},
        )
        # Ningún filtro tuvo efecto: se devuelve la lista completa, sin error 500.
        self.assertEqual(len(items), len(roles_lista_para(self.su)))

    def test_vista_aplica_filtros_de_la_querystring(self):
        self.client.force_login(self.su)
        resp = self.client.get(
            reverse("users:roles"),
            {"q": "territorial", "categoria": rbac.CATEGORIA_PROGRAMA, "estado": "activo"},
        )
        self.assertEqual(resp.status_code, 200)
        nombres = {it["group"].name for it in resp.context["items"]}
        self.assertEqual(nombres, {"Territorial Becas", "Territorial Ñachec"})
        self.assertIn("roles", resp.context)
        self.assertEqual(resp.context["filtro_q"], "territorial")
        self.assertEqual(resp.context["filtro_categoria"], rbac.CATEGORIA_PROGRAMA)
        self.assertEqual(resp.context["filtro_estado"], "activo")
        self.assertTrue(resp.context["hay_filtros_activos"])
        self.assertIn(rbac.CATEGORIA_PROGRAMA, resp.context["categorias_rol"])

    def test_vista_ignora_programa_ajeno_del_admin_de_programa(self):
        self.client.force_login(self.admin_becas)
        resp = self.client.get(reverse("users:roles"), {"programa": str(self.nachec.pk)})
        self.assertEqual(resp.status_code, 200)
        nombres = {it["group"].name for it in resp.context["items"]}
        self.assertEqual(nombres, {"Admin Becas", "Territorial Becas", "Territorial Becas Inactivo"})

    def test_items_exponen_labels_humanos_de_capacidades(self):
        self.client.force_login(self.su)
        resp = self.client.get(reverse("users:roles"))
        self.assertEqual(resp.status_code, 200)

        item = next(it for it in resp.context["items"] if it["group"] == self.rol_global)
        self.assertEqual(
            item["capacidades_tabla"],
            [{"codigo": "dashboard.ver", "label": "Ver dashboard"}],
        )
