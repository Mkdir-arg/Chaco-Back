"""Backoffice — ABM de Relevamientos y Convocatorias de Becas (#76).

Acceso granular por entidad (ver/crear/editar de Convocatoria y Relevamiento).
El alcance por segmento se aplica en la query (un coordinador solo ve/gestiona
relevamientos de sus segmentos asignados); el Admin ve todos.
"""

import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.rbac import CapacidadRequeridaMixin, puede, requiere
from programas.forms import ConvocatoriaForm, ReasignarTerritorialForm, RelevamientoForm, ReprogramarForm
from programas.models import Convocatoria, Formulario, Relevamiento
from programas.services.autorizacion import puede_gestionar_segmento, segmentos_visibles
from programas.views.ajax_utils import ajax_errors, ajax_ok, is_ajax

CAP_CONVOCATORIA_VER = "becas.convocatoria.ver"
CAP_CONVOCATORIA_CREAR = "becas.convocatoria.crear"
CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
CAP_RELEVAMIENTO_VER = "becas.relevamiento.ver"
CAP_RELEVAMIENTO_CREAR = "becas.relevamiento.crear"
CAP_RELEVAMIENTO_EDITAR = "becas.relevamiento.editar"


def _convocatorias_qs(request):
    return (
        Convocatoria.objects.select_related("segmento", "subsegmento")
        .annotate(n_relevamientos=Count("relevamientos", distinct=True))
        .filter(segmento__in=segmentos_visibles(request.user))
        .order_by("-fecha_inicio", "nombre")
    )


def _convocatorias_ajax(request, message="Convocatoria guardada."):
    return ajax_ok(
        request,
        target="#convocatorias-table",
        partial="programas/becas/relevamientos/_convocatorias_table.html",
        context={"convocatorias": _convocatorias_qs(request)},
        message=message,
    )


