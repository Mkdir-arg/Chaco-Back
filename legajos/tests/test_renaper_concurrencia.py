"""Los tres seguimientos que dejó la revisión del PR 7a (#623) sobre el token de RENAPER.

Los tres salen del mismo lugar —la coordinación del login que ese PR introdujo— y
los tres se miden sin abrir un socket (el runner de la suite corta toda salida
HTTP, localhost incluido):

a. **El presupuesto.** ``core.integraciones.CADENAS`` declaraba ``login +
   consulta`` = 30 s para «consultar RENAPER», y el comentario de al lado
   prometía 2 s de espera nombrando un ``ESPERA_LOGIN_SEGUNDOS`` que ya no
   existe. Con ``VUELTAS_TOKEN`` esperas de ``connect + read + margen`` sin un
   límite compartido, el peor caso real era 3 × 16 + 15 = **63 s** —por encima de
   los 60 de nginx— y ``core.E003`` no lo veía, porque solo sabe sumar lo
   declarado.
b. **El ganador de la rotación.** Leía ``self.token`` fuera del candado apenas
   volvía de ``login()``: si un 401 de otro hilo lo descartaba en esa ventana
   —que es justo lo que pasa en una rotación— levantaba «el login terminó sin
   dejar token» con un token bueno recién traído, sin usar sus vueltas
   restantes, mientras los que esperaban sí reintentaban.
c. **``descartar_token(usado=)`` entre procesos.** La guarda comparaba contra
   ``self.token``, que es del worker. Si el que rotó fue **otro** worker, el 401
   viejo pasaba la guarda y borraba de la caché compartida el token que ese otro
   acababa de publicar: la rotación volvía a ser una ronda de logins, ahora en
   todos los procesos.
"""

import datetime
import threading
import time
from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings

import legajos.services.consulta_renaper as consulta_renaper
from core.checks import presupuesto_de_llamadas_externas
from core.integraciones import CADENAS, PRESUPUESTO_SEGUNDOS, costo, costo_de_cadena
from legajos.tests.test_renaper_cliente import AJUSTES, PERSONA, _BaseRenaperTest, _respuesta


@override_settings(**AJUSTES)
class PresupuestoDeLaCadenaTests(_BaseRenaperTest):
    """(a) La cadena declarada tiene que ser la cuenta real, no dos de sus tres términos."""

    def test_la_cadena_declara_la_espera_del_token(self):
        self.assertEqual(
            CADENAS["legajos · consultar RENAPER"],
            ("renaper.espera_token", "renaper.login", "renaper.consulta"),
        )

    def test_la_cuenta_declarada_es_la_del_comentario(self):
        """16 (espera) + 15 (login propio) + 15 (consulta) = 46, bajo 55 y bajo 60."""
        self.assertEqual(costo_de_cadena("legajos · consultar RENAPER"), 46)
        self.assertLessEqual(costo_de_cadena("legajos · consultar RENAPER"), PRESUPUESTO_SEGUNDOS)

    def test_la_espera_declarada_es_la_que_el_cliente_usa(self):
        """La declaración no puede quedar al lado del código: es el mismo número."""
        self.assertEqual(consulta_renaper.APIClient().espera_login, costo("renaper.espera_token"))

    @override_settings(RENAPER_TIMEOUT=20)
    def test_subir_el_timeout_de_renaper_deja_el_check_en_rojo(self):
        """Con 5 + 20 la cuenta da 76: el check de deploy tiene que frenarlo."""
        errores = presupuesto_de_llamadas_externas(None)

        self.assertEqual({error.id for error in errores}, {"core.E003"})
        self.assertIn("legajos · consultar RENAPER", " ".join(error.msg for error in errores))

    def test_el_limite_se_comparte_entre_el_token_y_el_reintento_por_401(self):
        """El 401 no puede abrir una segunda ronda de espera + login.

        Sin el límite compartido, un request que ya gastó su presupuesto volvía a
        renovar el token y a consultar: otros 30 s encima de los 46 declarados.
        """
        cliente = consulta_renaper.APIClient()
        cliente.espera_login = 0.05
        logins, consultas = [], []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                logins.append(url)
                return _respuesta(200, {"token": f"tok{len(logins)}", "expiration": "2099-01-01T00:00:00Z"})
            consultas.append(url)
            time.sleep(0.08)  # la consulta sola ya se pasa del límite
            return _respuesta(401, {"message": "token vencido"})

        with patch.object(cliente.session, "post", side_effect=post):
            resultado = cliente.consultar_ciudadano("30111222", "F")

        self.assertEqual(len(consultas), 1, "reintentó con el presupuesto agotado")
        self.assertEqual(resultado["status_code"], 401)

    def test_con_presupuesto_el_reintento_por_401_sigue_corriendo(self):
        """El límite acota el reintento, no lo apaga: SIIS-14 sigue en pie."""
        cliente = consulta_renaper.APIClient()
        consultas = []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                return _respuesta(200, {"token": "tok", "expiration": "2099-01-01T00:00:00Z"})
            consultas.append(url)
            if len(consultas) == 1:
                return _respuesta(401, {"message": "token vencido"})
            return _respuesta(200, PERSONA)

        with patch.object(cliente.session, "post", side_effect=post):
            resultado = cliente.consultar_ciudadano("30111222", "F")

        self.assertEqual(len(consultas), 2)
        self.assertTrue(resultado["success"], resultado.get("error"))


