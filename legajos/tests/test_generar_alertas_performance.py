"""PERF-20: lo que cuesta la pasada horaria de alertas.

`generar_alertas` corre **cada hora** en los cuatro ambientes (CronJob de k8s y
crontab de icore) y arrancaba recorriendo `Ciudadano.objects.filter(activo=True)`:
tres consultas por ciudadano —el `SELECT` de la persona, el `UPDATE` en bloque de sus
alertas MEDIA/BAJA y el `SELECT` de sus legajos, casi siempre con un `IN` vacío—
tuviera legajo o no. Medido por la auditoría con 20.200 activos de los que 200 tienen
legajo: **61.821 sentencias por corrida**, 38 s; proyectado a 40.000 ciudadanos, unas
122.000 sentencias por hora.

El costo tiene que depender de los **legajos**, no del padrón. Es lo que fijan estos
dos tests, que son la forma de la ficha: el mismo K con 10 y con 200 ciudadanos sin
legajo, y un número fijo de consultas por lote de legajos.

Medición en este mismo banco sintético (2.000 activos / 20 con legajo, SQLite en
memoria, Django 5.2.17):

| | pasada 1 | pasada en régimen |
|---|---|---|
| antes (#639) | 6.181 sentencias | 6.141 |
| después | 45 (40 son los `INSERT` de las altas) | **4** |
"""

from datetime import timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.models.contactos import HistorialContacto
from programas.models import InscripcionPrograma, Programa


@tag("performance")
class PasadaDeAlertasPerformanceTests(TestCase):
    def setUp(self):
        self.profesional = User.objects.create_user("profesional-perf20", password="x")
        self.programa = Programa.objects.create(codigo=Programa.TipoPrograma.DISPOSITIVOS, nombre="Programa PERF-20")

    # ---------------------------------------------------------------- andamios

    def _ciudadanos_sueltos(self, cuantos, *, desde):
        """Ciudadanos activos **sin** legajo: la población que la pasada vieja pagaba."""
        Ciudadano.objects.bulk_create(
            [
                Ciudadano(dni=f"7{indice:07d}", nombre="Sin", apellido=f"Legajo {indice}")
                for indice in range(desde, desde + cuantos)
            ]
        )

    def _ciudadanos_con_legajo(self, cuantos, *, desde):
        for indice in range(desde, desde + cuantos):
            ciudadano = Ciudadano.objects.create(dni=f"8{indice:07d}", nombre="Con", apellido=f"Legajo {indice}")
            legajo = LegajoAtencion.objects.create(responsable=self.profesional, plan_vigente=False)
            InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa, legajo_id=legajo.id)
            HistorialContacto.objects.create(
                legajo=legajo,
                tipo_contacto="LLAMADA",
                fecha_contacto=timezone.now() - timedelta(days=45),
                profesional=self.profesional,
                estado="EXITOSO",
                motivo="Seguimiento",
                resumen="—",
            )

    def _consultas_de_la_pasada(self):
        with CaptureQueriesContext(connection) as capturadas:
            call_command("generar_alertas", stdout=StringIO())
        return len(capturadas.captured_queries)

    # ------------------------------------------------------------------ casos

    def test_las_consultas_no_crecen_con_los_ciudadanos_sin_legajo(self):
        """El test de la ficha: el mismo K con 10 y con 200 ciudadanos sin legajo.

        Antes eran tres consultas por cada uno de los 200, así que el número crecía con
        el padrón de Becas —que no tiene legajos de atención— y no con el trabajo real.
        """
        self._ciudadanos_con_legajo(3, desde=0)
        self._ciudadanos_sueltos(10, desde=0)
        con_diez = self._consultas_de_la_pasada()

        # Se borran las alertas para que la segunda medición vuelva a ser una pasada en
        # frío: las altas son el único término que sí depende del trabajo real, y los
        # 190 ciudadanos que se agregan no traen ninguna.
        AlertaCiudadano.objects.all().delete()
        self._ciudadanos_sueltos(190, desde=10)
        con_doscientos = self._consultas_de_la_pasada()

        self.assertEqual(
            con_diez,
            con_doscientos,
            f"la pasada volvió a pagar por ciudadano: {con_diez} con 10 sin legajo y {con_doscientos} con 200",
        )

    def test_la_pasada_en_regimen_cuesta_lo_mismo_con_3_que_con_9_legajos(self):
        """N contra 3N sobre los legajos: dentro de un lote, el costo es fijo.

        En régimen —que es el 99 % de las 24 corridas diarias— no hay nada que crear ni
        que cerrar, así que la pasada son las cuatro lecturas del lote y nada más. Antes
        crecía con los legajos *y* con el padrón, y además reescribía la tabla entera.
        """
        self._ciudadanos_con_legajo(3, desde=0)
        self._consultas_de_la_pasada()
        con_tres = self._consultas_de_la_pasada()

        self._ciudadanos_con_legajo(6, desde=3)
        self._consultas_de_la_pasada()
        con_nueve = self._consultas_de_la_pasada()

        self.assertEqual(
            con_tres,
            con_nueve,
            f"la pasada en régimen volvió a pagar por legajo: {con_tres} con 3 y {con_nueve} con 9",
        )
        self.assertLessEqual(con_nueve, 6, "la pasada en régimen tiene que ser un puñado fijo de lecturas")
