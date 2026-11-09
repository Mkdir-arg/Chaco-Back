"""Detalle del dispositivo en el celular (390 px): solapas, Equipo e indicadores.

El defecto eran tres: las solapas se achicaban y se pisaban (los botones del `flex` no llevaban
`shrink-0`), el Rol y el Responsable del Equipo quedaban bajo la columna fija de acciones, y
la caja de ícono de las tarjetas «tablero» le dejaba ~40 px al rótulo. Acá se fija lo que se puede
medir sin navegador: el marcado y el CSS. Cada guarda se verificó con mutación.
"""

import re

from django.conf import settings
from django.urls import reverse

from programas.tests.test_dispositivos_equipo_ui_411 import BaseUI


class SolapasEnUnaFilaTests(BaseUI):
    def test_cada_solapa_no_se_achica(self):
        """Sin `shrink-0` el botón cede ancho y el ícono, el texto y el conteo se encimen."""

        self._entrar(self.admin)
        html = self.client.get(self.url_detalle).content.decode()
        botones = re.findall(r'<button[^>]*role="tab"[^>]*>', html)

        self.assertGreaterEqual(len(botones), 5)
        for boton in botones:
            self.assertIn("shrink-0", boton)
            self.assertIn("whitespace-nowrap", boton)

    def test_la_barra_scrollea_en_horizontal(self):
        self._entrar(self.admin)
        html = self.client.get(self.url_detalle).content.decode()
        lista = re.search(r'<div class="([^"]*)" role="tablist"', html)

        self.assertIsNotNone(lista)
        self.assertIn("overflow-x-auto", lista.group(1))

    def test_las_clases_de_la_barra_estan_en_el_css_compilado(self):
        css = (settings.BASE_DIR / "static" / "custom" / "css" / "tailwind.css").read_text(encoding="utf-8")
        for clase in (".shrink-0", ".overflow-x-auto", ".whitespace-nowrap", ".gap-1", ".px-3"):
            self.assertIn(clase, css)


class EquipoEnCelularTests(BaseUI):
    def test_rol_y_responsable_van_tambien_bajo_el_nombre(self):
        self._entrar(self.admin)
        html = self.client.get(reverse("dispositivos:detalle", args=[self.disp_a.pk]) + "?tab=equipo").content.decode()
        panel = html.split('id="panel-equipo"', 1)[1].split('id="panel-historial"', 1)[0]
        fila = panel.split("<tbody>", 1)[1].split("</tr>", 1)[0]

        # Bajo el nombre (solo celular) y en sus columnas (desde lg).
        self.assertIn('class="lg:hidden', fila)
        self.assertEqual(fila.count("Responsable</span>"), 2)

    def test_las_columnas_rol_y_responsable_se_ocultan_en_celular(self):
        self._entrar(self.admin)
        html = self.client.get(reverse("dispositivos:detalle", args=[self.disp_a.pk]) + "?tab=equipo").content.decode()
        panel = html.split('id="panel-equipo"', 1)[1].split('id="panel-historial"', 1)[0]

        self.assertIn('<th class="nodo-th hidden lg:table-cell">Rol</th>', panel)
        self.assertIn('<th class="nodo-th hidden lg:table-cell">Responsable</th>', panel)
        self.assertIn(
            r".lg\:table-cell", (settings.BASE_DIR / "static/custom/css/tailwind.css").read_text(encoding="utf-8")
        )


class TarjetaTableroEnCelularTests(BaseUI):
    def test_la_caja_del_icono_baja_encima_del_rotulo_bajo_480_px(self):
        css = (settings.BASE_DIR / "static" / "custom" / "css" / "nodo-stat-card.css").read_text(encoding="utf-8")
        bloque = re.search(r"@media \(max-width: 479\.98px\)\s*\{(.*?)\n\}", css, re.S)

        self.assertIsNotNone(bloque)
        self.assertIn(".nodo-stat-tablero > div:first-child", bloque.group(1))
        self.assertIn("flex-direction: column-reverse", bloque.group(1))
