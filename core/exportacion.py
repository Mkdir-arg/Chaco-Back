"""Saneo de celdas para cualquier exportación tabular (CSV y XLSX).

``celda_segura`` vivía en ``programas/services/exportacion_reportes.py`` y la
importaban dos vistas de ``legajos`` —el padrón de ciudadanos y el CSV de reportes
del legajo— que no exportan nada de Becas: el único motivo de esa dependencia era
esta función. Neutralizar fórmulas y caracteres de control antes de escribir un
archivo que alguien abre en Excel es una regla transversal, así que vive acá;
``programas.services.exportacion_reportes`` la re-exporta para sus llamadores.
"""

from datetime import datetime

from django.utils import timezone
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE


def celda_segura(valor):
    """El valor listo para escribirse en una celda de CSV o XLSX (RED-70, SEC-20).

    Hace dos cosas, en este orden:

    1. Le saca el huso a los ``datetime`` con zona: ``openpyxl`` no escribe fechas
       *aware* y la planilla se lee siempre en hora local.
    2. Sobre los textos, borra los caracteres de control que ``openpyxl`` rechaza
       con ``IllegalCharacterError`` —un texto pegado desde otro programa no puede
       tirar la planilla— y recién después prefija con una comilla simple lo que
       Excel interpretaría como fórmula (``=``, ``+``, ``-``, ``@``). El orden
       importa: un ``\\x0b=1+1`` sin limpiar no arranca con ``=`` y se escaparía.
    """
    if isinstance(valor, datetime) and timezone.is_aware(valor):
        return timezone.localtime(valor).replace(tzinfo=None)

    if isinstance(valor, str):
        valor = ILLEGAL_CHARACTERS_RE.sub("", valor)
        if valor.lstrip().startswith(("=", "+", "-", "@")):
            return f"'{valor}"

    return valor
