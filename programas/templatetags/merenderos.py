from django import template

register = template.Library()


@register.simple_tag
def racion(valores, dia, servicio):
    return valores.get((dia, servicio), 0)


@register.filter
def observacion(observaciones, dia):
    return observaciones.get(str(dia), "")


@register.filter
def total(totales, dia):
    return totales.get(dia, 0)
