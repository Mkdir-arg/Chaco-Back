"""Template tags del motor de capacidades (RBAC).

Reemplazan al filtro ``has_group`` (por nombre de grupo). Uso en templates::

    {% load rbac %}
    {% if request.user|puede:"ciudadano.ver" %} ... {% endif %}
"""
from django import template

from core import rbac

register = template.Library()


@register.filter(name="puede")
def puede(user, codigo):
    """¿El usuario tiene la capacidad ``codigo``? (p. ej. ``"ciudadano.ver"``)."""
    try:
        return rbac.puede(user, codigo)
    except Exception:
        return False


@register.filter(name="es_ciudadano_portal")
def es_ciudadano_portal(user):
    """¿El usuario es un ciudadano del portal? (marcador de identidad)."""
    try:
        return rbac.es_ciudadano_portal(user)
    except Exception:
        return False
