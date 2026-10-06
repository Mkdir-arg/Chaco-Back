"""SIIS-09 / PERF-09: la red de un request entra en los 60 s de nginx.

«Aprobar» encadena cuatro llamadas externas dentro del mismo clic —token de
SIIS, compatibilidad, alta en la tabla intermedia y el correo de resolución— y
las tres primeras compartían un único par de timeouts de ``(10, 30)``. En el
peor caso la cadena pasaba los 120 s y nginx la cortaba a los 60
(``nginx.conf:97``): el operador veía un 504 **con el alta posiblemente hecha
del otro lado**, que es justo lo que empuja al reintento manual que SIIS-01 y
SIIS-02 tratan de evitar.

Dos frentes acá:

* **El presupuesto.** ``core.integraciones.CADENAS`` declara qué llama cada
  request; el check de deploy suma los timeouts configurados y falla si alguna
  cadena pasa los 55 s. Los tests atan esa declaración al código: lo que el
  cliente pide de verdad al salir a la red es lo que la declaración dice.
* **El cortacircuito.** Un servicio que ya falló tres veces seguidas no se
  vuelve a consultar por un minuto. Con la Gran Base caída, cada paso 1 del link
  público retenía un hilo hasta agotar el timeout para terminar, igual, en
  ``manual``.
"""

from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from core.checks import presupuesto_de_llamadas_externas
from core.integraciones import (
    CADENAS,
    PRESUPUESTO_SEGUNDOS,
    Cortacircuito,
    cadenas_fuera_de_presupuesto,
    costo,
    costo_de_cadena,
)
from programas.services import personas as personas_mod
from programas.services import siis as siis_mod

CREDENCIALES = {
    "SIIS_API_URL": "https://siis.example",
    "SIIS_API_CLIENT_ID": "client",
    "SIIS_API_CLIENT_SECRET": "secret",
    "PERSONAS_API_URL": "https://personas.example",
    "PERSONAS_API_CLIENT_ID": "client",
    "PERSONAS_API_CLIENT_SECRET": "secret",
    "PERSONAS_API_ENTIDAD_UUID": "uuid",
}


def _respuesta(body, status=200):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = body
    respuesta.raise_for_status.return_value = None
    return respuesta


class PresupuestoDeclaradoTests(SimpleTestCase):
    """La aritmética: con los timeouts configurados, ninguna cadena pasa 55 s."""

    def test_ninguna_cadena_declarada_pasa_el_presupuesto(self):
        self.assertEqual(cadenas_fuera_de_presupuesto(), [])

    def test_aprobar_un_caso_es_la_cadena_mas_larga(self):
        """La que motivó la ficha: token + compatibilidad + alta + correo."""
        self.assertEqual(costo_de_cadena("becas · aprobar un caso"), 55)
        self.assertLessEqual(costo_de_cadena("becas · aprobar un caso"), PRESUPUESTO_SEGUNDOS)

    def test_el_check_de_deploy_no_tiene_nada_que_decir(self):
        self.assertEqual(presupuesto_de_llamadas_externas(None), [])

    @override_settings(
        SIIS_API_CONNECT_TIMEOUT=10,
        SIIS_API_TIMEOUT_TOKEN=30,
        SIIS_API_TIMEOUT_CONSULTA=30,
        SIIS_API_TIMEOUT=30,
        EMAIL_TIMEOUT=10,
    )
    def test_con_los_timeouts_de_antes_el_check_corta(self):
        """Los valores que tenía el repo antes de SIIS-09: 130 s para «Aprobar».

        Es el hallazgo escrito como test permanente. Si alguien vuelve a subir
        los timeouts «porque SIIS anda lento», esto es lo que lo frena, y lo
        frena en ``check --deploy``, o sea en el CI y antes del deploy.
        """
        errores = presupuesto_de_llamadas_externas(None)

        self.assertTrue(errores)
        self.assertEqual({error.id for error in errores}, {"core.E003"})
        mensaje = " ".join(error.msg for error in errores)
        self.assertIn("becas · aprobar un caso", mensaje)
        self.assertIn("130 s", mensaje)

    @override_settings(SIIS_API_TIMEOUT=200)
    def test_subir_un_solo_timeout_ya_deja_el_check_en_rojo(self):
        nombres = [nombre for nombre, _ in cadenas_fuera_de_presupuesto()]

        self.assertIn("becas · aprobar un caso", nombres)
        self.assertNotIn("link público · paso 1 (identificar)", nombres)


