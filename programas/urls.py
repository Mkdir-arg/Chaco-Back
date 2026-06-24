"""URLs del backoffice del Programa Becas (namespace ``becas``)."""
from django.urls import path

from programas.views import configuracion as cfg
from programas.views import relevamientos as rel
from programas.views import revision as rev

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

    # --- Convocatorias ---
    path("convocatorias/", rel.ConvocatoriaListView.as_view(), name="convocatorias"),
    path("convocatorias/nueva/", rel.ConvocatoriaCreateView.as_view(), name="convocatoria_crear"),

    # --- Relevamientos ---
    path("relevamientos/", rel.RelevamientoListView.as_view(), name="relevamientos"),
    path("relevamientos/nuevo/", rel.RelevamientoCreateView.as_view(), name="relevamiento_crear"),
    path("relevamientos/<int:pk>/", rel.RelevamientoDetailView.as_view(), name="relevamiento_detalle"),
    path("relevamientos/<int:pk>/reasignar/", rel.relevamiento_reasignar, name="relevamiento_reasignar"),
    path("relevamientos/<int:pk>/reprogramar/", rel.relevamiento_reprogramar, name="relevamiento_reprogramar"),

    # --- Revisión de formularios ---
    path("revision/", rev.RevisionRelevamientoListView.as_view(), name="revision"),
    path("revision/relevamiento/<int:relevamiento_pk>/", rev.revision_formularios, name="revision_formularios"),
    path("revision/relevamiento/<int:pk>/iniciar/", rev.relevamiento_iniciar_revision, name="revision_iniciar"),
    path("revision/relevamiento/<int:pk>/terminar/", rev.relevamiento_terminar, name="revision_terminar"),
    path("revision/formulario/<int:pk>/", rev.formulario_detalle, name="formulario_detalle"),
    path("revision/formulario/<int:pk>/aprobar/", rev.formulario_aprobar, name="formulario_aprobar"),
    path("revision/formulario/<int:pk>/rechazar/", rev.formulario_rechazar, name="formulario_rechazar"),
]
