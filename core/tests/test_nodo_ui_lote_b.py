"""Piezas del lote B de Dispositivos MVP: mapa de plazas con su leyenda y galería
fotográfica histórica."""

import re
from datetime import date

from django.template.loader import render_to_string
from django.test import SimpleTestCase

MAPA = "components/_mapa_plazas.html"
LEYENDA = "components/_leyenda_plazas.html"
GALERIA = "components/_galeria_fotos.html"

ICONOS = {
    "success": "fa-circle-check",
    "info": "fa-user",
    "warning": "fa-clock",
    "brand": "fa-right-left",
    "danger": "fa-ban",
}


def _plaza(codigo="A-01", estado="Disponible", tono="success", **extra):
    return {"codigo": codigo, "estado": estado, "tono": tono, **extra}


class MapaPlazasTest(SimpleTestCase):
    def test_cada_plaza_lleva_codigo_estado_e_icono(self):
        # El color no puede ser el unico portador: texto e icono en cada celda.
        for tono, icono in ICONOS.items():
            html = render_to_string(MAPA, {"plazas": [_plaza("B-07", "Estado X", tono)]})

            self.assertIn("B-07", html)
            self.assertIn("Estado X", html)
            self.assertIn(icono, html)
            self.assertIn(f"bg-{tono}-soft", html)

    def test_el_tono_lo_decide_la_vista_y_uno_desconocido_es_neutro(self):
        html = render_to_string(MAPA, {"plazas": [_plaza(tono="inventado"), _plaza("A-02", tono=None)]})

        self.assertEqual(html.count("bg-secondary"), 2)
        self.assertNotIn("-soft", html)
        self.assertIn("fa-circle", html)

    def test_plaza_con_url_es_un_enlace_y_sin_url_no_se_puede_tabular(self):
        html = render_to_string(
            MAPA,
            {"plazas": [_plaza("A-01", url="/dispositivos/1/plazas/1/"), _plaza("A-02", "Ocupada", "info")]},
        )

        self.assertEqual(html.count("<a "), 1)
        self.assertIn('href="/dispositivos/1/plazas/1/"', html)
        self.assertNotIn("tabindex", html)
        self.assertNotIn("onclick", html)
        # el enlace lleva una clase bg-* (la regla global de enlaces no le pisa el color)
        enlace = re.search(r"<a [^>]*>", html).group(0)
        self.assertIn("bg-success-soft", enlace)
        self.assertIn("cursor-pointer", enlace)
        self.assertNotIn("aria-disabled", enlace)
        self.assertIn('aria-disabled="true" class="cursor-not-allowed', html)

    def test_plaza_elegida_se_marca_con_texto_y_aria_current(self):
        html = render_to_string(MAPA, {"plazas": [_plaza(url="/x", seleccionada=True)]})

        self.assertIn('aria-current="true"', html)
        self.assertIn("Elegida", html)
        self.assertNotIn("Elegida", render_to_string(MAPA, {"plazas": [_plaza(url="/x")]}))

    def test_el_detalle_se_trunca_con_title_y_se_escapa(self):
        html = render_to_string(MAPA, {"plazas": [_plaza(detalle="<b>Díaz</b>")]})

        self.assertIn("truncate", html)
        self.assertNotIn("<b>Díaz", html)
        self.assertIn("&lt;b&gt;D", html)
        self.assertIn('title="&lt;b&gt;', html)

    def test_el_codigo_se_lee_como_plaza(self):
        html = render_to_string(MAPA, {"plazas": [_plaza("C-04")]})

        self.assertIn('<span class="sr-only">Plaza </span>C-04', html)

    def test_detalle_completo_solo_cambia_el_title_y_mantiene_el_escapado(self):
        plaza = _plaza(detalle="hasta 18/11 08:46")
        html = render_to_string(MAPA, {"plazas": [plaza]})
        completo = 'hasta 18/11/2027 08:46 <b>"</b>'
        extendido = render_to_string(MAPA, {"plazas": [{**plaza, "detalle_completo": completo}]})
        self.assertEqual(
            extendido,
            html.replace('title="hasta 18/11 08:46"', 'title="hasta 18/11/2027 08:46 &lt;b&gt;&quot;&lt;/b&gt;"'),
        )
        self.assertEqual(render_to_string(MAPA, {"plazas": [{**plaza, "detalle_completo": ""}]}), html)

    def test_tiene_tope_de_200_y_avisa(self):
        plazas = [_plaza(f"P-{n:03d}") for n in range(250)]
        html = render_to_string(MAPA, {"plazas": plazas})

        self.assertEqual(html.count("<li>"), 200)
        self.assertIn("P-199", html)
        self.assertNotIn("P-200", html)
        self.assertIn("Mostrando 200 de 250 plazas.", html)

    def test_total_mayor_que_lo_enviado_avisa_sin_recortar(self):
        html = render_to_string(MAPA, {"plazas": [_plaza()], "total": 60})

        self.assertIn("Mostrando 1 de 60 plazas.", html)
        self.assertNotIn("Mostrando", render_to_string(MAPA, {"plazas": [_plaza()], "total": 1}))

    def test_sin_plazas_muestra_el_vacio(self):
        for contexto in ({}, {"plazas": []}):
            html = render_to_string(MAPA, contexto)

            self.assertIn("Este sector no tiene plazas", html)
            self.assertNotIn("<ul", html)

    def test_no_trae_estilos_en_linea_ni_scripts(self):
        html = render_to_string(MAPA, {"plazas": [_plaza(url="/x")]})

        self.assertNotIn("style=", html)
        self.assertNotIn("<script", html)


