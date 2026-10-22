import time

from django.conf import settings
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from core.middleware import CLAVE_ULTIMA_ACTIVIDAD, MARGEN_INACTIVIDAD_SEGUNDOS


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


class LogoutNoDejaNextAlLoginTests(TestCase):
    """El POST a `/logout` con la sesión vencida terminaba en `/?next=/logout`.

    Al ingresar, el login redirigía a `next`, o sea a GET `/logout`, que da 405.
    Dos defensas: el middleware de inactividad no pone `next` cuando el pedido es
    el logout, y el login nunca devuelve el logout como destino.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("territorial", password="Clave-Logout-2026x")
        self.logout_url = reverse("users:logout")
        self.login_url = reverse("users:login")

    def _envejecer(self):
        sesion = self.client.session
        sesion[CLAVE_ULTIMA_ACTIVIDAD] = time.time() - (15 * 60 + MARGEN_INACTIVIDAD_SEGUNDOS + 1)
        sesion.save()

    @override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
    def test_logout_con_sesion_vencida_va_al_login_sin_next(self):
        self.client.force_login(self.usuario)
        self._envejecer()

        respuesta = self.client.post(self.logout_url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], self.login_url)
        self.assertNotIn("next", respuesta["Location"])
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
    def test_una_ruta_comun_con_sesion_vencida_sigue_llevando_next(self):
        self.client.force_login(self.usuario)
        self._envejecer()

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta["Location"])

    def test_login_con_next_logout_va_a_la_pagina_de_inicio(self):
        respuesta = self.client.post(
            self.login_url + "?next=" + self.logout_url,
            {"username": "territorial", "password": "Clave-Logout-2026x", "next": self.logout_url},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse(settings.LOGIN_REDIRECT_URL))

    def test_usuario_logueado_en_login_con_next_logout_no_va_al_logout(self):
        self.client.force_login(self.usuario)

        respuesta = self.client.get(self.login_url + "?next=" + self.logout_url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertNotEqual(respuesta["Location"], self.logout_url)
        self.assertEqual(respuesta["Location"], reverse(settings.LOGIN_REDIRECT_URL))

    def test_login_con_next_valido_sigue_funcionando(self):
        destino = reverse("core:inicio")

        respuesta = self.client.post(
            self.login_url + "?next=" + destino,
            {"username": "territorial", "password": "Clave-Logout-2026x", "next": destino},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], destino)
