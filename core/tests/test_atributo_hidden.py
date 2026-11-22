"""El atributo `hidden` oculta siempre, y «Calcular distancia por calle» no se ve sin Google Maps (#1297).

* **CSS** — `utils.css` (que carga el shell del backoffice) declara `[hidden] { display: none !important; }`;
  sin eso, `.btn-nodo { display: inline-flex }` le ganaba al `hidden` del navegador y el botón se veía sin
  hacer nada. El portal ciudadano no carga `utils.css`: queda como estaba.
* **JS** (`nodo-derivar-distancias.js`, corrido en node con un DOM mínimo; sin node se saltea) — costos de
  Google: sin key no se engancha nada y el botón queda oculto; con key el botón aparece pero abrir la página no
  le manda nada a Google; el clic calcula una vez aunque lleguen clics repetidos.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS = Path(settings.BASE_DIR) / "static" / "custom" / "css"
JS = Path(settings.BASE_DIR) / "static" / "custom" / "js" / "nodo-derivar-distancias.js"
TEMPLATES = Path(settings.BASE_DIR)


def _sin_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


class ReglaGlobalDeHiddenTests(SimpleTestCase):
    def test_utils_css_declara_hidden_con_important(self):
        css = _sin_comentarios((CSS / "utils.css").read_text(encoding="utf-8"))
        self.assertRegex(css, r"\[hidden\]\s*\{\s*display:\s*none\s*!important;\s*\}")

    def test_el_shell_del_backoffice_carga_utils_css_despues_de_tailwind(self):
        base = (TEMPLATES / "templates" / "includes" / "base.html").read_text(encoding="utf-8")
        self.assertIn("custom/css/utils.css", base)
        self.assertLess(base.index("custom/css/tailwind.css"), base.index("custom/css/utils.css"))

    def test_el_portal_no_comparte_utils_css(self):
        portal = (TEMPLATES / "portal" / "templates" / "portal" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("utils.css", portal)

    def test_ninguna_regla_de_pieza_muestra_un_elemento_con_hidden(self):
        """Ninguna hoja le da un `display` distinto de `none` a un selector `[hidden]`: la regla global no pisa nada."""

        for hoja in CSS.glob("*.css"):
            if hoja.name == "tailwind.css":
                continue
            for selector, cuerpo in re.findall(
                r"([^{}]*\[hidden\][^{}]*)\{([^{}]*)\}", _sin_comentarios(hoja.read_text(encoding="utf-8"))
            ):
                for valor in re.findall(r"(?<![-\w])display:\s*([\w-]+)", cuerpo):
                    self.assertEqual(valor, "none", f"{hoja.name}: {selector.strip()}")


HARNESS = r"""
const fs = require('fs');
const fuente = fs.readFileSync(process.argv[1], 'utf8');
const configurado = process.argv[2] === 'con-key';
const oyentes = {};
const boton = { hidden: true, disabled: false, addEventListener: (tipo, f) => { oyentes[tipo] = f; } };
const estado = { hidden: true, textContent: '' };
const config = { origen: { lat: -27.45, lng: -58.98 }, destinos: [{ clave: 'a', lat: -27.46, lng: -58.99 }] };
let importaciones = 0;
global.window = global;
global.document = {
  getElementById: (id) => (id === 'derivar-distancias-config' ? { textContent: JSON.stringify(config) } : null),
  querySelector: (selector) => ({ '[data-derivar-por-calle]': boton, '[data-derivar-por-calle-estado]': estado }[selector] || null),
  addEventListener: () => {},
};
window.NodoMapa = { configurado, importar: () => { importaciones += 1; return new Promise(() => {}); } };
eval(fuente);
const esperar = () => new Promise((r) => setTimeout(r, 20));
(async () => {
  const alCargar = { oculto: boton.hidden, importaciones, clic: !!oyentes.click };
  let trasClics = null;
  if (oyentes.click) {
    oyentes.click(); await esperar();
    oyentes.click(); oyentes.click(); await esperar();
    trasClics = { importaciones, deshabilitado: boton.disabled };
  }
  console.log(JSON.stringify({ alCargar, trasClics }));
})();
"""


class ScriptDeDistanciaPorCalleTests(SimpleTestCase):
    def _correr(self, caso):
        node = shutil.which("node")
        if not node:
            self.skipTest("node no está instalado")
        salida = subprocess.run([node, "-e", HARNESS, str(JS), caso], capture_output=True, text=True, check=True).stdout
        return json.loads(salida)

    def test_sin_key_no_engancha_nada_y_el_boton_sigue_oculto(self):
        resultado = self._correr("sin-key")
        self.assertEqual(resultado["alCargar"], {"oculto": True, "importaciones": 0, "clic": False})
        self.assertIsNone(resultado["trasClics"])

    def test_con_key_el_boton_aparece_pero_abrir_la_pagina_no_llama_a_google(self):
        resultado = self._correr("con-key")
        self.assertEqual(resultado["alCargar"], {"oculto": False, "importaciones": 0, "clic": True})

    def test_clics_repetidos_hacen_un_solo_calculo(self):
        resultado = self._correr("con-key")
        self.assertEqual(resultado["trasClics"], {"importaciones": 1, "deshabilitado": True})
