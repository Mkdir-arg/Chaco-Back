"""OPS-07 · Una regla de vencimiento que explota no se lleva puestas a las demás.

`procesar_vencimientos` corre en dos lugares: el cron de las 03:10 y el **arranque del
contenedor** (`LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` de `docker-compose.prod.yml`). Las
reglas se registran por app y son independientes entre sí —cerrar convocatorias vencidas
no tiene nada que ver con lo que registre Legajos mañana— pero el comando las corría en
un solo `for` sin aislar: la primera que lanzaba dejaba a las siguientes sin correr y, en
el arranque, tiraba abajo el contenedor entero (`set -eu`).

Ahora cada regla se aísla, lo que falló va al log con traceback, y el comando **igual
termina en error** al final: el cron tiene que ponerse rojo, que es la única notificación
que hay. Lo que ya no puede es decidir por las otras reglas.
"""

import logging
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from core.services import vencimientos as registro
from core.services.vencimientos import ReglaVencimiento


class _QuerysetFalso:
    def __init__(self, cantidad):
        self.cantidad = cantidad

    def count(self):
        return self.cantidad


def _regla(slug, *, pendientes=1, explota_en=None):
    """`explota_en` ∈ {None, "pendientes", "aplicar"}."""

    def _pendientes():
        if explota_en == "pendientes":
            raise RuntimeError(f"{slug}: no se pudo consultar")
        return _QuerysetFalso(pendientes)

    def _aplicar(qs):
        if explota_en == "aplicar":
            raise RuntimeError(f"{slug}: no se pudo aplicar")
        return qs.count()

    return ReglaVencimiento(slug=slug, descripcion=f"regla {slug}", pendientes=_pendientes, aplicar=_aplicar)


class ReglasAisladasTests(TestCase):
    def _correr(self, reglas, **opciones):
        salida, errores = StringIO(), StringIO()
        with patch.object(registro, "REGLAS", list(reglas)):
            with self.assertLogs("core.management.commands.procesar_vencimientos", level=logging.ERROR) as log:
                try:
                    call_command("procesar_vencimientos", stdout=salida, stderr=errores, **opciones)
                    error = None
                except CommandError as excepcion:
                    error = excepcion
        return error, salida.getvalue() + errores.getvalue(), log.output

    def test_la_regla_que_falla_no_frena_a_la_siguiente(self):
        error, texto, _ = self._correr([_regla("primera", explota_en="aplicar"), _regla("segunda", pendientes=3)])

        self.assertIn("segunda: 3 procesado(s)", texto)
        self.assertIsNotNone(error, "el comando tiene que terminar en error: el cron es la notificación")
        self.assertIn("primera", str(error))

    def test_el_traceback_va_al_log_y_no_solo_a_la_salida(self):
        _, _, log = self._correr([_regla("primera", explota_en="aplicar"), _regla("segunda")])

        self.assertTrue(any("primera" in linea for linea in log))
        self.assertTrue(any("Traceback" in linea for linea in log))

    def test_tambien_aisla_el_conteo_de_pendientes(self):
        """`pendientes()` corre fuera de la `atomic`: ahí también se puede caer."""
        error, texto, _ = self._correr([_regla("primera", explota_en="pendientes"), _regla("segunda", pendientes=2)])

        self.assertIn("segunda: 2 procesado(s)", texto)
        self.assertIn("primera", str(error))

    def test_el_dry_run_tambien_sigue_despues_de_un_error(self):
        error, texto, _ = self._correr(
            [_regla("primera", explota_en="pendientes"), _regla("segunda", pendientes=5)], dry_run=True
        )

        self.assertIn("[dry-run] segunda: 5 pendiente(s)", texto)
        self.assertIn("primera", str(error))

    def test_sin_fallas_sigue_terminando_bien(self):
        salida = StringIO()
        with patch.object(registro, "REGLAS", [_regla("primera"), _regla("segunda", pendientes=2)]):
            call_command("procesar_vencimientos", stdout=salida, stderr=StringIO())

        self.assertIn("3 registro(s) procesado(s)", salida.getvalue())
