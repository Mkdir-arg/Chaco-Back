"""Reglas de negocio de Becas que dependen de «hoy» (RED-50).

RN-22 —menor de 18 ⇒ se exige apoderado— está escrita **cuatro veces** y tres de
las cuatro preguntan la fecha con `date.today()`:

- `programas/services/becas.py::es_menor`
- `programas/services/condiciones.py::edad_en_anios`
- `programas/services/siis_envio.py` (`hoy = hoy or date.today()`, lo que viaja a SIIS)
- `programas/management/commands/corregir_datos_siis.py` — **la única** con
  `timezone.localdate()`

Ni el `Dockerfile`, ni los compose, ni `docker/k8s/*.yaml` definen `TZ`: los
contenedores corren en **UTC**, así que entre las 21:00 y las 24:00 de Chaco
`date.today()` ya devuelve el día siguiente. Un caso cargado a las 22:00 de la
víspera del cumpleaños 18 se evalúa como mayor y el formulario no pide apoderado.
No se ve en los tests porque las máquinas de desarrollo están en ART.

El arreglo es de la **Ola 3**: una sola `edad_en_anios(fecha, hoy=None)` con
`hoy = hoy or timezone.localdate()`, `MAYORIA_DE_EDAD = 18` en un solo lugar y la
regla `DTZ011` de flake8-datetimez para `programas/`, `legajos/` y `portal/`.
Hasta entonces `test_el_corte_es_la_fecha_local_no_la_del_sistema` queda en
`expectedFailure`: describe el bug, y el día que la Ola 3 lo arregle el test pasa
a *unexpected success* y hay que sacarle el decorador.
"""

import unittest
from contextlib import ExitStack
from datetime import date, datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from programas.services.becas import es_menor
from programas.services.condiciones import edad_en_anios

#: Las 23:00 del 30 de junio en Chaco son las 02:00 del 1 de julio en UTC.
INSTANTE_UTC = datetime(2026, 7, 1, 2, 0, tzinfo=dt_timezone.utc)
#: Lo que el contenedor (UTC) cree que es hoy, y lo que de verdad es hoy acá.
HOY_DEL_CONTENEDOR = date(2026, 7, 1)
HOY_LOCAL = date(2026, 6, 30)
#: Cumple 18 el 1 de julio de 2026: la noche anterior sigue siendo menor.
NACE_EL_1_DE_JULIO = date(2008, 7, 1)

#: Los módulos que resuelven «hoy» con el `date` que importaron.
MODULOS_CON_DATE = (
    "programas.services.becas",
    "programas.services.condiciones",
    "programas.services.siis_envio",
    "legajos.selectors.ciudadanos",
)


class _FechaDelContenedor(date):
    """`date` cuyo `today()` contesta lo que contestaría un contenedor en UTC."""

    @classmethod
    def today(cls):
        return HOY_DEL_CONTENEDOR


class EdadHorarioTests(TestCase):
    def _noche_del_30(self):
        """Pone al proceso en las 23:00 del 30/06 local (02:00 UTC del 01/07)."""
        pila = ExitStack()
        pila.enter_context(patch.object(timezone, "now", return_value=INSTANTE_UTC))
        for modulo in MODULOS_CON_DATE:
            pila.enter_context(patch(f"{modulo}.date", _FechaDelContenedor))
        return pila

    def test_el_reloj_del_test_simula_bien_el_contenedor_en_utc(self):
        """Control del andamio: sin esto, el `expectedFailure` de abajo podría
        estar fallando porque el parche no hace lo que dice."""
        from programas.services import becas as servicio_becas

        with self._noche_del_30():
            self.assertEqual(timezone.localdate(), HOY_LOCAL)
            self.assertEqual(servicio_becas.date.today(), HOY_DEL_CONTENEDOR)
            self.assertNotEqual(timezone.localdate(), servicio_becas.date.today())

    @unittest.expectedFailure
    def test_el_corte_es_la_fecha_local_no_la_del_sistema(self):
        """RED-50 (hoy ROJO): las tres implementaciones de RN-22 usan el día del
        sistema, que en el contenedor es el de UTC.

        Cuando la Ola 3 unifique la edad en `timezone.localdate()` este test pasa
        a *unexpected success*: hay que sacarle el `expectedFailure`.
        """
        with self._noche_del_30():
            self.assertTrue(
                es_menor(NACE_EL_1_DE_JULIO),
                "`es_menor` ya cumplió años en UTC: RN-22 deja de pedir apoderado una noche antes.",
            )
            self.assertEqual(
                edad_en_anios(NACE_EL_1_DE_JULIO),
                17,
                "`edad_en_anios` cuenta un año de más entre las 21:00 y las 24:00 de Chaco.",
            )

    def test_la_cuenta_de_anios_es_correcta_cuando_le_dan_el_dia(self):
        """La aritmética no está en discusión y tiene que sobrevivir a la Ola 3:
        lo único que cambia es de dónde sale `hoy`."""
        for hoy, esperado_edad, esperado_menor in (
            (HOY_LOCAL, 17, True),
            (HOY_DEL_CONTENEDOR, 18, False),
        ):
            with self.subTest(hoy=hoy.isoformat()):
                self.assertEqual(edad_en_anios(NACE_EL_1_DE_JULIO, hoy=hoy), esperado_edad)
                self.assertEqual(es_menor(NACE_EL_1_DE_JULIO, referencia=hoy), esperado_menor)

    def test_sin_fecha_de_nacimiento_no_se_inventa_una_edad(self):
        """RN-22 no se puede evaluar sin la fecha: `None`, nunca `0` ni `False`."""
        self.assertIsNone(es_menor(None))
        self.assertIsNone(edad_en_anios(None))
        self.assertIsNone(edad_en_anios(""))
