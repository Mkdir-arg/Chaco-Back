"""«Hoy» en hora de Chaco fuera de Dispositivos (BEC-18, y la edad de RED-50).

Los contenedores no definen `TZ`: corren en UTC. Entre las 21:00 y las 24:00 de
Argentina, `timezone.now().date()` ya devuelve **mañana**, y las pantallas que
cuentan «de hoy» contra un `DateField` en hora local —`fecha_inscripcion`, que
`auto_now_add` llena con la fecha local del proceso— salían en cero todas las
noches. Lo mismo con las antigüedades («sin evaluación hace N días») y con las
fechas de cierre, que quedaban corridas un día.

El arreglo es `timezone.localdate()` (y `core.utils_fechas.fecha_local` para pasar
un `datetime` guardado a su día local). **No** se toca el SQL: nada de `__date` ni
`Trunc*` sobre un `DateTimeField`, que en ECOM —MariaDB sin tablas de zona
horaria— se traduce a `CONVERT_TZ` y devuelve NULL (DIS-01, guardia en
`core/tests/test_sql_portable.py`).

Estos casos corren congelando el reloj a las 23:30 ART, que es la hora en la que
el bug aparecía.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as tz_utc

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.tests.reloj import reloj_en
from legajos.models import Ciudadano, LegajoAtencion
from legajos.selectors.ciudadanos import _build_ciudadanos_dashboard_metrics, buscar_ciudadanos_rapido
from programas.models import InscripcionPrograma, Programa

#: 23:30 del 30/06/2026 en Argentina = 02:30 UTC del 01/07.
NOCHE_ART = datetime(2026, 7, 1, 2, 30, tzinfo=tz_utc.utc)
DIA_LOCAL = date(2026, 6, 30)
DIA_EN_UTC = date(2026, 7, 1)


class _BaseFechas(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.ciudadano = Ciudadano.objects.create(dni="38200001", nombre="Nilda", apellido="Nocturna")
        self.programa = Programa.objects.create(codigo="BEC18", nombre="Programa BEC-18")

    def inscripcion_del_dia_local(self):
        inscripcion = InscripcionPrograma.objects.create(
            ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.ACTIVO
        )
        # `auto_now_add` ya puso la fecha del proceso: la fijamos al día local.
        InscripcionPrograma.objects.filter(pk=inscripcion.pk).update(fecha_inscripcion=DIA_LOCAL)
        return inscripcion


class ContadoresDeHoyTests(_BaseFechas):
    def test_las_inscripciones_de_hoy_se_cuentan_en_el_dia_local(self):
        self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            metricas = _build_ciudadanos_dashboard_metrics(total_ciudadanos=1)
        self.assertEqual(
            metricas["seguimientos_hoy"],
            1,
            "Con la fecha de UTC el contador «de hoy» queda en 0 entre las 21 y las 24 de Chaco.",
        )

    def test_una_inscripcion_de_ayer_no_entra(self):
        inscripcion = self.inscripcion_del_dia_local()
        InscripcionPrograma.objects.filter(pk=inscripcion.pk).update(fecha_inscripcion=DIA_LOCAL - timedelta(days=1))
        with reloj_en(NOCHE_ART):
            metricas = _build_ciudadanos_dashboard_metrics(total_ciudadanos=1)
        self.assertEqual(metricas["seguimientos_hoy"], 0)

    def test_el_contador_cacheado_del_dashboard_usa_la_misma_fecha(self):
        from dashboard.utils import contar_seguimientos_hoy

        self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            self.assertEqual(contar_seguimientos_hoy(), 1)

    def test_la_clave_de_cache_del_contador_es_la_del_dia_local(self):
        """La clave lleva la fecha: con la de UTC, a las 21:00 empezaba una clave
        nueva y vacía y el contador se reiniciaba a mitad del día de trabajo."""
        from dashboard.utils import contar_seguimientos_hoy

        self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            contar_seguimientos_hoy()
            self.assertEqual(cache.get(f"seguimientos_hoy_{DIA_LOCAL}"), 1)
            self.assertIsNone(cache.get(f"seguimientos_hoy_{DIA_EN_UTC}"))

    def test_las_metricas_de_la_api_del_inicio_cuentan_igual(self):
        from dashboard.api_views import _calcular_metricas_dashboard

        self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            datos = _calcular_metricas_dashboard()
        self.assertEqual(datos["metricas"]["seguimientos"], 1)


class EdadDelCiudadanoTests(_BaseFechas):
    """RED-50 en la búsqueda rápida del encabezado: la edad del dropdown."""

    def test_el_buscador_rapido_no_adelanta_el_cumpleanios(self):
        Ciudadano.objects.filter(pk=self.ciudadano.pk).update(fecha_nacimiento=date(2008, 7, 1))
        with reloj_en(NOCHE_ART):
            resultado = buscar_ciudadanos_rapido("38200001")
        self.assertEqual(resultado[0]["edad"], 17)

    def test_la_property_del_modelo_dice_lo_mismo(self):
        self.ciudadano.fecha_nacimiento = date(2008, 7, 1)
        with reloj_en(NOCHE_ART):
            self.assertEqual(self.ciudadano.edad, 17)

    def test_sin_fecha_de_nacimiento_la_edad_es_none(self):
        with reloj_en(NOCHE_ART):
            self.assertIsNone(self.ciudadano.edad)
            self.assertIsNone(buscar_ciudadanos_rapido("38200001")[0]["edad"])


class AntiguedadDeLegajoTests(_BaseFechas):
    def setUp(self):
        super().setUp()
        responsable = User.objects.create_user("resp-bec18", password="x")
        self.legajo = LegajoAtencion.objects.create(responsable=responsable)
        InscripcionPrograma.objects.create(ciudadano=self.ciudadano, programa=self.programa, legajo_id=self.legajo.id)
        # `fecha_apertura` y `fecha_admision` son `auto_now_add`: se corren por UPDATE.
        hace_veinte = DIA_LOCAL - timedelta(days=20)
        LegajoAtencion.objects.filter(pk=self.legajo.pk).update(fecha_apertura=hace_veinte, fecha_admision=hace_veinte)
        # Se relee entero: `inscripcion_programa` es `cached_property` y el
        # post_save del alta ya la resolvió (sin inscripción) en el objeto viejo.
        self.legajo = LegajoAtencion.objects.get(pk=self.legajo.pk)

    def test_los_dias_desde_la_admision_se_cuentan_contra_el_dia_local(self):
        with reloj_en(NOCHE_ART):
            self.assertEqual(self.legajo.dias_desde_admision, 20)

    def test_las_alertas_cuentan_los_mismos_dias(self):
        from legajos.services.alertas import AlertasService

        with reloj_en(NOCHE_ART):
            alertas = AlertasService._generar_alertas_legajo(self.legajo)
        sin_evaluacion = [a for a in alertas if a is not None and a.tipo == "SIN_EVALUACION"]
        self.assertEqual(len(sin_evaluacion), 1, [a.tipo for a in alertas if a])
        self.assertIn("20 días", sin_evaluacion[0].mensaje)


class FechaDeCierreTests(_BaseFechas):
    def test_la_baja_de_una_inscripcion_cierra_con_la_fecha_local(self):
        from legajos.services.programas import BajaProgramaService

        inscripcion = self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            BajaProgramaService.dar_de_baja(inscripcion.pk, usuario=None, motivo="Se mudó")
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.fecha_cierre, DIA_LOCAL)

    def test_el_cierre_desde_la_solapa_usa_la_misma_fecha(self):
        from programas.services.solapas import SolapasService

        inscripcion = self.inscripcion_del_dia_local()
        usuario = User.objects.create_user("op-bec18", password="x")
        with reloj_en(NOCHE_ART):
            SolapasService.cerrar_inscripcion(inscripcion, "Se mudó", usuario)
        inscripcion.refresh_from_db()
        self.assertEqual(inscripcion.fecha_cierre, DIA_LOCAL)
