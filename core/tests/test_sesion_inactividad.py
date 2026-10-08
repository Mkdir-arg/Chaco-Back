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

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from core.middleware import (
    CLAVE_ULTIMA_ACTIVIDAD,
    MARGEN_INACTIVIDAD_SEGUNDOS,
    RUTAS_SIN_MARCA_DE_ACTIVIDAD,
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
class PollingDeFondoNoRenuevaTests(TestCase):
    """El `setInterval` del navegador no es «el usuario está ahí».

    Con estas rutas marcando actividad, una pestaña olvidada en el dashboard de
    performance o en cualquier pantalla del backoffice —el notificador de
    conversaciones va en `includes/base.html`— renovaba la sesión sola cada 5 s,
    y el cierre por inactividad no cerraba nada. La señal de actividad real es el
    latido, que `idle-logout.js` dispara solo con mouse, teclado o scroll.
    """

    @classmethod
    def setUpTestData(cls):
        cls.agente = User.objects.create_user("agente-fondo", "agente-fondo@example.test", CLAVE)

    def setUp(self):
        self.navegador = Client()
        self.navegador.force_login(self.agente)

    def test_las_rutas_de_la_lista_existen(self):
        """Una ruta mal escrita acá no rompe nada: deja de eximir en silencio."""
        from django.urls import resolve

        for ruta in sorted(RUTAS_SIN_MARCA_DE_ACTIVIDAD):
            with self.subTest(ruta=ruta):
                self.assertTrue(resolve(ruta))

    def test_el_polling_de_fondo_no_corre_el_reloj(self):
        for ruta in sorted(RUTAS_SIN_MARCA_DE_ACTIVIDAD):
            with self.subTest(ruta=ruta):
                _envejecer(self.navegador, VENTANA_REFRESCO_SEGUNDOS + 5)
                antes = self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD]

                self.navegador.get(ruta)

                self.assertEqual(self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD], antes)

    def test_pero_tampoco_salvan_una_sesion_ya_vencida(self):
        """No marcar no es quedar exento: el corte sigue aplicando."""
        ruta = "/conversaciones/api/estadisticas/"
        _envejecer(self.navegador, 15 * 60 + MARGEN_INACTIVIDAD_SEGUNDOS + 1)

        respuesta = self.navegador.get(ruta)

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(respuesta.url.startswith(reverse("users:login")))

    def test_el_latido_sigue_siendo_actividad(self):
        """Es la contracara: lo único que renueva sin pedir pantallas."""
        self.assertNotIn(reverse("core:sesion_latido"), RUTAS_SIN_MARCA_DE_ACTIVIDAD)

        _envejecer(self.navegador, VENTANA_REFRESCO_SEGUNDOS + 5)
        antes = self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD]

        self.navegador.post(reverse("core:sesion_latido"))

        self.assertGreater(self.navegador.session[CLAVE_ULTIMA_ACTIVIDAD], antes)


@override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
class ApiConSesionExpiraTests(TestCase):
    """`/api/` está exenta del **refresco**, no de la **expiración**.

    Eximir la rama entera dejaba que una cookie de sesión robada sirviera el
    padrón por la API durante las 24 h de `SESSION_COOKIE_AGE`, con la marca de
    actividad envejecida 48 h: el cierre por inactividad no existía del otro lado
    de `/api/`.
    """

    #: El pedido del escenario: con sesión viva y la capacidad puesta, da 200.
    PADRON = "/api/legajos/ciudadanos/?search=peralta"

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth.models import Group, Permission
        from django.contrib.contenttypes.models import ContentType

        from core import rbac
        from legajos.models import Ciudadano
        from users.models import Capacidad, RolMeta

        Ciudadano.objects.create(dni="25666777", nombre="Ana", apellido="Peralta")

        grupo = Group.objects.create(name="Rol idle ciudadano.ver")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        grupo.permissions.add(
            Permission.objects.get(
                codename=rbac.codename_de("ciudadano.ver"),
                content_type=ContentType.objects.get_for_model(Capacidad),
            )
        )
        cls.agente = User.objects.create_user("agente-api-idle", "agente-api@example.test", CLAVE)
        cls.agente.groups.add(grupo)

    def test_con_la_sesion_viva_la_api_sirve_el_padron(self):
        """Control: sin esto, el test de abajo daría verde por falta de permiso."""
        navegador = Client()
        navegador.force_login(self.agente)

        self.assertEqual(navegador.get(self.PADRON).status_code, 200)

    def test_con_la_sesion_vencida_la_api_no_sirve_el_padron(self):
        navegador = Client()
        navegador.force_login(self.agente)
        _envejecer(navegador, 48 * 60 * 60)

        respuesta = navegador.get(self.PADRON)

        self.assertIn(respuesta.status_code, (401, 403, 302))

    def test_la_api_no_renueva_la_sesion_de_quien_no_esta_mirando(self):
        navegador = Client()
        navegador.force_login(self.agente)
        _envejecer(navegador, VENTANA_REFRESCO_SEGUNDOS + 5)
        antes = navegador.session[CLAVE_ULTIMA_ACTIVIDAD]

        navegador.get(self.PADRON)

        self.assertEqual(navegador.session[CLAVE_ULTIMA_ACTIVIDAD], antes)


@override_settings(SESSION_IDLE_TIMEOUT_MINUTES=15)
class ApiDeCampoNoExpiraTests(TestCase):
    """La app de campo autentica por Token **sin cookie**: no hay sesión que vencer.

    Por eso quitar la exención de `/api/` no la toca: llega al middleware con
    `request.user` anónimo —el Token lo resuelve DRF **dentro** de la vista— y el
    pedido pasa de largo. El test manda solo el Token justamente para probar eso:
    con un `force_login` delante estaría probando una sesión de backoffice.
    """

    def test_la_app_de_campo_entra_sin_sesion_y_no_expira(self):
        from rest_framework.authtoken.models import Token

        territorial = User.objects.create_user("territorial-idle", "t-idle@example.test", CLAVE)
        token = Token.objects.create(user=territorial)

        navegador = Client()
        self.assertNotIn(settings.SESSION_COOKIE_NAME, navegador.cookies)

        respuesta = navegador.get("/api/becas/relevamientos/", HTTP_AUTHORIZATION=f"Token {token.key}")

        # Ni el redirect al login ni el 401 del corte por inactividad: la app no
        # pasa por el middleware porque no trae sesión.
        self.assertNotIn(respuesta.status_code, (302, 401))


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
