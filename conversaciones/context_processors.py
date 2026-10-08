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
            # backoffice. `puede_ver_ciudadanos` decide si el script viaja
            # (es la capacidad de la campana del navbar, que es su única
            # superficie) y `puede_alertas_sensibles` decide si además abre
            # el socket: la capacidad de `/ws/alertas/` es `ciudadano.sensible`
            # (G1c-04, D-11), y sin ella el handshake rebotaba con 4403 y el
            # script lo reintentaba cinco veces por página. Las dos resuelven
            # sobre el mismo juego de permisos que ya leyó la línea de arriba,
            # así que no agregan consultas.
            "puede_ver_ciudadanos": rbac.puede(request.user, "ciudadano.ver"),
            "puede_alertas_sensibles": rbac.puede(request.user, "ciudadano.sensible"),
        }
    return {
        "user_groups_list": [],
        "user_primary_group": None,
        "user_is_superuser": False,
        "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
        "puede_conversaciones": False,
        "puede_ver_ciudadanos": False,
        "puede_alertas_sensibles": False,
    }
