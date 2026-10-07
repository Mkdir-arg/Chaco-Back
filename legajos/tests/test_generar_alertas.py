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

El `assertNumQueries` de la pasada (3 consultas por ciudadano activo) es PERF-20 y va
en la Ola 4: acá se prueba comportamiento, no costo.

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
from django.test import TestCase
from django.utils import timezone

from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.models.contactos import HistorialContacto
from legajos.services.alertas import AlertasService
from programas.models import InscripcionPrograma, Programa


class GenerarAlertasTests(TestCase):
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
        """Las MEDIA/BAJA se apagan al empezar la pasada y solo reviven si siguen
        aplicando. Acá: el legajo gana su plan, así que `SIN_PLAN` deja de aplicar."""
        ciudadano, legajo = self._ciudadano_con_legajo(estado=LegajoAtencion.Estado.ABIERTO, plan_vigente=False)

        self._pasada()
        sin_plan = self._activas(ciudadano, "SIN_PLAN").get()

        LegajoAtencion.objects.filter(pk=legajo.pk).update(plan_vigente=True)
        self._pasada()

        sin_plan.refresh_from_db()
        self.assertFalse(sin_plan.activa)
        self.assertFalse(self._activas(ciudadano, "SIN_PLAN").exists())

    def test_una_alerta_alta_no_se_apaga_sola(self):
        """La contracara: la desactivación en bloque es **solo** MEDIA/BAJA.

        Si alguien ampliara ese `update()` a todas las prioridades, una `RIESGO_ALTO`
        se apagaría en cada pasada y volvería a notificarse: ruido permanente.
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
