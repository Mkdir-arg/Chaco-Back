"""FE-19 · Un solo handler de confirmación para Dispositivos y Merenderos.

El mismo `[data-confirm]` estaba implementado tres veces, y las tres distintas: una sin
`data-confirm-ok` ni motivo, otra sin `buttonsStyling:false` y la tercera pintando el
botón de confirmar con `text-fg-danger` **siempre**. Resultado: «Rechazar» confirmaba
en el color de marca y acciones reversibles confirmaban en rojo.

Ahora el handler vive en `programas/templates/programas/_swal_confirm_js.html` y el
tono lo declara la pantalla con `data-confirm-danger`. SweetAlert2 sigue siendo la
pieza **legacy condicionada** de esas pantallas (Cambio 48); para UI nueva rige
`data-confirm-url` → `ModernModal`.
"""

from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.tests.js_harness import correr_script, requiere_node, script_con

REPO = Path(settings.BASE_DIR)

INCLUDE = "programas/_swal_confirm_js.html"
PANTALLAS = (
    "programas/templates/programas/dispositivos/legajo/detail.html",
    "programas/templates/programas/merenderos/detail.html",
    "programas/templates/programas/merenderos/solicitudes.html",
)

#: Monta un `<form>` falso que registra qué se le colgó y cómo se envió, y dispara el
#: click sobre un botón con el `dataset` pedido.
_BANCO = """
var __enviados = [];
var __creados = [];
var __formFalso = {
  appendChild: function (el) { __creados.push({name: el.name, value: el.value, type: el.type}); },
  submit: function () { __enviados.push('submit'); },
  requestSubmit: function () { __enviados.push('requestSubmit'); },
  contains: function () { return true; }
};
Swal.fire = function (opciones) {
  __log.swal.push(opciones);
  return {then: function (cb) { cb({isConfirmed: __confirmado, value: __valor}); }};
};
var __confirmado = true;
var __valor = '  texto del motivo  ';
function __clickEn(dataset) {
  var boton = {
    dataset: dataset,
    closest: function (selector) {
      if (selector === 'form') { return __formFalso; }
      // El `closest` real resuelve el selector: `[data-confirm]` no matchea un botón
      // que solo trae `data-confirm-url` (el del confirm canónico de Becas).
      if (selector === '[data-confirm]') { return dataset.confirm !== undefined ? boton : null; }
      throw new Error('selector no previsto: ' + selector);
    }
  };
  (__handlers.click || []).forEach(function (fn) {
    fn({target: boton, preventDefault: function () {}});
  });
}
"""

_VOLCADO = "\n__log.enviados = __enviados;\n__log.creados = __creados;\n"


