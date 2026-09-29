"""Encabezado y acciones del caso de Becas: estado real, lista de espera y duplicados.

- CMP-3: el badge de estado sale del parcial único ``_formulario_estado_badge.html``;
  un caso dado de baja ya no se muestra como «Enviado».
- CMP-N1 (decisión del usuario): un caso en lista de espera no se aprueba desde el
  caso, solo promoviéndolo desde Cupo y beneficiarios. Antes, con cupo libre,
  «Aprobar» lo pasaba a APROBADO y dejaba su fila de ``ListaEspera`` colgando.
- POP-5: «Conservar este» / «Conservar el otro» rechazan un caso sin vuelta atrás:
  piden confirmación y el envío es uno solo aunque se confirme dos veces.
"""

from django.contrib.auth.models import Group, Permission
from django.urls import reverse

from core.tests.js_harness import atributos_de, correr_script, requiere_node, script_con
from programas.management.commands.seed_becas import ROL_COORDINADOR
from programas.models import Formulario, ListaEspera
from programas.tests.test_becas_revision import _BaseAprobacionTest, _BaseRevisionTest


def _texto(html):
    return " ".join(html.split())


class EstadoDelCasoEnElEncabezadoTests(_BaseRevisionTest):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def _detalle(self):
        return self.client.get(reverse("becas:formulario_detalle", args=[self.form_a.pk])).content.decode()

    def test_un_caso_dado_de_baja_no_dice_enviado(self):
        self.form_a.estado = Formulario.Estado.BAJA
        self.form_a.save(update_fields=["estado"])
        html = self._detalle()
        self.assertIn('<span class="badge badge-gray badge-dot">Dado de baja</span>', html)
        self.assertNotIn(">Enviado</span>", html)

    def test_un_caso_enviado_sigue_en_amarillo(self):
        html = self._detalle()
        self.assertIn('<span class="badge badge-warning badge-dot">Enviado</span>', html)


class EsperaNoSeApruebaDesdeElCasoTests(_BaseAprobacionTest):
    """El segmento tiene cupo libre (100 lugares): es el escenario que aprobaba."""

    def setUp(self):
        super().setUp()
        self.entrada = ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=3)
        self.url = reverse("becas:formulario_detalle", args=[self.form_a.pk])

    def test_aprobar_no_aprueba_a_quien_esta_en_espera(self):
        resp = self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]), follow=True)

        self.form_a.refresh_from_db()
        self.entrada.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        self.assertFalse(self.entrada.promovido)
        self.validar_compatibilidad.assert_not_called()
        mensajes = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("lista de espera" in m for m in mensajes), mensajes)

    def test_el_detalle_no_ofrece_aprobar_y_dice_la_posicion(self):
        html = self.client.get(self.url).content.decode()
        texto = _texto(html)
        self.assertNotIn('id="btn-aprobar"', html)
        self.assertNotIn('id="form-aprobar"', html)
        self.assertIn('id="btn-rechazar"', html)
        self.assertIn('<span class="badge badge-warning">Lista de espera · posición 3</span>', texto)
        self.assertIn(
            "Está en la lista de espera del segmento (posición 3). Se aprueba al promoverlo desde "
            "Cupo y beneficiarios.",
            texto,
        )
        self.assertIn(reverse("becas:cupo_segmento", args=[self.seg_a.pk]), html)

    def test_sin_capacidad_de_cupo_no_hay_link(self):
        coordinador = Group.objects.get(name=ROL_COORDINADOR)
        coordinador.permissions.remove(
            *Permission.objects.filter(codename__in=["becas_cupo_ver", "becas_beneficiario_ver"])
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Está en la lista de espera del segmento (posición 3).", _texto(html))
        self.assertNotIn(reverse("becas:cupo_segmento", args=[self.seg_a.pk]), html)

    def test_la_entrada_promovida_no_cuenta_como_espera(self):
        self.entrada.promovido = True
        self.entrada.save(update_fields=["promovido"])
        html = self.client.get(self.url).content.decode()
        self.assertIn('id="btn-aprobar"', html)
        self.assertNotIn("Lista de espera · posición", html)

    def test_sin_espera_se_sigue_aprobando(self):
        self.entrada.delete()
        self.client.post(reverse("becas:formulario_aprobar", args=[self.form_a.pk]))
        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)


