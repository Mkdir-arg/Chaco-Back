"""El helper de fechas locales: rangos semiabiertos en hora argentina (DIS-01)."""

from datetime import date, datetime
from datetime import timezone as tz_utc

from django.test import SimpleTestCase
from django.utils import timezone

from core.utils_fechas import (
    a_fecha,
    fecha_local,
    inicio_del_dia_local,
    q_rango_local,
    rango_dia_local,
    rango_periodo_local,
)

#: 23:30 del 1/9/2026 en Argentina (UTC-3), tal como se guarda.
NOCHE_DEL_1 = datetime(2026, 9, 2, 2, 30, tzinfo=tz_utc.utc)


class UtilsFechasTests(SimpleTestCase):
    def test_el_dia_empieza_a_las_00_locales_y_termina_en_el_siguiente(self):
        inicio, fin = rango_dia_local(date(2026, 9, 1))

        self.assertEqual(timezone.localtime(inicio).isoformat(), "2026-09-01T00:00:00-03:00")
        self.assertEqual(timezone.localtime(fin).isoformat(), "2026-09-02T00:00:00-03:00")

    def test_el_rango_es_semiabierto_y_cubre_el_borde_de_la_noche(self):
        """Las 23:30 ART del 1/9 están guardadas como 02:30 UTC del 2/9."""
        inicio, fin = rango_dia_local(date(2026, 9, 1))

        self.assertTrue(inicio <= NOCHE_DEL_1 < fin)
        self.assertFalse(rango_dia_local(date(2026, 9, 2))[0] <= NOCHE_DEL_1)

    def test_el_hasta_del_periodo_es_inclusivo_como_fecha(self):
        inicio, fin = rango_periodo_local(date(2026, 9, 1), date(2026, 9, 30))

        self.assertEqual(timezone.localtime(inicio).date(), date(2026, 9, 1))
        self.assertEqual(timezone.localtime(fin).isoformat(), "2026-10-01T00:00:00-03:00")

    def test_los_extremos_son_opcionales(self):
        self.assertEqual(rango_periodo_local(), (None, None))
        self.assertIsNone(rango_periodo_local(desde=date(2026, 9, 1))[1])
        self.assertIsNone(rango_periodo_local(hasta=date(2026, 9, 1))[0])

    def test_acepta_fechas_iso_y_vacios_como_los_que_llegan_de_un_request(self):
        self.assertEqual(a_fecha("2026-09-01"), date(2026, 9, 1))
        self.assertIsNone(a_fecha(""))
        self.assertIsNone(a_fecha(None))
        with self.assertRaises(ValueError):
            a_fecha("ayer")

    def test_fecha_local_de_un_datetime_guardado_en_utc(self):
        self.assertEqual(fecha_local(NOCHE_DEL_1), date(2026, 9, 1))
        self.assertIsNone(fecha_local(None))

    def test_el_q_compara_la_columna_pelada_sin_funciones(self):
        """Lo que se le manda al motor son dos parámetros, no un ``CONVERT_TZ``."""
        condicion = q_rango_local("fecha_ingreso", date(2026, 9, 1), date(2026, 9, 30))

        hijos = dict(condicion.children)
        self.assertEqual(set(hijos), {"fecha_ingreso__gte", "fecha_ingreso__lt"})
        self.assertEqual(hijos["fecha_ingreso__gte"], inicio_del_dia_local(date(2026, 9, 1)))
        self.assertEqual(hijos["fecha_ingreso__lt"], inicio_del_dia_local(date(2026, 10, 1)))

    def test_sin_extremos_el_q_no_filtra(self):
        self.assertEqual(len(q_rango_local("fecha_ingreso").children), 0)
