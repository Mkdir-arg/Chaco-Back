"""Utilidades básicas de dashboard."""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError

from legajos.models import Ciudadano
from programas.models import InscripcionPrograma

logger = logging.getLogger(__name__)


def table_exists(table_name):
    """Check if a DB table exists without exploding when DB is unavailable."""
    try:
        vendor = connection.vendor
    except ImproperlyConfigured:
        logger.debug("Base de datos no configurada; omitiendo chequeo de %s", table_name)
        return False

    try:
        if vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES LIKE %s", [table_name])
                return cursor.fetchone() is not None
        return table_name in connection.introspection.table_names()
    except (OperationalError, ProgrammingError, AttributeError) as error:
        logger.debug("No se pudo comprobar la existencia de %s (%s); se asume ausente", table_name, error)
        return False


CACHE_TIMEOUT = getattr(settings, "DASHBOARD_CACHE_TIMEOUT", 300)


def contar_usuarios():
    """Contar la cantidad total de usuarios."""
    cache_key = "contar_usuarios"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = User.objects.count()
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_ciudadanos():
    """Contar la cantidad total de ciudadanos."""
    cache_key = "contar_ciudadanos"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = Ciudadano.objects.count()
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_legajos():
    """Contar inscripciones activas para mantener compatibilidad con el dashboard."""
    from django.db.models import Count, Q

    cache_key = "stats_legajos"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = InscripcionPrograma.objects.aggregate(
            total=Count("id"), activos=Count("id", filter=Q(estado__in=["ACTIVO", "EN_SEGUIMIENTO"]))
        )
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_seguimientos_hoy():
    """Contar nuevas inscripciones del día con caché."""
    from django.utils import timezone

    cache_key = f"seguimientos_hoy_{timezone.now().date()}"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = InscripcionPrograma.objects.filter(fecha_inscripcion=timezone.now().date()).count()
        cache.set(cache_key, cached_value, timeout=300)  # 5 min
    return cached_value


def contar_alertas_activas():
    """Contar alertas activas con caché."""
    from legajos.models import AlertaCiudadano

    cache_key = "alertas_activas"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = AlertaCiudadano.objects.filter(activa=True).count()
        cache.set(cache_key, cached_value, timeout=60)  # 1 min
    return cached_value


def invalidate_dashboard_cache():
    """Invalida el caché del dashboard."""
    cache.delete("contar_usuarios")
    cache.delete("contar_ciudadanos")
    cache.delete("stats_legajos")
    cache.delete("alertas_activas")
    from django.utils import timezone

    cache.delete(f"seguimientos_hoy_{timezone.now().date()}")
