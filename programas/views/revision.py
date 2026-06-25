"""Backoffice — Revisión de formularios de Becas (#77).

Acceso: Coordinador y Admin (capacidad ``becas.revisar``), con alcance por
segmento. Permite listar los formularios de un relevamiento finalizado, editar
campos de contacto/apoderado (cada cambio queda en ``TracaFormulario``) y
aprobar/rechazar (con motivo) caso a caso. La validación SIS es un placeholder.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from core.rbac import CapacidadRequeridaMixin, requiere
from programas.forms import FormularioRevisionForm
from programas.models import (
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
)
from programas.services.autorizacion import puede_gestionar_segmento, segmentos_visibles
from programas.services.becas import registrar_traza

CAP = "becas.revisar"


class _RevisionMixin(CapacidadRequeridaMixin, LoginRequiredMixin):
    capacidades_requeridas = CAP


def _assert_scope_relevamiento(request, relevamiento):
    if not puede_gestionar_segmento(request.user, relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este relevamiento.")


def _assert_scope_formulario(request, formulario):
    if not puede_gestionar_segmento(request.user, formulario.relevamiento.segmento):
        raise PermissionDenied("No tiene acceso a este formulario.")


class RevisionRelevamientoListView(_RevisionMixin, ListView):
    """Relevamientos listos para revisar (finalizados / en revisión)."""

    template_name = "programas/becas/revision/relevamiento_list.html"
    context_object_name = "relevamientos"
    paginate_by = 25

    def get_queryset(self):
        return (
            Relevamiento.objects.select_related("convocatoria__segmento", "territorial")
            .filter(
                convocatoria__segmento__in=segmentos_visibles(self.request.user),
                estado__in=[
                    Relevamiento.Estado.FINALIZADO,
                    Relevamiento.Estado.EN_REVISION,
                    Relevamiento.Estado.TERMINADO,
                ],
            )
            .order_by("-fecha_finalizado", "-fecha_asignada")
        )


@login_required
@requiere(CAP)
def revision_formularios(request, relevamiento_pk):
    relevamiento = get_object_or_404(
        Relevamiento.objects.select_related("convocatoria__segmento"), pk=relevamiento_pk
    )
    _assert_scope_relevamiento(request, relevamiento)

    formularios = relevamiento.formularios.select_related("ciudadano").order_by("-creado")
    estado = request.GET.get("estado")
    if estado:
        formularios = formularios.filter(estado=estado)

    return render(
        request,
        "programas/becas/revision/formulario_list.html",
        {
            "relevamiento": relevamiento,
            "formularios": formularios,
            "estados": Formulario.Estado.choices,
            "estado_actual": estado or "",
            "pendientes": relevamiento.formularios.filter(estado=Formulario.Estado.ENVIADO).count(),
        },
    )


def _respuestas_resueltas(formulario):
    """Arma listas legibles de respuestas (pregunta/requisito → valor)."""
    data = formulario.data or {}
    globales = data.get("globales", {}) or {}
    requisitos = data.get("requisitos", {}) or {}

    preg_map = {str(p.pk): p.texto for p in PreguntaGlobal.objects.all()}
    req_ids = [int(k) for k in requisitos.keys() if str(k).isdigit()]
    req_map = {str(r.pk): r.texto for r in RequisitoNativo.objects.filter(pk__in=req_ids)}

    globales_list = [(preg_map.get(str(k), f"Pregunta #{k}"), v) for k, v in globales.items()]
    requisitos_list = [(req_map.get(str(k), f"Requisito #{k}"), v) for k, v in requisitos.items()]
    return globales_list, requisitos_list


@login_required
@requiere(CAP)
def formulario_detalle(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento", "ciudadano"), pk=pk
    )
    _assert_scope_formulario(request, formulario)

    if request.method == "POST":
        # Edición de campos de contacto/apoderado con traza por cambio.
        anteriores = {f: getattr(formulario, f) for f in FormularioRevisionForm.Meta.fields}
        form = FormularioRevisionForm(request.POST, instance=formulario)
        if form.is_valid():
            cambios = []
            for campo in FormularioRevisionForm.Meta.fields:
                nuevo = form.cleaned_data[campo]
                if anteriores[campo] != nuevo:
                    cambios.append((FormularioRevisionForm.LABELS[campo], anteriores[campo], nuevo))
            form.save()
            n = registrar_traza(formulario, request.user, cambios)
            if n:
                messages.success(request, f"Formulario actualizado ({n} cambio(s) registrado(s)).")
            else:
                messages.info(request, "No hubo cambios para guardar.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
    else:
        form = FormularioRevisionForm(instance=formulario)

    globales_list, requisitos_list = _respuestas_resueltas(formulario)
    return render(
        request,
        "programas/becas/revision/formulario_detalle.html",
        {
            "formulario": formulario,
            "relevamiento": formulario.relevamiento,
            "form": form,
            "globales_list": globales_list,
            "requisitos_list": requisitos_list,
            "trazas": formulario.trazas.select_related("editado_por")[:50],
        },
    )


@login_required
@requiere(CAP)
def formulario_aprobar(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk
    )
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        formulario.estado = Formulario.Estado.APROBADO
        formulario.motivo_rechazo = ""
        formulario.save(update_fields=["estado", "motivo_rechazo", "modificado"])
        registrar_traza(formulario, request.user, [("estado", "ENVIADO", "APROBADO")])
        messages.success(request, "Formulario aprobado.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP)
def formulario_rechazar(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"), pk=pk
    )
    _assert_scope_formulario(request, formulario)
    if request.method == "POST":
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Debés indicar el motivo del rechazo.")
            return redirect("becas:formulario_detalle", pk=formulario.pk)
        estado_anterior = formulario.estado
        formulario.estado = Formulario.Estado.RECHAZADO
        formulario.motivo_rechazo = motivo
        formulario.save(update_fields=["estado", "motivo_rechazo", "modificado"])
        registrar_traza(formulario, request.user, [("estado", estado_anterior, f"RECHAZADO: {motivo}")])
        messages.success(request, "Formulario rechazado.")
    return redirect("becas:formulario_detalle", pk=formulario.pk)


@login_required
@requiere(CAP)
def relevamiento_iniciar_revision(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope_relevamiento(request, rel)
    if request.method == "POST" and rel.estado == Relevamiento.Estado.FINALIZADO:
        rel.estado = Relevamiento.Estado.EN_REVISION
        rel.save(update_fields=["estado", "modificado"])
        messages.success(request, "Relevamiento marcado en revisión.")
    return redirect("becas:revision_formularios", relevamiento_pk=rel.pk)


@login_required
@requiere(CAP)
def relevamiento_terminar(request, pk):
    rel = get_object_or_404(Relevamiento.objects.select_related("convocatoria__segmento"), pk=pk)
    _assert_scope_relevamiento(request, rel)
    if request.method == "POST" and rel.estado == Relevamiento.Estado.EN_REVISION:
        pendientes = rel.formularios.filter(estado=Formulario.Estado.ENVIADO).count()
        if pendientes:
            messages.error(request, f"Quedan {pendientes} formulario(s) sin revisar.")
        else:
            rel.estado = Relevamiento.Estado.TERMINADO
            rel.save(update_fields=["estado", "modificado"])
            messages.success(request, "Relevamiento terminado.")
    return redirect("becas:revision_formularios", relevamiento_pk=rel.pk)
