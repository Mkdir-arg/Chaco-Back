"""Pantallas y descargas de los reportes transversales de Becas."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponseBadRequest
from django.views.generic import TemplateView, View

from core.rbac import puede
from programas.forms_reportes import ReporteBecasFiltroForm
from programas.services import reportes_becas as datasets
from programas.services.autorizacion import (
    programa_becas,
)
from programas.services.exportacion_reportes import respuesta_reporte

REPORTES = {
    "cupos": {
        "titulo": "Cupos por segmento",
        "descripcion": "Capacidad, ocupación, disponibilidad y lista de espera.",
        "funcion": datasets.reporte_cupos,
    },
    "avance": {
        "titulo": "Avance de convocatorias",
        "descripcion": "Estados de relevamientos y formularios por convocatoria.",
        "funcion": datasets.reporte_avance,
    },
    "produccion": {
        "titulo": "Producción territorial",
        "descripcion": "Actividad y resultados de cada territorial en un período.",
        "funcion": datasets.reporte_produccion,
    },
    "embudo": {
        "titulo": "Embudo de revisión",
        "descripcion": "Avance por etapa del circuito de validación y aprobación.",
        "funcion": datasets.reporte_embudo,
    },
    "beneficiarios": {
        "titulo": "Padrón de beneficiarios",
        "descripcion": "Personas aprobadas en todas las convocatorias visibles.",
        "funcion": datasets.reporte_beneficiarios,
    },
}


class ReportesPermissionMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not puede(request.user, "becas.reportes.ver", programa=programa_becas()):
            raise PermissionDenied("No tiene acceso a los reportes de Becas.")
        return super().dispatch(request, *args, **kwargs)


class ReportesHubView(ReportesPermissionMixin, TemplateView):
    template_name = "programas/becas/reportes/hub.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "reportes": REPORTES.items()}


def _filtros(request, codigo):
    form = ReporteBecasFiltroForm(request.GET, user=request.user)
    if not form.is_valid():
        raise ValueError(" ".join(form.non_field_errors() or ["Revisá los filtros ingresados."]))
    return form, form.parametros(codigo)


class ReporteBecasView(ReportesPermissionMixin, TemplateView):
    template_name = "programas/becas/reportes/reporte.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["error"] = ""
        ctx["page_obj"] = None
        ctx["paginator"] = None
        codigo = self.kwargs["reporte"]
        definicion = REPORTES.get(codigo)
        if not definicion:
            ctx["error"] = "Reporte no válido."
            return ctx
        try:
            form, parametros = _filtros(self.request, codigo)
            if codigo == "beneficiarios":
                queryset = datasets.beneficiarios_queryset(self.request.user, **parametros)
                paginator = Paginator(queryset, 25)
                page_obj = paginator.get_page(self.request.GET.get("page"))
                reporte = datasets.reporte_beneficiarios_desde_queryset(page_obj.object_list)
                query = self.request.GET.copy()
                query.pop("page", None)
                ctx.update({"page_obj": page_obj, "paginator": paginator, "pagination_query": query.urlencode()})
            else:
                reporte = definicion["funcion"](self.request.user, **parametros)
        except ValueError as error:
            form = ReporteBecasFiltroForm(self.request.GET, user=self.request.user)
            reporte, ctx["error"] = None, str(error)
        ctx.update(
            {
                "codigo": codigo,
                "definicion": definicion,
                "reporte": reporte,
                "filtros_form": form,
                "segmentos": form.fields["segmento"].queryset,
                "convocatorias": form.fields["convocatoria"].queryset,
                "territoriales": form.fields["territorial"].queryset,
                "puede_exportar": puede(self.request.user, "becas.reportes.exportar", programa=programa_becas()),
                "querystring": self.request.GET.urlencode(),
                "filtro_segmento": self.request.GET.get("segmento", ""),
                "filtro_desde": self.request.GET.get("desde", ""),
                "filtro_hasta": self.request.GET.get("hasta", ""),
                "filtro_estado": self.request.GET.get("estado", ""),
                "filtro_territorial": self.request.GET.get("territorial", ""),
                "filtro_convocatoria": self.request.GET.get("convocatoria", ""),
                "filtro_solo_activos": self.request.GET.get("solo_activos", ""),
                "advanced": False,
                "allow_or": False,
                "reset_url": self.request.path,
            }
        )
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
            _, parametros = _filtros(request, reporte)
            resultado = definicion["funcion"](request.user, **parametros)
        except ValueError as error:
            return HttpResponseBadRequest(str(error))
        return respuesta_reporte(resultado, formato, f"becas_{reporte}")
