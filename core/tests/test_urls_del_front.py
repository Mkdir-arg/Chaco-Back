"""Toda URL que el front escribe a mano tiene que resolver contra el URLconf (RED-42).

El backoffice llama a sus endpoints JSON de dos maneras: con `{% url %}` —que
revienta en el render si la ruta no existe— y con la ruta escrita como literal
dentro del JavaScript, que no la revisa nadie. Al 04/10/2026 había cuatro
literales que resolvían 404 en producción y el `.catch()` los tapaba con un
`console.error`: la solapa de Red Familiar, las dos del historial de contactos y
el toggle de tema.

Este módulo recorre `templates/`, `*/templates/` y `static/**/*.js`, saca los
literales de `fetch(...)`, `$.ajax({url: ...})` y las **rutas asignadas a una
variable** (`const url = "/legajos/…"`), normaliza los segmentos que son una
interpolación entera (`${id}`, `{{ pk }}`) y afirma que `django.urls.resolve`
los encuentra. Lo conocido-roto vive en `ALLOWLIST`, que es un **ratchet**: cada
ficha que arregla su URL saca su entrada, y una entrada que ya no hace falta
también falla (si no, la lista crece y deja de medir nada).

La tercera forma —la asignación— se agregó en la ronda 2 del PR #611: las dos
rutas de borrado de adjuntos de `ciudadano_detail.html` se armaban en un `const
urlEliminar = …` y pasaban por abajo del barrido, que solo miraba el punto de
llamada. Para no inundarlo de falsos positivos (`/static/…`, `/media/…`, un
`href` de un sitio ajeno), una asignación solo cuenta si su **primer segmento**
es uno de los prefijos que el URLconf raíz reconoce (`_prefijos_de_la_app`), que
se calculan del URLconf y no de una lista escrita a mano.

`core/tests/urls_sin_conversaciones.py` no se usa acá a propósito: el barrido
tiene que ver el URLconf real, con `/conversaciones/` incluido.
"""

import itertools
import re
import uuid
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import Resolver404, resolve

from core.tests.js_harness import sin_comentarios

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
# `const url = "/x/"`, `x.href = '/x/'`, `? \`/x/\` :` … La ruta se arma lejos del
# `fetch`, así que el punto de llamada no la delata. Se filtra por prefijo real del
# URLconf (ver `_prefijos_de_la_app`): sin eso entran `/static/…` y cualquier `href`.
LITERAL_ASIGNADO = re.compile(r"""[=?:]\s*(?P<comilla>["'`])(?P<url>/[^"'`\n]*)(?P=comilla)""")

# Un segmento que es **toda** una interpolación: `${id}`, `{{ pk }}`, `{{pk}}`.
SEGMENTO_INTERPOLADO = re.compile(r"^(?:\$\{[^}]*\}|\{\{[^}]*\}\})$")
# Cualquier interpolación suelta (para descartar segmentos mezclados).
HAY_INTERPOLACION = re.compile(r"\$\{|\{\{|\{%")

# Sondas para los segmentos variables: un entero y un UUID cubren los dos
# conversores que usa el repo (`<int:...>`, `<uuid:...>`); `<str:...>` y
# `<slug:...>` los matchea cualquiera de los dos.
SONDAS = ("1", str(uuid.uuid4()))

# Tope de segmentos variables por URL para probar **todas** las combinaciones de
# sonda (2^N). Hoy el máximo real es 1; con 4 son 16 `resolve`, que no se nota.
# Por encima del tope se prueba una sonda por URL, que es lo que se hacía antes.
TOPE_COMBINACIONES = 4

