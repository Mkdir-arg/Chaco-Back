"""Dispositivos cuenta y muestra los movimientos en hora local (DIS-01, DIS-08).

Los `datetime` se guardan en UTC: un ingreso de las 23:30 del 1/9 en Argentina está
guardado como 02:30 UTC del 2/9. Preguntarle la fecha al motor
(``fecha_ingreso__date``) funciona en SQLite y en el MySQL de icore, pero en ECOM
—MariaDB sin tablas de zona horaria— ``CONVERT_TZ`` devuelve NULL y el parte F-01
sale en cero (DIS-01). Y resolverlo en Python con ``valor.date()`` devuelve el día
en UTC, que para todo lo que pasa después de las 21:00 es el día siguiente (DIS-08).

Estos casos corren en SQLite, así que no reproducen la pata de MariaDB: eso lo hacen
``core/tests/test_sql_motor_real.py`` (forma del SQL compilado) y
``core/tests/test_motor_real.py`` (ejecutado contra MariaDB sin tzinfo). Lo que fijan
acá es el resultado en hora local, que es lo que el fix tiene que preservar: una
corrección que use medianoche UTC los pone en rojo.
"""

from datetime import date, datetime, timedelta
from datetime import timezone as tz_utc

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.tests.reloj import ART, reloj_en
from legajos.models import Ciudadano
from programas.models import (
    Admision,
    Cama,
    Dispositivo,
    Programa,
    RegistroDiario,
    TipoDispositivo,
)
from programas.services.indicadores import indicadores_dispositivo
from programas.services.registro_diario import calcular_cantidades
from programas.services.reportes import filtrar_dispositivos, movimientos_dispositivos

#: 23:30 del 1/9/2026 en Argentina, tal como queda guardado (UTC-3).
INGRESO_NOCTURNO = datetime(2026, 9, 2, 2, 30, tzinfo=tz_utc.utc)
DIA_LOCAL = date(2026, 9, 1)


