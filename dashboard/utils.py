"""Utilidades básicas de dashboard."""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.utils import OperationalError, ProgrammingError

from dashboard.cache import (
    CLAVE_ALERTAS,
    CLAVE_CIUDADANOS,
    CLAVE_STATS_LEGAJOS,
    CLAVE_STATS_LEGAJOS_ATENCION,
    CLAVE_USUARIOS,
    clave_seguimientos_hoy,
)
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
    cache_key = CLAVE_USUARIOS
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = User.objects.count()
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_ciudadanos():
    """Contar la cantidad total de ciudadanos."""
    cache_key = CLAVE_CIUDADANOS
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = Ciudadano.objects.count()
        cache.set(cache_key, cached_value, timeout=CACHE_TIMEOUT)
    return cached_value


def contar_legajos():
    """Contar **inscripciones** activas, pese al nombre.

    Agrega `InscripcionPrograma`, no `LegajoAtencion`. Ninguna pantalla la consume:
    su último llamador era `dashboard.views.home.DashboardView`, que RED-78 borró. Se
    mantiene porque la clave `stats_legajos` que escribe sigue teniendo quien la
    invalide y porque RED-51 (Ola 4) tiene dos tests escritos alrededor de que
    `stats_legajos` agrega inscripciones; sacarla es de esa ficha, no de esta.

    La home **ya no la usa**: su tarjeta dice «Legajos activos» y para eso está
    `contar_legajos_atencion()` (G2-04).
    """
    from django.db.models import Count, Q

    cache_key = CLAVE_STATS_LEGAJOS
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
    baja de un legajo, así que no queda vieja hasta que expire el TTL. El mapa de qué
    modelo mueve qué clave está en `dashboard/cache.py` (RED-51).
    """
    from legajos.selectors import resumen_legajos_atencion

    cache_key = CLAVE_STATS_LEGAJOS_ATENCION
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
    cache_key = clave_seguimientos_hoy(hoy)
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = InscripcionPrograma.objects.filter(fecha_inscripcion=hoy).count()
        cache.set(cache_key, cached_value, timeout=300)  # 5 min
    return cached_value


def contar_alertas_activas():
    """Contar alertas activas con caché."""
    from legajos.models import AlertaCiudadano

    cache_key = CLAVE_ALERTAS
    cached_value = cache.get(cache_key)
    if cached_value is None:
        cached_value = AlertaCiudadano.objects.filter(activa=True).count()
        cache.set(cache_key, cached_value, timeout=60)  # 1 min
    return cached_value


# RED-51: acá vivía una de las dos `invalidate_dashboard_cache`. La que queda es
# `dashboard.cache.invalidar_dashboard()`, y las claves que borra —con qué modelo mueve
# cada una— están en esa misma tabla.
