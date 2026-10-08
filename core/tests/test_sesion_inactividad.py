"""SEC-35 · El cierre por inactividad existe del lado del servidor.

Hasta el Cambio 185 el único que contaba la inactividad era
``static/custom/js/idle-logout.js``: con el JS deshabilitado, con la pantalla
abierta en una máquina compartida o con la cookie de sesión copiada, la sesión
seguía sirviendo las 24 h de ``SESSION_COOKIE_AGE``. Estos tests fijan las dos
mitades del arreglo: el middleware que corta, y el latido que impide que corte a
quien está trabajando sin pedir pantallas.

La otra mitad de la ficha —las cookies `Secure` que dependían de
``ENVIRONMENT=prd``— se verifica en ``CookiesSegurasTests``, contra el módulo de
settings y no contra una respuesta: el valor se deriva al importar.
"""

import time

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.middleware import (
    CLAVE_ULTIMA_ACTIVIDAD,
    MARGEN_INACTIVIDAD_SEGUNDOS,
    VENTANA_REFRESCO_SEGUNDOS,
)

CLAVE = "Clave-Seg-2026x"


def _envejecer(cliente, segundos):
    """Mueve hacia atrás la marca de actividad de la sesión del cliente."""
    sesion = cliente.session
    sesion[CLAVE_ULTIMA_ACTIVIDAD] = time.time() - segundos
    sesion.save()


@override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
class ExpiracionPorInactividadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.agente = User.objects.create_user("agente-idle", "agente-idle@example.test", CLAVE)

    def setUp(self):
        self.navegador = Client()
        self.navegador.force_login(self.agente)

    def test_el_login_deja_la_marca_puesta(self):
        """Sin esto la escribiría el primer request de cada sesión (una consulta más)."""
        self.assertIn(CLAVE_ULTIMA_ACTIVIDAD, self.navegador.session)

    def test_trabajando_la_sesion_sigue_viva(self):
        _envejecer(self.navegador, 5 * 60)

        respuesta = self.navegador.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 200)

    def test_pasado_el_timeout_la_sesion_se_cierra(self):
        _envejecer(self.navegador, 15 * 60 + MARGEN_INACTIVIDAD_SEGUNDOS + 1)

        respuesta = self.navegador.get(reverse("core:inicio"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse("users:login")))
        # La sesión se fue de verdad: el pedido siguiente tampoco entra.
        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 302)

    def test_el_margen_no_corta_antes_que_el_aviso_de_la_pantalla(self):
        """Justo en el límite del JS, el servidor todavía deja pasar.

        El contador del navegador mide mouse y teclado y el del servidor mide
        pedidos: el margen es lo que impide que el servidor mate la sesión de
        alguien que la pantalla todavía considera viva.
        """
        _envejecer(self.navegador, 15 * 60 + MARGEN_INACTIVIDAD_SEGUNDOS - 5)

        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 200)

    def test_el_latido_renueva_la_sesion(self):
        _envejecer(self.navegador, 15 * 60 - 30)

        latido = self.navegador.post(reverse("core:sesion_latido"))
        self.assertEqual(latido.status_code, 200)

        # Y con la marca renovada, el minuto que faltaba ya no alcanza.
        _envejecer(self.navegador, 60)
        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 200)

    def test_el_latido_es_post_y_pide_sesion(self):
        self.assertEqual(self.navegador.get(reverse("core:sesion_latido")).status_code, 405)
        self.assertEqual(Client().post(reverse("core:sesion_latido")).status_code, 302)

    def test_la_marca_no_se_reescribe_en_cada_pedido(self):
        """El techo de escritura es lo que evita un UPDATE de sesión por clic."""
        antes = self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD]

        self.navegador.get(reverse("core:inicio"))

        self.assertEqual(self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD], antes)

    def test_pasada_la_ventana_la_marca_se_corre(self):
        _envejecer(self.navegador, VENTANA_REFRESCO_SEGUNDOS + 5)
        antes = self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD]

        self.navegador.get(reverse("core:inicio"))

        self.assertGreater(self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD], antes)

    @override_settings(SESSION_IDLE_TIMEOUT_MINUTES=0)
    def test_en_cero_la_expiracion_queda_apagada(self):
        _envejecer(self.navegador, 48 * 60 * 60)

        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 200)

    def test_una_sesion_vieja_sin_marca_no_se_cierra(self):
        """Las sesiones abiertas al desplegar esto no se caen de golpe."""
        sesion = self.navegador.session
        del sesion[CLAVE_ULTIMA_ACTIVIDAD]
        sesion.save()

        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 200)
        self.assertIn(CLAVE_ULTIMA_ACTIVIDAD, self.navegador.session)


@override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
class ApiDeCampoNoExpiraTests(TestCase):
    """La app de campo autentica por Token y no tiene sesión que expirar.

    Es el caso que obliga a eximir `/api/`: ahí `request.user` todavía es anónimo
    cuando corre el middleware —el Token lo resuelve DRF **dentro** de la vista—,
    así que lo único que podría pasar es que una sesión de backoffice abierta en
    otra pestaña se llevara puesto el pedido de la app.
    """

    def test_la_api_de_campo_contesta_con_la_sesion_vencida(self):
        from rest_framework.authtoken.models import Token

        territorial = User.objects.create_user("territorial-idle", "t-idle@example.test", CLAVE)
        token = Token.objects.create(user=territorial)

        navegador = Client()
        navegador.force_login(territorial)
        _envejecer(navegador, 48 * 60 * 60)

        respuesta = navegador.get("/api/becas/relevamientos/", HTTP_AUTHORIZATION=f"Token {token.key}")

        self.assertNotEqual(respuesta.status_code, 302)


class CookiesSegurasTests(TestCase):
    """Las cookies dejaron de depender de `ENVIRONMENT` (SEC-35).

    `ENVIRONMENT` es una declaración y no un hecho —icore vale `prd` siendo DEV y
    QA lo pisa a `prd` (OPS-12)—, así que atarles el flag `Secure` dejaba la
    cookie de sesión viajando en claro en cualquier ambiente servido que no la
    declarara. El hecho es `DEBUG`.
    """

    def _settings_con(self, **entorno):
        """Evalúa `config/settings.py` **aparte**, con ese entorno.

        Se carga el archivo como un módulo propio y no se recarga
        `config.settings`: pisar el que ya está cargado le cambiaría los settings
        al resto de la suite.
        """
        import importlib.util
        import os
        import sys
        from pathlib import Path
        from unittest.mock import patch

        archivo = Path(__file__).resolve().parents[2] / "config" / "settings.py"
        base = {k: v for k, v in os.environ.items() if k not in ("DJANGO_DEBUG", "ENVIRONMENT")}
        spec = importlib.util.spec_from_file_location("_settings_de_prueba", archivo)
        modulo = importlib.util.module_from_spec(spec)
        try:
            with patch.dict(os.environ, {**base, **entorno}, clear=True), patch.object(sys, "argv", ["manage.py"]):
                spec.loader.exec_module(modulo)
            return (modulo.SESSION_COOKIE_SECURE, modulo.CSRF_COOKIE_SECURE)
        finally:
            sys.modules.pop("_settings_de_prueba", None)

    def test_sin_environment_pero_sin_debug_las_cookies_son_seguras(self):
        self.assertEqual(
            self._settings_con(DJANGO_SECRET_KEY="test-key", DJANGO_DEBUG="False"),
            (True, True),
        )

    def test_en_desarrollo_local_siguen_sin_secure(self):
        self.assertEqual(
            self._settings_con(DJANGO_SECRET_KEY="test-key", DJANGO_DEBUG="True"),
            (False, False),
        )
