"""La lista de espera se respeta en todos los caminos (CMP-N1).

Decisión del usuario: un caso en lista de espera no se aprueba salvo
promoviéndolo desde Cupo. Antes la regla vivía solo en la vista de aprobar:

- el servicio ``aprobar_o_poner_en_espera``, con cupo libre, aprobaba igual y
  dejaba la fila de ``ListaEspera`` activa, colgando;
- el proceso masivo volvía a consultar a SIIS por cada caso en espera en cada
  corrida y, con cupo, lo aprobaba;
- rechazar (o descartar por duplicado, o dar de baja) dejaba la fila viva;
- desde Cupo se podía «promover» a APROBADO a un caso ya RECHAZADO.
"""

from io import StringIO
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from programas.models import CorridaSiis, EnvioSIIS, Formulario, ListaEspera, TracaFormulario
from programas.services import proceso_masivo
from programas.services.cupo import (
    CasoEnListaEspera,
    aprobar_o_poner_en_espera,
    dar_baja_beneficiario,
    promover_lista_espera,
)
from programas.tests.test_becas_revision import _BaseAprobacionTest
from programas.tests.test_proceso_masivo import _BaseProcesoTest


class _BaseEsperaTest(_BaseAprobacionTest):
    """``form_a`` listo para aprobar, con cupo libre (100) y en la lista de espera."""

    def setUp(self):
        super().setUp()
        self.entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=4)

    def _trazas_espera(self, formulario):
        return list(
            TracaFormulario.objects.filter(formulario=formulario, campo="lista_espera").values_list(
                "valor_anterior", "valor_nuevo"
            )
        )


class AprobarEnEsperaServicioTests(_BaseEsperaTest):
    def test_el_servicio_no_aprueba_a_quien_esta_en_espera_aunque_haya_cupo(self):
        with self.assertRaises(ValidationError) as ctx:
            aprobar_o_poner_en_espera(self.form_a, self.coord_a)

        self.assertIsInstance(ctx.exception, CasoEnListaEspera)
        self.assertIn("lista de espera", ctx.exception.message)
        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        self.assertFalse(self.entrada.promovido)

    def test_sin_espera_el_servicio_aprueba(self):
        self.entrada.delete()
        self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

    def test_una_espera_ya_cerrada_no_bloquea(self):
        self.entrada.promovido = True
        self.entrada.save(update_fields=["promovido"])
        self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

    def test_el_estado_se_relee_bajo_el_lock(self):
        """El objeto en memoria dice ENVIADO pero otra operación ya lo resolvió."""
        self.entrada.delete()
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)

        with self.assertRaises(ValidationError):
            aprobar_o_poner_en_espera(self.form_a, self.coord_a)

        self.assertEqual(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").count(), 0)


class RechazoCierraLaEsperaTests(_BaseEsperaTest):
    @patch("programas.views.revision.enviar_aviso_resolucion")
    def test_rechazar_saca_al_caso_de_la_lista(self, aviso):
        self.client.post(reverse("becas:formulario_rechazar", args=[self.form_a.pk]), {"motivo": "no cumple"})

        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertTrue(self.entrada.promovido)
        self.assertEqual(self._trazas_espera(self.form_a), [("Posición 4 en Seg A", "Cerrada: caso rechazado")])
        aviso.assert_called_once()
        self.assertFalse(ListaEspera.objects.filter(segmento=self.seg_a, promovido=False).exists())

    def test_descartar_la_carga_duplicada_la_saca_de_la_lista(self):
        previo = Formulario.objects.create(relevamiento=self.rel_a, celular="3624300300")
        self.form_a.conflicto_duplicado = True
        self.form_a.duplicado_de = previo
        self.form_a.save(update_fields=["conflicto_duplicado", "duplicado_de"])

        self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[self.form_a.pk]), {"decision": "conservar_previo"}
        )

        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertTrue(self.entrada.promovido)

    def test_reemplazar_la_carga_anterior_la_saca_de_la_lista(self):
        nueva = Formulario.objects.create(
            relevamiento=self.rel_a, celular="3624300300", conflicto_duplicado=True, duplicado_de=self.form_a
        )

        self.client.post(
            reverse("becas:formulario_resolver_duplicado", args=[nueva.pk]), {"decision": "conservar_actual"}
        )

        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        self.assertTrue(self.entrada.promovido)

    def test_la_baja_no_deja_la_espera_viva(self):
        """Datos previos a la regla: un APROBADO con fila activa colgando."""
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.APROBADO)
        self.form_a.refresh_from_db()

        dar_baja_beneficiario(self.form_a, self.admin)

        self.entrada.refresh_from_db()
        self.assertTrue(self.entrada.promovido)
        self.assertEqual(self._trazas_espera(self.form_a), [("Posición 4 en Seg A", "Cerrada: caso dado de baja")])


