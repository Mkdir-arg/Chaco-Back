"""
URLs para transiciones de estado Ñachec
"""

from django.urls import path

from ..views.nachec_cierre import cerrar_caso_nachec, reabrir_caso_nachec
from ..views.nachec_dashboard import dashboard_nachec
from ..views.nachec_decisiones import activar_plan, cerrar_caso, evaluar_caso, pasar_a_seguimiento
from ..views.nachec_operacion import (
    adjuntar_evidencias,
    asignar_territorial,
    autosave_relevamiento,
    completar_tarea,
    completar_validacion,
    enviar_a_asignacion,
    finalizar_relevamiento,
    formulario_relevamiento,
    iniciar_relevamiento,
    reasignar_territorial,
    ver_tarea_validacion,
)
from ..views.nachec_prestaciones import (
    cancelar_prestacion,
    confirmar_entrega_prestacion,
    iniciar_prestacion,
    reprogramar_prestacion,
)

urlpatterns = [
    path("dashboard/", dashboard_nachec, name="nachec_dashboard"),
    path("tarea/<int:tarea_id>/completar/", completar_tarea, name="nachec_completar_tarea"),
    path("caso/<int:caso_id>/tarea-validacion/", ver_tarea_validacion, name="nachec_ver_tarea_validacion"),
    path("caso/<int:caso_id>/completar-validacion/", completar_validacion, name="nachec_completar_validacion"),
    path("caso/<int:caso_id>/enviar-asignacion/", enviar_a_asignacion, name="nachec_enviar_asignacion"),
    path("caso/<int:caso_id>/asignar-territorial/", asignar_territorial, name="nachec_asignar_territorial"),
    path("caso/<int:caso_id>/reasignar-territorial/", reasignar_territorial, name="nachec_reasignar_territorial"),
    path("caso/<int:caso_id>/iniciar-relevamiento/", iniciar_relevamiento, name="nachec_iniciar_relevamiento"),
    path("caso/<int:caso_id>/relevamiento/", formulario_relevamiento, name="nachec_formulario_relevamiento"),
    path("caso/<int:caso_id>/relevamiento/autosave/", autosave_relevamiento, name="nachec_autosave_relevamiento"),
    path("caso/<int:caso_id>/adjuntar-evidencias/", adjuntar_evidencias, name="nachec_adjuntar_evidencias"),
    path("caso/<int:caso_id>/finalizar-relevamiento/", finalizar_relevamiento, name="nachec_finalizar_relevamiento"),
    path("caso/<int:caso_id>/evaluar/", evaluar_caso, name="nachec_evaluar_caso"),
    path("caso/<int:caso_id>/activar-plan/", activar_plan, name="nachec_activar_plan"),
    path("caso/<int:caso_id>/pasar-seguimiento/", pasar_a_seguimiento, name="nachec_pasar_seguimiento"),
    path("caso/<int:caso_id>/cerrar/", cerrar_caso, name="nachec_cerrar_caso_legajo"),
    path("prestacion/<int:prestacion_id>/iniciar/", iniciar_prestacion, name="nachec_iniciar_prestacion"),
    path(
        "prestacion/<int:prestacion_id>/confirmar-entrega/",
        confirmar_entrega_prestacion,
        name="nachec_confirmar_entrega",
    ),
    path("prestacion/<int:prestacion_id>/reprogramar/", reprogramar_prestacion, name="nachec_reprogramar_prestacion"),
    path("prestacion/<int:prestacion_id>/cancelar/", cancelar_prestacion, name="nachec_cancelar_prestacion"),
    path("caso/<int:caso_id>/cerrar-caso/", cerrar_caso_nachec, name="nachec_cerrar_caso"),
    path("caso/<int:caso_id>/reabrir-caso/", reabrir_caso_nachec, name="nachec_reabrir_caso"),
]
