"""
Vistas para Gestión Operativa de Programas
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, ListView

from core.rbac import CapacidadRequeridaMixin
from programas.models import InscripcionPrograma, Programa


class ProgramaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = "programa.ver"
    """
    Lista de programas que el usuario puede gestionar.
    - SuperAdmin: ve todos
    - Coordinador: ve solo sus programas asignados
    """
    model = Programa
    template_name = "legajos/programas/programa_list.html"
    context_object_name = "programas"

    def get_queryset(self):
        # DEPRECATED: filtros/annotates legacy removidos (dependían de models_institucional).
        return Programa.objects.filter(estado=Programa.Estado.ACTIVO).order_by("orden", "nombre")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["es_superadmin"] = self.request.user.is_superuser
        return context


class ProgramaDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    capacidades_requeridas = "programa.ver"
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
        programa = self.get_object()

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


@login_required
@require_http_methods(["POST"])
def dar_de_baja_inscripcion(request, inscripcion_id):
    """
    Da de baja a un ciudadano de un programa persistente.
    Espera campo POST 'motivo' (obligatorio).
    """
    from ..services.programas import BajaProgramaService

    inscripcion = get_object_or_404(InscripcionPrograma, id=inscripcion_id)
    motivo = request.POST.get("motivo", "").strip()

    if not motivo:
        messages.error(request, "Debe ingresar un motivo para la baja.")
        return redirect("legajos:programa_detalle", pk=inscripcion.programa_id)

    try:
        BajaProgramaService.dar_de_baja(
            inscripcion_id=inscripcion_id,
            usuario=request.user,
            motivo=motivo,
        )
        messages.success(
            request,
            f"{inscripcion.ciudadano.nombre_completo} fue dado de baja del programa correctamente.",
        )
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("legajos:programa_detalle", pk=inscripcion.programa_id)
