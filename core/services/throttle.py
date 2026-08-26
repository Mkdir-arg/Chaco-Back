"""Rate-limit simple basado en cache, para vistas Django no-DRF.

La IP del cliente se resuelve **sin confiar a ciegas en las cabeceras**: un
``X-Real-IP`` puesto por el atacante anulaba el límite entero (bastaba mandarlo
distinto en cada request). Ahora las cabeceras de proxy solo se leen cuando la
conexión viene de un proxy conocido (``TRUSTED_PROXY_NETS``); si no, manda
``REMOTE_ADDR``, que no se puede falsificar.
"""

import ipaddress
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

IP_DESCONOCIDA = "desconocida"


def _redes_confiables():
    redes = []
    for crudo in getattr(settings, "TRUSTED_PROXY_NETS", ()):
        try:
            redes.append(ipaddress.ip_network(crudo.strip(), strict=False))
        except ValueError:
            logger.warning("TRUSTED_PROXY_NETS: %r no es una red válida, se ignora", crudo)
    return redes


def _es_proxy_confiable(ip_texto):
    try:
        ip = ipaddress.ip_address(ip_texto)
    except ValueError:
        return False
    return any(ip in red for red in _redes_confiables())


def ip_cliente(request):
    """IP real del cliente, considerando el proxy solo si es confiable.

    En Kubernetes/nginx el request siempre llega desde la red interna, así que
    las cabeceras se usan; un pedido que llegue directo al contenedor desde
    afuera no puede inflar el límite mandando cabeceras falsas.
    """
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    if not _es_proxy_confiable(remote):
        return remote or IP_DESCONOCIDA

    # De derecha a izquierda: se descartan los saltos que son proxies conocidos
    # y se toma la primera IP que no lo sea. Con un solo proxy da lo mismo que
    # leer el último elemento; con dos (ingress externo + nginx interno) es la
    # diferencia entre la IP del ciudadano y la del proxy —que haría que todo el
    # país comparta una única cubeta de rate limit—.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    for candidata in reversed([p.strip() for p in forwarded.split(",") if p.strip()]):
        if not _es_proxy_confiable(candidata):
            return candidata
    real_ip = (request.META.get("HTTP_X_REAL_IP") or "").strip()
    if real_ip and not _es_proxy_confiable(real_ip):
        return real_ip
    return real_ip or remote or IP_DESCONOCIDA


# Nombre histórico: lo usa el resto del código.
_ip_cliente = ip_cliente


def rate_limit_excedido(request, clave, limite, ventana_segundos=60, *, sufijo="", incluir_ip=True):
    """True si se superó ``limite`` invocaciones en la ventana dada.

    Por defecto la cubeta es por IP. Con ``incluir_ip=False`` y un ``sufijo`` la
    cubeta pasa a ser de ese sufijo (p. ej. el documento tipeado) **sin** la IP:
    es lo que hace que rotar de IP no alcance para enumerar. Mezclar las dos
    cosas en una sola clave sería inútil, porque cada IP tendría su propia cuota
    para el mismo documento.

    Ante una caché caída **no bloquea**: la disponibilidad del trámite pesa más
    que el límite, y la falla queda logueada. Antes la excepción subía y el
    formulario devolvía 500.
    """
    partes = ["throttle", clave]
    if incluir_ip:
        partes.append(ip_cliente(request))
    if sufijo:
        partes.append(sufijo)
    key = ":".join(partes)
    try:
        if cache.add(key, 1, ventana_segundos):
            return False
        try:
            return cache.incr(key) > limite
        except ValueError:
            # La clave expiró entre el add y el incr: arranca ventana nueva.
            cache.add(key, 1, ventana_segundos)
            return False
    except Exception:  # Redis caído, timeout, etc.
        logger.exception("No se pudo aplicar el rate limit %s", clave)
        return False
