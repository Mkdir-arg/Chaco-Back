"""Exportación común de datasets tabulares a CSV y XLSX."""

import csv

from django.http import HttpResponse, HttpResponseBadRequest
from openpyxl import Workbook


def celda_segura(valor):
    if isinstance(valor, str) and valor.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{valor}"
    return valor


def respuesta_reporte(reporte, formato, nombre):
    filas = ([celda_segura(valor) for valor in fila] for fila in reporte.filas)
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
