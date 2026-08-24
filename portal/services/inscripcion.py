"""Servicios del formulario público de inscripción de Becas (#293, análisis #289).

Reglas del paso 1 del link: disponibilidad del relevamiento, control de
duplicados por convocatoria completa (RN-P5), rate limiting por IP (RN-P11) y
el desafío anti-bot. El padrón (RN-P14) vive en ``programas.services.padron``
y la consulta de identidad en ``programas.services.personas``.
"""

from __future__ import annotations

import random

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from programas.models import Formulario, Relevamiento

# Rate limit del paso 1 (RN-P11): intentos por IP dentro de la ventana. Los
# rechazos por límite o captcha nunca llegan a consultar RENAPER/Gran Base.
MAX_INTENTOS_IP = getattr(settings, "INSCRIPCION_MAX_INTENTOS_IP", 10)
VENTANA_SEGUNDOS = getattr(settings, "INSCRIPCION_VENTANA_SEGUNDOS", 600)

SESSION_KEY_CAPTCHA = "inscripcion_captcha"
SESSION_KEY_CAPTCHA_PREGUNTA = "inscripcion_captcha_pregunta"


def relevamiento_disponible(relevamiento):
    """¿El link acepta envíos? Una sola respuesta para vencido, pausado, cupo
    lleno o cerrado: la pantalla pública no revela el motivo (RN-P4)."""
    return bool(
        relevamiento.es_publico
        and relevamiento.estado == Relevamiento.Estado.EN_CURSO
        and relevamiento.habilitado_en(timezone.now())
        and not relevamiento.cupo_completo
    )


def dni_ya_inscripto(convocatoria, dni):
    """Duplicado por convocatoria completa (RN-P5): cualquier relevamiento, de
    campo o público, por ciudadano resuelto o identificación offline."""
    return (
        Formulario.objects.filter(relevamiento__convocatoria=convocatoria)
        .filter(Q(ciudadano__dni=dni) | Q(datos_identificacion__dni=dni))
        .exists()
    )


def _ip_de(request):
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if reenviada:
        return reenviada.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def intentos_excedidos(request):
    clave = f"inscripcion:intentos:{_ip_de(request)}"
    return (cache.get(clave) or 0) >= MAX_INTENTOS_IP


def registrar_intento(request):
    clave = f"inscripcion:intentos:{_ip_de(request)}"
    if cache.add(clave, 1, VENTANA_SEGUNDOS):
        return 1
    try:
        return cache.incr(clave)
    except ValueError:  # la clave expiró entre el add y el incr
        cache.set(clave, 1, VENTANA_SEGUNDOS)
        return 1


def nuevo_captcha(request):
    """Desafío aritmético anti-bot del paso 1 (decisión del plan: autoalojado,
    sin servicio externo ni dependencia nueva). Se regenera en cada render."""
    a, b = random.randint(2, 9), random.randint(2, 9)
    request.session[SESSION_KEY_CAPTCHA] = a + b
    request.session[SESSION_KEY_CAPTCHA_PREGUNTA] = f"¿Cuánto es {a} + {b}?"
    return request.session[SESSION_KEY_CAPTCHA_PREGUNTA]


def pregunta_captcha(request):
    return request.session.get(SESSION_KEY_CAPTCHA_PREGUNTA) or nuevo_captcha(request)


def captcha_valido(request, respuesta):
    esperado = request.session.get(SESSION_KEY_CAPTCHA)
    try:
        return esperado is not None and int(respuesta) == esperado
    except (TypeError, ValueError):
        return False


def clave_sesion(relevamiento):
    """La identificación del paso 1 vive en la sesión, por relevamiento."""
    return f"inscripcion_{relevamiento.pk}"
