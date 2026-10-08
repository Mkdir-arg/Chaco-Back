"""SEC-01 (lo que faltaba) · Toda vista DRF del backoffice declara su permiso.

El Cambio 100 puso `IsAuthenticated` como `DEFAULT_PERMISSION_CLASSES` y el 109
creó `BackofficeAutenticado` para las vistas que declaran `permission_classes`
propias —que por eso **no heredan** el default—. Los Cambios 113, 114 y 115 lo
aplicaron a la lista que nombraba la ficha, y quedaron afuera las que nadie había
inventariado: las cuatro de Conversaciones (montadas bajo **dos** prefijos), las
ocho de performance, las tres pantallas de documentación de la API —que declaran
`AllowAny` por dentro del `login_required`— y las raíces de los `DefaultRouter`.

Ninguna era explotable: la sesión viaja por cookie y `PortalCiudadanoMiddleware`
frena al ciudadano del portal antes de la vista. Lo que cierra este test no es un
agujero sino el **molde**: una vista DRF nueva nace con el permiso puesto o este
test se pone rojo, que es lo que la lista escrita a mano no podía sostener.

La app de campo queda afuera a propósito: no es backoffice. Autentica por Token
(`programas/api/views.py`) y su gate es `CampoBecasPermission`.
"""

from django.test import SimpleTestCase
from django.urls import get_resolver
from rest_framework.views import APIView

from core.api_permissions import BackofficeAutenticado

#: Prefijos cuyas vistas **no** son del backoffice, con el motivo por entrada.
#: Mismo criterio que las allowlists de `test_superficie_publica`: literal, con
#: ratchet, para que sumar una sea deliberado.
FUERA_DEL_BACKOFFICE = {
    "api/becas/": "App de campo: Token + CampoBecasPermission, no es una sesión de backoffice.",
}


def _vistas_drf():
    """``(ruta, clase)`` de cada vista DRF del URLconf, sin repetir.

    `as_view()` deja la clase en `view.cls`, y `functools.wraps` la arrastra a
    través de `login_required`: por eso también se ven las que están envueltas.
    """

    def recorrer(resolver, prefijo=""):
        for patron in resolver.url_patterns:
            if hasattr(patron, "url_patterns"):
                yield from recorrer(patron, prefijo + str(patron.pattern))
            else:
                yield prefijo + str(patron.pattern), patron.callback

    vistas = {}
    for ruta, callback in recorrer(get_resolver()):
        cls = getattr(callback, "cls", None)
        if cls is None or not (isinstance(cls, type) and issubclass(cls, APIView)):
            continue
        # `@api_view` fabrica una `WrappedAPIView` por vista y le copia el
        # `__name__` de la función (el `__qualname__` queda genérico para todas).
        vistas.setdefault(f"{cls.__module__}.{cls.__name__}", (ruta, cls))
    return vistas


class PermisoDeLaApiDelBackofficeTests(SimpleTestCase):
    def test_todas_declaran_backoffice_autenticado(self):
        sin_permiso = []
        for nombre, (ruta, cls) in _vistas_drf().items():
            if any(ruta.startswith(prefijo) for prefijo in FUERA_DEL_BACKOFFICE):
                continue
            if BackofficeAutenticado not in list(getattr(cls, "permission_classes", [])):
                sin_permiso.append(f"{nombre} → /{ruta}")

        self.assertEqual(
            sorted(sin_permiso),
            [],
            "\n".join(["Vistas DRF sin BackofficeAutenticado:", *sorted(sin_permiso)]),
        )

    def test_el_barrido_ve_las_que_tiene_que_ver(self):
        """Sin esto, un `_vistas_drf()` que devuelva vacío daría verde."""
        nombres = _vistas_drf()

        self.assertGreaterEqual(len(nombres), 20)
        for esperada in (
            "conversaciones.api_views.alertas_conversaciones_count",
            "core.views.performance.performance_api",
            "drf_spectacular.views.SpectacularSwaggerView",
            "core.api_routers.RaizApiBackoffice",
        ):
            with self.subTest(vista=esperada):
                self.assertIn(esperada, nombres)

    def test_la_app_de_campo_sigue_siendo_la_unica_excepcion(self):
        self.assertEqual(list(FUERA_DEL_BACKOFFICE), ["api/becas/"])
