"""Context processors de core.

`sidebar_badges` expone los contadores que se muestran como badge en los
ítems del sidebar (visible en todo el backoffice). Cada contador está
gateado por permiso y es tolerante a fallos (si algo no está disponible,
no rompe el render: simplemente no muestra el badge).
"""

import logging

from django.conf import settings

from core import rbac

logger = logging.getLogger(__name__)


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
            from conversaciones.selectors import get_conversaciones_pendientes_count

            # Corre en todos los requests del backoffice: cache corto por usuario,
            # reutilizado también por la vista de inicio.
            badges["badge_conversaciones"] = get_conversaciones_pendientes_count(user)
        except Exception:
            # RED-55: sigue degradando a 0 —esto corre en el 100 % del tráfico
            # autenticado y hacerlo explotar voltearía el backoffice entero—, pero
            # deja el traceback. Antes, un `OperationalError` de MariaDB por el
            # `read_timeout` de 10 s se veía como «no hay conversaciones pendientes».
            logger.exception("sidebar_badges: no se pudo contar las conversaciones pendientes")
            badges["badge_conversaciones"] = 0

    return badges
