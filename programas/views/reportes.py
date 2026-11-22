"""Descargas CSV/XLSX de los datos visibles en Dispositivos."""

from django.http import HttpResponseBadRequest
from django.views import View

from programas.services.dispositivos import dispositivos_visibles, localidades_visibles
from programas.services.exportacion_reportes import respuesta_reporte
from programas.services.reportes import (
    filtrar_dispositivos,
    padron_dispositivos,
)
from programas.views.dispositivos_legajo import DispositivoProgramaPermissionMixin


def _respuesta(reporte, formato, nombre):
    return respuesta_reporte(reporte, formato, nombre)


class DispositivoExportView(DispositivoProgramaPermissionMixin, View):
    """Padrón de dispositivos.

    Los reportes de **ocupación** y **movimientos** se fueron con el circuito operativo
    de la versión 1: los repone el MVP v2 sobre `Plaza` y `Estadia`. Con ellos se fue
    también el filtro por período, que acotaba por fecha de ingreso o de egreso de
    una estadía; el padrón se sigue filtrando por tipo, estado y localidad.
    """

    capacidad_requerida = "dispositivo.ver"

    def get(self, request, reporte, formato):
        # `localidades_visibles` suma 1 consulta a la exportación (las localidades que el select ofrece):
        # es el precio de que listado y exportación apliquen la misma regla de localidad.
        dispositivos = filtrar_dispositivos(
            dispositivos_visibles(request.user),
            tipo=request.GET.get("tipo"),
            estado=request.GET.get("estado"),
            localidad=request.GET.get("localidad", "").strip(),
            q=request.GET.get("q", "").strip(),
            localidades_ofrecidas=localidades_visibles(request.user),
        )
        if reporte == "padron":
            return _respuesta(padron_dispositivos(dispositivos), formato, "padron_dispositivos")
        return HttpResponseBadRequest("Reporte no válido.")