class PromoverExigeEnviadoTests(_BaseEsperaTest):
    def _rechazado(self):
        Formulario.objects.filter(pk=self.form_a.pk).update(estado=Formulario.Estado.RECHAZADO)
        return ListaEspera.objects.select_related("formulario", "segmento").get(pk=self.entrada.pk)

    def test_promover_un_rechazado_falla_y_cierra_la_fila(self):
        entrada = self._rechazado()

        with self.assertRaises(ValidationError) as ctx:
            promover_lista_espera(entrada, self.admin)

        self.assertIn("ya no está pendiente", ctx.exception.message)
        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        # El cierre se confirma aunque el servicio lance el error.
        self.assertTrue(self.entrada.promovido)
        self.assertEqual(
            self._trazas_espera(self.form_a), [("Posición 4 en Seg A", "Cerrada: el caso ya estaba rechazado")]
        )

    @patch("programas.views.cupo.enviar_beneficiario_a_siis")
    @patch("programas.views.cupo.enviar_aviso_resolucion")
    def test_la_vista_no_avisa_ni_informa_a_siis(self, aviso, enviar):
        self._rechazado()
        self.client.force_login(self.admin)

        resp = self.client.post(reverse("becas:lista_espera_promover", args=[self.entrada.pk]), follow=True)

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.RECHAZADO)
        aviso.assert_not_called()
        enviar.assert_not_called()
        mensajes = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("ya no está pendiente" in m for m in mensajes), mensajes)

    def test_la_fila_ya_promovida_en_la_base_no_se_promueve_dos_veces(self):
        """La vista cargó la fila activa; otra promoción la cerró antes del lock."""
        entrada = ListaEspera.objects.select_related("formulario", "segmento").get(pk=self.entrada.pk)
        ListaEspera.objects.filter(pk=self.entrada.pk).update(promovido=True)

        with self.assertRaises(ValidationError):
            promover_lista_espera(entrada, self.admin)

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)

    def test_un_enviado_se_sigue_promoviendo(self):
        entrada = ListaEspera.objects.select_related("formulario", "segmento").get(pk=self.entrada.pk)
        promover_lista_espera(entrada, self.admin)
        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertTrue(self.entrada.promovido)


class MasivoRespetaLaEsperaTests(_BaseProcesoTest):
    def setUp(self):
        super().setUp()
        self.en_espera = self._caso()
        ListaEspera.objects.create(formulario=self.en_espera, segmento=self.segmento, posicion=1)
        self.libre = self._caso()

    def test_el_selector_deja_afuera_al_enviado_en_espera(self):
        pks = set(proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))
        self.assertEqual(pks, {self.libre.pk})

    def test_el_aprobado_con_fila_colgando_se_sigue_informando(self):
        aprobado = self._caso(Formulario.Estado.APROBADO)
        ListaEspera.objects.create(formulario=aprobado, segmento=self.segmento, posicion=2)
        self.assertIn(aprobado.pk, proceso_masivo.candidatos(programa=self.programa).values_list("pk", flat=True))

    @patch("programas.services.proceso_masivo.enviar_aviso_resolucion")
    @patch("programas.services.proceso_masivo.enviar_beneficiario_a_siis")
    @patch("programas.services.proceso_masivo.validar_formulario_en_siis")
    @patch("programas.services.proceso_masivo.armar_payload", return_value=({}, {}))
    def test_la_corrida_no_consulta_a_siis_ni_aprueba_al_caso_en_espera(self, _payload, validar, enviar, _aviso):
        validar.return_value.estado = "OK"
        enviar.side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )

        with patch("programas.services.proceso_masivo.aprobar_o_poner_en_espera", return_value="aprobado") as aprobar:
            corrida = proceso_masivo.correr(CorridaSiis.objects.create(programa=self.programa, total_pedido=10))

        consultados = [llamada.args[0].pk for llamada in validar.call_args_list]
        aprobados = [llamada.args[0].pk for llamada in aprobar.call_args_list]
        self.assertEqual(consultados, [self.libre.pk])
        self.assertEqual(aprobados, [self.libre.pk])
        self.assertEqual(corrida.elegidos, 1)
        self.en_espera.refresh_from_db()
        self.assertEqual(self.en_espera.estado, Formulario.Estado.ENVIADO)


