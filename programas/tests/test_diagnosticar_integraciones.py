"""Tests del comando ``diagnosticar_integraciones``.

Lo que se verifica es que **distinga** las causas que desde la pantalla del
formulario público se ven iguales: credenciales de Base de Personas sin cargar,
DNI que no está en la fuente, consulta que responde con datos, y las cuatro
razones por las que un link muestra "Formulario no disponible".

Cada clase parte de un entorno donde **el resto** de las integraciones está sano
(``ENTORNO_SANO``), para que el código de salida hable solo de lo que se prueba.
También se verifica que el comando nunca imprima un secreto.
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import Mock, patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from programas.models import Convocatoria, Relevamiento, Segmento
from programas.services.personas import TOKEN_CACHE_KEY
from users.models import Capacidad

SECRETO = "secreto-que-no-debe-aparecer"

# Todo lo que no se está probando, sano: así una falla en la salida es la que se busca.
ENTORNO_SANO = dict(
    RENAPER_TEST_MODE=True,
    SIIS_API_URL="https://siis.example",
    SIIS_API_CLIENT_ID="siis-client",
    SIIS_API_CLIENT_SECRET="siis-secret",
)

SIN_PERSONAS = dict(
    ENTORNO_SANO,
    PERSONAS_API_CLIENT_ID="",
    PERSONAS_API_CLIENT_SECRET="",
    PERSONAS_API_ENTIDAD_UUID="",
)

CON_PERSONAS = dict(
    ENTORNO_SANO,
    PERSONAS_API_URL="https://personas.example/api/v1",
    PERSONAS_API_CLIENT_ID="client-id-de-prueba",
    PERSONAS_API_CLIENT_SECRET=SECRETO,
    PERSONAS_API_ENTIDAD_UUID="b2f1f520-db5e-4d3d-88d2-785f2d614f3d",
    PERSONAS_API_FUENTE_ID=13,
    PERSONAS_API_CONNECT_TIMEOUT=1,
    PERSONAS_API_TIMEOUT=2,
)

PERSONA_OK = {
    "codigo_http": 200,
    "data": {
        "nombre": "PAMELA JANET",
        "apellido": "ROMERO",
        "fechaNacimiento": "08/05/1992",
        "dni": "36210951",
        "sexo": "F",
    },
}
PERSONA_NO_ENCONTRADA = {"codigo_http": 200, "data": {"codigo": 12, "mensaje": "NO SE ENCONTRO INFORMACION"}}


def _respuesta(payload, status=200):
    respuesta = Mock(status_code=status)
    respuesta.json.return_value = payload
    respuesta.raise_for_status.return_value = None
    return respuesta


def _correr(*args):
    """Corre el comando y devuelve ``(salida, codigo_de_salida)``."""
    salida = StringIO()
    codigo = 0
    try:
        call_command("diagnosticar_integraciones", *args, stdout=salida, stderr=salida)
    except SystemExit as exc:
        codigo = exc.code
    return salida.getvalue(), codigo


class BaseDiagnosticoTests(TestCase):
    def setUp(self):
        # El token vive en caché entre corridas del proceso: sin esto un test le
        # presta el token al siguiente y el mock no se ejercita.
        cache.delete(TOKEN_CACHE_KEY)


@override_settings(**SIN_PERSONAS)
class SinCredencialesTests(BaseDiagnosticoTests):
    def test_detecta_base_de_personas_sin_credenciales(self):
        salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("configuración incompleta", salida)
        self.assertIn("NUNCA va a precargar", salida)

    def test_no_pretende_haber_probado_la_consulta(self):
        salida, _ = _correr("--dni", "36210951", "--sexo", "F")

        self.assertNotIn("precargaría", salida)


@override_settings(**CON_PERSONAS)
class ConfiguracionTests(BaseDiagnosticoTests):
    @patch("programas.services.personas.requests.post")
    def test_no_imprime_el_secreto(self, post):
        post.return_value = _respuesta({"data": {"token": "t" * 30}})

        salida, _ = _correr()

        self.assertNotIn(SECRETO, salida)
        self.assertIn("PERSONAS_API_CLIENT_SECRET", salida)
        self.assertIn(f"presente ({len(SECRETO)} caracteres)", salida)

    @patch("programas.services.personas.requests.post")
    def test_sin_dni_avisa_que_no_ejercito_la_consulta(self, post):
        post.return_value = _respuesta({"data": {"token": "t" * 30}})

        salida, codigo = _correr()

        self.assertEqual(codigo, 0)
        self.assertIn("token obtenido", salida)
        self.assertIn("sin --dni no se probó una consulta real", salida)

    @patch("programas.services.personas.requests.post")
    def test_token_rechazado_es_falla(self, post):
        post.side_effect = ValueError("credenciales invalidas")

        salida, codigo = _correr()

        self.assertEqual(codigo, 1)
        self.assertIn("no se pudo obtener el token", salida)


@override_settings(**CON_PERSONAS)
class ConsultaTests(BaseDiagnosticoTests):
    def setUp(self):
        super().setUp()
        self.post = patch("programas.services.personas.requests.post").start()
        self.post.return_value = _respuesta({"data": {"token": "t" * 30}})
        self.get = patch("programas.services.personas.requests.get").start()
        self.addCleanup(patch.stopall)

    def test_consulta_con_datos_confirma_que_el_publico_precarga(self):
        self.get.return_value = _respuesta(PERSONA_OK)

        salida, codigo = _correr("--dni", "36210951", "--sexo", "F")

        self.assertEqual(codigo, 0)
        self.assertIn("ROMERO, PAMELA JANET", salida)
        self.assertIn("1992-05-08", salida)
        self.assertIn("precargaría estos datos", salida)

    def test_dni_no_encontrado_es_aviso_no_falla(self):
        self.get.return_value = _respuesta(PERSONA_NO_ENCONTRADA)

        salida, codigo = _correr("--dni", "21884116", "--sexo", "M")

        self.assertEqual(codigo, 0, "un DNI ausente no es una falla de la integración")
        self.assertIn("no está en la fuente 13", salida)
        self.assertIn("La integración funciona", salida)

    def test_acepta_sexo_en_palabras(self):
        self.get.return_value = _respuesta(PERSONA_OK)

        salida, _ = _correr("--dni", "36210951", "--sexo", "Femenino")

        self.assertIn("36210951/F", salida)

    def test_sexo_invalido_es_falla(self):
        salida, codigo = _correr("--dni", "36210951", "--sexo", "X")

        self.assertEqual(codigo, 1)
        self.assertIn("no es válido", salida)


@override_settings(**CON_PERSONAS)
class LinkPublicoTests(BaseDiagnosticoTests):
    """Auditoría del link: los cuatro motivos de «Formulario no disponible»."""

    @classmethod
    def setUpTestData(cls):
        cls.segmento = Segmento.objects.create(nombre="Prueba de test", cupo_maximo=100)
        cls.convocatoria = Convocatoria.objects.create(
            nombre="Test form",
            segmento=cls.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

    def setUp(self):
        super().setUp()
        self.post = patch("programas.services.personas.requests.post").start()
        self.post.return_value = _respuesta({"data": {"token": "t" * 30}})
        self.get = patch("programas.services.personas.requests.get").start()
        self.get.return_value = _respuesta(PERSONA_OK)
        self.addCleanup(patch.stopall)

    def _publico(self, **kwargs):
        ahora = timezone.now()
        datos = dict(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            territorial=None,
            fecha_asignada=ahora - timedelta(hours=1),
            fecha_hasta=ahora + timedelta(hours=1),
            cupo_maximo=100,
            zona="Resistencia",
        )
        datos.update(kwargs)
        return Relevamiento.objects.create(**datos)

    def test_link_vigente_acepta_inscripciones(self):
        rel = self._publico()

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 0)
        self.assertIn("el link ACEPTA inscripciones", salida)

    def test_detecta_que_todavia_no_empezo(self):
        rel = self._publico(
            fecha_asignada=timezone.now() + timedelta(hours=5),
            fecha_hasta=timezone.now() + timedelta(days=1),
        )

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 1)
        self.assertIn("todavía no empezó", salida)
        self.assertIn("Formulario no disponible", salida)

    def test_detecta_vencido(self):
        rel = self._publico(
            fecha_asignada=timezone.now() - timedelta(days=2),
            fecha_hasta=timezone.now() - timedelta(days=1),
        )

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 1)
        self.assertIn("vencido", salida)

    def test_detecta_pausa(self):
        rel = self._publico()
        rel.pausado = True
        rel.pausa_motivo = "Pausa de prueba"
        rel.save(update_fields=["pausado", "pausa_motivo"])

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 1)
        self.assertIn("pausado o bloqueado", salida)
        self.assertIn("Pausa de prueba", salida)

    def test_detecta_estado_que_no_es_en_curso(self):
        rel = self._publico()
        rel.estado = Relevamiento.Estado.FINALIZADO
        rel.save(update_fields=["estado"])

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 1)
        self.assertIn("solo acepta envíos En curso", salida)

    def test_busca_por_token_como_en_la_url(self):
        rel = self._publico()

        salida, _ = _correr("--token", str(rel.token_publico))

        self.assertIn(f"relevamiento #{rel.pk}", salida)

    def test_token_inexistente_es_falla(self):
        salida, codigo = _correr("--token", "11111111-1111-1111-1111-111111111111")

        self.assertEqual(codigo, 1)
        self.assertIn("ningún relevamiento público tiene el token", salida)

    def test_relevamiento_territorial_no_se_audita_como_publico(self):
        # Un público no se puede convertir en territorial (lo impide la
        # CheckConstraint tipo↔territorial), así que se crea uno de verdad.
        territorial = User.objects.create_user("terri_diag", password="x")
        rel = self._publico(tipo=Relevamiento.Tipo.TERRITORIAL, territorial=territorial)

        salida, codigo = _correr("--relevamiento", str(rel.pk))

        self.assertEqual(codigo, 1)
        self.assertIn("no es de formulario público", salida)

    def test_dni_fuera_del_padron_es_falla(self):
        rel = self._publico()
        rel.padron.create(dni="36210951", sexo="F")

        salida, codigo = _correr("--relevamiento", str(rel.pk), "--dni", "40999888", "--sexo", "M")

        self.assertEqual(codigo, 1)
        self.assertIn("NO está en el padrón", salida)

    def test_dni_en_el_padron_es_ok(self):
        rel = self._publico()
        rel.padron.create(dni="36210951", sexo="F")

        salida, codigo = _correr("--relevamiento", str(rel.pk), "--dni", "36.210.951", "--sexo", "Femenino")

        self.assertEqual(codigo, 0)
        self.assertIn("está en el padrón", salida)

    def test_informa_los_roles_que_tienen_la_capacidad(self):
        ct = ContentType.objects.get_for_model(Capacidad)
        permiso, _ = Permission.objects.get_or_create(
            content_type=ct,
            codename="becas_relevamiento_publico",
            defaults={"name": "Formulario público"},
        )
        grupo = Group.objects.create(name="Rol con formulario público")
        grupo.permissions.add(permiso)

        salida, _ = _correr()

        self.assertIn("la tienen: Rol con formulario público", salida)
