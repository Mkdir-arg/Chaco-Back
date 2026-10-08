"""Contrato del esquema OpenAPI y de las vistas de documentación (RED-36, RED-37).

`drf_spectacular` estaba configurado (`DEFAULT_SCHEMA_CLASS`, `SPECTACULAR_SETTINGS`,
las tres rutas de `config/urls.py` y hasta una excepción de CSP para `/api/docs/`)
pero la app no estaba en `INSTALLED_APPS`: `/api/docs/` y `/api/redoc/` daban 500
con `TemplateDoesNotExist` y `manage.py spectacular` no existía, así que ningún
gate de esquema era posible (RED-36).

Además el esquema publicaba tipos falsos —`definicion_formulario`,
`cupo_disponible`, `cupo_completo` y `pausado` como `string`— y
`/api/becas/personas/consultar/` no declaraba su cuerpo (RED-37). Quien generara
un cliente desde el esquema escribía código que no compila contra la API real.

Los dos ratchets de acá —`VISTAS_CON_ERROR_CONOCIDO` y `MAX_WARNINGS_CONOCIDOS`—
fijan lo que hay hoy y **solo pueden bajar**: una vista nueva sin serializer o un
`SerializerMethodField` sin anotar ponen el test en rojo.
"""

import re

from django.contrib.auth.models import User
from django.core.management import get_commands
from django.test import TestCase
from django.urls import reverse
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator

# Las vistas que todavía no declaran serializer. Spectacular las descarta del
# esquema ("Ignoring view for now"), así que cada una es un endpoint que la
# documentación no publica. La Ola 7 las cierra con `inline_serializer`
# (RED-37 punto 3); hasta entonces, la lista solo puede achicarse.
VISTAS_CON_ERROR_CONOCIDO = {
    # dashboard/api_views/__init__.py
    "actividad_reciente",
    "alertas_criticas",
    "buscar_ciudadanos",
    "metricas_dashboard",
    "tendencias_datos",
    # conversaciones/api_views/
    "alertas_conversaciones_count",
    "alertas_conversaciones_preview",
    "conversacion_detalle",
    "marcar_mensajes_leidos",
    # La vista de las pruebas de la «fase 2» salió de acá con OPS-10 (Ola 7): se borró
    # junto con el módulo que la alimentaba.
}

# Warnings del generador (tipos que caen a `string`, colisiones de enum, un
# parámetro de path sin tipo). No rompen el esquema pero lo empobrecen; el gate
# de CI suma `--fail-on-warn` cuando este número llegue a 0 (RED-43). Eran 24
# antes de anotar los serializers de Becas.
MAX_WARNINGS_CONOCIDOS = 15


def _generar_esquema_y_sus_avisos():
    """Genera el esquema y devuelve `(esquema, errores, warnings)`.

    Spectacular no levanta excepciones: acumula los avisos en `GENERATOR_STATS`
    (y los imprime por stderr) y sigue. Sin mirar ese acumulador, un esquema
    roto se genera "bien". Las cachés son globales del proceso y deduplican, así
    que hay que resetearlas antes: si otro test ya pidió `/api/schema/`, la
    segunda generación no reporta nada.
    """
    GENERATOR_STATS.reset()
    with GENERATOR_STATS.silence():
        esquema = SchemaGenerator().get_schema(request=None, public=True)
    errores = sorted(GENERATOR_STATS._error_cache)
    warnings = sorted(GENERATOR_STATS._warn_cache)
    GENERATOR_STATS.reset()
    return esquema, errores, warnings


def _nombre_de_vista(aviso):
    """`…: Error [buscar_ciudadanos]: unable to guess…` → `buscar_ciudadanos`."""
    return aviso.split("Error [", 1)[1].split("]", 1)[0]


class DocumentacionDeApiTests(TestCase):
    """RED-36: las tres rutas de documentación responden, y detrás de login."""

    URLS = ("/api/schema/", "/api/docs/", "/api/redoc/")

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("doc-api", password="Clave-Seg-2026x", is_staff=True)

    def test_el_comando_spectacular_esta_disponible(self):
        """Sin la app en `INSTALLED_APPS` no existe `manage.py spectacular`, y sin
        el comando ningún gate de esquema en CI es posible (RED-36, R-18)."""
        self.assertIn("spectacular", get_commands())

    def test_schema_docs_y_redoc_responden_200(self):
        self.client.force_login(self.staff)

        for url in self.URLS:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)

    def test_schema_docs_y_redoc_siguen_detras_de_login(self):
        """El inventario de endpoints no es superficie pública (seguridad, 26/08/2026)."""
        login = reverse("users:login")

        for url in self.URLS:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 302)
                self.assertTrue(respuesta["Location"].startswith(login))


