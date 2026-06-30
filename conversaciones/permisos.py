"""Helpers de autorización de conversaciones, sobre el motor RBAC por capacidades.

- ``puede_operar``: acceso a la bandeja de conversaciones (capacidad ``conversacion.operar``).
- ``ve_todas_las_conversaciones``: supervisor/superusuario ve toda la cola.
- ``es_operador_restringido``: operador básico, ve solo sus conversaciones asignadas.
"""

from core import rbac


def puede_operar(user):
    return rbac.puede(user, "conversacion.operar")


def ve_todas_las_conversaciones(user):
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return user.is_superuser or rbac.puede(user, "conversacion.configurar") or rbac.puede(user, "conversacion.metricas")


def es_operador_restringido(user):
    """Operador que solo ve sus conversaciones asignadas (no supervisor)."""
    return puede_operar(user) and not ve_todas_las_conversaciones(user)
