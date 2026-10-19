"""El token de SIIS se pide fuera del request (pedido del proveedor, 19/10).

El login real corre en un hilo con ``SIIS_API_TIMEOUT_LOGIN``; el request solo
espera. Los tests sustituyen el lanzador por una ejecución sincrónica (o diferida)
y el reloj por uno falso, así que ninguno duerme de verdad.
"""

import logging
from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from core.checks import presupuesto_de_llamadas_externas
from programas.services import siis
from programas.services.siis import (
    LOGIN_LOCK_KEY,
    LOGIN_PAUSA_KEY,
    TOKEN_CACHE_KEY,
    TOKEN_VENCE_KEY,
    SiisAPIClient,
    _SiisConfigurationError,
)


class RelojFalso:
    """``_reloj``/``_dormir`` sin dormir: cada espera avanza el reloj. Corta si se pasa de largo."""

    def __init__(self, tope=120):
        self.t = 1000.0
        self.dormidas = 0
        self.tope = tope

    def reloj(self):
        return self.t

    def dormir(self, segundos):
        self.dormidas += 1
        self.t += segundos
        if self.t > 1000.0 + self.tope:
            raise AssertionError("la espera no tiene límite: el request siguió esperando")


def _respuesta_login(token="tok-1", expires_in=3600):
    r = Mock(status_code=200)
    r.raise_for_status.return_value = None
    r.json.return_value = {"access_token": token, "expires_in": expires_in}
    return r


