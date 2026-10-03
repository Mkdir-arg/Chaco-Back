from django.urls import include, path

from . import views

app_name = "conversaciones"

urlpatterns = [
    # API URLs
    path("api/", include("conversaciones.api_urls")),
    # Las URLs públicas del chat (chat/, consultar-renaper/, iniciar/, <id>/enviar/
    # y <id>/mensajes/) quedaron desmontadas: sin login creaban el legajo de
    # cualquier DNI y devolvían sus datos de RENAPER (G1-01 y G1-02, auditoría
    # oct-2026). El ciudadano consulta por el portal, con sesión.
    # Con ellas cae también <id>/evaluar/: era la última escritura anónima de la
    # app —un POST sin login ni control de dueño pisaba la satisfacción de
    # cualquier conversación por id— y ninguna pantalla la consumía (R0-01).
    # URLs del backoffice
    path("", views.lista_conversaciones, name="lista"),
    path("<int:conversacion_id>/", views.detalle_conversacion, name="detalle"),
    path("<int:conversacion_id>/asignar/", views.asignar_conversacion, name="asignar"),
    path("<int:conversacion_id>/reasignar/", views.reasignar_conversacion, name="reasignar"),
    path("<int:conversacion_id>/responder/", views.enviar_mensaje_operador, name="enviar_mensaje_operador"),
    path("<int:conversacion_id>/cerrar/", views.cerrar_conversacion, name="cerrar"),
    # Métricas y gestión
    path("metricas/", views.metricas_conversaciones, name="metricas"),
    path("configurar-cola/", views.configurar_cola, name="configurar_cola"),
    path("asignacion-automatica/", views.asignacion_automatica, name="asignacion_automatica"),
    path("api/metricas/", views.api_metricas_tiempo_real, name="api_metricas"),
    path("api/estadisticas/", views.api_estadisticas_tiempo_real, name="api_estadisticas"),
    path("api/conversacion/<int:conversacion_id>/", views.api_conversacion_detalle, name="api_conversacion_detalle"),
]
