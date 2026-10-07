"""Toda URL que el front escribe a mano tiene que resolver contra el URLconf (RED-42).

El backoffice llama a sus endpoints JSON de dos maneras: con `{% url %}` —que
revienta en el render si la ruta no existe— y con la ruta escrita como literal
dentro del JavaScript, que no la revisa nadie. Al 04/10/2026 había cuatro
literales que resolvían 404 en producción y el `.catch()` los tapaba con un
`console.error`: la solapa de Red Familiar, las dos del historial de contactos y
el toggle de tema.

Este módulo recorre `templates/`, `*/templates/` y `static/**/*.js`, saca los
literales de `fetch(...)` y `$.ajax({url: ...})`, normaliza los segmentos que son
una interpolación entera (`${id}`, `{{ pk }}`) y afirma que `django.urls.resolve`
los encuentra. Lo conocido-roto vive en `ALLOWLIST`, que es un **ratchet**: cada
ficha que arregla su URL saca su entrada, y una entrada que ya no hace falta
también falla (si no, la lista crece y deja de medir nada).

`core/tests/urls_sin_conversaciones.py` no se usa acá a propósito: el barrido
tiene que ver el URLconf real, con `/conversaciones/` incluido.
"""

import re
import uuid
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

RAIZ = Path(settings.BASE_DIR)

# Carpetas que se barren. `static/` se toma entera (los `.js` propios y los de
# vendor; los de vendor no escriben rutas de este sistema, así que no molestan).
DIRECTORIOS_TEMPLATES = ["templates"] + [
    f"{app}/templates"
    for app in ("core", "users", "legajos", "programas", "portal", "conversaciones", "configuracion", "dashboard")
]
DIRECTORIOS_JS = ["static"]

# `fetch("/x/")`, `fetch('/x/')`, `fetch(`/x/`)` y `$.ajax({ url: "/x/" ... })`.
LITERAL_FETCH = re.compile(r"""fetch\s*\(\s*(?P<comilla>["'`])(?P<url>/[^"'`\n]*)(?P=comilla)""")
LITERAL_AJAX = re.compile(r"""url\s*:\s*(?P<comilla>["'`])(?P<url>/[^"'`\n]*)(?P=comilla)""")

# Un segmento que es **toda** una interpolación: `${id}`, `{{ pk }}`, `{{pk}}`.
SEGMENTO_INTERPOLADO = re.compile(r"^(?:\$\{[^}]*\}|\{\{[^}]*\}\})$")
# Cualquier interpolación suelta (para descartar segmentos mezclados).
HAY_INTERPOLACION = re.compile(r"\$\{|\{\{|\{%")

# Sondas para los segmentos variables: un entero y un UUID cubren los dos
# conversores que usa el repo (`<int:...>`, `<uuid:...>`); `<str:...>` y
# `<slug:...>` los matchea cualquiera de los dos.
SONDAS = ("1", str(uuid.uuid4()))

# Literales conocidos-rotos al 07/10/2026, cada uno con la ficha que lo saca.
# NO se agregan entradas nuevas: una URL nueva que no resuelve es un bug nuevo.
ALLOWLIST = {
    # LEG-06 (Ola 5): `historial_contactos.html` es código muerto; las vistas
    # existen (`legajos/views/historial_contactos.py`) pero sin ruta. La ficha
    # borra el template.
    "/legajos/1/contactos/api/",
    "/legajos/contactos/1/detalle/",
    # RED-75 (Ola 5, D-RED-07 = A): `static/custom/js/base.js::sendThemePreference`
    # postea la preferencia de tema a una vista que nunca existió.
    "/set_dark_mode/",
}


def _archivos():
    for carpeta in DIRECTORIOS_TEMPLATES:
        yield from sorted((RAIZ / carpeta).rglob("*.html"))
    for carpeta in DIRECTORIOS_JS:
        yield from sorted((RAIZ / carpeta).rglob("*.js"))


def _normalizar(url):
    """Ruta lista para `resolve`, o `None` si no se puede decidir sin ejecutar JS."""
    ruta = url.split("?", 1)[0].split("#", 1)[0]
    if not ruta.startswith("/"):
        return None
    partes = ruta.split("/")
    normalizadas = []
    for parte in partes:
        if SEGMENTO_INTERPOLADO.match(parte):
            normalizadas.append(None)  # segmento variable: se prueba con las sondas
        elif HAY_INTERPOLACION.search(parte):
            return None  # interpolación mezclada dentro del segmento: indecidible
        else:
            normalizadas.append(parte)
    return normalizadas


def _candidatas(partes):
    """Las rutas concretas a probar: cada segmento variable con cada sonda.

    Alcanza con que **una** resuelva: una ruta con `<uuid:pk>` solo acepta la
    sonda UUID, y una con `<int:pk>` solo la numérica.
    """
    if None not in partes:
        return ["/".join(partes)]
    return ["/".join(sonda if p is None else p for p in partes) for sonda in SONDAS]


def _resuelve(partes):
    for candidata in _candidatas(partes):
        try:
            resolve(candidata)
        except Resolver404:
            continue
        return True
    return False


def _literales_del_front():
    """`{ruta normalizada: [archivo:línea, ...]}` de todo literal del front."""
    encontrados = {}
    for archivo in _archivos():
        texto = archivo.read_text(encoding="utf-8", errors="replace")
        for patron in (LITERAL_FETCH, LITERAL_AJAX):
            for coincidencia in patron.finditer(texto):
                partes = _normalizar(coincidencia.group("url"))
                if partes is None:
                    continue
                linea = texto.count("\n", 0, coincidencia.start()) + 1
                clave = "/".join("1" if p is None else p for p in partes)
                encontrados.setdefault(clave, {"partes": partes, "donde": []})
                encontrados[clave]["donde"].append(f"{archivo.relative_to(RAIZ).as_posix()}:{linea}")
    return encontrados


class UrlsDelFrontTests(SimpleTestCase):
    """RED-42: ningún `fetch` literal del backoffice apunta a una ruta inexistente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.literales = _literales_del_front()

    def test_el_barrido_encuentra_literales(self):
        """Si el patrón deja de matchear, el test pasaría vacío sin medir nada."""
        self.assertGreater(len(self.literales), 5, "el barrido no encontró literales: el patrón se rompió")

    def test_todo_fetch_literal_resuelve(self):
        rotos = {
            clave: datos["donde"]
            for clave, datos in sorted(self.literales.items())
            if clave not in ALLOWLIST and not _resuelve(datos["partes"])
        }

        self.assertEqual(
            rotos,
            {},
            "URLs escritas a mano en el front que no resuelven contra el URLconf "
            f"(usá {{% url %}} o agregá la ruta): {rotos}",
        )

    def test_la_allowlist_no_tiene_entradas_de_mas(self):
        """Ratchet: una entrada que ya resuelve —o que ya no está en el front— sale."""
        sobrantes = []
        for clave in sorted(ALLOWLIST):
            datos = self.literales.get(clave)
            if datos is None:
                sobrantes.append(f"{clave} (ya no aparece en el front)")
            elif _resuelve(datos["partes"]):
                sobrantes.append(f"{clave} (ya resuelve)")

        self.assertEqual(sobrantes, [], f"entradas de la allowlist de RED-42 que hay que borrar: {sobrantes}")