def _assert_scope(request, relevamiento):
    """403 si el usuario no puede gestionar el segmento del relevamiento."""
    if not puede_gestionar_segmento(request.user, relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


# ---------------------------------------------------------------------------
# Convocatorias (prerequisito para crear relevamientos)
# ---------------------------------------------------------------------------
class ConvocatoriaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_CONVOCATORIA_VER
    template_name = "programas/becas/relevamientos/convocatoria_list.html"
    context_object_name = "convocatorias"

    def get_queryset(self):
        return _convocatorias_qs(self.request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ConvocatoriaForm()
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        ctx["form_convocatoria"] = form
        return ctx


class ConvocatoriaDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Convocatoria
    capacidades_requeridas = CAP_CONVOCATORIA_VER
    template_name = "programas/becas/relevamientos/convocatoria_detail.html"
    context_object_name = "convocatoria"

    def get_queryset(self):
        return Convocatoria.objects.select_related("segmento", "subsegmento").filter(
            segmento__in=segmentos_visibles(self.request.user)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        conv = self.object
        relevamientos = conv.relevamientos.select_related("territorial").order_by("-fecha_asignada")
        ctx["relevamientos"] = relevamientos
        # Beneficiarios = formularios cargados en los relevamientos de esta convocatoria.
        beneficiarios = (
            Formulario.objects.filter(relevamiento__convocatoria=conv)
            .select_related("ciudadano", "relevamiento")
            .order_by("-creado")
        )
        ctx["beneficiarios"] = beneficiarios
        ctx["n_relevamientos"] = relevamientos.count()
        ctx["n_beneficiarios"] = beneficiarios.count()
        ctx["n_aprobados"] = beneficiarios.filter(estado=Formulario.Estado.APROBADO).count()
        ctx["cupo_segmento"] = conv.segmento.cupo_maximo
        form = ConvocatoriaForm(instance=conv)
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        ctx["form_convocatoria"] = form
        return ctx


class ConvocatoriaCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = CAP_CONVOCATORIA_CREAR
    form_class = ConvocatoriaForm
    template_name = "programas/becas/relevamientos/convocatoria_form.html"
    success_url = reverse_lazy("becas:convocatorias")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        return form

    def form_valid(self, form):
        self.object = form.save()
        if is_ajax(self.request):
            return _convocatorias_ajax(self.request, "Convocatoria creada.")
        messages.success(self.request, "Convocatoria creada.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)


class ConvocatoriaUpdateView(CapacidadRequeridaMixin, LoginRequiredMixin, UpdateView):
    capacidades_requeridas = CAP_CONVOCATORIA_EDITAR
    form_class = ConvocatoriaForm
    template_name = "programas/becas/relevamientos/convocatoria_form.html"
    context_object_name = "convocatoria"

    def get_queryset(self):
        return Convocatoria.objects.filter(segmento__in=segmentos_visibles(self.request.user))

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        return form

    def get_success_url(self):
        return reverse("becas:convocatoria_detalle", kwargs={"pk": self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, "Convocatoria actualizada.")
        return super().form_valid(form)


@login_required
@requiere(CAP_CONVOCATORIA_EDITAR)
def convocatoria_toggle_activo(request, pk):
    conv = get_object_or_404(Convocatoria.objects.filter(segmento__in=segmentos_visibles(request.user)), pk=pk)
    if request.method == "POST":
        conv.activo = not conv.activo
        conv.save(update_fields=["activo", "modificado"])
        messages.success(request, f"Convocatoria {'activada' if conv.activo else 'desactivada'}.")
    return redirect(request.POST.get("next") or "becas:convocatorias")


@login_required
@requiere(CAP_CONVOCATORIA_VER)
def convocatoria_export_beneficiarios(request, pk):
    conv = get_object_or_404(Convocatoria.objects.filter(segmento__in=segmentos_visibles(request.user)), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="beneficiarios_convocatoria_{conv.pk}.csv"'
    response.write("﻿")  # BOM para Excel
    writer = csv.writer(response)
    writer.writerow(["DNI", "Nombre", "Estado", "Relevamiento", "Fecha"])
    formularios = (
        Formulario.objects.filter(relevamiento__convocatoria=conv)
        .select_related("ciudadano", "relevamiento")
        .order_by("-creado")
    )
    for f in formularios:
        if f.ciudadano_id:
            dni = f.ciudadano.dni
            nombre = f.ciudadano.nombre_completo
        else:
            ident = f.datos_identificacion or {}
            dni = ident.get("dni", "")
            nombre = f"{ident.get('nombre', '')} {ident.get('apellido', '')}".strip()
        writer.writerow([dni, nombre, f.get_estado_display(), f.relevamiento.nombre, f.creado.strftime("%d/%m/%Y")])
    return response


@login_required
@requiere(CAP_CONVOCATORIA_VER)
def convocatoria_export_relevamientos(request, pk):
    conv = get_object_or_404(Convocatoria.objects.filter(segmento__in=segmentos_visibles(request.user)), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="relevamientos_convocatoria_{conv.pk}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(["Relevamiento", "Territorial", "Zona", "Fecha asignada", "Estado", "Formularios"])
    relevamientos = conv.relevamientos.select_related("territorial").order_by("-fecha_asignada")
    for r in relevamientos:
        terr = r.territorial.get_full_name() or r.territorial.username
        writer.writerow(
            [
                r.nombre,
                terr,
                r.zona,
                r.fecha_asignada.strftime("%d/%m/%Y"),
                r.get_estado_display(),
                r.formularios.count(),
            ]
        )
    return response


# ---------------------------------------------------------------------------
# Relevamientos
# ---------------------------------------------------------------------------
class RelevamientoListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_RELEVAMIENTO_VER
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
        # Form + nombre autogenerado para el modal "Nuevo relevamiento".
        ctx["form_crear"] = RelevamientoForm(segmentos_permitidos=segmentos_visibles(self.request.user))
        ctx["siguiente_nombre"] = f"Relevamiento {Relevamiento.objects.count() + 1:03d}"
        return ctx


class RelevamientoCreateView(CapacidadRequeridaMixin, LoginRequiredMixin, CreateView):
    capacidades_requeridas = CAP_RELEVAMIENTO_CREAR
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


class RelevamientoDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Relevamiento
    capacidades_requeridas = CAP_RELEVAMIENTO_VER
    template_name = "programas/becas/relevamientos/relevamiento_detail.html"
    context_object_name = "relevamiento"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        _assert_scope(self.request, obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rel = self.object
        ctx["form_reasignar"] = ReasignarTerritorialForm(initial={"territorial": rel.territorial})
        ctx["form_reprogramar"] = ReprogramarForm(initial={"fecha_asignada": rel.fecha_asignada})
        ctx["n_formularios"] = rel.formularios.count()
        ctx["puede_revisar"] = puede(self.request.user, "becas.revision.ver")
        ctx["estados_revisables"] = [
            Relevamiento.Estado.FINALIZADO,
            Relevamiento.Estado.EN_REVISION,
        ]
        return ctx


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
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
@requiere(CAP_RELEVAMIENTO_EDITAR)
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
