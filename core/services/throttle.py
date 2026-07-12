"""Rate-limit simple por IP basado en cache, para vistas Django no-DRF."""

from django.core.cache import cache


def _ip_cliente(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "desconocida")


def rate_limit_excedido(request, clave, limite, ventana_segundos=60):
    """True si la IP superó `limite` invocaciones en la ventana dada."""
    key = f"throttle:{clave}:{_ip_cliente(request)}"
    if cache.add(key, 1, ventana_segundos):
        return False
    try:
        return cache.incr(key) > limite
    except ValueError:
        # La clave expiró entre el add y el incr: arranca ventana nueva.
        cache.add(key, 1, ventana_segundos)
        return False
