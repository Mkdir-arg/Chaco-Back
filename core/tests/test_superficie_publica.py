"""Barrido del URLconf: qué contesta cada ruta sin sesión y qué revienta con una.

Dos reglas que hasta ahora no estaban escritas en ningún lado ejecutable:

- **RED-02** — toda ruta del backoffice rebota al anónimo (redirección al login o
  `401/403/404/405/426`). Las excepciones viven en `ALLOWLIST_PUBLICA`, una lista
  literal con un comentario por entrada: agregar una ruta pública pasa a ser un
  cambio deliberado y revisable. La Ola 0 cerró once superficies abiertas una por
  una, cada una con su test puntual; ninguno mira el conjunto.
- **RED-30** — ninguna pantalla da 500 con un superusuario y la base mínima del
  test. Un `{% load %}` que falta, un template renombrado o un `select_related`
  sobre una relación que ya no existe dejan una pantalla rota sin que la suite
  diga nada.

El recorrido es el mismo para las dos: `get_resolver()` recursivo, cada patrón
concretado con valores de juguete y descartado si no vuelve a resolver. El número
de rutas depende de cómo se concreten los `re_path`, así que no se copia de
ningún informe: lo mide este archivo.
"""

import re
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import URLPattern, URLResolver, get_resolver, resolve, reverse
from django.urls.exceptions import Resolver404

# --------------------------------------------------------------------------- #
# Recorrido del URLconf
# --------------------------------------------------------------------------- #

# `admin` es el admin de Django (su propia autorización, y `admin/doc/` monta
# cientos de rutas de documentación); `silk` solo existe con DEBUG; los estáticos
# y `/media/` tienen sus propios tests (`core/tests/test_media_protegida.py`).
NAMESPACES_FUERA = {"admin", "admindocs", "silk"}
PREFIJOS_FUERA = ("admin/", "static/", "media/", "silk/", "__debug__/")

# Valor de juguete por converter de `path()`.
_VALORES_CONVERTER = {
    "int": "1",
    "str": "x",
    "slug": "x",
    "uuid": "00000000-0000-0000-0000-000000000000",
    "path": "x",
}

_CONVERTER = re.compile(r"<(?:([a-z_]+):)?[A-Za-z_]\w*>")
_GRUPO_REGEX = re.compile(r"\(\?P<[^>]+>([^()]*)\)")
_METACARACTERES = re.compile(r"[\\()\[\]?*+|^$]")


def _concretar_route(route):
    """`becas/convocatoria/<int:pk>/` → `becas/convocatoria/1/`."""
    faltantes = []

    def reemplazo(coincidencia):
        converter = coincidencia.group(1) or "str"
        if converter not in _VALORES_CONVERTER:
            faltantes.append(converter)
            return ""
        return _VALORES_CONVERTER[converter]

    concretado = _CONVERTER.sub(reemplazo, route)
    return None if faltantes else concretado


def _valor_para_grupo(interior):
    """Valor de juguete para el interior de un `(?P<nombre>...)` de `re_path`."""
    if "a-f" in interior or "A-F" in interior:
        return _VALORES_CONVERTER["uuid"]
    if re.fullmatch(r"\[?\\?d?0?-?9?\]?[+*]?|\d+|\[0-9\][+*]?|\\d[+*]?", interior):
        return "1"
    return "x"


def _concretar_regex(patron):
    """`^casos/(?P<pk>[0-9]+)/$` → `casos/1/`; `None` si queda regex sin resolver."""
    texto = _GRUPO_REGEX.sub(lambda c: _valor_para_grupo(c.group(1)), patron.lstrip("^").rstrip("$"))
    return None if _METACARACTERES.search(texto) else texto


def _concretar(patron):
    route = getattr(patron, "_route", None)
    if route is not None:
        return _concretar_route(route)
    return _concretar_regex(str(patron))


