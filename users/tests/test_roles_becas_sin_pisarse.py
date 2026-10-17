"""Cambio 333: un usuario puede tener varios roles, pero no dos que se pisen en Becas.

Decisión del PM (17/10/2026) sobre el diagnóstico del Cambio 332: Administrador,
Referente, Coordinador Regional y Coordinador de Becas fijan alcances que las funciones
de ``programas.services.autorizacion`` evalúan en órdenes distintos, así que a lo sumo
uno por usuario. Territorial, los roles de otros programas y los globales se combinan
libremente (default del juez, a confirmar).
"""

import json
import subprocess
import tempfile
from io import StringIO
from itertools import combinations
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core import rbac
from core.tests.js_harness import NODE, requiere_node
from programas.management.commands.seed_becas import (
    ROL_ADMIN,
    ROL_COORDINADOR,
    ROL_COORDINADOR_REGIONAL,
    ROL_REFERENTE,
    ROL_TERRITORIAL,
)
from programas.models import AsignacionTerritorial, Programa, Segmento
from programas.services.autorizacion import (
    ALCANCE_ADMINISTRADOR,
    ALCANCE_COORDINADOR,
    ALCANCE_COORDINADOR_REGIONAL,
    ALCANCE_REFERENTE,
    MENSAJE_ROLES_SE_PISAN,
    alcance_becas_de_rol,
    alcances_becas_de_roles,
    programa_becas,
    roles_becas_que_se_pisan,
)
from users.admin import UsuarioAdminChangeForm
from users.forms import CustomUserChangeForm, UserCreationForm
from users.models import Capacidad, RolMeta

CLAVE = "Clave-Segura-2026"
SCRIPT_SELECTOR = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "usuarios-roles-alcance.js"
RUNNER_SELECTOR = Path(__file__).parent / "js" / "roles_alcance.cjs"


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, caps, programa=None, activo=True):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA if programa else "Sistema",
        programa=programa,
        activo=activo,
    )
    for codigo in caps:
        grupo.permissions.add(_perm(codigo))
    return grupo


class Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.becas = Programa.objects.get(codigo="BECAS")
        self.disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        self.admin = Group.objects.get(name=ROL_ADMIN)
        self.coordinador = Group.objects.get(name=ROL_COORDINADOR)
        self.regional = Group.objects.get(name=ROL_COORDINADOR_REGIONAL)
        self.referente = Group.objects.get(name=ROL_REFERENTE)
        self.territorial = Group.objects.get(name=ROL_TERRITORIAL)
        self.root = User.objects.create_superuser("root", "root@x.test", CLAVE)
        self.segmento = Segmento.objects.create(nombre="Norte", cupo_maximo=10)

    def _datos(self, grupos, **extra):
        datos = {
            "username": "nuevo",
            "email": "nuevo@x.test",
            "first_name": "Nueva",
            "last_name": "Persona",
            "groups": [str(g.pk) for g in grupos],
        }
        datos.update(extra)
        return datos