@override_settings(**CREDENCIALES)
class TimeoutsQueSalenALaRedTests(TestCase):
    """Lo declarado es lo que el cliente pide de verdad.

    Sin esto, ``CADENAS`` sería una planilla al lado del código: alguien cambia
    qué timeout usa una llamada y la suma declarada sigue dando bien.
    """

    def setUp(self):
        cache.clear()

    def test_el_token_la_consulta_y_el_alta_usan_su_propio_timeout(self):
        pedidos = []

        def post(url, **kwargs):
            pedidos.append((url, kwargs["timeout"]))
            if url.endswith("/auth/token"):
                return _respuesta({"access_token": "t", "expires_in": 3600})
            return _respuesta({"resultado": "OK", "apto": True})

        with patch.object(siis_mod.sesion, "post", side_effect=post):
            siis_mod.validar_compatibilidad("30111222", 7)
            siis_mod.cargar_beneficiario({"dni": "30111222"})

        usados = dict((url.rsplit("/", 1)[-1], timeout) for url, timeout in pedidos)
        self.assertEqual(sum(usados["token"]), costo("siis.token"))
        self.assertEqual(sum(usados["compatibilidad"]), costo("siis.consulta"))
        self.assertEqual(sum(usados["tab-intermedia"]), costo("siis.alta"))

    def test_la_cadena_de_aprobar_medida_entra_en_el_presupuesto(self):
        """``test_presupuesto_timeouts``: la suma de lo que sale a la red.

        El token se cuenta una vez aunque lo pidan las dos llamadas: queda en
        caché con el TTL que informa SIIS.
        """
        from django.conf import settings

        pedidos = []

        def post(url, **kwargs):
            pedidos.append(sum(kwargs["timeout"]))
            if url.endswith("/auth/token"):
                return _respuesta({"access_token": "t", "expires_in": 3600})
            return _respuesta({"resultado": "OK", "apto": True})

        with patch.object(siis_mod.sesion, "post", side_effect=post):
            siis_mod.validar_compatibilidad("30111222", 7)
            siis_mod.cargar_beneficiario({"dni": "30111222"})

        self.assertEqual(len(pedidos), 3, "el token se pidió más de una vez")
        self.assertLessEqual(sum(pedidos) + settings.EMAIL_TIMEOUT, PRESUPUESTO_SEGUNDOS)

    def test_la_consulta_a_personas_usa_el_timeout_de_consulta(self):
        pedidos = []

        def get(url, **kwargs):
            pedidos.append(sum(kwargs["timeout"]))
            return _respuesta({"data": {"nombres": "Ana", "apellido": "Pérez", "dni": "30111222"}})

        with patch.object(personas_mod.sesion, "post", return_value=_respuesta({"data": {"token": "t"}})):
            with patch.object(personas_mod.sesion, "get", side_effect=get):
                personas_mod.consultar_persona("30111222", "F")

        self.assertEqual(pedidos, [costo("personas.consulta")])
        self.assertLessEqual(costo_de_cadena("link público · paso 1 (identificar)"), PRESUPUESTO_SEGUNDOS)

    def test_las_cadenas_declaradas_nombran_servicios_que_existen(self):
        """Una cadena con un nombre de llamada mal escrito reventaría recién en
        el deploy: el check la recorre entera."""
        for nombre in CADENAS:
            self.assertGreater(costo_de_cadena(nombre), 0, nombre)


class CortacircuitoTests(SimpleTestCase):
    """La pieza sola: tres fallas seguidas abren, una respuesta cierra."""

    def setUp(self):
        cache.clear()

    def test_tres_fallas_seguidas_lo_abren(self):
        corte = Cortacircuito("prueba")

        self.assertFalse(corte.abierto())
        corte.registrar_falla()
        corte.registrar_falla()
        self.assertFalse(corte.abierto(), "dos fallas no alcanzan")
        corte.registrar_falla()
        self.assertTrue(corte.abierto())

    def test_una_respuesta_en_el_medio_borra_lo_acumulado(self):
        corte = Cortacircuito("prueba")
        corte.registrar_falla()
        corte.registrar_falla()

        corte.registrar_exito()
        corte.registrar_falla()

        self.assertFalse(corte.abierto(), "las fallas tienen que ser seguidas")

    def test_el_exito_cierra_uno_abierto(self):
        corte = Cortacircuito("prueba")
        for _ in range(3):
            corte.registrar_falla()

        corte.registrar_exito()

        self.assertFalse(corte.abierto())

    def test_dos_servicios_no_se_pisan(self):
        uno, otro = Cortacircuito("uno"), Cortacircuito("otro")
        for _ in range(3):
            uno.registrar_falla()

        self.assertTrue(uno.abierto())
        self.assertFalse(otro.abierto())


