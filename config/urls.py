from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
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
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
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

    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", _media_serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler500 = "config.views.server_error"
