from functools import wraps

from django.core.cache import cache
from django.views.decorators.cache import cache_page


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


def cache_queryset(timeout=300, key_prefix="qs"):
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
