import logging

from django.core.cache import cache
from django.utils.asyncio import async_unsafe

logger = logging.getLogger(__name__)

ALERTAS_CRITICAS_CACHE_TIMEOUT = 30


def alertas_criticas_cache_key(user_id):
    return f"alertas_criticas_user_{user_id}"


@async_unsafe
def alertas_eventos_criticos(request):
    """Context processor para mostrar alertas de eventos críticos al responsable"""

    if not request.user.is_authenticated:
        return {}

    cache_key = alertas_criticas_cache_key(request.user.id)
    eventos_pendientes = cache.get(cache_key)
    if eventos_pendientes is None:
        try:
            eventos_pendientes = []
            cache.set(cache_key, eventos_pendientes, ALERTAS_CRITICAS_CACHE_TIMEOUT)
        except Exception:
            logger.exception(
                "Error al cargar alertas críticas para usuario %s",
                request.user.id,
            )
            eventos_pendientes = []

    return {"eventos_criticos_pendientes": eventos_pendientes}
