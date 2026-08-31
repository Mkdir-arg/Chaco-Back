"""Backoffice — Configuración del Programa Becas (#74).

Acceso granular por entidad (ver/crear/editar de Segmento, Subsegmento,
Requisito nativo, Pregunta global y Coordinador). La mutación de la estructura
de un segmento existente (subsegmento, requisito, coordinador) queda además
acotada por :func:`puede_gestionar_segmento` — así, si en el futuro se le
otorgan estas capacidades a un rol no-admin, solo puede operar sobre los
segmentos que tiene asignados.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, ListView, UpdateView
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, puede_alguna, requiere
from programas.forms import (
    AsignacionCoordinadorForm,
    GrupoRequisitoForm,
    PreguntaGlobalForm,
    ProgramaSiisCreateForm,
    RequisitoNativoForm,
    SegmentoCreateForm,
    SegmentoForm,
    SubsegmentoForm,
)
from programas.models import (
    AsignacionCoordinador,
    CanalFormulario,
    GrupoRequisito,
    ItemDiseno,
    PreguntaGlobal,
    PresentacionCampo,
    ProgramaSiis,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services.autorizacion import (
    SegmentoScopedMixin,
    es_admin_becas,
    es_coordinador_regional_becas,
    puede_gestionar_segmento,
    puede_operar_subsegmento,
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


def _assert_scope_subsegmento(request, subsegmento):
    """403 si el usuario no puede operar **ese** subsegmento (alcance del Coordinador Regional)."""
    if not puede_operar_subsegmento(request.user, subsegmento):
        raise PermissionDenied("No tiene acceso a este subsegmento.")


def _segmentos_qs(user):
    return (
        segmentos_visibles(user)
        .select_related("programa")
        .annotate(
            n_subsegmentos=Count("subsegmentos", distinct=True),
            n_coordinadores=Count("asignaciones_coordinador", distinct=True),
        )
        .prefetch_related("asignaciones_coordinador__coordinador")
        .order_by("nombre")
    )


def _programas_qs(user):
    """Programas SIIS que el usuario puede ver: todos para el admin; para el
    resto, los que contienen alguno de sus segmentos visibles."""
    if es_admin_becas(user):
        base = ProgramaSiis.objects.all()
    else:
        base = ProgramaSiis.objects.filter(segmentos__in=segmentos_visibles(user)).distinct()
    return base.annotate(n_segmentos=Count("segmentos", distinct=True)).order_by("nombre")


def _programas_bloqueados_siis(user):
    """Programas que dejaron de estar vigentes en SIIS (aviso en pantalla)."""
    return _programas_qs(user).filter(siis_programa_estado__in=ProgramaSiis.ESTADOS_SIIS_BLOQUEANTES)


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


def _requisitos_programa_ajax(request, programa, message="Requisito guardado."):
    return ajax_ok(
        request,
        target="#reqs-programa-panel",
        partial="programas/becas/config/_requisitos_programa_panel.html",
        context={
            "requisitos": programa.requisitos.order_by("orden", "id"),
            "programa": programa,
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
    qs = (
        requisitos_visibles(user)
        .select_related("programa", "segmento", "subsegmento")
        .order_by("segmento__nombre", "orden", "id")
    )
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
# Programas (SIIS)
# ---------------------------------------------------------------------------
class ProgramaSiisListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    model = ProgramaSiis
    capacidades_requeridas = CAP_SEGMENTO_VER
    template_name = "programas/becas/config/programa_list.html"
    context_object_name = "programas"

    def get_queryset(self):
        return _programas_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["form_programa"] = ProgramaSiisCreateForm()
        ctx["programas_bloqueados_siis"] = _programas_bloqueados_siis(self.request.user)
        return ctx


class ProgramaSiisCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    model = ProgramaSiis
    capacidades_requeridas = CAP_SEGMENTO_CREAR
    form_class = ProgramaSiisCreateForm
    template_name = "programas/becas/config/programa_list.html"
    success_url = reverse_lazy("becas:programas")

    def form_valid(self, form):
        self.object = form.save()
        # "Guardar y configurar": ir al detalle a cargar los segmentos.
        detalle = reverse("becas:programa_detalle", args=[self.object.pk])
        if is_ajax(self.request):
            return ajax_redirect(detalle, "Programa vinculado — agregá sus segmentos.")
        messages.success(self.request, "Programa vinculado.")
        return redirect(detalle)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class ProgramaSiisDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = ProgramaSiis
    capacidades_requeridas = CAP_SEGMENTO_VER
    template_name = "programas/becas/config/programa_detail.html"
    context_object_name = "programa"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not _programas_qs(self.request.user).filter(pk=obj.pk).exists():
            raise PermissionDenied("No tiene acceso a este programa.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        programa = self.object
        segmentos = (
            segmentos_visibles(self.request.user)
            .filter(programa=programa)
            .annotate(n_subsegmentos=Count("subsegmentos", distinct=True))
            .prefetch_related("asignaciones_coordinador__coordinador")
            .order_by("nombre")
        )
        ctx["segmentos"] = segmentos
        ctx["requisitos"] = programa.requisitos.order_by("orden", "id")
        ctx["form_segmento"] = SegmentoCreateForm(initial={"programa": programa.pk})
        ctx["form_requisito"] = RequisitoNativoForm(programa=programa)
        ctx["presentacion_choices"] = PresentacionCampo.choices
        ctx["canal_choices"] = CanalFormulario.choices
        return ctx


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
        with transaction.atomic():
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
        # El Coordinador Regional entra al segmento solo como contexto: ve
        # únicamente sus subsegmentos y no la configuración del segmento.
        solo_sus_subsegmentos = es_coordinador_regional_becas(self.request.user)
        ctx["solo_sus_subsegmentos"] = solo_sus_subsegmentos
        subsegmentos_qs = seg.subsegmentos.all()
        if solo_sus_subsegmentos:
            subsegmentos_qs = subsegmentos_qs.filter(pk__in=subsegmentos_visibles(self.request.user))
        subsegmentos = list(subsegmentos_qs.select_related("referente").order_by("nombre"))
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
        # Heredados del programa: solo lectura acá, se editan en el detalle del programa.
        ctx["requisitos_programa"] = (
            seg.programa.requisitos.order_by("orden", "id") if seg.programa_id else RequisitoNativo.objects.none()
        )
        ctx["form_segmento"] = SegmentoForm(instance=seg)
        ctx["form_subsegmento"] = SubsegmentoForm(segmento=seg)
        ctx["form_coordinador"] = AsignacionCoordinadorForm(segmento=seg)
        ctx["form_requisito"] = RequisitoNativoForm(segmento=seg)
        ctx["presentacion_choices"] = PresentacionCampo.choices
        ctx["canal_choices"] = CanalFormulario.choices
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
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error("nombre", "Ya existe un subsegmento con ese nombre en este segmento.")
                if is_ajax(request):
                    return ajax_errors(form)
                return render(
                    request,
                    "programas/becas/config/subsegmento_form.html",
                    {"form": form, "segmento": segmento, "subsegmento": None},
                )
            if is_ajax(request):
                subs = list(segmento.subsegmentos.select_related("referente").order_by("nombre"))
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
    _assert_scope_subsegmento(request, sub)
    if request.method == "POST":
        form = SubsegmentoForm(request.POST, instance=sub, segmento=sub.segmento)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error("nombre", "Ya existe un subsegmento con ese nombre en este segmento.")
                if is_ajax(request):
                    return ajax_errors(form)
                return render(
                    request,
                    "programas/becas/config/subsegmento_form.html",
                    {"form": form, "segmento": sub.segmento, "subsegmento": sub},
                )
            if is_ajax(request):
                origin = request.POST.get("origin")
                if origin == "panel":
                    subs = list(sub.segmento.subsegmentos.select_related("referente").order_by("nombre"))
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
    _assert_scope_subsegmento(request, sub)
    segmento_pk = sub.segmento_id
    if request.method == "POST":
        try:
            sub.delete()
            messages.success(request, "Subsegmento eliminado.")
        except ProtectedError:
            messages.error(request, "No se puede eliminar el subsegmento porque está utilizado por una convocatoria.")
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
# Requisitos nativos (de programa, segmento o subsegmento)
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_REQUISITO_CREAR)
def requisito_programa_crear(request, programa_pk):
    programa = get_object_or_404(ProgramaSiis, pk=programa_pk)
    if not es_admin_becas(request.user):
        raise PermissionDenied("Solo el Administrador del programa puede configurar sus requisitos.")
    if request.method == "POST":
        form = RequisitoNativoForm(request.POST, programa=programa)
        if form.is_valid():
            form.save()
            if is_ajax(request):
                return _requisitos_programa_ajax(request, programa, message="Requisito agregado.")
            messages.success(request, "Requisito agregado.")
            return redirect("becas:programa_detalle", pk=programa.pk)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = RequisitoNativoForm(programa=programa)
    return render(
        request,
        "programas/becas/config/requisito_form.html",
        {"form": form, "programa": programa},
    )


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


def _assert_scope_requisito(request, req):
    """Scope según el ancla: segmento/subsegmento → gestión del segmento;
    programa → solo el Administrador del programa."""
    if req.segmento_id:
        _assert_scope(request, req.segmento)
    elif not es_admin_becas(request.user):
        raise PermissionDenied("Solo el Administrador del programa puede configurar sus requisitos.")


@login_required
@requiere(CAP_REQUISITO_EDITAR)
def requisito_eliminar(request, pk):
    req = get_object_or_404(RequisitoNativo, pk=pk)
    _assert_scope_requisito(request, req)
    programa_pk = req.programa_id
    segmento_pk = req.segmento_id
    subsegmento_pk = req.subsegmento_id
    if request.method == "POST":
        req.delete()
        messages.success(request, "Requisito eliminado.")
    if subsegmento_pk:
        return redirect("becas:subsegmento_detalle", pk=subsegmento_pk)
    if segmento_pk:
        return redirect("becas:segmento_detalle", pk=segmento_pk)
    return redirect("becas:programa_detalle", pk=programa_pk)


@login_required
@requiere(CAP_REQUISITO_EDITAR)
def requisito_editar(request, pk):
    req = get_object_or_404(RequisitoNativo, pk=pk)
    _assert_scope_requisito(request, req)
    programa = req.programa
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
                if segmento:
                    return _requisitos_segmento_ajax(request, segmento, message="Requisito actualizado.")
                return _requisitos_programa_ajax(request, programa, message="Requisito actualizado.")
            messages.success(request, "Requisito actualizado.")
            if subsegmento:
                return redirect("becas:subsegmento_detalle", pk=subsegmento.pk)
            if segmento:
                return redirect("becas:segmento_detalle", pk=segmento.pk)
            return redirect("becas:programa_detalle", pk=programa.pk)
        elif is_ajax(request):
            return ajax_errors(form)
    else:
        form = RequisitoNativoForm(instance=req, segmento=segmento, subsegmento=subsegmento)
    return render(
        request,
        "programas/becas/config/requisito_form.html",
        {"form": form, "programa": programa, "segmento": segmento, "subsegmento": subsegmento, "requisito": req},
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
        ctx["presentacion_choices"] = PresentacionCampo.choices
        ctx["canal_choices"] = CanalFormulario.choices
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
        # Sobre el subsegmento, no sobre el segmento: un Coordinador Regional
        # entra al segmento pero solo puede abrir el subsegmento que tiene a cargo.
        self.assert_puede_operar_subsegmento(obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sub = self.object
        seg = sub.segmento
        ctx["segmento"] = seg
        # Herencia completa: primero los del programa, después los del segmento.
        heredados = list(seg.programa.requisitos.order_by("orden", "id")) if seg.programa_id else []
        heredados += list(seg.requisitos.filter(subsegmento__isnull=True).order_by("orden", "id"))
        ctx["requisitos_heredados"] = heredados
        ctx["requisitos_propios"] = sub.requisitos.order_by("orden", "id")
        ctx["form_requisito"] = RequisitoNativoForm(segmento=seg, subsegmento=sub)
        ctx["presentacion_choices"] = PresentacionCampo.choices
        ctx["canal_choices"] = CanalFormulario.choices
        return ctx


# ---------------------------------------------------------------------------
# Preguntas globales (cuestionario social)
# ---------------------------------------------------------------------------
def _grupos_con_preguntas():
    """``[(grupo, [preguntas])]`` en orden de pantalla, con los grupos vacíos
    (para poder soltar preguntas adentro). Cambio 58, #337."""
    grupos = list(GrupoRequisito.objects.order_by("orden", "id"))
    por_grupo = {g.pk: [] for g in grupos}
    sueltas = []
    for pregunta in PreguntaGlobal.objects.select_related("grupo").order_by("orden", "id"):
        (por_grupo[pregunta.grupo_id] if pregunta.grupo_id in por_grupo else sueltas).append(pregunta)
    resultado = [(g, por_grupo[g.pk]) for g in grupos]
    if sueltas:
        # Sin seed no hay «Cuestionario social»: se muestran igual, sin grupo.
        resultado.append((None, sueltas))
    return resultado


