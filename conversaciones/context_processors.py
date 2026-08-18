from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models import Prefetch, prefetch_related_objects
from django.utils.asyncio import async_unsafe

from core import rbac


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
            groups = []
        return {
            "user_groups_list": groups,
            "user_groups_json": str(groups).replace("'", '"'),
            "user_primary_group": groups[0] if groups else None,
            "user_is_superuser": request.user.is_superuser,
            "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
            "puede_conversaciones": rbac.puede(request.user, "conversacion.operar"),
        }
    return {
        "user_groups_list": [],
        "user_groups_json": "[]",
        "user_primary_group": None,
        "user_is_superuser": False,
        "websockets_enabled": getattr(settings, "WEBSOCKETS_ENABLED", False),
        "puede_conversaciones": False,
    }
