"""Descargas CSV/XLSX de los datos visibles en Dispositivos y Merenderos."""

from django.http import HttpResponseBadRequest
from django.views import View

from programas.models import Merendero
from programas.services.dispositivos import dispositivos_visibles
from programas.services.exportacion_reportes import respuesta_reporte
from programas.services.reportes import (
    filtrar_dispositivos,
    filtrar_merenderos,
    padron_dispositivos,
    padron_merenderos_con_entregas,
    parsear_periodo,
)
from programas.views.dispositivos_legajo import DispositivoProgramaPermissionMixin
from programas.views.merenderos import MerenderosPermissionMixin


def _periodo(request):
    return parsear_periodo(request.GET.get("desde"), request.GET.get("hasta"))


def _respuesta(reporte, formato, nombre):
    return respuesta_reporte(reporte, formato, nombre)


class DispositivoExportView(DispositivoProgramaPermissionMixin, View):
    """Padrón de dispositivos.

    Los reportes de **ocupación** y **movimientos** se fueron con `Cama` y
    `Admision`: los repone el MVP v2 sobre `Plaza` y `Estadia`. Con ellos se fue
    también el filtro por período, que acotaba por fecha de ingreso o de egreso de
    una estadía; el padrón se sigue filtrando por tipo, estado y localidad.
    """

    capacidad_requerida = "dispositivo.ver"

    def get(self, request, reporte, formato):
        dispositivos = filtrar_dispositivos(
            dispositivos_visibles(request.user),
            tipo=request.GET.get("tipo"),
            estado=request.GET.get("estado"),
            localidad=request.GET.get("localidad", "").strip(),
        )
        if reporte == "padron":
            return _respuesta(padron_dispositivos(dispositivos), formato, "padron_dispositivos")
        return HttpResponseBadRequest("Reporte no válido.")


class MerenderoExportView(MerenderosPermissionMixin, View):
    capacidad_requerida = "merendero.ver"

    def get(self, request, formato):
        try:
            desde, hasta = _periodo(request)
        except ValueError as error:
            return HttpResponseBadRequest(str(error))

        merenderos = filtrar_merenderos(
            Merendero.objects.all(),
            estado=request.GET.get("estado"),
            termino=request.GET.get("q", "").strip(),
            desde=desde,
            hasta=hasta,
        )
        return _respuesta(
            padron_merenderos_con_entregas(merenderos, desde=desde, hasta=hasta),
            formato,
            "padron_merenderos",
        )