@override_settings(**CREDENCIALES)
class GranBaseCaidaTests(TestCase):
    """SIIS-09 punto 4: el tope de ``identificar`` desde el link público."""

    def setUp(self):
        cache.clear()

    def test_la_cuarta_consulta_no_toca_la_red(self):
        """El de la ficha: mock que falla 3 veces → la cuarta no sale a la red."""
        import requests

        with patch.object(personas_mod.sesion, "post", return_value=_respuesta({"data": {"token": "t"}})):
            with patch.object(personas_mod.sesion, "get", side_effect=requests.ReadTimeout()) as consulta:
                for _ in range(3):
                    self.assertFalse(personas_mod.consultar_persona("30111222", "F")["success"])
                self.assertEqual(consulta.call_count, 3)

                cuarta = personas_mod.consultar_persona("30111222", "F")

                self.assertEqual(consulta.call_count, 3, "la cuarta consulta salió igual a la red")
        self.assertTrue(cuarta["cortado"])

    def test_identificar_cae_a_manual_con_el_cortacircuito_abierto(self):
        """El resultado es el mismo de siempre, sin pagar el timeout."""
        from programas.services.identidad import ORIGEN_MANUAL, identificar

        for _ in range(3):
            personas_mod.cortacircuito.registrar_falla()

        with patch.object(personas_mod.sesion, "get") as consulta:
            resultado = identificar(None, "30111222", "F", fila=None)

        consulta.assert_not_called()
        self.assertEqual(resultado["origen"], ORIGEN_MANUAL)
        self.assertFalse(resultado["validado"])
        self.assertTrue(resultado["error"])

    def test_un_dni_que_no_figura_no_cuenta_como_falla(self):
        """Un 404 es una respuesta: el servicio está en pie."""
        with patch.object(personas_mod.sesion, "post", return_value=_respuesta({"data": {"token": "t"}})):
            with patch.object(personas_mod.sesion, "get", return_value=_respuesta({}, status=404)) as consulta:
                for _ in range(4):
                    personas_mod.consultar_persona("30111222", "F")

                self.assertEqual(consulta.call_count, 4)


@override_settings(**CREDENCIALES)
class SiisCaidoTests(TestCase):
    """Lo mismo para la consulta de compatibilidad. El alta **no** pasa por acá."""

    def setUp(self):
        cache.clear()

    def test_la_cuarta_validacion_de_compatibilidad_no_toca_la_red(self):
        import requests

        cache.set(siis_mod.TOKEN_CACHE_KEY, "t", 60)
        with patch.object(siis_mod.sesion, "post", side_effect=requests.ReadTimeout()) as consulta:
            for _ in range(3):
                siis_mod.validar_compatibilidad("30111222", 7)
            self.assertEqual(consulta.call_count, 3)

            cuarta = siis_mod.validar_compatibilidad("30111222", 7)

            self.assertEqual(consulta.call_count, 3)
        self.assertFalse(cuarta["success"])
        self.assertTrue(cuarta["cortado"])

    def test_el_alta_sale_igual_con_el_cortacircuito_de_consultas_abierto(self):
        """El alta es irreversible y se decide caso por caso: no se saltea.

        Lo que no se puede hacer es dejar de intentar el alta por un corte que
        midió **otra** llamada. El INCIERTO de SIIS-02 ya cubre el caso de que
        SIIS no conteste.
        """
        cache.set(siis_mod.TOKEN_CACHE_KEY, "t", 60)
        for _ in range(3):
            siis_mod.cortacircuito_consultas.registrar_falla()

        with patch.object(siis_mod.sesion, "post", return_value=_respuesta({"ids_generados": [9]}, status=201)) as alta:
            resultado = siis_mod.cargar_beneficiario({"dni": "30111222"})

        alta.assert_called_once()
        self.assertTrue(resultado["success"])
