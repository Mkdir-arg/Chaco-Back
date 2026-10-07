"""La preferencia de tema vive en el navegador, no en el perfil (RED-75).

`static/custom/js/base.js::sendThemePreference` posteaba el modo oscuro a
`/set_dark_mode/`, una ruta que **nunca existió** en el URLconf: cada cambio de
tema era un 404 que el `.fail()` tapaba con un `console.warn`. Del otro lado,
`Profile.dark_mode` nacía en `True` y no lo escribía nadie, así que cualquier
trabajo futuro que lo leyera iba a leer siempre `True`.

**D-RED-07 = A (default del README §2.4 de la auditoría, aplicado):** la
preferencia se persiste **solo** en el navegador (`localStorage`), que es lo que
el shell ya hacía de verdad. Se fue el POST y se fue el campo del serializer; la
columna `users_profile.dark_mode` queda en la base hasta que una ficha de
contract la retire (expand/contract: borrarla acá rompería la release vieja).

Estos tests son el candado: si alguien vuelve a postear la preferencia, el
módulo se pone rojo antes de que la URL vuelva a la `ALLOWLIST` de
`core/tests/test_urls_del_front.py`.
"""

import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from users.serializers import ProfileSerializer

RAIZ = Path(settings.BASE_DIR)
SHELL_JS = RAIZ / "static" / "custom" / "js" / "base.js"

# Dónde podría reaparecer el POST: el JS del shell, los templates del backoffice
# y el resto del JS propio.
FUENTES_DEL_FRONT = [RAIZ / "templates", RAIZ / "static" / "custom" / "js"]

# Comentarios de JS, de HTML y de Django: ahí **sí** se nombra lo que se borró,
# que es justamente la documentación de por qué no está. Lo que no puede volver
# es el código.
COMENTARIOS = re.compile(r"/\*.*?\*/|//[^\n]*|<!--.*?-->|\{#.*?#\}|\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.S)


def _archivos_del_front():
    for carpeta in FUENTES_DEL_FRONT:
        for patron in ("*.html", "*.js"):
            yield from sorted(carpeta.rglob(patron))


class TemaTests(SimpleTestCase):
    def test_el_shell_no_postea_la_preferencia_de_tema(self):
        """Ni la función ni la ruta aparecen en el código de ningún archivo del front."""
        hallazgos = []
        for archivo in _archivos_del_front():
            texto = archivo.read_text(encoding="utf-8", errors="replace")
            # Se borra el comentario pero se conservan sus saltos de línea, para que
            # el número de línea del mensaje siga siendo el del archivo real.
            codigo = COMENTARIOS.sub(lambda m: "\n" * m.group(0).count("\n"), texto)
            for marca in ("sendThemePreference", "set_dark_mode"):
                if marca in codigo:
                    linea = codigo[: codigo.index(marca)].count("\n") + 1
                    hallazgos.append(f"{archivo.relative_to(RAIZ).as_posix()}:{linea} ({marca})")

        self.assertEqual(
            hallazgos,
            [],
            f"la preferencia de tema volvió a postearse a una ruta inexistente (RED-75, D-RED-07 = A): {hallazgos}",
        )

    def test_el_barrido_mira_el_codigo_y_no_solo_los_comentarios(self):
        """Si `COMENTARIOS` se comiera de más, el test de arriba pasaría vacío."""
        muestra = 'a = 1;\n// sendThemePreference\nurl: "/set_dark_mode/";\n'

        codigo = COMENTARIOS.sub(lambda m: "\n" * m.group(0).count("\n"), muestra)

        self.assertNotIn("sendThemePreference", codigo)
        self.assertIn("/set_dark_mode/", codigo)

    def test_la_ruta_que_se_posteaba_sigue_sin_existir(self):
        """Por si alguien «arregla» el 404 creando la vista en vez de sacar el POST."""
        with self.assertRaises(Resolver404):
            resolve("/set_dark_mode/")

    def test_el_perfil_de_la_api_no_expone_la_preferencia_de_tema(self):
        """`dark_mode` salió de `ProfileSerializer`: nadie lo lee ni lo escribe."""
        self.assertNotIn("dark_mode", ProfileSerializer().fields)

    def test_el_shell_sigue_recordando_el_tema_en_el_navegador(self):
        """La conducta que el usuario ve no cambia: `localStorage` la sostiene."""
        shell = SHELL_JS.read_text(encoding="utf-8")

        self.assertIn("localStorage.setItem(THEME_STORAGE_KEY", shell)
        self.assertIn("localStorage.getItem(THEME_STORAGE_KEY", shell)