def _recorrer(patrones, prefijo, namespace, salida):
    for entrada in patrones:
        trozo = _concretar(entrada.pattern)
        if trozo is None:
            continue
        ruta = f"{prefijo}{trozo}"
        if isinstance(entrada, URLResolver):
            sub = entrada.namespace or namespace
            if sub in NAMESPACES_FUERA or ruta.startswith(PREFIJOS_FUERA):
                continue
            _recorrer(entrada.url_patterns, ruta, sub, salida)
        elif isinstance(entrada, URLPattern):
            if namespace in NAMESPACES_FUERA or ruta.startswith(PREFIJOS_FUERA):
                continue
            salida.append((f"{namespace}:{entrada.name}" if namespace else (entrada.name or "?"), f"/{ruta}"))


def rutas_concretas():
    """Toda ruta GET-eable del URLconf, concretada y verificada con `resolve()`."""
    crudas = []
    _recorrer(get_resolver().url_patterns, "", None, crudas)

    vistas = []
    for nombre, url in crudas:
        try:
            resolve(url)
        except Resolver404:
            continue
        vistas.append((nombre, url))
    # Dos patrones distintos pueden concretar a la misma URL (p. ej. el detalle y
    # su alias): se barre una sola vez.
    return sorted(set(vistas))


# --------------------------------------------------------------------------- #
# RED-02 — qué contesta cada ruta sin sesión
# --------------------------------------------------------------------------- #

#: Rutas que **no rebotan** a un anónimo por diseño, con el motivo de cada una.
#: La lista es literal a propósito: generarla desde el código («toda vista sin
#: `@requiere` está bien») sería escribir el bug como si fuera la regla. Sumar
#: una entrada es una decisión de producto, y mueve el ratchet de abajo.
ALLOWLIST_PUBLICA = {
    "/": "Login del backoffice (LOGIN_URL); con sesión, el inicio.",
    "/login/": "Alias de compatibilidad del login (users:login_compat).",
    "/recuperar-contrasena/": "Recupero de contraseña del backoffice (Cambio 37).",
    "/recuperar-contrasena/enviada/": "Confirmación del recupero: no revela si el correo existe.",
    "/establecer-contrasena/x/x/": "Alta de clave por token de un solo uso; el token inválido muestra el aviso.",
    "/password_reset/": "Recupero de `django.contrib.auth.urls`, montado en la raíz.",
    "/password_reset/done/": "Ídem, pantalla de confirmación.",
    "/reset/x/x/": "Ídem, confirmación por token (el token inválido muestra el aviso).",
    "/reset/done/": "Ídem, pantalla final.",
    "/portal/": "Portal ciudadano: a dónde manda el middleware a un ciudadano (Cambio 102).",
    "/portal/csrf/": "Semilla de CSRF del formulario público de inscripción (Cambio 52).",
    "/health/": "Sonda de salud del contenedor; la consulta el orquestador, sin sesión.",
    "/favicon.ico": "Redirección permanente al PNG estático.",
}

ESTADOS_QUE_REBOTAN = {401, 403, 404, 405, 426}


