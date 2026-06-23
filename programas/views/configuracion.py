"""Backoffice — Configuración del Programa Becas (#74).

Solo el Admin del programa (capacidad ``becas.configurar``) accede a estas
vistas: ABM de segmentos/subsegmentos (con validación de cupo RN-40), asignación
de coordinadores, ABM de requisitos nativos y de preguntas globales.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, requiere
from programas.forms import (
    AsignacionCoordinadorForm,
    PreguntaGlobalForm,
    RequisitoNativoForm,
    SegmentoForm,
    SubsegmentoForm,
)
from programas.models import (
    AsignacionCoordinador,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
    Subsegmento,
)

CAP_CONFIG = "becas.configurar"


class _ConfigBecasMixin(CapacidadRequeridaMixin, LoginRequiredMixin):
    capacidades_requeridas = CAP_CONFIG


# ---------------------------------------------------------------------------
# Segmentos
# ---------------------------------------------------------------------------
class SegmentoListView(_ConfigBecasMixin, ListView):
    model = Segmento
    template_name = "programas/becas/config/segmento_list.html"
    context_object_name = "segmentos"
    paginate_by = 20

    def get_queryset(self):
        return Segmento.objects.annotate(
            n_subsegmentos=Count("subsegmentos", distinct=True),
            n_coordinadores=Count("asignaciones_coordinador", distinct=True),
        ).order_by("nombre")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        agg = Segmento.objects.aggregate(total=Count("id"), cupo=Sum("cupo_maximo"))
        ctx["stat_total"] = agg["total"] or 0
        ctx["stat_cupo"] = agg["cupo"] or 0
        ctx["stat_activos"] = Segmento.objects.filter(activo=True).count()
        return ctx


class SegmentoCreateView(_ConfigBecasMixin, CreateView):
    model = Segmento
    form_class = SegmentoForm
    template_name = "programas/becas/config/segmento_form.html"
    success_url = reverse_lazy("becas:segmentos")

    def form_valid(self, form):
        messages.success(self.request, "Segmento creado.")
        return super().form_valid(form)


class SegmentoUpdateView(_ConfigBecasMixin, UpdateView):
    model = Segmento
    form_class = SegmentoForm
    template_name = "programas/becas/config/segmento_form.html"
    success_url = reverse_lazy("becas:segmentos")

    def form_valid(self, form):
        messages.success(self.request, "Segmento actualizado.")
        return super().form_valid(form)


class SegmentoDetailView(_ConfigBecasMixin, DetailView):
    model = Segmento
    template_name = "programas/becas/config/segmento_detail.html"
    context_object_name = "segmento"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        seg = self.object
        ctx["subsegmentos"] = seg.subsegmentos.all().order_by("nombre")
        ctx["coordinadores"] = (
            seg.asignaciones_coordinador.select_related("coordinador").order_by("coordinador__username")
        )
        ctx["requisitos"] = seg.requisitos.filter(subsegmento__isnull=True).order_by("orden", "id")
        ctx["form_subsegmento"] = SubsegmentoForm(segmento=seg)
        ctx["form_coordinador"] = AsignacionCoordinadorForm(segmento=seg)
        ctx["form_requisito"] = RequisitoNativoForm(segmento=seg)
        return ctx


@login_required
@requiere(CAP_CONFIG)
def segmento_toggle_activo(request, pk):
    if request.method != "POST":
        return redirect("becas:segmentos")
    seg = get_object_or_404(Segmento, pk=pk)
    seg.activo = not seg.activo
    seg.save(update_fields=["activo", "modificado"])
    messages.success(request, f"Segmento {'activado' if seg.activo else 'desactivado'}.")
    return redirect("becas:segmentos")


# ---------------------------------------------------------------------------
# Subsegmentos
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_CONFIG)
def subsegmento_crear(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    if request.method == "POST":
        form = SubsegmentoForm(request.POST, segmento=segmento)
        if form.is_valid():
            form.save()
            messages.success(request, "Subsegmento agregado.")
            return redirect("becas:segmento_detalle", pk=segmento.pk)
    else:
        form = SubsegmentoForm(segmento=segmento)
    return render(
        request,
        "programas/becas/config/subsegmento_form.html",
        {"form": form, "segmento": segmento},
    )


@login_required
@requiere(CAP_CONFIG)
def subsegmento_editar(request, pk):
    sub = get_object_or_404(Subsegmento, pk=pk)
    if request.method == "POST":
        form = SubsegmentoForm(request.POST, instance=sub, segmento=sub.segmento)
        if form.is_valid():
            form.save()
            messages.success(request, "Subsegmento actualizado.")
            return redirect("becas:segmento_detalle", pk=sub.segmento_id)
    else:
        form = SubsegmentoForm(instance=sub, segmento=sub.segmento)
    return render(
        request,
        "programas/becas/config/subsegmento_form.html",
        {"form": form, "segmento": sub.segmento, "subsegmento": sub},
    )


@login_required
@requiere(CAP_CONFIG)
def subsegmento_eliminar(request, pk):
    sub = get_object_or_404(Subsegmento, pk=pk)
    segmento_pk = sub.segmento_id
    if request.method == "POST":
        sub.delete()
        messages.success(request, "Subsegmento eliminado.")
    return redirect("becas:segmento_detalle", pk=segmento_pk)


# ---------------------------------------------------------------------------
# Coordinadores
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_CONFIG)
def coordinador_asignar(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    if request.method == "POST":
        form = AsignacionCoordinadorForm(request.POST, segmento=segmento)
        if form.is_valid():
            form.save()
            messages.success(request, "Coordinador asignado.")
        else:
            for err in form.errors.get("coordinador", []):
                messages.error(request, err)
    return redirect("becas:segmento_detalle", pk=segmento.pk)


@login_required
@requiere(CAP_CONFIG)
def coordinador_desasignar(request, pk):
    asignacion = get_object_or_404(AsignacionCoordinador, pk=pk)
    segmento_pk = asignacion.segmento_id
    if request.method == "POST":
        asignacion.delete()
        messages.success(request, "Coordinador desasignado.")
    return redirect("becas:segmento_detalle", pk=segmento_pk)


# ---------------------------------------------------------------------------
# Requisitos nativos (de segmento o de subsegmento)
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_CONFIG)
def requisito_crear(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    subsegmento = None
    sub_pk = request.GET.get("subsegmento") or request.POST.get("subsegmento")
    if sub_pk:
        subsegmento = get_object_or_404(Subsegmento, pk=sub_pk, segmento=segmento)
    if request.method == "POST":
        form = RequisitoNativoForm(request.POST, segmento=segmento, subsegmento=subsegmento)
        if form.is_valid():
            form.save()
            messages.success(request, "Requisito agregado.")
            if subsegmento:
                return redirect("becas:subsegmento_detalle", pk=subsegmento.pk)
            return redirect("becas:segmento_detalle", pk=segmento.pk)
    else:
        form = RequisitoNativoForm(segmento=segmento, subsegmento=subsegmento)
    return render(
        request,
        "programas/becas/config/requisito_form.html",
        {"form": form, "segmento": segmento, "subsegmento": subsegmento},
    )


@login_required
@requiere(CAP_CONFIG)
def requisito_eliminar(request, pk):
    req = get_object_or_404(RequisitoNativo, pk=pk)
    segmento_pk = req.segmento_id
    subsegmento_pk = req.subsegmento_id
    if request.method == "POST":
        req.delete()
        messages.success(request, "Requisito eliminado.")
    if subsegmento_pk:
        return redirect("becas:subsegmento_detalle", pk=subsegmento_pk)
    return redirect("becas:segmento_detalle", pk=segmento_pk)


class SubsegmentoDetailView(_ConfigBecasMixin, DetailView):
    """Detalle de subsegmento: requisitos heredados (solo lectura) + propios."""

    model = Subsegmento
    template_name = "programas/becas/config/subsegmento_detail.html"
    context_object_name = "subsegmento"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sub = self.object
        ctx["segmento"] = sub.segmento
        ctx["requisitos_heredados"] = sub.segmento.requisitos.filter(
            subsegmento__isnull=True
        ).order_by("orden", "id")
        ctx["requisitos_propios"] = sub.requisitos.order_by("orden", "id")
        ctx["form_requisito"] = RequisitoNativoForm(segmento=sub.segmento, subsegmento=sub)
        return ctx


# ---------------------------------------------------------------------------
# Preguntas globales (cuestionario social)
# ---------------------------------------------------------------------------
class PreguntaGlobalListView(_ConfigBecasMixin, ListView):
    model = PreguntaGlobal
    template_name = "programas/becas/config/pregunta_list.html"
    context_object_name = "preguntas"

    def get_queryset(self):
        return PreguntaGlobal.objects.order_by("orden", "id")


class PreguntaGlobalCreateView(_ConfigBecasMixin, CreateView):
    model = PreguntaGlobal
    form_class = PreguntaGlobalForm
    template_name = "programas/becas/config/pregunta_form.html"
    success_url = reverse_lazy("becas:preguntas")

    def form_valid(self, form):
        messages.success(self.request, "Pregunta creada.")
        return super().form_valid(form)


class PreguntaGlobalUpdateView(_ConfigBecasMixin, UpdateView):
    model = PreguntaGlobal
    form_class = PreguntaGlobalForm
    template_name = "programas/becas/config/pregunta_form.html"
    success_url = reverse_lazy("becas:preguntas")

    def form_valid(self, form):
        messages.success(self.request, "Pregunta actualizada.")
        return super().form_valid(form)


@login_required
@requiere(CAP_CONFIG)
def pregunta_toggle_activo(request, pk):
    if request.method != "POST":
        return redirect("becas:preguntas")
    pregunta = get_object_or_404(PreguntaGlobal, pk=pk)
    pregunta.activo = not pregunta.activo
    pregunta.save(update_fields=["activo", "modificado"])
    messages.success(request, f"Pregunta {'activada' if pregunta.activo else 'desactivada'}.")
    return redirect("becas:preguntas")


@login_required
@requiere(CAP_CONFIG)
def pregunta_eliminar(request, pk):
    pregunta = get_object_or_404(PreguntaGlobal, pk=pk)
    if request.method == "POST":
        pregunta.delete()
        messages.success(request, "Pregunta eliminada.")
    return redirect("becas:preguntas")
