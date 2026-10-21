"""Orden de los requisitos de programa, segmento y subsegmento por arrastre
(Cambio 264, reemplaza el orden manual del Cambio 23).

El endpoint recibe la lista completa de los requisitos **propios** de una lista
y los renumera 1..N; los heredados no se mueven desde otra pantalla.
"""

import json
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.rbac import APP_LABEL, codename_de
from core.tests.js_harness import correr_script_pagina, requiere_node
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_COORDINADOR_REGIONAL
from programas.models import AsignacionCoordinador, ProgramaSiis, RequisitoNativo, Segmento, Subsegmento, TipoCampo


def _capacidad(codigo):
    return Permission.objects.get(content_type__app_label=APP_LABEL, codename=codename_de(codigo))


def _req(texto, orden, **ancla):
    return RequisitoNativo.objects.create(texto=texto, tipo=TipoCampo.STRING, orden=orden, **ancla)


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-req-orden", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.programa = ProgramaSiis.objects.create(nombre="Producción", siis_programa_id=38)
        self.seg = Segmento.objects.create(programa=self.programa, nombre="Seg A", cupo_maximo=100)
        self.otro_seg = Segmento.objects.create(programa=self.programa, nombre="Seg B", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.seg, nombre="Sub A", cupo_maximo=40)
        # Órdenes repetidos y con huecos, como quedaron datos viejos (Cambio 23).
        self.p1 = _req("Del programa 1", 3, programa=self.programa)
        self.p2 = _req("Del programa 2", 3, programa=self.programa)
        self.s1 = _req("Del segmento 1", 1, segmento=self.seg)
        self.s2 = _req("Del segmento 2", 5, segmento=self.seg)
        self.s3 = _req("Del segmento 3", 9, segmento=self.seg)
        self.u1 = _req("Del subsegmento 1", 1, segmento=self.seg, subsegmento=self.sub)
        self.u2 = _req("Del subsegmento 2", 2, segmento=self.seg, subsegmento=self.sub)
        self.ajeno = _req("De otro segmento", 1, segmento=self.otro_seg)

    def _reordenar(self, nivel, pk, ids, **kwargs):
        return self.client.post(
            reverse("becas:requisitos_reordenar", args=[nivel, pk]),
            data=json.dumps({"ids": ids}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            **kwargs,
        )

    @staticmethod
    def _ordenes(*reqs):
        return [RequisitoNativo.objects.get(pk=r.pk).orden for r in reqs]


class ReordenarTests(_Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_reordena_el_segmento_y_renumera_compacto(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["target"], "#reqs-panel")
        self.assertIn("data-sortable-lista", data["html"])
        self.assertEqual(self._ordenes(self.s3, self.s1, self.s2), [1, 2, 3])
        # Las otras listas no se tocan.
        self.assertEqual(self._ordenes(self.u1, self.u2, self.p1, self.ajeno), [1, 2, 3, 1])

    def test_reordena_el_programa_y_normaliza_repetidos(self):
        resp = self._reordenar("programa", self.programa.pk, [self.p2.pk, self.p1.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["target"], "#reqs-programa-panel")
        self.assertEqual(self._ordenes(self.p2, self.p1), [1, 2])

    def test_reordena_el_subsegmento(self):
        resp = self._reordenar("subsegmento", self.sub.pk, [self.u2.pk, self.u1.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["target"], "#reqs-propios-panel")
        self.assertEqual(self._ordenes(self.u2, self.u1), [1, 2])
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_el_parcial_devuelto_sale_en_el_orden_nuevo(self):
        html = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk]).json()["html"]
        self.assertLess(html.index("Del segmento 3"), html.index("Del segmento 1"))
        self.assertLess(html.index("Del segmento 1"), html.index("Del segmento 2"))

    def test_ids_repetidos_es_400(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s1.pk, self.s1.pk, self.s2.pk, self.s3.pk])
        self.assertEqual(resp.status_code, 400)

    def test_payload_invalido_es_400(self):
        url = reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk])
        self.assertEqual(self.client.post(url, data="no-json", content_type="application/json").status_code, 400)
        for cuerpo in ({}, {"ids": "1,2"}, {"ids": ["x"]}, {"ids": [True]}, ["no-objeto"]):
            resp = self.client.post(url, data=json.dumps(cuerpo), content_type="application/json")
            self.assertEqual(resp.status_code, 400, cuerpo)

    def test_un_id_ajeno_es_409_y_no_toca_nada(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s1.pk, self.s2.pk, self.s3.pk, self.ajeno.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_un_heredado_no_se_mueve_desde_el_subsegmento(self):
        # El del segmento se ve en el subsegmento como heredado, pero no es de su lista.
        resp = self._reordenar("subsegmento", self.sub.pk, [self.s1.pk, self.u1.pk, self.u2.pk])
        self.assertEqual(resp.status_code, 409)
        resp = self._reordenar("segmento", self.seg.pk, [self.p1.pk, self.s1.pk, self.s2.pk, self.s3.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.u1, self.p1), [1, 1, 3])

    def test_si_falta_uno_es_409(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s2.pk, self.s1.pk])
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self._ordenes(self.s1, self.s2), [1, 5])

    def test_nivel_desconocido_o_ancla_inexistente_es_404(self):
        self.assertEqual(self._reordenar("convocatoria", self.seg.pk, []).status_code, 404)
        self.assertEqual(self._reordenar("segmento", 999999, []).status_code, 404)

    def test_solo_post(self):
        url = reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_un_alta_despues_de_reordenar_va_al_final(self):
        self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        resp = self.client.post(
            reverse("becas:requisito_crear", args=[self.seg.pk]),
            {"texto": "Nuevo", "tipo": TipoCampo.STRING, "obligatorio": "True"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(RequisitoNativo.objects.get(texto="Nuevo").orden, 4)


class PermisosTests(_Base):
    def _coordinador(self, username, segmento, con_editar=True):
        user = User.objects.create_user(username, password="x")
        grupo = Group.objects.get(name=ROL_COORDINADOR)
        user.groups.add(grupo)
        if not con_editar:
            # Desde el Cambio 334 el Coordinador sembrado edita requisitos: el caso
            # «sin la capacidad» es un rol al que se la sacaron. Depende de que la semilla
            # no se vuelva a correr después: ``seed_becas`` se la devuelve al Coordinador.
            grupo.permissions.remove(_capacidad("becas.requisito.editar"))
        AsignacionCoordinador.objects.create(segmento=segmento, coordinador=user)
        cache.clear()
        return user

    def test_anonimo_no_reordena(self):
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertIn(resp.status_code, (302, 403))
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_sin_la_capacidad_de_editar_es_403(self):
        # Un rol de coordinación que ve y crea requisitos, pero no los edita.
        self.client.force_login(self._coordinador("coord-sin-editar", self.seg, con_editar=False))
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._ordenes(self.s1, self.s2, self.s3), [1, 5, 9])

    def test_coordinador_reordena_su_segmento_pero_no_uno_ajeno(self):
        self.client.force_login(self._coordinador("coord-con-editar", self.seg))
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self._reordenar("segmento", self.otro_seg.pk, [self.ajeno.pk])
        self.assertEqual(resp.status_code, 403)

    def test_coordinador_no_reordena_el_programa(self):
        self.client.force_login(self._coordinador("coord-programa", self.seg))
        resp = self._reordenar("programa", self.programa.pk, [self.p2.pk, self.p1.pk])
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(self._ordenes(self.p1, self.p2), [3, 3])

    def test_regional_reordena_solo_su_subsegmento(self):
        rol = Group.objects.get(name=ROL_COORDINADOR_REGIONAL)
        rol.permissions.add(_capacidad("becas.requisito.editar"))
        ana = User.objects.create_user("ana-orden", password="x")
        ana.groups.add(rol)
        beto = User.objects.create_user("beto-orden", password="x")
        Subsegmento.objects.filter(pk=self.sub.pk).update(referente=ana)
        par = Subsegmento.objects.create(segmento=self.seg, nombre="Sub B", cupo_maximo=40, referente=beto)
        del_par = _req("Del par", 1, segmento=self.seg, subsegmento=par)
        cache.clear()
        self.client.force_login(ana)
        self.assertEqual(self._reordenar("subsegmento", self.sub.pk, [self.u2.pk, self.u1.pk]).status_code, 200)
        self.assertEqual(self._reordenar("subsegmento", par.pk, [del_par.pk]).status_code, 403)
        # Lo del segmento entero no lo configura el Regional (SEC-30).
        resp = self._reordenar("segmento", self.seg.pk, [self.s3.pk, self.s1.pk, self.s2.pk])
        self.assertEqual(resp.status_code, 403)


class RenderTests(_Base):
    def test_el_admin_ve_manijas_solo_en_las_filas_propias(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:segmento_detalle", args=[self.seg.pk])).content.decode()
        self.assertIn("data-sortable-lista", html)
        self.assertIn('data-puede-ordenar="1"', html)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["segmento", self.seg.pk]), html)
        self.assertEqual(html.count('class="grip lista-grip" role="button" tabindex="0"'), 3)
        self.assertIn("flechas arriba y abajo", html)
        self.assertIn(f'data-item-id="{self.s1.pk}"', html)
        # Los heredados del programa se listan, pero sin manija ni fila ordenable.
        self.assertIn("Del programa 1", html)
        self.assertNotIn(f'data-item-id="{self.p1.pk}"', html)
        self.assertIn("vendor/sortablejs/Sortable.min.js", html)
        self.assertIn("custom/js/nodo-catalogo-grupos.js", html)
        self.assertNotIn('name="orden"', html)

    def test_subsegmento_arrastra_propios_y_heredados_quedan_fijos(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:subsegmento_detalle", args=[self.sub.pk])).content.decode()
        self.assertEqual(html.count("lista-grip"), 2)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["subsegmento", self.sub.pk]), html)
        for heredado in (self.p1, self.s1):
            self.assertIn(heredado.texto, html)
            self.assertNotIn(f'data-item-id="{heredado.pk}"', html)
        self.assertNotIn('name="orden"', html)

    def test_programa_arrastra_sus_requisitos(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:programa_detalle", args=[self.programa.pk])).content.decode()
        self.assertEqual(html.count("lista-grip"), 2)
        self.assertIn(reverse("becas:requisitos_reordenar", args=["programa", self.programa.pk]), html)
        self.assertNotIn('name="orden"', html)

    def test_sin_capacidad_de_editar_no_hay_manijas(self):
        coord = User.objects.create_user("coord-lector", password="x")
        grupo = Group.objects.get(name=ROL_COORDINADOR)
        # Depende de que la semilla no se vuelva a correr: ``seed_becas`` le devuelve
        # ``requisito.editar`` al Coordinador (Cambio 334).
        grupo.permissions.remove(_capacidad("becas.requisito.editar"))
        coord.groups.add(grupo)
        AsignacionCoordinador.objects.create(segmento=self.seg, coordinador=coord)
        self.client.force_login(coord)
        resp = self.client.get(reverse("becas:segmento_detalle", args=[self.seg.pk]))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('data-puede-ordenar="0"', html)
        self.assertNotIn("lista-grip", html)
        self.assertNotIn("vendor/sortablejs/Sortable.min.js", html)

    def test_la_lista_transversal_no_pide_orden(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("becas:requisitos_segmento")).content.decode()
        self.assertNotIn('name="orden"', html)


class JsListasTests(TestCase):
    def test_el_js_cablea_las_listas_planas(self):
        js = Path(settings.BASE_DIR, "static", "custom", "js", "nodo-catalogo-grupos.js").read_text(encoding="utf-8")
        self.assertIn("[data-sortable-lista]", js)
        self.assertIn("handle: '.lista-grip'", js)
        self.assertIn("lista.isConnected", js)
        self.assertIn("JSON.stringify({\n          ids:", js.replace("\r\n", "\n"))


# DOM falso con lo justo para mover nodos de verdad: cada contenedor tiene
# `children` real (Array) y appendChild/insertBefore sacan el nodo de su padre
# anterior, como el navegador. Las filas registran el foco de su manija.
_DOM_FALSO = r"""
var __foco = null;
function __sacar(n) {
  if (n.parentElement) {
    var arr = n.parentElement.children, i = arr.indexOf(n);
    if (i >= 0) { arr.splice(i, 1); }
  }
}
function __contenedor(attrs, hijos) {
  var c = {
    children: [], isConnected: true, dataset: {}, __on: {},
    classList: {add: function () {}, remove: function () {}},
    getAttribute: function (n) { return n in attrs ? attrs[n] : null; },
    appendChild: function (n) { __sacar(n); c.children.push(n); n.parentElement = c; return n; },
    insertBefore: function (n, ref) {
      __sacar(n);
      var i = ref ? c.children.indexOf(ref) : -1;
      if (i < 0) { c.children.push(n); } else { c.children.splice(i, 0, n); }
      n.parentElement = c;
      return n;
    },
    contains: function () { return false; },
    addEventListener: function (tipo, fn) { c.__on[tipo] = fn; },
    querySelector: function (sel) {
      var m = /data-item-id="(\d+)"/.exec(sel);
      return m ? c.children.filter(function (h) { return String(h.id) === m[1]; })[0] || null : null;
    }
  };
  (hijos || []).forEach(function (h) { c.appendChild(h); });
  return c;
}
function __fila(id) {
  var grip = {
    focus: function () { __foco = id; },
    closest: function (sel) { return sel.indexOf('grip') !== -1 ? grip : fila; }
  };
  var fila = {
    id: id, parentElement: null, grip: grip,
    get nextSibling() { var p = this.parentElement; return p.children[p.children.indexOf(this) + 1] || null; },
    getAttribute: function (n) { return n === 'data-item-id' || n === 'data-pregunta-id' ? String(id) : null; },
    matches: function () { return true; },
    querySelector: function (sel) { return sel.indexOf('grip') !== -1 ? grip : null; }
  };
  return fila;
}
function __ids(c) { return c.children.map(function (h) { return h.id === undefined ? 'placeholder' : h.id; }); }
__log.toasts = [];
window.toast = function (tipo, msg) { __log.toasts.push([tipo, msg]); };
window.setTimeout = function (fn) { fn(); return 0; };
window.clearTimeout = function () {};
var __ops = [];
window.Sortable = function (el, opts) { __ops.push(opts); return {option: function () {}, destroy: function () {}}; };
document.activeElement = null;
document.cookie = '';
"""


@requiere_node
class JsOrdenCsrfTests(SimpleTestCase):
    def test_envia_token_del_formulario_con_cookie_httponly_y_relee_al_guardar(self):
        self._comprobar_tokens("", "token-dom", ["token-dom", "token-renovado"])

    def test_prioriza_formulario_sobre_cookie(self):
        self._comprobar_tokens("csrftoken=token-cookie", "token-dom", ["token-dom", "token-renovado"])

    def test_conserva_fallback_a_cookie_sin_campo_oculto(self):
        self._comprobar_tokens("sessionid=x; csrftoken=token-cookie", None, ["token-cookie", "token-cookie"])

    def _comprobar_tokens(self, cookie, token, esperados):
        script = (Path(settings.BASE_DIR) / "static/custom/js/nodo-catalogo-grupos.js").read_text(encoding="utf-8")
        for agrupado in (True, False):
            with self.subTest(agrupado=agrupado):
                acciones = (
                    _DOM_FALSO
                    + f"""
document.cookie = {json.dumps(cookie)};
var __token = {json.dumps(None if token is None else {"value": token})};
var __lista = __contenedor({{'data-puede-ordenar': '1', 'data-url-reordenar': '/orden/'}}, []);
__lista.querySelectorAll = function () {{ return []; }};
document.querySelector = function (sel) {{
  if (sel === '[name="csrfmiddlewaretoken"]') return __token;
  return sel === '[data-sortable-grupos]' && {json.dumps(agrupado)} ? __lista : null;
}};
document.querySelectorAll = function (sel) {{
  return sel === '[data-sortable-lista]' && !{json.dumps(agrupado)} ? [__lista] : [];
}};
__log.tokens = [];
fetch = function (url, opciones) {{
  __log.tokens.push(opciones.headers['X-CSRFToken']);
  return new Promise(function () {{}});
}};
__disparar('document', 'DOMContentLoaded');
__ops[0].onEnd({{oldIndex: 0, newIndex: 1}});
if (__token) __token.value = 'token-renovado';
__ops[0].onEnd({{oldIndex: 1, newIndex: 0}});
"""
                )
                self.assertEqual(correr_script_pagina(script, acciones)["tokens"], esperados)


@requiere_node
class JsListaRevierteSiFallaTests(SimpleTestCase):
    """Si el guardado falla, la pantalla vuelve al orden que vino del servidor
    (hallazgo del revisor del PR #822): no queda mostrando un orden no guardado."""

    def setUp(self):
        self.script = (Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-catalogo-grupos.js").read_text(
            encoding="utf-8"
        )

    def _lista(self, mover, respuesta=None, red_caida=False):
        falla = (
            "fetch = function () { return Promise.reject(new Error('red')); };"
            if red_caida
            else f"__respuestas['/reordenar-lista/'] = {json.dumps(respuesta)};"
        )
        acciones = (
            _DOM_FALSO
            + f"""
var __f = [__fila(1), __fila(2), __fila(3)];
var __lista = __contenedor({{'data-url-reordenar': '/reordenar-lista/', 'data-indicador': 'ind',
                            'data-puede-ordenar': '1'}}, __f);
document.querySelector = function () {{ return null; }};
document.querySelectorAll = function (sel) {{ return sel === '[data-sortable-lista]' ? [__lista] : []; }};
{falla}
__disparar('document', 'DOMContentLoaded');
{mover}
__setTimeoutReal(function () {{
  __log.orden = __ids(__lista);
  __log.foco = __foco;
  __log.indicador = String(__el('ind').textContent);
}}, 20);
"""
        )
        return correr_script_pagina(self.script, acciones)

    # Arrastre: Sortable ya movió la fila 1 al medio cuando llama a onEnd.
    ARRASTRE = "__lista.insertBefore(__f[0], __f[2]); __ops[0].onEnd({oldIndex: 0, newIndex: 1, item: __f[0]});"
    # Teclado: flecha abajo sobre la manija de la fila 1.
    TECLADO = "__lista.__on.keydown({key: 'ArrowDown', target: __f[0].grip, preventDefault: function () {}});"

    def test_arrastre_rechazado_vuelve_al_orden_previo_y_enfoca_la_manija(self):
        log = self._lista(self.ARRASTRE, {"ok": False, "error": "La lista cambió. Recargá la página."})
        self.assertEqual(log["orden"], [1, 2, 3])
        self.assertEqual(log["foco"], 1)
        self.assertEqual(log["toasts"], [["error", "La lista cambió. Recargá la página."]])
        self.assertEqual(log["indicador"], "No se guardó el orden")

    def test_teclado_rechazado_vuelve_al_orden_previo(self):
        log = self._lista(self.TECLADO, {"ok": False, "error": "Sin permiso."})
        self.assertEqual(log["orden"], [1, 2, 3])
        self.assertEqual(log["foco"], 1)

    def test_red_caida_vuelve_al_orden_previo(self):
        log = self._lista(self.ARRASTRE, red_caida=True)
        self.assertEqual(log["orden"], [1, 2, 3])
        self.assertEqual(log["toasts"], [["error", "No se pudo guardar el orden. Revisá la conexión."]])

    def test_guardado_ok_no_revierte(self):
        log = self._lista(self.TECLADO, {"ok": True, "target": "#x", "html": "<p></p>"})
        self.assertEqual(log["orden"], [2, 1, 3])
        self.assertEqual(log["toasts"], [])

    def test_catalogo_agrupado_rechazado_vuelve_grupos_preguntas_y_placeholder(self):
        """El catálogo agrupado tenía el mismo problema: grupos, preguntas que
        cruzaron de grupo y el placeholder del grupo vacío vuelven a su lugar."""
        acciones = (
            _DOM_FALSO
            + """
var __ph = {placeholder: true, parentElement: null, matches: function () { return false; }};
var __tbA = __contenedor({}, [__fila(1), __fila(2)]);
var __tbB = __contenedor({}, [__ph]);
function __card(gid, tb) {
  var card = __contenedor({'data-grupo-id': gid}, []);
  card.id = 'g' + gid;
  card.querySelectorAll = function () { return tb.children.filter(function (h) { return !h.placeholder; }); };
  return card;
}
var __cA = __card('10', __tbA), __cB = __card('20', __tbB);
var __root = __contenedor({'data-puede-ordenar': '1', 'data-url-reordenar': '/reordenar/'}, [__cA, __cB]);
__root.querySelectorAll = function (sel) { return sel === '.grupo-card' ? __root.children : [__tbA, __tbB]; };
document.querySelector = function (sel) { return sel === '[data-sortable-grupos]' ? __root : null; };
document.querySelectorAll = function () { return []; };
__respuestas['/reordenar/'] = {ok: false, error: 'No se pudo.'};
__disparar('document', 'DOMContentLoaded');
// La pregunta 1 cruza al grupo vacío (sale el placeholder) y los grupos se invierten.
__tbB.appendChild(__tbA.children[0]); __sacar(__ph); __ph.parentElement = null;
__root.insertBefore(__cB, __cA);
__ops[1].onEnd({from: __tbA, to: __tbB, oldIndex: 0, newIndex: 0});
__setTimeoutReal(function () {
  __log.grupos = __ids(__root);
  __log.tbA = __ids(__tbA);
  __log.tbB = __ids(__tbB);
}, 20);
"""
        )
        log = correr_script_pagina(self.script, acciones)
        self.assertEqual(log["grupos"], ["g10", "g20"])
        self.assertEqual(log["tbA"], [1, 2])
        self.assertEqual(log["tbB"], ["placeholder"])
        self.assertEqual(log["toasts"], [["error", "No se pudo."]])
