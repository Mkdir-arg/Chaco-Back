from django.urls import include, path

from . import views

app_name = "conversaciones"

urlpatterns = [
    # API URLs
    path("api/", include("conversaciones.api_urls")),
    # URLs públicas para ciudadanos
    path("chat/", views.chat_ciudadano, name="chat_ciudadano"),
    path("consultar-renaper/", views.consultar_renaper, name="consultar_renaper"),
    path("iniciar/", views.iniciar_conversacion, name="iniciar_conversacion"),
    path("<int:conversacion_id>/enviar/", views.enviar_mensaje_ciudadano, name="enviar_mensaje_ciudadano"),
    path("<int:conversacion_id>/mensajes/", views.obtener_mensajes_ciudadano, name="obtener_mensajes_ciudadano"),
    # URLs del backoffice
    path("", views.lista_conversaciones, name="lista"),
    path("<int:conversacion_id>/", views.detalle_conversacion, name="detalle"),
    path("<int:conversacion_id>/asignar/", views.asignar_conversacion, name="asignar"),
    path("<int:conversacion_id>/reasignar/", views.reasignar_conversacion, name="reasignar"),
    path("<int:conversacion_id>/responder/", views.enviar_mensaje_operador, name="enviar_mensaje_operador"),
    path("<int:conversacion_id>/cerrar/", views.cerrar_conversacion, name="cerrar"),
    path("<int:conversacion_id>/evaluar/", views.evaluar_conversacion, name="evaluar"),
    # Métricas y gestión
    path("metricas/", views.metricas_conversaciones, name="metricas"),
    path("configurar-cola/", views.configurar_cola, name="configurar_cola"),
    path("asignacion-automatica/", views.asignacion_automatica, name="asignacion_automatica"),
    path("api/metricas/", views.api_metricas_tiempo_real, name="api_metricas"),
    path("api/estadisticas/", views.api_estadisticas_tiempo_real, name="api_estadisticas"),
    path("api/conversacion/<int:conversacion_id>/", views.api_conversacion_detalle, name="api_conversacion_detalle"),
]
