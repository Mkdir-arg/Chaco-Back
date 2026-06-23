"""URLs del backoffice del Programa Becas (namespace ``becas``)."""
from django.urls import path

from programas.views import configuracion as cfg

app_name = "becas"

urlpatterns = [
    # --- Configuración: Segmentos ---
    path("config/segmentos/", cfg.SegmentoListView.as_view(), name="segmentos"),
    path("config/segmentos/nuevo/", cfg.SegmentoCreateView.as_view(), name="segmento_crear"),
    path("config/segmentos/<int:pk>/", cfg.SegmentoDetailView.as_view(), name="segmento_detalle"),
    path("config/segmentos/<int:pk>/editar/", cfg.SegmentoUpdateView.as_view(), name="segmento_editar"),
    path("config/segmentos/<int:pk>/toggle/", cfg.segmento_toggle_activo, name="segmento_toggle"),

    # --- Subsegmentos ---
    path("config/segmentos/<int:segmento_pk>/subsegmentos/nuevo/", cfg.subsegmento_crear, name="subsegmento_crear"),
    path("config/subsegmentos/<int:pk>/", cfg.SubsegmentoDetailView.as_view(), name="subsegmento_detalle"),
    path("config/subsegmentos/<int:pk>/editar/", cfg.subsegmento_editar, name="subsegmento_editar"),
    path("config/subsegmentos/<int:pk>/eliminar/", cfg.subsegmento_eliminar, name="subsegmento_eliminar"),

    # --- Coordinadores ---
    path("config/segmentos/<int:segmento_pk>/coordinadores/asignar/", cfg.coordinador_asignar, name="coordinador_asignar"),
    path("config/coordinadores/<int:pk>/desasignar/", cfg.coordinador_desasignar, name="coordinador_desasignar"),

    # --- Requisitos nativos ---
    path("config/segmentos/<int:segmento_pk>/requisitos/nuevo/", cfg.requisito_crear, name="requisito_crear"),
    path("config/requisitos/<int:pk>/eliminar/", cfg.requisito_eliminar, name="requisito_eliminar"),

    # --- Preguntas globales (cuestionario social) ---
    path("config/preguntas/", cfg.PreguntaGlobalListView.as_view(), name="preguntas"),
    path("config/preguntas/nueva/", cfg.PreguntaGlobalCreateView.as_view(), name="pregunta_crear"),
    path("config/preguntas/<int:pk>/editar/", cfg.PreguntaGlobalUpdateView.as_view(), name="pregunta_editar"),
    path("config/preguntas/<int:pk>/toggle/", cfg.pregunta_toggle_activo, name="pregunta_toggle"),
    path("config/preguntas/<int:pk>/eliminar/", cfg.pregunta_eliminar, name="pregunta_eliminar"),
]
