"""Descargas CSV/XLSX de los datos visibles en Dispositivos y Merenderos."""

import csv

from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.dateparse import parse_date
from django.views import View
from openpyxl import Workbook

from programas.models import Merendero
from programas.services.dispositivos import dispositivos_visibles
from programas.services.reportes import (
    filtrar_dispositivos,
    movimientos_dispositivos,
    ocupacion_dispositivos,
    padron_dispositivos,
    padron_merenderos_con_entregas,
)
from programas.views.dispositivos_legajo import DispositivoProgramaPermissionMixin
from programas.views.merenderos import MerenderosPermissionMixin


def _periodo(request):
    desde = _fecha(request.GET.get("desde"), "desde")
    hasta = _fecha(request.GET.get("hasta"), "hasta")
    if desde and hasta and desde > hasta:
        raise ValueError("La fecha desde no puede ser posterior a la fecha hasta.")
    return desde, hasta


def _fecha(valor, nombre):
    if not valor:
        return None
    fecha = parse_date(valor)
    if fecha is None:
        raise ValueError(f"La fecha {nombre} no es válida.")
    return fecha


def _celda_segura(valor):
    if isinstance(valor, str) and valor.startswith(("=", "+", "-", "@")):
        return f"'{valor}"
    return valor


def _respuesta(reporte, formato, nombre):
    filas = ([_celda_segura(valor) for valor in fila] for fila in reporte.filas)
    if formato == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(reporte.encabezados)
        writer.writerows(filas)
        return response
    if formato == "xlsx":
        libro = Workbook(write_only=True)
        hoja = libro.create_sheet("Reporte")
        hoja.append(list(reporte.encabezados))
        for fila in filas:
            hoja.append(fila)
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
        libro.save(response)
        return response
    return HttpResponseBadRequest("Formato de exportación no válido.")


class DispositivoExportView(DispositivoProgramaPermissionMixin, View):
    capacidad_requerida = "dispositivo.ver"

    def get(self, request, reporte, formato):
        try:
            desde, hasta = _periodo(request)
        except ValueError as error:
            return HttpResponseBadRequest(str(error))

        dispositivos = filtrar_dispositivos(
            dispositivos_visibles(request.user),
            tipo=request.GET.get("tipo"),
            estado=request.GET.get("estado"),
            localidad=request.GET.get("localidad", "").strip(),
        )
        if reporte == "padron":
            return _respuesta(padron_dispositivos(dispositivos), formato, "padron_dispositivos")
        if reporte == "ocupacion":
            return _respuesta(ocupacion_dispositivos(dispositivos), formato, "ocupacion_dispositivos")
        if reporte == "movimientos":
            return _respuesta(
                movimientos_dispositivos(dispositivos, desde=desde, hasta=hasta),
                formato,
                "movimientos_dispositivos",
            )
        return HttpResponseBadRequest("Reporte no válido.")


class MerenderoExportView(MerenderosPermissionMixin, View):
    capacidad_requerida = "merendero.ver"

    def get(self, request, formato):
        try:
            desde, hasta = _periodo(request)
        except ValueError as error:
            return HttpResponseBadRequest(str(error))

        merenderos = Merendero.objects.all()
        estado = request.GET.get("estado")
        termino = request.GET.get("q", "").strip()
        if estado:
            merenderos = merenderos.filter(estado=estado)
        if termino:
            merenderos = merenderos.filter(nombre__icontains=termino)
        return _respuesta(
            padron_merenderos_con_entregas(merenderos, desde=desde, hasta=hasta),
            formato,
            "padron_merenderos",
        )
