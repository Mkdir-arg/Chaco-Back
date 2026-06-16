from django.urls import include, path

from .views import alertas as views_alertas
from .views import ciudadanos as views_ciudadanos
from .views import contactos_api as views_contactos_api
from .views import contactos_panel as views_contactos_panel
from .views import dashboard_simple as views_simple
from .views import derivacion as views_derivacion
from .views import derivacion_programa as views_derivacion_programa
from .views import programas as views_programas
from . import views_ciudadanos_api

app_name = "legajos"

urlpatterns = [
    path("", views_ciudadanos.CiudadanoListView.as_view(), name="lista"),
    path("nuevo/", views_ciudadanos.CiudadanoCreateView.as_view(), name="nuevo"),
    path("ciudadanos/", views_ciudadanos.CiudadanoListView.as_view(), name="ciudadanos"),
    path("ciudadanos/buscar/", views_ciudadanos_api.ciudadano_buscar_api, name="ciudadano_buscar_api"),
    path("ciudadanos/nuevo/", views_ciudadanos.CiudadanoCreateView.as_view(), name="ciudadano_nuevo"),
    path("ciudadanos/confirmar/", views_ciudadanos.CiudadanoConfirmarView.as_view(), name="ciudadano_confirmar"),
    path("ciudadanos/manual/", views_ciudadanos.CiudadanoManualView.as_view(), name="ciudadano_manual"),
    path("ciudadanos/<int:pk>/", views_ciudadanos.CiudadanoDetailView.as_view(), name="ciudadano_detalle"),
    path("ciudadanos/<int:pk>/editar/", views_ciudadanos.CiudadanoUpdateView.as_view(), name="ciudadano_editar"),
    path("programas/", views_programas.ProgramaListView.as_view(), name="programas"),
    path("programas/<int:pk>/", views_programas.ProgramaDetailView.as_view(), name="programa_detalle"),
    path("nachec/", include("legajos.urls_nachec")),
    path(
        "ciudadanos/<int:ciudadano_id>/derivar-programa/",
        views_derivacion.derivar_programa_view,
        name="derivar_programa",
    ),
    path("dashboard-contactos/", views_contactos_panel.dashboard_contactos_simple, name="dashboard_contactos"),
    path("reportes/", views_simple.reportes_view, name="reportes"),
    path("reportes/exportar-csv/", views_simple.exportar_reportes_csv, name="exportar_csv"),
    path("derivaciones-ciudadano/<int:derivacion_id>/aceptar/", views_derivacion_programa.aceptar_derivacion_programa, name="derivacion_ciudadano_aceptar"),
    path("derivaciones-ciudadano/<int:derivacion_id>/rechazar/", views_derivacion_programa.rechazar_derivacion_programa, name="derivacion_ciudadano_rechazar"),
    path("test-contactos/", views_simple.dashboard_contactos_simple, name="test_contactos"),
    path("test-api/", views_simple.test_api, name="test_api"),
    path(
        "<uuid:legajo_id>/historial-contactos/",
        views_contactos_panel.historial_contactos_simple,
        name="historial_contactos",
    ),
    path("<uuid:legajo_id>/red-contactos/", views_contactos_panel.red_contactos_simple, name="red_contactos"),
    path(
        "ciudadanos/<int:ciudadano_id>/actividades/",
        views_contactos_api.actividades_ciudadano_api,
        name="actividades_ciudadano",
    ),
    path("<uuid:legajo_id>/subir-archivos/", views_contactos_api.subir_archivos_legajo, name="subir_archivos"),
    path("<uuid:legajo_id>/archivos/", views_contactos_api.archivos_legajo_api, name="archivos_legajo"),
    path(
        "ciudadanos/<int:ciudadano_id>/archivos/",
        views_contactos_api.archivos_ciudadano_api,
        name="archivos_ciudadano",
    ),
    path(
        "ciudadanos/<int:ciudadano_id>/subir-archivos/",
        views_contactos_api.subir_archivos_ciudadano,
        name="subir_archivos_ciudadano",
    ),
    path("archivos/<int:archivo_id>/eliminar/", views_contactos_api.eliminar_archivo, name="eliminar_archivo"),
    path(
        "ciudadanos/<int:ciudadano_id>/alertas/",
        views_contactos_api.alertas_ciudadano_api,
        name="alertas_ciudadano",
    ),
    path("alertas/<int:alerta_id>/cerrar/", views_contactos_api.cerrar_alerta_api, name="cerrar_alerta_ciudadano"),
    path(
        "ciudadanos/<int:ciudadano_id>/timeline/",
        views_contactos_api.timeline_ciudadano_api,
        name="timeline_ciudadano",
    ),
    path(
        "ciudadanos/<int:ciudadano_id>/prediccion-riesgo/",
        views_contactos_api.prediccion_riesgo_api,
        name="prediccion_riesgo",
    ),
    path("<uuid:legajo_id>/evolucion/", views_contactos_api.evolucion_legajo_api, name="evolucion_legajo"),
    path("alertas/", views_alertas.alertas_dashboard, name="alertas_dashboard"),
    path("alertas/<int:alerta_id>/cerrar-ajax/", views_alertas.cerrar_alerta_ajax, name="cerrar_alerta_ajax"),
    path("alertas/count/", views_alertas.alertas_count_ajax, name="alertas_count_ajax"),
    path("alertas/preview/", views_alertas.alertas_preview_ajax, name="alertas_preview_ajax"),
    path("alertas/debug/", views_alertas.debug_alertas, name="debug_alertas"),
    path("alertas/test/", views_alertas.test_alertas_page, name="test_alertas"),
]
