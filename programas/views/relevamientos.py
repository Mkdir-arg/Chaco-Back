"""Backoffice — ABM de Relevamientos y Convocatorias de Becas (#76).

Acceso: Coordinador y Admin (capacidad ``becas.relevamientos``). El alcance por
segmento se aplica en la query (un coordinador solo ve/gestiona relevamientos de
sus segmentos asignados); el Admin ve todos.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from core.rbac import CapacidadRequeridaMixin, puede, requiere
from programas.forms import ConvocatoriaForm, RelevamientoForm, ReprogramarForm, ReasignarTerritorialForm
from programas.models import Convocatoria, Relevamiento
from programas.services.autorizacion import puede_gestionar_segmento, segmentos_visibles

CAP = "becas.relevamientos"


class _RelevMixin(CapacidadRequeridaMixin, LoginRequiredMixin):
    capacidades_requeridas = CAP


def _assert_scope(request, relevamiento):
    """403 si el usuario no puede gestionar el segmento del relevamiento."""
    if not puede_gestionar_segmento(request.user, relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


# ---------------------------------------------------------------------------
# Convocatorias (prerequisito para crear relevamientos)
# ---------------------------------------------------------------------------
class ConvocatoriaListView(_RelevMixin, ListView):
    template_name = "programas/becas/relevamientos/convocatoria_list.html"
    context_object_name = "convocatorias"
    paginate_by = 20

    def get_queryset(self):
        return (
            Convocatoria.objects.select_related("segmento", "subsegmento")
            .filter(segmento__in=segmentos_visibles(self.request.user))
            .order_by("-fecha_inicio", "nombre")
        )


class ConvocatoriaCreateView(_RelevMixin, CreateView):
    form_class = ConvocatoriaForm
    template_name = "programas/becas/relevamientos/convocatoria_form.html"
    success_url = reverse_lazy("becas:convocatorias")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        return form

    def form_valid(self, form):
        messages.success(self.request, "Convocatoria creada.")
        return super().form_valid(form)


# ---------------------------------------------------------------------------
# Relevamientos
# ---------------------------------------------------------------------------
class RelevamientoListView(_RelevMixin, ListView):
    template_name = "programas/becas/relevamientos/relevamiento_list.html"
    context_object_name = "relevamientos"
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Relevamiento.objects.select_related("convocatoria__segmento", "territorial")
            .filter(convocatoria__segmento__in=segmentos_visibles(self.request.user))
            .order_by("-fecha_asignada", "nombre")
        )
        estado = self.request.GET.get("estado")
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["estados"] = Relevamiento.Estado.choices
        ctx["estado_actual"] = self.request.GET.get("estado", "")
        return ctx


class RelevamientoCreateView(_RelevMixin, CreateView):
    form_class = RelevamientoForm
    template_name = "programas/becas/relevamientos/relevamiento_form.html"
    success_url = reverse_lazy("becas:relevamientos")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["segmentos_permitidos"] = segmentos_visibles(self.request.user)
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Relevamiento creado y asignado.")
        return super().form_valid(form)


class RelevamientoDetailView(_RelevMixin, DetailView):
    model = Relevamiento
    template_name = "programas/becas/relevamientos/relevamiento_detail.html"
    context_object_name = "relevamiento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        _assert_scope(self.request, obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rel = self.object
        ctx["form_reasignar"] = ReasignarTerritorialForm()
        ctx["form_reprogramar"] = ReprogramarForm(initial={"fecha_asignada": rel.fecha_asignada})
        ctx["n_formularios"] = rel.formularios.count()
        ctx["puede_revisar"] = puede(self.request.user, "becas.revisar")
        return ctx


@login_required
@requiere(CAP)
def relevamiento_reasignar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    if request.method == "POST":
        form = ReasignarTerritorialForm(request.POST)
        if form.is_valid():
            rel.territorial = form.cleaned_data["territorial"]
            rel.save(update_fields=["territorial", "modificado"])
            messages.success(request, "Territorial reasignado.")
        else:
            messages.error(request, "No se pudo reasignar: revisá el territorial seleccionado.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP)
def relevamiento_reprogramar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    if request.method == "POST":
        form = ReprogramarForm(request.POST)
        if form.is_valid():
            rel.fecha_asignada = form.cleaned_data["fecha_asignada"]
            rel.save(update_fields=["fecha_asignada", "modificado"])
            messages.success(request, "Relevamiento reprogramado.")
        else:
            messages.error(request, "Fecha inválida.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)
