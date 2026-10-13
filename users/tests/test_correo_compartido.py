"""Un mismo correo en varios usuarios del backoffice (decisión del PM, 13/10/2026).

Una persona puede tener más de un usuario con la misma casilla, y eso se mantiene:
no hay correo único. Lo que no puede pasar es que no sepa **de qué usuario** es cada
correo de recupero, ni que el alta le muestre una clave que el sistema va a ignorar.
"""

import re

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.tests.test_usuarios_abm import _admin

CORREO = "persona@example.com"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RecuperoConCorreoCompartidoTests(TestCase):
    def setUp(self):
        self.jperez = User.objects.create_user("jperez", email=CORREO, password="Anterior-123")
        self.jperez_becas = User.objects.create_user("jperez.becas", email=CORREO, password="Anterior-123")

    def _pedir_recupero(self):
        respuesta = self.client.post(reverse("users:recuperar_contrasena"), {"email": CORREO})
        self.assertRedirects(respuesta, reverse("users:recuperar_contrasena_enviada"))

    def _correo_de(self, usuario):
        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        correos = [m for m in mail.outbox if f"/establecer-contrasena/{uid}/" in m.body]
        self.assertEqual(len(correos), 1, f"se esperaba un solo correo con el enlace de {usuario.username}")
        return correos[0], uid

    def test_sale_un_correo_por_usuario_y_cada_uno_dice_de_cual_es(self):
        self._pedir_recupero()

        self.assertEqual(len(mail.outbox), 2)
        for usuario, otro in ((self.jperez, self.jperez_becas), (self.jperez_becas, self.jperez)):
            correo, uid = self._correo_de(usuario)
            html = correo.alternatives[0][0]

            self.assertEqual(correo.to, [CORREO])
            self.assertTrue(correo.subject.endswith(f"— usuario {usuario.username}"), correo.subject)
            self.assertNotIn("\n", correo.subject)
            self.assertIn(f"Este enlace cambia la contraseña del usuario {usuario.username}.", correo.body)
            self.assertIn(
                f'Este enlace cambia la contraseña del usuario <strong style="color:#252f40;">{usuario.username}</strong>.',
                html,
            )
            # El enlace del html es el de este usuario, no el del otro.
            self.assertIn(f"/establecer-contrasena/{uid}/", html)
            uid_otro = urlsafe_base64_encode(force_bytes(otro.pk))
            self.assertNotIn(f"/establecer-contrasena/{uid_otro}/", correo.body)
            self.assertNotIn(f"/establecer-contrasena/{uid_otro}/", html)

    def test_la_pagina_del_enlace_dice_que_usuario_se_esta_cambiando(self):
        self._pedir_recupero()
        correo, _ = self._correo_de(self.jperez_becas)
        enlace = re.search(r"https?://[^/\s]+(/establecer-contrasena/\S+/)", correo.body).group(1)

        respuesta = self.client.get(enlace, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["validlink"])
        self.assertContains(
            respuesta, "Estás definiendo la contraseña del usuario <strong>jperez.becas</strong>.", html=False
        )

    def test_enlace_invalido_no_nombra_ningun_usuario(self):
        uid = urlsafe_base64_encode(force_bytes(self.jperez.pk))
        respuesta = self.client.get(
            reverse("users:establecer_contrasena", kwargs={"uidb64": uid, "token": "no-es-un-token"})
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Estás definiendo la contraseña")
        self.assertNotContains(respuesta, "jperez")


class AltaClaveConCorreoTests(TestCase):
    AYUDA_CON_CORREO = "Se genera automáticamente y se envía por correo."

    def setUp(self):
        self.client.force_login(_admin("admin.alta"))
        self.url = reverse("users:usuario_crear")

    def _bloque_clave(self, respuesta):
        html = respuesta.content.decode()
        inicio = html.index('id="clave-alta"')
        return html[inicio : html.index("</div>", inicio)]

    def test_sin_correo_la_clave_es_obligatoria(self):
        bloque = self._bloque_clave(self.client.get(self.url))

        self.assertIn('<span id="clave-alta-obligatoria" class="text-fg-danger">*</span>', bloque)
        self.assertIn('aria-describedby="id_password-ayuda"', bloque)
        self.assertIn("Con correo informado no hace falta", bloque)
        self.assertIn(f'data-ayuda-con-correo="{self.AYUDA_CON_CORREO}"', bloque)

    def test_con_correo_la_pantalla_dice_que_la_genera_el_sistema(self):
        # Vuelve renderizado por otro error (usuario repetido): el estado sale del correo
        # cargado, y el correo repetido no es error (puede estar en varios usuarios).
        User.objects.create_user("repetido", email=CORREO, password="x")
        respuesta = self.client.post(self.url, {"username": "repetido", "email": CORREO})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["form"].errors.get("username"))
        self.assertNotIn("email", respuesta.context["form"].errors)
        bloque = self._bloque_clave(respuesta)
        self.assertIn('<span id="clave-alta-obligatoria" class="text-fg-danger" hidden>*</span>', bloque)
        self.assertIn(
            f'<p id="id_password-ayuda" class="mt-1 text-xs text-body-subtle">{self.AYUDA_CON_CORREO}</p>', bloque
        )

    def test_la_edicion_no_muestra_el_bloque_de_clave_del_alta(self):
        otro = User.objects.create_user("existente", email=CORREO, password="x")

        respuesta = self.client.get(reverse("users:usuario_editar", args=[otro.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, 'id="clave-alta"')
