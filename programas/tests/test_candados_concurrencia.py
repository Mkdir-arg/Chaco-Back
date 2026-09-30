"""Candados: dos requests simultáneos no se pisan.

Las dos carreras que cubre este módulo se reprodujeron a mano con dos pestañas:

- lanzar el proceso masivo dos veces deja dos corridas EN_CURSO, y los dos hilos
  aprueban e informan a SIIS los mismos casos;
- rechazar un caso (o descartar una carga duplicada) mientras otro request lo
  aprueba pisa la aprobación, le libera el cupo y le manda el correo de «no fue
  aprobado».

La carrera se simula, no se corre: la suite usa SQLite en memoria, donde
``select_for_update()`` es un no-op y dos hilos de verdad no probarían nada. Lo
que se comprueba es lo que sí depende del código: que la decisión se tome con lo
que hay adentro del candado y no con lo que se leyó antes.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from programas.models import CorridaSiis, Formulario, TracaFormulario
from programas.services import proceso_masivo
from programas.tests.test_becas_revision import _BaseAprobacionTest
from programas.tests.test_proceso_masivo import _BaseProcesoTest

# A propósito escrito acá y no importado de la vista: lo que se comprueba es el
# texto que ve la persona, no que dos módulos compartan una constante.
MENSAJE_EN_CURSO = "Ya hay una corrida en curso. Esperá a que termine o frenala."


class CandadoCorridaMasivaTests(_BaseProcesoTest):
    """Entre ``en_curso()`` y el ``create()`` no puede entrar nadie."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("admin_candado", password="x")
        self.client.force_login(self.admin)

    def _url(self, nombre="proceso_masivo_lanzar"):
        return reverse(f"becas:{nombre}", args=[self.programa.pk])

    def test_una_corrida_que_entro_mientras_esperabamos_el_candado_frena_la_nuestra(self):
        """La pantalla vio el camino libre; con el candado tomado, ya no lo está."""
        rastro = {"consultas": 0, "rival": None}

        def en_curso_falsa():
            rastro["consultas"] += 1
            if rastro["consultas"] == 1:
                # Chequeo de la vista, antes del candado: no hay nada corriendo.
                return None
            # Re-chequeo del servicio, ya con el candado: el otro request
            # commiteó su corrida mientras esperábamos.
            if rastro["rival"] is None:
                rastro["rival"] = CorridaSiis.objects.create(
                    programa=self.programa, total_pedido=7, latido=timezone.now()
                )
            return rastro["rival"]

        with (
            patch.object(CorridaSiis, "en_curso", side_effect=en_curso_falsa),
            patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar,
        ):
            resp = self.client.post(self._url(), {"total_pedido": "25"})

        self.assertEqual(resp.status_code, 302)
        lanzar.assert_not_called()
        # Solo sobrevive la del rival: la nuestra no llegó a escribirse.
        self.assertEqual([c.total_pedido for c in CorridaSiis.objects.all()], [7])
        self.assertIn(MENSAJE_EN_CURSO, [str(m) for m in get_messages(resp.wsgi_request)])

    def test_con_el_camino_libre_la_corrida_se_crea_igual(self):
        with patch("programas.views.proceso_masivo.servicio.lanzar") as lanzar:
            self.client.post(self._url(), {"total_pedido": "25"})

        corrida = CorridaSiis.objects.get()
        self.assertEqual(corrida.total_pedido, 25)
        self.assertEqual(corrida.solicitada_por, self.admin)
        self.assertEqual(corrida.estado, CorridaSiis.Estado.EN_CURSO)
        lanzar.assert_called_once()

    def test_el_servicio_no_crea_nada_si_ya_hay_una_viva(self):
        CorridaSiis.objects.create(programa=self.programa, total_pedido=3, latido=timezone.now())

        creada = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

        self.assertIsNone(creada)
        self.assertEqual(CorridaSiis.objects.count(), 1)

    def test_una_interrumpida_no_bloquea_al_servicio(self):
        """El candado no cambia la regla del latido: un pod muerto no traba nada."""
        CorridaSiis.objects.create(
            programa=self.programa,
            total_pedido=3,
            latido=timezone.now() - CorridaSiis.LATIDO_VENCIDO * 2,
        )

        creada = proceso_masivo.crear_corrida(programa=self.programa, solicitada_por=self.user, total_pedido=5)

        self.assertIsNotNone(creada)
        self.assertEqual(CorridaSiis.objects.count(), 2)


class CandadoRechazoTests(_BaseAprobacionTest):
    """Rechazar decide con el estado que hay bajo el candado."""

    def _rechazar(self, motivo="No cumple los requisitos"):
        return self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": motivo})

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_no_pisa_una_aprobacion_que_entro_mientras_consultabamos_siis(self, aviso):
        """La consulta a SIIS es la ventana larga del request: ahí entra el otro."""

        def validar_y_que_otro_apruebe(formulario, usuario):
            Formulario.objects.filter(pk=formulario.pk).update(estado=Formulario.Estado.APROBADO)
            return self.validacion

        with patch("programas.views.revision.validar_formulario_en_siis", side_effect=validar_y_que_otro_apruebe):
            resp = self._rechazar()

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(self.form_a.motivo_rechazo, "")
        self.assertFalse(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").exists())
        aviso.assert_not_called()

    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_sin_carrera_el_rechazo_sigue_funcionando(self, aviso):
        resp = self._rechazar(motivo="Documentación incompleta")

        self.assertEqual(resp.status_code, 302)
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.form_a.motivo_rechazo, "Documentación incompleta")
        aviso.assert_called_once()


class CandadoDuplicadoTests(_BaseAprobacionTest):
    """Resolver un duplicado tampoco decide con datos de hace un rato."""

    def setUp(self):
        super().setUp()
        self.previo = Formulario.objects.create(relevamiento=self.rel_a, celular="3624300300")
        Formulario.objects.filter(pk=self.form_a.pk).update(conflicto_duplicado=True, duplicado_de=self.previo)
        self.form_a.refresh_from_db()

    def _resolver(self, decision="conservar_previo", pk=None):
        return self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[pk or self.form_a.pk]), {"decision": decision}
        )

    def test_conservar_previo_no_descarta_una_carga_que_ya_aprobaron(self):
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)

        self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertFalse(self.form_a.conflicto_resuelto)
        self.assertEqual(self.form_a.motivo_rechazo, "")

    def test_el_conflicto_resuelto_se_relee_bajo_el_candado(self):
        """Otra pestaña resolvió el conflicto entre la lectura y el candado."""

        def resuelve_el_otro(request, formulario):
            Formulario.objects.filter(pk=formulario.pk).update(conflicto_resuelto=True)

        with patch("programas.views.revision._assert_scope_formulario", side_effect=resuelve_el_otro):
            self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_conservar_actual_no_reemplaza_una_carga_anterior_ya_resuelta(self):
        Formulario.objects.filter(pk=self.previo.pk).update(estado=Formulario.Estado.APROBADO)

        self._resolver(decision="conservar_actual")

        self.previo.refresh_from_db()
        self.form_a.refresh_from_db()
        self.assertEqual(self.previo.estado, Formulario.Estado.APROBADO)
        self.assertFalse(self.form_a.conflicto_resuelto)

    def test_sin_carrera_el_duplicado_se_resuelve_igual(self):
        self._resolver()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertTrue(self.form_a.conflicto_resuelto)
