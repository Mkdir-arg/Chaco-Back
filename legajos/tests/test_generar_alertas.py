"""`generar_alertas`: la pasada horaria que no tenía un solo test (TST-02).

Ítem 3 del Top-5 de tests faltantes por valor. Medido el 04-oct-2026:
`legajos/management/commands/generar_alertas.py` al **0 %** y
`legajos/services/alertas.py` al **35 %**, con el comando corriendo **cada hora** en
los cuatro ambientes (cron de k8s y crontab de icore) y escribiendo alertas que
después manda por WebSocket a todo el backoffice.

Lo que fija este módulo es el contrato de la pasada:

* una alerta se genera cuando corresponde (umbral de 30 días sin contacto);
* **dos pasadas seguidas no duplican** nada (idempotencia: es lo que la vuelve apta
  para cron);
* la alerta MEDIA/BAJA que ya no aplica se **desactiva** en vez de quedar colgada;
* un ciudadano sin legajo no rompe la pasada entera;
* el WebSocket sale **una vez por alerta nueva**, no una por pasada (LEG-01: la
  re-notificación es lo que convertía esto en una ráfaga).

El costo de la pasada (PERF-20) se mide en `test_generar_alertas_performance`: acá se
prueba comportamiento. La clase `ReconciliacionDeAlertasTests` fija lo que agregó
LEG-01 (Ola 4 PR 4): la pasada **reconcilia** en vez de apagar y recrear.

Detalle del dominio que no se ve leyendo el servicio: `LegajoAtencion.ciudadano` es
una **property** que resuelve por `InscripcionPrograma` (`services/linking.py`), así
que un legajo sin inscripción no tiene ciudadano y la pasada no lo ve. Por eso cada
caso arma el trío ciudadano + programa + inscripción.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.models.contactos import HistorialContacto
from legajos.services.alertas import AlertasService
from programas.models import InscripcionPrograma, Programa


class BaseAlertasTestCase(TestCase):
    """Andamios compartidos: el trío ciudadano + programa + inscripción y la pasada."""

    def setUp(self):
        self.profesional = User.objects.create_user("profesional-alertas", password="x")
        self.programa = Programa.objects.create(codigo=Programa.TipoPrograma.DISPOSITIVOS, nombre="Programa de alertas")

    # ---------------------------------------------------------------- andamios

    def _ciudadano_con_legajo(self, dni="30111222", *, estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=True):
        """Ciudadano + legajo enlazados, con el legajo abierto hace poco.

        `fecha_apertura` es `auto_now_add`: se retrocede con `update()` solo cuando el
        caso lo necesita. Acá queda en hoy para que **no** dispare la alerta
        `SIN_EVALUACION` (umbral: 15 días) y cada test mida una sola cosa.
        """
        ciudadano = Ciudadano.objects.create(dni=dni, nombre="Ana", apellido="Alerta")
        legajo = LegajoAtencion.objects.create(responsable=self.profesional, estado=estado, plan_vigente=plan_vigente)
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa, legajo_id=legajo.id)
        return ciudadano, legajo

    def _contacto(self, legajo, *, hace_dias, estado="EXITOSO"):
        return HistorialContacto.objects.create(
            legajo=legajo,
            tipo_contacto="LLAMADA",
            fecha_contacto=timezone.now() - timedelta(days=hace_dias),
            profesional=self.profesional,
            estado=estado,
            motivo="Seguimiento",
            resumen="—",
        )

    def _pasada(self):
        salida = StringIO()
        call_command("generar_alertas", stdout=salida)
        return salida.getvalue()

    def _activas(self, ciudadano, tipo=None):
        qs = AlertaCiudadano.objects.filter(ciudadano=ciudadano, activa=True)
        return qs.filter(tipo=tipo) if tipo else qs


class GenerarAlertasTests(BaseAlertasTestCase):
    # ------------------------------------------------------------------ casos

    def test_un_ciudadano_sin_contacto_reciente_genera_su_alerta(self):
        ciudadano, legajo = self._ciudadano_con_legajo()
        self._contacto(legajo, hace_dias=45)

        self._pasada()

        alerta = self._activas(ciudadano, "SIN_CONTACTO").get()
        self.assertEqual(alerta.prioridad, "ALTA")
        self.assertIn("45", alerta.mensaje)

    def test_un_contacto_dentro_del_umbral_no_genera_alerta(self):
        """Control del andamio: sin esto, el test de arriba pasaría igual con el
        umbral roto (cualquier contacto generaría la alerta)."""
        ciudadano, legajo = self._ciudadano_con_legajo()
        self._contacto(legajo, hace_dias=10)

        self._pasada()

        self.assertFalse(self._activas(ciudadano, "SIN_CONTACTO").exists())

    def test_dos_pasadas_seguidas_no_duplican_la_alerta(self):
        """Es lo que vuelve a la pasada apta para un cron horario.

        Sin esto, 24 corridas por día dejarían 24 filas por ciudadano y 24 avisos por
        WebSocket.
        """
        ciudadano, legajo = self._ciudadano_con_legajo()
        self._contacto(legajo, hace_dias=45)

        self._pasada()
        primera = list(self._activas(ciudadano).values_list("id", flat=True))
        self._pasada()

        self.assertEqual(list(self._activas(ciudadano).values_list("id", flat=True)), primera)
        self.assertEqual(AlertaCiudadano.objects.filter(ciudadano=ciudadano).count(), len(primera))

    def test_la_alerta_que_ya_no_aplica_se_desactiva(self):
        """La MEDIA/BAJA que dejó de aplicar se cierra. Acá: el legajo gana su plan,
        así que `SIN_PLAN` deja de corresponder."""
        ciudadano, legajo = self._ciudadano_con_legajo(estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=False)

        self._pasada()
        sin_plan = self._activas(ciudadano, "SIN_PLAN").get()

        LegajoAtencion.objects.filter(pk=legajo.pk).update(plan_vigente=True)
        self._pasada()

        sin_plan.refresh_from_db()
        self.assertFalse(sin_plan.activa)
        self.assertFalse(self._activas(ciudadano, "SIN_PLAN").exists())

    def test_una_alerta_alta_no_se_apaga_sola(self):
        """La contracara: el cierre automático es **solo** MEDIA/BAJA.

        Si alguien ampliara el cierre a todas las prioridades, una `RIESGO_ALTO` se
        apagaría en cada pasada y volvería a notificarse: ruido permanente.
        """
        ciudadano, legajo = self._ciudadano_con_legajo()
        LegajoAtencion.objects.filter(pk=legajo.pk).update(nivel_riesgo="ALTO")

        self._pasada()
        riesgo = self._activas(ciudadano, "RIESGO_ALTO").get()
        self._pasada()
        riesgo.refresh_from_db()

        self.assertTrue(riesgo.activa)

    def test_un_ciudadano_sin_legajo_no_rompe_la_pasada(self):
        """El comando recorre **todos** los ciudadanos activos, tengan legajo o no."""
        huerfano = Ciudadano.objects.create(dni="30999888", nombre="Sin", apellido="Legajo")
        con_legajo, legajo = self._ciudadano_con_legajo(dni="30111333")
        self._contacto(legajo, hace_dias=45)

        salida = self._pasada()

        self.assertFalse(AlertaCiudadano.objects.filter(ciudadano=huerfano).exists())
        self.assertTrue(self._activas(con_legajo, "SIN_CONTACTO").exists())
        self.assertIn("Alertas activas tras la pasada", salida)

    def test_el_envio_por_websocket_se_llama_una_vez_por_alerta_nueva(self):
        """LEG-01: el aviso sale al **crear**, no en cada pasada.

        El parche va sobre `_enviar_notificacion_alerta` —no sobre el channel layer—
        porque es el borde que decide *cuándo* se avisa; lo que mande adentro es otro
        contrato (`test_alertas_websocket_escape`).
        """
        ciudadano, legajo = self._ciudadano_con_legajo()
        self._contacto(legajo, hace_dias=45)

        with patch.object(AlertasService, "_enviar_notificacion_alerta") as enviar:
            self._pasada()
            llamadas_primera = enviar.call_count
            self._pasada()
            llamadas_segunda = enviar.call_count

        nuevas = self._activas(ciudadano).count()
        self.assertEqual(llamadas_primera, nuevas)
        self.assertEqual(
            llamadas_segunda,
            llamadas_primera,
            "la segunda pasada no crea alertas nuevas: tampoco tiene que volver a avisar",
        )

    def test_un_ciudadano_inactivo_queda_fuera_de_la_pasada(self):
        ciudadano, legajo = self._ciudadano_con_legajo()
        self._contacto(legajo, hace_dias=45)
        Ciudadano.objects.filter(pk=ciudadano.pk).update(activo=False)

        self._pasada()

        self.assertFalse(AlertaCiudadano.objects.filter(ciudadano=ciudadano).exists())


class ReconciliacionDeAlertasTests(BaseAlertasTestCase):
    """LEG-01 (Ola 4 PR 4): la pasada reconcilia, no apaga y recrea.

    Antes, cada corrida empezaba con un ``update(activa=False)`` sobre **todas** las
    MEDIA/BAJA del ciudadano y después volvía a crearlas: una fila nueva por hora, un
    aviso por WebSocket por hora a todo el que estuviera conectado y una tabla que
    crecía sin techo (200 → 510 → 610 en dos corridas del seed de la auditoría).
    """

    def test_la_segunda_pasada_no_escribe_ni_una_fila(self):
        """La idempotencia medida donde se ve: en el SQL.

        `test_dos_pasadas_seguidas_no_duplican_la_alerta` mira el resultado; esto mira
        que para llegar a ese resultado no se toque la tabla. Antes: un `UPDATE` por
        ciudadano activo más un `INSERT` por alerta MEDIA, en cada corrida.
        """
        _, legajo = self._ciudadano_con_legajo(estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=False)
        self._contacto(legajo, hace_dias=45)

        self._pasada()
        with CaptureQueriesContext(connection) as capturadas:
            self._pasada()

        escrituras = [
            consulta["sql"]
            for consulta in capturadas.captured_queries
            if consulta["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
        ]
        self.assertEqual(escrituras, [], "la pasada en régimen volvió a escribir")

    def test_la_alerta_que_deja_de_aplicar_se_cierra_con_fecha(self):
        """El `update(activa=False)` masivo no escribía `fecha_cierre`: la alerta
        quedaba apagada sin decir cuándo, y el dashboard de cerradas no la mostraba."""
        ciudadano, legajo = self._ciudadano_con_legajo(estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=False)

        self._pasada()
        sin_plan = self._activas(ciudadano, "SIN_PLAN").get()

        LegajoAtencion.objects.filter(pk=legajo.pk).update(plan_vigente=True)
        self._pasada()

        sin_plan.refresh_from_db()
        self.assertFalse(sin_plan.activa)
        self.assertIsNotNone(sin_plan.fecha_cierre)
        self.assertIsNone(sin_plan.cerrada_por, "la cerró la pasada, no una persona")

    def test_la_alerta_que_vuelve_a_aplicar_estrena_fila_y_aviso(self):
        """El contrapeso del test de arriba: cerrar no puede dejar la alerta muerta.

        Si el legajo vuelve a quedar sin plan, la alerta tiene que volver —y volver a
        avisar—, porque es información nueva: entre medio alguien la vio cerrada.
        """
        ciudadano, legajo = self._ciudadano_con_legajo(estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=False)

        self._pasada()
        LegajoAtencion.objects.filter(pk=legajo.pk).update(plan_vigente=True)
        self._pasada()
        with patch.object(AlertasService, "_enviar_notificacion_alerta") as enviar:
            LegajoAtencion.objects.filter(pk=legajo.pk).update(plan_vigente=False)
            self._pasada()

        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(AlertaCiudadano.objects.filter(ciudadano=ciudadano, tipo="SIN_PLAN").count(), 2)
        self.assertEqual(self._activas(ciudadano, "SIN_PLAN").count(), 1)

    def test_la_alerta_de_conversaciones_sobrevive_la_pasada(self):
        """Cambio de conducta explícito de LEG-01.

        `MENSAJE_CIUDADANO` es MEDIA y cuelga de `legajo=None`: el `update` masivo por
        ciudadano la apagaba en la primera pasada horaria —sin `fecha_cierre` y sin que
        nadie la hubiera leído— porque la pasada apagaba *todas* las MEDIA/BAJA del
        ciudadano antes de mirar sus legajos. La genera un mensaje del ciudadano, no el
        estado del legajo: esta pasada no la cierra.
        """
        ciudadano, legajo = self._ciudadano_con_legajo()
        de_conversaciones = AlertaCiudadano.objects.create(
            ciudadano=ciudadano,
            legajo=None,
            tipo="MENSAJE_CIUDADANO",
            prioridad="MEDIA",
            mensaje="Nuevo mensaje del ciudadano en conversación",
        )

        self._pasada()

        de_conversaciones.refresh_from_db()
        self.assertTrue(de_conversaciones.activa)

    def test_el_cierre_no_toca_los_legajos_de_otro_ciudadano(self):
        """El recorte del cierre es el lote de legajos de la pasada, no la tabla."""
        _, propio = self._ciudadano_con_legajo(dni="30222111", plan_vigente=False)
        ajeno_inactivo = Ciudadano.objects.create(dni="30222333", nombre="In", apellido="Activo", activo=False)
        legajo_ajeno = LegajoAtencion.objects.create(responsable=self.profesional, plan_vigente=False)
        InscripcionPrograma.objects.create(ciudadano=ajeno_inactivo, programa=self.programa, legajo_id=legajo_ajeno.id)
        suelta = AlertaCiudadano.objects.create(
            ciudadano=ajeno_inactivo,
            legajo=legajo_ajeno,
            tipo="SIN_PLAN",
            prioridad="MEDIA",
            mensaje="de un ciudadano inactivo",
        )

        self._pasada()

        suelta.refresh_from_db()
        self.assertTrue(suelta.activa, "la pasada cerró una alerta de un legajo que no revisó")
        self.assertTrue(AlertaCiudadano.objects.filter(legajo=propio, tipo="SIN_PLAN", activa=True).exists())
