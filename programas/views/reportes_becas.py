"""Pantallas y descargas de los reportes transversales de Becas."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.core.paginator import Paginator
from django.views.generic import TemplateView, View

from core.rbac import puede
from programas.services.autorizacion import convocatorias_visibles, programa_becas, segmentos_visibles, usuarios_territoriales_becas
from programas.services.exportacion_reportes import respuesta_reporte
from programas.services.reportes import parsear_periodo
from programas.services.reportes import Reporte
from programas.services import reportes_becas as datasets


REPORTES = {
    "cupos": {"titulo": "Cupos por segmento", "descripcion": "Capacidad, ocupación, disponibilidad y lista de espera.", "funcion": datasets.reporte_cupos},
    "avance": {"titulo": "Avance de convocatorias", "descripcion": "Estados de relevamientos y formularios por convocatoria.", "funcion": datasets.reporte_avance},
    "produccion": {"titulo": "Producción territorial", "descripcion": "Actividad y resultados de cada territorial en un período.", "funcion": datasets.reporte_produccion},
    "embudo": {"titulo": "Embudo de revisión", "descripcion": "Avance por etapa del circuito de validación y aprobación.", "funcion": datasets.reporte_embudo},
    "beneficiarios": {"titulo": "Padrón de beneficiarios", "descripcion": "Personas aprobadas en todas las convocatorias visibles.", "funcion": datasets.reporte_beneficiarios},
}


class ReportesPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not puede(
            request.user, "becas.reportes.ver", programa=programa_becas()
        ):
            raise PermissionDenied("No tiene acceso a los reportes de Becas.")
        return super().dispatch(request, *args, **kwargs)


class ReportesHubView(ReportesPermissionMixin, TemplateView):
    template_name = "programas/becas/reportes/hub.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "reportes": REPORTES.items()}


def _parametros(request, reporte):
    desde, hasta = parsear_periodo(request.GET.get("desde"), request.GET.get("hasta"))
    comunes = {"desde": desde, "hasta": hasta}
    if reporte == "cupos":
        return {"segmento_id": request.GET.get("segmento") or None, "solo_activos": request.GET.get("solo_activos") == "1"}
    if reporte == "avance":
        return {**comunes, "segmento_id": request.GET.get("segmento") or None, "estado": request.GET.get("estado") or None}
    if reporte == "produccion":
        return {**comunes, "segmento_id": request.GET.get("segmento") or None, "territorial_id": request.GET.get("territorial") or None}
    if reporte == "embudo":
        return {**comunes, "convocatoria_id": request.GET.get("convocatoria") or None}
    return {**comunes, "segmento_id": request.GET.get("segmento") or None, "convocatoria_id": request.GET.get("convocatoria") or None}


class ReporteBecasView(ReportesPermissionMixin, TemplateView):
    template_name = "programas/becas/reportes/reporte.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        codigo = self.kwargs["reporte"]
        definicion = REPORTES.get(codigo)
        if not definicion:
            ctx["error"] = "Reporte no válido."
            return ctx
        try:
            reporte = definicion["funcion"](self.request.user, **_parametros(self.request, codigo))
        except ValueError as error:
            reporte, ctx["error"] = None, str(error)
        if codigo == "beneficiarios" and reporte is not None:
            paginator = Paginator(reporte.filas, 25)
            page_obj = paginator.get_page(self.request.GET.get("page"))
            reporte = Reporte(reporte.encabezados, tuple(page_obj.object_list))
            query = self.request.GET.copy()
            query.pop("page", None)
            ctx.update({"page_obj": page_obj, "paginator": paginator, "pagination_query": query.urlencode()})
        ctx.update({
            "codigo": codigo, "definicion": definicion, "reporte": reporte,
            "segmentos": segmentos_visibles(self.request.user),
            "convocatorias": convocatorias_visibles(self.request.user),
            "territoriales": usuarios_territoriales_becas().filter(
                relevamientos_asignados__convocatoria__in=convocatorias_visibles(self.request.user)
            ).distinct(),
            "puede_exportar": puede(self.request.user, "becas.reportes.exportar", programa=programa_becas()),
            "querystring": self.request.GET.urlencode(),
        })
        return ctx


class ReporteBecasExportView(ReportesPermissionMixin, View):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not puede(
            request.user, "becas.reportes.exportar", programa=programa_becas()
        ):
            raise PermissionDenied("No tiene permiso para exportar reportes de Becas.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, reporte, formato):
        definicion = REPORTES.get(reporte)
        if not definicion:
            return HttpResponseBadRequest("Reporte no válido.")
        try:
            resultado = definicion["funcion"](request.user, **_parametros(request, reporte))
        except ValueError as error:
            return HttpResponseBadRequest(str(error))
        return respuesta_reporte(resultado, formato, f"becas_{reporte}")
