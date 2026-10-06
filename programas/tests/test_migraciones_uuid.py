"""RED-18 · La reversa de las migraciones UUID normaliza antes de achicar.

Las cinco migraciones que ampliaron columnas UUID a ``char(36)`` (MariaDB 10.7+ tiene
UUID nativo y Django 5 manda los valores **con guiones**) vuelven achicando a
``char(32)``. Si antes no se sacan los guiones, MariaDB corta los últimos cuatro
caracteres: ``ERROR 1265 Data truncated`` con ``STRICT_TRANS_TABLES``, o —peor— un UUID
mutilado que ya no apunta a nada.

Cuatro de las cinco normalizaban **solo** si el motor tenía UUID nativo
(``has_native_uuid_field``), que es justo la condición equivocada: una base restaurada
desde otro motor trae los guiones puestos aunque ese motor no sea MariaDB. El patrón
correcto estaba desde el principio en ``programas.0073``, con su comentario explicando
por qué; acá se fija para las cinco.

La reversa real está además bloqueada por la barrera de RED-15 (D-RED-05), que aborta
antes de cualquier DDL. Estos tests llaman a las funciones ``restaurar_*``
directamente, que es el único camino que queda para verificar el **orden** del SQL sin
una base real: el contenido se verificó aparte contra MariaDB 10.11 y MySQL 8.0 (ver la
entrada del Cambio 135 en ``docs/internal/requerimientos.md``).
"""

import importlib
import re

from django.test import SimpleTestCase

# (módulo, función de reversa, columnas que achica)
REVERSAS = (
    (
        "programas.migrations.0047_ampliar_formulario_client_uuid",
        "restaurar_client_uuid_mysql",
        ("client_uuid",),
    ),
    (
        "programas.migrations.0048_ampliar_validacionsis_id_consulta",
        "restaurar_id_consulta_mysql",
        ("legajo_id", "id_consulta", "client_uuid"),
    ),
    (
        "programas.migrations.0073_ampliar_relevamiento_token_publico",
        "restaurar_token_publico_mysql",
        ("token_publico",),
    ),
    (
        "legajos.migrations.0007_ampliar_uuid_legajos",
        "restaurar_uuid_legajos_mysql",
        ("object_id", "legajo_id", "id"),
    ),
    (
        "users.migrations.0023_ampliar_solicitud_cambio_email_token",
        "restaurar_token_mysql",
        ("token",),
    ),
)

ACHICA = re.compile(r"MODIFY\s+(?P<columna>\w+)\s+char\(32\)", re.IGNORECASE)
NORMALIZA = re.compile(r"UPDATE\s+\S+\s+SET\s+(?P<columna>\w+)\s*=\s*REPLACE\(", re.IGNORECASE)


class _Features:
    def __init__(self, nativo):
        self.has_native_uuid_field = nativo


class _Conexion:
    def __init__(self, vendor, nativo):
        self.vendor = vendor
        self.features = _Features(nativo)
        self.alias = "default"


class _SchemaEditorEspia:
    """Registra el SQL en vez de ejecutarlo: lo que importa acá es el orden."""

    def __init__(self, vendor="mysql", nativo=True):
        self.connection = _Conexion(vendor, nativo)
        self.ejecutado = []

    def execute(self, sql, params=()):
        self.ejecutado.append(" ".join(sql.split()))


def _reversa(modulo, funcion):
    return getattr(importlib.import_module(modulo), funcion)


class ReversaUuidTests(SimpleTestCase):
    def _correr(self, modulo, funcion, nativo):
        espia = _SchemaEditorEspia(nativo=nativo)
        _reversa(modulo, funcion)(None, espia)
        return espia.ejecutado

    def test_reversa_uuid_normaliza_antes_de_achicar(self):
        """Con y sin UUID nativo: el ``REPLACE`` de cada columna va antes de su ``MODIFY``."""
        for modulo, funcion, columnas in REVERSAS:
            for nativo in (True, False):
                with self.subTest(migracion=modulo, has_native_uuid_field=nativo):
                    sentencias = self._correr(modulo, funcion, nativo)

                    for columna in columnas:
                        normaliza = [
                            i
                            for i, s in enumerate(sentencias)
                            if (m := NORMALIZA.search(s)) and m["columna"] == columna
                        ]
                        achica = [
                            i for i, s in enumerate(sentencias) if (m := ACHICA.search(s)) and m["columna"] == columna
                        ]
                        self.assertTrue(
                            normaliza, f"{columna}: la reversa no normaliza a hex\n" + "\n".join(sentencias)
                        )
                        self.assertTrue(achica, f"{columna}: la reversa no achica a char(32)")
                        self.assertLess(
                            normaliza[0],
                            achica[0],
                            f"{columna}: achica antes de sacar los guiones (ERROR 1265)",
                        )

    def test_la_normalizacion_solo_toca_las_filas_de_36(self):
        """Sin el filtro por longitud, un segundo intento volvería a cortar valores ya hex."""
        for modulo, funcion, _ in REVERSAS:
            with self.subTest(migracion=modulo):
                for sentencia in self._correr(modulo, funcion, nativo=True):
                    if NORMALIZA.search(sentencia):
                        self.assertIn("CHAR_LENGTH", sentencia.upper())
                        self.assertIn("= 36", sentencia)

    def test_fuera_de_mysql_la_reversa_no_hace_nada(self):
        """En SQLite la ida fue un no-op: la vuelta tampoco toca la base."""
        for modulo, funcion, _ in REVERSAS:
            with self.subTest(migracion=modulo):
                espia = _SchemaEditorEspia(vendor="sqlite")
                _reversa(modulo, funcion)(None, espia)

                self.assertEqual(espia.ejecutado, [])