# Literales conocidos-rotos al 07/10/2026, cada uno con la ficha que lo saca.
# NO se agregan entradas nuevas **por código nuevo**: una URL que no resuelve y la
# escribió este PR es un bug de este PR. Lo que sí entra —y entró en la ronda 2 del
# #611— es deuda vieja que el barrido recién empieza a ver porque se ensanchó.
ALLOWLIST = {
    # LEG-06 (Ola 5): `historial_contactos.html` es código muerto; las vistas
    # existen (`legajos/views/historial_contactos.py`) pero sin ruta. La ficha
    # borra el template. Las dos últimas las destapó el patrón de asignación de la
    # ronda 2 (`const url = modoEdicion ? … : …`, líneas 598-599).
    "/legajos/1/contactos/api/",
    "/legajos/contactos/1/detalle/",
    "/legajos/1/contactos/crear/",
    "/legajos/contactos/1/editar/",
    # HALLAZGO NUEVO de la ronda 2 del #611, **sin ficha todavía**:
    # `legajos/templates/legajos/programas/programa_detail.html:654` le pone al form
    # de «Dar de baja» un `action` que no existe en el URLconf. La vista sí existe
    # (`legajos/views/programas.py::dar_de_baja_inscripcion`, con `@login_required` y
    # `@require_http_methods(["POST"])`), pero **nadie la rutea**: el botón de una
    # pantalla viva (`/legajos/programas/<pk>/`) postea a un 404 desde siempre.
    # NO se arregla acá: rutear la vista haría funcionar por primera vez una baja
    # destructiva que nunca corrió en producción, y eso es decisión del PM, no un
    # arreglo al paso. Ver la Resolución de RED-42 y el cuerpo del PR.
    "/legajos/acompanamiento/1/dar-de-baja/",
    # RED-75 salió de acá el 07/10/2026 (Cambio 164): `sendThemePreference` se
    # borró de `base.js` con el default D-RED-07 = A, así que `/set_dark_mode/`
    # ya no aparece en el front. El candado lo tiene `users/tests/test_tema.py`.
}


def _archivos():
    for carpeta in DIRECTORIOS_TEMPLATES:
        yield from sorted((RAIZ / carpeta).rglob("*.html"))
    for carpeta in DIRECTORIOS_JS:
        yield from sorted((RAIZ / carpeta).rglob("*.js"))


def _prefijos_de_la_app():
    """Los primeros segmentos fijos que el URLconf raíz reconoce.

    `{"legajos", "becas", "dispositivos", "api", "system-metrics-api", …}`. Sale del
    URLconf y no de una lista escrita a mano, así que una app nueva entra sola. Se
    baja un nivel cuando el `include` cuelga de la raíz (`path("", include(...))`,
    que es como entran las rutas de `core`), y se descartan los segmentos que son un
    conversor (`<int:pk>`): ahí cualquier cosa matchea y el filtro dejaría de filtrar.
    """
    from django.urls import URLResolver, get_resolver

    prefijos = set()

    def recorrer(resolver, prefijo):
        for patron in resolver.url_patterns:
            ruta = prefijo + str(patron.pattern)
            primero = ruta.lstrip("/").split("/", 1)[0]
            if isinstance(patron, URLResolver) and not primero:
                recorrer(patron, ruta)
            elif primero and "<" not in primero:
                prefijos.add(primero)

    recorrer(get_resolver(), "")
    return prefijos


PREFIJOS_DE_LA_APP = None  # se calcula una vez, con Django ya levantado


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
    """Las rutas concretas a probar: **una sonda por segmento**, todas las combinaciones.

    Alcanza con que una resuelva: una ruta con `<uuid:pk>` solo acepta la sonda
    UUID y una con `<int:pk>` solo la numérica. Usar la **misma** sonda para
    todos los segmentos daba un falso roto en cuanto una URL mezclara los dos
    conversores (`/legajos/<uuid:legajo_id>/contactos/<int:pk>/`): ninguna de las
    dos corridas uniformes resuelve, aunque la ruta exista.
    """
    variables = partes.count(None)
    if not variables:
        return ["/".join(partes)]
    if variables > TOPE_COMBINACIONES:
        # Degradación segura: sin combinatoria, una sonda para toda la URL. Un
        # literal así no existe hoy; si aparece, lo peor que pasa es un falso
        # roto que se resuelve poniéndolo en la allowlist o subiendo el tope.
        combinaciones = [(sonda,) * variables for sonda in SONDAS]
    else:
        combinaciones = itertools.product(SONDAS, repeat=variables)

    candidatas = []
    for sondas in combinaciones:
        restantes = iter(sondas)
        candidatas.append("/".join(next(restantes) if p is None else p for p in partes))
    return candidatas


