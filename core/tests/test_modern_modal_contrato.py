"""Contrato de ``ModernModal`` (``templates/includes/base.html``), el motor de
confirmaciones del backoffice (DP-1).

- Pie con los botones del sistema: ``btn-base`` y «Cancelar» ``btn-tertiary`` (POP-11).
- ``options.icon`` fija el tono del ícono de una confirmación; una destructiva sin
  ``icon`` toma el tono danger en vez del «?» gris (POP-20).
- Tras el primer confirmar/cancelar/cerrar se ignoran los clics repetidos durante la
  animación de cierre: un doble clic no ejecuta ``onConfirm`` dos veces.
- En una confirmación destructiva el foco inicial va a Cancelar.

Los tests de comportamiento corren el ``<script>`` real del template con ``node``
sobre el DOM permisivo de ``js_harness`` (``setTimeout`` corre en el acto).
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from core.tests.js_harness import correr_script_pagina, requiere_node, script_con

BASE_HTML = Path(settings.BASE_DIR, "templates", "includes", "base.html")
MARCADOR = "window.ModernModal = {"

DANGER = "bg-[color:var(--bg-danger-soft)] text-[color:var(--text-fg-danger)]"
WARNING = "bg-[color:var(--bg-warning-soft)] text-[color:var(--text-fg-warning)]"
QUESTION = "bg-[color:var(--bg-tertiary)] text-[color:var(--text-body-subtle)]"
INFO = "bg-[color:var(--bg-brand-soft)] text-[color:var(--text-fg-brand)]"

# Registra qué botón recibe el foco y deja a mano los handlers de los botones.
_PREPARAR = r"""
__disparar('document', 'DOMContentLoaded');
var M = window.ModernModal;
__el('modal-confirm').focus = function () { __log.valores.foco = 'confirm'; };
__el('modal-cancel').focus = function () { __log.valores.foco = 'cancel'; };
var __i = {className: ''};
__el('modal-overlay').classList = {
  add: function (c) { __log.valores.overlay = 'add:' + c; },
  remove: function (c) { __log.valores.overlay = 'remove:' + c; }
};
__el('modal-icon').querySelector = function () { return __i; };
function __estado() {
  __log.valores.icono = String(__el('modal-icon').className);
  __log.valores.iconoFa = String(__i.className);
  __log.valores.confirmar = String(__el('modal-confirm').className);
}
"""


def _markup(elemento_id):
    html = BASE_HTML.read_text(encoding="utf-8")
    m = re.search(r'<button id="%s" class="([^"]*)"' % elemento_id, html)
    assert m, f"no está el botón #{elemento_id} en base.html"
    return m.group(1).split()


def _correr(acciones):
    script = script_con(BASE_HTML.read_text(encoding="utf-8"), MARCADOR)
    return correr_script_pagina(script, _PREPARAR + acciones)["valores"]


class ModernModalPieTests(SimpleTestCase):
    def test_cancelar_es_terciario_y_base(self):
        clases = _markup("modal-cancel")
        self.assertIn("btn-tertiary", clases)
        self.assertIn("btn-base", clases)
        self.assertNotIn("btn-sm", clases)
        self.assertNotIn("btn-secondary", clases)

    def test_confirmar_es_base(self):
        clases = _markup("modal-confirm")
        self.assertIn("btn-base", clases)
        self.assertNotIn("btn-sm", clases)

    def test_hoja_inferior_en_celular_se_mantiene(self):
        html = BASE_HTML.read_text(encoding="utf-8")
        self.assertIn("items-end justify-center p-0 sm:min-h-screen sm:items-center", html)
        self.assertIn("modal-footer flex flex-col-reverse", html)

    def test_script_documenta_la_opcion_icon(self):
        script = script_con(BASE_HTML.read_text(encoding="utf-8"), MARCADOR)
        self.assertIn("options.icon", script)
        self.assertNotIn("btn-sm", script)


@requiere_node
class ModernModalComportamientoTests(SimpleTestCase):
    def test_destructiva_sin_icon_usa_tono_danger(self):
        v = _correr("M.show({type: 'confirm', danger: true, title: 't'}); __estado();")
        self.assertIn(DANGER, v["icono"])
        self.assertIn("fa-exclamation-circle", v["iconoFa"])
        self.assertIn("btn-danger", v["confirmar"])
        self.assertIn("btn-base", v["confirmar"])

    def test_confirmvariant_danger_tambien_es_destructiva(self):
        v = _correr("M.show({type: 'confirm', confirmVariant: 'danger'}); __estado();")
        self.assertIn(DANGER, v["icono"])
        self.assertEqual(v["foco"], "cancel")

    def test_confirmacion_no_destructiva_conserva_el_signo_de_pregunta(self):
        v = _correr("M.show({type: 'confirm', title: 't'}); __estado();")
        self.assertIn(QUESTION, v["icono"])
        self.assertIn("fa-question-circle", v["iconoFa"])
        self.assertIn("btn-brand", v["confirmar"])
        self.assertIn("btn-base", v["confirmar"])

    def test_icon_fija_el_tono(self):
        casos = {
            "warning": (WARNING, "fa-exclamation-triangle"),
            "danger": (DANGER, "fa-exclamation-circle"),
            "question": (QUESTION, "fa-question-circle"),
            "info": (INFO, "fa-info-circle"),
        }
        for icono, (tono, fa) in casos.items():
            with self.subTest(icon=icono):
                v = _correr("M.show({type: 'confirm', icon: '%s'}); __estado();" % icono)
                self.assertIn(tono, v["icono"])
                self.assertIn(fa, v["iconoFa"])

    def test_icon_manda_sobre_danger(self):
        # DA-4: «¿Asignar igual?» es de atención pero puede ir con botón rojo.
        v = _correr("M.show({type: 'confirm', danger: true, icon: 'warning'}); __estado();")
        self.assertIn(WARNING, v["icono"])
        self.assertIn("btn-danger", v["confirmar"])

    def test_icon_invalido_cae_en_el_default(self):
        for icono in ("otro", "toString", "constructor"):
            with self.subTest(icon=icono):
                v = _correr("M.show({type: 'confirm', icon: '%s'}); __estado();" % icono)
                self.assertIn(QUESTION, v["icono"])

    def test_tipos_que_no_son_confirm_no_cambian(self):
        v = _correr("M.show({type: 'error', danger: true, icon: 'info'}); __estado();")
        self.assertIn(DANGER, v["icono"])
        v = _correr("M.show({type: 'success', icon: 'danger'}); __estado();")
        self.assertIn("--bg-success-soft", v["icono"])

    def test_doble_clic_en_confirmar_ejecuta_onconfirm_una_vez(self):
        v = _correr(
            "var n = 0;"
            "M.show({type: 'confirm', danger: true, onConfirm: function () { n++; }});"
            "__el('modal-confirm').onclick(); __el('modal-confirm').onclick();"
            "__log.valores.n = String(n);"
        )
        self.assertEqual(v["n"], "1")

    def test_doble_clic_en_cancelar_ejecuta_oncancel_una_vez(self):
        v = _correr(
            "var n = 0, c = 0;"
            "M.show({type: 'confirm', onConfirm: function () { c++; }, onCancel: function () { n++; }});"
            "__el('modal-cancel').onclick(); __el('modal-cancel').onclick(); __el('modal-confirm').onclick();"
            "__log.valores.n = String(n); __log.valores.c = String(c);"
        )
        self.assertEqual(v["n"], "1")
        self.assertEqual(v["c"], "0")

    def test_confirmar_despues_de_escape_no_confirma(self):
        v = _correr(
            "var n = 0;"
            "M.show({type: 'confirm', onConfirm: function () { n++; }});"
            "__disparar('document', 'keydown', {key: 'Escape'});"
            "__el('modal-confirm').onclick();"
            "__log.valores.n = String(n);"
        )
        self.assertEqual(v["n"], "0")

    def test_un_nuevo_modal_vuelve_a_aceptar_clics(self):
        v = _correr(
            "var n = 0;"
            "M.show({type: 'confirm', onConfirm: function () { n++; }});"
            "__el('modal-confirm').onclick();"
            "M.show({type: 'confirm', onConfirm: function () { n++; }});"
            "__el('modal-confirm').onclick();"
            "__log.valores.n = String(n);"
        )
        self.assertEqual(v["n"], "2")

    def test_confirmar_cierra_el_overlay(self):
        v = _correr("M.show({type: 'confirm'}); __el('modal-confirm').onclick();")
        self.assertEqual(v["overlay"], "add:hidden")

    def test_onconfirm_que_abre_otro_modal_no_lo_cierra(self):
        # El cierre del primero corre después de su onConfirm: no puede ocultar al segundo.
        v = _correr(
            "M.show({type: 'confirm', onConfirm: function () {"
            "  M.show({type: 'error', title: 'No se pudo eliminar'}); }});"
            "__el('modal-confirm').onclick();"
        )
        self.assertEqual(v["overlay"], "remove:hidden")

    def test_foco_inicial_en_cancelar_si_es_destructiva(self):
        v = _correr("M.show({type: 'confirm', danger: true});")
        self.assertEqual(v["foco"], "cancel")

    def test_foco_inicial_en_confirmar_si_no_es_destructiva(self):
        v = _correr("M.show({type: 'confirm'});")
        self.assertEqual(v["foco"], "confirm")

    def test_alerta_danger_sin_cancelar_enfoca_confirmar(self):
        # Sin type confirm, «Cancelar» está oculto: el foco no puede ir ahí.
        v = _correr("M.show({type: 'error', danger: true});")
        self.assertEqual(v["foco"], "confirm")
