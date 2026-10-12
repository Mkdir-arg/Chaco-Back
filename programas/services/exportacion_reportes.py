"""Exportación común de datasets tabulares a CSV y XLSX."""

import csv

from asgiref.sync import sync_to_async
from django.core.handlers.asgi import ASGIRequest
from django.http import HttpResponse, HttpResponseBadRequest, StreamingHttpResponse
from openpyxl import Workbook

# `celda_segura` es transversal (la usan también los CSV de `legajos`, que no exportan
# nada de Becas) y vive en `core.exportacion`. Se re-exporta acá porque la usan las dos
# funciones de abajo y porque la importan por este camino las vistas y los tests de
# `programas`.
from core.exportacion import celda_segura

#: Lo que se acumula antes de mandar un trozo del CSV al cliente. Fila por fila son
#: decenas de miles de escrituras por archivo —y bajo ASGI, decenas de miles de saltos
#: de hilo—; 64 KB son ~120 trozos para el CSV de 20.000 casos.
TROZO_CSV = 64 * 1024

__all__ = [
    "celda_segura",
    "respuesta_csv_en_streaming",
    "respuesta_libro",
    "respuesta_reporte",
]


def _nombre_hoja(nombre):
    """Excel limita el nombre de hoja a 31 caracteres y prohíbe ``[]:*?/\\``."""

    limpio = "".join("_" if c in "[]:*?/\\" else c for c in nombre).strip() or "Hoja"

    return limpio[:31]


def respuesta_libro(hojas, nombre, alcance=""):
    """XLSX de varias hojas: ``hojas`` es una lista de ``(nombre_hoja, Reporte)``.



    Cada hoja arranca con el alcance aplicado (RN-16 del análisis #366) para que un

    archivo descargado sea reconstruible, una fila en blanco, y después el reporte.

    Complementa a :func:`respuesta_reporte`, que sigue sirviendo a una hoja sola.

    """

    libro = Workbook(write_only=True)

    for nombre_hoja, reporte in hojas:
        hoja = libro.create_sheet(_nombre_hoja(nombre_hoja))

        if alcance:
            hoja.append([celda_segura(f"Alcance: {alcance}")])

            hoja.append([])

        # SEC-20: los encabezados no son fijos —en «respuestas por persona» son los
        # textos de las preguntas, que los carga un operador—, así que pasan por el
        # mismo saneo que las celdas.
        hoja.append([celda_segura(valor) for valor in reporte.encabezados])

        for fila in reporte.filas:
            hoja.append([celda_segura(valor) for valor in fila])

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    response["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'

    libro.save(response)

    return response


class _Eco:
    """Un «archivo» que no guarda nada: devuelve lo que le escriben.

    Es el adaptador que deja usar ``csv.writer`` dentro de un generador: cada
    ``writerow`` devuelve la línea ya armada en vez de acumularla en un buffer.
    """

    def write(self, valor):
        return valor


def _trozos_del_csv(reporte, alcance):
    """El mismo CSV que arma :func:`respuesta_reporte`, en trozos de ``TROZO_CSV``."""
    eco = _Eco()
    escritor = csv.writer(eco)
    # El BOM va primero y solo una vez, igual que el `response.write(BOM)` de
    # `respuesta_reporte`: es lo que hace que Excel abra el archivo en UTF-8.
    pendiente = ["\ufeff"]
    largo = 1
    if alcance:
        pendiente.append(escritor.writerow([celda_segura(f"Alcance: {alcance}")]))
        pendiente.append(escritor.writerow([]))
    pendiente.append(escritor.writerow([celda_segura(valor) for valor in reporte.encabezados]))
    for fila in reporte.filas:
        linea = escritor.writerow([celda_segura(valor) for valor in fila])
        pendiente.append(linea)
        largo += len(linea)
        if largo >= TROZO_CSV:
            yield "".join(pendiente)
            pendiente, largo = [], 0
    if pendiente:
        yield "".join(pendiente)


def _como_asincrono(iterable):
    """El mismo generador, visto como iterador asincrónico.

    Bajo ASGI (daphne), ``StreamingHttpResponse`` con un iterador **sincrónico** no
    transmite nada: Django lo consume entero con ``sync_to_async(list)`` y recién
    después manda el cuerpo (``django/http/response.py``), que es justo lo que este
    export quiere evitar. Cada ``next`` va a un hilo con ``thread_sensitive=True``, el
    mismo en el que corrió la vista, así que las consultas de cada lote se hacen donde
    la conexión a la base ya está.
    """
    fin = object()

    async def agenerador():
        iterador = iter(iterable)
        siguiente = sync_to_async(lambda: next(iterador, fin))
        while True:
            trozo = await siguiente()
            if trozo is fin:
                return
            yield trozo

    return agenerador()


def respuesta_csv_en_streaming(request, reporte, nombre, alcance=""):
    """El CSV de ``reporte``, **byte por byte el mismo** que :func:`respuesta_reporte`,
    pero servido con ``StreamingHttpResponse``.

    Existe para los exports grandes (PERF-03 punto 3): las filas se escriben a medida que
    se arman, así que el archivo empieza a salir sin esperar a la última y ni el servicio
    ni la respuesta tienen la convocatoria entera en memoria. ``reporte.filas`` puede ser
    cualquier iterable —un :class:`~programas.services.reportes.ReportePerezoso` por
    lotes— y se recorre **una sola vez**.
    """
    trozos = _trozos_del_csv(reporte, alcance)
    contenido = _como_asincrono(trozos) if isinstance(request, ASGIRequest) else trozos
    response = StreamingHttpResponse(contenido, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
    return response


def respuesta_reporte(reporte, formato, nombre, alcance=""):

    filas = ([celda_segura(valor) for valor in fila] for fila in reporte.filas)

    if formato == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8")

        response["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'

        response.write("\ufeff")

        writer = csv.writer(response)

        if alcance:
            writer.writerow([celda_segura(f"Alcance: {alcance}")])

            writer.writerow([])

        writer.writerow([celda_segura(valor) for valor in reporte.encabezados])

        writer.writerows(filas)

        return response

    if formato == "xlsx":
        libro = Workbook(write_only=True)

        hoja = libro.create_sheet("Reporte")

        if alcance:
            hoja.append([celda_segura(f"Alcance: {alcance}")])

            hoja.append([])

        hoja.append([celda_segura(valor) for valor in reporte.encabezados])

        for fila in filas:
            hoja.append(fila)

        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        response["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'

        libro.save(response)

        return response

    return HttpResponseBadRequest("Formato de exportación no válido.")
