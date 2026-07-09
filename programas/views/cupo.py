"""Backoffice — Gestión de cupo y lista de espera por segmento (issue #78, RN-04/05).

Acceso de lectura: ``becas.cupo.ver`` o ``becas.beneficiario.ver`` (Admin del
programa, o Coordinador con asignación activa en el segmento). Acciones de
mutación (baja, promoción, agregar a lista de espera): ``becas.beneficiario.editar``,
también scoped al segmento.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic.detail import DetailView

from core.rbac import CapacidadRequeridaMixin, puede_alguna
from programas.models import Formulario, ListaEspera, Segmento
from programas.services.autorizacion import SegmentoScopedMixin, puede_gestionar_segmento
from programas.services.cupo import (
    agregar_a_lista_espera,
    dar_baja_beneficiario,
    get_cupo_stats,
    promover_lista_espera,
)

CAP_CUPO_VER = "becas.cupo.ver"
CAP_BENEFICIARIO_VER = "becas.beneficiario.ver"
CAP_BENEFICIARIO_EDITAR = "becas.beneficiario.editar"


class CupoSegmentoDetailView(SegmentoScopedMixin, CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    """Vista principal de cupo: stat cards + Beneficiarios / Lista de espera / Pendientes."""

    model = Segmento
    capacidades_requeridas = [CAP_CUPO_VER, CAP_BENEFICIARIO_VER]
    template_name = "programas/becas/cupo/segmento_detail.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        self.assert_puede_gestionar_segmento(obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        segmento = self.object

        stats = get_cupo_stats(segmento)

        beneficiarios = (
            Formulario.objects.filter(
                estado=Formulario.Estado.APROBADO,
                ciudadano__isnull=False,
                relevamiento__convocatoria__segmento=segmento,
            )
            .select_related("ciudadano", "relevamiento__convocatoria")
            .order_by("modificado")
        )

        lista_espera = (
            ListaEspera.objects.filter(segmento=segmento, promovido=False)
            .select_related("formulario__ciudadano", "formulario__relevamiento__convocatoria")
            .order_by("posicion")
        )

        # Formularios ENVIADOS del segmento que aún no están en lista de espera
        formularios_en_espera_ids = ListaEspera.objects.filter(segmento=segmento, promovido=False).values_list(
            "formulario_id", flat=True
        )
        pendientes = (
            Formulario.objects.filter(
                estado=Formulario.Estado.ENVIADO,
                ciudadano__isnull=False,
                relevamiento__convocatoria__segmento=segmento,
            )
            .exclude(pk__in=formularios_en_espera_ids)
            .select_related("ciudadano", "relevamiento__convocatoria")
            .order_by("creado")
        )

        ctx.update(
            {
                "stats": stats,
                "beneficiarios": beneficiarios,
                "lista_espera": lista_espera,
                "pendientes": pendientes,
                "puede_editar_beneficiarios": puede_alguna(self.request.user, [CAP_BENEFICIARIO_EDITAR]),
            }
        )
        return ctx


@login_required
def dar_baja_beneficiario_view(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"),
        pk=pk,
    )
    segmento = formulario.relevamiento.convocatoria.segmento
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR]) or not puede_gestionar_segmento(
        request.user, segmento
    ):
        raise PermissionDenied
    if request.method == "POST":
        try:
            dar_baja_beneficiario(formulario, request.user)
            messages.warning(
                request,
                f"Se liberó 1 cupo en {segmento.nombre}. ¿Promover desde lista de espera?",
            )
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": segmento.pk}) + "?tab=beneficiarios")


@login_required
def promover_lista_espera_view(request, pk):
    lista = get_object_or_404(
        ListaEspera.objects.select_related("formulario__ciudadano", "segmento"),
        pk=pk,
    )
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR]) or not puede_gestionar_segmento(
        request.user, lista.segmento
    ):
        raise PermissionDenied
    if request.method == "POST":
        try:
            promover_lista_espera(lista, request.user)
            nombre = lista.formulario.ciudadano.nombre_completo if lista.formulario.ciudadano else "el ciudadano"
            messages.success(request, f"{nombre} fue promovido como beneficiario.")
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": lista.segmento.pk}) + "?tab=lista_espera")


@login_required
def agregar_lista_espera_view(request, pk):
    formulario = get_object_or_404(
        Formulario.objects.select_related("relevamiento__convocatoria__segmento"),
        pk=pk,
    )
    segmento = formulario.relevamiento.convocatoria.segmento
    if not puede_alguna(request.user, [CAP_BENEFICIARIO_EDITAR]) or not puede_gestionar_segmento(
        request.user, segmento
    ):
        raise PermissionDenied
    if request.method == "POST":
        try:
            agregar_a_lista_espera(formulario, segmento, request.user)
            messages.success(request, "Formulario agregado a la lista de espera.")
        except ValidationError as e:
            messages.error(request, e.message)
    return redirect(reverse("becas:cupo_segmento", kwargs={"pk": segmento.pk}) + "?tab=lista_espera")
