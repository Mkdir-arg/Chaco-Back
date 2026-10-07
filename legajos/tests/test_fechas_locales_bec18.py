"""«Hoy» en hora de Chaco fuera de Dispositivos (BEC-18, y la edad de RED-50).

Los contenedores no definen `TZ`: corren en **UTC**. Entre las 21:00 y las 24:00 de
Argentina eso rompe las fechas por **las dos puntas**, y hay que arreglar las dos o
el bug cambia de lado:

* **Al leer.** `timezone.now().date()` ya devuelve mañana, así que los contadores
  «de hoy» preguntaban por un día que todavía no empezó y salían en cero.
* **Al escribir.** `DateField(auto_now_add=True)` guarda `datetime.date.today()`,
  que es la fecha del **proceso**, no la del `TIME_ZONE` del proyecto: una
  inscripción de las 22:00 nacía con fecha de mañana. Comparar esa columna contra
  `timezone.localdate()` la deja afuera igual —solo que ahora por el otro lado—.

Por eso los `DateField` que registran «el día en que pasó» (`fecha_inscripcion`,
`fecha_apertura`, `fecha_admision`, `fecha_asignacion`, `fecha_ingreso`) se escriben
con `default=timezone.localdate`, que es la misma función con la que se los consulta.
Los `DateTimeField` no se tocan: guardan un instante absoluto en UTC y están bien.

El resto del arreglo es `timezone.localdate()` al leer (y `core.utils_fechas.fecha_local`
para pasar un `datetime` guardado a su día local). **No** se toca el SQL: nada de
`__date` ni `Trunc*` sobre un `DateTimeField`, que en ECOM —MariaDB sin tablas de zona
horaria— se traduce a `CONVERT_TZ` y devuelve NULL (DIS-01, guardia en
`core/tests/test_sql_portable.py`).

Estos casos congelan el reloj a las 23:30 ART, que es la hora en la que el bug
aparecía. El instante está en el pasado a propósito: así `timezone.localdate()`
—congelada— nunca coincide con `datetime.date.today()` —la fecha real de la máquina—,
y el test distingue las dos fuentes en cualquier zona horaria, sin depender de dónde
corra.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as tz_utc

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from core.tests.reloj import reloj_en
from legajos.models import Ciudadano, LegajoAtencion
from legajos.selectors.ciudadanos import _build_ciudadanos_dashboard_metrics, buscar_ciudadanos_rapido
from programas.models import (
    AsignacionCoordinador,
    AsignacionReferente,
    AsignacionTerritorial,
    InscripcionPrograma,
    ListaEspera,
    Programa,
)

#: Los `DateField` que registran «el día en que pasó» (BEC-18).
CAMPOS_DE_FECHA_LOCAL = (
    (InscripcionPrograma, "fecha_inscripcion"),
    (LegajoAtencion, "fecha_apertura"),
    (LegajoAtencion, "fecha_admision"),
    (AsignacionCoordinador, "fecha_asignacion"),
    (AsignacionReferente, "fecha_asignacion"),
    (AsignacionTerritorial, "fecha_asignacion"),
    (ListaEspera, "fecha_ingreso"),
)

#: 23:30 del 30/06/2026 en Argentina = 02:30 UTC del 01/07.
NOCHE_ART = datetime(2026, 7, 1, 2, 30, tzinfo=tz_utc.utc)
DIA_LOCAL = date(2026, 6, 30)
DIA_EN_UTC = date(2026, 7, 1)

#: Las apps del repo (el barrido ignora `auth`, `contenttypes` y demás de Django).
APPS_DEL_REPO = ("conversaciones", "configuracion", "core", "dashboard", "legajos", "portal", "programas", "users")


class _BaseFechas(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.ciudadano = Ciudadano.objects.create(dni="38200001", nombre="Nilda", apellido="Nocturna")
        self.programa = Programa.objects.create(codigo="BEC18", nombre="Programa BEC-18")

    def inscripcion_del_dia_local(self):
        """Un alta hecha a las 23:30 ART, con el reloj del proyecto congelado ahí.

        No se corrige la fecha con un `UPDATE`: que quede en `DIA_LOCAL` es
        justamente lo que estos tests verifican.
        """
        with reloj_en(NOCHE_ART):
            return InscripcionPrograma.objects.create(
                ciudadano=self.ciudadano, programa=self.programa, estado=InscripcionPrograma.Estado.ACTIVO
            )


class FechaDeAltaEnDiaLocalTests(_BaseFechas):
    """La mitad de escritura de BEC-18: el día que se guarda es el **local**.

    Es la premisa de la que cuelga todo el resto: si la columna se escribe con la
    fecha del proceso, leerla con `timezone.localdate()` no arregla nada, solo
    cambia de lado el día que se pierde.
    """

    def test_el_alta_de_las_2230_queda_con_la_fecha_local_y_no_con_la_del_proceso(self):
        inscripcion = self.inscripcion_del_dia_local()
        self.assertEqual(
            inscripcion.fecha_inscripcion,
            DIA_LOCAL,
            "`auto_now_add` guarda `date.today()`: la fila nace con la fecha del proceso.",
        )
        self.assertNotEqual(
            inscripcion.fecha_inscripcion,
            date.today(),
            "El reloj congelado está en el pasado: si coinciden, la fecha salió del proceso.",
        )

    def test_el_legajo_tambien_se_abre_y_se_admite_en_el_dia_local(self):
        responsable = User.objects.create_user("resp-alta-bec18", password="x")
        with reloj_en(NOCHE_ART):
            legajo = LegajoAtencion.objects.create(responsable=responsable)
        self.assertEqual(legajo.fecha_apertura, DIA_LOCAL)
        self.assertEqual(legajo.fecha_admision, DIA_LOCAL)

    def test_lo_escrito_y_lo_leido_salen_de_la_misma_funcion(self):
        """El alta de las 23:30 se cuenta como «hoy» en esa misma ventana.

        Con `auto_now_add` la fila quedaba en el día del proceso y el contador
        —que pregunta por `timezone.localdate()`— no la veía nunca.
        """
        self.inscripcion_del_dia_local()
        with reloj_en(NOCHE_ART):
            metricas = _build_ciudadanos_dashboard_metrics(total_ciudadanos=1)
        self.assertEqual(metricas["seguimientos_hoy"], 1)

    def test_ningun_datefield_del_dominio_vuelve_a_auto_now(self):
        """Ratchet: `auto_now`/`auto_now_add` en un `DateField` es la fecha del proceso.

        Vale para cualquier modelo del repo, no solo para los que hoy se comparan
        con «hoy»: una columna que dice «el día en que pasó» y guarda el día de UTC
        ya está mal aunque todavía nadie la filtre. En un `DateTimeField` no hay
        problema —guarda un instante absoluto—, así que el barrido los ignora.
        """
        from django.apps import apps
        from django.db import models

        culpables = []
        for modelo in apps.get_models():
            if not modelo._meta.app_label.startswith(APPS_DEL_REPO):
                continue
            for campo in modelo._meta.local_fields:
                if type(campo) is not models.DateField:
                    continue
                if getattr(campo, "auto_now", False) or getattr(campo, "auto_now_add", False):
                    culpables.append(f"{modelo._meta.label}.{campo.name}")
        self.assertEqual(
            culpables,
            [],
            "Estos `DateField` guardan la fecha del proceso (UTC en los contenedores). "
            f"Van con `default=timezone.localdate`: {', '.join(culpables)}",
        )

    def test_los_campos_de_la_ficha_usan_la_fecha_local(self):
        """El ratchet de arriba mira la forma; este nombra los campos de la ficha,
        para que un renombre no lo deje mirando al vacío."""
        from django.utils import timezone as tz

        for modelo, nombre in CAMPOS_DE_FECHA_LOCAL:
            with self.subTest(campo=f"{modelo.__name__}.{nombre}"):
                campo = modelo._meta.get_field(nombre)
                self.assertIs(campo.default, tz.localdate)
                self.assertFalse(campo.editable, "Era `auto_now_add`: no puede pasar a editable.")


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
        # El legajo se abre veinte días antes, con el reloj puesto ahí: el `default`
        # del campo lo escribe solo, sin `UPDATE` que corrija la fecha.
        hace_veinte = NOCHE_ART - timedelta(days=20)
        with reloj_en(hace_veinte):
            self.legajo = LegajoAtencion.objects.create(responsable=responsable)
        InscripcionPrograma.objects.create(ciudadano=self.ciudadano, programa=self.programa, legajo_id=self.legajo.id)
        self.assertEqual(self.legajo.fecha_apertura, DIA_LOCAL - timedelta(days=20))
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
