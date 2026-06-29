"""Filtros de template del backoffice de Becas."""
from django import template

register = template.Library()


@register.filter
def iniciales(value):
    """Iniciales de un nombre: 1ª letra del primer y último término (máx 2),
    en mayúscula. "María García" -> "MG"; "Carlos" -> "C"."""
    if not value:
        return ""
    partes = str(value).split()
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0][:1].upper()
    return (partes[0][:1] + partes[-1][:1]).upper()
