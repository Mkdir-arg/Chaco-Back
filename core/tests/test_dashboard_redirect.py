from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class DashboardRedirectTests(TestCase):
    """`/dashboard/` es un alias histórico y tiene que llevar al inicio real.

    Resolvía `dashboard:inicio`, que está montado en la raíz junto al login: el
    reverse daba `/`, así que el usuario autenticado rebotaba por la pantalla de
    login en lugar de aterrizar en `/inicio/`.
    """

    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="dashboard_redirect",
            password="clave-de-prueba",
        )

    def test_usuario_autenticado_termina_en_inicio(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:dashboard"))

        # `fetch_redirect_response=False`: acá se valida el destino del redirect,
        # no que `/inicio/` renderice.
        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)

    def test_el_destino_no_es_el_login(self):
        """La regresión concreta: el destino no puede volver a ser `/`."""
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse("core:dashboard"))

        self.assertNotEqual(respuesta["Location"], reverse("users:login"))

    def test_usuario_anonimo_sigue_protegido(self):
        destino = reverse("core:dashboard")

        respuesta = self.client.get(destino)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], f"{reverse('users:login')}?next={destino}")
