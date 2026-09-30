"""Catálogo de requisitos generales: piezas comunes de diseño (ola 3, PR P-D).

Render de la lista (page_header, modales accesibles, acciones .nodo-icon-btn,
estados vacíos), formularios de respaldo (TIT-10) y autoguardado del catálogo
sin toast de éxito (DA-2), ejecutando el JS real con node.
"""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.tests.js_harness import correr_script_pagina, requiere_node
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import GrupoRequisito, PreguntaGlobal, ProgramaSiis, TipoCampo
from programas.tests.test_catalogo_drag import _seed


class _Base(TestCase):
    def setUp(self):
        _seed()
        self.admin = User.objects.create_user("admin-pdiseno", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.grupo = GrupoRequisito.objects.get(clave="cuestionario")
        self.p = PreguntaGlobal.objects.create(
            texto="Pregunta de prueba", tipo=TipoCampo.STRING, grupo=self.grupo, orden=100
        )


class ListaPreguntasRenderTests(_Base):
    def test_encabezado_y_modales_accesibles(self):
        html = self.client.get(reverse("becas:preguntas")).content.decode()
        self.assertIn("<h1", html)
        for tid in ("modal-crear-titulo", "modal-edit-titulo", "modal-grupo-titulo"):
            self.assertIn(f'aria-labelledby="{tid}"', html)
            self.assertIn(f'id="{tid}"', html)
            self.assertIn(f'role="dialog" aria-modal="true" aria-labelledby="{tid}"', html)
        self.assertEqual(html.count("x-becas-modal="), 3)
        self.assertIn("custom/js/becas-modal.js", html)
        self.assertIn("max-h-[90vh]", html)
        # El indicador del autoguardado vive fuera de la tabla que se reemplaza.
        self.assertIn('id="catalogo-guardado"', html)

    def test_alerta_del_editor_de_condicion_con_titulo(self):
        html = self.client.get(reverse("becas:preguntas")).content.decode()
        self.assertIn("Sin campos para condicionar", html)

    def test_acciones_de_fila(self):
        html = self.client.get(reverse("becas:preguntas")).content.decode()
        self.assertIn("nodo-icon-btn", html)
        self.assertIn('aria-label="Editar pregunta Pregunta de prueba"', html)
        self.assertIn('aria-label="Desactivar pregunta Pregunta de prueba"', html)
        self.assertIn('data-confirm-ok="Sí, desactivar"', html)
        self.assertIn('data-confirm-icon="question"', html)
        self.assertIn('aria-label="Eliminar pregunta Pregunta de prueba"', html)
        self.assertIn('data-confirm-danger="true"', html)

    def test_activar_una_pregunta_inactiva(self):
        PreguntaGlobal.objects.filter(pk=self.p.pk).update(activo=False)
        html = self.client.get(reverse("becas:preguntas")).content.decode()
        self.assertIn('aria-label="Activar pregunta Pregunta de prueba"', html)
        self.assertIn('data-confirm-ok="Sí, activar"', html)

    def test_tabla_plana_usa_clases_nodo(self):
        html = self.client.get(reverse("becas:preguntas"), {"q": "prueba"}).content.decode()
        self.assertIn("nodo-thead-row", html)
        self.assertIn("nodo-th", html)
        self.assertIn("nodo-td", html)

    def test_estado_vacio_con_filtros_ofrece_limpiar(self):
        html = self.client.get(reverse("becas:preguntas"), {"q": "zzzz-no-existe"}).content.decode()
        self.assertIn("Ninguna pregunta coincide con los filtros", html)
        self.assertIn("Limpiar filtros", html)
        self.assertIn(f'href="{reverse("becas:preguntas")}"', html)

    def test_estado_vacio_sin_filtros_sin_boton_de_limpiar(self):
        PreguntaGlobal.objects.all().delete()
        GrupoRequisito.objects.all().delete()
        html = self.client.get(reverse("becas:preguntas")).content.decode()
        self.assertIn("No hay preguntas configuradas", html)
        self.assertNotIn("Ninguna pregunta coincide", html)


class FormulariosDeRespaldoTests(_Base):
    def test_pregunta_form_con_encabezado_y_cancelar_terciario(self):
        html = self.client.get(reverse("becas:pregunta_crear")).content.decode()
        self.assertIn("Nueva pregunta</h1>", html)
        self.assertIn('aria-label="Volver a requisitos generales"', html)
        self.assertIn('btn-tertiary btn-base">Cancelar</a>', html)
        self.assertNotIn("← Cancelar", html)
        self.assertIn(f'href="{reverse("becas:preguntas")}"', html)

    def test_pregunta_form_edicion(self):
        html = self.client.get(reverse("becas:pregunta_editar", args=[self.p.pk])).content.decode()
        self.assertIn("Editar pregunta</h1>", html)

    def test_requisito_form_cancela_al_detalle_de_origen(self):
        programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        url = reverse("becas:requisito_programa_crear", args=[programa.pk])
        html = self.client.get(url).content.decode()
        self.assertIn("Nuevo requisito nativo</h1>", html)
        destino = reverse("becas:programa_detalle", args=[programa.pk])
        self.assertIn(f'href="{destino}" class="btn-nodo btn-tertiary btn-base">Cancelar</a>', html)
        self.assertNotIn("← Cancelar", html)


@requiere_node
class AutoguardadoSinToastTests(SimpleTestCase):
    """DA-2: el autoguardado del catálogo no emite toast de éxito; los errores sí."""

    def setUp(self):
        self.script = (Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-catalogo-grupos.js").read_text(
            encoding="utf-8"
        )

    def _correr(self, respuesta):
        acciones = f"""
__log.toasts = [];
window.toast = function (tipo, msg) {{ __log.toasts.push([tipo, msg]); }};
var __ops = [];
window.Sortable = function (el, opts) {{ __ops.push(opts); }};
var __root = {{
  isConnected: true,
  classList: {{add: function () {{}}, remove: function () {{}}}},
  getAttribute: function (n) {{ return n === 'data-puede-ordenar' ? '1' : '/reordenar/'; }},
  querySelectorAll: function () {{ return []; }},
  dataset: {{}},
  addEventListener: function () {{}}
}};
document.querySelector = function (sel) {{ return sel === '[data-sortable-grupos]' ? __root : null; }};
document.cookie = '';
__respuestas['/reordenar/'] = {json.dumps(respuesta)};
__disparar('document', 'DOMContentLoaded');
__ops[0].onEnd({{oldIndex: 0, newIndex: 1}});
__setTimeoutReal(function () {{ __log.indicador = String(__el('catalogo-guardado').textContent); }}, 20);
"""
        return correr_script_pagina(self.script, acciones)

    def test_exito_no_muestra_toast_y_actualiza_el_indicador(self):
        log = self._correr({"ok": True, "target": "#x", "html": "<p></p>", "message": "Orden guardado."})
        self.assertEqual(log["toasts"], [])
        self.assertEqual(log["indicador"], "Orden guardado")

    def test_error_si_muestra_toast(self):
        log = self._correr({"ok": False, "error": "Sin permiso."})
        self.assertEqual(log["toasts"], [["error", "Sin permiso."]])
        self.assertEqual(log["indicador"], "No se guardó el orden")