@override_settings(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=5,
    SIIS_API_TIMEOUT_TOKEN=5,
    SIIS_API_TIMEOUT_LOGIN=15,
)
class TokenFueraDelRequestTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.reloj = RelojFalso()
        for destino, nuevo in (
            ("programas.services.siis._reloj", self.reloj.reloj),
            ("programas.services.siis._dormir", self.reloj.dormir),
        ):
            p = patch(destino, nuevo)
            p.start()
            self.addCleanup(p.stop)
        self.pendientes = []

    def _lanzador_sincronico(self):
        p = patch.object(siis, "lanzar_en_segundo_plano", side_effect=lambda f: f())
        p.start()
        self.addCleanup(p.stop)

    def _lanzador_diferido(self):
        """El hilo «arranca» pero no avanza hasta que el test lo suelta."""
        p = patch.object(siis, "lanzar_en_segundo_plano", side_effect=self.pendientes.append)
        p.start()
        self.addCleanup(p.stop)

    def _post(self, **kwargs):
        p = patch("programas.services.siis.sesion.post", **kwargs)
        mock = p.start()
        self.addCleanup(p.stop)
        return mock

    def test_cache_fria_y_login_rapido_devuelve_el_token_con_un_solo_post(self):
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login())

        self.assertEqual(SiisAPIClient()._token(), "tok-1")

        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 15))
        self.assertIsNone(cache.get(LOGIN_LOCK_KEY), "el candado se libera al terminar")
        self.assertEqual(SiisAPIClient()._token(), "tok-1")
        self.assertEqual(post.call_count, 1, "el segundo pedido sale de la caché")

    def test_login_mas_lento_que_la_espera_falla_a_tiempo_y_deja_el_token_para_el_siguiente(self):
        self._lanzador_diferido()
        post = self._post(return_value=_respuesta_login())

        with self.assertRaises(requests.ReadTimeout):
            SiisAPIClient()._token()
        # El límite es connect + token = 10 s de reloj; no se pasó de ahí.
        self.assertLessEqual(self.reloj.t - 1000.0, 10 + siis.INTERVALO_ESPERA_TOKEN)
        self.assertEqual(post.call_count, 0)

        # El hilo termina después de que el request ya se dio por vencido.
        self.assertEqual(len(self.pendientes), 1)
        self.pendientes.pop()()
        self.assertEqual(post.call_count, 1)

        self.assertEqual(SiisAPIClient()._token(), "tok-1")
        self.assertEqual(post.call_count, 1, "no vuelve a pagar el login")

    def test_token_dentro_de_la_ventana_de_renovacion_se_devuelve_y_dispara_una_renovacion(self):
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login("tok-nuevo"))
        cache.set(TOKEN_CACHE_KEY, "tok-viejo", 3000)
        cache.set(TOKEN_VENCE_KEY, siis._ahora() + 120, 3000)  # vence en 2 min < 10

        # El que llama recibe el actual sin esperar...
        self.assertEqual(SiisAPIClient()._token(), "tok-viejo")
        # ...y la renovación corrió (acá sincrónica) y dejó el nuevo.
        self.assertEqual(post.call_count, 1)
        self.assertEqual(cache.get(TOKEN_CACHE_KEY), "tok-nuevo")
        self.assertEqual(self.reloj.dormidas, 0)

    def test_token_lejos_de_vencer_no_renueva(self):
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login())
        cache.set(TOKEN_CACHE_KEY, "tok", 3000)
        cache.set(TOKEN_VENCE_KEY, siis._ahora() + 3000, 3000)

        self.assertEqual(SiisAPIClient()._token(), "tok")
        self.assertEqual(post.call_count, 0)

    def test_token_viejo_sin_clave_de_vencimiento_se_usa_sin_renovar(self):
        """Rolling deploy: un pod viejo guardó solo el string."""
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login())
        cache.set(TOKEN_CACHE_KEY, "tok-de-un-pod-viejo", 60)

        self.assertEqual(SiisAPIClient()._token(), "tok-de-un-pod-viejo")
        self.assertEqual(post.call_count, 0)

    def test_candado_tomado_por_otro_no_lanza_un_segundo_login_y_usa_el_token_cuando_aparece(self):
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login())
        cache.set(LOGIN_LOCK_KEY, "otro-pod", 30)

        def aparece_el_token(segundos):
            self.reloj.t += segundos
            cache.set(TOKEN_CACHE_KEY, "tok-del-otro-pod", 60)

        with patch("programas.services.siis._dormir", aparece_el_token):
            self.assertEqual(SiisAPIClient()._token(), "tok-del-otro-pod")
        self.assertEqual(post.call_count, 0)

    def test_candado_tomado_y_sin_token_vence_por_la_espera(self):
        self._lanzador_sincronico()
        post = self._post(return_value=_respuesta_login())
        cache.set(LOGIN_LOCK_KEY, "otro-pod", 30)

        with self.assertRaises(requests.ReadTimeout):
            SiisAPIClient()._token()
        self.assertEqual(post.call_count, 0)

    def test_login_fallido_deja_pausa_y_la_siguiente_llamada_falla_rapido_sin_post(self):
        self._lanzador_sincronico()
        post = self._post(side_effect=requests.ReadTimeout("lento"))

        with self.assertRaises(requests.ConnectionError):
            SiisAPIClient()._token()
        self.assertEqual(post.call_count, 1)
        self.assertTrue(cache.get(LOGIN_PAUSA_KEY))
        self.assertIsNone(cache.get(LOGIN_LOCK_KEY), "el candado se libera aunque falle")

        dormidas = self.reloj.dormidas
        with self.assertRaises(requests.ConnectionError):
            SiisAPIClient()._token()
        self.assertEqual(post.call_count, 1, "en pausa no se vuelve a pegar")
        self.assertEqual(self.reloj.dormidas, dormidas, "y no espera")

    def test_cuerpo_sin_access_token_es_error_de_configuracion_y_tambien_pausa(self):
        self._lanzador_sincronico()
        malo = Mock(status_code=200)
        malo.raise_for_status.return_value = None
        malo.json.return_value = {"otra": "cosa"}
        self._post(return_value=malo)

        with self.assertLogs("programas.services.siis", level="ERROR"):
            with self.assertRaises(_SiisConfigurationError) as ctx:
                SiisAPIClient()._token()
        self.assertFalse(ctx.exception.falta_configuracion)

    def test_configuracion_incompleta_falla_enseguida_sin_lanzar_nada(self):
        parche = patch.object(siis, "lanzar_en_segundo_plano")
        lanzar = parche.start()
        self.addCleanup(parche.stop)
        with override_settings(SIIS_API_CLIENT_SECRET=""):
            with self.assertRaises(_SiisConfigurationError) as ctx:
                SiisAPIClient()._token()
        self.assertTrue(ctx.exception.falta_configuracion)
        lanzar.assert_not_called()

    def test_expires_in_chico_avisa_sin_reinterpretarlo(self):
        self._lanzador_sincronico()
        self._post(return_value=_respuesta_login(expires_in=60))

        with self.assertLogs("programas.services.siis", level=logging.WARNING) as logs:
            SiisAPIClient()._token()
        self.assertTrue(any("expires_in=60" in linea for linea in logs.output))
        self.assertEqual(cache.get(TOKEN_CACHE_KEY), "tok-1", "se guarda igual, con el mínimo de 60 s")

    def test_login_sincronico_del_diagnostico_usa_el_timeout_de_login_y_guarda(self):
        post = self._post(return_value=_respuesta_login("tok-diag"))

        self.assertEqual(SiisAPIClient()._login(), "tok-diag")
        self.assertEqual(post.call_args.kwargs["timeout"], (5, 15))
        self.assertEqual(cache.get(TOKEN_CACHE_KEY), "tok-diag")

    def test_validar_compatibilidad_con_login_lento_devuelve_error_sin_pasarse_del_limite(self):
        self._lanzador_diferido()
        post = self._post(return_value=_respuesta_login())

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 59, "2005-08-15")

        self.assertFalse(resultado["success"])
        self.assertLessEqual(self.reloj.t - 1000.0, 10 + siis.INTERVALO_ESPERA_TOKEN)
        self.assertEqual(post.call_count, 0)

    def test_alta_con_login_lento_no_sale_y_queda_no_enviada(self):
        self._lanzador_diferido()
        self._post(return_value=_respuesta_login())

        with patch("programas.services.siis.escritura_siis_bloqueada", return_value=False):
            r = SiisAPIClient().cargar_beneficiario({"dni": 1})
        self.assertEqual(r["resultado"], "NO_ENVIADO")

    def test_el_presupuesto_de_llamadas_externas_sigue_sin_errores_con_los_defaults(self):
        self.assertEqual(presupuesto_de_llamadas_externas(None), [])
