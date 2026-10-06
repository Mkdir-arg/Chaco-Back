"""`compile_templates.py --bloques`: un bloque que nadie declara deja de pasar (FE-05).

`{% block extra_js %}` en un hijo de `includes/main.html` no es un error de sintaxis —el
template compila y la página se ve bien— pero Django descarta el bloque y su contenido no
llega nunca al navegador. Así estuvo rota la cascada Secretaría → Subsecretaría del wizard
de programas: el `<script>` existía en el archivo y no existía en el HTML.
"""

import importlib.util
import tempfile
from pathlib import Path

from django.conf import settings
from django.template.utils import get_app_template_dirs
from django.test import SimpleTestCase

_RUTA = Path(settings.BASE_DIR, "scripts", "compile_templates.py")
_SPEC = importlib.util.spec_from_file_location("compile_templates", _RUTA)
compile_templates = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(compile_templates)


def _dirs_del_repo():
    repo = str(Path(settings.BASE_DIR).resolve()).lower()
    dirs = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    dirs += [Path(d) for d in get_app_template_dirs("templates")]
    return [
        d for d in dirs if str(d.resolve()).lower().startswith(repo) and "site-packages" not in d.resolve().as_posix()
    ]


class BloquesSinDestinoTests(SimpleTestCase):
    def test_el_repo_no_tiene_bloques_sin_destino_nuevos(self):
        huerfanos = [
            (nombre, bloque)
            for nombre, bloque, _padre in compile_templates.bloques_sin_destino(_dirs_del_repo())
            if (nombre, bloque) not in compile_templates.BLOQUES_SIN_DESTINO_CONOCIDOS
        ]

        self.assertEqual(huerfanos, [])

    def test_la_allowlist_no_tiene_entradas_muertas(self):
        """Cuando la ficha dueña cierra, su entrada sale: si no, la lista tapa regresiones."""
        vivos = {(nombre, bloque) for nombre, bloque, _ in compile_templates.bloques_sin_destino(_dirs_del_repo())}

        self.assertEqual(compile_templates.BLOQUES_SIN_DESTINO_CONOCIDOS - vivos, set())

    def test_el_wizard_de_programas_ya_no_esta_en_la_lista(self):
        """La regresión concreta que cierra FE-05."""
        sin_destino = compile_templates.bloques_sin_destino(_dirs_del_repo())

        self.assertNotIn(
            ("configuracion/programa_wizard_paso1.html", "extra_js"),
            [(nombre, bloque) for nombre, bloque, _ in sin_destino],
        )

    def test_detecta_un_bloque_que_el_padre_no_declara(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "shell.html").write_text("{% block cuerpo %}{% endblock %}", encoding="utf-8")
            (base / "hijo.html").write_text(
                '{% extends "shell.html" %}{% block cuerpo %}ok{% endblock %}{% block extra_js %}x{% endblock %}',
                encoding="utf-8",
            )

            self.assertEqual(
                compile_templates.bloques_sin_destino([base]),
                [("hijo.html", "extra_js", "shell.html")],
            )

    def test_un_bloque_anidado_dentro_de_uno_heredado_no_cuenta(self):
        """Se renderiza igual: el padre declara el de afuera."""
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "shell.html").write_text("{% block cuerpo %}{% endblock %}", encoding="utf-8")
            (base / "hijo.html").write_text(
                '{% extends "shell.html" %}{% block cuerpo %}{% block interno %}x{% endblock %}{% endblock %}',
                encoding="utf-8",
            )

            self.assertEqual(compile_templates.bloques_sin_destino([base]), [])

    def test_una_cadena_que_no_se_puede_resolver_no_concluye_nada(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / "hijo.html").write_text(
                '{% extends "no-existe.html" %}{% block extra_js %}x{% endblock %}', encoding="utf-8"
            )

            self.assertEqual(compile_templates.bloques_sin_destino([base]), [])
