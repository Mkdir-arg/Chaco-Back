"""Planillas de la campaña: la plantilla vacía (RF-007-17) y el resultado por destinatario (RF-007-16)."""

from __future__ import annotations

from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook

from core.exportacion import celda_segura
from notificaciones.models import Destinatario

ENCABEZADO_PLANTILLA = "email"
EJEMPLOS_PLANTILLA = ("persona@ejemplo.com", "otra.persona@ejemplo.com.ar")


def _a_bytes(libro):
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def plantilla_xlsx():
    """Una hoja con el encabezado ``email`` y dos filas de ejemplo para reemplazar."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Destinatarios"
    hoja.append([ENCABEZADO_PLANTILLA])
    for ejemplo in EJEMPLOS_PLANTILLA:
        hoja.append([ejemplo])
    hoja.column_dimensions["A"].width = 40
    return _a_bytes(libro)


def resultado_xlsx(campana):
    """Los destinatarios con su estado, fecha de envío y error, y las filas descartadas.

    Antes de enviar sirve como «lista a enviar» (todo pendiente); después, como resultado.
    Cada celda pasa por ``celda_segura``: el valor descartado es texto libre del Excel
    original y un ``=…`` se abriría como fórmula (RED-70, SEC-20).
    """
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Destinatarios"
    hoja.append(["Correo", "Fila del Excel", "Estado", "Enviado", "Detalle"])
    destinatarios = (
        Destinatario.objects.filter(campana=campana)
        .order_by("fila_excel", "pk")
        .values_list("email", "fila_excel", "estado", "enviado_en", "error")
    )
    etiquetas = dict(Destinatario.Estado.choices)
    for email, fila, estado, enviado_en, error in destinatarios.iterator(chunk_size=1000):
        enviado = timezone.localtime(enviado_en).strftime("%d/%m/%Y %H:%M") if enviado_en else ""
        hoja.append([celda_segura(email), fila, etiquetas.get(estado, estado), enviado, celda_segura(error)])
    hoja.column_dimensions["A"].width = 40
    hoja.column_dimensions["E"].width = 60

    descartes = libro.create_sheet("Descartados")
    descartes.append(["Fila del Excel", "Valor leído", "Motivo"])
    for descartado in campana.descartados.order_by("fila_excel", "pk").iterator(chunk_size=1000):
        descartes.append([descartado.fila_excel, celda_segura(descartado.valor), descartado.get_motivo_display()])
    descartes.column_dimensions["B"].width = 40
    return _a_bytes(libro)
