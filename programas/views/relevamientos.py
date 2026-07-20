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
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.rbac import CapacidadRequeridaMixin, puede, requiere
from programas.forms import ConvocatoriaForm, ReasignarTerritorialForm, RelevamientoForm, ReprogramarForm
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento
from programas.services.autorizacion import puede_gestionar_segmento, segmentos_visibles
from programas.views.ajax_utils import ajax_errors, ajax_ok, is_ajax

CAP_CONVOCATORIA_VER = "becas.convocatoria.ver"
CAP_CONVOCATORIA_CREAR = "becas.convocatoria.crear"
CAP_CONVOCATORIA_EDITAR = "becas.convocatoria.editar"
CAP_RELEVAMIENTO_VER = "becas.relevamiento.ver"
CAP_RELEVAMIENTO_CREAR = "becas.relevamiento.crear"
CAP_RELEVAMIENTO_EDITAR = "becas.relevamiento.editar"
CAP_REPORTES = "becas.programa.administrar"


def _convocatorias_qs(request):
    return (
        Convocatoria.objects.select_related("segmento", "subsegmento")
        .defer("descripcion", "segmento__descripcion", "subsegmento__descripcion")
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


def _relevamientos_ajax(request, convocatoria, message="Relevamiento creado y asignado."):
    """Re-renderiza la tabla de relevamientos de una convocatoria (pestaña
    "Relevamientos" de su detalle) tras crear uno desde el modal embebido."""
    relevamientos = list(convocatoria.relevamientos.select_related("territorial").order_by("-fecha_asignada"))
    return ajax_ok(
        request,
        target="#relevamientos-table",
        partial="programas/becas/relevamientos/_relevamientos_tab_table.html",
        context={"relevamientos": relevamientos},
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
        # Materializados una vez: los counts se derivan en Python (evita 3
        # queries COUNT extra sobre los mismos datos).
        relevamientos = list(conv.relevamientos.select_related("territorial").order_by("-fecha_asignada"))
        ctx["relevamientos"] = relevamientos
        # Beneficiarios = formularios cargados en los relevamientos de esta convocatoria.
        beneficiarios = list(
            Formulario.objects.filter(relevamiento__convocatoria=conv)
            .select_related("ciudadano", "relevamiento")
            .order_by("-creado")
        )
        ctx["beneficiarios"] = beneficiarios
        ctx["n_relevamientos"] = len(relevamientos)
        ctx["n_beneficiarios"] = len(beneficiarios)
        ctx["n_aprobados"] = sum(1 for f in beneficiarios if f.estado == Formulario.Estado.APROBADO)
        ctx["puede_reportes"] = puede(self.request.user, CAP_REPORTES)
        ctx["cupo_segmento"] = conv.segmento.cupo_maximo
        form = ConvocatoriaForm(instance=conv)
        form.fields["segmento"].queryset = segmentos_visibles(self.request.user)
        ctx["form_convocatoria"] = form
        # Modal "Nuevo relevamiento" con esta convocatoria preseleccionada.
        ctx["form_crear"] = RelevamientoForm(
            initial={"convocatoria": conv},
            segmentos_permitidos=segmentos_visibles(self.request.user),
        )
        ctx["siguiente_nombre"] = Relevamiento.proximo_nombre()
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
@requiere(CAP_REPORTES)
def convocatoria_export_beneficiarios(request, pk):
    conv = get_object_or_404(Convocatoria.objects.select_related("segmento"), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="beneficiarios_convocatoria_{conv.pk}.csv"'
    response.write("﻿")  # BOM para Excel
    writer = csv.writer(response)
    writer.writerow(["Nombre", "DNI", "Segmento", "Convocatoria", "Fecha de aprobación"])
    formularios = (
        Formulario.objects.filter(relevamiento__convocatoria=conv, estado=Formulario.Estado.APROBADO)
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
        writer.writerow([nombre, dni, conv.segmento.nombre, conv.nombre, f.modificado.strftime("%d/%m/%Y")])
    return response


@login_required
@requiere(CAP_REPORTES)
def convocatoria_export_relevamientos(request, pk):
    conv = get_object_or_404(Convocatoria, pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="relevamientos_convocatoria_{conv.pk}.csv"'
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow(
        ["Relevamiento", "Territorial", "Fecha asignada", "Zona", "Estado", "Enviados", "Aprobados", "Rechazados"]
    )
    relevamientos = (
        conv.relevamientos.select_related("territorial")
        .annotate(
            n_enviados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.ENVIADO)),
            n_aprobados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.APROBADO)),
            n_rechazados=Count("formularios", filter=Q(formularios__estado=Formulario.Estado.RECHAZADO)),
        )
        .order_by("-fecha_asignada")
    )
    for r in relevamientos:
        terr = r.territorial.get_full_name() or r.territorial.username
        writer.writerow(
            [
                r.nombre,
                terr,
                r.fecha_asignada.strftime("%d/%m/%Y"),
                r.zona,
                r.get_estado_display(),
                r.n_enviados,
                r.n_aprobados,
                r.n_rechazados,
            ]
        )
    return response


@login_required
@requiere(CAP_REPORTES)
def convocatoria_export_lista_espera(request, pk):
    conv = get_object_or_404(Convocatoria.objects.select_related("segmento"), pk=pk)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="lista_espera_convocatoria_{conv.pk}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["Posición", "Nombre", "DNI", "Segmento", "Fecha de ingreso"])
    entradas = (
        ListaEspera.objects.filter(formulario__relevamiento__convocatoria=conv, promovido=False)
        .select_related("formulario__ciudadano", "segmento")
        .order_by("posicion")
    )
    for entrada in entradas:
        formulario = entrada.formulario
        if formulario.ciudadano_id:
            nombre = formulario.ciudadano.nombre_completo
            dni = formulario.ciudadano.dni
        else:
            datos = formulario.datos_identificacion or {}
            nombre = f"{datos.get('nombre', '')} {datos.get('apellido', '')}".strip()
            dni = datos.get("dni", "")
        writer.writerow(
            [entrada.posicion, nombre, dni, entrada.segmento.nombre, entrada.fecha_ingreso.strftime("%d/%m/%Y")]
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
            .defer("observaciones", "convocatoria__descripcion", "convocatoria__segmento__descripcion")
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
        ctx["siguiente_nombre"] = Relevamiento.proximo_nombre()
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
        self.object = form.save()
        if is_ajax(self.request):
            return _relevamientos_ajax(self.request, self.object.convocatoria)
        messages.success(self.request, "Relevamiento creado y asignado.")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if is_ajax(self.request):
            return ajax_errors(form)
        return super().form_invalid(form)

    def get_success_url(self):
        # "next" permite volver a la pantalla de origen (p. ej. el detalle de la
        # convocatoria cuando se crea desde su modal).
        next_url = self.request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return str(self.success_url)


class RelevamientoDetailView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = Relevamiento
    # El template y _assert_scope recorren convocatoria/segmento/territorial.
    queryset = Relevamiento.objects.select_related("convocatoria__segmento", "convocatoria__subsegmento", "territorial")
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
        ctx["form_reasignar"] = ReasignarTerritorialForm(
            initial={"territorial": rel.territorial}, segmento=rel.convocatoria.segmento
        )
        ctx["form_reprogramar"] = ReprogramarForm(initial={"fecha_asignada": rel.fecha_asignada})
        # Personas relevadas: se listan en la solapa "Formularios". Se materializa
        # una vez y el contador se deriva en Python (evita un COUNT extra).
        formularios = list(rel.formularios.select_related("ciudadano").order_by("-creado"))
        ctx["formularios"] = formularios
        ctx["n_formularios"] = len(formularios)
        ctx["puede_revisar"] = puede(self.request.user, "becas.revision.ver")
        ctx["estados_revisables"] = [
            Relevamiento.Estado.FINALIZADO,
            Relevamiento.Estado.EN_REVISION,
            Relevamiento.Estado.TERMINADO,
        ]
        return ctx


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
@require_POST
def relevamiento_finalizar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    if rel.estado != Relevamiento.Estado.EN_CURSO:
        messages.error(request, "Solo se puede finalizar un relevamiento en curso.")
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    rel.estado = Relevamiento.Estado.FINALIZADO
    rel.fecha_finalizado = timezone.now()
    rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
    messages.success(request, "Relevamiento finalizado.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
@require_POST
def relevamiento_reabrir(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    if rel.estado != Relevamiento.Estado.FINALIZADO:
        messages.error(request, "Solo se puede reabrir un relevamiento finalizado.")
        return redirect("becas:relevamiento_detalle", pk=rel.pk)

    rel.estado = Relevamiento.Estado.EN_CURSO
    rel.fecha_finalizado = None
    rel.save(update_fields=["estado", "fecha_finalizado", "modificado"])
    messages.success(request, "Relevamiento reabierto.")
    return redirect("becas:relevamiento_detalle", pk=rel.pk)


@login_required
@requiere(CAP_RELEVAMIENTO_EDITAR)
def relevamiento_reasignar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope(request, rel)
    if request.method == "POST":
        form = ReasignarTerritorialForm(request.POST, segmento=rel.convocatoria.segmento)
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
