"""Piezas de UI del lote Emergencia: semáforo de SLA (badge y reloj), tarjeta de dispositivo
para derivar, contador de avance «N de N» y celda de diferencia de una conciliación."""

import re

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.templatetags.nodo_ui import menos

SEMAFORO = "components/_semaforo_sla.html"
TARJETA = "components/_tarjeta_dispositivo_derivar.html"
CONTADOR = "components/_contador_avance.html"
CELDA = "components/_celda_diferencia.html"


def _texto(html):
    """El texto visible, sin etiquetas y con los espacios colapsados."""
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


class SemaforoSlaTest(SimpleTestCase):
    ESTADOS = {
        "EN_TERMINO": ("badge-success", "fa-circle-check", "En término · 12 min"),
        "POR_VENCER": ("badge-warning", "fa-clock", "Por vencer · 12 min"),
        "FUERA": ("badge-danger", "fa-triangle-exclamation", "Fuera de SLA · 12 min"),
    }

    def _render(self, **contexto):
        return render_to_string(SEMAFORO, contexto)

    def test_cada_estado_lleva_texto_icono_y_color(self):
        # RU-19: el color nunca es el único portador.
        for estado, (variante, icono, texto) in self.ESTADOS.items():
            with self.subTest(estado=estado):
                html = self._render(estado=estado, minutos=12, tramo="derivar")

                self.assertIn(f'class="badge badge-dot {variante}"', html)
                self.assertIn(f'<i class="fas {icono}" aria-hidden="true"></i>', html)
                self.assertEqual(_texto(html), texto)
                self.assertIn(f'data-semaforo-sla="{estado}"', html)
                self.assertNotIn("role=", html)

    def test_un_estado_desconocido_dibuja_neutro_y_sin_minutos(self):
        for estado in ("INVENTADO", "", None, '"><script>'):
            with self.subTest(estado=estado):
                html = self._render(estado=estado, minutos=42, tramo="derivar", variante="reloj")

                self.assertIn('class="badge badge-dot badge-gray"', html)
                self.assertIn("fa-circle", html)
                self.assertEqual(_texto(html), "Sin SLA")
                self.assertIn('data-semaforo-sla=""', html)
                self.assertNotIn("<script>", html)
        self.assertEqual(_texto(render_to_string(SEMAFORO)), "Sin SLA")

    def test_el_reloj_lleva_texto_largo_y_role_status(self):
        en_termino = self._render(estado="EN_TERMINO", minutos=8, tramo="derivar", variante="reloj")
        por_vencer = self._render(estado="POR_VENCER", minutos=3, tramo="aceptar", variante="reloj")
        fuera = self._render(estado="FUERA", minutos=42, tramo="derivar", variante="reloj")

        self.assertEqual(_texto(en_termino), "Derivar vence en 8 min")
        # Por vencer se dice en palabras: el texto no puede ser el mismo que en término.
        self.assertEqual(_texto(por_vencer), "Por vencer · Aceptar vence en 3 min")
        self.assertEqual(_texto(fuera), "Derivar · Fuera de SLA · 42 min")
        for html, variante in ((en_termino, "badge-success"), (por_vencer, "badge-warning"), (fuera, "badge-danger")):
            self.assertIn('role="status"', html)
            self.assertIn(variante, html)
            self.assertEqual(html.count('aria-hidden="true"'), 1)

    def test_el_reloj_sin_tramo_no_inventa_uno(self):
        self.assertEqual(_texto(self._render(estado="EN_TERMINO", minutos=8, variante="reloj")), "Vence en 8 min")
        self.assertEqual(
            _texto(self._render(estado="POR_VENCER", minutos=8, variante="reloj")), "Por vencer · Vence en 8 min"
        )
        self.assertEqual(_texto(self._render(estado="FUERA", minutos=42, variante="reloj")), "Fuera de SLA · 42 min")

    def test_el_tramo_se_presenta_igual_venga_como_venga(self):
        for tramo in ("derivar", "DERIVAR", "Derivar"):
            with self.subTest(tramo=tramo):
                html = self._render(estado="EN_TERMINO", minutos=8, tramo=tramo, variante="reloj")
                self.assertEqual(_texto(html), "Derivar vence en 8 min")

    def test_sin_minutos_el_texto_no_los_lleva_y_un_cero_se_muestra(self):
        self.assertEqual(_texto(self._render(estado="FUERA")), "Fuera de SLA")
        self.assertEqual(_texto(self._render(estado="POR_VENCER", minutos=None)), "Por vencer")
        self.assertEqual(_texto(self._render(estado="EN_TERMINO", minutos="")), "En término")
        self.assertEqual(_texto(self._render(estado="FUERA", minutos=0)), "Fuera de SLA · 0 min")
        self.assertEqual(_texto(self._render(estado="EN_TERMINO", tramo="tomar", variante="reloj")), "Tomar en término")
        self.assertEqual(
            _texto(self._render(estado="POR_VENCER", tramo="tomar", variante="reloj")), "Por vencer · Tomar"
        )
        self.assertEqual(_texto(self._render(estado="POR_VENCER", variante="reloj")), "Por vencer")

    def test_una_variante_desconocida_es_el_badge_corto(self):
        html = self._render(estado="FUERA", minutos=42, tramo="derivar", variante="inventada")

        self.assertEqual(_texto(html), "Fuera de SLA · 42 min")
        self.assertNotIn("role=", html)

    def test_escapa_el_tramo(self):
        html = self._render(estado="EN_TERMINO", minutos=8, tramo="<b>x</b>", variante="reloj")

        self.assertNotIn("<b>", html)
        self.assertIn("&lt;b&gt;", html)