class ClasificacionTests(Base):
    def test_clasifica_los_cinco_roles_sembrados(self):
        self.assertEqual(alcance_becas_de_rol(self.admin), ALCANCE_ADMINISTRADOR)
        self.assertEqual(alcance_becas_de_rol(self.coordinador), ALCANCE_COORDINADOR)
        self.assertEqual(alcance_becas_de_rol(self.regional), ALCANCE_COORDINADOR_REGIONAL)
        self.assertEqual(alcance_becas_de_rol(self.referente), ALCANCE_REFERENTE)
        self.assertIsNone(alcance_becas_de_rol(self.territorial))

    def test_el_administrador_sembrado_gana_aunque_tenga_referente_y_regional(self):
        """Por eso la prioridad: el Administrador también trae las otras dos marcas."""
        caps = set(rbac.capacidades_de_grupo(self.admin))
        self.assertIn("becas.referente", caps)
        self.assertIn("becas.coordinador_regional", caps)
        self.assertEqual(alcance_becas_de_rol(self.admin), ALCANCE_ADMINISTRADOR)

    def test_clasifica_por_capacidad_no_por_nombre(self):
        disfrazado = _rol("Becas — Coordinador (viejo)", ["becas.referente", "becas.segmento.ver"], self.becas)
        self.assertEqual(alcance_becas_de_rol(disfrazado), ALCANCE_REFERENTE)

    def test_roles_de_otro_programa_globales_o_inactivos_no_fijan_alcance(self):
        otro_programa = _rol("Disp con caps de Becas", ["becas.referente"], self.disp)
        global_ = _rol("Global con caps de Becas", ["becas.segmento.ver"])
        inactivo = _rol("Becas inactivo", ["becas.referente"], self.becas, activo=False)

        self.assertEqual(alcances_becas_de_roles([otro_programa, global_, inactivo]), {})

    def test_resuelve_todos_los_roles_con_una_sola_consulta(self):
        roles = [self.admin, self.coordinador, self.regional, self.referente, self.territorial]
        programa = programa_becas()
        with self.assertNumQueries(1):
            alcances = alcances_becas_de_roles(roles, programa=programa)
        self.assertEqual(len(alcances), 4)

    def test_dos_del_mismo_tipo_no_se_pisan(self):
        otro_coordinador = _rol("Becas — Coordinador B", ["becas.segmento.ver"], self.becas)
        self.assertEqual(roles_becas_que_se_pisan([self.coordinador, otro_coordinador]), [])


