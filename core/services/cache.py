from django.core.cache import cache
from django.views.decorators.cache import cache_page
from functools import wraps


def cache_view(timeout=300):
    """Decorator para cachear vistas con timeout personalizado"""
    return cache_page(timeout)


def cache_queryset(timeout=300, key_prefix='qs'):
    """Decorator para cachear querysets"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
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
    try:
        from django_redis import get_redis_connection
        conn = get_redis_connection("default")
        keys = conn.keys(f"*{pattern}*")
        if keys:
            conn.delete(*keys)
    except ImportError:
        if hasattr(cache, '_cache'):
            keys_to_delete = [k for k in cache._cache.keys() if pattern in k]
            for key in keys_to_delete:
                cache.delete(key)
        else:
            cache.clear()
    except Exception:
        cache.clear()
