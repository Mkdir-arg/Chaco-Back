from unittest.mock import Mock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from programas.services.siis import TOKEN_CACHE_KEY, SiisAPIClient, SiisCatalogError, motivos_de_rechazo


@override_settings(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)
class SiisClientTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    @patch("programas.services.siis.requests.post")
    def test_compatible_obtiene_token_y_envia_el_contrato_vigente(self, post):
        token = Mock(status_code=200)
        token.json.return_value = {"access_token": "abc", "expires_in": 3600}
        token.raise_for_status.return_value = None
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "resultado": "OK",
            "apto": True,
            "id_consulta": "9b04df54-bde0-4aaa-85e7-99234e9e21aa",
        }
        post.side_effect = [token, respuesta]

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 59, "2005-08-15")

        self.assertTrue(resultado["success"])
        self.assertTrue(resultado["compatible"])
        self.assertEqual(
            post.call_args_list[1].kwargs["json"],
            {"dni": "21884116", "id_programa": 59, "fecha_nacimiento": "2005-08-15"},
        )

    @patch("programas.services.siis.requests.post")
    def test_sin_fecha_de_nacimiento_no_manda_el_campo(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"resultado": "OK", "apto": True}
        post.return_value = respuesta

        SiisAPIClient().validar_compatibilidad("21884116", 59)

        self.assertEqual(post.call_args.kwargs["json"], {"dni": "21884116", "id_programa": 59})

    @patch("programas.services.siis.requests.post")
    def test_rechazo_llega_en_http_200_y_no_es_error_tecnico(self, post):
        """SIIS resuelve el veredicto siempre con 200: el rechazo viaja en ``apto``."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "resultado": "RECHAZADO",
            "apto": False,
            "validaciones": {
                "padron_siis": "REGISTRADO",
                "empleo_publico": "INCOMPATIBLE_PLANTA",
                "duplicidad_becas": "SIN_INCOMPATIBILIDAD",
            },
        }
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 59)

        self.assertTrue(resultado["success"])
        self.assertFalse(resultado["compatible"])

    @patch("programas.services.siis.requests.post")
    def test_error_de_contrato_se_informa_como_tecnico(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {"error": "VALIDACION_ENTRADA"}
        post.return_value = respuesta

        resultado = SiisAPIClient().validar_compatibilidad("21884116", 999)

        self.assertFalse(resultado["success"])
        self.assertEqual(resultado["error"], "VALIDACION_ENTRADA")

    @patch("programas.services.siis.requests.get")
    def test_lista_programas_conserva_el_detalle_informativo_del_contrato(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "programas": [
                {
                    "id": 38,
                    "nombre": "Programa A",
                    "descripcion": "Fortalecimiento comunitario",
                    "jurisdiccion_id": 3,
                    "estado": "ACTIVO",
                    "controla_empleo_publico": True,
                    "controla_horas_docentes": False,
                    "edad_minima": 18,
                }
            ]
        }
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        programas = SiisAPIClient().listar_programas()

        self.assertEqual(len(programas), 1)
        self.assertEqual(programas[0]["id"], 38)
        self.assertEqual(programas[0]["nombre"], "Programa A")
        self.assertEqual(programas[0]["estado"], "ACTIVO")
        self.assertEqual(programas[0]["edad_minima"], 18)
        self.assertTrue(programas[0]["controla_empleo_publico"])
        self.assertIn("estado=ACTIVO", get.call_args.args[0])

    @patch("programas.services.siis.requests.get")
    def test_lista_programas_descarta_inactivos_que_llegan_igual(self, get):
        """El filtro se le pide a SIIS y se reaplica: un inactivo no llega al select."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "programas": [
                {"id": 38, "nombre": "Vigente", "estado": "ACTIVO"},
                {"id": 39, "nombre": "Dado de baja", "estado": "INACTIVO"},
            ]
        }
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        self.assertEqual([p["id"] for p in SiisAPIClient().listar_programas()], [38])

    @patch("programas.services.siis.requests.get")
    def test_programa_sin_estado_se_asume_activo(self, get):
        """Si ECOM dejara de informar ``estado``, mejor catálogo completo que vacío."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"programas": [{"id": 38, "nombre": "Sin estado"}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        programas = SiisAPIClient().listar_programas()

        self.assertEqual([p["id"] for p in programas], [38])
        self.assertEqual(programas[0]["estado"], "ACTIVO")

    @patch("programas.services.siis.requests.get")
    def test_catalogo_completo_pide_todos_y_conserva_los_inactivos(self, get):
        """Detectar una baja necesita ``estado=TODOS``: con ACTIVO el programa desaparece."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {
            "programas": [
                {"id": 38, "nombre": "Vigente", "estado": "ACTIVO"},
                {"id": 39, "nombre": "Dado de baja", "estado": "INACTIVO"},
            ]
        }
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        programas = SiisAPIClient().listar_programas_todos()

        self.assertEqual({p["id"]: p["estado"] for p in programas}, {38: "ACTIVO", 39: "INACTIVO"})
        self.assertIn("estado=TODOS", get.call_args.args[0])

    def test_motivos_de_rechazo_solo_traduce_las_banderas_incumplidas(self):
        motivos = motivos_de_rechazo(
            {
                "padron_siis": "REGISTRADO",
                "vigencia_programa": "VIGENTE",
                "edad_minima": "EDAD_INSUFICIENTE",
                "empleo_publico": "INCOMPATIBLE_PLANTA",
                "horas_docentes": "SIN_INCOMPATIBILIDAD",
            }
        )

        self.assertEqual([bandera for bandera, _ in motivos], ["edad_minima", "empleo_publico"])
        self.assertIn("edad mínima", motivos[0][1])

    def test_motivos_de_rechazo_tolera_una_respuesta_sin_validaciones(self):
        self.assertEqual(motivos_de_rechazo(None), [])

    @patch("programas.services.siis.requests.get", side_effect=requests.Timeout)
    def test_timeout_del_catalogo_muestra_un_mensaje_util(self, _get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        with self.assertRaisesMessage(SiisCatalogError, "tardó demasiado en responder"):
            SiisAPIClient().listar_programas()

    # ------------------------------------------------------------------
    # Alta de beneficiarios (tabla intermedia) y catálogos maestros
    # ------------------------------------------------------------------
    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_201_devuelve_el_id(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=201)
        respuesta.json.return_value = {
            "status": "OK",
            "total_insertados": 1,
            "ids_generados": [26],
            "registros": [{"id": 26}],
        }
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({"dni": 1, "tdoc": 1})

        self.assertTrue(r["success"])
        self.assertEqual(r["siis_id"], 26)
        self.assertTrue(post.call_args.args[0].endswith("/api/v1/auth/tab-intermedia"))
        self.assertEqual(post.call_args.kwargs["json"], {"dni": 1, "tdoc": 1})

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_201_sin_ids_generados_lee_registros(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=201)
        respuesta.json.return_value = {"registros": [{"id": 31, "dni": 1}]}
        post.return_value = respuesta

        self.assertEqual(SiisAPIClient().cargar_beneficiario({})["siis_id"], 31)

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_400_trae_detalles_por_campo(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=400)
        respuesta.json.return_value = {
            "error": "DATOS_INVALIDOS",
            "mensaje": "Uno o más campos no superaron las validaciones.",
            "detalles": {"barrio_actual": ["mínimo 4 caracteres"]},
        }
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({})

        self.assertFalse(r["success"])
        self.assertEqual(r["codigo"], "DATOS_INVALIDOS")
        self.assertFalse(r["reintentable"])
        self.assertEqual(r["detalles"], {"barrio_actual": ["mínimo 4 caracteres"]})

    @patch.object(SiisAPIClient, "_token", return_value="abc")
    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_401_invalida_el_token_y_reintenta_una_vez(self, post, _token):
        """SIIS-02: el 401 garantiza que el alta no se procesó, así que se reintenta
        **adentro**, una sola vez, con un token nuevo. Si vuelve a fallar, queda
        NO_ENVIADO (reintentable), no incierto."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=401)
        respuesta.json.return_value = {"error": "UNAUTHORIZED"}
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({})

        self.assertEqual(post.call_count, 2)
        self.assertEqual(r["codigo"], "UNAUTHORIZED")
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertTrue(r["reintentable"])
        self.assertIsNone(cache.get(TOKEN_CACHE_KEY))

    @patch("programas.services.siis.requests.post")
    def test_cargar_beneficiario_503_es_reintentable(self, post):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=503)
        respuesta.json.return_value = {"error": "ERROR_BD_LEGACY"}
        post.return_value = respuesta

        r = SiisAPIClient().cargar_beneficiario({})

        self.assertEqual(r["codigo"], "ERROR_BD_LEGACY")
        self.assertTrue(r["reintentable"])

    @patch("programas.services.siis.requests.post", side_effect=requests.ConnectTimeout())
    def test_cargar_beneficiario_connect_timeout_no_salio_y_se_reintenta(self, _post):
        """La conexión no se abrió: el alta no salió (SIIS-02)."""
        cache.set(TOKEN_CACHE_KEY, "abc", 60)

        r = SiisAPIClient().cargar_beneficiario({})

        self.assertFalse(r["success"])
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertEqual(r["codigo"], "ERROR_TECNICO")
        self.assertTrue(r["reintentable"])

    @patch("programas.services.siis.requests.get")
    def test_catalogo_normaliza_y_cachea(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"data": [{"id": 22, "nombre": "Chaco"}, {"id": "x", "nombre": "Mal"}, {"id": 2}]}
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        items = SiisAPIClient().catalogo("provincias")
        SiisAPIClient().catalogo("provincias")

        self.assertEqual(items, [{"id": 22, "nombre": "Chaco"}])
        self.assertEqual(get.call_count, 1)
        self.assertTrue(get.call_args.args[0].endswith("/api/v1/auth/catalogos/provincias"))

    @patch("programas.services.siis.requests.get")
    def test_funciones_programa_pide_por_id_programa(self, get):
        cache.set(TOKEN_CACHE_KEY, "abc", 60)
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = [{"id": 4, "nombre": "Nivel Operativo", "id_programa": 79}]
        respuesta.raise_for_status.return_value = None
        get.return_value = respuesta

        items = SiisAPIClient().funciones_programa(79)

        self.assertEqual(items[0]["id"], 4)
        self.assertIn("id_programa=79", get.call_args.args[0])

    def test_catalogo_nombre_desconocido(self):
        with self.assertRaises(ValueError):
            SiisAPIClient().catalogo("otra-cosa")


@override_settings(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=1,
    SIIS_API_TIMEOUT=2,
)
class ResultadoDelAltaTests(SimpleTestCase):
    """SIIS-02 · La tabla de D-S02, entera: qué resultado deja cada desenlace.

    La pregunta que contesta ``resultado`` es una sola: **¿puede haber quedado un
    alta del otro lado?** De eso depende si el caso se libera para reintentar
    (``NO_ENVIADO``) o queda tomado hasta conciliarlo (``INCIERTO``). Un alta en
    SIIS no se puede dar de baja desde acá, así que equivocarse hacia
    «reintentable» es irreversible.
    """

    def setUp(self):
        cache.clear()

    def _resultado(self, **kwargs):
        with patch.object(SiisAPIClient, "_token", return_value="abc"):
            with patch("programas.services.siis.requests.post", **kwargs):
                return SiisAPIClient().cargar_beneficiario({"dni": 1})

    def _respuesta(self, status, body=None):
        respuesta = Mock(status_code=status)
        respuesta.json.return_value = body if body is not None else {}
        return self._resultado(return_value=respuesta)

    def test_201_es_ok(self):
        r = self._respuesta(201, {"ids_generados": [26]})
        self.assertEqual(r["resultado"], "OK")
        self.assertEqual(r["siis_id"], 26)

    def test_connect_timeout_no_salio(self):
        r = self._resultado(side_effect=requests.ConnectTimeout())
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertTrue(r["reintentable"])

    def test_dns_que_no_resuelve_no_salio(self):
        """``ConnectionError`` envuelve el error de urllib3: hay que mirar la cadena."""
        from urllib3.exceptions import MaxRetryError, NewConnectionError

        fallo = requests.ConnectionError(
            MaxRetryError(pool=None, url="/", reason=NewConnectionError(None, "no resuelve"))
        )
        r = self._resultado(side_effect=fallo)
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertTrue(r["reintentable"])

    def test_read_timeout_es_incierto(self):
        """El POST ya está entregado: SIIS pudo haberlo procesado."""
        r = self._resultado(side_effect=requests.ReadTimeout("read"))
        self.assertEqual(r["resultado"], "INCIERTO")
        self.assertEqual(r["codigo"], "RESULTADO_INCIERTO")
        self.assertFalse(r["reintentable"])

    def test_conexion_cortada_a_mitad_es_incierta(self):
        r = self._resultado(side_effect=requests.ConnectionError("cortada"))
        self.assertEqual(r["resultado"], "INCIERTO")
        self.assertFalse(r["reintentable"])

    def test_respuesta_truncada_es_incierta(self):
        r = self._resultado(side_effect=requests.exceptions.ChunkedEncodingError("truncada"))
        self.assertEqual(r["resultado"], "INCIERTO")

    def test_400_datos_invalidos_es_rechazo(self):
        r = self._respuesta(400, {"error": "DATOS_INVALIDOS", "detalles": {"barrio_actual": ["mínimo 4"]}})
        self.assertEqual(r["resultado"], "RECHAZADO")
        self.assertEqual(r["codigo"], "DATOS_INVALIDOS")
        self.assertFalse(r["reintentable"])

    def test_4xx_sin_codigo_es_rechazo_de_configuracion(self):
        """Un 404 o un 422 sin cuerpo no es un dato del beneficiario: es la integración."""
        for status in (404, 422):
            with self.subTest(status=status):
                r = self._respuesta(status)
                self.assertEqual(r["resultado"], "RECHAZADO")
                self.assertEqual(r["codigo"], "CONFIGURACION")
                self.assertFalse(r["reintentable"])

    def test_408_y_429_son_inciertos(self):
        for status in (408, 429):
            with self.subTest(status=status):
                self.assertEqual(self._respuesta(status)["resultado"], "INCIERTO")

    def test_503_del_legacy_ocupado_se_reintenta(self):
        """D-S02: el único 5xx que garantiza que el alta no se escribió."""
        r = self._respuesta(503, {"error": "ERROR_BD_LEGACY"})
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertEqual(r["codigo"], "ERROR_BD_LEGACY")
        self.assertTrue(r["reintentable"])

    def test_500_502_504_y_503_sin_codigo_son_inciertos(self):
        for status in (500, 502, 504, 503):
            with self.subTest(status=status):
                r = self._respuesta(status)
                self.assertEqual(r["resultado"], "INCIERTO")
                self.assertFalse(r["reintentable"])

    def test_un_token_que_no_se_puede_obtener_no_salio(self):
        with patch.object(SiisAPIClient, "_token", side_effect=requests.ConnectionError("sin red")):
            with patch("programas.services.siis.requests.post") as post:
                r = SiisAPIClient().cargar_beneficiario({"dni": 1})
        post.assert_not_called()
        self.assertEqual(r["resultado"], "NO_ENVIADO")
        self.assertEqual(r["codigo"], "ERROR_TECNICO")