class AltaTests(Base):
    def _form(self, grupos, **extra):
        return UserCreationForm(data=self._datos(grupos, **extra), operador=self.root)

    def test_rechaza_cada_par_de_tipos_distintos(self):
        for primero, segundo in combinations([self.admin, self.coordinador, self.regional, self.referente], 2):
            with self.subTest(par=(primero.name, segundo.name)):
                form = self._form([primero, segundo])
                self.assertFalse(form.is_valid())
                errores = " ".join(form.errors.get("groups", []))
                self.assertIn("no se pueden combinar", errores)
                self.assertIn(primero.name, errores)
                self.assertIn(segundo.name, errores)

    def test_el_mensaje_nombra_los_dos_roles(self):
        form = self._form([self.referente, self.coordinador])

        self.assertFalse(form.is_valid())
        esperado = MENSAJE_ROLES_SE_PISAN.format(a=ROL_COORDINADOR, b=ROL_REFERENTE)
        self.assertEqual(form.errors["groups"], [esperado])

    def test_acepta_coordinador_mas_territorial(self):
        form = self._form([self.coordinador, self.territorial], segmento_territorial=str(self.segmento.pk))
        self.assertTrue(form.is_valid(), form.errors)

    def test_acepta_un_rol_de_becas_mas_uno_de_otro_programa(self):
        operativo_disp = _rol("Operativo Dispositivos", ["dispositivo.ver"], self.disp)
        form = self._form([self.coordinador, operativo_disp])
        self.assertTrue(form.is_valid(), form.errors)

    def test_acepta_dos_roles_del_mismo_tipo(self):
        otro_coordinador = _rol("Becas — Coordinador B", ["becas.segmento.ver"], self.becas)
        form = self._form([self.coordinador, otro_coordinador])
        self.assertTrue(form.is_valid(), form.errors)

    def test_por_http_no_crea_el_usuario(self):
        self.client.force_login(self.root)

        respuesta = self.client.post(reverse("users:usuario_crear"), self._datos([self.coordinador, self.regional]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("groups", respuesta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="nuevo").exists())


class EdicionTests(Base):
    def setUp(self):
        super().setUp()
        self.con_conflicto = User.objects.create_user("mixto", "mixto@x.test", CLAVE)
        self.con_conflicto.groups.add(self.coordinador, self.regional)

    def _post(self, grupos, **extra):
        datos = self._datos(grupos, username="mixto", email="mixto@x.test", password="")
        datos.update(extra)
        return self.client.post(reverse("users:usuario_editar", args=[self.con_conflicto.pk]), datos)

    def test_un_usuario_que_ya_tiene_el_conflicto_queda_bloqueado_al_editarlo(self):
        self.client.force_login(self.root)

        respuesta = self._post([self.coordinador, self.regional], telefono="3624000000")

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no se pueden combinar", " ".join(respuesta.context["form"].errors["groups"]))
        self.con_conflicto.refresh_from_db()
        self.assertEqual(self.con_conflicto.profile.telefono or "", "")

    def test_se_desbloquea_al_resolverlo(self):
        self.client.force_login(self.root)

        respuesta = self._post([self.coordinador])

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(list(self.con_conflicto.groups.all()), [self.coordinador])

    def test_el_form_de_edicion_tambien_lo_marca(self):
        form = CustomUserChangeForm(
            data=self._datos([self.coordinador, self.regional], username="mixto", email="mixto@x.test"),
            instance=self.con_conflicto,
            operador=self.root,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("groups", form.errors)


class OperadorNoGlobalTests(Base):
    """Un admin de usuarios de Becas no ve el rol Administrador (no es delegable), pero
    el guardado se lo conserva al usuario: sumarle un Coordinador desde acá también se
    pisa, y el error no nombra el rol que el operador no ve."""

    def setUp(self):
        super().setUp()
        rol_operador = _rol("Admin usuarios Becas", ["programa.usuario.administrar"], self.becas)
        self.operador = User.objects.create_user("operador-becas", "op@x.test", CLAVE)
        self.operador.groups.add(rol_operador)
        self.objetivo = User.objects.create_user("objetivo", "objetivo@x.test", CLAVE)
        self.objetivo.groups.add(self.admin)

    def test_el_operador_no_ve_el_rol_que_se_conserva(self):
        form = CustomUserChangeForm(instance=self.objetivo, operador=self.operador)
        visibles = set(form.fields["groups"].queryset)
        self.assertNotIn(self.admin, visibles)
        self.assertIn(self.coordinador, visibles)

    def test_no_puede_crear_el_conflicto_combinando_un_rol_visible_con_uno_oculto(self):
        self.client.force_login(self.operador)

        respuesta = self.client.post(
            reverse("users:usuario_editar", args=[self.objetivo.pk]),
            self._datos([self.coordinador], username="objetivo", email="objetivo@x.test", password=""),
        )

        self.assertEqual(respuesta.status_code, 200)
        errores = " ".join(respuesta.context["form"].errors["groups"])
        self.assertIn(f"El rol «{ROL_COORDINADOR}» no se puede combinar", errores)
        self.assertNotIn(ROL_ADMIN, errores)
        self.assertEqual(list(self.objetivo.groups.all()), [self.admin])

    def test_un_conflicto_entre_dos_roles_que_no_ve_no_le_traba_la_edicion(self):
        """No lo puede resolver: bloquearlo lo dejaría sin poder tocar ni el teléfono."""
        oculto = _rol(
            "Becas — Regional con configurar", ["becas.coordinador_regional", "programa.configurar"], self.becas
        )
        self.objetivo.groups.add(oculto, self.territorial)
        AsignacionTerritorial.objects.create(territorial=self.objetivo, segmento=self.segmento)
        form = CustomUserChangeForm(
            data=self._datos(
                [self.territorial],
                username="objetivo",
                email="objetivo@x.test",
                segmento_territorial=str(self.segmento.pk),
            ),
            instance=self.objetivo,
            operador=self.operador,
        )
        form.is_valid()
        self.assertNotIn("groups", form.errors)


class SelectorTests(Base):
    def test_cada_opcion_lleva_su_tipo_de_alcance_y_el_aviso_tiene_el_texto_del_servidor(self):
        self.client.force_login(self.root)

        respuesta = self.client.get(reverse("users:usuario_crear"))

        self.assertContains(respuesta, f'value="{self.coordinador.pk}"')
        contenido = respuesta.content.decode()
        for rol, tipo in (
            (self.admin, "administrador"),
            (self.coordinador, "coordinador"),
            (self.regional, "coordinador_regional"),
            (self.referente, "referente"),
        ):
            with self.subTest(rol=rol.name):
                self.assertRegex(contenido, rf'id="rol-{rol.pk}"[^>]*data-alcance-becas="{tipo}"')
        self.assertNotRegex(contenido, rf'id="rol-{self.territorial.pk}"[^>]*data-alcance-becas=')
        self.assertContains(respuesta, "data-mensaje-roles-se-pisan=")
        self.assertContains(respuesta, "custom/js/usuarios-roles-alcance.js")


@requiere_node
class AvisoDelSelectorTests(SimpleTestCase):
    """El JS del selector, en Node sobre un DOM mínimo: revierte y avisa con ModernModal."""

    ROLES = [
        {"id": "coord", "nombre": ROL_COORDINADOR, "alcance": "coordinador"},
        {"id": "coord-b", "nombre": "Becas — Coordinador B", "alcance": "coordinador"},
        {"id": "ref", "nombre": ROL_REFERENTE, "alcance": "referente"},
        {"id": "terr", "nombre": ROL_TERRITORIAL, "alcance": ""},
    ]

    def _correr(self, clics):
        escenario = {"plantilla": MENSAJE_ROLES_SE_PISAN, "roles": self.ROLES, "clics": clics}
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "escenario.json"
            ruta.write_text(json.dumps(escenario), encoding="utf-8")
            proceso = subprocess.run(
                [NODE, str(RUNNER_SELECTOR), str(SCRIPT_SELECTOR), str(ruta)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
        if proceso.returncode != 0:
            raise AssertionError(f"node falló:\n{proceso.stderr}")
        return json.loads(proceso.stdout)

    def test_revierte_el_rol_que_choca_y_avisa_con_el_texto_del_servidor(self):
        resultado = self._correr(["coord", "ref"])

        self.assertEqual(resultado["tildados"], ["coord"])
        self.assertEqual(len(resultado["modales"]), 1)
        self.assertEqual(resultado["modales"][0]["type"], "warning")
        self.assertEqual(
            resultado["modales"][0]["message"],
            MENSAJE_ROLES_SE_PISAN.format(a=ROL_COORDINADOR, b=ROL_REFERENTE),
        )
        # El selector de la pantalla ya ve el rol destildado: chips y contadores no lo cuentan.
        self.assertEqual(resultado["vistos"], ["coord:true", "ref:false"])

    def test_deja_sumar_territorial_y_otro_rol_del_mismo_tipo(self):
        resultado = self._correr(["coord", "terr", "coord-b"])

        self.assertEqual(resultado["tildados"], ["coord", "coord-b", "terr"])
        self.assertEqual(resultado["modales"], [])


class OtrosCaminosTests(Base):
    def test_el_alta_por_csv_no_replica_una_referencia_con_conflicto(self):
        referencia = User.objects.create_user("referencia", "ref@x.test", CLAVE)
        referencia.groups.add(self.referente, self.coordinador)
        with tempfile.TemporaryDirectory() as carpeta:
            csv_path = Path(carpeta) / "usuarios.csv"
            csv_path.write_text(
                "Usuario,Email,Nombre completo,Apellido,Contraseña\nnueva,n@x.test,Nueva,Persona,Clave-Segura-2026\n",
                encoding="utf-8",
            )
            with self.assertRaisesMessage(CommandError, "no se pueden combinar"):
                call_command(
                    "import_users_from_csv",
                    str(csv_path),
                    reference_user_id=referencia.pk,
                    aplicar=True,
                    stdout=StringIO(),
                )
        self.assertFalse(User.objects.filter(username="nueva").exists())

    def test_el_admin_de_django_tampoco_deja_combinarlos(self):
        usuario = User.objects.create_user("en-admin", "admin@x.test", CLAVE)
        datos = {"username": "en-admin", "date_joined": "2026-10-17 10:00:00", "groups": [self.admin.pk]}

        con_conflicto = UsuarioAdminChangeForm(
            data={**datos, "groups": [self.admin.pk, self.referente.pk]}, instance=usuario
        )
        self.assertFalse(con_conflicto.is_valid())
        self.assertIn("groups", con_conflicto.errors)

        sin_conflicto = UsuarioAdminChangeForm(data=datos, instance=usuario)
        self.assertTrue(sin_conflicto.is_valid(), sin_conflicto.errors)
