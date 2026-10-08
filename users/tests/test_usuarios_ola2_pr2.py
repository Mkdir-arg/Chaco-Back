"""ABM de usuarios y roles — Ola 2, PR 2 (G1b-05, G1b-07, G1b-08, R0b-01, R0b-02, R0b-10).

Las PoC de `docs/internal/auditoria-2026-10/poc/test_repro_usuarios.py` afirmaban el
comportamiento defectuoso; acá están **invertidas**, con el nombre que pide cada ficha.
Cada bloque trae además la batería de roles que exige la auditoría: anónimo, usuario sin
rol, usuario con la capacidad justa y superusuario.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from zeal import zeal_ignore

from core import rbac
from programas.models import Programa
from users.models import Capacidad, Profile, RolMeta
from users.selectors.usuarios import puede_gestionar_credenciales
from users.services.roles import RolesAdminService

CLAVE = "Clave-Segura-2026"


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, caps, programa=None, categoria=None, activo=True):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=categoria or (rbac.CATEGORIA_PROGRAMA if programa else "Sistema"),
        programa=programa,
        activo=activo,
    )
    for codigo in caps:
        grupo.permissions.add(_perm(codigo))
    return grupo


def _user(username, *grupos, password=CLAVE, **extra):
    usuario = User.objects.create_user(username, password=password, email=f"{username}@x.test", **extra)
    for grupo in grupos:
        usuario.groups.add(grupo)
    return usuario


def _post_user(client, target, grupos, **extra):
    datos = {
        "username": target.username,
        "email": target.email,
        "first_name": target.first_name,
        "last_name": target.last_name,
        "password": "",
        "groups": [str(g.pk) for g in grupos],
    }
    datos.update(extra)
    return client.post(reverse("users:usuario_editar", args=[target.pk]), datos)


class Base(TestCase):
    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.disp = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        self.rol_global = _rol("Admins", ["usuario.administrar", "rol.administrar"])
        self.root = _user("root-global", self.rol_global)


# --------------------------------------------------------------------------- #
# G1b-05 — una cuenta no queda activa y sin ningún rol
# --------------------------------------------------------------------------- #
class G1b05CuentaSinRolTests(Base):
    def setUp(self):
        super().setUp()
        self.rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        self.rol_op = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        self.operador = _user("operador", self.rol_op)
        self.adm = _user("adm-disp", self.rol_adm_disp)

    def test_admin_programa_no_puede_dejar_la_cuenta_sin_roles(self):
        """La PoC invertida: destildar el único rol dejaba la cuenta **viva** y, de
        paso, fuera del listado del admin que la dejó así."""
        self.client.force_login(self.adm)

        respuesta = _post_user(self.client, self.operador, [])

        self.assertEqual(respuesta.status_code, 200)  # vuelve al formulario con el error
        self.assertIn("groups", respuesta.context["form"].errors)
        self.operador.refresh_from_db()
        self.assertEqual(self.operador.groups.count(), 1)

    def test_el_camino_correcto_sigue_abierto_desactivar_la_cuenta(self):
        """Lo que el error propone: si hay que sacarle el acceso, se desactiva."""
        self.client.force_login(self.adm)

        respuesta = self.client.post(reverse("users:usuario_toggle", args=[self.operador.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.operador.refresh_from_db()
        self.assertFalse(self.operador.is_active)
        self.assertEqual(self.operador.groups.count(), 1)  # sigue visible en el listado

    def test_el_alta_de_un_admin_de_programa_exige_un_rol(self):
        self.client.force_login(self.adm)

        respuesta = self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": "nuevo-sin-rol",
                "email": "",
                "password": "Clave-Nueva-2026",
                "first_name": "",
                "last_name": "",
                "groups": [],
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("groups", respuesta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="nuevo-sin-rol").exists())

    def test_el_admin_global_sigue_pudiendo_dejarla_sin_roles(self):
        """A él la cuenta no se le esconde: su listado las muestra todas."""
        self.client.force_login(self.root)

        respuesta = _post_user(self.client, self.operador, [])

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.operador.groups.count(), 0)

    def test_un_admin_de_otro_programa_no_llega_a_la_pantalla(self):
        ajeno = _user("adm-becas", _rol("AdmUsuBecas", ["programa.usuario.administrar"], self.becas))
        self.client.force_login(ajeno)

        self.assertEqual(
            self.client.get(reverse("users:usuario_editar", args=[self.operador.pk])).status_code, 302
        )

    def test_sin_rol_y_anonimo_no_entran_al_abm(self):
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)  # anónimo
        self.client.force_login(_user("pelado"))
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)

    def test_el_superusuario_entra(self):
        self.client.force_login(_user("su", is_superuser=True, is_staff=True))
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 200)


# --------------------------------------------------------------------------- #
# G1b-07 — desactivar el último rol admin
# --------------------------------------------------------------------------- #
class G1b07ToggleRolSinAdminTests(Base):
    def test_desactivar_el_unico_rol_admin_de_un_programa_avisa_y_no_rompe(self):
        """Antes: `SinAdministradorProgramaError` sin capturar → 500."""
        rol = _rol("AdmBecas", ["programa.usuario.administrar", "programa.rol.administrar"], self.becas)
        _user("unico-adm-becas", rol)
        self.client.force_login(self.root)

        with zeal_ignore():
            respuesta = self.client.post(reverse("users:rol_toggle", args=[rol.pk]), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        rol.meta.refresh_from_db()
        self.assertTrue(rol.meta.activo)
        self.assertIn("sin ningún administrador", " ".join(m.message for m in respuesta.context["messages"]))

    def test_desactivar_el_unico_rol_admin_global_no_deja_el_sistema_sin_nadie(self):
        self.client.force_login(self.root)

        with zeal_ignore():
            respuesta = self.client.post(reverse("users:rol_toggle", args=[self.rol_global.pk]), follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.rol_global.meta.refresh_from_db()
        self.assertTrue(self.rol_global.meta.activo)
        self.assertTrue(rbac.usuarios_que_administran().exists())

    def test_con_otro_admin_global_la_desactivacion_sigue_andando(self):
        otro = _rol("Admins 2", ["usuario.administrar", "rol.administrar"])
        _user("segundo-admin", otro)
        self.client.force_login(self.root)

        with zeal_ignore():
            respuesta = self.client.post(reverse("users:rol_toggle", args=[self.rol_global.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.rol_global.meta.refresh_from_db()
        self.assertFalse(self.rol_global.meta.activo)

    def test_un_rol_operativo_se_desactiva_sin_consultar_administradores(self):
        """El check global solo corre para los roles que otorgan administración."""
        rol = _rol("Operativo", ["ciudadano.ver"])

        self.assertFalse(RolesAdminService.toggle_activo(rol))

    def test_sin_capacidad_y_anonimo_no_togglean(self):
        rol = _rol("Operativo", ["ciudadano.ver"])
        self.assertEqual(self.client.post(reverse("users:rol_toggle", args=[rol.pk])).status_code, 302)
        rol.meta.refresh_from_db()
        self.assertTrue(rol.meta.activo)

        self.client.force_login(_user("pelado"))
        self.assertEqual(self.client.post(reverse("users:rol_toggle", args=[rol.pk])).status_code, 302)
        rol.meta.refresh_from_db()
        self.assertTrue(rol.meta.activo)


# --------------------------------------------------------------------------- #
# G1b-08 — la clave que tipea un operador
# --------------------------------------------------------------------------- #
class G1b08ClaveTipeadaTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.root)

    def test_el_alta_rechaza_una_clave_que_no_pasa_los_validadores(self):
        respuesta = self.client.post(
            reverse("users:usuario_crear"),
            {
                "username": "debil",
                "email": "",
                "password": "12345678",
                "first_name": "",
                "last_name": "",
                "groups": [str(self.rol_global.pk)],
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password", respuesta.context["form"].errors)
        self.assertFalse(User.objects.filter(username="debil").exists())

    def test_la_edicion_rechaza_una_clave_que_no_pasa_los_validadores(self):
        victima = _user("victima", self.rol_global)

        respuesta = _post_user(self.client, victima, [self.rol_global], password="12345678")

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("password", respuesta.context["form"].errors)
        victima.refresh_from_db()
        self.assertFalse(victima.check_password("12345678"))

    def test_fijarle_la_clave_a_otro_obliga_a_cambiarla(self):
        victima = _user("victima", self.rol_global)
        self.assertFalse(Profile.objects.get(user=victima).debe_cambiar_contrasena)

        respuesta = _post_user(self.client, victima, [self.rol_global], password="Clave-Puesta-Por-Otro-26")

        self.assertEqual(respuesta.status_code, 302)
        victima.refresh_from_db()
        self.assertTrue(victima.check_password("Clave-Puesta-Por-Otro-26"))
        self.assertTrue(Profile.objects.get(user=victima).debe_cambiar_contrasena)

    def test_cambiarse_la_propia_clave_desde_el_abm_no_obliga_a_nada(self):
        respuesta = _post_user(self.client, self.root, [self.rol_global], password="Mi-Clave-Nueva-2026")

        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Profile.objects.get(user=self.root).debe_cambiar_contrasena)

    def test_una_edicion_sin_clave_no_toca_el_flag(self):
        victima = _user("victima", self.rol_global)

        _post_user(self.client, victima, [self.rol_global], first_name="Otro")

        victima.refresh_from_db()
        self.assertTrue(victima.check_password(CLAVE))
        self.assertFalse(Profile.objects.get(user=victima).debe_cambiar_contrasena)


# --------------------------------------------------------------------------- #
# R0b-01 — el aviso de SEC-03 llega a la pantalla
# --------------------------------------------------------------------------- #
class R0b01AvisoDeCredencialesTests(Base):
    def test_el_formulario_muestra_por_que_el_usuario_y_el_correo_estan_grises(self):
        rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        rol_op_disp = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        rol_op_becas = _rol("OpBecas", ["relevamiento.ver"], self.becas)
        multiprograma = _user("multi", rol_op_disp, rol_op_becas)
        self.client.force_login(_user("adm-disp", rol_adm_disp))

        respuesta = self.client.get(reverse("users:usuario_editar", args=[multiprograma.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["form"].credenciales_editables)
        self.assertContains(respuesta, "Solo lo puede cambiar quien administre todos los roles")

    def test_con_todos_los_roles_en_alcance_no_hay_aviso(self):
        rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        rol_op_disp = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        propio = _user("propio", rol_op_disp)
        self.client.force_login(_user("adm-disp", rol_adm_disp))

        respuesta = self.client.get(reverse("users:usuario_editar", args=[propio.pk]))

        self.assertTrue(respuesta.context["form"].credenciales_editables)
        self.assertNotContains(respuesta, "Solo lo puede cambiar quien administre todos los roles")


# --------------------------------------------------------------------------- #
# R0b-02 — un rol desactivado de otro programa también saca de alcance
# --------------------------------------------------------------------------- #
class R0b02RolDesactivadoFueraDeAlcanceTests(Base):
    def setUp(self):
        super().setUp()
        self.rol_adm_becas = _rol("AdmUsuBecas", ["programa.usuario.administrar"], self.becas)
        self.rol_op_becas = _rol("OpBecas", ["relevamiento.ver"], self.becas)
        self.adm_becas = _user("adm-becas", self.rol_adm_becas)

    def test_un_rol_inactivo_de_otro_programa_frena_las_credenciales(self):
        """Si alguien reactiva ese rol, el usuario recupera el acceso a Dispositivos
        con una clave que puso el admin de Becas."""
        dormido = _rol("AdmUsuDispDormido", ["programa.usuario.administrar"], self.disp, activo=False)
        target = _user("multi", self.rol_op_becas, dormido)

        self.assertFalse(puede_gestionar_credenciales(self.adm_becas, target))

        self.client.force_login(self.adm_becas)
        respuesta = _post_user(self.client, target, [self.rol_op_becas], password="Pwn3d-Clave-2026")
        self.assertEqual(respuesta.status_code, 302)
        target.refresh_from_db()
        self.assertFalse(target.check_password("Pwn3d-Clave-2026"))

    def test_un_rol_inactivo_del_propio_programa_no_frena_nada(self):
        """La contracara: el rol dormido es de Becas, que es lo que este admin
        administra. Sacar el `exclude` a secas lo dejaba sin poder tocar a los
        suyos."""
        dormido = _rol("OpBecasDormido", ["relevamiento.ver"], self.becas, activo=False)
        target = _user("propio", self.rol_op_becas, dormido)

        self.assertTrue(puede_gestionar_credenciales(self.adm_becas, target))

    def test_el_admin_global_no_tiene_restriccion(self):
        dormido = _rol("AdmUsuDispDormido", ["programa.usuario.administrar"], self.disp, activo=False)
        target = _user("multi", self.rol_op_becas, dormido)

        self.assertTrue(puede_gestionar_credenciales(self.root, target))


# --------------------------------------------------------------------------- #
# R0b-10 — el listado no ofrece botones que el servidor rechaza
# --------------------------------------------------------------------------- #
class R0b10BotonesDelListadoTests(Base):
    def setUp(self):
        super().setUp()
        self.rol_adm_disp = _rol("AdmUsuDisp", ["programa.usuario.administrar"], self.disp)
        self.rol_op_disp = _rol("OpDisp", ["dispositivo.ver"], self.disp)
        self.rol_op_becas = _rol("OpBecas", ["relevamiento.ver"], self.becas)
        self.adm = _user("adm-disp", self.rol_adm_disp)

    def test_el_listado_no_ofrece_editar_ni_togglear_a_un_superusuario(self):
        superusuario = _user("su", self.rol_op_disp, is_superuser=True)
        self.client.force_login(self.adm)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, reverse("users:usuario_editar", args=[superusuario.pk]))
        self.assertNotContains(respuesta, reverse("users:usuario_toggle", args=[superusuario.pk]))

    def test_el_listado_no_ofrece_togglear_a_un_multiprograma(self):
        """Editarlo sí (los roles de Dispositivos son suyos); activarlo o
        desactivarlo no, porque es la cuenta entera (SEC-03)."""
        multi = _user("multi", self.rol_op_disp, self.rol_op_becas)
        self.client.force_login(self.adm)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertContains(respuesta, reverse("users:usuario_editar", args=[multi.pk]))
        self.assertNotContains(respuesta, reverse("users:usuario_toggle", args=[multi.pk]))

    def test_sobre_un_usuario_propio_siguen_estando_los_dos_botones(self):
        propio = _user("propio", self.rol_op_disp)
        self.client.force_login(self.adm)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertContains(respuesta, reverse("users:usuario_editar", args=[propio.pk]))
        self.assertContains(respuesta, reverse("users:usuario_toggle", args=[propio.pk]))

    def test_el_admin_global_sigue_viendo_todos_los_botones(self):
        superusuario = _user("su", self.rol_op_disp, is_superuser=True)
        self.client.force_login(self.root)

        respuesta = self.client.get(reverse("users:usuarios"))

        self.assertContains(respuesta, reverse("users:usuario_editar", args=[superusuario.pk]))
        self.assertContains(respuesta, reverse("users:usuario_toggle", args=[superusuario.pk]))

    def test_la_anotacion_no_consulta_una_vez_por_fila(self):
        """«En lote, sin N+1» (R0b-10). El techo se mide sobre un listado de 12
        usuarios: si alguien vuelve a llamar a `puede_gestionar_usuario` por fila,
        el número se dispara."""
        for i in range(12):
            _user(f"op-{i}", self.rol_op_disp)
        self.client.force_login(self.adm)

        with self.assertNumQueries(15):
            self.client.get(reverse("users:usuarios"))
