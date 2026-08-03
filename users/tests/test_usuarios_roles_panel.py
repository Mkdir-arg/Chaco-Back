"""Panel "Roles por categoría" del ABM de Usuarios (agrupación + render del template)."""

from django.contrib.auth.models import Group, User
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase

from core import rbac
from programas.models import Programa
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import RolMeta


def _programa(codigo, nombre):
    """Los programas base los siembra una migración: reusarlos en vez de duplicar."""
    existente = Programa.objects.filter(codigo=codigo).first()
    if existente is not None:
        return existente
    return Programa.objects.create(codigo=codigo, nombre=nombre, estado=Programa.Estado.ACTIVO)


def _rol(nombre, categoria, programa=None, descripcion="", activo=True):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=categoria,
        programa=programa,
        descripcion=descripcion,
        activo=activo,
    )
    return grupo


class RolesPorCategoriaTests(TestCase):
    def setUp(self):
        self.programa_becas = _programa("BECAS", "Becas")
        self.programa_disp = _programa("DISPOSITIVOS", "Dispositivos")
        self.rol_backoffice = _rol("Operador legajos", rbac.CATEGORIA_BACKOFFICE, descripcion="Carga legajos")
        self.rol_sistema = _rol("Auditor", rbac.CATEGORIA_SISTEMA)
        self.rol_becas = _rol("Coordinador Becas", rbac.CATEGORIA_BECAS)
        self.rol_prog_becas = _rol("Operador Becas", rbac.CATEGORIA_PROGRAMA, programa=self.programa_becas)
        self.rol_prog_disp = _rol("Operador Dispositivos", rbac.CATEGORIA_PROGRAMA, programa=self.programa_disp)

    def _tabs(self, form):
        return {tab["label"]: tab for tab in form.roles_por_categoria()}

    def test_agrupa_por_categoria_en_el_orden_canonico(self):
        tabs = [tab["label"] for tab in UserCreationForm().roles_por_categoria()]
        # Solo categorías con roles asignables, en el orden de rbac.CATEGORIAS_ROL.
        self.assertEqual(
            tabs,
            [rbac.CATEGORIA_BACKOFFICE, rbac.CATEGORIA_SISTEMA, rbac.CATEGORIA_BECAS, rbac.CATEGORIA_PROGRAMA],
        )

    def test_tab_expone_id_slug_y_total(self):
        """El id es el slug de la categoría (lo usan data-tab / aria-controls del panel)."""
        tabs = self._tabs(UserCreationForm())
        self.assertEqual(tabs[rbac.CATEGORIA_BECAS]["id"], "becas")
        self.assertEqual(tabs[rbac.CATEGORIA_BECAS]["total"], 1)

    def test_id_de_tab_sin_acentos_ni_espacios(self):
        _rol("Referente institucional", rbac.CATEGORIA_INSTITUCION)
        tab = self._tabs(UserCreationForm())[rbac.CATEGORIA_INSTITUCION]
        self.assertEqual(tab["id"], "institucion")

    def test_categoria_programa_subagrupa_por_programa(self):
        tab = self._tabs(UserCreationForm())[rbac.CATEGORIA_PROGRAMA]
        self.assertEqual([g["label"] for g in tab["grupos"]], ["Becas", "Dispositivos"])
        self.assertEqual(
            [r["nombre"] for g in tab["grupos"] for r in g["roles"]], ["Operador Becas", "Operador Dispositivos"]
        )

    def test_categorias_no_programa_van_en_una_sola_tarjeta_sin_titulo(self):
        grupos = self._tabs(UserCreationForm())[rbac.CATEGORIA_BACKOFFICE]["grupos"]
        self.assertEqual(len(grupos), 1)
        self.assertEqual(grupos[0]["label"], "")

    def test_rol_expone_descripcion_para_la_ficha(self):
        rol = self._tabs(UserCreationForm())[rbac.CATEGORIA_BACKOFFICE]["grupos"][0]["roles"][0]
        self.assertEqual(rol["descripcion"], "Carga legajos")
        self.assertFalse(rol["checked"])

    def test_marca_los_roles_del_usuario_al_editar(self):
        user = User.objects.create_user("juana", password="x")
        user.groups.add(self.rol_becas, self.rol_prog_disp)
        tabs = self._tabs(CustomUserChangeForm(instance=user))
        tildados = {
            rol["nombre"]
            for tab in tabs.values()
            for grupo in tab["grupos"]
            for rol in grupo["roles"]
            if rol["checked"]
        }
        self.assertEqual(tildados, {"Coordinador Becas", "Operador Dispositivos"})

    def test_conserva_lo_tildado_cuando_el_post_es_invalido(self):
        """Un POST que no valida no debe perder los roles que el operador tildó."""
        form = UserCreationForm(data={"username": "", "email": "", "password": "", "groups": [str(self.rol_becas.pk)]})
        self.assertFalse(form.is_valid())
        rol = self._tabs(form)[rbac.CATEGORIA_BECAS]["grupos"][0]["roles"][0]
        self.assertTrue(rol["checked"])

    def test_rol_inactivo_asignado_se_marca_como_inactivo(self):
        rol_viejo = _rol("Rol discontinuado", rbac.CATEGORIA_BACKOFFICE, activo=False)
        user = User.objects.create_user("pedro", password="x")
        user.groups.add(rol_viejo)
        roles = self._tabs(CustomUserChangeForm(instance=user))[rbac.CATEGORIA_BACKOFFICE]["grupos"][0]["roles"]
        inactivos = [r["nombre"] for r in roles if r["inactivo"]]
        self.assertEqual(inactivos, ["Rol discontinuado"])

    def test_rol_territorial_de_becas_queda_marcado_para_el_campo_segmento(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_becas", stdout=StringIO())
        from programas.management.commands.seed_becas import ROL_TERRITORIAL

        territoriales = [
            rol["nombre"]
            for tab in UserCreationForm().roles_por_categoria()
            for grupo in tab["grupos"]
            for rol in grupo["roles"]
            if rol["territorial"]
        ]
        self.assertIn(ROL_TERRITORIAL, territoriales)


class UserFormTemplateTests(TestCase):
    """El template renderiza el panel con checkboxes ``groups`` (sin JS de por medio)."""

    def setUp(self):
        self.programa = _programa("BECAS", "Becas")
        self.rol = _rol("Coordinador Becas", rbac.CATEGORIA_BECAS, descripcion="Revisa formularios")
        self.rol_programa = _rol("Operador Becas", rbac.CATEGORIA_PROGRAMA, programa=self.programa)
        self.admin = User.objects.create_superuser("admin_tpl", "a@a.com", "x")

    def _render(self, form, obj=None):
        request = RequestFactory().get("/usuarios/editar/1/")
        request.user = self.admin
        return render_to_string("user/user_form.html", {"form": form, "object": obj}, request=request)

    def test_renderiza_solapas_y_checkboxes_de_roles(self):
        html = self._render(UserCreationForm())
        self.assertIn("Roles por categoría", html)
        self.assertIn('data-tab="becas"', html)
        self.assertIn('data-tab="programa"', html)
        self.assertIn(f'name="groups" value="{self.rol.pk}"', html)
        self.assertIn("Revisa formularios", html)

    def test_los_roles_asignados_se_renderizan_tildados(self):
        user = User.objects.create_user("juan", password="x")
        user.groups.add(self.rol)
        html = self._render(CustomUserChangeForm(instance=user), obj=user)
        marca = html.split(f'name="groups" value="{self.rol.pk}"')[1][:400]
        self.assertIn("checked", marca)

    def test_el_alta_pide_contrasena_y_la_edicion_no(self):
        self.assertIn('name="password"', self._render(UserCreationForm()))
        user = User.objects.create_user("juan2", password="x")
        self.assertNotIn('name="password"', self._render(CustomUserChangeForm(instance=user), obj=user))