class TarjetaDispositivoDerivarTest(SimpleTestCase):
    def _dispositivo(self, **extra):
        dispositivo = {
            "pk": 7,
            "nombre": "CIS N.º 3",
            "localidad": "Resistencia",
            "libres": 9,
            "reservadas": 2,
            "distancia_km": 3.2,
            "marca": "ALCANZA",
            "faltan": 0,
        }
        dispositivo.update(extra)
        return dispositivo

    def _render(self, **extra):
        return render_to_string(TARJETA, {"dispositivo": self._dispositivo(**extra)})

    def test_muestra_nombre_localidad_plazas_y_distancia(self):
        html = self._render()
        texto = _texto(html)

        self.assertIn("data-tarjeta-dispositivo-derivar", html)
        self.assertIn('aria-labelledby="dispositivo-derivar-7-titulo"', html)
        self.assertIn('id="dispositivo-derivar-7-titulo"', html)
        self.assertIn("CIS N.º 3", texto)
        self.assertIn("Resistencia · a 3,2 km", texto)
        self.assertIn("Plazas libres 9", texto)
        self.assertIn("Reservadas 2", texto)

    def test_sin_distancia_lo_dice_en_texto(self):
        for extra in ({"distancia_km": None}, {}):
            dispositivo = self._dispositivo(**extra)
            if not extra:
                del dispositivo["distancia_km"]
            texto = _texto(render_to_string(TARJETA, {"dispositivo": dispositivo}))

            self.assertIn("distancia desconocida", texto)
            self.assertNotIn(" km", texto)

    def test_una_distancia_cero_no_es_desconocida(self):
        self.assertIn("a 0,0 km", _texto(self._render(distancia_km=0)))

    def test_la_marca_va_en_texto_ademas_del_color(self):
        casos = (
            ({"marca": "ALCANZA"}, "badge-success", "Alcanza"),
            ({"marca": "FALTAN", "faltan": 2}, "badge-warning", "Faltan 2 plazas"),
            ({"marca": "FALTAN", "faltan": 1}, "badge-warning", "Falta 1 plaza"),
            ({"marca": "FALTAN", "faltan": None}, "badge-warning", "Faltan plazas"),
            ({"marca": "SIN_PLAZAS"}, "badge-danger", "Sin plazas"),
        )
        for extra, variante, texto in casos:
            with self.subTest(extra=extra):
                html = self._render(**extra)

                self.assertInHTML(f'<span class="badge badge-dot {variante}">{texto}</span>', html)
                self.assertEqual(html.count('class="badge '), 1)

    def test_una_marca_desconocida_no_se_dibuja(self):
        for marca in ("INVENTADA", "", None):
            with self.subTest(marca=marca):
                self.assertNotIn("badge", self._render(marca=marca))

    def test_sin_accion_no_hay_pie(self):
        for extra in ({}, {"accion_url": "/derivar/7/"}, {"accion_texto": "Derivar a CIS N.º 3"}):
            with self.subTest(extra=extra):
                html = self._render(**extra)

                self.assertNotIn("<footer", html)
                self.assertNotIn("btn-nodo", html)

    def test_la_accion_es_un_enlace_con_el_texto_de_la_vista(self):
        html = self._render(accion_url="/derivar/7/", accion_texto="Derivar a CIS N.º 3")

        self.assertInHTML('<a href="/derivar/7/" class="btn-nodo btn-brand btn-sm">Derivar a CIS N.º 3</a>', html)
        self.assertNotIn("disabled", html)

    def test_con_motivo_la_accion_queda_deshabilitada_y_explicada(self):
        html = self._render(
            marca="SIN_PLAZAS",
            libres=0,
            accion_url="/derivar/7/",
            accion_texto="Derivar a CIS N.º 3",
            accion_motivo="Sin plazas disponibles",
        )

        self.assertInHTML(
            '<button type="button" class="btn-nodo btn-brand btn-sm" disabled '
            'aria-describedby="dispositivo-derivar-7-motivo">Derivar a CIS N.º 3</button>',
            html,
        )
        self.assertInHTML(
            '<p id="dispositivo-derivar-7-motivo" class="text-xs text-body-subtle">Sin plazas disponibles</p>', html
        )
        # El motivo gana: el destino no llega al HTML.
        self.assertNotIn("/derivar/7/", html)
        self.assertNotIn("<a ", html)

    def test_la_tarjeta_no_infiere_el_bloqueo_de_la_marca(self):
        # Sin plazas y sin motivo: la vista decidió que se puede (p. ej. elegir destino de un kit).
        html = self._render(marca="SIN_PLAZAS", libres=0, accion_url="/elegir/7/", accion_texto="Elegir")

        self.assertIn('href="/elegir/7/"', html)
        self.assertNotIn("disabled", html)

    def test_sin_conteos_muestra_cero_y_sin_localidad_lo_dice(self):
        dispositivo = {"pk": 1, "nombre": "Refugio"}
        texto = _texto(render_to_string(TARJETA, {"dispositivo": dispositivo}))

        self.assertIn("Plazas libres 0", texto)
        self.assertIn("Reservadas 0", texto)
        self.assertIn("Sin localidad cargada · distancia desconocida", texto)

    def test_escapa_el_texto_de_la_vista(self):
        html = self._render(
            nombre="<script>alert(1)</script>",
            localidad="<b>x</b>",
            accion_texto="<i>Derivar</i>",
            accion_motivo="<u>no</u>",
        )

        for crudo in ("<script>", "<b>x", "<i>Derivar", "<u>no"):
            self.assertNotIn(crudo, html)
        self.assertIn("&lt;script&gt;", html)

    def test_los_iconos_van_ocultos_al_lector(self):
        html = self._render()

        self.assertEqual(html.count("<i "), html.count('aria-hidden="true"'))


