"""Autorización de la configuración del Programa Dispositivos."""

from django.core.cache import cache

from core import rbac

PROGRAMA_DISPOSITIVOS_CODIGO = "DISPOSITIVOS"
CAP_CONFIGURAR = "programa.configurar"
_CACHE_KEY = "programas:dispositivos"


def programa_dispositivos():
    from programas.models import Programa

    programa = cache.get(_CACHE_KEY)
    if programa is None:
        programa = Programa.objects.filter(codigo=PROGRAMA_DISPOSITIVOS_CODIGO).first()
        if programa is not None:
            cache.set(_CACHE_KEY, programa, 300)
    return programa


def puede_configurar_dispositivos(user):
    """Exige la capacidad existente con alcance sobre DISPOSITIVOS."""

    programa = programa_dispositivos()
    return programa is not None and rbac.puede(user, CAP_CONFIGURAR, programa=programa)
