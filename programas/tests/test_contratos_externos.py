"""Los parsers de RENAPER, Personas y SIIS corren contra la respuesta real (RED-41).

Hasta la auditoría de oct-2026 los tres clientes se probaban contra diccionarios
escritos a mano en cada test: tres o cuatro claves planas, sin el domicilio
anidado, sin el sobre del proveedor. ~20 claves de upstream se leen con `.get()`
y default silencioso, así que ninguno de esos tests podía ver el escenario que
más duele: **que el contrato lo cambie el proveedor**. Si `result` se anida un
nivel más, `consultar_renaper` devuelve `{"success": True, "data": {}}` y el caso
se marca **validado con el nombre vacío**.

Acá los tres parsers consumen un fixture **compartido** por servicio y rama
(`programas/fixtures/contratos/`, ver su README): sintético por **D-RED-04**
—icore tiene datos reales y corre con `ENVIRONMENT=prd`—, pero con la estructura
completa. `test_toda_clave_leida_existe_en_el_fixture` cierra el círculo: una
clave nueva que el parser empiece a leer y que el fixture no tenga pone el
módulo en rojo, que es el recordatorio de verificarla contra el proveedor.

No se toca la red: todo pasa por `unittest.mock`.
"""

import ast
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from legajos.services import consulta_renaper
from programas.services import siis
from programas.services.personas import TOKEN_CACHE_KEY as PERSONAS_TOKEN_KEY
from programas.services.personas import PersonasAPIClient, normalizar_persona

RAIZ = Path(settings.BASE_DIR)
CONTRATOS = RAIZ / "programas" / "fixtures" / "contratos"


def contrato(nombre):
    """El cuerpo JSON que devuelve el proveedor, tal cual."""
    return json.loads((CONTRATOS / f"{nombre}.json").read_text(encoding="utf-8"))


def _respuesta(cuerpo, status=200):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = cuerpo
    respuesta.raise_for_status.return_value = None
    return respuesta


RENAPER_SETTINGS = dict(
    RENAPER_API_URL="https://renaper.example/api",
    RENAPER_API_USERNAME="usuario",
    RENAPER_API_PASSWORD="clave",
    RENAPER_API_KEY="api-key-de-prueba",
    RENAPER_TEST_MODE=False,
)

PERSONAS_SETTINGS = dict(
    PERSONAS_API_URL="https://personas.example/api/v1",
    PERSONAS_API_CLIENT_ID="client",
    PERSONAS_API_CLIENT_SECRET="secret",
    PERSONAS_API_ENTIDAD_UUID="entity",
    PERSONAS_API_FUENTE_ID=13,
    PERSONAS_API_CONNECT_TIMEOUT=5,
    PERSONAS_API_TIMEOUT=10,
)

SIIS_SETTINGS = dict(
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="client",
    SIIS_API_CLIENT_SECRET="secret",
    SIIS_API_CONNECT_TIMEOUT=5,
    SIIS_API_TIMEOUT=20,
    SIIS_API_TIMEOUT_TOKEN=10,
    SIIS_API_TIMEOUT_CONSULTA=10,
)


