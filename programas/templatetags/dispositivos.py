from django import template

from programas.services.dispositivos import puede_configurar_dispositivos

register = template.Library()


@register.simple_tag(name="puede_configurar_dispositivos")
def puede_configurar_dispositivos_tag(user):
    return puede_configurar_dispositivos(user)
