from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from users.services.correo import enviar_credenciales_usuario, generar_password_provisoria


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="DATAÑACH <no-responder@example.com>",
)
class CredencialesPorCorreoTests(TestCase):
    """RN-C1: el alta envía usuario + clave provisoria (revierte el Cambio 13)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="territorial.correo",
            email="territorial@example.com",
            first_name="Ana",
        )

    def test_el_correo_lleva_usuario_y_clave_provisoria(self):
        enviar_credenciales_usuario(self.user, "Clave-Provisoria-9", protocol="https", domain="datanach.example")

        self.assertEqual(len(mail.outbox), 1)
        enviado = mail.outbox[0]
        self.assertIn("territorial.correo", enviado.body)
        self.assertIn("Clave-Provisoria-9", enviado.body)
        self.assertIn("https://datanach.example", enviado.body)

    def test_adjunta_la_version_html_con_la_marca(self):
        enviar_credenciales_usuario(self.user, "Clave-Provisoria-9", protocol="https", domain="datanach.example")

        alternativas = mail.outbox[0].alternatives
        self.assertEqual(len(alternativas), 1)
        html, tipo = alternativas[0]
        self.assertEqual(tipo, "text/html")
        self.assertIn("Clave-Provisoria-9", html)
        self.assertIn("DATAÑACH", html)
        # El logo tiene que ser una URL absoluta: el cliente de correo no resuelve /static/.
        self.assertIn("https://datanach.example/static/custom/chaco/login-logo.png", html)

    def test_el_asunto_se_prefija_fuera_de_produccion(self):
        # ENVIRONMENT por defecto en tests es "dev".
        enviar_credenciales_usuario(self.user, "Clave-Provisoria-9", domain="datanach.example")

        self.assertTrue(mail.outbox[0].subject.startswith("[DEV] "))

    def test_sin_correo_no_envia_y_avisa(self):
        sin_correo = User.objects.create_user(username="sin.correo")

        with self.assertRaises(ValueError):
            enviar_credenciales_usuario(sin_correo, "Clave-Provisoria-9")
        self.assertEqual(len(mail.outbox), 0)

    def test_la_clave_generada_no_usa_caracteres_ambiguos(self):
        for _ in range(20):
            clave = generar_password_provisoria()
            self.assertEqual(len(clave), 12)
            self.assertFalse(set(clave) & set("0O1lI"))


class LoginBrandAssetTests(TestCase):
    def test_login_web_usa_el_logo_svg_liviano(self):
        response = self.client.get(reverse("users:login"))

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("/static/custom/chaco/login-logo.svg", html)
        self.assertNotIn("/static/custom/chaco/login-logo.png", html)
        self.assertIn("/static/custom/css/tailwind.css", html)
        self.assertNotIn("cdn.tailwindcss.com", html)


class UserProfileSignalTests(TestCase):
    def test_crear_usuario_crea_su_profile(self):
        user = User.objects.create_user(username="usuario-con-profile")

        self.assertEqual(user.profile.user, user)


class CambioObligatorioPrimerLoginTests(TestCase):
    """RN-C2: con la clave provisoria sin cambiar no se puede operar."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="territorial.correo",
            email="territorial@example.com",
            password="Clave-Provisoria-9",
        )
        # Sobre la instancia cacheada, igual que el servicio: escribirlo por otra
        # vía lo pisa el post_save de User (ver `save_user_profile`).
        self.user.profile.debe_cambiar_contrasena = True
        self.user.profile.save(update_fields=["debe_cambiar_contrasena"])
        self.destino = reverse("users:cambiar_contrasena_obligatorio")

    def test_toda_pantalla_redirige_al_cambio_de_clave(self):
        self.client.force_login(self.user)

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertRedirects(respuesta, self.destino, fetch_redirect_response=False)

    def test_la_propia_pantalla_de_cambio_no_redirige(self):
        self.client.force_login(self.user)

        respuesta = self.client.get(self.destino)

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, f'method="post" action="{reverse("users:logout")}"')

    def test_al_cambiarla_se_libera_el_acceso_y_no_se_pierde_la_sesion(self):
        self.client.force_login(self.user)

        respuesta = self.client.post(
            self.destino,
            {"new_password1": "Nueva-clave-segura-2026", "new_password2": "Nueva-clave-segura-2026"},
        )

        self.assertRedirects(respuesta, reverse("core:inicio"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nueva-clave-segura-2026"))
        self.assertFalse(self.user.profile.debe_cambiar_contrasena)
        # La sesión rotó al cambiar la clave: el Profile tiene que quedar alineado
        # o BackofficeSingleSessionMiddleware expulsa al usuario en el próximo request.
        self.assertEqual(self.user.profile.backoffice_session_key, self.client.session.session_key)
        self.assertEqual(self.client.get(reverse("core:inicio")).status_code, 200)


class LogoutTests(TestCase):
    def test_logout_por_post_cierra_la_sesion(self):
        user = User.objects.create_user(username="operador.logout", password="clave-segura")
        self.client.force_login(user)

        respuesta = self.client.post(reverse("users:logout"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
