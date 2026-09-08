"""Panel "Roles por ámbito" del ABM de Usuarios (agrupación + render del template)."""

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


class RolesPorAmbitoTests(TestCase):
    def setUp(self):
        self.programa_becas = _programa("BECAS", "Becas")
        self.programa_disp = _programa("DISPOSITIVOS", "Dispositivos")
        self.rol_backoffice = _rol("Operador legajos", rbac.CATEGORIA_BACKOFFICE, descripcion="Carga legajos")
        self.rol_sistema = _rol("Auditor", rbac.CATEGORIA_SISTEMA)
        # "Territorial" es el rol legacy con categoría Becas y sin programa: tiene que
        # caer en la MISMA solapa que los roles del programa Becas.
        self.rol_cat_becas = _rol("Territorial", rbac.CATEGORIA_BECAS)
        self.rol_prog_becas = _rol("Becas — Coordinador", rbac.CATEGORIA_PROGRAMA, programa=self.programa_becas)
        self.rol_prog_disp = _rol("Operador Dispositivos", rbac.CATEGORIA_PROGRAMA, programa=self.programa_disp)

    def _tabs(self, form):
        return {tab["label"]: tab for tab in form.roles_por_ambito()}

    def _roles(self, form, label):
        return [rol["nombre"] for rol in self._tabs(form)[label]["roles"]]

    def test_una_solapa_por_ambito_sin_solapa_programa(self):
        """Cada programa es su propia solapa: no existe una solapa "Programa" contenedora."""
        labels = [tab["label"] for tab in UserCreationForm().roles_por_ambito()]
        self.assertNotIn(rbac.CATEGORIA_PROGRAMA, labels)
        self.assertEqual(
            labels,
            [rbac.CATEGORIA_BACKOFFICE, rbac.CATEGORIA_SISTEMA, rbac.CATEGORIA_BECAS, "Dispositivos"],
        )

    def test_categoria_becas_y_programa_becas_van_en_la_misma_solapa(self):
        tab = self._tabs(UserCreationForm())[rbac.CATEGORIA_BECAS]
        self.assertEqual(tab["total"], 2)
        self.assertEqual(sorted(r["nombre"] for r in tab["roles"]), ["Becas — Coordinador", "Territorial"])

    def test_solapa_expone_id_slug_y_total(self):
        """El id es el slug del ámbito (lo usan data-tab / aria-controls del panel)."""
        tabs = self._tabs(UserCreationForm())
        self.assertEqual(tabs["Dispositivos"]["id"], "dispositivos")
        self.assertEqual(tabs["Dispositivos"]["total"], 1)

    def test_id_de_solapa_sin_acentos_ni_espacios(self):
        _rol("Referente institucional", rbac.CATEGORIA_INSTITUCION)
        self.assertEqual(self._tabs(UserCreationForm())[rbac.CATEGORIA_INSTITUCION]["id"], "institucion")

    def test_ids_de_solapa_no_chocan_entre_ambitos_parecidos(self):
        """Dos ámbitos que slugifican igual no pueden compartir data-tab."""
        _rol("Rol Ñachec", rbac.CATEGORIA_PROGRAMA, programa=_programa("NACHEC1", "Ñachec"))
        _rol("Rol Nachec", rbac.CATEGORIA_PROGRAMA, programa=_programa("NACHEC2", "Nachec"))
        ids = [tab["id"] for tab in UserCreationForm().roles_por_ambito()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_roles_de_programa_sin_programa_van_al_final(self):
        """El bug de RolMeta.programa en NULL queda visible en su propia solapa, última."""
        _rol("Rol huérfano", rbac.CATEGORIA_PROGRAMA)
        tabs = [tab["label"] for tab in UserCreationForm().roles_por_ambito()]
        self.assertEqual(tabs[-1], "Sin programa")
        self.assertEqual(self._roles(UserCreationForm(), "Sin programa"), ["Rol huérfano"])

    def test_roles_ordenados_por_nombre_dentro_de_la_solapa(self):
        _rol("Aaa primero", rbac.CATEGORIA_SISTEMA)
        self.assertEqual(self._roles(UserCreationForm(), rbac.CATEGORIA_SISTEMA), ["Aaa primero", "Auditor"])

    def test_rol_expone_descripcion_para_la_ficha(self):
        rol = self._tabs(UserCreationForm())[rbac.CATEGORIA_BACKOFFICE]["roles"][0]
        self.assertEqual(rol["descripcion"], "Carga legajos")
        self.assertFalse(rol["checked"])

    def test_marca_los_roles_del_usuario_al_editar(self):
        user = User.objects.create_user("juana", password="x")
        user.groups.add(self.rol_cat_becas, self.rol_prog_disp)
        tabs = self._tabs(CustomUserChangeForm(instance=user))
        tildados = {rol["nombre"] for tab in tabs.values() for rol in tab["roles"] if rol["checked"]}
        self.assertEqual(tildados, {"Territorial", "Operador Dispositivos"})

    def test_conserva_lo_tildado_cuando_el_post_es_invalido(self):
        """Un POST que no valida no debe perder los roles que el operador tildó."""
        form = UserCreationForm(
            data={"username": "", "email": "", "password": "", "groups": [str(self.rol_prog_becas.pk)]}
        )
        self.assertFalse(form.is_valid())
        tildados = [r["nombre"] for r in self._tabs(form)[rbac.CATEGORIA_BECAS]["roles"] if r["checked"]]
        self.assertEqual(tildados, ["Becas — Coordinador"])

    def test_rol_inactivo_asignado_se_marca_como_inactivo(self):
        rol_viejo = _rol("Rol discontinuado", rbac.CATEGORIA_BACKOFFICE, activo=False)
        user = User.objects.create_user("pedro", password="x")
        user.groups.add(rol_viejo)
        roles = self._tabs(CustomUserChangeForm(instance=user))[rbac.CATEGORIA_BACKOFFICE]["roles"]
        self.assertEqual([r["nombre"] for r in roles if r["inactivo"]], ["Rol discontinuado"])

    def test_rol_territorial_de_becas_queda_marcado_para_el_campo_segmento(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_becas", stdout=StringIO())
        from programas.management.commands.seed_becas import ROL_TERRITORIAL

        territoriales = [
            rol["nombre"] for tab in UserCreationForm().roles_por_ambito() for rol in tab["roles"] if rol["territorial"]
        ]
        self.assertIn(ROL_TERRITORIAL, territoriales)


class UserFormTemplateTests(TestCase):
    """El template renderiza el panel con checkboxes ``groups`` (sin JS de por medio)."""

    def setUp(self):
        self.programa = _programa("BECAS", "Becas")
        self.rol = _rol("Territorial", rbac.CATEGORIA_BECAS, descripcion="Releva en campo")
        self.rol_programa = _rol("Becas — Coordinador", rbac.CATEGORIA_PROGRAMA, programa=self.programa)
        self.admin = User.objects.create_superuser("admin_tpl", "a@a.com", "x")

    def _render(self, form, obj=None):
        request = RequestFactory().get("/usuarios/editar/1/")
        request.user = self.admin
        return render_to_string("user/user_form.html", {"form": form, "object": obj}, request=request)

    def test_renderiza_una_solapa_por_ambito_con_sus_checkboxes(self):
        html = self._render(UserCreationForm())
        self.assertIn("Roles por ámbito", html)
        self.assertIn('data-tab="becas"', html)
        self.assertIn(f'name="groups" value="{self.rol.pk}"', html)
        self.assertIn(f'name="groups" value="{self.rol_programa.pk}"', html)
        self.assertIn("Releva en campo", html)

    def test_no_renderiza_solapa_programa_contenedora(self):
        html = self._render(UserCreationForm())
        self.assertNotIn('data-tab="programa"', html)

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
