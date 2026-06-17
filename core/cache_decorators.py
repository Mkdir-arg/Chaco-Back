from django.core.cache import cache
from django.views.decorators.cache import cache_page
from functools import wraps
import hashlib

def cache_view(timeout=300):
    """Decorator para cachear vistas **públicas/anónimas** con timeout personalizado.

    ⚠️ NO usar en vistas autenticadas / con contenido por usuario (p. ej. que
    extiendan ``includes/base.html`` con el sidebar del usuario): ``cache_page``
    como decorador de vista genera la clave de cache antes de que el
    ``SessionMiddleware`` agregue ``Vary: Cookie``, por lo que cachea la página
    COMPLETA cross-user (el primero que la abre define lo que ven los demás).
    Para contenido por usuario, cachear los cálculos a nivel de datos.
    """
    return cache_page(timeout)

def cache_queryset(timeout=300, key_prefix='qs'):
    """Decorator para cachear querysets"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave única basada en función y parámetros
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            result = cache.get(cache_key)
            if result is None:
                result = func(*args, **kwargs)
                cache.set(cache_key, result, timeout)
            
            return result
        return wrapper
    return decorator

def invalidate_cache_pattern(pattern):
    """Invalida cache por patrón"""
    from django.core.cache import cache
    
    try:
        # Intentar con django_redis si está disponible
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(f"*{pattern}*")
        if keys:
            conn.delete(*keys)
    except ImportError:
        # Si no hay redis, usar cache local
        if hasattr(cache, '_cache'):
            # Para LocMemCache, limpiar claves que contengan el patrón
            keys_to_delete = [k for k in cache._cache.keys() if pattern in k]
            for key in keys_to_delete:
                cache.delete(key)
        else:
            # Fallback: limpiar todo
            cache.clear()
    except Exception:
        # Cualquier otro error: limpiar todo
        cache.clear()