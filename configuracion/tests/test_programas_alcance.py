"""SEC-07 / D-07 — ``programa.configurar`` se evalúa con el alcance que corresponde.

PoC invertida (`poc/test_repro_seguridad.py::SEC07ProgramaConfigurarTests`): el admin de
roles de Becas se tildaba ``programa.configurar`` en un rol **de Becas** y el wizard de
**Dispositivos** le contestaba 200. Las nueve vistas la pedían con ``@requiere``, que
evalúa sin alcance.

**D-07 = Sí** (default del README §2.2, aplicado): el admin de un programa edita el
wizard **solo de su programa**; crear programas queda para los roles sin programa.

Contrato de respuesta del backoffice sin capacidad: **redirect** al listado, no 403 (es
lo que ya fijó RED-73 y lo que usan los tests del wizard).
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from configuracion.tests.test_configuracion_ola5 import usuario_con
from core import rbac
from core.models import Secretaria, Subsecretaria
from programas.models import Programa
from users.models import Capacidad, RolMeta

PASOS_EDICION = (
    "configuracion:programa_editar_paso1",
    "configuracion:programa_editar_paso2",
    "configuracion:programa_editar_paso3",
    "configuracion:programa_editar_paso4",
)
PASOS_ALTA = (
    "configuracion:programa_wizard_paso1",
    "configuracion:programa_wizard_paso2",
    "configuracion:programa_wizard_paso3",
    "configuracion:programa_wizard_paso4",
)


def _usuario_de_programa(username, programa, *codigos):
    """Usuario con un rol de categoría Programa acotado a ``programa``."""
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    grupo = Group.objects.create(name=f"Rol {username}")
    RolMeta.objects.create(
        grupo=grupo,
        categoria=rbac.CATEGORIA_PROGRAMA,
        programa=programa,
        activo=True,
    )
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.secretaria = Secretaria.objects.create(nombre="Secretaría")
        cls.subsecretaria = Subsecretaria.objects.create(nombre="Subsecretaría", secretaria=cls.secretaria)
        cls.becas = Programa.objects.create(codigo="BECAS", nombre="Becas", subsecretaria=cls.subsecretaria)
        cls.dispositivos = Programa.objects.create(
            codigo="DISPOSITIVOS", nombre="Dispositivos", subsecretaria=cls.subsecretaria
        )


class SEC07AlcanceDelWizardTests(Base):
    def test_configurar_de_rol_becas_no_edita_dispositivos(self):
        """La PoC invertida: antes esto devolvía 200 en los cuatro pasos."""
        operador = _usuario_de_programa("adm-becas-cfg", self.becas, "programa.configurar")
        self.client.force_login(operador)

        for nombre in PASOS_EDICION:
            with self.subTest(paso=nombre):
                respuesta = self.client.get(reverse(nombre, args=[self.dispositivos.pk]))
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], reverse("configuracion:programas"))

    def test_configurar_de_rol_becas_si_edita_becas(self):
        """D-07: lo que sí puede es el suyo. Si no, el fix dejaría el wizard inservible
        para todo rol de programa."""
        operador = _usuario_de_programa("adm-becas-cfg-propio", self.becas, "programa.configurar")
        self.client.force_login(operador)

        respuesta = self.client.get(reverse("configuracion:programa_editar_paso1", args=[self.becas.pk]))

        self.assertEqual(respuesta.status_code, 200)

    def test_configurar_global_edita_cualquiera(self):
        """Un rol **sin programa** (Backoffice/Sistema) conserva el alcance de siempre."""
        operador = usuario_con("programa.configurar", username="cfg-global")
        self.client.force_login(operador)

        for programa in (self.becas, self.dispositivos):
            with self.subTest(programa=programa.codigo):
                respuesta = self.client.get(reverse("configuracion:programa_editar_paso1", args=[programa.pk]))
                self.assertEqual(respuesta.status_code, 200)

    def test_cambiar_el_estado_de_otro_programa_tampoco(self):
        """``programa_cambiar_estado`` es la décima vista: activa y suspende un programa."""
        operador = _usuario_de_programa("adm-becas-estado", self.becas, "programa.configurar")
        self.client.force_login(operador)
        estado_previo = self.dispositivos.estado

        respuesta = self.client.post(
            reverse("configuracion:programa_cambiar_estado", args=[self.dispositivos.pk]),
            {"estado": Programa.Estado.INACTIVO},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.dispositivos.refresh_from_db()
        self.assertEqual(self.dispositivos.estado, estado_previo)


class D07CrearProgramaTests(Base):
    """D-07: crear un programa no tiene alcance posible, así que es de un rol global."""

    def test_un_rol_de_programa_no_entra_al_alta(self):
        operador = _usuario_de_programa("adm-becas-alta", self.becas, "programa.configurar")
        self.client.force_login(operador)

        for nombre in PASOS_ALTA:
            with self.subTest(paso=nombre):
                respuesta = self.client.get(reverse(nombre))
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], reverse("configuracion:programas"))

    def test_un_rol_global_sigue_entrando_al_alta(self):
        operador = usuario_con("programa.configurar", username="cfg-global-alta")
        self.client.force_login(operador)

        self.assertEqual(self.client.get(reverse("configuracion:programa_wizard_paso1")).status_code, 200)

    def test_el_listado_no_le_ofrece_crear(self):
        operador = _usuario_de_programa("adm-becas-listado", self.becas, "programa.configurar")
        self.client.force_login(operador)

        respuesta = self.client.get(reverse("configuracion:programas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_crear"])
        self.assertNotContains(respuesta, "Nuevo programa")


class SEC07ListadoPorFilaTests(Base):
    """El lápiz se dibuja fila por fila: el listado es global (SEC-36), la edición no."""

    def test_el_admin_de_un_programa_solo_ve_editable_el_suyo(self):
        operador = _usuario_de_programa("adm-becas-fila", self.becas, "programa.configurar")
        self.client.force_login(operador)

        respuesta = self.client.get(reverse("configuracion:programas"))

        editables = {p.codigo: p.puede_editar for p in respuesta.context["programas"]}
        self.assertEqual(editables, {"BECAS": True, "DISPOSITIVOS": False})
        self.assertTrue(respuesta.context["puede_editar_alguno"])
        self.assertContains(respuesta, reverse("configuracion:programa_editar_paso1", args=[self.becas.pk]))
        self.assertNotContains(respuesta, reverse("configuracion:programa_editar_paso1", args=[self.dispositivos.pk]))

    def test_quien_solo_ve_el_catalogo_no_tiene_columna_de_acciones(self):
        """SEC-36 dejó entrar al listado con ``config.ver``: ahí no hay nada que editar."""
        operador = usuario_con("config.ver", username="cfg-solo-ver")
        self.client.force_login(operador)

        respuesta = self.client.get(reverse("configuracion:programas"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.context["puede_editar_alguno"])
        self.assertFalse(respuesta.context["puede_crear"])


class SEC07PorRolTests(Base):
    """La batería completa sobre la misma URL: anónimo, sin rol, rol de otro programa,
    admin del propio programa y superusuario."""

    def setUp(self):
        self.url = reverse("configuracion:programa_editar_paso1", args=[self.dispositivos.pk])

    def test_anonimo_va_al_login(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("users:login"), respuesta["Location"])

    def test_una_cuenta_sin_rol_no_entra(self):
        self.client.force_login(usuario_con(username="cfg-sin-rol-wizard"))

        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_un_rol_de_otro_programa_no_entra(self):
        self.client.force_login(_usuario_de_programa("adm-becas-rol", self.becas, "programa.configurar"))

        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_el_admin_del_propio_programa_entra(self):
        self.client.force_login(_usuario_de_programa("adm-disp-propio", self.dispositivos, "programa.configurar"))

        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_el_superusuario_entra(self):
        self.client.force_login(User.objects.create_superuser("root-wizard", "root@x.test", "x"))

        self.assertEqual(self.client.get(self.url).status_code, 200)


class PuedeSinProgramaTests(Base):
    """La primitiva nueva de ``core.rbac``, aparte de las vistas que la usan."""

    def test_una_capacidad_de_un_rol_de_programa_no_cuenta(self):
        operador = _usuario_de_programa("adm-becas-prim", self.becas, "programa.configurar")

        self.assertTrue(rbac.puede(operador, "programa.configurar"))  # sin alcance, sí
        self.assertTrue(rbac.puede(operador, "programa.configurar", programa=self.becas))
        self.assertFalse(rbac.puede(operador, "programa.configurar", programa=self.dispositivos))
        self.assertFalse(rbac.puede_sin_programa(operador, "programa.configurar"))

    def test_una_capacidad_de_un_rol_sin_programa_si_cuenta(self):
        operador = usuario_con("programa.configurar", username="cfg-prim-global")

        self.assertTrue(rbac.puede_sin_programa(operador, "programa.configurar"))

    def test_el_superusuario_activo_pasa_y_el_inactivo_no(self):
        root = User.objects.create_superuser("root-prim", "root-prim@x.test", "x")

        self.assertTrue(rbac.puede_sin_programa(root, "programa.configurar"))

        root.is_active = False

        self.assertFalse(rbac.puede_sin_programa(root, "programa.configurar"))

    def test_un_rol_desactivado_no_cuenta(self):
        operador = usuario_con("programa.configurar", username="cfg-prim-dormido")
        RolMeta.objects.filter(grupo__user=operador).update(activo=False)

        self.assertFalse(rbac.puede_sin_programa(operador, "programa.configurar"))

    def test_el_anonimo_no_pasa(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(rbac.puede_sin_programa(AnonymousUser(), "programa.configurar"))
        self.assertFalse(rbac.puede_sin_programa(None, "programa.configurar"))
