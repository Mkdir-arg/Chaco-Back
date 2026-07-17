"""Context processors de core.

`sidebar_badges` expone los contadores que se muestran como badge en los
ítems del sidebar (visible en todo el backoffice). Cada contador está
gateado por permiso y es tolerante a fallos (si algo no está disponible,
no rompe el render: simplemente no muestra el badge).
"""

from django.conf import settings
from django.core.cache import cache

from core import rbac


def session_idle_config(request):
    """Expone la config de idle-logout a todos los templates.

    Los valores vienen de settings (a su vez de variables de entorno), así el
    frontend arma `window.idleLogoutConfig` sin hardcodear tiempos.
    """
    return {
        "session_idle_timeout_minutes": settings.SESSION_IDLE_TIMEOUT_MINUTES,
        "session_idle_warning_seconds": settings.SESSION_IDLE_WARNING_SECONDS,
    }


def sidebar_badges(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {}

    badges = {}

    # Conversaciones sin asignar (pendientes y sin operador)
    if rbac.puede(user, "conversacion.operar"):
        try:
            from conversaciones.models import Conversacion

            # Corre en todos los requests del backoffice: cache corto compartido.
            badges["badge_conversaciones"] = cache.get_or_set(
                "sidebar:conversaciones_pendientes",
                lambda: Conversacion.objects.filter(estado="pendiente", operador_asignado__isnull=True).count(),
                30,
            )
        except Exception:
            badges["badge_conversaciones"] = 0

    return badges