class DocumentacionSinTercerosTests(TestCase):
    """Ni Swagger-UI ni Redoc salen a buscar nada afuera.

    Los defaults de `SWAGGER_UI_DIST` y `REDOC_DIST` apuntan a
    `cdn.jsdelivr.net/npm/<paquete>@latest`: código de terceros, sin versión
    fija, ejecutándose con la sesión de un usuario de backoffice. Se sirven
    desde `/static/` con `SIDECAR` y la versión pineada en `requirements.txt`;
    las fuentes que la plantilla del paquete traía escritas a mano salen con
    `templates/api/redoc.html` (RED-36, revisión del PR R-04).
    """

    URLS = ("/api/docs/", "/api/redoc/")

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user("doc-cdn", password="Clave-Seg-2026x", is_staff=True)

    def test_el_html_no_referencia_dominios_externos(self):
        self.client.force_login(self.staff)
        externos = re.compile(r'(?:src|href)\s*=\s*["\'](?P<url>(?:https?:)?//[^"\']+)')

        for url in self.URLS:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()

                encontrados = [m.group("url") for m in externos.finditer(html)]
                self.assertEqual(encontrados, [], f"{url} carga recursos de otro origen")

    def test_los_bundles_salen_del_static_propio(self):
        """La contracara: que no estén afuera porque no estén en ninguna parte."""
        self.client.force_login(self.staff)

        docs = self.client.get("/api/docs/").content.decode()
        redoc = self.client.get("/api/redoc/").content.decode()

        self.assertIn("/static/drf_spectacular_sidecar/swagger-ui-dist/swagger-ui-bundle.js", docs)
        self.assertIn("/static/drf_spectacular_sidecar/redoc/bundles/redoc.standalone.js", redoc)


class EsquemaOpenApiTests(TestCase):
    """RED-37: el esquema se genera y dice la verdad sobre los tipos."""

    @classmethod
    def setUpTestData(cls):
        cls.esquema, cls.errores, cls.warnings = _generar_esquema_y_sus_avisos()

    def test_el_esquema_se_genera_sin_errores(self):
        vistas = {_nombre_de_vista(linea) for linea in self.errores}

        nuevas = vistas - VISTAS_CON_ERROR_CONOCIDO
        self.assertFalse(
            nuevas,
            f"Vistas nuevas que el esquema no puede publicar: {sorted(nuevas)}. "
            "Declarales un serializer (`@extend_schema(request=…, responses=…)`) "
            "o agregalas a VISTAS_CON_ERROR_CONOCIDO con su ficha.",
        )
        arregladas = VISTAS_CON_ERROR_CONOCIDO - vistas
        self.assertFalse(
            arregladas,
            f"Estas vistas ya no fallan: {sorted(arregladas)}. Sacalas de "
            "VISTAS_CON_ERROR_CONOCIDO en el mismo diff (el ratchet solo baja).",
        )

    def test_el_esquema_no_suma_warnings(self):
        self.assertLessEqual(
            len(self.warnings),
            MAX_WARNINGS_CONOCIDOS,
            "El esquema sumó warnings nuevos:\n" + "\n".join(self.warnings),
        )

    def test_relevamiento_detail_publica_los_tipos_reales(self):
        """Lo que consume la app de campo: cupo numérico, pausa booleana y la
        definición del formulario como objeto, no como `string`."""
        propiedades = self.esquema["components"]["schemas"]["RelevamientoDetail"]["properties"]

        self.assertEqual(propiedades["definicion_formulario"]["type"], "object")
        self.assertEqual(propiedades["cupo_disponible"]["type"], "integer")
        self.assertEqual(propiedades["cupo_completo"]["type"], "boolean")
        self.assertEqual(propiedades["pausado"]["type"], "boolean")
        self.assertEqual(propiedades["pausa_motivo"]["type"], "string")

    def test_consultar_persona_declara_su_cuerpo(self):
        """`/api/becas/personas/consultar/` publicaba un POST sin `requestBody`:
        un cliente generado desde el esquema mandaba el cuerpo vacío."""
        operacion = self.esquema["paths"]["/api/becas/personas/consultar/"]["post"]

        self.assertIn("requestBody", operacion)
        contenido = operacion["requestBody"]["content"]["application/json"]["schema"]
        # `COMPONENT_SPLIT_REQUEST` le pone el sufijo `Request` al componente.
        self.assertEqual(contenido.get("$ref", "").split("/")[-1], "ConsultaPersonaRequest")

        campos = self.esquema["components"]["schemas"]["ConsultaPersonaRequest"]
        self.assertEqual(sorted(campos["required"]), ["dni", "sexo"])
        self.assertEqual(campos["properties"]["relevamiento"]["type"], "integer")
        self.assertEqual(campos["properties"]["sexo"]["$ref"].split("/")[-1], "SexoEnum")
        self.assertEqual(self.esquema["components"]["schemas"]["SexoEnum"]["enum"], ["F", "M"])

        respuesta = operacion["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertEqual(respuesta.get("$ref", "").split("/")[-1], "ConsultaPersonaRespuesta")
