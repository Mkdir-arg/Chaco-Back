"""Mapa de estados de Becas: un color por estado en todas las pantallas (DC-1..DC-4).

Tabla estado -> badge por parcial. Cada parcial es la única fuente del mapeo de su
entidad; estos tests fijan el mapa para que ninguna pantalla vuelva a inventar colores.
Se renderizan con instancias sin guardar (sin base de datos).
"""

import re
from datetime import timedelta

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.utils import timezone

from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento, Subsegmento

FORMULARIO = "programas/becas/_formulario_estado_badge.html"
RELEVAMIENTO = "programas/becas/relevamientos/_estado_badge.html"
CONVOCATORIA = "programas/becas/_convocatoria_estado_badge.html"
PAUSABLE = "programas/becas/_pausable_estado_badge.html"

_SPAN = re.compile(r'<span class="([^"]*)"[^>]*>([^<]*)</span>')


def badges(html):
    """[(tono, texto, con_dot), ...] de cada badge del HTML, en orden."""
    resultado = []
    for clases, texto in _SPAN.findall(html):
        partes = clases.split()
        assert "badge" in partes, clases
        tonos = [p for p in partes if p.startswith("badge-") and p != "badge-dot"]
        assert len(tonos) == 1, f"un solo tono por badge: {clases}"
        resultado.append((tonos[0].removeprefix("badge-"), texto.strip(), "badge-dot" in partes))
    return resultado


class FormularioEstadoBadgeTests(SimpleTestCase):
    def render(self, **ctx):
        return badges(render_to_string(FORMULARIO, ctx))

    def test_mapa_estado_a_tono(self):
        tabla = [
            ("ENVIADO", "warning", "Enviado"),
            ("APROBADO", "success", "Aprobado"),
            ("RECHAZADO", "danger", "Rechazado"),
            ("BAJA", "gray", "Dado de baja"),
        ]
        for estado, tono, texto in tabla:
            with self.subTest(estado=estado):
                self.assertEqual(self.render(estado=estado), [(tono, texto, True)])

    def test_enviado_es_warning_sin_pasar_color(self):
        # Antes el default era gris y solo algunas pantallas pasaban color_enviado="warning".
        self.assertEqual(self.render(estado="ENVIADO"), [("warning", "Enviado", True)])

    def test_dot_siempre_aunque_el_include_no_lo_pida(self):
        for estado in ("ENVIADO", "APROBADO", "RECHAZADO", "BAJA"):
            with self.subTest(estado=estado):
                self.assertTrue(all(dot for _, _, dot in self.render(estado=estado)))

    def test_include_existente_con_dot_y_color_enviado_sigue_igual(self):
        # relevamiento_detail, formulario_list y personas_list lo llaman así.
        self.assertEqual(
            self.render(estado="ENVIADO", dot=True, color_enviado="warning"),
            [("warning", "Enviado", True)],
        )

    def test_lista_de_espera_se_suma_al_estado(self):
        tabla = [
            ("ENVIADO", "warning", "Enviado"),
            ("APROBADO", "success", "Aprobado"),
        ]
        for estado, tono, texto in tabla:
            with self.subTest(estado=estado):
                self.assertEqual(
                    self.render(estado=estado, en_espera_activa=True),
                    [(tono, texto, True), ("warning", "Lista de espera", False)],
                )

    def test_sin_espera_no_hay_badge_de_lista_de_espera(self):
        self.assertEqual(self.render(estado="ENVIADO", en_espera_activa=False), [("warning", "Enviado", True)])


class RelevamientoEstadoBadgeTests(SimpleTestCase):
    def render(self, rel):
        return badges(render_to_string(RELEVAMIENTO, {"rel": rel}))

    def test_mapa_estado_a_tono(self):
        tabla = [
            ("ASIGNADO", "gray", "Asignado"),
            ("EN_CURSO", "warning", "En curso"),
            ("FINALIZANDO", "warning", "Finalizando (sync)"),
            ("FINALIZADO", "brand", "Finalizado"),
            ("EN_REVISION", "info", "En revisión"),
            ("TERMINADO", "success", "Terminado"),
        ]
        for estado, tono, texto in tabla:
            with self.subTest(estado=estado):
                self.assertEqual(self.render(Relevamiento(estado=estado)), [(tono, texto, True)])

    def test_vencido_es_warning_como_la_convocatoria(self):
        rel = Relevamiento(estado="EN_CURSO", fecha_hasta=timezone.now() - timedelta(days=1))
        self.assertEqual(
            self.render(rel),
            [("warning", "En curso", True), ("warning", "Vencido", True)],
        )


