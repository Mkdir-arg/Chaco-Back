from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.services.invitations import enviar_invitacion_usuario


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="DATAÑACH <no-responder@example.com>",
)
class InvitacionUsuarioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="territorial.correo",
            email="territorial@example.com",
            password="temporal-inicial",
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)
        self.url = reverse("users:establecer_contrasena", kwargs={"uidb64": self.uid, "token": self.token})

    def test_correo_informa_usuario_y_enlace_sin_contrasena(self):
        enviar_invitacion_usuario(self.user, f"https://datanach.example{self.url}")

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("territorial.correo", mail.outbox[0].body)
        self.assertIn(self.url, mail.outbox[0].body)
        self.assertNotIn("temporal-inicial", mail.outbox[0].body)

    def test_enlace_permite_establecer_una_nueva_contrasena(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            response.url,
            {"new_password1": "Nueva-clave-segura-2026", "new_password2": "Nueva-clave-segura-2026"},
        )
        self.assertRedirects(response, reverse("users:login"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Nueva-clave-segura-2026"))
