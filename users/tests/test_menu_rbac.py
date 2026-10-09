from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from core import rbac
from users.models import RolMeta
from users.tests.test_rbac import _perm, render_sidebar

_CAPS_OPERADOR = [
    "ciudadano.ver",
    # SEC-20 / D-20 (PM, 08-oct-2026): la exportación del padrón es capacidad propia y
    # se siembra a quien tiene `ciudadano.ver`, así que el Operador la conserva.
    "ciudadano.exportar",
    "reporte.ver",
    "config.administrar",
    "usuario.administrar",
    "rol.administrar",
]


class OperadorBackofficeSeedTests(TestCase):
    """#59 — el seed crea el rol 'Operador de backoffice' idempotente."""

    def test_seed_crea_operador_con_caps_exactas(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        g = Group.objects.get(name="Operador de backoffice")
        self.assertCountEqual(rbac.capacidades_de_grupo(g), _CAPS_OPERADOR)
        self.assertFalse(g.meta.protegido)
        self.assertEqual(g.meta.categoria, rbac.CATEGORIA_BACKOFFICE)

    def test_seed_idempotente(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        g = Group.objects.get(name="Operador de backoffice")  # no duplica
        self.assertCountEqual(rbac.capacidades_de_grupo(g), _CAPS_OPERADOR)


class MenuRestringidoTests(TestCase):
    """#59 — el sidebar se gobierna por capacidades (ítems gateados)."""

    def setUp(self):
        call_command("seed_rbac", verbosity=0, stdout=StringIO())
        self.rol = Group.objects.get(name="Operador de backoffice")
        self.user = User.objects.create_user("op", password="x")
        self.user.groups.add(self.rol)

    def test_menu_reducido_para_rol_restringido(self):  # TC-59-01..04
        html = render_sidebar(User.objects.get(pk=self.user.pk))
        # Ve: Ciudadanos (ciudadano.ver) y Administración (usuario.administrar).
        self.assertIn(reverse("legajos:ciudadanos"), html)
        self.assertIn(reverse("users:usuarios"), html)
        # No ve los 2 sub-ítems gateados ni los módulos sin capacidad.
        self.assertNotIn(reverse("legajos:ciudadano_nuevo"), html)  # TC-59-03
        # TC-59-04 medía «Cola Conversaciones» (`conversacion.configurar`), el otro
        # sub-ítem gateado. Se fue con el apagado de la app (G1-01 fase 2): que el
        # sidebar no lo nombre lo mide `conversaciones/tests/test_apagado.py`.
        self.assertNotIn("/conversaciones/", html)  # TC-59-04
        self.assertNotIn(reverse("legajos:dashboard_contactos"), html)  # TC-59-02
        self.assertNotIn(reverse("core:relevamientos"), html)  # TC-59-02

    def test_admin_ve_menu_completo(self):  # TC-59-07
        su = User.objects.create_superuser("root", "root@example.com", "x")
        html = render_sidebar(su)
        self.assertNotIn(reverse("legajos:ciudadano_nuevo"), html)  # ocultado del menú por decisión de producto
        # Ni al superusuario, que tiene `conversacion.configurar` por bypass: el ítem
        # no existe más (G1-01 fase 2).
        self.assertNotIn("/conversaciones/", html)
        self.assertIn(reverse("legajos:dashboard_contactos"), html)
        # Usamos href= para evitar falso positivo por substring de /becas/relevamientos/
        self.assertNotIn(f'href="{reverse("core:relevamientos")}"', html)

    def test_modulo_becas_se_muestra_como_programas(self):
        su = User.objects.create_superuser("root-programas", "root-programas@example.com", "x")

        html = render_sidebar(su)

        self.assertIn('<span class="flex-1">Programas</span>', html)
        self.assertIn('title="Programas"', html)
        self.assertNotIn('<span class="flex-1">Becas</span>', html)

    def test_item_programas_marca_la_pantalla_activa(self):
        su = User.objects.create_superuser("root-activo", "root-activo@example.com", "x")
        url = reverse("becas:programas")
        req = RequestFactory().get(url)
        req.user = su
        req.resolver_match = resolve(url)

        html = render_to_string("includes/sidebar/opciones.html", {"request": req, "branding": {}})

        inicio = html.index(f'<a href="{url}"')
        ancla = html[inicio : html.index("</a>", inicio)]
        self.assertIn("background: var(--bg-brand)", ancla)
        self.assertIn('aria-current="page"', ancla)

    def _sidebar_en(self, nombre_url, user):
        url = reverse(nombre_url)
        req = RequestFactory().get(url)
        req.user = user
        req.resolver_match = resolve(url)
        return render_to_string("includes/sidebar/opciones.html", {"request": req, "branding": {}})

    @staticmethod
    def _ancla(html, href, desde=0):
        inicio = html.index(f'<a href="{href}"', desde)
        return html[inicio : html.index("</a>", inicio)]

    def test_subitem_reportes_de_becas_marca_aria_current(self):
        su = User.objects.create_superuser("root-rep-becas", "root-rep-becas@example.com", "x")
        html = self._sidebar_en("becas:reportes", su)
        ancla = self._ancla(html, reverse("becas:reportes"))
        self.assertIn("background: var(--bg-brand)", ancla)
        self.assertIn('aria-current="page"', ancla)

    def test_grupos_colapsados_marcan_aria_current(self):
        su = User.objects.create_superuser("root-colapsado", "root-colapsado@example.com", "x")
        casos = [("becas:programas", "Programas"), ("configuracion:provincias", "Configuración")]
        for nombre, etiqueta in casos:
            with self.subTest(etiqueta):
                html = self._sidebar_en(nombre, su)
                inicio = html.index(f'title="{etiqueta}"')
                ancla = html[html.rindex("<a ", 0, inicio) : html.index("</a>", inicio)]
                self.assertIn("background: var(--bg-brand)", ancla)
                self.assertIn('aria-current="page"', ancla)

    def test_reportes_de_nivel_superior_no_se_marca_en_becas(self):
        su = User.objects.create_superuser("root-doble", "root-doble@example.com", "x")
        html = self._sidebar_en("becas:reportes", su)
        ancla = self._ancla(html, reverse("legajos:reportes"))
        self.assertNotIn("background: var(--bg-brand)", ancla)
        self.assertNotIn("aria-current", ancla)

    def test_ciudadanos_no_se_marca_en_reportes_ni_dashboard_de_legajos(self):
        su = User.objects.create_superuser("root-ciud", "root-ciud@example.com", "x")
        for nombre in ("legajos:reportes", "legajos:dashboard_contactos"):
            with self.subTest(nombre):
                html = self._sidebar_en(nombre, su)
                ancla = self._ancla(html, reverse("legajos:ciudadanos"))
                self.assertNotIn("aria-current", ancla)

    def test_rol_inactivo_solo_inicio(self):  # TC-59-08
        self.rol.meta.activo = False
        self.rol.meta.save(update_fields=["activo"])
        html = render_sidebar(User.objects.get(pk=self.user.pk))
        self.assertNotIn(reverse("legajos:ciudadanos"), html)
        self.assertNotIn(reverse("users:usuarios"), html)
        self.assertIn(reverse("core:inicio"), html)  # Inicio siempre visible


class MenuNotificacionesTests(TestCase):
    """Análisis 007, RF-007-01: el grupo «Notificaciones» con «Campañas», solo con `notificacion.ver`."""

    def _user(self, username, *codigos):
        g = Group.objects.create(name=f"rol-{username}")
        RolMeta.objects.create(grupo=g, categoria="Backoffice", activo=True)
        for c in codigos:
            g.permissions.add(_perm(c))
        u = User.objects.create_user(username, password="x")
        u.groups.add(g)
        return User.objects.get(pk=u.pk)

    def test_sin_notificacion_ver_no_ve_el_grupo(self):
        html = render_sidebar(self._user("sin-notif", "reporte.ver"))
        self.assertNotIn(reverse("notificaciones:campanas"), html)
        self.assertNotIn("Notificaciones", html)

    def test_con_notificacion_ver_ve_el_grupo_expandido_y_colapsado(self):
        html = render_sidebar(self._user("con-notif", "notificacion.ver"))
        self.assertIn('<span class="flex-1">Notificaciones</span>', html)
        self.assertIn('title="Notificaciones"', html)
        self.assertEqual(html.count(f'href="{reverse("notificaciones:campanas")}"'), 2)
        self.assertIn("Campañas", html)

    def test_va_despues_de_reportes(self):
        su = User.objects.create_superuser("root-notif", "root-notif@example.com", "x")
        html = render_sidebar(su)
        self.assertLess(html.index(reverse("legajos:reportes")), html.index(reverse("notificaciones:campanas")))

    def test_marca_la_pantalla_activa(self):
        su = User.objects.create_superuser("root-notif-act", "root-notif-act@example.com", "x")
        url = reverse("notificaciones:campanas")
        req = RequestFactory().get(url)
        req.user = su
        req.resolver_match = resolve(url)
        html = render_to_string("includes/sidebar/opciones.html", {"request": req, "branding": {}})
        inicio = html.index(f'<a href="{url}"')
        ancla = html[inicio : html.index("</a>", inicio)]
        self.assertIn('aria-current="page"', ancla)


class CiudadanoListBotonNuevoTests(TestCase):
    """#59 — el botón 'Nuevo Ciudadano' del LISTADO también se gatea por ciudadano.crear.

    (El enforcement por URL ya existía; esto evita el ítem visible que rebota.)
    """

    def _user(self, *codigos):
        g = Group.objects.create(name="rol-" + "-".join(codigos))
        RolMeta.objects.create(grupo=g, categoria="Backoffice", activo=True)
        for c in codigos:
            g.permissions.add(_perm(c))
        u = User.objects.create_user("u-" + "-".join(codigos), password="x")
        u.groups.add(g)
        return u

    # El botón se mide por su **destino** y no por su texto: el rótulo cambió con la
    # migración al arquetipo Listado (Cambio 167) y, con la aserción sobre el texto, el
    # caso «sin capacidad» pasaba igual aunque el botón siguiera dibujándose.
    def test_sin_crear_no_ve_boton(self):
        self.client.force_login(self._user("ciudadano.ver"))
        resp = self.client.get(reverse("legajos:ciudadanos"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("legajos:ciudadano_nuevo"))

    def test_con_crear_ve_boton(self):
        self.client.force_login(self._user("ciudadano.ver", "ciudadano.crear"))
        resp = self.client.get(reverse("legajos:ciudadanos"))
        self.assertContains(resp, f'href="{reverse("legajos:ciudadano_nuevo")}"')
