"""Barrido del URLconf: qué contesta cada ruta sin sesión y qué revienta con una.

Dos reglas que hasta ahora no estaban escritas en ningún lado ejecutable:

- **RED-02** — toda ruta del backoffice rebota al anónimo (redirección al login o
  `401/403/426`). Las excepciones viven en `ALLOWLIST_PUBLICA`, una lista literal
  con un comentario por entrada: agregar una ruta pública pasa a ser un cambio
  deliberado y revisable. La Ola 0 cerró once superficies abiertas una por una,
  cada una con su test puntual; ninguno mira el conjunto.
- **RED-30** — ninguna pantalla da 500 con un superusuario y la base mínima del
  test. Un `{% load %}` que falta, un template renombrado o un `select_related`
  sobre una relación que ya no existe dejan una pantalla rota sin que la suite
  diga nada.
- **RED-89** — ninguna ruta privada le contesta a un usuario de backoffice **sin
  ningún rol**: el recién creado, el del programa equivocado, el que quedó sin
  capacidades después de un cambio de rol. Es la pregunta que RED-02 no hace
  (su cliente es anónimo) y la que midió, el 04-oct-2026, que cualquier cuenta
  de backoffice borraba adjuntos de cualquier ciudadano.

El recorrido es el mismo para las tres: `get_resolver()` recursivo, cada patrón
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
    "/health/ready/": (
        "Readiness (OPS-04): la consultan el deploy y el monitoreo, sin sesión. Devuelve "
        "«ok» o el tipo de error de la base/cache, nunca credenciales ni datos."
    ),
    "/favicon.ico": "Redirección permanente al PNG estático.",
    "/api/becas/auth/token/": "Login de la app de campo: cambia usuario y clave por token (400 sin credenciales).",
    # Las tres del link público de inscripción (Cambio 41). Contestan 404 porque
    # el token de juguete del barrido no existe, que es lo correcto: el 404 no
    # distingue «token inválido» de «token vencido» y no filtra convocatorias.
    "/portal/inscripcion/00000000-0000-0000-0000-000000000000/": "Paso 1 del link público de inscripción.",
    "/portal/inscripcion/00000000-0000-0000-0000-000000000000/formulario/": "Paso 2 del link público.",
    "/portal/inscripcion/00000000-0000-0000-0000-000000000000/confirmacion/": "Confirmación del link público.",
}

#: Qué cuenta como «rebotar». **`404` y `405` no están**, y esa ausencia es el
#: test: el guard de una ruta privada tiene que correr *antes* del lookup del
#: objeto y antes de que Django mire el método, así que a un anónimo una ruta
#: privada nunca le contesta ni 404 ni 405.
#:
#: La primera versión los aceptaba y eso dejaba ciego al barrido: como las URLs
#: se concretan con valores de juguete sobre una base vacía, un 404 era la
#: respuesta esperable de medio URLconf y tapaba la pregunta. La revisión del PR
#: lo demostró sacándole `CapacidadRequeridaMixin` y `LoginRequiredMixin` a
#: `CiudadanoDetailView`: queda un `DetailView` pelado, el `pk` de juguete no
#: existe, la vista contesta 404 y **el test seguía verde**.
#:
#: Un 404 legítimo para el anónimo —una ruta pública cuyo objeto no existe, como
#: el link de inscripción con un token inventado— va a `ALLOWLIST_PUBLICA` con su
#: motivo, igual que un 200. Las rutas POST-only se repiten con POST en `_pedir`.
ESTADOS_QUE_REBOTAN = {401, 403, 426}


class SuperficieAnonimaTests(TestCase):
    """RED-02 · Ninguna ruta del backoffice contesta a un anónimo."""

    @classmethod
    def setUpTestData(cls):
        cls.rutas = rutas_concretas()
        cls.destinos_de_rebote = {reverse(settings.LOGIN_URL), reverse("portal:home")}

    def setUp(self):
        self.anonimo = Client(raise_request_exception=False)

    def _rebota(self, respuesta):
        """Rebotar es contestar `401/403/426` o mandar al login / al portal.

        La comparación es por *path exacto*: `reverse(settings.LOGIN_URL)` es `/`
        (el login vive en la raíz), así que un `in` daría por bueno cualquier
        redirección del sistema.
        """
        if respuesta.status_code in ESTADOS_QUE_REBOTAN:
            return True
        if respuesta.status_code in (301, 302):
            return urlparse(respuesta["Location"]).path in self.destinos_de_rebote
        return False

    def _pedir(self, url):
        """GET; si la vista solo acepta POST, se repite el pedido con POST.

        El cliente **no** verifica CSRF a propósito: con la verificación puesta,
        el 403 del token faltante llegaría antes que el guard y taparía la única
        pregunta que importa acá, que es si la vista mira quién pide.
        """
        respuesta = self.anonimo.get(url)
        if respuesta.status_code == 405:
            respuesta = self.anonimo.post(url, {})
        return respuesta

    def test_ninguna_ruta_responde_al_anonimo(self):
        abiertas = []
        for nombre, url in self.rutas:
            if url in ALLOWLIST_PUBLICA:
                continue
            respuesta = self._pedir(url)
            if self._rebota(respuesta):
                continue
            abiertas.append(f"{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(abiertas, [], "\n".join(["Rutas abiertas al anónimo:", *abiertas]))

    def test_el_barrido_recorre_todo_el_urlconf(self):
        """Si el recorrido se rompe, los otros tests pasan barriendo nada."""
        self.assertGreater(len(self.rutas), 250)
        urls = {url for _, url in self.rutas}
        for esperada in ("/usuarios/", "/becas/convocatorias/", "/legajos/ciudadanos/", "/api/users/me/"):
            self.assertIn(esperada, urls)

    def test_la_allowlist_publica_mide_lo_que_se_midio(self):
        """Ratchet: 17 rutas que no rebotan, medidas el 04-oct-2026.

        Falla si el número cambia **en cualquier sentido**. Hacia arriba porque
        publicar una ruta tiene que ser deliberado; hacia abajo porque una
        entrada que dejó de hacer falta hay que sacarla de la lista, no dejarla
        cubriendo de más. En los dos casos el arreglo es el mismo: revisar la
        lista y actualizar este número en el mismo commit.
        """
        self.assertEqual(len(ALLOWLIST_PUBLICA), 18)  # +1: /health/ready/ (OPS-04, Cambio 153)

    def test_la_allowlist_publica_no_tiene_entradas_muertas(self):
        """Una URL que ya no existe en el URLconf deja de justificar nada."""
        urls = {url for _, url in self.rutas}
        self.assertEqual(sorted(set(ALLOWLIST_PUBLICA) - urls), [])


# --------------------------------------------------------------------------- #
# RED-30 — ninguna pantalla revienta
# --------------------------------------------------------------------------- #

#: Rutas que dan `>= 500` por un bug de otra ola, con su ficha. Vacía: `/api/docs/`
#: y `/api/redoc/` estuvieron acá por RED-36 y salieron cuando se mergeó el PR
#: R-04 (Cambio 118), que puso `drf_spectacular` en `INSTALLED_APPS`.
EXCEPCIONES_HUMO = {}

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


# --------------------------------------------------------------------------- #
# RED-89 — qué contesta cada ruta a un usuario de backoffice SIN NINGÚN ROL
# --------------------------------------------------------------------------- #

#: Rutas que un autenticado **sin una sola capacidad** puede pedir, más allá de
#: las públicas. Mismo criterio que `ALLOWLIST_PUBLICA`: literal, con un motivo
#: por entrada, y con el ratchet de abajo para que sumar una sea deliberado.
#:
#: RED-02 contestó «¿qué ve un anónimo?»; nadie había preguntado «¿qué ve el
#: usuario recién creado, el del programa equivocado, el que quedó sin
#: capacidades después de un cambio de rol?». El barrido del 04-oct-2026 midió
#: **31 rutas** abiertas a ese usuario, 17 de ellas de Legajos: borraba adjuntos
#: ajenos (hard delete) y cerraba alertas de cualquiera. Esas 17 son las que
#: cerró este mismo PR (SEC-10, SEC-11, SEC-18); las de acá son las que quedan
#: por diseño.
EXTRAS_SIN_ROL = {
    # Índices de endpoints de DRF: listan nombres de rutas, ningún dato.
    "/api/core/": "api-root de DRF: índice de endpoints, sin datos de personas.",
    "/api/legajos/": "api-root de DRF: índice de endpoints, sin datos de personas.",
    "/api/becas/": "api-root de DRF: índice de endpoints, sin datos de personas.",
    # Catálogos institucionales y geográficos: los pueblan los formularios del
    # backoffice, no contienen datos de personas.
    "/api/core/dias/": "Catálogo de días de la semana.",
    "/api/core/localidades/": "Catálogo geográfico de localidades.",
    "/ajax/load-localidades/": "Catálogo geográfico encadenado de los formularios.",
    "/ajax/load-municipios/": "Catálogo geográfico encadenado de los formularios.",
    "/ajax/load-subsecretarias/": "Catálogo institucional encadenado de los formularios.",
    "/configuracion/programas/": "Catálogo institucional de programas (nombres y estado).",
    # `/inicio/` es el destino al que manda `_respuesta_sin_permiso`: si rebotara,
    # rebotaría en bucle. Se verificó que su HTML trae solo contadores agregados,
    # ni el nombre ni el DNI de ningún ciudadano (RED-89, 04-oct-2026).
    "/inicio/": "Destino del propio rebote; solo contadores agregados, verificado.",
    # Las cuatro de Conversaciones contestan 200 pero **vacío**: el guard está
    # adentro de la vista (`usuario_tiene_permiso_conversaciones`), que devuelve
    # `{"count": 0}` y `{"results": []}` a quien no lo tiene. No exponen nada, así
    # que no son un bug que arreglar: son una forma distinta de escribir el guard.
    "/api/conversaciones/alertas/count/": (
        "responde vacío, el guard está adentro de la vista (`usuario_tiene_permiso_conversaciones`)"
    ),
    "/api/conversaciones/alertas/preview/": (
        "responde vacío, el guard está adentro de la vista (`usuario_tiene_permiso_conversaciones`)"
    ),
    "/conversaciones/api/alertas/count/": (
        "responde vacío, el guard está adentro de la vista (`usuario_tiene_permiso_conversaciones`)"
    ),
    "/conversaciones/api/alertas/preview/": (
        "responde vacío, el guard está adentro de la vista (`usuario_tiene_permiso_conversaciones`)"
    ),
}

#: Las públicas también: si un anónimo puede pedir una ruta, un autenticado sin
#: rol también. Unir las dos listas evita que el día que se publique (o se cierre)
#: una ruta haya que acordarse de tocar dos lugares.
ALLOWLIST_SIN_ROL = {**ALLOWLIST_PUBLICA, **EXTRAS_SIN_ROL}


class SuperficieSinRolTests(TestCase):
    """RED-89 · Ninguna ruta privada contesta a un usuario de backoffice sin rol."""

    @classmethod
    def setUpTestData(cls):
        cls.rutas = rutas_concretas()
        # Sin grupos, sin `user_permissions`, sin `is_superuser`: exactamente el
        # usuario que crea el administrador antes de asignarle un rol.
        cls.sin_rol = User.objects.create_user("sin_rol", "sin_rol@example.test", "x")

    def setUp(self):
        self.navegador = Client(raise_request_exception=False)
        self.navegador.force_login(self.sin_rol)

    def _expone(self, respuesta):
        """¿La ruta le **contesta con cuerpo propio** a este usuario? (`2xx`).

        La pregunta de RED-02 era «¿rebota?» y ahí `404` no cuenta como rebote: a
        un anónimo el guard tiene que correr antes del lookup. Acá la pregunta es
        la inversa —«¿qué le llega al usuario sin rol?»— y la respuesta medible es
        el `2xx`: el `403`/`426` y el redirect de `_respuesta_sin_permiso` son
        rebotes, y el `404`/`405` no le entrega nada.

        **Lo que este barrido no ve, dicho explícito:** una vista que resuelve el
        objeto *antes* del guard (`dar_baja_beneficiario_view` de Becas es el
        molde) le contesta `404` al `pk` de juguete y `403` recién con un objeto
        real. Está guardada, pero en el orden equivocado; ordenarlo es trabajo de
        las fichas de esas vistas, no de este barrido, que mediría lo mismo antes
        y después. `SuperficieAnonimaTests` sí sostiene la regla estricta.
        """
        return 200 <= respuesta.status_code < 300

    def _pedir(self, url):
        """GET; si la vista solo acepta POST, se repite con POST (ídem RED-02)."""
        respuesta = self.navegador.get(url)
        if respuesta.status_code == 405:
            respuesta = self.navegador.post(url, {})
        return respuesta

    def test_la_sesion_del_barrido_es_un_usuario_sin_rol(self):
        """Sin esto, el barrido podría estar midiendo a un anónimo (RED-02 otra vez)."""
        self.assertEqual(self.sin_rol.groups.count(), 0)
        self.assertEqual(self.sin_rol.user_permissions.count(), 0)
        self.assertFalse(self.sin_rol.is_superuser)
        # Entra al backoffice: `/inicio/` contesta 200 y es a donde lo manda el
        # propio `_respuesta_sin_permiso`.
        self.assertEqual(self.navegador.get(reverse("core:inicio")).status_code, 200)

    def test_ninguna_ruta_privada_responde_a_un_usuario_sin_rol(self):
        abiertas = []
        for nombre, url in self.rutas:
            if url in ALLOWLIST_SIN_ROL:
                continue
            respuesta = self._pedir(url)
            if self._expone(respuesta):
                abiertas.append(f"{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(abiertas, [], "\n".join(["Rutas abiertas a un usuario sin rol:", *abiertas]))

    def test_ninguna_ruta_revienta_con_un_usuario_sin_rol(self):
        """`POST /api/legajos/alertas/x/cerrar/` daba 500: el `pk` no numérico
        llegaba crudo a `AlertasService.cerrar_alerta` (RED-89, SEC-18). El humo
        de RED-30 no lo veía porque corre con GET y con superusuario.
        """
        rotas = []
        for nombre, url in self.rutas:
            respuesta = self._pedir(url)
            if respuesta.status_code >= 500:
                rotas.append(f"{nombre} → {url} ({respuesta.status_code})")

        self.assertEqual(rotas, [], "\n".join(["Rutas que revientan con un usuario sin rol:", *rotas]))

    def test_la_allowlist_sin_rol_mide_lo_que_se_midio(self):
        """Ratchet en las dos direcciones, igual que el de `ALLOWLIST_PUBLICA`.

        14 entradas propias + las 18 públicas. El barrido del 04-oct-2026 midió
        31 rutas abiertas a este usuario: estas 14 y las 17 de Legajos, que no
        están acá porque este PR les puso capacidad (SEC-10, SEC-11, SEC-18). La
        32.ª es `/health/ready/`, que agregó el Cambio 153 (OPS-04).
        """
        self.assertEqual(len(EXTRAS_SIN_ROL), 14)
        self.assertEqual(len(ALLOWLIST_SIN_ROL), 32)

    def test_la_allowlist_sin_rol_no_tiene_entradas_muertas(self):
        urls = {url for _, url in self.rutas}
        self.assertEqual(sorted(set(ALLOWLIST_SIN_ROL) - urls), [])