def _preguntas_ajax(request, message="Pregunta guardada."):
    return ajax_ok(
        request,
        target="#preguntas-table",
        partial="programas/becas/config/_preguntas_grupos.html",
        context={"grupos_con_preguntas": _grupos_con_preguntas(), "canal_choices": CanalFormulario.choices},
        message=message,
    )


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
@require_POST
def preguntas_reordenar(request):
    """Guarda el orden que dejó el drag & drop (#337): grupos por posición y
    preguntas por grupo. El orden del catálogo es único entre todas las
    preguntas (Cambio 23), así que se renumeran todas en el orden recibido y
    las que no vinieron quedan detrás, en su orden relativo."""
    try:
        payload = json.loads(request.body or b"{}")
        grupos = payload["grupos"]
        assert isinstance(grupos, list)
        grupo_ids = [int(g["id"]) for g in grupos if g.get("id") not in (None, "", "null")]
        pregunta_ids = [int(pk) for g in grupos for pk in g.get("preguntas", [])]
    except (ValueError, KeyError, AssertionError, TypeError, AttributeError):
        return JsonResponse({"ok": False, "error": "Payload inválido."}, status=400)
    if len(set(grupo_ids)) != len(grupo_ids) or len(set(pregunta_ids)) != len(pregunta_ids):
        return JsonResponse({"ok": False, "error": "Hay ids repetidos."}, status=400)
    existentes_g = set(GrupoRequisito.objects.filter(pk__in=grupo_ids).values_list("pk", flat=True))
    existentes_p = set(PreguntaGlobal.objects.filter(pk__in=pregunta_ids).values_list("pk", flat=True))
    if set(grupo_ids) - existentes_g or set(pregunta_ids) - existentes_p:
        return JsonResponse(
            {"ok": False, "error": "Algún grupo o pregunta ya no existe; recargá la página."}, status=409
        )

    with transaction.atomic():
        for posicion, grupo in enumerate(grupos):
            if grupo.get("id") in (None, "", "null"):
                continue
            GrupoRequisito.objects.filter(pk=int(grupo["id"])).update(orden=posicion)
        orden = 1
        for grupo in grupos:
            grupo_id = None if grupo.get("id") in (None, "", "null") else int(grupo["id"])
            for pk in grupo.get("preguntas", []):
                PreguntaGlobal.objects.filter(pk=int(pk)).update(grupo_id=grupo_id, orden=orden)
                orden += 1
        for pk in (
            PreguntaGlobal.objects.exclude(pk__in=pregunta_ids).order_by("orden", "id").values_list("pk", flat=True)
        ):
            PreguntaGlobal.objects.filter(pk=pk).update(orden=orden)
            orden += 1
    return _preguntas_ajax(request, "Orden guardado.")


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
@require_POST
def grupo_crear(request):
    form = GrupoRequisitoForm(request.POST)
    if not form.is_valid():
        return ajax_errors(form) if is_ajax(request) else redirect("becas:preguntas")
    grupo = form.save(commit=False)
    ultimo = GrupoRequisito.objects.aggregate(m=Max("orden"))["m"]
    grupo.orden = 0 if ultimo is None else ultimo + 1
    grupo.save()
    if is_ajax(request):
        return _preguntas_ajax(request, "Grupo creado.")
    messages.success(request, "Grupo creado.")
    return redirect("becas:preguntas")


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
@require_POST
def grupo_editar(request, pk):
    grupo = get_object_or_404(GrupoRequisito, pk=pk)
    form = GrupoRequisitoForm(request.POST, instance=grupo)
    if not form.is_valid():
        return ajax_errors(form) if is_ajax(request) else redirect("becas:preguntas")
    form.save()
    if is_ajax(request):
        return _preguntas_ajax(request, "Grupo actualizado.")
    messages.success(request, "Grupo actualizado.")
    return redirect("becas:preguntas")


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
@require_POST
def grupo_eliminar(request, pk):
    grupo = get_object_or_404(GrupoRequisito, pk=pk)
    if grupo.protegido:
        messages.error(request, "Este grupo viene con el sistema y no se puede eliminar.")
    elif grupo.preguntas.exists():
        messages.error(request, "El grupo tiene preguntas: movelas a otro grupo antes de eliminarlo.")
    else:
        # Los diseños que lo referencian (SET_NULL) conservan su último nombre.
        ItemDiseno.objects.filter(grupo_catalogo=grupo, etiqueta="").update(etiqueta=grupo.nombre)
        grupo.delete()
        messages.success(request, "Grupo eliminado.")
    return redirect("becas:preguntas")


class PreguntaGlobalListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    model = PreguntaGlobal
    capacidades_requeridas = CAP_PREGUNTA_VER
    template_name = "programas/becas/config/pregunta_list.html"
    context_object_name = "preguntas"

    def get_queryset(self):
        # Cambio 58: agrupadas; dentro del grupo, por orden.
        queryset = PreguntaGlobal.objects.select_related("grupo").order_by("grupo__orden", "grupo__id", "orden", "id")
        texto = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "").strip()
        obligatorio = self.request.GET.get("obligatorio", "").strip()
        activo = self.request.GET.get("activo", "").strip()
        if texto:
            queryset = queryset.filter(texto__icontains=texto)
        if tipo in TipoCampo.values:
            queryset = queryset.filter(tipo=tipo)
        if obligatorio in {"1", "0"}:
            queryset = queryset.filter(obligatorio=obligatorio == "1")
        if activo in {"1", "0"}:
            queryset = queryset.filter(activo=activo == "1")
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tipo_choices"] = TipoCampo.choices
        ctx["presentacion_choices"] = PresentacionCampo.choices
        ctx["canal_choices"] = CanalFormulario.choices
        ctx["hay_filtros_activos"] = any(
            self.request.GET.get(nombre, "").strip() for nombre in ("q", "tipo", "obligatorio", "activo")
        )
        ctx["grupos"] = GrupoRequisito.objects.order_by("orden", "id")
        # Cambio 58 (#337): sin filtros, la lista se muestra agrupada y con
        # drag & drop; con filtros, la tabla plana de siempre.
        ctx["grupos_con_preguntas"] = None if ctx["hay_filtros_activos"] else _grupos_con_preguntas()
        ctx["form_grupo"] = GrupoRequisitoForm()
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
    if pregunta.es_identidad:
        # Cambio 58, D12: sin identidad no hay caso.
        messages.error(request, "Los campos de identidad de la persona no se pueden desactivar.")
        return redirect("becas:preguntas")
    pregunta.activo = not pregunta.activo
    pregunta.save(update_fields=["activo", "modificado"])
    messages.success(request, f"Pregunta {'activada' if pregunta.activo else 'desactivada'}.")
    return redirect("becas:preguntas")


