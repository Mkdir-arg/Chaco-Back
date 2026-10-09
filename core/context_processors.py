"""Context processors de core.

`identidad_usuario` publica al shell del backoffice quién es el usuario (sus
roles, si es superusuario) y las dos perillas que el shell consulta para decidir
qué JavaScript cargar. Vivía en `conversaciones.context_processors.user_groups`
(RED-13): cuatro de sus variables no eran de esa app y las usa `includes/base.html`,
que extiende **todo** el backoffice, así que apagar `conversaciones` sin moverlo
dejaba `window.isSuperuser` en `false` y los websockets apagados sin un solo error
a la vista.

`sidebar_badges` expone los contadores que se muestran como badge en los
ítems del sidebar (visible en todo el backoffice). Cada contador está
gateado por permiso y es tolerante a fallos (si algo no está disponible,
no rompe el render: simplemente no muestra el badge).
"""

import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Prefetch, prefetch_related_objects
from django.utils.asyncio import async_unsafe

from core import rbac

logger = logging.getLogger(__name__)


@async_unsafe
def identidad_usuario(request):
    """Roles del usuario (para el JS del shell) y flags de capacidad del shell."""
    if request.user.is_authenticated:
        try:
            if getattr(request.user, "_group_names_cache", None) is None:
                prefetch_related_objects(
                    [request.user],
                    Prefetch("groups", queryset=Group.objects.order_by("pk")),
                )
            groups = list(rbac.nombres_de_grupos(request.user))
        except Exception:
            # RED-55: el usuario sigue viendo el backoffice sin su rol en el sidebar
            # —degradar es deliberado, corre en cada render autenticado—, pero el
            # motivo queda escrito. Sin esto, un `OperationalError` de MariaDB se
            # confundía con «este usuario no tiene grupos».
            logger.exception("identidad_usuario: no se pudieron leer los grupos del usuario")
            groups = []
        return {
            "user_groups_list": groups,
            "user_primary_group": groups[0] if groups else None,
            "user_is_superuser": request.user.is_superuser,
            "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
            # G3-03: `alertas_websocket.js` se incluía para **todo** el
            # backoffice, y ante el 4403 reintentaba cinco veces por página
            # contra el único daphne. Con D-11 (Cambio 179) la campana del
            # navbar —su única superficie— y `/ws/alertas/` piden la misma
            # capacidad, así que alcanza **un** flag: sin él no hay campana ni
            # script. Resuelve sobre el mismo juego de permisos que ya leyó la
            # línea de arriba, así que no agrega consultas.
            "puede_alertas_sensibles": rbac.puede(request.user, "ciudadano.sensible"),
        }
    return {
        "user_groups_list": [],
        "user_primary_group": None,
        "user_is_superuser": False,
        "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
        "puede_alertas_sensibles": False,
    }


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
    """Contadores del sidebar.

    Quedó sin contadores con el apagado de `conversaciones` (G1-01 fase 2): el
    único que había era `badge_conversaciones`. Se mantiene declarado —el
    contrato con `settings.py` y con el sidebar sigue siendo este— para que el
    próximo badge entre acá y no en otro context processor nuevo.
    """
    return {}