class ConvocatoriaEstadoBadgeTests(SimpleTestCase):
    def convocatoria(self, *, activo=True, vencida=False, pausada=False, segmento_pausado=False):
        segmento = Segmento(nombre="S", pausado=segmento_pausado, pausa_motivo="motivo segmento")
        hoy = timezone.localdate()
        return Convocatoria(
            nombre="C",
            segmento=segmento,
            activo=activo,
            pausado=pausada,
            pausa_motivo="motivo propio",
            fecha_fin=hoy - timedelta(days=1) if vencida else hoy + timedelta(days=10),
        )

    def render(self, conv):
        return badges(render_to_string(CONVOCATORIA, {"convocatoria": conv}))

    def test_mapa_estado_a_tono(self):
        tabla = [
            ({"activo": True}, "success", "Activa"),
            ({"activo": False}, "gray", "Cerrada"),
            ({"activo": True, "vencida": True}, "warning", "Vencida"),
            ({"activo": True, "pausada": True}, "warning", "Pausada"),
            ({"activo": True, "segmento_pausado": True}, "warning", "Pausada"),
        ]
        for kwargs, tono, texto in tabla:
            with self.subTest(**kwargs):
                self.assertEqual(self.render(self.convocatoria(**kwargs)), [(tono, texto, True)])

    def test_precedencia_pausa_vencida_activa_cerrada(self):
        # pausa > vencida
        self.assertEqual(self.render(self.convocatoria(vencida=True, pausada=True))[0][1], "Pausada")
        # pausa > cerrada (misma lógica que el encabezado de convocatoria_detail)
        self.assertEqual(self.render(self.convocatoria(activo=False, pausada=True))[0][1], "Pausada")
        # vencida solo aplica si sigue activa: cerrada y vencida es «Cerrada»
        self.assertEqual(self.render(self.convocatoria(activo=False, vencida=True))[0][1], "Cerrada")

    def test_pausada_lleva_el_motivo_en_title(self):
        html = render_to_string(CONVOCATORIA, {"convocatoria": self.convocatoria(segmento_pausado=True)})
        self.assertIn('title="motivo segmento"', html)


class PausableEstadoBadgeTests(SimpleTestCase):
    def render(self, objeto, **ctx):
        return badges(render_to_string(PAUSABLE, {"objeto": objeto, **ctx}))

    def test_segmento(self):
        tabla = [
            (Segmento(nombre="S", activo=True), "success", "Activo"),
            (Segmento(nombre="S", activo=False), "gray", "Inactivo"),
            (Segmento(nombre="S", activo=True, pausado=True), "warning", "Pausado"),
            (Segmento(nombre="S", activo=False, pausado=True), "warning", "Pausado"),
        ]
        for objeto, tono, texto in tabla:
            with self.subTest(activo=objeto.activo, pausado=objeto.pausado):
                self.assertEqual(self.render(objeto), [(tono, texto, True)])

    def test_subsegmento_hereda_la_pausa_del_segmento(self):
        tabla = [
            (Subsegmento(nombre="Sub", segmento=Segmento(nombre="S")), "success", "Activo"),
            (Subsegmento(nombre="Sub", segmento=Segmento(nombre="S", pausado=True)), "warning", "Pausado"),
            (Subsegmento(nombre="Sub", pausado=True, segmento=Segmento(nombre="S")), "warning", "Pausado"),
        ]
        for objeto, tono, texto in tabla:
            with self.subTest(objeto=objeto):
                self.assertEqual(self.render(objeto), [(tono, texto, True)])

    def test_programa_sin_campo_activo_nunca_sale_inactivo(self):
        self.assertEqual(self.render(ProgramaSiis(nombre="P", siis_programa_id=1)), [("success", "Activo", True)])

    def test_programa_pausado_es_warning_no_danger(self):
        programa = ProgramaSiis(nombre="P", siis_programa_id=1, pausado=True, pausa_motivo="mantenimiento")
        self.assertEqual(self.render(programa), [("warning", "Pausado", True)])
        self.assertEqual(self.render(programa, solo_manual=True), [("warning", "Pausado", True)])

    def test_programa_bloqueado_por_siis_depende_de_solo_manual(self):
        programa = ProgramaSiis(nombre="P", siis_programa_id=1, siis_programa_estado="INACTIVO")
        # pausa_efectiva incluye el bloqueo por SIIS...
        self.assertEqual(self.render(programa), [("warning", "Pausado", True)])
        # ...pero las pantallas de programa lo muestran aparte: solo_manual mira solo `pausado`.
        self.assertEqual(self.render(programa, solo_manual=True), [("success", "Activo", True)])