class ContadorAvanceTest(SimpleTestCase):
    def _render(self, **contexto):
        return render_to_string(CONTADOR, contexto)

    def _barra(self, html):
        return re.search(r'<span [^>]*role="progressbar"[^>]*>', html).group(0)

    def test_dice_n_de_n_con_la_etiqueta_y_es_una_barra_en_unidades(self):
        html = self._render(hechos=3, total=7, etiqueta="confirmadas")
        barra = self._barra(html)

        self.assertIn("data-contador-avance", html)
        self.assertEqual(_texto(html), "3 de 7 confirmadas")
        self.assertIn('aria-valuemin="0"', barra)
        self.assertIn('aria-valuemax="7"', barra)
        self.assertIn('aria-valuenow="3"', barra)
        self.assertIn('aria-valuetext="3 de 7 confirmadas"', barra)
        self.assertIn('aria-label="Avance"', barra)
        self.assertIn('style="--avance:43%"', html)
        self.assertIn("bg-brand", html)
        self.assertNotIn("success", html)

    def test_total_cero_no_divide_por_cero(self):
        for contexto in ({"hechos": 0, "total": 0}, {"hechos": None, "total": None}, {}):
            with self.subTest(contexto=contexto):
                html = self._render(etiqueta="confirmadas", **contexto)
                barra = self._barra(html)

                self.assertEqual(_texto(html), "0 de 0 confirmadas")
                self.assertIn('aria-valuemax="0"', barra)
                self.assertIn('aria-valuenow="0"', barra)
                self.assertIn('style="--avance:0%"', html)
                # Sin nada que contar no hay «todo hecho».
                self.assertNotIn("success", html)

    def test_con_todo_hecho_lo_refuerza_con_tono_e_icono(self):
        html = self._render(hechos=7, total=7, etiqueta="confirmadas")

        self.assertEqual(_texto(html), "7 de 7 confirmadas")
        self.assertIn('style="--avance:100%"', html)
        self.assertIn("bg-success", html)
        self.assertIn('<i class="fas fa-circle-check text-fg-success" aria-hidden="true"></i>', html)
        self.assertNotIn("bg-brand", html)

    def test_sin_etiqueta_queda_el_n_de_n(self):
        html = self._render(hechos=1, total=4)

        self.assertEqual(_texto(html), "1 de 4")
        self.assertIn('aria-valuetext="1 de 4"', html)

    def test_el_nombre_accesible_se_puede_pasar_y_se_escapa(self):
        html = self._render(hechos=1, total=4, etiqueta="<b>x</b>", nombre='Integrantes "confirmados"')

        self.assertIn('aria-label="Integrantes &quot;confirmados&quot;"', html)
        self.assertNotIn("<b>", html)


