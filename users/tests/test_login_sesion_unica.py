from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from users.models import Profile


class LoginSesionUnicaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="operador.login", password="clave-correcta")

    def _ingresar(self, client):
        return client.post(reverse("users:login"), {"username": self.user.username, "password": "clave-correcta"})

    def test_el_login_registra_la_sesion_web_en_el_profile(self):
        respuesta = self._ingresar(self.client)

        self.assertEqual(respuesta.status_code, 302)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.backoffice_session_key, self.client.session.session_key)

    def test_el_login_crea_el_profile_si_el_usuario_no_lo_tiene(self):
        Profile.objects.filter(user=self.user).delete()

        respuesta = self._ingresar(self.client)

        self.assertEqual(respuesta.status_code, 302)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.backoffice_session_key, self.client.session.session_key)

    def test_un_nuevo_ingreso_queda_como_la_sesion_vigente(self):
        primera = Client()
        segunda = Client()

        self._ingresar(primera)
        self._ingresar(segunda)

        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.backoffice_session_key, segunda.session.session_key)
        self.assertNotEqual(profile.backoffice_session_key, primera.session.session_key)