class LeyendaPlazasTest(SimpleTestCase):
    def test_cada_estado_es_una_pastilla_con_icono_y_texto(self):
        leyenda = [
            {"estado": "Disponible", "tono": "success"},
            {"estado": "Ocupada", "tono": "info"},
            {"estado": "Reservada", "tono": "warning"},
            {"estado": "Prestada", "tono": "brand"},
            {"estado": "Fuera de servicio", "tono": "danger"},
        ]
        html = render_to_string(LEYENDA, {"leyenda": leyenda})

        self.assertIn('aria-label="Leyenda de estados de plaza"', html)
        for item in leyenda:
            self.assertIn(item["estado"], html)
            self.assertIn(f'class="badge badge-{item["tono"]}"', html)
            self.assertIn(
                f'<i class="fas {ICONOS[item["tono"]]}" aria-hidden="true"></i> {item["estado"]}</span>', html
            )
        self.assertEqual(html.count("aria-hidden"), 5)

    def test_sin_leyenda_no_dibuja_nada(self):
        self.assertEqual(render_to_string(LEYENDA, {}).strip(), "")

    def test_usa_los_mismos_tonos_que_el_mapa(self):
        for tono in ICONOS:
            leyenda = render_to_string(LEYENDA, {"leyenda": [{"estado": "E", "tono": tono}]})
            mapa = render_to_string(MAPA, {"plazas": [_plaza(estado="E", tono=tono)]})

            for clase in (f"bg-{tono}-soft", f"text-fg-{tono}", ICONOS[tono]):
                self.assertIn(clase, mapa)
            self.assertIn(f"badge-{tono}", leyenda)
            self.assertIn(ICONOS[tono], leyenda)

    def test_tono_desconocido_dibuja_pastilla_gris_con_circulo(self):
        html = render_to_string(LEYENDA, {"leyenda": [{"estado": "E", "tono": "otro"}]})

        self.assertIn('class="badge badge-gray"', html)
        self.assertIn('<i class="fas fa-circle" aria-hidden="true">', html)


class GaleriaFotosTest(SimpleTestCase):
    def _foto(self, rotulo="fachada", **extra):
        return {"url": "/media/dispositivos/fotos/1.jpg", "rotulo": rotulo, **extra}

    def test_la_foto_es_lazy_con_alt_y_fecha(self):
        html = render_to_string(
            GALERIA,
            {"fotos": [self._foto(alt="Fachada del pabellón A", fecha=date(2026, 9, 6))]},
        )

        self.assertIn('loading="lazy"', html)
        self.assertIn('alt="Fachada del pabellón A"', html)
        self.assertIn('<time class="block text-body-subtle" datetime="2026-09-06">06/09/2026</time>', html)
        self.assertIn('src="/media/dispositivos/fotos/1.jpg"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn("se abre en una pestaña nueva", html)

    def test_sin_alt_usa_el_rotulo_y_nunca_queda_vacio(self):
        html = render_to_string(GALERIA, {"fotos": [self._foto("cocina")]})

        self.assertIn('alt="cocina"', html)
        self.assertNotIn('alt=""', html)

    def test_sin_fecha_no_dibuja_time(self):
        self.assertNotIn("<time", render_to_string(GALERIA, {"fotos": [self._foto()]}))

    def test_sin_url_dibuja_la_celda_con_camara_y_texto(self):
        html = render_to_string(GALERIA, {"fotos": [{"rotulo": "techo"}]})

        self.assertNotIn("<img", html)
        self.assertIn("fa-camera", html)
        self.assertIn("techo: sin imagen", html)

    def test_escapa_rotulo_y_alt(self):
        html = render_to_string(GALERIA, {"fotos": [self._foto("<i>x</i>", alt='"><script>')]})

        self.assertNotIn("<i>x", html)
        self.assertNotIn("<script", html)
        self.assertIn("&lt;i&gt;x", html)

    def test_tiene_tope_de_24_y_avisa(self):
        fotos = [self._foto(f"foto-{n:02d}") for n in range(30)]
        html = render_to_string(GALERIA, {"fotos": fotos})

        self.assertEqual(html.count("<img"), 24)
        self.assertIn("foto-23", html)
        self.assertNotIn("foto-24", html)
        self.assertIn("Mostrando 24 de 30 fotos.", html)

    def test_total_mayor_que_lo_enviado_avisa(self):
        html = render_to_string(GALERIA, {"fotos": [self._foto()], "total": 80})

        self.assertIn("Mostrando 1 de 80 fotos.", html)
        self.assertNotIn("Mostrando", render_to_string(GALERIA, {"fotos": [self._foto()]}))

    def test_sin_fotos_muestra_el_vacio(self):
        for contexto in ({}, {"fotos": []}):
            html = render_to_string(GALERIA, contexto)

            self.assertIn("Sin fotos", html)
            self.assertNotIn("<img", html)

    def test_no_trae_estilos_en_linea(self):
        self.assertNotIn("style=", render_to_string(GALERIA, {"fotos": [self._foto()]}))