def _resuelve(partes):
    for candidata in _candidatas(partes):
        try:
            resolve(candidata)
        except Resolver404:
            continue
        return True
    return False


def _es_ruta_de_la_app(partes):
    """¿El primer segmento fijo es un prefijo que el URLconf raíz reconoce?

    Filtro **solo** para las asignaciones, que son muchas y la mayoría no son rutas
    del sistema. En `fetch(...)` y `url:` no se aplica: ahí cualquier cosa que
    empiece con `/` es una llamada a este backend y tiene que resolver.
    """
    global PREFIJOS_DE_LA_APP
    if PREFIJOS_DE_LA_APP is None:
        PREFIJOS_DE_LA_APP = _prefijos_de_la_app()
    primero = next((p for p in partes[1:] if p), None)
    return primero in PREFIJOS_DE_LA_APP


def _literales_del_front():
    """`{ruta normalizada: [archivo:línea, ...]}` de todo literal del front."""
    encontrados = {}
    for archivo in _archivos():
        # Sin comentarios: las fichas que retiran una ruta la **nombran** en el
        # comentario que explica por qué ya no está (`// FE-09: /legajos/<id>/ no
        # resuelve…`), y leerlos daba la ruta por viva.
        texto = sin_comentarios(archivo.read_text(encoding="utf-8", errors="replace"))
        for patron in (LITERAL_FETCH, LITERAL_AJAX, LITERAL_ASIGNADO):
            for coincidencia in patron.finditer(texto):
                partes = _normalizar(coincidencia.group("url"))
                if partes is None:
                    continue
                if patron is LITERAL_ASIGNADO and not _es_ruta_de_la_app(partes):
                    continue
                linea = texto.count("\n", 0, coincidencia.start()) + 1
                clave = "/".join("1" if p is None else p for p in partes)
                encontrados.setdefault(clave, {"partes": partes, "donde": []})
                donde = f"{archivo.relative_to(RAIZ).as_posix()}:{linea}"
                if donde not in encontrados[clave]["donde"]:
                    encontrados[clave]["donde"].append(donde)
    return encontrados