class ContratoUpstreamTests(TestCase):
    """RED-41: cada rama documentada del proveedor, contra el parser de verdad."""

    def setUp(self):
        # El cortacircuito y los tokens viven en la caché: sin esto, el test que
        # corre antes decide si el siguiente sale a «la red».
        cache.clear()

    # ── RENAPER ──────────────────────────────────────────────────────────
    def _renaper(self, cuerpo):
        """Corre la cadena completa `consultar_ciudadano` → `consultar_datos_renaper`."""
        cliente = consulta_renaper.APIClient()
        cliente.session = Mock()
        cliente.session.get.return_value = _respuesta(cuerpo)
        cliente.session.post.return_value = _respuesta(cuerpo)
        with patch.object(consulta_renaper, "_get_client", return_value=cliente):
            return consulta_renaper.consultar_datos_renaper("11111111", "F")

    @override_settings(**RENAPER_SETTINGS)
    def test_renaper_ok(self):
        resultado = self._renaper(contrato("renaper_ok"))

        self.assertTrue(resultado["success"], resultado.get("error"))
        datos = resultado["data"]
        # Ningún campo vacío: con el sobre cambiado, todos estos salían en "".
        self.assertEqual(datos["nombre"], "Sintetica Prueba")
        self.assertEqual(datos["apellido"], "Contrato")
        self.assertEqual(datos["fecha_nacimiento"], "1990-01-02")
        self.assertEqual(datos["genero"], "F")
        self.assertEqual(datos["domicilio"], "Calle Inventada 742 3 B")
        self.assertEqual(datos["dni"], "11111111")

    @override_settings(**RENAPER_SETTINGS)
    def test_renaper_fallecido(self):
        """`mensaf == "FALLECIDO"` corta el alta: no devuelve `data`."""
        resultado = self._renaper(contrato("renaper_fallecido"))

        self.assertEqual(resultado, {"success": False, "fallecido": True})

    @override_settings(**RENAPER_SETTINGS)
    def test_renaper_con_el_sobre_viejo_del_proveedor(self):
        """El proveedor ya cambió una vez: `isSuccess`/`result` en vez de `success`/`data`.

        El parser mira las dos. Este test es el que se pondría rojo el día que
        agregue un tercer sobre y nadie actualice el cliente.
        """
        cuerpo = contrato("renaper_ok")
        viejo = {"isSuccess": True, "result": cuerpo["data"]}

        resultado = self._renaper(viejo)

        self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertEqual(resultado["data"]["nombre"], "Sintetica Prueba")

    @override_settings(**RENAPER_SETTINGS)
    def test_renaper_con_el_result_anidado_un_nivel_mas_no_se_marca_validado(self):
        """El escenario que nombra la ficha, hoy **no** cubierto por el cliente.

        Si el proveedor anida `result` un nivel, el cliente devuelve
        `{"success": True, "data": {}}` y el caso se marca validado con el nombre
        vacío. El arreglo (exigir que el `data` traiga al menos nombre y
        apellido) es de la Ola 3 junto con SIIS-10: acá queda medido.
        """
        cuerpo = contrato("renaper_ok")
        anidado = {"isSuccess": True, "result": {"persona": cuerpo["data"]}}

        resultado = self._renaper(anidado)

        self.assertTrue(resultado["success"])
        self.assertEqual(resultado["data"]["nombre"], None)
        self.assertEqual(resultado["data"]["apellido"], None)

    # ── Base de Personas ─────────────────────────────────────────────────
    def _personas(self, cuerpo, status=200):
        cache.delete(PERSONAS_TOKEN_KEY)
        with (
            patch("programas.services.personas.sesion.post") as post,
            patch("programas.services.personas.sesion.get") as get,
        ):
            post.return_value = _respuesta({"data": {"token": "token-de-prueba"}})
            get.return_value = _respuesta(cuerpo, status=status)
            return PersonasAPIClient().consultar("11111111", "F")

    @override_settings(**PERSONAS_SETTINGS)
    def test_personas_ok(self):
        resultado = self._personas(contrato("personas_ok"))

        self.assertTrue(resultado["success"], resultado.get("error"))
        self.assertEqual(resultado["data"]["apellido"], "Contrato")
        self.assertEqual(resultado["data"]["sexo"], "F")
        # El proveedor manda `08/05/1992`; el resto del sistema espera ISO.
        self.assertEqual(resultado["data"]["fecha_nacimiento"], "1992-05-08")

    @override_settings(**PERSONAS_SETTINGS)
    def test_personas_no_encontrada(self):
        resultado = self._personas(contrato("personas_no_encontrada"))

        self.assertFalse(resultado["success"])
        self.assertTrue(resultado["not_found"])

    @unittest.expectedFailure
    def test_personas_no_toma_claves_anidadas(self):
        """SIIS-10 (Ola 3): `_aplanar` aplana a cualquier profundidad con `setdefault`.

        En el fixture, `domicilio.localidad.nombre` («Resistencia») aparece antes
        que `nombres` en el recorrido, así que gana y la persona queda validada
        llamándose «Resistencia». El arreglo —extraer por ruta, leyendo solo el
        primer nivel— es de la Ola 3. Mientras tanto este test documenta el bug
        con `expectedFailure`: el día que SIIS-10 lo arregle, pasa a verde y hay
        que sacarle el decorador.
        """
        persona = normalizar_persona(contrato("personas_ok"), "11111111")

        self.assertEqual(persona["nombre"], "Sintetica Prueba")

    def test_personas_toma_hoy_la_clave_anidada(self):
        """Contracara del anterior, para que el bug quede medido y no solo esperado."""
        persona = normalizar_persona(contrato("personas_ok"), "11111111")

        self.assertEqual(persona["nombre"], "Resistencia")

    # ── SIIS ─────────────────────────────────────────────────────────────
    def _alta_siis(self, cuerpo, status):
        with (
            patch("programas.services.siis.sesion.post") as post,
            patch("programas.services.siis.sesion.get"),
        ):
            post.side_effect = [
                _respuesta({"access_token": "token-de-prueba", "expires_in": 3600}),
                _respuesta(cuerpo, status=status),
            ]
            return siis.cargar_beneficiario({"dni": 11111111})

    @override_settings(**SIIS_SETTINGS)
    def test_siis_alta_ok(self):
        resultado = self._alta_siis(contrato("siis_alta_ok"), status=201)

        self.assertTrue(resultado["success"])
        self.assertEqual(resultado["resultado"], siis.RESULTADO_OK)
        # El id de la fila en la tabla intermedia: es lo que se concilia después.
        self.assertEqual(resultado["siis_id"], 987654)
        self.assertFalse(resultado["reintentable"])

    @override_settings(**SIIS_SETTINGS)
    def test_siis_rechazado(self):
        resultado = self._alta_siis(contrato("siis_rechazado"), status=400)

        self.assertFalse(resultado["success"])
        self.assertEqual(resultado["resultado"], siis.RESULTADO_RECHAZADO)
        self.assertEqual(resultado["codigo"], "DATOS_INVALIDOS")
        self.assertFalse(resultado["reintentable"])
        # `detalles` es lo que el coordinador ve campo por campo en la revisión.
        self.assertEqual(
            set(resultado["detalles"]),
            {"fecha_nacim_apoderado", "id_fun_x_plan"},
        )
        self.assertIn("no cumple los requisitos", resultado["error"])


