r"""Reproducciones del ABM de usuarios y roles (verificación G2, pasada 3).

Auditoría integral DATAÑACH, oct-2026 (ver el README.md de la carpeta de la auditoría).

CÓMO LEERLO (importante para TDD)
  Cada test AFIRMA EL COMPORTAMIENTO DEFECTUOSO ACTUAL: hoy PASA (verde = el bug existe en
  origin/development @ 917e583). Después del fix, el test correspondiente tiene que FALLAR.
  Para el ciclo TDD del ítem: copiá el test, INVERTÍ la aserción (o escribí el test de la
  sección «Tests a agregar» de la ficha), confirmá que el test invertido FALLA antes del fix
  y PASA después. Este archivo NO se commitea tal cual: se commitea el test invertido, con
  el nombre que pide la ficha.

CÓMO CORRERLO (PowerShell, raíz del repo, en el worktree de la ola)
  $env:PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"   # el venv vive en el checkout principal
  $env:DJANGO_SECRET_KEY = "test-key"; $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
  Copy-Item <este archivo> users/tests/test_repro_usuarios.py
  & $env:PY manage.py test users.tests.test_repro_usuarios -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  G1b01ToggleCrossProgramTests                   -> SEC-03 (ampliación G1b-01: toggle y credenciales de multiprograma)
  G1b02EscaladaDentroDelProgramaTests            -> G1b-02
  G1b03y04TokenCampoTests                        -> SEC-26 (clave provisoria del territorial; token que sobrevive al cambio de clave)
  G1b05CuentaFantasmaTests                       -> G1b-05
  G1b06CapsGlobalesBorradasTests                 -> G1b-06
  G2OperadorBackofficeSeedTests                  -> OPS-06 (origen G2-02, absorbido: seed_rbac reactiva «Operador de backoffice»)
  G1b07ToggleRolSinAdminTests                    -> G1b-07
  G2CambioClaveSinClaveActualTests               -> G2-03
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from zeal import zeal_ignore

from core import rbac
from programas.models import Programa
from users.forms.auth import UsuariosAuthenticationForm
from users.models import Capacidad, Profile, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, caps, programa=None, categoria=None):
    g = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=g,
        categoria=categoria or (rbac.CATEGORIA_PROGRAMA if programa else "Sistema"),
        programa=programa,
        activo=True,
    )
    for c in caps:
        g.permissions.add(_perm(c))
    return g


def _user(username, *grupos, password="Clave-Segura-2026"):
    u = User.objects.create_user(username, password=password, email=f"{username}@x.test")
    for g in grupos:
        u.groups.add(g)
    return u


def _post_user(client, target, groups, **extra):
    data = {
        "username": target.username,
        "email": target.email,
        "first_name": target.first_name,
        "last_name": target.last_name,
        "password": "",
        "groups": [str(g.pk) for g in groups],
    }
    data.update(extra)
    return client.post(reverse("users:usuario_editar", args=[target.pk]), data)


class Base(TestCase):
    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        # Admin global de respaldo (para que asegurar_admin_restante no frene nada).
        self.global_rol = _rol("Admins", ["usuario.administrar", "rol.administrar"])
        self.root = _user("root-global", self.global_rol)


class G1b01ToggleCrossProgramTests(Base):
    """Admin de usuarios de Dispositivos desactiva al admin de Becas (que tiene un rol operativo de Dispositivos)."""

    def test_admin_dispositivos_desactiva_admin_becas(self):
        rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        rol_op_disp = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        rol_adm_becas = _rol("AdmBecas", ["programa.usuario.administrar", "programa.rol.administrar"], self.becas)
        _user("otro-adm-becas", rol_adm_becas)  # hay otro admin de Becas: el guard de RN-8 no frena
        victima = _user("adm-becas", rol_adm_becas, rol_op_disp)
        atacante = _user("adm-disp", rol_adm_disp)
        self.client.force_login(atacante)
        resp = self.client.post(reverse("users:usuario_toggle", args=[victima.pk]))
        self.assertEqual(resp.status_code, 302)
        victima.refresh_from_db()
        self.assertFalse(victima.is_active)  # cuenta de Becas apagada por el admin de Dispositivos

    def test_admin_dispositivos_cambia_clave_de_admin_becas(self):
        rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        rol_op_disp = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        rol_adm_becas = _rol("AdmBecas", ["programa.usuario.administrar", "programa.rol.administrar"], self.becas)
        victima = _user("adm-becas", rol_adm_becas, rol_op_disp)
        atacante = _user("adm-disp", rol_adm_disp)
        self.client.force_login(atacante)
        resp = _post_user(self.client, victima, [rol_op_disp], password="Pwn3d-Clave-2026", email="evil@x.test")
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["form"].errors)
        victima.refresh_from_db()
        self.assertTrue(victima.check_password("Pwn3d-Clave-2026"))
        self.assertEqual(victima.email, "evil@x.test")
        self.assertTrue(victima.groups.filter(pk=rol_adm_becas.pk).exists())  # conserva su rol de Becas


class G1b02EscaladaDentroDelProgramaTests(Base):
    def test_admin_roles_se_da_admin_usuarios_editando_su_rol(self):
        rol_ra = _rol("RA Becas", ["programa.rol.administrar"], self.becas)
        a = _user("solo-roles", rol_ra)
        self.client.force_login(a)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)  # no entra a Usuarios
        with zeal_ignore():
            resp = self.client.post(
                reverse("users:rol_editar", args=[rol_ra.pk]),
                {
                    "name": "RA Becas",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "capacidades": ["programa.rol.administrar", "programa.usuario.administrar", "programa.configurar"],
                },
            )
        self.assertEqual(resp.status_code, 302)
        a = User.objects.get(pk=a.pk)
        self.assertTrue(rbac.puede(a, "programa.usuario.administrar"))
        self.assertTrue(rbac.puede(a, "programa.configurar"))
        self.client.force_login(a)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 200)

    def test_admin_usuarios_se_asigna_rol_con_admin_roles(self):
        rol_ua = _rol("UA Becas", ["programa.usuario.administrar"], self.becas)
        rol_full = _rol("Admin completo Becas", ["programa.rol.administrar", "becas.programa.administrar"], self.becas)
        b = _user("solo-usuarios", rol_ua)
        self.client.force_login(b)
        self.assertEqual(self.client.get(reverse("users:roles")).status_code, 302)
        resp = _post_user(self.client, b, [rol_ua, rol_full])
        self.assertEqual(resp.status_code, 302)
        b = User.objects.get(pk=b.pk)
        self.assertTrue(rbac.puede(b, "programa.rol.administrar"))
        self.assertTrue(rbac.puede(b, "becas.programa.administrar"))


class G1b03y04TokenCampoTests(Base):
    def setUp(self):
        super().setUp()
        self.rol_terr = _rol("Terr", ["becas.campo"], self.becas)
        self.terr = _user("terri", self.rol_terr, password="Provisoria-123")
        Profile.objects.filter(user=self.terr).update(debe_cambiar_contrasena=True)
        self.api = APIClient()

    def test_provisoria_nunca_se_cambia_pero_da_token(self):
        form = UsuariosAuthenticationForm(data={"username": "terri", "password": "Provisoria-123"})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.non_field_errors().as_data()[0].code, "territorial_mobile_only")
        resp = self.api.post(reverse("becas_api:token"), {"username": "terri", "password": "Provisoria-123"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Profile.objects.get(user=self.terr).debe_cambiar_contrasena)

    def test_token_sobrevive_cambio_de_clave(self):
        resp = self.api.post(reverse("becas_api:token"), {"username": "terri", "password": "Provisoria-123"})
        key = resp.data["token"]
        self.terr.set_password("Nueva-Clave-2026")
        self.terr.save()
        self.api.credentials(HTTP_AUTHORIZATION=f"Token {key}")
        self.assertEqual(self.api.get("/api/becas/relevamientos/").status_code, 200)


class G1b05CuentaFantasmaTests(Base):
    def test_admin_programa_quita_todos_los_roles_y_la_cuenta_sigue_viva(self):
        rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        rol_op = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        u = _user("operador", rol_op, password="Clave-Segura-2026")
        adm = _user("adm-disp", rol_adm_disp)
        self.client.force_login(adm)
        resp = _post_user(self.client, u, [])
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.is_active)
        self.assertEqual(u.groups.count(), 0)
        # Ya no aparece en el listado del admin que lo dejó así.
        lista = self.client.get(reverse("users:usuarios"))
        self.assertNotIn(u, list(lista.context["users"]))
        # Y puede entrar al backoffice.
        form = UsuariosAuthenticationForm(data={"username": "operador", "password": "Clave-Segura-2026"})
        self.assertTrue(form.is_valid())
        c = self.client_class()
        c.force_login(u)
        self.assertEqual(c.get(reverse("core:inicio")).status_code, 200)


class G1b06CapsGlobalesBorradasTests(Base):
    def test_admin_roles_programa_borra_caps_globales_al_guardar(self):
        rol = _rol("Operador Becas", ["relevamiento.ver"], self.becas)
        rol.permissions.add(_perm("ciudadano.ver"))  # agregada por el admin global
        rol_ra = _rol("RA Becas", ["programa.rol.administrar"], self.becas)
        a = _user("adm-roles-becas", rol_ra)
        self.client.force_login(a)
        # GET muestra solo caps de programa; el POST reenvía lo que ve.
        with zeal_ignore():
            resp = self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operador Becas",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "descripcion": "cambio de texto",
                    "capacidades": [
                        "relevamiento.ver"
                    ],  # lo que el navegador reenvía: el árbol no muestra ciudadano.ver
                },
            )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("ciudadano.ver", rbac.capacidades_de_grupo(rol))


class G2OperadorBackofficeSeedTests(TestCase):
    def test_seed_rbac_reactiva_operador_de_backoffice(self):
        call_command("seed_rbac", verbosity=0)
        g = Group.objects.get(name="Operador de backoffice")
        g.meta.activo = False
        g.meta.save()
        g.permissions.clear()
        call_command("seed_rbac", verbosity=0)
        g.meta.refresh_from_db()
        self.assertTrue(g.meta.activo)
        caps = rbac.capacidades_de_grupo(g)
        self.assertIn("usuario.administrar", caps)
        self.assertIn("rol.administrar", caps)


class G1b07ToggleRolSinAdminTests(Base):
    def test_desactivar_unico_rol_admin_de_programa_da_500(self):
        rol_adm_becas = _rol("AdmBecas", ["programa.usuario.administrar", "programa.rol.administrar"], self.becas)
        _user("unico-adm-becas", rol_adm_becas)
        self.client.force_login(self.root)  # admin global (no superusuario)
        self.client.raise_request_exception = False
        with zeal_ignore():
            resp = self.client.post(reverse("users:rol_toggle", args=[rol_adm_becas.pk]))
        self.assertEqual(resp.status_code, 500)
        rol_adm_becas.meta.refresh_from_db()
        self.assertTrue(rol_adm_becas.meta.activo)  # la transacción revirtió, pero el usuario ve un 500

    def test_desactivar_rol_global_no_protegido_deja_sistema_sin_admin(self):
        # El único admin global obtiene la capacidad de un rol NO protegido ("Admins").
        self.client.force_login(self.root)
        with zeal_ignore():
            resp = self.client.post(reverse("users:rol_toggle", args=[self.global_rol.pk]))
        self.assertEqual(resp.status_code, 302)
        self.global_rol.meta.refresh_from_db()
        self.assertFalse(self.global_rol.meta.activo)
        self.assertFalse(rbac.usuarios_que_administran().exists())


class G2CambioClaveSinClaveActualTests(Base):
    def test_cualquier_sesion_cambia_la_clave_sin_conocer_la_actual(self):
        u = _user("victima", _rol("OpX", ["ciudadano.ver"]), password="Original-2026")
        self.assertFalse(Profile.objects.get(user=u).debe_cambiar_contrasena)
        self.client.force_login(u)
        resp = self.client.post(
            reverse("users:cambiar_contrasena_obligatorio"),
            {"new_password1": "Tomada-Por-Xss-99", "new_password2": "Tomada-Por-Xss-99"},
        )
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.check_password("Tomada-Por-Xss-99"))
