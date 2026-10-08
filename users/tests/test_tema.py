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

**Ola 7, FE-14:** `base.js` era además un **huérfano** —no lo cargaba ningún
template—, así que el 404 por cambio de tema que describe RED-75 nunca llegó a
pasar en producción. El archivo se borró; el barrido de abajo sigue mirando todo
el front, que es donde el POST podría reaparecer.
"""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from core.tests.js_harness import sin_comentarios
from users.serializers import ProfileSerializer

RAIZ = Path(settings.BASE_DIR)
SHELL_JS = RAIZ / "static" / "custom" / "js" / "base.js"

# Dónde podría reaparecer el POST: el JS del shell, los templates del backoffice
# y el resto del JS propio.
FUENTES_DEL_FRONT = [RAIZ / "templates", RAIZ / "static" / "custom" / "js"]

# Los comentarios se saltean (`sin_comentarios`, el helper compartido con el barrido
# de RED-42): ahí **sí** se nombra lo que se borró, que es justamente la documentación
# de por qué no está. Lo que no puede volver es el código.


def _archivos_del_front():
    for carpeta in FUENTES_DEL_FRONT:
        for patron in ("*.html", "*.js"):
            yield from sorted(carpeta.rglob(patron))


class TemaTests(SimpleTestCase):
    def test_el_shell_no_postea_la_preferencia_de_tema(self):
        """Ni la función ni la ruta aparecen en el código de ningún archivo del front."""
        hallazgos = []
        for archivo in _archivos_del_front():
            codigo = sin_comentarios(archivo.read_text(encoding="utf-8", errors="replace"))
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
        """Si `sin_comentarios` se comiera de más, el test de arriba pasaría vacío."""
        muestra = 'a = 1;\n// sendThemePreference\nurl: "/set_dark_mode/";\n'

        codigo = sin_comentarios(muestra)

        self.assertNotIn("sendThemePreference", codigo)
        self.assertIn("/set_dark_mode/", codigo)

    def test_la_ruta_que_se_posteaba_sigue_sin_existir(self):
        """Por si alguien «arregla» el 404 creando la vista en vez de sacar el POST."""
        with self.assertRaises(Resolver404):
            resolve("/set_dark_mode/")

    def test_el_perfil_de_la_api_no_expone_la_preferencia_de_tema(self):
        """`dark_mode` salió de `ProfileSerializer`: nadie lo lee ni lo escribe."""
        self.assertNotIn("dark_mode", ProfileSerializer().fields)

    def test_el_archivo_que_posteaba_el_tema_ya_no_existe(self):
        """FE-14 (Ola 7): `base.js` era huérfano —ningún template lo cargaba—.

        Hasta acá este módulo afirmaba que `base.js` seguía guardando el tema en
        `localStorage`. Era cierto como texto y **falso como conducta**: el archivo
        no se servía en ninguna pantalla, así que ni el POST que RED-75 sacó ni el
        `localStorage` que lo reemplazó llegaban nunca al navegador. Lo que sostiene
        la red ahora son los tres tests de arriba, que barren **todo** el front: si
        el POST vuelve —en este archivo o en cualquier otro—, se ponen rojos.
        """
        self.assertFalse(SHELL_JS.exists(), f"{SHELL_JS.name} volvió al repo: revisar FE-14 y RED-75")
