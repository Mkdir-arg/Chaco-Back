from django.core.exceptions import ObjectDoesNotExist


def etiqueta_usuario(user):
    """Etiqueta consistente para usuarios en selectores del backoffice."""
    nombre = user.get_full_name().strip() or user.username
    try:
        dni = user.profile.dni
    except ObjectDoesNotExist:
        dni = None
    return f"{nombre} ({dni})" if dni else nombre