@override_settings(**AJUSTES)
class GanadorDeLaRotacionTests(_BaseRenaperTest):
    """(b) El que gana la carrera del login tiene las mismas vueltas que los demás."""

    def test_el_ganador_no_cae_si_le_descartan_el_token_recien_traido(self):
        """El hallazgo, con la ventana abierta a mano para no depender del scheduler."""
        cliente = consulta_renaper.APIClient()
        logins = []

        def login_falso():
            logins.append(1)
            token = f"tok{len(logins)}"
            cliente.token = token
            cliente.token_expiration = datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)
            if len(logins) == 1:
                # Otro hilo se come un 401 con este token y lo descarta justo
                # entre que se publica y que el ganador lo lee.
                cliente.descartar_token(usado=token)
            return token

        with patch.object(cliente, "login", side_effect=login_falso):
            token = cliente.get_token()

        self.assertEqual(token, "tok2", "el ganador no usó sus vueltas restantes")
        self.assertEqual(len(logins), 2)

    def test_un_200_sin_token_sigue_cortando_en_la_primera(self):
        """Lo que no se reintenta: el proveedor contesta lo mismo y cuesta un login entero."""
        cliente = consulta_renaper.APIClient()

        with patch.object(cliente, "login", return_value=None) as login:
            with self.assertRaises(Exception) as capturado:  # noqa: B017
                cliente.get_token()

        self.assertEqual(login.call_count, 1)
        self.assertIn("sin dejar token", str(capturado.exception))

    def test_el_ganador_concurrente_termina_consultando(self):
        """Lo mismo con hilos de verdad y un servicio que rota el primer token."""
        cliente = consulta_renaper.APIClient()
        candado = threading.Lock()
        logins, consultas, resultados = [], [], []
        muertos = set()

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                with candado:
                    logins.append(url)
                    numero = len(logins)
                    if numero == 1:
                        muertos.add("tok1")
                return _respuesta(200, {"token": f"tok{numero}", "expiration": "2099-01-01T00:00:00Z"})
            usado = (kwargs.get("headers") or {}).get("Authorization", "").split(" ", 1)[-1]
            with candado:
                consultas.append(usado)
                vencido = usado in muertos
            return _respuesta(401, {"message": "no"}) if vencido else _respuesta(200, PERSONA)

        barrera = threading.Barrier(4)

        def trabajo():
            barrera.wait()
            resultados.append(cliente.consultar_ciudadano("30111222", "F"))

        with patch.object(cliente.session, "post", side_effect=post):
            equipo = [threading.Thread(target=trabajo) for _ in range(4)]
            for hilo in equipo:
                hilo.start()
            for hilo in equipo:
                hilo.join(10)

        self.assertEqual(len(resultados), 4)
        for resultado in resultados:
            self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertGreaterEqual(len(consultas), 4, "alguno falló sin consultar")


@override_settings(**AJUSTES)
class TokenCompartidoEntreProcesosTests(_BaseRenaperTest):
    """(c) `descartar_token(usado=)` mira la caché compartida, no el estado del worker."""

    def _publicar(self, token):
        cache.set(
            consulta_renaper.TOKEN_CACHE_KEY,
            {"token": token, "expiration": "2099-01-01T00:00:00Z"},
            60,
        )

    def _con_token(self, token):
        cliente = consulta_renaper.APIClient()
        cliente.token = token
        cliente.token_expiration = datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)
        return cliente

    def test_un_401_viejo_no_le_tira_el_token_nuevo_a_otro_worker(self):
        """El hallazgo: dos clientes, una sola caché."""
        worker_a = self._con_token("tok1")
        # El worker B ya rotó y publicó el token nuevo en la caché compartida.
        self._publicar("tok2")

        worker_a.descartar_token(usado="tok1")

        self.assertEqual(cache.get(consulta_renaper.TOKEN_CACHE_KEY)["token"], "tok2")
        # Y el A, que tenía el viejo, lo suelta y toma el de la caché.
        self.assertIsNone(worker_a.token)
        self.assertEqual(worker_a._token_vigente(), "tok2")

    def test_el_401_del_token_que_sigue_publicado_si_lo_borra(self):
        worker = self._con_token("tok1")
        self._publicar("tok1")

        worker.descartar_token(usado="tok1")

        self.assertIsNone(cache.get(consulta_renaper.TOKEN_CACHE_KEY))

    def test_sin_usado_se_borra_igual(self):
        """`descartar_token()` a secas sigue siendo «olvidate de todo»."""
        self._publicar("tok1")

        consulta_renaper.APIClient().descartar_token()

        self.assertIsNone(cache.get(consulta_renaper.TOKEN_CACHE_KEY))

    def test_una_entrada_rota_en_la_cache_se_descarta(self):
        """Lo que no es un dict no se puede comparar: es basura y se tira."""
        cache.set(consulta_renaper.TOKEN_CACHE_KEY, "un texto suelto", 60)

        consulta_renaper.APIClient().descartar_token(usado="tok1")

        self.assertIsNone(cache.get(consulta_renaper.TOKEN_CACHE_KEY))

    def test_dos_clientes_comparten_el_token_de_la_cache(self):
        """La razón de ser de la caché: el segundo worker no vuelve a loguearse."""
        worker_a, worker_b = consulta_renaper.APIClient(), consulta_renaper.APIClient()
        logins = []

        def post(url, **kwargs):
            if url.endswith("/auth/login"):
                logins.append(url)
                return _respuesta(200, {"token": "tok1", "expiration": "2099-01-01T00:00:00Z"})
            return _respuesta(200, PERSONA)

        with patch.object(worker_a.session, "post", side_effect=post):
            worker_a.consultar_ciudadano("30111222", "F")
        with patch.object(worker_b.session, "post", side_effect=post):
            worker_b.consultar_ciudadano("30111223", "F")

        self.assertEqual(len(logins), 1, "el segundo worker volvió a loguearse")
