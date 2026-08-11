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


def _alguna(user, codigos):
    return any(puede(user, codigo) for codigo in codigos)


@register.filter(name="puede_abm_usuarios")
def puede_abm_usuarios(user):
    """¿Le abre la puerta del ABM de Usuarios?

    Deriva de :data:`core.rbac.CAPS_ENTRADA_ABM_USUARIOS`, la misma constante que
    usa la vista, para que el menú y la vista no puedan quedar desalineados (ver
    una entrada y comerse un 403, o al revés). No enumerar capacidades acá.
    """
    return _alguna(user, rbac.CAPS_ENTRADA_ABM_USUARIOS)


@register.filter(name="puede_abm_roles")
def puede_abm_roles(user):
    """¿Le abre la puerta del ABM de Roles? (deriva de ``CAPS_ENTRADA_ABM_ROLES``)."""
    return _alguna(user, rbac.CAPS_ENTRADA_ABM_ROLES)


@register.filter(name="es_ciudadano_portal")
def es_ciudadano_portal(user):
    """¿El usuario es un ciudadano del portal? (marcador de identidad)."""
    try:
        return rbac.es_ciudadano_portal(user)
    except Exception:
        return False
