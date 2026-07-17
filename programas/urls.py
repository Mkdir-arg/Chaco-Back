"""URLs del backoffice del Programa Becas (namespace ``becas``)."""

from django.urls import path

from programas.views import configuracion as cfg
from programas.views import cupo as cpo
from programas.views import relevamientos as rel
from programas.views import revision as rev
from programas.views import solapas_becas as sb

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
    path(
        "config/segmentos/<int:pk>/subsegmentos-json/",
        cfg.segmento_subsegmentos_json,
        name="segmento_subsegmentos_json",
    ),
    path("config/subsegmentos/<int:pk>/", cfg.SubsegmentoDetailView.as_view(), name="subsegmento_detalle"),
    path("config/subsegmentos/<int:pk>/editar/", cfg.subsegmento_editar, name="subsegmento_editar"),
    path("config/subsegmentos/<int:pk>/eliminar/", cfg.subsegmento_eliminar, name="subsegmento_eliminar"),
    # --- Coordinadores ---
    path(
        "config/segmentos/<int:segmento_pk>/coordinadores/asignar/", cfg.coordinador_asignar, name="coordinador_asignar"
    ),
    path("config/coordinadores/<int:pk>/desasignar/", cfg.coordinador_desasignar, name="coordinador_desasignar"),
    # --- Requisitos nativos ---
    path("config/segmentos/<int:segmento_pk>/requisitos/nuevo/", cfg.requisito_crear, name="requisito_crear"),
    path("config/requisitos/<int:pk>/editar/", cfg.requisito_editar, name="requisito_editar"),
    path("config/requisitos/<int:pk>/eliminar/", cfg.requisito_eliminar, name="requisito_eliminar"),
    path("config/requisitos/", cfg.RequisitosSegmentoView.as_view(), name="requisitos_segmento"),
    # --- Preguntas globales (cuestionario social) ---
    path("config/preguntas/", cfg.PreguntaGlobalListView.as_view(), name="preguntas"),
    path("config/preguntas/nueva/", cfg.PreguntaGlobalCreateView.as_view(), name="pregunta_crear"),
    path("config/preguntas/<int:pk>/editar/", cfg.PreguntaGlobalUpdateView.as_view(), name="pregunta_editar"),
    path("config/preguntas/<int:pk>/toggle/", cfg.pregunta_toggle_activo, name="pregunta_toggle"),
    path("config/preguntas/<int:pk>/eliminar/", cfg.pregunta_eliminar, name="pregunta_eliminar"),
    # --- Convocatorias ---
    path("convocatorias/", rel.ConvocatoriaListView.as_view(), name="convocatorias"),
    path("convocatorias/nueva/", rel.ConvocatoriaCreateView.as_view(), name="convocatoria_crear"),
    path("convocatorias/<int:pk>/", rel.ConvocatoriaDetailView.as_view(), name="convocatoria_detalle"),
    path("convocatorias/<int:pk>/editar/", rel.ConvocatoriaUpdateView.as_view(), name="convocatoria_editar"),
    path("convocatorias/<int:pk>/toggle/", rel.convocatoria_toggle_activo, name="convocatoria_toggle"),
    path(
        "convocatorias/<int:pk>/export/beneficiarios/",
        rel.convocatoria_export_beneficiarios,
        name="convocatoria_export_beneficiarios",
    ),
    path(
        "convocatorias/<int:pk>/export/relevamientos/",
        rel.convocatoria_export_relevamientos,
        name="convocatoria_export_relevamientos",
    ),
    path(
        "convocatorias/<int:pk>/export/lista-espera/",
        rel.convocatoria_export_lista_espera,
        name="convocatoria_export_lista_espera",
    ),
    # --- Relevamientos ---
    path("relevamientos/", rel.RelevamientoListView.as_view(), name="relevamientos"),
    path("relevamientos/nuevo/", rel.RelevamientoCreateView.as_view(), name="relevamiento_crear"),
    path("relevamientos/<int:pk>/", rel.RelevamientoDetailView.as_view(), name="relevamiento_detalle"),
    path("relevamientos/<int:pk>/finalizar/", rel.relevamiento_finalizar, name="relevamiento_finalizar"),
    path("relevamientos/<int:pk>/reabrir/", rel.relevamiento_reabrir, name="relevamiento_reabrir"),
    path("relevamientos/<int:pk>/reasignar/", rel.relevamiento_reasignar, name="relevamiento_reasignar"),
    path("relevamientos/<int:pk>/reprogramar/", rel.relevamiento_reprogramar, name="relevamiento_reprogramar"),
    # --- Revisión de formularios ---
    path("revision/", rev.RevisionPersonasListView.as_view(), name="revision"),
    path("revision/renaper/pendientes/", rev.RenaperPendientesListView.as_view(), name="renaper_pendientes"),
    path("revision/relevamiento/<int:relevamiento_pk>/", rev.revision_formularios, name="revision_formularios"),
    path("revision/relevamiento/<int:pk>/iniciar/", rev.relevamiento_iniciar_revision, name="revision_iniciar"),
    path("revision/relevamiento/<int:pk>/terminar/", rev.relevamiento_terminar, name="revision_terminar"),
    path("revision/formulario/<int:pk>/", rev.formulario_detalle, name="formulario_detalle"),
    path("revision/formulario/<int:pk>/aprobar/", rev.formulario_aprobar, name="formulario_aprobar"),
    path("revision/formulario/<int:pk>/rechazar/", rev.formulario_rechazar, name="formulario_rechazar"),
    path(
        "revision/formulario/<int:pk>/revalidar-renaper/",
        rev.formulario_revalidar_renaper,
        name="formulario_revalidar_renaper",
    ),
    # --- Cupo y lista de espera (#78) ---
    path("cupo/segmento/<int:pk>/", cpo.CupoSegmentoDetailView.as_view(), name="cupo_segmento"),
    path("cupo/beneficiario/<int:pk>/baja/", cpo.dar_baja_beneficiario_view, name="beneficiario_dar_baja"),
    path("cupo/lista-espera/<int:pk>/promover/", cpo.promover_lista_espera_view, name="lista_espera_promover"),
    path("cupo/formulario/<int:pk>/agregar-espera/", cpo.agregar_lista_espera_view, name="formulario_agregar_espera"),
    # --- Solapa Becas en legajo (#80) ---
    path("becas/ciudadano/<int:pk>/", sb.becas_ciudadano_detalle, name="becas_ciudadano_detalle"),
]
