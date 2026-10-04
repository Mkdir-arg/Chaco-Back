"""RED-15 · Barreras de reversa de las migraciones UUID.

En MariaDB 10.7+ la reversa de las migraciones que achican un ``char(36)`` a
``char(32)`` falla a mitad de camino (errno 150 / «Data truncated») y deja tablas
huérfanas y ``django_migrations`` a medias: un estado que no corresponde a ninguna
release. Decisión D-RED-05: **barrera** — por debajo de esas migraciones solo se
vuelve con restore (runbook D.4 de ``docs/internal/processes.md``).

Estos tests fijan las dos mitades de la barrera: la marca legible en el archivo y
que la reversa aborte **antes** de tocar la base.
"""

import importlib
from pathlib import Path

from django.db.migrations import RunPython
from django.db.migrations.exceptions import IrreversibleError
from django.test import SimpleTestCase

RAIZ = Path(__file__).resolve().parents[2]

MARCA = "# BARRERA-DE-REVERSA:"

# (módulo importable, ruta del archivo, etiqueta tal como aparece en el runbook D.4)
BARRERAS = (
    (
        "programas.migrations.0047_ampliar_formulario_client_uuid",
        "programas/migrations/0047_ampliar_formulario_client_uuid.py",
        "programas.0047",
    ),
    (
        "programas.migrations.0048_ampliar_validacionsis_id_consulta",
        "programas/migrations/0048_ampliar_validacionsis_id_consulta.py",
        "programas.0048",
    ),
    (
        "programas.migrations.0073_ampliar_relevamiento_token_publico",
        "programas/migrations/0073_ampliar_relevamiento_token_publico.py",
        "programas.0073",
    ),
    (
        "legajos.migrations.0007_ampliar_uuid_legajos",
        "legajos/migrations/0007_ampliar_uuid_legajos.py",
        "legajos.0007",
    ),
    (
        "users.migrations.0023_ampliar_solicitud_cambio_email_token",
        "users/migrations/0023_ampliar_solicitud_cambio_email_token.py",
        "users.0023",
    ),
)


class _ConexionEspia:
    def __init__(self, vendor):
        self.vendor = vendor
        self.alias = "default"


class _SchemaEditorEspia:
    """Registra el SQL en vez de ejecutarlo: si la barrera deja pasar algo, se ve."""

    def __init__(self, vendor="mysql"):
        self.connection = _ConexionEspia(vendor)
        self.ejecutado = []

    def execute(self, sql, params=()):
        self.ejecutado.append(sql)


class BarrerasDeReversaTests(SimpleTestCase):
    def _barrera(self, modulo):
        operaciones = importlib.import_module(modulo).Migration.operations
        return operaciones[-1]

    def test_cada_migracion_uuid_declara_la_marca(self):
        """La marca es lo que lee una persona (y el gate de RED-14) al abrir el archivo."""
        for _, ruta, etiqueta in BARRERAS:
            with self.subTest(migracion=etiqueta):
                contenido = (RAIZ / ruta).read_text(encoding="utf-8")
                self.assertTrue(MARCA in contenido, f"{ruta} no declara la marca {MARCA}")

    def test_la_barrera_es_la_ultima_operacion(self):
        """Django desaplica en orden inverso: la última es la primera de la reversa."""
        for modulo, _, etiqueta in BARRERAS:
            with self.subTest(migracion=etiqueta):
                operacion = self._barrera(modulo)
                self.assertIsInstance(operacion, RunPython)
                self.assertEqual(operacion.reverse_code.__name__, "bloquear_reversa")

    def test_la_reversa_aborta_sin_tocar_la_base(self):
        for modulo, _, etiqueta in BARRERAS:
            with self.subTest(migracion=etiqueta):
                espia = _SchemaEditorEspia(vendor="mysql")
                with self.assertRaises(IrreversibleError) as capturado:
                    self._barrera(modulo).reverse_code(None, espia)
                self.assertEqual(espia.ejecutado, [], "la barrera ejecutó SQL antes de abortar")
                mensaje = str(capturado.exception)
                self.assertIn(etiqueta, mensaje)
                self.assertIn("D.4", mensaje)

    def test_la_barrera_no_hace_nada_hacia_adelante(self):
        for modulo, _, etiqueta in BARRERAS:
            with self.subTest(migracion=etiqueta):
                espia = _SchemaEditorEspia(vendor="mysql")
                self._barrera(modulo).code(None, espia)
                self.assertEqual(espia.ejecutado, [])

    def test_fuera_de_mysql_la_reversa_no_se_bloquea(self):
        """En SQLite la ida fue un no-op: no hay nada que la reversa pueda romper."""
        for modulo, _, etiqueta in BARRERAS:
            with self.subTest(migracion=etiqueta):
                espia = _SchemaEditorEspia(vendor="sqlite")
                self._barrera(modulo).reverse_code(None, espia)
                self.assertEqual(espia.ejecutado, [])
