import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Prefetch, prefetch_related_objects
from django.utils.asyncio import async_unsafe

from core import rbac

logger = logging.getLogger(__name__)


@async_unsafe
def user_groups(request):
    """Context processor: datos de grupos (para JS) y flags de capacidad del usuario."""
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
            logger.exception("user_groups: no se pudieron leer los grupos del usuario")
            groups = []
        return {
            "user_groups_list": groups,
            "user_primary_group": groups[0] if groups else None,
            "user_is_superuser": request.user.is_superuser,
            "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
            "puede_conversaciones": rbac.puede(request.user, "conversacion.operar"),
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
        "puede_conversaciones": False,
        "puede_alertas_sensibles": False,
    }
