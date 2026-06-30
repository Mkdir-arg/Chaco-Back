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


@register.simple_tag(name="puede_en")
def puede_en(user, codigo, programa=None):
    """Variante con alcance de Programa del filtro :func:`puede`.

    Uso en template::

        {% puede_en request.user "relevamiento.gestionar" programa=obj.programa as ok %}
        {% if ok %} ... {% endif %}

    Con ``programa`` nulo equivale a ``request.user|puede:codigo``.
    """
    try:
        return rbac.puede(user, codigo, programa=programa)
    except Exception:
        return False


@register.filter(name="es_ciudadano_portal")
def es_ciudadano_portal(user):
    """¿El usuario es un ciudadano del portal? (marcador de identidad)."""
    try:
        return rbac.es_ciudadano_portal(user)
    except Exception:
        return False
