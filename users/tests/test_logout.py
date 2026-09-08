from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


class LogoutPorPostTests(TestCase):
    """`LogoutView` dejó de aceptar GET en Django 5.0.

    El upgrade a Django 5.2 dejó el cierre de sesión del backoffice devolviendo 405,
    porque el ítem del menú era un enlace. Estas pruebas fijan el contrato: la sesión
    se cierra por POST y ninguna pantalla vuelve a ofrecer el logout como enlace.

    Las dos últimas renderizan el template directamente en lugar de pedir la página
    con el cliente de pruebas: así verifican el markup sin depender de que la vista
    completa se pueda montar.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("territorial", password="clave-actual")
        self.url = reverse("users:logout")

    def test_el_post_cierra_la_sesion_y_lleva_al_login(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("users:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_el_menu_del_backoffice_cierra_sesion_por_formulario(self):
        html = render_to_string("includes/navbar.html", {"user": self.usuario})

        self.assertIn('action="%s"' % self.url, html)
        self.assertNotIn('href="%s"' % self.url, html)

    def test_la_pantalla_de_cambio_obligatorio_sale_por_formulario(self):
        html = render_to_string("user/cambiar_contrasena_obligatorio.html", {"user": self.usuario})

        self.assertIn('action="%s"' % self.url, html)
        self.assertNotIn('href="%s"' % self.url, html)
