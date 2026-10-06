"""RED-18 · La reversa UUID, ejecutada contra el motor de verdad.

``programas/tests/test_migraciones_uuid.py`` fija el **orden** del SQL sin abrir
conexión (corre en todos los PRs, sobre SQLite). Acá se ejecuta: una fila con el token
en la forma larga —36 caracteres con guiones, que es lo que Django 5 escribe sobre
MariaDB 10.7+ y lo que trae cualquier base restaurada desde ahí— y la reversa de
``users.0023`` encima. Sin la normalización que agrega RED-18, el ``MODIFY … char(32)``
corta los últimos cuatro caracteres: ``ERROR 1265 Data truncated`` con
``STRICT_TRANS_TABLES`` (que es como se conecta este proyecto), o un token mutilado si
alguien lo apaga.

Lleva ``@tag("mysql")``: lo corre el job «Motor real» de `pr-performance.yml` contra
`mariadb:10.11`, `mariadb:11` y `mysql:8.0` (PR R-11, Cambio 130), donde la base de
tests se arma con las migraciones reales. En la suite normal se saltea.

Se eligió ``users_solicitudcambioemail`` entre las cinco migraciones UUID porque su fila
se crea con un ``User`` y nada más: las otras cuatro necesitan media convocatoria armada
y lo que se prueba acá es el ``ALTER``, no el dominio. El ``ALTER`` se deshace en un
``addCleanup`` registrado **antes** de la reversa, así que la columna vuelve a
``char(36)`` incluso si el test falla.
"""

import importlib
import unittest
import uuid

from django.contrib.auth.models import User
from django.db import connection
from django.test import TransactionTestCase, tag

from users.models import SolicitudCambioEmail

MIGRACION = importlib.import_module("users.migrations.0023_ampliar_solicitud_cambio_email_token")

TABLA = "users_solicitudcambioemail"


def _tipo_de_columna():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = 'token'",
            [TABLA],
        )
        return cursor.fetchone()[0].lower()


def _token_guardado(pk):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT token FROM {TABLA} WHERE id = %s", [pk])  # noqa: S608 - tabla fija
        return cursor.fetchone()[0]


@tag("mysql")
@unittest.skipUnless(connection.vendor == "mysql", "necesita MySQL/MariaDB (DJANGO_TEST_MOTOR)")
class ReversaUuidMotorRealTests(TransactionTestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="cambio-email", password="x")  # noqa: S106
        self.valor = uuid.uuid4()
        self.solicitud = SolicitudCambioEmail.objects.create(
            user=self.usuario, nuevo_email="nuevo@ejemplo.gob.ar", token=self.valor
        )
        # La forma larga, venga de donde venga la base: es el estado que RED-18 describe.
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE {TABLA} SET token = %s WHERE id = %s", [str(self.valor), self.solicitud.pk])  # noqa: S608
        self.assertEqual(len(_token_guardado(self.solicitud.pk)), 36)

    def test_la_reversa_achica_sin_truncar_el_token(self):
        self.addCleanup(self._restaurar_columna)

        with connection.schema_editor() as editor:
            MIGRACION.restaurar_token_mysql(None, editor)

        self.assertEqual(_tipo_de_columna(), "char(32)")
        self.assertEqual(_token_guardado(self.solicitud.pk), self.valor.hex)

    def _restaurar_columna(self):
        with connection.schema_editor() as editor:
            MIGRACION.ampliar_token_mysql(None, editor)
        self.assertEqual(_tipo_de_columna(), "char(36)")
