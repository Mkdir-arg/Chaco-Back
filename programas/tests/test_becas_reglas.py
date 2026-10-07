"""Reglas de negocio de Becas que dependen de «hoy» (RED-50).

RN-22 —menor de 18 ⇒ se exige apoderado— estaba escrita **cuatro** veces y tres
de las cuatro preguntaban la fecha con `date.today()`:

- `programas/services/becas.py::es_menor`
- `programas/services/condiciones.py::edad_en_anios`
- `programas/services/siis_envio.py` (`hoy = hoy or date.today()`, lo que viaja a SIIS)
- `programas/management/commands/corregir_datos_siis.py` — **la única** con
  `timezone.localdate()`

Ni el `Dockerfile`, ni los compose, ni `docker/k8s/*.yaml` definen `TZ`: los
contenedores corren en **UTC**, así que entre las 21:00 y las 24:00 de Chaco
`date.today()` ya devolvía el día siguiente. Un caso cargado a las 22:00 de la
víspera del cumpleaños 18 se evaluaba como mayor y el formulario no pedía
apoderado. No se veía en los tests porque las máquinas de desarrollo están en ART.

**Arreglado en la Ola 3 (PR 6).** La cuenta vive una sola vez en `core/edad.py`
(`edad_en_anios`, `es_menor`, `MAYORIA_DE_EDAD`) y resuelve «hoy» con
`timezone.localdate()`, que lee el `TIME_ZONE` del proyecto y no el reloj del
contenedor. `test_el_corte_es_la_fecha_local_no_la_del_sistema` perdió su
`expectedFailure` y ahora pasa de verdad; el guardarraíl para que no vuelva a
aparecer un cuarto cálculo es la regla `DTZ011` de ruff (`pyproject.toml`), que
`test_no_queda_ningun_calculo_de_edad_con_la_fecha_del_sistema` deja además
atada a los módulos concretos de esta ficha.
"""

import ast
from datetime import date, datetime
from datetime import timezone as dt_timezone
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from core.edad import MAYORIA_DE_EDAD, edad_en_anios, es_menor
from core.tests.reloj import reloj_en

#: Las 23:00 del 30 de junio en Chaco son las 02:00 del 1 de julio en UTC.
INSTANTE_UTC = datetime(2026, 7, 1, 2, 0, tzinfo=dt_timezone.utc)
#: Lo que el contenedor (UTC) cree que es hoy, y lo que de verdad es hoy acá.
HOY_DEL_CONTENEDOR = date(2026, 7, 1)
HOY_LOCAL = date(2026, 6, 30)
#: Cumple 18 el 1 de julio de 2026: la noche anterior sigue siendo menor.
NACE_EL_1_DE_JULIO = date(2008, 7, 1)

#: Los módulos donde vivía cada una de las cuatro copias de RN-22.
MODULOS_DE_LA_FICHA = (
    "programas/services/becas.py",
    "programas/services/condiciones.py",
    "programas/services/siis_envio.py",
    "programas/management/commands/corregir_datos_siis.py",
    "legajos/selectors/ciudadanos.py",
    "legajos/models/base.py",
)