class MasivoCasoQueEntraEnEsperaTests(_BaseEsperaTest):
    """Entró a la lista entre la selección y su turno: el servicio lo frena y el
    masivo lo cuenta aparte, no como «no aprobable»."""

    @patch("programas.services.proceso_masivo.enviar_beneficiario_a_siis")
    @patch("programas.services.proceso_masivo.validar_formulario_en_siis")
    def test_cuenta_ya_en_espera_y_no_aprueba(self, validar, enviar):
        validar.return_value = self.validacion
        cuenta = proceso_masivo.Cuenta()

        proceso_masivo.procesar_caso(self.form_a, self.coord_a, None, cuenta)

        self.assertEqual(cuenta.ya_en_espera, 1)
        self.assertEqual(cuenta.no_aprobable, 0)
        self.assertEqual(cuenta.aprobados, 0)
        enviar.assert_not_called()
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)


class ComandoCerrarEsperaColgadaTests(_BaseEsperaTest):
    """``form_a`` (ENVIADO, en espera) es una fila legítima: nunca se toca."""

    def setUp(self):
        super().setUp()
        self.colgadas = []
        for i, estado in enumerate(
            (Formulario.Estado.RECHAZADO, Formulario.Estado.APROBADO, Formulario.Estado.BAJA), start=10
        ):
            caso = Formulario.objects.create(relevamiento=self.rel_a, celular=f"36243000{i}", estado=estado)
            self.colgadas.append(ListaEspera.objects.create(formulario=caso, segmento=self.seg_a, posicion=i))

    def _correr(self, *args):
        salida = StringIO()
        call_command("cerrar_espera_colgada", *args, stdout=salida)
        return salida.getvalue()

    def _activas(self):
        return set(ListaEspera.objects.filter(promovido=False).values_list("pk", flat=True))

    def test_por_defecto_solo_lista(self):
        salida = self._correr()

        self.assertIn("activas de casos ya resueltos: 3", salida)
        for fila in self.colgadas:
            self.assertIn(f"fila {fila.pk:>6}", salida)
        self.assertNotIn(f"fila {self.entrada.pk:>6}", salida)
        self.assertIn("Ensayo", salida)
        self.assertEqual(self._activas(), {self.entrada.pk, *(f.pk for f in self.colgadas)})

    def test_aplicar_las_cierra_y_es_idempotente(self):
        salida = self._correr("--aplicar", "--usuario", self.admin.username)

        self.assertIn("Cerradas: 3 filas de 3 casos.", salida)
        self.assertEqual(self._activas(), {self.entrada.pk})
        traza = TracaFormulario.objects.get(formulario=self.colgadas[0].formulario, campo="lista_espera")
        self.assertEqual(traza.editado_por, self.admin)
        self.assertEqual(traza.valor_nuevo, "Cerrada: limpieza de datos, el caso ya estaba rechazado")

        segunda = self._correr("--aplicar")
        self.assertIn("No hay filas", segunda)
        self.assertEqual(TracaFormulario.objects.filter(campo="lista_espera").count(), 3)

    def test_usuario_inexistente_corta(self):
        with self.assertRaises(CommandError):
            self._correr("--aplicar", "--usuario", "nadie")
        self.assertEqual(len(self._activas()), 4)
