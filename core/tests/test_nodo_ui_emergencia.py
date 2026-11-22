"""Piezas de UI del lote Emergencia: semáforo de SLA (badge y reloj), tarjeta de dispositivo
para derivar, contador de avance «N de N», celda de diferencia de una conciliación y barra con
marcas de umbral."""

import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from core.templatetags.nodo_ui import entero_o_none, menos, porcentaje_barra
from programas.services.ocupacion import Conteo, tension_de_ocupacion

SEMAFORO = "components/_semaforo_sla.html"
TARJETA = "components/_tarjeta_dispositivo_derivar.html"
CONTADOR = "components/_contador_avance.html"
CELDA = "components/_celda_diferencia.html"
BARRA = "components/_barra_umbral.html"


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

    def test_con_texto_tiempo_el_lapso_se_lee_como_lo_escribio_el_selector(self):
        # Una derivación que nadie aceptó en dos días se lee «48 h», no «2880 min».
        fila = self._render(estado="FUERA", minutos=2880, tramo="aceptar", texto_tiempo="48 h")
        reloj = self._render(estado="EN_TERMINO", minutos=300, tramo="aceptar", texto_tiempo="5 h", variante="reloj")
        fuera = self._render(estado="FUERA", minutos=4320, tramo="aceptar", texto_tiempo="3 d", variante="reloj")

        self.assertEqual(_texto(fila), "Fuera de SLA · 48 h")
        self.assertEqual(_texto(reloj), "Aceptar vence en 5 h")
        self.assertEqual(_texto(fuera), "Aceptar · Fuera de SLA · 3 d")

    def test_texto_tiempo_sin_minutos_no_se_muestra_y_vacio_no_cambia_nada(self):
        self.assertEqual(_texto(self._render(estado="FUERA", texto_tiempo="48 h")), "Fuera de SLA")
        self.assertEqual(
            self._render(estado="FUERA", minutos=42, texto_tiempo=""), self._render(estado="FUERA", minutos=42)
        )
        self.assertEqual(_texto(self._render(estado="INVENTADO", minutos=42, texto_tiempo="48 h")), "Sin SLA")

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

    def test_con_item_lo_nombra_dentro_del_badge(self):
        faltan = render_to_string(CELDA, {"enviada": 12, "recibida": 10, "item": "Agua 6 l"})
        sobra = render_to_string(CELDA, {"enviada": 10, "recibida": 11, "item": "Colchón"})

        self.assertInHTML('<span class="badge badge-danger">−2 · faltan (Agua 6 l)</span>', faltan)
        self.assertInHTML('<span class="badge badge-warning">+1 · de más (Colchón)</span>', sobra)
        self.assertEqual(_texto(render_to_string(CELDA, {"enviada": 3, "recibida": 3, "item": "X"})), "sin diferencia")

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


class _TipoConUmbrales:
    umbral_ocupacion_amarillo = 70
    umbral_ocupacion_rojo = 85


