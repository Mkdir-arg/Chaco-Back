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
    """Contar **inscripciones** activas, pese al nombre.

    Agrega `InscripcionPrograma`, no `LegajoAtencion`. Se mantiene tal cual porque la
    consume `dashboard.views.home.DashboardView` (la copia vieja del inicio, tapada por
    el orden del URLconf: RED-78) y porque RED-51 tiene dos tests escritos alrededor de
    que `stats_legajos` agrega inscripciones.

    La home **ya no la usa**: su tarjeta dice «Legajos activos» y para eso está
    `contar_legajos_atencion()` (G2-04).
    """
    from django.db.models import Count, Q

    cache_key = "stats_legajos"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = InscripcionPrograma.objects.aggregate(
            total=Count("id"), activos=Count("id", filter=Q(estado__in=["ACTIVO", "EN_SEGUIMIENTO"]))
        )
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_legajos_atencion():
    """``{"total": n, "activos": n}`` de `LegajoAtencion`, cacheado.

    La definición de «activo» no se escribe acá: la trae
    `legajos.selectors.resumen_legajos_atencion()`, que es la misma que usa
    `/legajos/reportes/`. Las dos pantallas tienen que dar el mismo número (G2-04).

    La clave la borra el receiver de `legajos/signals/core.py` en cada alta, edición o
    baja de un legajo, así que no queda vieja hasta que expire el TTL.
    """
    from legajos.selectors import resumen_legajos_atencion

    cache_key = "stats_legajos_atencion"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = resumen_legajos_atencion()
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_seguimientos_hoy():
    """Contar nuevas inscripciones del día con caché."""
    from django.utils import timezone

    # El día **local**: `fecha_inscripcion` es un DateField que se llena con la
    # fecha local, así que con la de UTC el contador daba 0 entre las 21 y las 24
    # y además partía la clave de caché en dos días distintos (BEC-18).
    hoy = timezone.localdate()
    cache_key = f"seguimientos_hoy_{hoy}"
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = InscripcionPrograma.objects.filter(fecha_inscripcion=hoy).count()
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
    cache.delete("stats_legajos_atencion")
    cache.delete("alertas_activas")
    from django.utils import timezone

    cache.delete(f"seguimientos_hoy_{timezone.localdate()}")
