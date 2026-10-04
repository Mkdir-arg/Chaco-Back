"""RED-71 (auditoría oct-2026): contrato de `ApiCorsMiddleware`.

Hoy el middleware es un **no-op**: `DJANGO_CORS_ALLOWED_ORIGINS` no está definida
en ningún `.env.*.example` ni compose, y `_is_dev_origin` corta con `DEBUG=False`.
Eso es lo que hay que congelar, porque el **Cambio 52** fundamenta una decisión de
seguridad en que «no hay `django-cors-headers` en el proyecto, así que ningún
sitio externo puede leerlo»: la conclusión es correcta pero el motivo no —hay un
CORS propio, escrito a mano— y nada escrito lo sostenía.

Lo que estos tests ponen por escrito:

- sin orígenes configurados, ninguna respuesta de `/api/` lleva
  `Access-Control-Allow-Origin` (y por lo tanto tampoco `-Credentials`);
- poner un origen en la variable alcanza para que ese origen lea `/api/` **con la
  cookie del usuario**: es una decisión, no un detalle de configuración;
- con `DEBUG=False` ningún host privado pasa, ni siquiera `10.0.0.5`;
- con `DEBUG=True` el prefijo de `_is_dev_origin` acepta `10.atacante.com`
  (README §8.3: explotable solo en una máquina de desarrollo). Queda fijado para
  que quitar la guarda de `DEBUG` no sea un cambio silencioso;
- el `OPTIONS` anónimo a `/api/` contesta 200 con cuerpo vacío sin tocar la base;
- fuera de `/api/` el middleware no toca nada.

**Gotcha:** `allowed_origins` se lee en `__init__` con `os.getenv`, no de
`settings`. `override_settings` no sirve: hay que instanciar el middleware con la
variable puesta.
"""

import os
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from core.middleware import ApiCorsMiddleware

RAIZ = Path(settings.BASE_DIR)
VARIABLE = "DJANGO_CORS_ALLOWED_ORIGINS"
ORIGEN_PROPIO = "https://app.datanach.chaco.gob.ar"
ORIGEN_AJENO = "https://evil.example"
RUTA_API = "/api/users/me/"


def _middleware(origenes=""):
    """El middleware tal como lo arma Django al arrancar, con la variable puesta."""
    with patch.dict(os.environ, {VARIABLE: origenes}):
        return ApiCorsMiddleware(lambda request: HttpResponse("ok"))


class ApiCorsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _respuesta(self, origenes="", ruta=RUTA_API, origin=ORIGEN_AJENO, **extra):
        peticion = self.factory.get(ruta, HTTP_ORIGIN=origin, **extra)
        return _middleware(origenes)(peticion)

    def test_sin_origenes_configurados_ninguna_respuesta_lleva_allow_origin(self):
        respuesta = self._respuesta(origenes="")

        self.assertNotIn("Access-Control-Allow-Origin", respuesta)
        self.assertNotIn("Access-Control-Allow-Credentials", respuesta)

    def test_un_origen_de_la_lista_recibe_las_cabeceras_y_otro_no(self):
        permitida = self._respuesta(origenes=ORIGEN_PROPIO, origin=ORIGEN_PROPIO)
        rechazada = self._respuesta(origenes=ORIGEN_PROPIO, origin=ORIGEN_AJENO)

        self.assertEqual(permitida["Access-Control-Allow-Origin"], ORIGEN_PROPIO)
        # Con credenciales: el origen de la lista lee `/api/` con la cookie de
        # sesión del usuario. Por eso sumar un origen es una decisión revisable.
        self.assertEqual(permitida["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(permitida["Vary"], "Origin")
        self.assertNotIn("Access-Control-Allow-Origin", rechazada)

    @override_settings(DEBUG=False)
    def test_con_debug_false_un_host_privado_no_pasa(self):
        for origen in (f"http://10.0.0.5:{8000}", "https://10.atacante.com", "http://localhost:3000"):
            with self.subTest(origen=origen):
                respuesta = self._respuesta(origenes="", origin=origen)
                self.assertNotIn("Access-Control-Allow-Origin", respuesta)

    @override_settings(DEBUG=True)
    def test_con_debug_true_el_prefijo_de_dev_acepta_un_host_ajeno(self):
        """Caracterización: `_is_dev_origin` compara por prefijo, no por red.

        `10.atacante.com` no es una IP privada, pero empieza con `10.` y pasa.
        Solo alcanza a una máquina con `DEBUG=True` (README §8.3), y el test está
        acá para que sacar la guarda de `DEBUG` no sea gratis.
        """
        respuesta = self._respuesta(origenes="", origin="https://10.atacante.com")

        self.assertEqual(respuesta["Access-Control-Allow-Origin"], "https://10.atacante.com")

    def test_una_ruta_fuera_de_api_nunca_lleva_cabeceras_cors(self):
        respuesta = self._respuesta(origenes=ORIGEN_PROPIO, ruta="/usuarios/", origin=ORIGEN_PROPIO)

        self.assertNotIn("Access-Control-Allow-Origin", respuesta)

    def test_sin_cabecera_origin_no_agrega_nada(self):
        peticion = self.factory.get(RUTA_API)

        respuesta = _middleware(ORIGEN_PROPIO)(peticion)

        self.assertNotIn("Access-Control-Allow-Origin", respuesta)


class OptionsAnonimoTests(TestCase):
    """El preflight se contesta sin llegar a la vista (ni a la base)."""

    def test_options_a_api_responde_200_sin_sesion_y_sin_cuerpo(self):
        with self.assertNumQueries(0):
            respuesta = self.client.options(RUTA_API)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content, b"")
        self.assertNotIn("Access-Control-Allow-Origin", respuesta)

    def test_options_a_una_ruta_de_api_inexistente_tambien_da_200_vacio(self):
        """No sirve para enumerar: contesta igual exista o no la ruta."""
        respuesta = self.client.options("/api/no-existe-nada/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.content, b"")


class ConfiguracionCorsTests(SimpleTestCase):
    """Que el no-op siga siendo no-op en los entornos que el repo describe."""

    def test_el_middleware_esta_montado(self):
        self.assertIn("core.middleware.ApiCorsMiddleware", settings.MIDDLEWARE)

    def test_ningun_entorno_de_ejemplo_trae_origenes_cargados(self):
        """La variable se documenta vacía: cargarla abre `/api/` con credenciales."""
        for nombre in (".env.qa.example", ".env.local.example"):
            with self.subTest(archivo=nombre):
                for linea in (RAIZ / nombre).read_text(encoding="utf-8").splitlines():
                    if linea.strip().startswith(f"{VARIABLE}="):
                        self.assertEqual(linea.strip(), f"{VARIABLE}=")

    def test_la_variable_esta_documentada_en_el_ejemplo_del_entorno_servido(self):
        contenido = (RAIZ / ".env.qa.example").read_text(encoding="utf-8")

        self.assertIn(f"{VARIABLE}=", contenido)