class BaseDispositivo(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user("fechas-locales")
        self.tipo = TipoDispositivo.objects.create(codigo="FL", nombre="Hogar", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="FL-001", nombre="Hogar fechas locales", tipo=self.tipo, camas_totales=2
        )
        self.cama = Cama.objects.create(dispositivo=self.dispositivo, codigo="C-01")
        self.ciudadano = Ciudadano.objects.create(dni="38100001", nombre="Nilda", apellido="Nocturna")

    def admision(self, *, ingreso, egreso=None, cama=None):
        admision = Admision.objects.create(
            ciudadano=self.ciudadano,
            dispositivo=self.dispositivo,
            cama=cama if cama is not None else self.cama,
            fecha_ingreso=ingreso,
            fecha_egreso=egreso,
            estado=Admision.Estado.ALOJADO if egreso is None else Admision.Estado.EGRESADO,
        )
        Admision.objects.filter(pk=admision.pk).update(fecha_ingreso=ingreso, fecha_egreso=egreso)
        admision.refresh_from_db()
        return admision


class ParteDiarioFechaLocalTests(BaseDispositivo):
    """DIS-01: el parte F-01 cuenta el día **local**, sin preguntarle la fecha al motor."""

    def test_ingreso_2330_art_cuenta_en_fecha_local(self):
        self.admision(ingreso=INGRESO_NOCTURNO)

        cantidades = calcular_cantidades(dispositivo=self.dispositivo, fecha=DIA_LOCAL)

        self.assertEqual(cantidades["ingresos"], 1)
        self.assertEqual(calcular_cantidades(dispositivo=self.dispositivo, fecha=date(2026, 9, 2))["ingresos"], 0)

    def test_egreso_0030_art_cuenta_en_el_dia_siguiente(self):
        """El otro borde: 00:30 ART del 2/9 (03:30 UTC) no es movimiento del 1/9."""
        self.admision(ingreso=INGRESO_NOCTURNO, egreso=datetime(2026, 9, 2, 3, 30, tzinfo=tz_utc.utc))

        self.assertEqual(calcular_cantidades(dispositivo=self.dispositivo, fecha=DIA_LOCAL)["egresos"], 0)
        self.assertEqual(calcular_cantidades(dispositivo=self.dispositivo, fecha=date(2026, 9, 2))["egresos"], 1)

    def test_la_ocupacion_nocturna_respeta_el_cierre_del_dia_local(self):
        """Quien ingresó a las 23:30 ocupa esa noche; quien egresó a las 20:00, no."""
        self.admision(ingreso=INGRESO_NOCTURNO)
        otro = Ciudadano.objects.create(dni="38100002", nombre="Omar", apellido="Temprano")
        cama = Cama.objects.create(dispositivo=self.dispositivo, codigo="C-02")
        Admision.objects.create(
            ciudadano=otro,
            dispositivo=self.dispositivo,
            cama=cama,
            fecha_ingreso=datetime(2026, 8, 30, 15, 0, tzinfo=tz_utc.utc),
            fecha_egreso=datetime(2026, 9, 1, 23, 0, tzinfo=tz_utc.utc),  # 20:00 ART del 1/9
            estado=Admision.Estado.EGRESADO,
        )

        cantidades = calcular_cantidades(dispositivo=self.dispositivo, fecha=DIA_LOCAL)

        self.assertEqual(cantidades["ocupacion_nocturna"], 1)


class ExportMovimientosFechaLocalTests(BaseDispositivo):
    """DIS-01 y DIS-08: el export por período trae el movimiento y con su fecha local."""

    def test_export_movimientos_con_periodo_no_vacio(self):
        self.admision(ingreso=INGRESO_NOCTURNO)

        dispositivos = filtrar_dispositivos(Dispositivo.objects.all(), desde=DIA_LOCAL, hasta=DIA_LOCAL)

        self.assertEqual(list(dispositivos), [self.dispositivo])

    def test_movimiento_2230_art_se_exporta_con_fecha_local(self):
        """DIS-08: ``fecha_ingreso.date()`` es la fecha UTC, un día más que la real.

        El movimiento quedaba fuera del período (el filtro de Python lo descartaba
        aunque el SQL lo trajera) y, cuando entraba, la columna «Fecha» mostraba el
        día siguiente.
        """
        self.admision(ingreso=INGRESO_NOCTURNO)

        reporte = movimientos_dispositivos(Dispositivo.objects.all(), desde=DIA_LOCAL, hasta=DIA_LOCAL)

        self.assertEqual(len(reporte.filas), 1)
        self.assertEqual(reporte.filas[0][0], "Ingreso")
        self.assertEqual(reporte.filas[0][1], "01/09/2026")

    def test_el_egreso_tambien_se_exporta_con_su_fecha_local(self):
        self.admision(ingreso=datetime(2026, 8, 30, 15, 0, tzinfo=tz_utc.utc), egreso=INGRESO_NOCTURNO)

        reporte = movimientos_dispositivos(Dispositivo.objects.all(), desde=DIA_LOCAL, hasta=DIA_LOCAL)

        self.assertEqual([(fila[0], fila[1]) for fila in reporte.filas], [("Egreso", "01/09/2026")])


class IndicadorActualizacionFechaLocalTests(BaseDispositivo):
    """DIS-08: «última actualización» se mide contra la fecha local del parte."""

    def test_actualizacion_parte_nocturno_cuenta_en_fecha_local(self):
        Programa.objects.create(codigo=Programa.TipoPrograma.DISPOSITIVOS, nombre="Dispositivos")
        registro = RegistroDiario.objects.create(
            dispositivo=self.dispositivo,
            fecha=date(2026, 9, 9),
            turno=RegistroDiario.Turno.NOCHE,
            firmado_por=self.usuario,
        )
        # 22:30 ART del 9/9 = 01:30 UTC del 10/9: con la fecha UTC el parte parece de hoy.
        RegistroDiario.objects.filter(pk=registro.pk).update(modificado=datetime(2026, 9, 10, 1, 30, tzinfo=tz_utc.utc))

        indicadores = indicadores_dispositivo(self.dispositivo, hoy=date(2026, 9, 10))

        self.assertEqual(indicadores["actualizacion"]["dias"], 1)

    def test_un_parte_de_hoy_no_suma_dias(self):
        """Contraprueba: el que de verdad se actualizó hoy sigue dando cero.

        ``modificado`` es **ahora**, no «hace cinco minutos»: con el offset, entre las
        00:00 y las 00:05 ART ese instante cae en el día local anterior y el indicador
        devolvía 1. El test se ponía rojo cinco minutos por día, siempre de noche y
        nunca en el CI (que corre en UTC), que es la peor forma de un test flaky.
        Lo mismo vale para cualquier test que reste minutos a ``now()`` y después
        compare contra una fecha local: `test_la_medianoche_local_no_mueve_el_contador`
        es la red que lo impide.
        """
        Programa.objects.create(codigo=Programa.TipoPrograma.DISPOSITIVOS, nombre="Dispositivos")
        registro = RegistroDiario.objects.create(
            dispositivo=self.dispositivo,
            fecha=timezone.localdate(),
            turno=RegistroDiario.Turno.MANIANA,
            firmado_por=self.usuario,
        )
        RegistroDiario.objects.filter(pk=registro.pk).update(modificado=timezone.now())

        indicadores = indicadores_dispositivo(self.dispositivo)

        self.assertEqual(indicadores["actualizacion"]["dias"], 0)

    def test_la_medianoche_local_no_mueve_el_contador(self):
        """A las 00:02 ART —el borde que hacía fallar el test de arriba— sigue dando cero.

        Con el reloj congelado ahí, «hace cinco minutos» es *ayer* en hora local: si
        alguien vuelve a escribir `now() - timedelta(minutes=…)` en un test de fecha
        local, acá se ve sin esperar a la medianoche.
        """
        medianoche_pasada = datetime(2026, 9, 10, 0, 2, tzinfo=ART)
        with reloj_en(medianoche_pasada):
            Programa.objects.create(codigo=Programa.TipoPrograma.DISPOSITIVOS, nombre="Dispositivos")
            registro = RegistroDiario.objects.create(
                dispositivo=self.dispositivo,
                fecha=timezone.localdate(),
                turno=RegistroDiario.Turno.MANIANA,
                firmado_por=self.usuario,
            )
            self.assertEqual(timezone.localdate(), date(2026, 9, 10))
            RegistroDiario.objects.filter(pk=registro.pk).update(modificado=timezone.now())

            indicadores = indicadores_dispositivo(self.dispositivo)

            self.assertEqual(indicadores["actualizacion"]["dias"], 0)

            # Y la contracara: cinco minutos antes **sí** es ayer, que es exactamente lo
            # que le pasaba al test de arriba una vez por día.
            RegistroDiario.objects.filter(pk=registro.pk).update(modificado=medianoche_pasada - timedelta(minutes=5))

            self.assertEqual(indicadores_dispositivo(self.dispositivo)["actualizacion"]["dias"], 1)