@login_required
@requiere(CAP_PREGUNTA_EDITAR)
def pregunta_eliminar(request, pk):
    pregunta = get_object_or_404(PreguntaGlobal, pk=pk)
    if request.method == "POST":
        if pregunta.protegido:
            # Cambio 58, RN-5: los protegidos se renombran, agrupan y ordenan; no se borran.
            messages.error(
                request, "Este campo viene con el sistema y no se puede eliminar; podés renombrarlo o moverlo de grupo."
            )
            return redirect("becas:preguntas")
        pregunta.delete()
        messages.success(request, "Pregunta eliminada.")
    return redirect("becas:preguntas")


# ---------------------------------------------------------------------------
# API JSON — uso interno del formulario de convocatoria
# ---------------------------------------------------------------------------
@login_required
def segmento_subsegmentos_json(request, pk):
    """Devuelve los subsegmentos de un segmento para el filtrado dinámico.

    Va scoped igual que el queryset del form (``subsegmentos_permitidos`` de
    ``ConvocatoriaForm``): el select se puebla por acá, así que sin este corte
    el Coordinador Regional veía en la lista los subsegmentos de sus pares
    (el POST igual los rechazaba, pero la UI ofrecía lo que no puede elegir).
    """
    if not puede_alguna(request.user, ["becas.convocatoria.ver", "becas.convocatoria.crear"]):
        raise PermissionDenied
    segmento = get_object_or_404(segmentos_visibles(request.user), pk=pk)
    data = list(
        subsegmentos_visibles(request.user)
        .filter(segmento=segmento)
        .order_by("nombre")
        .values("id", "nombre", "cupo_maximo")
    )
    return JsonResponse(data, safe=False)