class BarraUmbralTest(SimpleTestCase):
    def _render(self, **contexto):
        return render_to_string(BARRA, contexto)

    def _de_tension(self, ocupadas, operativas, *, tipo=None, **extra):
        tension = tension_de_ocupacion(
            Conteo(totales=operativas, ocupadas=ocupadas, reservadas=0, prestadas=0), tipo=tipo
        )
        return self._render(
            valor=tension.ocupadas,
            maximo=tension.operativas,
            porcentaje=tension.porcentaje,
            tono=tension.tono,
            etiqueta=tension.etiqueta,
            **extra,
        )

    def _sr(self, html):
        return re.search(r'<span class="sr-only">([^<]*)</span>', html).group(1)

    def test_con_umbrales_dibuja_marcas_tono_cifra_y_badge(self):
        # TC-1175-01: la red al 88 % con el corte general 60/80.
        html = self._de_tension(1633, 1850, umbral_exigida=60, umbral_critica=80)

        self.assertIn('style="--avance:88%"', html)
        self.assertIn(
            'class="nodo-barra-umbral-relleno nodo-ficha-medidor block h-full max-w-full rounded-full bg-danger"', html
        )
        self.assertIn('style="--umbral:60%" title="Exigida desde 60 %" data-marca="exigida"', html)
        self.assertIn('style="--umbral:80%" title="Crítica desde 80 %" data-marca="critica"', html)
        self.assertIn('<span class="badge badge-danger whitespace-nowrap">', html)
        self.assertIn('<i class="fas fa-circle-exclamation" aria-hidden="true"></i> Crítica', html)
        self.assertIn(">88 %</span>", html)
        self.assertIn("Exigida desde 60 %</span>", html)
        self.assertIn("Crítica desde 80 %</span>", html)

    def test_las_marcas_son_las_del_tipo(self):
        # TC-1175-02: un tipo 70/85 marca ahí y el nivel responde a esos umbrales.
        tipo = _TipoConUmbrales()
        html = self._de_tension(
            58, 70, tipo=tipo, umbral_exigida=tipo.umbral_ocupacion_amarillo, umbral_critica=tipo.umbral_ocupacion_rojo
        )

        self.assertIn('style="--umbral:70%"', html)
        self.assertIn('style="--umbral:85%"', html)
        self.assertNotIn("--umbral:60%", html)
        self.assertNotIn("--umbral:80%", html)
        self.assertEqual(self._sr(html), "Ocupación: 83 por ciento, nivel Exigida.")
        self.assertIn("bg-warning", html)

    def test_un_tono_icono_y_texto_por_nivel(self):
        # TC-1175-03: el nivel nunca depende solo del color.
        tipo = _TipoConUmbrales()
        casos = {
            40: ("bg-success", "badge-success", "fa-circle-check", "Normal"),
            75: ("bg-warning", "badge-warning", "fa-triangle-exclamation", "Exigida"),
            90: ("bg-danger", "badge-danger", "fa-circle-exclamation", "Crítica"),
        }
        for ocupadas, (relleno, badge, icono, etiqueta) in casos.items():
            with self.subTest(ocupadas=ocupadas):
                html = self._de_tension(ocupadas, 100, tipo=tipo, umbral_exigida=70, umbral_critica=85)

                self.assertIn(
                    f"nodo-barra-umbral-relleno nodo-ficha-medidor block h-full max-w-full rounded-full {relleno}", html
                )
                self.assertIn(f"badge {badge}", html)
                self.assertIn(f'<i class="fas {icono}" aria-hidden="true"></i> {etiqueta}', html)

    def test_sin_umbrales_es_la_variante_sin_marcas_con_cifra(self):
        # TC-1175-04: el embudo.
        html = self._render(valor=204, maximo=212, texto="204 casos", nombre="Tomados")

        self.assertNotIn("nodo-barra-umbral-marca", html)
        self.assertNotIn("nodo-barra-umbral-muestra", html)
        self.assertNotIn("desde", html)
        self.assertNotIn("badge", html)
        self.assertIn(
            'class="nodo-barra-umbral-relleno nodo-ficha-medidor block h-full max-w-full rounded-full bg-brand" style="--avance:96%"',
            html,
        )
        self.assertIn(">204 casos</span>", html)
        self.assertEqual(self._sr(html), "Tomados: 96 por ciento (204 casos).")

    def test_vacia_y_llena(self):
        # TC-1175-05.
        vacia = self._de_tension(0, 40, umbral_exigida=60, umbral_critica=80)
        llena = self._de_tension(40, 40, umbral_exigida=60, umbral_critica=80)

        self.assertIn('style="--avance:0%"', vacia)
        self.assertIn(">0 %</span>", vacia)
        self.assertIn("Normal", vacia)
        self.assertIn('style="--avance:100%"', llena)
        self.assertIn(">100 %</span>", llena)

    def test_sin_plazas_operativas_dice_raya_y_sin_plazas(self):
        # TC-1175-06: no es un 0 %.
        html = self._de_tension(0, 0, umbral_exigida=60, umbral_critica=80)

        self.assertNotIn("--avance", html)
        self.assertNotIn(">0 %</span>", html)
        self.assertIn(">—</span>", html)
        self.assertIn('<span class="badge badge-gray whitespace-nowrap">', html)
        self.assertIn("fa-circle-minus", html)
        self.assertEqual(self._sr(html), "Ocupación: sin cifra, nivel Sin plazas.")
        self.assertIn(">—</span>", self._render())

    def test_el_texto_equivalente_dice_valor_y_nivel_y_lo_grafico_va_oculto(self):
        # TC-1175-07.
        html = self._de_tension(1633, 1850, umbral_exigida=60, umbral_critica=80, nombre="Capacidad de la red")

        self.assertEqual(self._sr(html), "Capacidad de la red: 88 por ciento, nivel Crítica.")
        self.assertIn('<div class="flex items-center gap-3" aria-hidden="true">', html)
        self.assertNotIn("role=", html)

    def test_escapa_lo_que_escribe_la_vista(self):
        html = self._render(valor=1, maximo=2, nombre="<b>x</b>", texto='"><script>', etiqueta="<i>y</i>")

        self.assertNotIn("<b>", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<i>y</i>", html)

    def test_un_umbral_que_no_es_numero_no_se_dibuja(self):
        for basura in ("50%;background:red", "x", ""):
            with self.subTest(umbral=basura):
                html = self._render(valor=1, maximo=2, umbral_exigida=basura, umbral_critica=80)

                self.assertNotIn("background:red", html)
                self.assertNotIn('data-marca="exigida"', html)
                self.assertNotIn("Exigida desde", html)
                self.assertNotIn("--umbral:%", html)
                self.assertIn('style="--umbral:80%"', html)
                self.assertIn("Crítica desde 80 %", html)

    def test_un_umbral_cero_dibuja_marca_y_leyenda(self):
        # MinValueValidator(0): un umbral amarillo 0 es válido y el nivel Exigida lo usó.
        html = self._render(valor=1, maximo=2, umbral_exigida=0, umbral_critica=80)

        self.assertIn('style="--umbral:0%" title="Exigida desde 0 %" data-marca="exigida"', html)
        self.assertIn("Exigida desde 0 %</span>", html)

    def test_entero_o_none(self):
        self.assertEqual(entero_o_none(0), 0)
        self.assertEqual(entero_o_none("70"), 70)
        self.assertIsNone(entero_o_none(None))
        self.assertIsNone(entero_o_none(""))
        self.assertIsNone(entero_o_none("50%;x"))

    def test_porcentaje_barra(self):
        self.assertEqual(porcentaje_barra(1633, 1850), 88)
        self.assertEqual(porcentaje_barra(0, 40), 0)
        self.assertEqual(porcentaje_barra(5, 0), None)
        self.assertEqual(porcentaje_barra(None, 10), None)
        self.assertEqual(porcentaje_barra(1, 3, 34), 34)
        self.assertEqual(porcentaje_barra(1, 3, "x"), None)
        self.assertEqual(porcentaje_barra(1, 3, None), 33)

    def test_la_pista_lleva_su_clase_gancho_y_el_alto_contraste_la_usa(self):
        """MINOR de la auditoría del PR #1210: el alto contraste no depende de la posición del span."""
        self.assertIn('class="nodo-barra-umbral-pista block h-2', self._render(valor=1, maximo=2))
        css = (Path(settings.BASE_DIR) / "static/custom/css/nodo-barra-umbral.css").read_text(encoding="utf-8")
        self.assertIn(".nodo-barra-umbral-pista {", css)
        self.assertNotIn("first-child", css)

    def test_porcentaje_barra_delega_en_entero_o_none(self):
        self.assertEqual(porcentaje_barra("7", "10"), 70)
        self.assertEqual(porcentaje_barra("x", 10), None)
        self.assertEqual(porcentaje_barra(1, 3, 88.0), 88)
