"""
Vistas para Gestión Operativa de Programas
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from core.rbac import CapacidadRequeridaMixin
from programas.models import InscripcionPrograma, Programa


class ProgramaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    # Gate de legajos: estas pantallas quedaron como destino de redirect de las
    # derivaciones y bajas de inscripción, que las opera quien trabaja legajos.
    capacidades_requeridas = "ciudadano.ver"
    """
    Lista de programas que el usuario puede gestionar.
    - SuperAdmin: ve todos
    - Coordinador: ve solo sus programas asignados
    """
    model = Programa
    template_name = "legajos/programas/programa_list.html"
    context_object_name = "programas"

    def get_queryset(self):
        # Solo el listado de programas activos. Las anotaciones de instituciones,
        # derivaciones pendientes y casos activos dependían de `models_institucional`
        # y se fueron con él; el template dejó de imprimirlas (FE-16).
        return Programa.objects.filter(estado=Programa.Estado.ACTIVO).order_by("orden", "nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["es_superadmin"] = self.request.user.is_superuser
        return context


class ProgramaDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    capacidades_requeridas = "ciudadano.ver"
    """
    Vista detallada de un programa con 5 solapas operativas:
    1. Dashboard Ejecutivo
    2. Bandeja de Derivaciones
    3. Ciudadanos en Atención
    4. Instituciones Participantes
    5. Indicadores
    """
    model = Programa
    template_name = "legajos/programas/programa_detail.html"
    context_object_name = "programa"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        programa = self.object

        # DEPRECATED: operativa institucional legacy retirada con models_institucional.
        context.update(
            {
                "legacy_programa_operativa_deprecated": True,
                "total_instituciones": 0,
                "total_derivaciones_pendientes": 0,
                "total_casos_activos": 0,
                "total_casos_totales": 0,
                "derivaciones_ciudadanos": [],
                "derivaciones_institucionales": [],
                "instituciones": [],
                "casos_activos": [],
                "acompanamientos": [],
                "total_acompanamientos_activos": 0,
                "stats_ciudadanos": {
                    "pendientes": 0,
                    "aceptadas": 0,
                    "rechazadas": 0,
                },
                "stats_acompanamientos": {
                    "activos": 0,
                    "seguimiento": 0,
                    "cerrados": 0,
                    "bajas": 0,
                },
                "total_derivaciones": 0,
                "tasa_aceptacion": 0,
                "top_instituciones": [],
                "max_casos_institucion": 0,
                "ultimas_derivaciones": [],
                "promedio_casos_institucion": 0,
                "total_acompanamientos_totales": InscripcionPrograma.objects.filter(programa=programa).count(),
                "es_superadmin": self.request.user.is_superuser,
            }
        )
        return context


# LEG-06 (Ola 7): acá vivía `dar_de_baja_inscripcion`, que **ningún `path()` montaba**.
# Su único invocador era un botón de `programa_detail.html` que posteaba a
# `/legajos/acompanamiento/<id>/dar-de-baja/` —404 desde siempre, medido por RED-42— y
# que además nunca se dibujaba, porque `acompanamientos` viene vacío fijo (FE-16). El
# servicio que llamaba, `BajaProgramaService`, sigue en `legajos/services/programas.py`
# con su test de BEC-18: estrenar la baja es decisión del PM, no limpieza de deuda.