class UrlsDelFrontTests(SimpleTestCase):
    """RED-42: ningún `fetch` literal del backoffice apunta a una ruta inexistente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.literales = _literales_del_front()

    def test_los_patrones_siguen_sacando_la_ruta(self):
        """Si el patrón deja de matchear, el test pasaría vacío sin medir nada.

        El contador de literales **vivos** no sirve de guardia: la Ola 5 convirtió
        los once que quedaban a `{% url %}` o a `data-url` (RED-42), y el día que
        LEG-06 borre `historial_contactos.html` el barrido va a dar cero
        legítimamente. Lo que tiene que seguir funcionando es el extractor, así
        que se lo ejercita contra una muestra escrita acá.
        """
        muestra = (
            'fetch("/uno/");\n'
            "fetch('/dos/${id}/');\n"
            "fetch(`/tres/`);\n"
            '$.ajax({url: "/cuatro/", type: "POST"});\n'
            'fetch("https://ajeno.example/x/");\n'  # no empieza con `/`: se descarta
            "fetch(`/cinco/pre${id}post/`);\n"  # interpolación mezclada: indecidible
        )

        encontrados = sorted(
            "/".join("1" if parte is None else parte for parte in _normalizar(m.group("url")) or [])
            for patron in (LITERAL_FETCH, LITERAL_AJAX)
            for m in patron.finditer(muestra)
            if _normalizar(m.group("url"))
        )

        self.assertEqual(encontrados, ["/cuatro/", "/dos/1/", "/tres/", "/uno/"])

    def test_el_barrido_recorre_el_front_de_verdad(self):
        """Y que los archivos estén donde el módulo los busca."""
        archivos = list(_archivos())

        self.assertGreater(len(archivos), 100, "el barrido no encontró archivos: se movió alguna carpeta")
        self.assertTrue(any(a.name == "base.html" for a in archivos))

    def _asignadas(self, muestra):
        """Las rutas que el patrón de asignación saca de `muestra`, ya filtradas."""
        encontradas = []
        for m in LITERAL_ASIGNADO.finditer(sin_comentarios(muestra)):
            partes = _normalizar(m.group("url"))
            if partes is None or not _es_ruta_de_la_app(partes):
                continue
            encontradas.append("/".join("1" if p is None else p for p in partes))
        return sorted(set(encontradas))

    def test_el_patron_ve_una_ruta_asignada_a_una_variable(self):
        """La forma que se le escapaba al barrido hasta la ronda 2 del #611."""
        muestra = (
            "const urlEliminar = '/legajos/ciudadanos/${id}/archivos/${a}/eliminar/';\n"
            "form.action = `/legajos/acompanamiento/${id}/dar-de-baja/`;\n"
            'const otra = archivo.tipo === "x" ? "/becas/convocatorias/" : "/dispositivos/";\n'
        )

        self.assertEqual(
            self._asignadas(muestra),
            [
                "/becas/convocatorias/",
                "/dispositivos/",
                "/legajos/acompanamiento/1/dar-de-baja/",
                "/legajos/ciudadanos/1/archivos/1/eliminar/",
            ],
        )

    def test_el_patron_de_asignacion_no_se_lleva_puesto_lo_que_no_es_una_ruta(self):
        """Sin el filtro por prefijo del URLconf el barrido medía cualquier cosa.

        Y sin sacar los comentarios, la ficha que **documenta** una ruta retirada la
        volvía a dar por viva: así entraban `/legajos/<id>/` (FE-09, un `//` en
        `ciudadano_detail.html`) y `/legajos/<uuid>/` (un `{% comment %}` en
        `alertas_dashboard.html`).
        """
        muestra = (
            "img.src = '/static/custom/img/logo.png';\n"
            "const doc = '/media/padrones/x.xlsx';\n"
            "a.href = 'https://ajeno.example/legajos/1/';\n"
            "const sep = '/';\n"
            "// FE-09: `/legajos/<id>/` no resuelve, por eso es texto y no un link.\n"
            "{# `/legajos/<uuid>/` tampoco #}\n"
        )

        self.assertEqual(self._asignadas(muestra), [])

    def test_los_prefijos_salen_del_urlconf_y_no_de_una_lista(self):
        prefijos = _prefijos_de_la_app()

        self.assertLessEqual({"legajos", "becas", "dispositivos", "merenderos", "api"}, prefijos)
        # Las de la raíz (`path("", include("core.urls"))`) también, o el filtro
        # dejaría ciego todo lo que cuelga del root.
        self.assertIn("performance-api", prefijos)
        # Y ningún conversor: `<int:pk>` matchearía con cualquier primer segmento.
        self.assertEqual([p for p in prefijos if "<" in p], [])

    def test_una_url_que_mezcla_conversores_no_da_falso_roto(self):
        """`/legajos/<uuid:legajo_id>/archivos/<int:archivo_id>/eliminar/` existe.

        Con una sonda única para toda la URL ninguna de las dos corridas resolvía
        —la numérica falla en el UUID, la UUID falla en el entero— y la ruta,
        que es real, se reportaba como rota.
        """
        partes = _normalizar("/legajos/${legajoId}/archivos/${archivoId}/eliminar/")

        self.assertEqual(partes.count(None), 2)
        self.assertTrue(_resuelve(partes))
        # Y la contracara: con una sonda uniforme, esa misma URL daba falso roto.
        uniformes = ["/".join(sonda if p is None else p for p in partes) for sonda in SONDAS]
        for candidata in uniformes:
            with self.subTest(candidata=candidata), self.assertRaises(Resolver404):
                resolve(candidata)

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
