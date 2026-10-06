"""RED-15 y RED-57 · Barreras de reversa.

Ocho migraciones por las que no se vuelve, por dos motivos distintos:

- **RED-15 (UUID).** En MariaDB 10.7+ la reversa de las migraciones que achican un
  ``char(36)`` a ``char(32)`` falla a mitad de camino (errno 150 / «Data truncated») y
  deja tablas huérfanas y ``django_migrations`` a medias: un estado que no corresponde a
  ninguna release. Fuera de MySQL/MariaDB la ida ya era un no-op, así que la vuelta no
  tiene nada que romper y no se bloquea.
- **RED-57 (pérdida de datos).** ``programas.0032``, ``0056`` y ``0069`` copian o borran
  datos y vuelven con ``RunPython.noop`` o con el ``AddField`` automático: ``migrate``
  informa ``OK`` y la base queda incompleta. Eso no depende del motor, así que estas tres
  bloquean en **todos**.

Decisión D-RED-05: **barrera** — por debajo de esas migraciones solo se vuelve con
restore (runbook D.4 de ``docs/internal/processes.md``).

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
BARRERAS_UUID = (
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

# Las tres de RED-57: lo que se pierde al revertirlas son datos, no esquema.
BARRERAS_DATOS = (
    (
        "programas.migrations.0032_siis_segmento_en_subsegmento",
        "programas/migrations/0032_siis_segmento_en_subsegmento.py",
        "programas.0032",
    ),
    (
        "programas.migrations.0056_padron_convocatoria_identidad",
        "programas/migrations/0056_padron_convocatoria_identidad.py",
        "programas.0056",
    ),
    (
        "programas.migrations.0069_identificadores_siis_por_nivel",
        "programas/migrations/0069_identificadores_siis_por_nivel.py",
        "programas.0069",
    ),
)

# La lista completa del paso D.4 del runbook.
BARRERAS = BARRERAS_UUID + BARRERAS_DATOS


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

    def test_cada_barrera_declara_la_marca(self):
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

    def test_fuera_de_mysql_las_barreras_de_uuid_no_se_bloquean(self):
        """En SQLite la ida fue un no-op: no hay nada que la reversa pueda romper."""
        for modulo, _, etiqueta in BARRERAS_UUID:
            with self.subTest(migracion=etiqueta):
                espia = _SchemaEditorEspia(vendor="sqlite")
                self._barrera(modulo).reverse_code(None, espia)
                self.assertEqual(espia.ejecutado, [])

    def test_las_barreras_por_perdida_de_datos_bloquean_en_cualquier_motor(self):
        """RED-57: lo que se pierde son filas y columnas, y eso pasa igual en SQLite."""
        for modulo, _, etiqueta in BARRERAS_DATOS:
            with self.subTest(migracion=etiqueta):
                espia = _SchemaEditorEspia(vendor="sqlite")
                with self.assertRaises(IrreversibleError):
                    self._barrera(modulo).reverse_code(None, espia)
                self.assertEqual(espia.ejecutado, [])