class SuperficieAnonimaTests(TestCase):
    """RED-02 · Ninguna ruta del backoffice contesta a un anónimo."""

    @classmethod
    def setUpTestData(cls):
        cls.rutas = rutas_concretas()
        cls.destinos_de_rebote = {reverse(settings.LOGIN_URL), reverse("portal:home")}

    def setUp(self):
        self.anonimo = Client(raise_request_exception=False)

    def _rebota(self, respuesta):
        """Rebotar es contestar `401/403/404/405/426` o mandar al login / al portal.

        La comparación es por *path exacto*: `reverse(settings.LOGIN_URL)` es `/`
        (el login vive en la raíz), así que un `in` daría por bueno cualquier
        redirección del sistema.
        """
        if respuesta.status_code in ESTADOS_QUE_REBOTAN:
            return True
        if respuesta.status_code in (301, 302):
            return urlparse(respuesta["Location"]).path in self.destinos_de_rebote
        return False

    def test_ninguna_ruta_responde_al_anonimo(self):
        abiertas = []
        for nombre, url in self.rutas:
            respuesta = self.anonimo.get(url)
            if self._rebota(respuesta) or url in ALLOWLIST_PUBLICA:
                continue
            abiertas.append(f"{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(abiertas, [], "\n".join(["Rutas abiertas al anónimo:", *abiertas]))

    def test_el_barrido_recorre_todo_el_urlconf(self):
        """Si el recorrido se rompe, los otros tests pasan barriendo nada."""
        self.assertGreater(len(self.rutas), 250)
        urls = {url for _, url in self.rutas}
        for esperada in ("/usuarios/", "/becas/convocatorias/", "/legajos/ciudadanos/", "/api/users/me/"):
            self.assertIn(esperada, urls)

    def test_la_allowlist_publica_no_crecio(self):
        """Ratchet: 13 rutas públicas medidas el 04-oct-2026. Solo puede bajar."""
        self.assertEqual(len(ALLOWLIST_PUBLICA), 13)

    def test_la_allowlist_publica_no_tiene_entradas_muertas(self):
        """Una URL que ya no existe en el URLconf deja de justificar nada."""
        urls = {url for _, url in self.rutas}
        self.assertEqual(sorted(set(ALLOWLIST_PUBLICA) - urls), [])


# --------------------------------------------------------------------------- #
# RED-30 — ninguna pantalla revienta
# --------------------------------------------------------------------------- #

#: Rutas que hoy dan `>= 500` con sesión y que **no** se arreglan en este PR.
#: Cada una con su ficha: cuando la ficha se cierre, la entrada se va y el test
#: pasa a cubrir la ruta.
EXCEPCIONES_HUMO = {
    "/api/docs/": "RED-36 · `drf_spectacular` no está en INSTALLED_APPS: TemplateDoesNotExist.",
    "/api/redoc/": "RED-36 · ídem.",
}

#: Proxies al catálogo de SIIS. Salen a la red del organismo, que en el CI no
#: existe, y ahí **contestan 503 a propósito** (`SiisCatalogError` →
#: `JsonResponse({"error": …}, status=503)`, `programas/views/revision.py:852`).
#: Es degradación declarada, no una pantalla rota: queda fuera del humo.
PROXIES_EXTERNOS = {
    "/becas/revision/siis/localidades/": "becas:siis_localidades",
    "/becas/revision/siis/funciones/": "becas:siis_funciones",
}


class NingunaPantallaDa500Tests(TestCase):
    """RED-30 · Humo: con un superusuario, ninguna pantalla GET revienta."""

    @classmethod
    def setUpTestData(cls):
        cls.rutas = rutas_concretas()
        cls.superusuario = User.objects.create_superuser("humo_superusuario", "humo@example.test", "x")

    def setUp(self):
        self.navegador = Client(raise_request_exception=False)
        self.navegador.force_login(self.superusuario)

    def test_la_sesion_del_humo_entra_al_backoffice(self):
        """Sin esto, un middleware que redirija todo dejaría el humo en la nada."""
        self.assertEqual(self.navegador.get("/usuarios/").status_code, 200)

    def test_ninguna_pantalla_da_500(self):
        rotas = []
        for nombre, url in self.rutas:
            if url in EXCEPCIONES_HUMO or url in PROXIES_EXTERNOS:
                continue
            respuesta = self.navegador.get(url)
            if respuesta.status_code >= 500:
                rotas.append(f"{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(rotas, [], "\n".join(["Pantallas que revientan:", *rotas]))

    def test_las_excepciones_del_humo_siguen_siendo_necesarias(self):
        """Cuando la ficha de una excepción se cierre, este test lo avisa."""
        sanas = []
        for url in EXCEPCIONES_HUMO:
            if self.navegador.get(url).status_code < 500:
                sanas.append(url)

        self.assertEqual(sanas, [], f"Ya no dan 500: {sanas}. Sacarlas de EXCEPCIONES_HUMO.")