# Qué fixture respalda a cada parser, y qué claves de ese parser **no** están en
# el fixture a propósito (ramas de error, claves de nuestra propia respuesta).
PARSERS = {
    "legajos/services/consulta_renaper.py": {
        "fixtures": ["renaper_ok", "renaper_fallecido"],
        "ignorar": {
            # Sobre alternativo del proveedor (se arma en el test, no en el fixture).
            "isSuccess",
            "result",
            "message",
            # Claves de la respuesta que arma **este** repo, no del proveedor.
            "error",
            "status_code",
            "raw_response",
            "data",
            "fallecido",
            # Modo API key / login, fuera del contrato de consulta.
            "token",
            "expiration",
        },
    },
    "programas/services/personas.py": {
        "fixtures": ["personas_ok", "personas_no_encontrada"],
        "ignorar": {
            "data",
            "token",
            # Ramas de fallecido y variantes que el parser tolera pero que el
            # proveedor todavía no confirmó (task #243).
            "mensaf",
            "fallecido",
            "es_fallecido",
            "fecha_fallecimiento",
            "fechaFallecimiento",
            "fecha_defuncion",
        },
    },
}


def _claves_leidas(ruta):
    """Literales de `X.get("clave")` y `X["clave"]` del módulo."""
    arbol = ast.parse((RAIZ / ruta).read_text(encoding="utf-8"))
    claves = set()
    for nodo in ast.walk(arbol):
        if (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "get"
            and nodo.args
            and isinstance(nodo.args[0], ast.Constant)
            and isinstance(nodo.args[0].value, str)
        ):
            claves.add(nodo.args[0].value)
    return claves


def _claves_del_fixture(nombre):
    """Todas las claves del JSON, a cualquier profundidad."""

    def recorrer(valor):
        if isinstance(valor, dict):
            for clave, item in valor.items():
                yield clave
                yield from recorrer(item)
        elif isinstance(valor, list):
            for item in valor:
                yield from recorrer(item)

    return set(recorrer(contrato(nombre)))


class ClavesDelContratoTests(SimpleTestCase):
    """Cada clave que el parser lee del upstream existe en algún fixture."""

    def test_toda_clave_leida_existe_en_el_fixture(self):
        faltantes = {}
        for ruta, config in PARSERS.items():
            delfixture = set().union(*(_claves_del_fixture(n) for n in config["fixtures"]))
            # Solo las claves que parecen del proveedor: las nuestras (snake_case
            # de la respuesta que arma el repo) están en `ignorar`.
            sin_respaldo = sorted(_claves_leidas(ruta) - delfixture - config["ignorar"])
            if sin_respaldo:
                faltantes[ruta] = sin_respaldo

        self.assertEqual(
            faltantes,
            {},
            "claves de upstream que el parser lee y que ningún fixture de contrato tiene: "
            "o el fixture quedó viejo, o la clave se inventó. Verificala contra el proveedor "
            f"antes de agregarla al fixture: {faltantes}",
        )

    def test_los_fixtures_existen_y_son_json(self):
        archivos = sorted(p.stem for p in CONTRATOS.glob("*.json"))

        self.assertEqual(
            archivos,
            [
                "personas_no_encontrada",
                "personas_ok",
                "renaper_fallecido",
                "renaper_ok",
                "siis_alta_ok",
                "siis_rechazado",
            ],
        )
        for nombre in archivos:
            with self.subTest(fixture=nombre):
                self.assertIsInstance(contrato(nombre), dict)