class EdadHorarioTests(TestCase):
    def _noche_del_30(self):
        """Pone al proceso en las 23:00 del 30/06 local (02:00 UTC del 01/07)."""
        return reloj_en(INSTANTE_UTC)

    def test_el_reloj_del_test_simula_bien_el_contenedor_en_utc(self):
        """Control del andamio: sin esto, el test de abajo podría estar en verde
        porque el instante elegido no es una de esas tres horas."""
        with self._noche_del_30():
            self.assertEqual(timezone.localdate(), HOY_LOCAL)
            self.assertEqual(timezone.now().date(), HOY_DEL_CONTENEDOR)
            self.assertNotEqual(timezone.localdate(), timezone.now().date())

    def test_el_corte_es_la_fecha_local_no_la_del_sistema(self):
        """RED-50: quien cumple 18 el 01/07 sigue siendo menor a las 23:00 del 30/06,
        aunque para el reloj del contenedor (UTC) ya sea el 01/07."""
        with self._noche_del_30():
            self.assertTrue(
                es_menor(NACE_EL_1_DE_JULIO),
                "`es_menor` cumplió años en UTC: RN-22 deja de pedir apoderado una noche antes.",
            )
            self.assertEqual(
                edad_en_anios(NACE_EL_1_DE_JULIO),
                17,
                "`edad_en_anios` cuenta un año de más entre las 21:00 y las 24:00 de Chaco.",
            )

    def test_la_cuenta_de_anios_es_correcta_cuando_le_dan_el_dia(self):
        """La aritmética no está en discusión: lo único que cambió es de dónde
        sale `hoy` cuando no se lo pasan."""
        for hoy, esperado_edad, esperado_menor in (
            (HOY_LOCAL, 17, True),
            (HOY_DEL_CONTENEDOR, 18, False),
        ):
            with self.subTest(hoy=hoy.isoformat()):
                self.assertEqual(edad_en_anios(NACE_EL_1_DE_JULIO, hoy=hoy), esperado_edad)
                self.assertEqual(es_menor(NACE_EL_1_DE_JULIO, hoy=hoy), esperado_menor)

    def test_sin_fecha_de_nacimiento_no_se_inventa_una_edad(self):
        """RN-22 no se puede evaluar sin la fecha: `None`, nunca `0` ni `False`."""
        self.assertIsNone(es_menor(None))
        self.assertIsNone(edad_en_anios(None))
        self.assertIsNone(edad_en_anios(""))
        self.assertIsNone(edad_en_anios("no es una fecha"))

    def test_la_mayoria_de_edad_se_lee_de_un_solo_lugar(self):
        """El 18 dejó de estar escrito al lado de cada comparación: los dos módulos
        que lo usaban importan la misma constante."""
        from programas.management.commands import corregir_datos_siis
        from programas.services import siis_envio

        self.assertEqual(MAYORIA_DE_EDAD, 18)
        self.assertIs(siis_envio.MAYORIA_DE_EDAD, MAYORIA_DE_EDAD)
        self.assertIs(corregir_datos_siis.MAYORIA_DE_EDAD, MAYORIA_DE_EDAD)


class SinCalculoDeEdadPropioTests(SimpleTestCase):
    """Ratchet de la unificación: la cuenta de RN-22 no vuelve a escribirse a mano.

    `DTZ011` ya prohíbe `date.today()` en todo el código productivo; esto cubre el
    otro medio camino, que es copiar la resta de años con un `hoy` que venga de
    cualquier lado. Si mañana alguien la reescribe en uno de los módulos de la
    ficha, este test lo nombra con su archivo y su línea.
    """

    #: La forma de la cuenta: `(hoy.month, hoy.day) < (nacimiento.month, nacimiento.day)`.
    def _tiene_la_resta_de_cumpleanios(self, nodo):
        if not isinstance(nodo, ast.Compare) or len(nodo.ops) != 1:
            return False
        if not isinstance(nodo.ops[0], ast.Lt):
            return False
        izq, der = nodo.left, nodo.comparators[0]
        if not (isinstance(izq, ast.Tuple) and isinstance(der, ast.Tuple)):
            return False
        atributos = {n.attr for lado in (izq, der) for n in ast.walk(lado) if isinstance(n, ast.Attribute)}
        return {"month", "day"} <= atributos

    def test_no_queda_ningun_calculo_de_edad_con_la_fecha_del_sistema(self):
        raiz = Path(settings.BASE_DIR)
        copias = []
        for relativo in MODULOS_DE_LA_FICHA:
            archivo = raiz / relativo
            self.assertTrue(archivo.is_file(), f"{relativo} se movió: actualizá la lista de la ficha RED-50.")
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                if self._tiene_la_resta_de_cumpleanios(nodo):
                    copias.append(f"{relativo}:{nodo.lineno}")
        self.assertEqual(
            copias,
            [],
            f"RN-22 volvió a escribirse a mano. La cuenta vive en `core.edad.edad_en_anios`: {', '.join(copias)}",
        )

    def test_el_detector_ve_la_cuenta_cuando_esta(self):
        """Control del andamio: con un detector que no detecta nada, el ratchet
        de arriba pasaría solo."""
        fuente = (
            "def edad(nacimiento, hoy):\n"
            "    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))\n"
        )
        encontrados = [n for n in ast.walk(ast.parse(fuente)) if self._tiene_la_resta_de_cumpleanios(n)]
        self.assertEqual(len(encontrados), 1)
