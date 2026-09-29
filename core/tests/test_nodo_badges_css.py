"""Los CSS propios no pueden tener comentarios que se cierren antes de tiempo.

Un ``*/`` dentro del texto de un comentario (p. ej. ``--color-pink-*/--color-brand-*``)
cierra el comentario y deja el resto como basura que el navegador antepone al
selector de la regla siguiente, que se descarta entera.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

CSS_DIR = Path(settings.BASE_DIR) / "static" / "custom" / "css"
COMENTARIO = re.compile(r"/\*.*?\*/", re.DOTALL)
REGLA = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _reglas(css):
    """Reglas planas (selector, cuerpo) tras quitar comentarios como el navegador."""
    sin_comentarios = COMENTARIO.sub("", css)
    return [(sel.strip(), cuerpo) for sel, cuerpo in REGLA.findall(sin_comentarios)]


class NodoBadgesCssTests(SimpleTestCase):
    def test_badge_gray_tiene_regla_propia_con_fondo(self):
        css = (CSS_DIR / "nodo-badges.css").read_text(encoding="utf-8")
        reglas = [cuerpo for sel, cuerpo in _reglas(css) if sel == ".badge-gray"]
        self.assertTrue(reglas, ".badge-gray no existe como regla (comentario roto).")
        self.assertIn("background", reglas[0])

    def test_ningun_selector_arrastra_texto_de_comentario(self):
        for ruta in sorted(CSS_DIR.glob("*.css")):
            css = ruta.read_text(encoding="utf-8")
            for sel, _ in _reglas(css):
                if sel.startswith("@"):
                    continue
                with self.subTest(archivo=ruta.name, selector=sel[:60]):
                    self.assertNotRegex(sel, r"\*/|/\*|\bde las primitivas\b")
