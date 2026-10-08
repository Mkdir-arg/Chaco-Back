"""Derivaciones a programa: capacidad y método (SEC-12, auditoría oct-2026).

Antes de este cambio las dos rutas de la bandeja —`aceptar` y `rechazar`— eran
`@login_required` a secas y aceptaban **GET**: un `<img src="/legajos/
derivaciones-ciudadano/3/aceptar/">` en cualquier página aceptaba la derivación
con la sesión de quien la mirara, sin capacidad y sin CSRF, y el aceptar crea
además una `InscripcionPrograma`. La pantalla de derivación/inscripción directa
decidía por `request.user.is_staff`, que no es una capacidad del RBAC.

DECISIÓN CLIENTE D-12 = reusar `ciudadano.editar`, sin capacidad nueva.
"""

from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.models import DerivacionPrograma, InscripcionPrograma, Programa
from users.models import Capacidad, RolMeta

CLAVE = "Clave-Seg-2026x"


def usuario_con(*codigos, username=None, is_staff=False):
    """Usuario de backoffice con exactamente esas capacidades."""
    usuario = User.objects.create_user(
        username or f"d-{'-'.join(codigos) or 'sin-rol'}",
        password=CLAVE,
        is_staff=is_staff,
    )
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol derivaciones " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class DerivacionesRbacTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.programa = Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos")
        cls.ciudadano = Ciudadano.objects.create(dni="20999111", nombre="Delia", apellido="Escobar")

    def setUp(self):
        self.derivacion = DerivacionPrograma.objects.create(
            ciudadano=self.ciudadano,
            programa_destino=self.programa,
            motivo="m",
        )
        self.url_aceptar = reverse("legajos:derivacion_ciudadano_aceptar", args=[self.derivacion.pk])
        self.url_rechazar = reverse("legajos:derivacion_ciudadano_rechazar", args=[self.derivacion.pk])

    def _sigue_pendiente(self):
        self.derivacion.refresh_from_db()
        return self.derivacion.estado == "PENDIENTE"

    # ------------------------------------------------------------------ método
    def test_aceptar_por_get_es_405_y_no_inscribe(self):
        """La PoC `SEC12DerivacionGetTests` invertida: el GET ya no escribe."""
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.editar", username="edita-get"))

        respuesta = cliente.get(self.url_aceptar)

        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(self._sigue_pendiente())
        self.assertFalse(InscripcionPrograma.objects.filter(ciudadano=self.ciudadano).exists())

    def test_rechazar_por_get_es_405_y_sigue_pendiente(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.editar", username="edita-get-rech"))

        respuesta = cliente.get(self.url_rechazar)

        self.assertEqual(respuesta.status_code, 405)
        self.assertTrue(self._sigue_pendiente())

    # ------------------------------------------------------------- capacidades
    def test_el_anonimo_va_al_login(self):
        for url in (self.url_aceptar, self.url_rechazar):
            with self.subTest(url=url):
                respuesta = Client().post(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertIn(reverse("users:login"), respuesta["Location"])
        self.assertTrue(self._sigue_pendiente())

    def test_sin_rol_no_acepta_ni_rechaza(self):
        cliente = Client()
        cliente.force_login(usuario_con(username="sin-rol-deriva"))

        for url in (self.url_aceptar, self.url_rechazar):
            with self.subTest(url=url):
                respuesta = cliente.post(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta["Location"], reverse("core:inicio"))
        self.assertTrue(self._sigue_pendiente())
        self.assertFalse(InscripcionPrograma.objects.filter(ciudadano=self.ciudadano).exists())

    def test_con_ciudadano_ver_tampoco(self):
        """Ver legajos no alcanza para mover una derivación (D-12)."""
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="solo-ve-deriva"))

        respuesta = cliente.post(self.url_aceptar)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("core:inicio"))
        self.assertTrue(self._sigue_pendiente())

    def test_el_ciudadano_del_portal_no_entra(self):
        usuario = User.objects.create_user("portal-deriva", password=CLAVE)
        grupo, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        usuario.groups.add(grupo)
        cliente = Client()
        cliente.force_login(usuario)

        respuesta = cliente.post(self.url_aceptar)

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("/legajos/", respuesta["Location"])
        self.assertTrue(self._sigue_pendiente())

    def test_con_ciudadano_editar_acepta(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.editar", username="edita-acepta"))

        respuesta = cliente.post(self.url_aceptar)

        self.assertEqual(respuesta.status_code, 302)
        self.derivacion.refresh_from_db()
        self.assertEqual(self.derivacion.estado, "ACEPTADA")

    def test_el_superusuario_rechaza(self):
        cliente = Client()
        cliente.force_login(User.objects.create_superuser("root-deriva", "root-d@example.test", CLAVE))

        respuesta = cliente.post(self.url_rechazar)

        self.assertEqual(respuesta.status_code, 302)
        self.derivacion.refresh_from_db()
        self.assertEqual(self.derivacion.estado, "RECHAZADA")


class DerivarProgramaViewRbacTests(TestCase):
    """`derivar_programa_view`: la pantalla pide capacidad y la inscripción
    directa deja de depender de `is_staff` (SEC-12, D-12)."""

    @classmethod
    def setUpTestData(cls):
        cls.ciudadano = Ciudadano.objects.create(dni="21777888", nombre="Rubén", apellido="Paz")

    def _url(self):
        return reverse("legajos:derivar_programa", args=[self.ciudadano.pk])

    def test_sin_rol_no_abre_la_pantalla(self):
        cliente = Client()
        cliente.force_login(usuario_con(username="sin-rol-pantalla"))

        respuesta = cliente.get(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("core:inicio"))

    def test_con_ciudadano_ver_tampoco(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="solo-ve-pantalla"))

        self.assertEqual(cliente.get(self._url()).status_code, 302)

    def test_is_staff_sin_capacidad_ya_no_ofrece_inscripcion_directa(self):
        """`is_staff` es una marca del admin de Django, no una capacidad."""
        cliente = Client()
        cliente.force_login(usuario_con(username="staff-sin-rol", is_staff=True))

        respuesta = cliente.get(self._url())

        self.assertEqual(respuesta.status_code, 302)

    def test_con_ciudadano_editar_abre_y_ofrece_inscripcion_directa(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.editar", username="edita-pantalla"))

        respuesta = cliente.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["puede_inscripcion_directa"])

    def test_el_anonimo_va_al_login(self):
        respuesta = Client().get(self._url())

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse("users:login"), respuesta["Location"])


