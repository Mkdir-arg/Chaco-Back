"""Context processors de core.

`sidebar_badges` expone los contadores que se muestran como badge en los
ítems del sidebar (visible en todo el backoffice). Cada contador está
gateado por permiso y es tolerante a fallos (si algo no está disponible,
no rompe el render: simplemente no muestra el badge).
"""
from core import rbac


def sidebar_badges(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    badges = {}

    # Conversaciones sin asignar (pendientes y sin operador)
    if rbac.puede(user, "conversacion.operar"):
        try:
            from conversaciones.models import Conversacion

            badges["badge_conversaciones"] = Conversacion.objects.filter(
                estado="pendiente", operador_asignado__isnull=True
            ).count()
        except Exception:
            badges["badge_conversaciones"] = 0

    return badges
