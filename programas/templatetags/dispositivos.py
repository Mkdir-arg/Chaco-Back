from django import template

from programas.services.dispositivos import (
    puede_configurar_dispositivos,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
)

register = template.Library()


@register.simple_tag(name="puede_configurar_dispositivos")
def puede_configurar_dispositivos_tag(user):
    return puede_configurar_dispositivos(user)


@register.simple_tag(name="puede_en_programa_dispositivos")
def puede_en_programa_dispositivos_tag(user, capacidad):
    return puede_en_programa_dispositivos(user, capacidad)


@register.simple_tag(name="puede_operar_dispositivo")
def puede_operar_dispositivo_tag(user, dispositivo, capacidad):
    return puede_operar_dispositivo(user, dispositivo, capacidad)
