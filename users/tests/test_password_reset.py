from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetTests(TestCase):
    def test_envia_enlace_y_la_respuesta_no_revela_cuentas(self):
        User.objects.create_user("territorial", email="territorial@example.com", password="anterior")
        url = reverse("users:recuperar_contrasena")

        existente = self.client.post(url, {"email": "territorial@example.com"})
        inexistente = self.client.post(url, {"email": "nadie@example.com"})

        self.assertRedirects(existente, reverse("users:recuperar_contrasena_enviada"))
        self.assertRedirects(inexistente, reverse("users:recuperar_contrasena_enviada"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/establecer-contrasena/", mail.outbox[0].body)
