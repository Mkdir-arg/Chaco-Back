"""Backoffice — Configuración del Programa Becas (#74).

Acceso granular por entidad (ver/crear/editar de Segmento, Subsegmento,
Requisito nativo, Pregunta global y Coordinador). La mutación de la estructura
de un segmento existente (subsegmento, requisito, coordinador) queda además
acotada por :func:`puede_gestionar_segmento` — así, si en el futuro se le
otorgan estas capacidades a un rol no-admin, solo puede operar sobre los
segmentos que tiene asignados.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, puede_alguna, requiere
from programas.forms import (
    AsignacionCoordinadorForm,
    PreguntaGlobalForm,
    RequisitoNativoForm,
    SegmentoCreateForm,
    SegmentoForm,
    SubsegmentoForm,
)
from programas.models import (
    AsignacionCoordinador,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services.autorizacion import (
    SegmentoScopedMixin,
    puede_gestionar_segmento,
    requisitos_visibles,
    segmentos_visibles,
    subsegmentos_visibles,
)
from programas.views.ajax_utils import ajax_errors, ajax_ok, ajax_redirect, is_ajax

CAP_SEGMENTO_VER = "becas.segmento.ver"
CAP_SEGMENTO_CREAR = "becas.segmento.crear"
CAP_SEGMENTO_EDITAR = "becas.segmento.editar"
CAP_SUBSEGMENTO_VER = "becas.subsegmento.ver"
CAP_SUBSEGMENTO_CREAR = "becas.subsegmento.crear"
CAP_SUBSEGMENTO_EDITAR = "becas.subsegmento.editar"
CAP_REQUISITO_VER = "becas.requisito.ver"
CAP_REQUISITO_CREAR = "becas.requisito.crear"
CAP_REQUISITO_EDITAR = "becas.requisito.editar"
CAP_PREGUNTA_VER = "becas.pregunta.ver"
CAP_PREGUNTA_CREAR = "becas.pregunta.crear"
CAP_PREGUNTA_EDITAR = "becas.pregunta.editar"
CAP_COORDINADOR_CREAR = "becas.coordinador.crear"
CAP_COORDINADOR_EDITAR = "becas.coordinador.editar"


def _assert_scope(request, segmento):
    """403 si el usuario no puede gestionar el ``segmento`` (ver ``SegmentoScopedMixin``)."""
    if not puede_gestionar_segmento(request.user, segmento):
        raise PermissionDenied("No tiene acceso a este segmento.")


def _segmentos_qs(user):
    return (
        segmentos_visibles(user)
        .annotate(
            n_subsegmentos=Count("subsegmentos", distinct=True),
            n_coordinadores=Count("asignaciones_coordinador", distinct=True),
        )
        .prefetch_related("asignaciones_coordinador__coordinador")
        .order_by("nombre")
    )


def _segmentos_ajax(request, message="Segmento guardado."):
    return ajax_ok(
        request,
        target="#segmentos-table",
        partial="programas/becas/config/_segmentos_table.html",
        context={"segmentos": _segmentos_qs(request.user)},
        message=message,
    )


def _requisitos_segmento_ajax(request, segmento, message="Requisito guardado."):
    return ajax_ok(
        request,
        target="#reqs-panel",
        partial="programas/becas/config/_requisitos_panel.html",
        context={
            "requisitos": segmento.requisitos.filter(subsegmento__isnull=True).order_by("orden", "id"),
            "segmento": segmento,
        },
        message=message,
    )


def _requisitos_subsegmento_ajax(request, subsegmento, message="Requisito guardado."):
    return ajax_ok(
        request,
        target="#reqs-propios-panel",
        partial="programas/becas/config/_requisitos_propios_panel.html",
        context={
            "requisitos_propios": subsegmento.requisitos.order_by("orden", "id"),
            "subsegmento": subsegmento,
            "segmento": subsegmento.segmento,
        },
        message=message,
    )


def _requisitos_reqseg_qs(user, segmento_id=None, subsegmento_id=None):
    qs = requisitos_visibles(user).select_related("segmento", "subsegmento").order_by("segmento__nombre", "orden", "id")
    if segmento_id:
        qs = qs.filter(segmento_id=segmento_id)
    if subsegmento_id:
        qs = qs.filter(subsegmento_id=subsegmento_id)
    return qs


def _requisitos_reqseg_ajax(request, message="Guardado."):
    seg = request.POST.get("f_segmento") or None
    sub = request.POST.get("f_subsegmento") or None
    return ajax_ok(
        request,
        target="#reqseg-table",
        partial="programas/becas/config/_requisitos_page_table.html",
        context={"requisitos": _requisitos_reqseg_qs(request.user, seg, sub)},
        message=message,
    )


# ---------------------------------------------------------------------------
# Segmentos
# ---------------------------------------------------------------------------
class SegmentoListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    model = Segmento
    capacidades_requeridas = CAP_SEGMENTO_VER
    template_name = "programas/becas/config/segmento_list.html"
    context_object_name = "segmentos"

    def get_queryset(self):
        return _segmentos_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_segmento"] = SegmentoCreateForm()
        return ctx


class SegmentoCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    model = Segmento
    capacidades_requeridas = CAP_SEGMENTO_CREAR
    form_class = SegmentoCreateForm
    template_name = "programas/becas/config/segmento_form.html"
    success_url = reverse_lazy("becas:segmentos")

    def form_valid(self, form):
        self.object = form.save()
        # El coordinador del alta se persiste como asignación (modal del kit).
        AsignacionCoordinador.objects.create(segmento=self.object, coordinador=form.cleaned_data["coordinador"])
        # "Guardar y configurar": ir al detalle a cargar subsegmentos/cupos.
        detalle = reverse("becas:segmento_detalle", args=[self.object.pk])
        if is_ajax(self.request):
            return ajax_redirect(detalle, "Segmento creado — agregá sus subsegmentos.")
        messages.success(self.request, "Segmento creado.")
        return redirect(detalle)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class SegmentoUpdateView(SegmentoScopedMixin, CapacidadRequeridaMixin, LoginRequiredMixin, UpdateView):
    model = Segmento
    capacidades_requeridas = CAP_SEGMENTO_EDITAR
    form_class = SegmentoForm
    template_name = "programas/becas/config/segmento_form.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.assert_puede_gestionar_segmento(obj)
        return obj

    def get_success_url(self):
        # La edición vive en la pestaña "Información general" del detalle; volver allí.
        return reverse("becas:segmento_detalle", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        self.object = form.save()
        if is_ajax(self.request):
            return _segmentos_ajax(self.request, "Segmento actualizado.")
        messages.success(self.request, "Segmento actualizado.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class SegmentoDetailView(SegmentoScopedMixin, CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Segmento
    capacidades_requeridas = CAP_SEGMENTO_VER
    template_name = "programas/becas/config/segmento_detail.html"
    context_object_name = "segmento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.assert_puede_gestionar_segmento(obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        seg = self.object
        subsegmentos = list(seg.subsegmentos.all().order_by("nombre"))
        ctx["subsegmentos"] = subsegmentos
        ctx["subsegmentos_cupo_total"] = sum(s.cupo_maximo for s in subsegmentos)
        # Cupo calculado UNA vez acá: las properties del modelo disparan un SUM
        # por cada acceso y el template las consulta muchas veces.
        ctx["cupo_distribuido"] = ctx["subsegmentos_cupo_total"]
        ctx["cupo_disponible"] = seg.cupo_maximo - ctx["subsegmentos_cupo_total"]
        ctx["coordinadores"] = seg.asignaciones_coordinador.select_related("coordinador").order_by(
            "coordinador__username"
        )
        # Solo lectura: la asignación del territorial se gestiona desde el ABM de Usuarios.
        ctx["territoriales"] = seg.asignaciones_territorial.select_related("territorial").order_by(
            "territorial__first_name", "territorial__last_name", "territorial__username"
        )
        ctx["requisitos"] = seg.requisitos.filter(subsegmento__isnull=True).order_by("orden", "id")
        ctx["form_segmento"] = SegmentoForm(instance=seg)
        ctx["form_subsegmento"] = SubsegmentoForm(segmento=seg)
        ctx["form_coordinador"] = AsignacionCoordinadorForm(segmento=seg)
        ctx["form_requisito"] = RequisitoNativoForm(segmento=seg)
        return ctx


@login_required
@requiere(CAP_SEGMENTO_EDITAR)
def segmento_toggle_activo(request, pk):
    if request.method != "POST":
        return redirect("becas:segmentos")
    seg = get_object_or_404(Segmento, pk=pk)
    _assert_scope(request, seg)
    seg.activo = not seg.activo
    seg.save(update_fields=["activo", "modificado"])
    messages.success(request, f"Segmento {'activado' if seg.activo else 'desactivado'}.")
    return redirect("becas:segmentos")


# ---------------------------------------------------------------------------
# Subsegmentos
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_SUBSEGMENTO_CREAR)
def subsegmento_crear(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    _assert_scope(request, segmento)
    if request.method == "POST":
        form = SubsegmentoForm(request.POST, segmento=segmento)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                subs = list(segmento.subsegmentos.all().order_by("nombre"))
                return ajax_ok(
                    request,
                    target="#subs-panel",
                    partial="programas/becas/config/_subsegmentos_panel.html",
                    context={
                        "subsegmentos": subs,
                        "subsegmentos_cupo_total": sum(s.cupo_maximo for s in subs),
                    },
                    message="Subsegmento agregado.",
                )
            messages.success(request, "Subsegmento agregado.")
            return redirect("becas:segmento_detalle", pk=segmento.pk)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = SubsegmentoForm(segmento=segmento)
    return render(
        request,
        "programas/becas/config/subsegmento_form.html",
        {"form": form, "segmento": segmento, "subsegmento": None},
    )


@login_required
@requiere(CAP_SUBSEGMENTO_EDITAR)
def subsegmento_editar(request, pk):
    sub = get_object_or_404(Subsegmento, pk=pk)
    _assert_scope(request, sub.segmento)
    if request.method == "POST":
        form = SubsegmentoForm(request.POST, instance=sub, segmento=sub.segmento)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                origin = request.POST.get("origin")
                if origin == "panel":
                    subs = list(sub.segmento.subsegmentos.all().order_by("nombre"))
                    return ajax_ok(
                        request,
                        target="#subs-panel",
                        partial="programas/becas/config/_subsegmentos_panel.html",
                        context={
                            "subsegmentos": subs,
                            "subsegmentos_cupo_total": sum(s.cupo_maximo for s in subs),
                        },
                        message="Subsegmento actualizado.",
                    )
                else:
                    return ajax_redirect(
                        reverse("becas:subsegmento_detalle", args=[sub.pk]),
                        message="Subsegmento actualizado.",
                    )
            messages.success(request, "Subsegmento actualizado.")
            return redirect("becas:segmento_detalle", pk=sub.segmento_id)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = SubsegmentoForm(instance=sub, segmento=sub.segmento)
    return render(
        request,
        "programas/becas/config/subsegmento_form.html",
        {"form": form, "segmento": sub.segmento, "subsegmento": sub},
    )


@login_required
@requiere(CAP_SUBSEGMENTO_EDITAR)
def subsegmento_eliminar(request, pk):
    sub = get_object_or_404(Subsegmento, pk=pk)
    _assert_scope(request, sub.segmento)
    segmento_pk = sub.segmento_id
    if request.method == "POST":
        sub.delete()
        messages.success(request, "Subsegmento eliminado.")
    return redirect("becas:segmento_detalle", pk=segmento_pk)


# ---------------------------------------------------------------------------
# Coordinadores
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_COORDINADOR_CREAR)
def coordinador_asignar(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    _assert_scope(request, segmento)
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
@requiere(CAP_COORDINADOR_EDITAR)
def coordinador_desasignar(request, pk):
    asignacion = get_object_or_404(AsignacionCoordinador, pk=pk)
    _assert_scope(request, asignacion.segmento)
    segmento_pk = asignacion.segmento_id
    if request.method == "POST":
        asignacion.delete()
        messages.success(request, "Coordinador desasignado.")
    return redirect("becas:segmento_detalle", pk=segmento_pk)


# ---------------------------------------------------------------------------
# Requisitos nativos (de segmento o de subsegmento)
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_REQUISITO_CREAR)
def requisito_crear(request, segmento_pk):
    segmento = get_object_or_404(Segmento, pk=segmento_pk)
    _assert_scope(request, segmento)
    subsegmento = None
    sub_pk = request.GET.get("subsegmento") or request.POST.get("subsegmento")
    if sub_pk:
        subsegmento = get_object_or_404(Subsegmento, pk=sub_pk, segmento=segmento)
    if request.method == "POST":
        form = RequisitoNativoForm(request.POST, segmento=segmento, subsegmento=subsegmento)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                if request.POST.get("scope") == "subsegmento" and subsegmento:
                    return _requisitos_subsegmento_ajax(request, subsegmento, message="Requisito agregado.")
                if request.POST.get("scope") == "reqseg":
                    return _requisitos_reqseg_ajax(request, message="Requisito agregado.")
                return _requisitos_segmento_ajax(request, segmento, message="Requisito agregado.")
            messages.success(request, "Requisito agregado.")
            if subsegmento:
                return redirect("becas:subsegmento_detalle", pk=subsegmento.pk)
            return redirect("becas:segmento_detalle", pk=segmento.pk)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = RequisitoNativoForm(segmento=segmento, subsegmento=subsegmento)
    return render(
        request,
        "programas/becas/config/requisito_form.html",
        {"form": form, "segmento": segmento, "subsegmento": subsegmento},
    )


@login_required
@requiere(CAP_REQUISITO_EDITAR)
def requisito_eliminar(request, pk):
    req = get_object_or_404(RequisitoNativo, pk=pk)
    _assert_scope(request, req.segmento)
    segmento_pk = req.segmento_id
    subsegmento_pk = req.subsegmento_id
    if request.method == "POST":
        req.delete()
        messages.success(request, "Requisito eliminado.")
    if subsegmento_pk:
        return redirect("becas:subsegmento_detalle", pk=subsegmento_pk)
    return redirect("becas:segmento_detalle", pk=segmento_pk)


@login_required
@requiere(CAP_REQUISITO_EDITAR)
def requisito_editar(request, pk):
    req = get_object_or_404(RequisitoNativo, pk=pk)
    _assert_scope(request, req.segmento)
    segmento = req.segmento
    subsegmento = req.subsegmento
    if request.method == "POST":
        form = RequisitoNativoForm(request.POST, instance=req, segmento=segmento, subsegmento=subsegmento)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                if request.POST.get("scope") == "subsegmento" and subsegmento:
                    return _requisitos_subsegmento_ajax(request, subsegmento, message="Requisito actualizado.")
                if request.POST.get("scope") == "reqseg":
                    return _requisitos_reqseg_ajax(request, message="Requisito actualizado.")
                return _requisitos_segmento_ajax(request, segmento, message="Requisito actualizado.")
            messages.success(request, "Requisito actualizado.")
            if subsegmento:
                return redirect("becas:subsegmento_detalle", pk=subsegmento.pk)
            return redirect("becas:segmento_detalle", pk=segmento.pk)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = RequisitoNativoForm(instance=req, segmento=segmento, subsegmento=subsegmento)
    return render(
        request,
        "programas/becas/config/requisito_form.html",
        {"form": form, "segmento": segmento, "subsegmento": subsegmento, "requisito": req},
    )


class RequisitosSegmentoView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    """Vista filtrable: todos los requisitos nativos, con filtro por segmento y subsegmento."""

    model = RequisitoNativo
    capacidades_requeridas = CAP_REQUISITO_VER
    template_name = "programas/becas/config/requisitos_segmento.html"
    context_object_name = "requisitos"

    def get_queryset(self):
        return _requisitos_reqseg_qs(
            self.request.user, self.request.GET.get("segmento"), self.request.GET.get("subsegmento")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["segmentos"] = segmentos_visibles(self.request.user).filter(activo=True).order_by("nombre")
        ctx["subsegmentos"] = (
            subsegmentos_visibles(self.request.user).select_related("segmento").order_by("segmento__nombre", "nombre")
        )
        ctx["seg_actual"] = self.request.GET.get("segmento", "")
        ctx["sub_actual"] = self.request.GET.get("subsegmento", "")
        ctx["tipo_choices"] = TipoCampo.choices
        ctx["form_requisito"] = RequisitoNativoForm()
        return ctx


class SubsegmentoDetailView(SegmentoScopedMixin, CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    """Detalle de subsegmento: requisitos heredados (solo lectura) + propios."""

    model = Subsegmento
    capacidades_requeridas = CAP_SUBSEGMENTO_VER
    template_name = "programas/becas/config/subsegmento_detail.html"
    context_object_name = "subsegmento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.assert_puede_gestionar_segmento(obj.segmento)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sub = self.object
        ctx["segmento"] = sub.segmento
        ctx["requisitos_heredados"] = sub.segmento.requisitos.filter(subsegmento__isnull=True).order_by("orden", "id")
        ctx["requisitos_propios"] = sub.requisitos.order_by("orden", "id")
        ctx["form_requisito"] = RequisitoNativoForm(segmento=sub.segmento, subsegmento=sub)
        return ctx


# ---------------------------------------------------------------------------
# Preguntas globales (cuestionario social)
# ---------------------------------------------------------------------------
def _preguntas_ajax(request, message="Pregunta guardada."):
    return ajax_ok(
        request,
        target="#preguntas-table",
        partial="programas/becas/config/_preguntas_table.html",
        context={"preguntas": PreguntaGlobal.objects.order_by("orden", "id")},
        message=message,
    )


class PreguntaGlobalListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    model = PreguntaGlobal
    capacidades_requeridas = CAP_PREGUNTA_VER
    template_name = "programas/becas/config/pregunta_list.html"
    context_object_name = "preguntas"

    def get_queryset(self):
        return PreguntaGlobal.objects.order_by("orden", "id")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tipo_choices"] = TipoCampo.choices
        return ctx


class PreguntaGlobalCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    model = PreguntaGlobal
    capacidades_requeridas = CAP_PREGUNTA_CREAR
    form_class = PreguntaGlobalForm
    template_name = "programas/becas/config/pregunta_form.html"
    success_url = reverse_lazy("becas:preguntas")

    def form_valid(self, form):
        self.object = form.save()
        if is_ajax(self.request):
            return _preguntas_ajax(self.request, "Pregunta creada.")
        messages.success(self.request, "Pregunta creada.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class PreguntaGlobalUpdateView(CapacidadRequeridaMixin, LoginRequiredMixin, UpdateView):
    model = PreguntaGlobal
    capacidades_requeridas = CAP_PREGUNTA_EDITAR
    form_class = PreguntaGlobalForm
    template_name = "programas/becas/config/pregunta_form.html"
    success_url = reverse_lazy("becas:preguntas")

    def form_valid(self, form):
        self.object = form.save()
        if is_ajax(self.request):
            return _preguntas_ajax(self.request, "Pregunta actualizada.")
        messages.success(self.request, "Pregunta actualizada.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
def pregunta_toggle_activo(request, pk):
    if request.method != "POST":
        return redirect("becas:preguntas")
    pregunta = get_object_or_404(PreguntaGlobal, pk=pk)
    pregunta.activo = not pregunta.activo
    pregunta.save(update_fields=["activo", "modificado"])
    messages.success(request, f"Pregunta {'activada' if pregunta.activo else 'desactivada'}.")
    return redirect("becas:preguntas")


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
def pregunta_eliminar(request, pk):
    pregunta = get_object_or_404(PreguntaGlobal, pk=pk)
    if request.method == "POST":
        pregunta.delete()
        messages.success(request, "Pregunta eliminada.")
    return redirect("becas:preguntas")


# ---------------------------------------------------------------------------
# API JSON — uso interno del formulario de convocatoria
# ---------------------------------------------------------------------------
@login_required
def segmento_subsegmentos_json(request, pk):
    """Devuelve los subsegmentos de un segmento para el filtrado dinámico."""
    if not puede_alguna(request.user, ["becas.convocatoria.ver", "becas.convocatoria.crear"]):
        raise PermissionDenied
    segmento = get_object_or_404(Segmento, pk=pk)
    data = list(segmento.subsegmentos.order_by("nombre").values("id", "nombre", "cupo_maximo"))
    return JsonResponse(data, safe=False)