class CeldaDiferenciaTest(SimpleTestCase):
    def _render(self, enviada, recibida):
        return render_to_string(CELDA, {"enviada": enviada, "recibida": recibida})

    def test_sin_diferencia_es_texto_neutro(self):
        for enviada, recibida in ((10, 10), (0, 0)):
            html = self._render(enviada, recibida)

            self.assertEqual(_texto(html), "sin diferencia")
            self.assertNotIn("badge", html)

    def test_si_falta_lleva_signo_palabra_y_tono(self):
        self.assertInHTML('<span class="badge badge-danger">−2 · faltan</span>', self._render(10, 8))
        self.assertInHTML('<span class="badge badge-danger">−1 · falta</span>', self._render(10, 9))

    def test_si_sobra_lleva_signo_palabra_y_tono(self):
        self.assertInHTML('<span class="badge badge-warning">+1 · de más</span>', self._render(10, 11))
        self.assertInHTML('<span class="badge badge-warning">+5 · de más</span>', self._render(0, 5))

    def test_todavia_no_recibida_es_una_raya_con_texto_para_el_lector(self):
        html = self._render(10, None)

        self.assertInHTML('<span class="text-body-subtle" aria-hidden="true">—</span>', html)
        self.assertInHTML('<span class="sr-only">Todavía no recibida</span>', html)
        self.assertNotIn("badge", html)
        self.assertNotIn("sin diferencia", html)

    def test_un_dato_invalido_no_inventa_sin_diferencia(self):
        for enviada, recibida in ((None, 3), (10, "x"), ("", 3)):
            with self.subTest(enviada=enviada, recibida=recibida):
                html = self._render(enviada, recibida)

                self.assertIn("—", html)
                self.assertInHTML('<span class="sr-only">Sin dato</span>', html)
                self.assertNotIn("sin diferencia", html)
                self.assertNotIn("badge", html)

    def test_el_filtro_menos_resta_enteros_o_devuelve_none(self):
        self.assertEqual(menos(8, 10), -2)
        self.assertEqual(menos("11", 10), 1)
        self.assertEqual(menos(0, 0), 0)
        self.assertIsNone(menos(None, 10))
        self.assertIsNone(menos(10, None))
        self.assertIsNone(menos("x", 1))