@requiere_node
class HandlerUnicoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.script = script_con(render_to_string(INCLUDE), "requiresMotivo")

    def correr(self, acciones):
        return correr_script(self.script, _BANCO + acciones + _VOLCADO)

    def test_una_accion_destructiva_confirma_en_rojo(self):
        log = self.correr("__clickEn({confirm: '', confirmDanger: '', confirmTitle: 'Rechazar dispositivo'});")
        clases = log["swal"][0]["customClass"]
        self.assertIn("btn-danger", clases["confirmButton"])
        self.assertIn("btn-base", clases["confirmButton"])

    def test_una_accion_no_destructiva_confirma_en_color_de_marca(self):
        log = self.correr("__clickEn({confirm: '', confirmTitle: '¿Validar dispositivo?'});")
        clases = log["swal"][0]["customClass"]
        self.assertIn("btn-brand", clases["confirmButton"])
        self.assertNotIn("btn-danger", clases["confirmButton"])

    def test_los_dos_botones_del_dialogo_tienen_variante_y_tamano(self):
        log = self.correr("__clickEn({confirm: ''});")
        for boton in ("confirmButton", "cancelButton"):
            with self.subTest(boton=boton):
                clases = log["swal"][0]["customClass"][boton].split()
                self.assertIn("btn-nodo", clases)
                self.assertTrue(
                    any(c.startswith("btn-") and c != "btn-nodo" and not c.startswith("btn-base") for c in clases)
                )
                self.assertIn("btn-base", clases)

    def test_el_estilo_de_los_botones_no_lo_pone_sweetalert(self):
        log = self.correr("__clickEn({confirm: ''});")
        self.assertIs(log["swal"][0]["buttonsStyling"], False)

    def test_los_textos_salen_de_los_data_attributes(self):
        log = self.correr(
            "__clickEn({confirm: '', confirmTitle: '¿Cerrar merendero?', "
            "confirmText: 'Impide nuevas entregas.', confirmOk: 'Sí, cerrar'});"
        )
        opciones = log["swal"][0]
        self.assertEqual(opciones["title"], "¿Cerrar merendero?")
        self.assertEqual(opciones["text"], "Impide nuevas entregas.")
        self.assertEqual(opciones["confirmButtonText"], "Sí, cerrar")

    def test_sin_data_attributes_hay_textos_por_defecto(self):
        log = self.correr("__clickEn({confirm: ''});")
        opciones = log["swal"][0]
        self.assertEqual(opciones["title"], "¿Confirmás la acción?")
        self.assertEqual(opciones["confirmButtonText"], "Confirmar")

    def test_el_motivo_obligatorio_viaja_en_el_post(self):
        log = self.correr("__clickEn({confirm: '', requiresMotivo: '', confirmTitle: 'Rechazar solicitud'});")
        self.assertEqual(log["swal"][0]["input"], "textarea")
        self.assertEqual(log["creados"], [{"name": "motivo", "value": "texto del motivo", "type": "hidden"}])

    def test_sin_motivo_pedido_no_se_agrega_el_campo(self):
        log = self.correr("__clickEn({confirm: ''});")
        self.assertEqual(log["creados"], [])

    def test_el_motivo_vacio_no_pasa_la_validacion(self):
        log = self.correr(
            "__clickEn({confirm: '', requiresMotivo: ''});\n"
            "__log.validacion = [__log.swal[0].inputValidator('   '), __log.swal[0].inputValidator(' ok ')];"
        )
        self.assertEqual(log["validacion"], ["El motivo es obligatorio.", None])

    def test_cancelar_no_envia_nada(self):
        log = self.correr("__confirmado = false;\n__clickEn({confirm: '', requiresMotivo: ''});")
        self.assertEqual(log["enviados"], [])
        self.assertEqual(log["creados"], [])

    def test_el_envio_dispara_el_evento_submit(self):
        """`form.submit()` a secas se saltea la guardia de doble envío del shell (FE-26)."""
        log = self.correr("__clickEn({confirm: ''});")
        self.assertEqual(log["enviados"], ["requestSubmit"])

    def test_no_intercepta_el_confirm_canonico_de_becas(self):
        """Becas escucha `[data-confirm-url]`; este handler, `[data-confirm]` a secas."""
        log = self.correr("__clickEn({confirmUrl: '/algo/'});")
        self.assertEqual(log["swal"], [])
        self.assertEqual(log["enviados"], [])


class PantallasSinHandlerPropioTests(SimpleTestCase):
    def test_las_tres_pantallas_incluyen_la_pieza_unica(self):
        for ruta in PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertTrue(INCLUDE in texto, f"{ruta} no incluye {INCLUDE}")

    def test_ninguna_pantalla_conserva_su_copia_del_handler(self):
        for ruta in PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertNotIn("Swal.fire", texto, f"{ruta}: el handler es el include")
                self.assertNotIn("sweetalert2.all.min.js", texto, f"{ruta}: la carga la hace el include")

    def test_rechazar_y_cerrar_declaran_que_son_destructivas(self):
        esperado = {
            "programas/templates/programas/dispositivos/legajo/detail.html": ("Rechazar", "Cerrar"),
            "programas/templates/programas/merenderos/detail.html": ("Cerrar",),
            "programas/templates/programas/merenderos/solicitudes.html": ("Rechazar",),
        }
        for ruta, etiquetas in esperado.items():
            texto = (REPO / ruta).read_text(encoding="utf-8")
            for linea in texto.splitlines():
                if "data-confirm " not in linea and "data-confirm>" not in linea:
                    continue
                for etiqueta in etiquetas:
                    if f">{etiqueta}</button>" in linea:
                        with self.subTest(ruta=ruta, etiqueta=etiqueta):
                            self.assertIn("data-confirm-danger", linea)

    def test_las_acciones_constructivas_no_se_declaran_destructivas(self):
        constructivas = ("Enviar a validación", "Validar", "Aprobar", "Suspender", "Observar", "Inactivar")
        for ruta in PANTALLAS:
            texto = (REPO / ruta).read_text(encoding="utf-8")
            for linea in texto.splitlines():
                for etiqueta in constructivas:
                    if f">{etiqueta}</button>" in linea:
                        with self.subTest(ruta=ruta, etiqueta=etiqueta):
                            self.assertNotIn("data-confirm-danger", linea)