class BandejaDeDerivacionesUiTests(TestCase):
    """SEC-12 del lado del template: las dos acciones son POST con CSRF.

    Se afirma sobre la **fuente** del template y no sobre el HTML renderizado
    porque hoy `ProgramaDetailView` deja `derivaciones_ciudadanos` en `[]`: la
    operativa institucional se retiró con `models_institucional` y la bandeja
    está vacía (LEG-06, Ola 7). Las URLs, en cambio, siguen publicadas y
    ejecutables —por eso el arreglo de las vistas no es latente—.
    """

    TEMPLATE = Path(settings.BASE_DIR) / "legajos" / "templates" / "legajos" / "programas" / "programa_detail.html"

    def setUp(self):
        self.fuente = self.TEMPLATE.read_text(encoding="utf-8")

    def test_rechazar_ya_no_es_un_enlace_get(self):
        self.assertNotIn("<a href=\"{% url 'legajos:derivacion_ciudadano_rechazar'", self.fuente)
        self.assertIn(
            '<form method="post" action="{% url \'legajos:derivacion_ciudadano_rechazar\' derivacion.pk %}"',
            self.fuente,
        )

    def test_las_dos_acciones_llevan_csrf(self):
        for nombre in ("derivacion_ciudadano_aceptar", "derivacion_ciudadano_rechazar"):
            with self.subTest(nombre=nombre):
                bloque = self.fuente.split(f"'legajos:{nombre}'", 1)[1][:200]
                self.assertIn("{% csrf_token %}", bloque)

    def test_el_rechazo_confirma_con_sweetalert_y_no_con_confirm_nativo(self):
        self.assertIn("¿Rechazar la derivación?", self.fuente)
        self.assertIn("js-rechazar-derivacion", self.fuente)
        self.assertNotIn("window.confirm(", self.fuente)