class ConfirmacionResolverDuplicadoTests(_BaseRevisionTest):
    """Los dos botones del conflicto de DNI rechazan un caso: se confirman."""

    def setUp(self):
        super().setUp()
        self.previo = Formulario.objects.create(
            relevamiento=self.rel_a, celular="3624300300", email_contacto="mismo@b.com"
        )
        self.form_a.conflicto_duplicado = True
        self.form_a.duplicado_de = self.previo
        self.form_a.save(update_fields=["conflicto_duplicado", "duplicado_de"])
        self.client.force_login(self.admin)

    def _html(self, formulario):
        return self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk])).content.decode()

    def _forms_duplicado(self, html):
        return [attrs for tag, attrs in atributos_de(html) if tag == "form" and "data-confirmar-duplicado" in attrs]

    def test_los_dos_forms_llevan_el_marcador_con_los_numeros(self):
        html = self._html(self.form_a)
        forms = self._forms_duplicado(html)
        self.assertEqual(len(forms), 2)
        este, otro = str(self.form_a.numero), str(self.previo.numero)
        pares = {(f["data-conservar"], f["data-descartar"]) for f in forms}
        self.assertEqual(pares, {(este, otro), (otro, este)})
        self.assertNotIn("confirm(", script_con(html, "data-confirmar-duplicado"))

    def test_los_numeros_son_coherentes_con_la_decision(self):
        """Visto desde cualquiera de las dos cargas, el caso que se conserva es el
        que la decisión deja en pie."""
        for visto in (self.form_a, self.previo):
            html = self._html(visto)
            partes = [
                p
                for p in html.split("<form")[1:]
                if p.lstrip().startswith("method") and "data-confirmar-duplicado" in p.split(">")[0]
            ]
            self.assertEqual(len(partes), 2)
            for parte in partes:
                decision = parte.split('name="decision" value="')[1].split('"')[0]
                conservar = parte.split('data-conservar="')[1].split('"')[0]
                esperado = self.previo.numero if decision == "conservar_previo" else self.form_a.numero
                self.assertEqual(conservar, str(esperado), (visto.pk, decision))

    @requiere_node
    def test_el_submit_no_sale_sin_confirmar_y_dos_confirmaciones_son_un_envio(self):
        script = script_con(self._html(self.form_a), "data-confirmar-duplicado")
        acciones = r"""
        var __ahora = 1000;
        Date.now = function () { return __ahora; };
        var __boton = {disabled: false};
        var __f = {dataset: {confirmarDuplicado: '', conservar: '7', descartar: '4'},
                   submit: function () { __log.submits.push('duplicado'); },
                   querySelector: function () { return __boton; }};
        __f.closest = function () { return __f; };
        function __submit() {
          var evento = {target: __f, defaultPrevented: false,
                        preventDefault: function () { this.defaultPrevented = true; }};
          (__handlers.submit || []).forEach(function (fn) { fn(evento); });
          return evento.defaultPrevented;
        }
        __log.prevenido = __submit();
        __log.submits_sin_confirmar = __log.submits.length;
        __log.modal[0].onConfirm();           // Enter de más apenas abre: no confirma
        __log.submits_rapido = __log.submits.length;
        __ahora += 500;
        __log.modal[0].onConfirm();
        __log.modal[0].onConfirm();           // doble clic durante el cierre de ModernModal
        __log.boton_deshabilitado = __boton.disabled;
        __submit();                           // otro submit con el envío ya en curso
        __log.modales_final = __log.modal.length;
        """
        log = correr_script(script, acciones)
        self.assertTrue(log["prevenido"])
        self.assertEqual(log["submits_sin_confirmar"], 0)
        self.assertEqual(log["submits_rapido"], 0)
        self.assertEqual(log["submits"], ["duplicado"])
        self.assertTrue(log["boton_deshabilitado"])
        self.assertEqual(log["modales_final"], 1)
        modal = log["modal"][0]
        self.assertEqual(modal["type"], "confirm")
        self.assertTrue(modal["danger"])
        self.assertEqual(modal["title"], "¿Conservar el caso 7?")
        self.assertEqual(modal["message"], "El caso 4 queda rechazado como carga duplicada. No se puede deshacer.")
        self.assertEqual(modal["confirmText"], "Sí, conservar el 7")
