"""FE-18 · Badges de estado de Merenderos y semáforo «Sin datos» de Dispositivos.

Merenderos no tenía parcial de badges: las tres pantallas volcaban
``{{ objeto.get_estado_display }}`` como texto suelto, así que un merendero cerrado y
uno activo se leían igual. El inventario pide un parcial por módulo como **única**
fuente del mapa estado→badge (el de Dispositivos es el contrato de referencia); estos
tests fijan el mapa de los dos modelos de Merenderos y exigen que las pantallas lo
incluyan en vez de reinventarlo.

El tercer bloque cubría el otro síntoma de la misma ficha: en el detalle del
dispositivo, «Sin datos» —ausencia de información, no un problema— salía en el rojo de
`text-fg-danger`, porque la cadena de `{% if %}` del semáforo terminaba en un `else`
que lo atrapaba. **Se fue el 09-10-2026**: la franja de indicadores se dio de baja con
`RegistroDiario` y `CampoTipoDispositivo` (MVP v2, release A). La regla que fijaba —que
la ausencia de dato no se pinta de peligro— vale igual para los indicadores de la v2, y
vuelve con ellos.
"""

import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from programas.models import Merendero, SolicitudMerendero

REPO = Path(settings.BASE_DIR)

MERENDERO = "programas/merenderos/_estado_badge.html"
SOLICITUD = "programas/merenderos/_solicitud_estado_badge.html"

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


class MerenderoEstadoBadgeTests(SimpleTestCase):
    def render(self, estado):
        return badges(render_to_string(MERENDERO, {"merendero": Merendero(estado=estado)}))

    def test_mapa_estado_a_tono(self):
        tabla = [
            ("ACTIVO", "success", "Activo"),
            ("SUSPENDIDO", "warning", "Suspendido"),
            ("CERRADO", "gray", "Cerrado"),
        ]
        for estado, tono, texto in tabla:
            with self.subTest(estado=estado):
                self.assertEqual(self.render(estado), [(tono, texto, True)])

    def test_el_mapa_cubre_todos_los_estados_del_modelo(self):
        for estado in Merendero.Estado.values:
            with self.subTest(estado=estado):
                self.assertEqual(len(self.render(estado)), 1)

    def test_suspendido_no_es_danger(self):
        # Suspender es reversible (D-M01): es una advertencia, no un error.
        self.assertEqual(self.render("SUSPENDIDO"), [("warning", "Suspendido", True)])

    def test_cerrado_es_gris_y_no_rojo(self):
        self.assertEqual(self.render("CERRADO"), [("gray", "Cerrado", True)])


class SolicitudMerenderoEstadoBadgeTests(SimpleTestCase):
    def render(self, estado):
        return badges(render_to_string(SOLICITUD, {"solicitud": SolicitudMerendero(estado=estado)}))

    def test_mapa_estado_a_tono(self):
        tabla = [
            ("BORRADOR", "white", "Borrador"),
            ("EN_REVISION", "info", "En revisión"),
            ("OBSERVADA", "warning", "Observada"),
            ("APROBADA", "success", "Aprobada"),
            ("RECHAZADA", "danger", "Rechazada"),
        ]
        for estado, tono, texto in tabla:
            with self.subTest(estado=estado):
                self.assertEqual(self.render(estado), [(tono, texto, True)])

    def test_el_mapa_cubre_todos_los_estados_del_modelo(self):
        for estado in SolicitudMerendero.Estado.values:
            with self.subTest(estado=estado):
                self.assertEqual(len(self.render(estado)), 1)


class PantallasDeMerenderosUsanElParcialTests(SimpleTestCase):
    """El mapa vive en el parcial; ninguna pantalla vuelve a escribir el estado a mano."""

    PANTALLAS = {
        "programas/templates/programas/merenderos/list.html": MERENDERO,
        "programas/templates/programas/merenderos/detail.html": MERENDERO,
        "programas/templates/programas/merenderos/solicitudes.html": SOLICITUD,
    }

    def test_cada_pantalla_incluye_el_parcial_de_su_entidad(self):
        for ruta, parcial in self.PANTALLAS.items():
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertTrue(parcial in texto, f"{ruta} no incluye {parcial}")

    def test_ninguna_pantalla_vuelca_el_estado_como_texto_suelto(self):
        for ruta in self.PANTALLAS:
            with self.subTest(ruta=ruta):
                texto = (REPO / ruta).read_text(encoding="utf-8")
                self.assertNotIn("get_estado_display", texto, f"{ruta}: el estado va por el parcial")
