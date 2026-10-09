from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from core.views.media import media_protegida


def websocket_upgrade_required(_request, *_args, **_kwargs):
    return HttpResponse("WebSocket endpoint requires an ASGI server.", status=426)


urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url=f"{settings.STATIC_URL}custom/chaco/favicon.png", permanent=True),
    ),
    # Único WebSocket del proyecto (`legajos/routing.py`). Esta ruta HTTP es el 426
    # que contesta cuando el runtime no es ASGI. `ws/conversaciones/…` y
    # `ws/alertas-conversaciones/` se fueron con el apagado de la app (G1-01 fase 2).
    path("ws/alertas/", websocket_upgrade_required),
    # G1c-10: acá estaba `admin/doc/` (`django.contrib.admindocs`), montado en
    # todos los entornos. Publicaba el índice de modelos, vistas, templates y
    # tags del proyecto —con sus docstrings— a cualquier `is_staff`; no lo
    # enlazaba ninguna pantalla y no lo usa nadie. Restringir `/admin/` por IP es
    # del ingress y va con el PM (punto 6 de SEC-26).
    path("admin/", admin.site.urls),
    # Specific paths first
    path("legajos/", include("legajos.urls")),
    path("configuracion/", include("configuracion.urls")),
    # G1-01 fase 2 (auditoría oct-2026): `conversaciones` está apagada. La app no
    # está en uso (decisión del PM, 29-sep-2026) y su chat público creaba el legajo
    # de cualquier DNI con el nombre que quisiera el cliente. Acá iba
    # `path("conversaciones/", include("conversaciones.urls"))` y, más abajo,
    # `api/conversaciones/`. Como con el portal (SEC-29), las vistas, los modelos y
    # los templates siguen en el repo sin ruta: lo que se apaga es la superficie.
    path("portal/", include("portal.urls")),
    path("becas/", include("programas.urls")),
    path("dispositivos/", include("programas.dispositivos_urls")),
    path("merenderos/", include("programas.merenderos_urls")),
    # Root paths last
    path("", include(("users.urls", "users"), namespace="users")),
    # SEC-26: `django.contrib.auth.urls` estuvo montado acá y publicaba en la raíz
    # un segundo juego de login, logout, recupero y **cambio de contraseña** que
    # ninguna pantalla enlazaba. Sin plantillas propias, el GET moría en
    # `TemplateDoesNotExist`, pero el POST a `/password_change/` no renderiza nada:
    # cambiaba la clave y redirigía, sin pedir la actual y sin pasar por ningún
    # límite de intentos. Los flujos de verdad —con sus plantillas, su throttle y
    # su gate— viven en `users.urls`.
    path("", include(("core.urls", "core"), namespace="core")),
    path("", include("dashboard.urls")),
    # `/health/` (liveness) y `/health/ready/` (readiness, OPS-04). Hasta el Cambio 153
    # convivía con `path("health/", include("health_check.urls"))` del paquete
    # `django-health-check`, que quedaba tapado por este include y nunca se alcanzaba:
    # dos apps compitiendo por la misma ruta, una de ellas tocando la base en lo que es
    # una sonda de liveness. Ese include se retiró; el paquete sigue en `INSTALLED_APPS`
    # porque tiene una migración aplicada y una tabla en los ambientes (OPS-13).
    path("", include(("healthcheck.urls", "healthcheck"), namespace="healthcheck")),
    # Flujos — editor visual HTML
    # API Routes
    path("api/legajos/", include("legajos.urls.api")),
    path("api/core/", include("core.api_urls")),
    path("api/users/", include("users.api_urls")),
    path("api/becas/", include("programas.api_urls")),
    # API Documentation
    # Documentación de la API detrás de login: el inventario completo de
    # endpoints, parámetros y modelos era reconocimiento gratuito para cualquiera
    # que llegara por el link público (seguridad, 26/08/2026).
    path("api/schema/", login_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/", login_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    # `template_name`: la plantilla del paquete trae Google Fonts escrito a mano
    # y `REDOC_DIST = "SIDECAR"` no la toca. La nuestra es la misma sin eso.
    path(
        "api/redoc/",
        login_required(SpectacularRedocView.as_view(url_name="schema", template_name="api/redoc.html")),
        name="redoc",
    ),
]

# Performance Profiling (Silk): solo en desarrollo/staging, nunca en producción.
if settings.DEBUG:
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

urlpatterns += staticfiles_urlpatterns()

# `/media/` SIEMPRE pasa por `media_protegida`: sesión + pertenencia por archivo
# (SEC-09 etapa 2). Antes la ruta dependía de `SERVE_MEDIA`, y arriba de ella
# estaba `static(MEDIA_URL, …)`, que con DEBUG=True ganaba por orden y servía
# `media/` **sin sesión** (R0b-07): un ambiente con las dos cosas prendidas dejaba
# los documentos del ciudadano abiertos. Las dos líneas se fueron; `media_protegida`
# decide con el mismo criterio en dev y en producción, y lo único que cambia por
# ambiente es si los bytes los manda Django o el servidor de adelante
# (`MEDIA_X_ACCEL`).
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", media_protegida, name="media_protegida"),
]

handler500 = "config.views.server_error"
