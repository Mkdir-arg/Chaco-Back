from django.conf import settings
from django.utils.asyncio import async_unsafe

from core import rbac


@async_unsafe
def user_groups(request):
    """Context processor: datos de grupos (para JS) y flags de capacidad del usuario."""
    if request.user.is_authenticated:
        try:
            groups = list(request.user.groups.values_list("name", flat=True))
        except Exception:
            groups = []
        return {
            "user_groups_list": groups,
            "user_groups_json": str(groups).replace("'", '"'),
            "user_is_superuser": request.user.is_superuser,
            "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
            "puede_conversaciones": rbac.puede(request.user, "conversacion.operar"),
        }
    return {
        "user_groups_list": [],
        "user_groups_json": "[]",
        "user_is_superuser": False,
        "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
        "puede_conversaciones": False,
    }
