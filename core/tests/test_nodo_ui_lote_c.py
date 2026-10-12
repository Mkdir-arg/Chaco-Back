"""Piezas del lote C del MVP de Dispositivos: tarjeta de turno y entradas de bitácora."""

from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

TURNO = "components/_turno_tarjeta.html"
ENTRADAS = "components/_entradas_bitacora.html"
RAIZ = Path(__file__).resolve().parents[2]


def _turno(**extra):
    datos = {"nombre": "Tarde", "horario": "14:00–22:00", "estado": "Abierto", "tono": "info"}
    datos.update(extra)
    return datos


def _entrada(**extra):
    datos = {"hora": "16:10", "categoria": "Incidente", "tono": "danger", "texto": "Discusión en comedor"}
    datos.update(extra)
    return datos


class TurnoTarjetaTest(SimpleTestCase):
    def test_dibuja_nombre_horario_estado_y_detalle(self):
        html = render_to_string(TURNO, {"turno": _turno(detalle="L. Méndez · 6 entradas")})
        for texto in ("Tarde", "14:00–22:00", "Abierto", "L. Méndez · 6 entradas", "badge-info"):
            self.assertIn(texto, html)

    def test_el_tono_lo_decide_la_vista(self):
        for tono, clase in (("success", "badge-success"), ("warning", "badge-warning"), ("danger", "badge-danger")):
            self.assertIn(clase, render_to_string(TURNO, {"turno": _turno(tono=tono)}))

    def test_tono_desconocido_o_ausente_dibuja_badge_neutro(self):
        for tono in ("inventado", ""):
            html = render_to_string(TURNO, {"turno": _turno(tono=tono)})
            self.assertIn("badge-gray", html)
            self.assertIn("Abierto", html)

    def test_turno_activo_se_marca_con_borde_y_aria_current(self):
        activo = render_to_string(TURNO, {"turno": _turno(activo=True)})
        self.assertIn("border-brand", activo)
        self.assertIn('aria-current="true"', activo)
        comun = render_to_string(TURNO, {"turno": _turno()})
        self.assertNotIn("aria-current", comun)
        self.assertNotIn("border-brand", comun)

    def test_turno_sin_abrir_usa_fondo_atenuado_no_opacidad(self):
        html = render_to_string(TURNO, {"turno": _turno(sin_abrir=True, estado="Sin abrir", tono="")})
        self.assertIn("bg-secondary", html)
        self.assertNotIn("opacity", html)

    def test_acciones_y_variante_desconocida_es_secundaria(self):
        acciones = [
            {"url": "/a/", "texto": "+ Novedad", "variante": "brand"},
            {"url": "/b/", "texto": "Cerrar turno", "variante": "rara"},
            {"url": "/c/", "texto": "Ver", "variante": "tertiary"},
        ]
        html = render_to_string(TURNO, {"turno": _turno(acciones=acciones)})
        self.assertIn('href="/a/"', html)
        self.assertIn("btn-brand", html)
        self.assertIn("btn-secondary", html)
        self.assertIn("btn-tertiary", html)

    def test_sin_acciones_no_dibuja_botones(self):
        self.assertNotIn("btn-nodo", render_to_string(TURNO, {"turno": _turno()}))

    def test_escapa_lo_que_manda_la_vista(self):
        html = render_to_string(TURNO, {"turno": _turno(detalle="<script>alert(1)</script>")})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)


class EntradasBitacoraTest(SimpleTestCase):
    def test_dibuja_hora_categoria_texto_y_autor(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada(titulo="Discusión", autor="L. Méndez")]})
        for texto in ("16:10", "Incidente", "Discusión en comedor", "L. Méndez", "badge-danger"):
            self.assertIn(texto, html)

    def test_la_categoria_va_con_texto_e_icono_ademas_del_color(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada()]})
        self.assertIn("</i> Incidente</span>", html)
        self.assertIn("fa-circle-exclamation", html)
        self.assertIn('aria-hidden="true"', html)

    def test_cada_tono_tiene_su_icono(self):
        iconos = {
            "success": "fa-circle-check",
            "info": "fa-circle-info",
            "warning": "fa-triangle-exclamation",
            "danger": "fa-circle-exclamation",
            "brand": "fa-flag",
        }
        for tono, icono in iconos.items():
            self.assertIn(icono, render_to_string(ENTRADAS, {"entradas": [_entrada(tono=tono)]}))

    def test_tono_desconocido_dibuja_badge_neutro_con_texto(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada(tono="inventado", categoria="Rara")]})
        self.assertIn("badge-gray", html)
        self.assertIn("fa-circle", html)
        self.assertIn("Rara", html)

    def test_el_texto_del_usuario_va_escapado(self):
        peligro = '<script>alert(1)</script><img src=x onerror="y">'
        html = render_to_string(ENTRADAS, {"entradas": [_entrada(texto=peligro, titulo="<b>t</b>", autor="<i>a</i>")]})
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertNotIn("<b>t</b>", html)
        self.assertNotIn("<i>a</i>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_respeta_los_saltos_de_linea_sin_abrir_html(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada(texto="uno\n<p>dos</p>")]})
        self.assertIn("uno<br>&lt;p&gt;dos&lt;/p&gt;", html)

    def test_automatica_y_version(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada(automatica=True, autor="L. Méndez", version=2)]})
        self.assertIn("Automática · L. Méndez", html)
        self.assertIn("Versión 2", html)
        sin_version = render_to_string(ENTRADAS, {"entradas": [_entrada(version=1)]})
        self.assertNotIn("Versión", sin_version)

    def test_sin_autor_ni_marcas_no_dibuja_linea_de_autoria(self):
        self.assertNotIn("mt-1 text-xs", render_to_string(ENTRADAS, {"entradas": [_entrada()]}))

    def test_lista_vacia_muestra_el_estado_vacio_canonico(self):
        for vacia in ([], None):
            html = render_to_string(ENTRADAS, {"entradas": vacia})
            self.assertIn("Todavía no hay entradas", html)
            self.assertNotIn("<ol", html)

    def test_sin_tope_ni_aviso_cuando_entra_todo(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada()] * 100})
        self.assertEqual(html.count("<li"), 100)
        self.assertNotIn("Mostrando", html)

    def test_tope_de_100_entradas_con_aviso(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada()] * 150})
        self.assertEqual(html.count("<li"), 100)
        self.assertIn("Mostrando 100 de 150 entradas.", html)

    def test_total_de_la_vista_avisa_el_recorte(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada()] * 50, "total": 480})
        self.assertEqual(html.count("<li"), 50)
        self.assertIn("Mostrando 50 de 480 entradas.", html)

    def test_total_menor_o_igual_no_avisa(self):
        html = render_to_string(ENTRADAS, {"entradas": [_entrada()] * 3, "total": 3})
        self.assertNotIn("Mostrando", html)


class ContratoDeLasPiezasTest(SimpleTestCase):
    def test_ninguna_pieza_apaga_el_escapado(self):
        for nombre in ("_turno_tarjeta.html", "_entradas_bitacora.html"):
            codigo = (RAIZ / "templates" / "components" / nombre).read_text(encoding="utf-8")
            self.assertNotIn("|safe", codigo)
            self.assertNotIn("autoescape off", codigo)
            self.assertNotIn("mark_safe", codigo)
            self.assertNotIn("style=", codigo)
