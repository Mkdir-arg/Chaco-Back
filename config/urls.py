from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView


def websocket_upgrade_required(_request, *_args, **_kwargs):
    return HttpResponse("WebSocket endpoint requires an ASGI server.", status=426)


urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(url=f"{settings.STATIC_URL}custom/chaco/favicon.png", permanent=True),
    ),
    path("ws/conversaciones/", websocket_upgrade_required),
    re_path(r"^ws/conversaciones/(?P<conversacion_id>\w+)/$", websocket_upgrade_required),
    path("ws/alertas/", websocket_upgrade_required),
    path("ws/alertas-conversaciones/", websocket_upgrade_required),
    path("admin/doc/", include("django.contrib.admindocs.urls")),
    path("admin/", admin.site.urls),
    # Specific paths first
    path("legajos/", include("legajos.urls")),
    path("configuracion/", include("configuracion.urls")),
    path("conversaciones/", include("conversaciones.urls")),
    path("portal/", include("portal.urls")),
    path("becas/", include("programas.urls")),
    path("dispositivos/", include("programas.dispositivos_urls")),
    path("merenderos/", include("programas.merenderos_urls")),
    # Root paths last
    path("", include(("users.urls", "users"), namespace="users")),
    path("", include("django.contrib.auth.urls")),
    path("", include(("core.urls", "core"), namespace="core")),
    path("", include("dashboard.urls")),
    path("", include(("healthcheck.urls", "healthcheck"), namespace="healthcheck")),
    # Flujos — editor visual HTML
    # API Routes
    path("api/legajos/", include("legajos.urls.api")),
    path("api/core/", include("core.api_urls")),
    path("api/users/", include("users.api_urls")),
    path("api/becas/", include("programas.api_urls")),
    path(
        "api/conversaciones/",
        include(("conversaciones.api_urls", "conversaciones_api"), namespace="conversaciones_api"),
    ),
    # API Documentation
    # Documentación de la API detrás de login: el inventario completo de
    # endpoints, parámetros y modelos era reconocimiento gratuito para cualquiera
    # que llegara por el link público (seguridad, 26/08/2026).
    path("api/schema/", login_required(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/", login_required(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    path("api/redoc/", login_required(SpectacularRedocView.as_view(url_name="schema")), name="redoc"),
    # Health Check
    path("health/", include("health_check.urls")),
]

# Performance Profiling (Silk): solo en desarrollo/staging, nunca en producción.
if settings.DEBUG:
    urlpatterns += [path("silk/", include("silk.urls", namespace="silk"))]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Las dos líneas de arriba solo actúan con DEBUG. En un ambiente servido sin nginx
# adelante (Kubernetes), SERVE_MEDIA=True hace que la app sirva los archivos
# subidos; los estáticos ya los sirve whitenoise sin ruta extra.
if settings.SERVE_MEDIA:
    from django.views.static import serve as _media_serve

    # Detrás de login: acá viven los documentos que sube el ciudadano (fotos de
    # DNI, certificados) y el Excel del padrón. Servirlos abiertos los dejaba
    # descargables por cualquiera que acertara la ruta, y los nombres eran los
    # originales del archivo. Revisión de seguridad del 26/08/2026.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", login_required(_media_serve), {"document_root": settings.MEDIA_ROOT}),
    ]

handler500 = "config.views.server_error"
