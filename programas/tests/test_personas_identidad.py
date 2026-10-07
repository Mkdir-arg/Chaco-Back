"""SIIS-10 · La identidad de Base de Personas se extrae por ruta, no aplanando.

``_aplanar`` recorría la respuesta entera con ``setdefault``, así que la primera
aparición de una clave a **cualquier** profundidad ganaba. Con la respuesta real
—que trae el domicilio anidado— ``domicilio.localidad.nombre`` le ganaba a
``nombres`` y la persona quedaba **validada** llamándose «Resistencia»: ese
nombre se fija en el paso 2 del link público, viaja al legajo y de ahí a SIIS.

Además la respuesta no se comparaba contra lo consultado: dos registros en
``data.personas`` mezclaban datos de dos personas en uno solo, y un ``dni``
distinto al pedido se aceptaba sin chistar.
"""

from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from programas.services.personas import TOKEN_CACHE_KEY, PersonasAPIClient, normalizar_persona

RESPUESTA_REAL = {
    "data": {
        "codigo": 0,
        "mensaje": "OK",
        "dni": "11111111",
        "nombres": "Sintetica Prueba",
        "apellido": "Contrato",
        "fechaNacimiento": "08/05/1992",
        "sexo": "F",
        "domicilio": {
            "calle": "Calle Inventada",
            "numero": "742",
            "localidad": {"id": 99, "nombre": "Resistencia"},
            "provincia": {"id": 22, "nombre": "Chaco"},
        },
    }
}


class IdentidadPorRutaTests(SimpleTestCase):
    """SIIS-10: `normalizar_persona` lee el registro, no el árbol entero."""

    def test_el_nombre_sale_del_registro_y_no_del_domicilio(self):
        """La PoC invertida (`PersonasAplanadoTests`): antes daba «Resistencia»."""
        persona = normalizar_persona(RESPUESTA_REAL, "11111111")

        self.assertEqual(persona["nombre"], "Sintetica Prueba")
        self.assertEqual(persona["apellido"], "Contrato")
        self.assertEqual(persona["fecha_nacimiento"], "1992-05-08")
        self.assertEqual(persona["sexo"], "F")

    def test_ninguna_clave_anidada_pisa_al_registro(self):
        """El caso mínimo de la ficha, con el nombre solo en el nivel de abajo."""
        payload = {"data": {"domicilio": {"localidad": {"nombre": "Resistencia"}}, "nombres": "Ana", "apellido": "P"}}

        self.assertEqual(normalizar_persona(payload, "1")["nombre"], "Ana")

    def test_nombres_le_gana_a_nombre(self):
        payload = {"data": {"nombre": "APELLIDO, Ana", "nombres": "Ana", "apellido": "Apellido"}}

        self.assertEqual(normalizar_persona(payload, "1")["nombre"], "Ana")

    def test_el_registro_bajo_data_persona_se_sigue_leyendo(self):
        """Contrato ya soportado (`PersonasNormalizationTests`): no se rompe."""
        payload = {
            "codigo_http": 200,
            "data": {
                "persona": {
                    "numero_documento": "30111222",
                    "apellido": "Perez",
                    "nombres": "Ana Maria",
                    "fechaNacimiento": "1990-01-02",
                    "genero": "F",
                }
            },
        }

        self.assertEqual(
            normalizar_persona(payload, "30111222"),
            {
                "dni": "30111222",
                "apellido": "Perez",
                "nombre": "Ana Maria",
                "fecha_nacimiento": "1990-01-02",
                "sexo": "F",
            },
        )

    def test_un_solo_registro_en_la_lista_tambien_sirve(self):
        payload = {"data": {"personas": [{"dni": "30111222", "nombres": "Ana", "apellido": "Perez"}]}}

        self.assertEqual(normalizar_persona(payload, "30111222")["nombre"], "Ana")


@override_settings(
    PERSONAS_API_URL="https://personas.example/api/v1",
    PERSONAS_API_CLIENT_ID="client",
    PERSONAS_API_CLIENT_SECRET="secret",
    PERSONAS_API_ENTIDAD_UUID="entity",
    PERSONAS_API_FUENTE_ID=13,
    PERSONAS_API_CONNECT_TIMEOUT=5,
    PERSONAS_API_TIMEOUT=10,
)
class RespuestaQueNoCorrespondeTests(SimpleTestCase):
    """SIIS-10: lo que no se puede atribuir a la persona consultada no se usa."""

    def setUp(self):
        cache.clear()
        cache.set(TOKEN_CACHE_KEY, "token-prueba", 60)

    def _consultar(self, data, dni="30111222", sexo="F"):
        respuesta = Mock(status_code=200)
        respuesta.json.return_value = {"codigo_http": 200, "data": data}
        respuesta.raise_for_status.return_value = None
        with patch("programas.services.personas.sesion.get", return_value=respuesta):
            return PersonasAPIClient().consultar(dni, sexo)

    def test_dos_registros_que_coinciden_son_una_respuesta_ambigua(self):
        resultado = self._consultar(
            {
                "personas": [
                    {"dni": "30111222", "nombres": "Ana", "apellido": "Perez"},
                    {"dni": "30111222", "nombres": "Ana Maria", "apellido": "Perez Lopez"},
                ]
            }
        )

        self.assertFalse(resultado["success"])
        self.assertIn("ambigua", resultado["error"])
        self.assertNotIn("data", resultado)

    def test_de_dos_registros_gana_el_del_documento_consultado(self):
        resultado = self._consultar(
            {
                "personas": [
                    {"dni": "99999999", "nombres": "Otra", "apellido": "Persona"},
                    {"dni": "30111222", "nombres": "Ana", "apellido": "Perez"},
                ]
            }
        )

        self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertEqual(resultado["data"]["nombre"], "Ana")
        self.assertEqual(resultado["data"]["apellido"], "Perez")

    def test_un_documento_distinto_al_consultado_no_se_acepta(self):
        resultado = self._consultar({"dni": "99999999", "nombres": "Otra", "apellido": "Persona"})

        self.assertFalse(resultado["success"])
        self.assertIn("no corresponde", resultado["error"])
        self.assertNotIn("data", resultado)

    def test_el_sexo_que_no_coincide_desempata_pero_no_bloquea_la_variante_larga(self):
        """«FEMENINO» y «F» son la misma persona; «M» y «F», no."""
        otro_sexo = self._consultar(
            {"personas": [{"dni": "30111222", "sexo": "M", "nombres": "Ana"}]},
            sexo="F",
        )
        self.assertFalse(otro_sexo["success"])

        variante = self._consultar(
            {"personas": [{"dni": "30111222", "sexo": "FEMENINO", "nombres": "Ana", "apellido": "Perez"}]},
            sexo="F",
        )
        self.assertTrue(variante["success"], variante.get("error"))
        self.assertEqual(variante["data"]["nombre"], "Ana")

    def test_una_lista_vacia_de_personas_no_inventa_una(self):
        resultado = self._consultar({"personas": []})

        self.assertFalse(resultado["success"])
        self.assertIn("ambigua", resultado["error"])
