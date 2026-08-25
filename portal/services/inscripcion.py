"""Servicios del formulario publico de inscripcion de Becas (#293, analisis #289).

Reglas del paso 1 del link: disponibilidad del relevamiento, control de
duplicados por convocatoria completa (RN-P5), rate limiting por IP (RN-P11) y
el desafio anti-bot. El padron (RN-P14) vive en ``programas.services.padron``
y la consulta de identidad en ``programas.services.personas``.
"""

from __future__ import annotations

import random

from django.conf import settings
from django.utils import timezone

from core.services.throttle import rate_limit_excedido
from programas.models import Relevamiento
from programas.services.inscripcion_publica import dni_en_convocatoria

# Rate limit del paso 1 (RN-P11): intentos por IP dentro de la ventana. Los
# rechazos por limite o captcha nunca llegan a consultar RENAPER/Gran Base.
MAX_INTENTOS_IP = getattr(settings, "INSCRIPCION_MAX_INTENTOS_IP", 10)
VENTANA_SEGUNDOS = getattr(settings, "INSCRIPCION_VENTANA_SEGUNDOS", 600)

SESSION_KEY_CAPTCHA = "inscripcion_captcha"
SESSION_KEY_CAPTCHA_PREGUNTA = "inscripcion_captcha_pregunta"


def relevamiento_disponible(relevamiento):
    """El link acepta envios cuando esta publico, vigente, en curso y con cupo."""
    return bool(
        relevamiento.es_publico
        and relevamiento.estado == Relevamiento.Estado.EN_CURSO
        and relevamiento.habilitado_en(timezone.now())
        and not relevamiento.cupo_completo
    )


# RN-P5 vive en una sola funcion (la ingesta la re-chequea en su transaccion).
dni_ya_inscripto = dni_en_convocatoria


def paso1_excedido(request):
    return rate_limit_excedido(request, "inscripcion_paso1", MAX_INTENTOS_IP, VENTANA_SEGUNDOS)


def nuevo_captcha(request):
    """Desafio aritmetico anti-bot del paso 1."""
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


def consumir_captcha(request):
    request.session.pop(SESSION_KEY_CAPTCHA, None)
    request.session.pop(SESSION_KEY_CAPTCHA_PREGUNTA, None)


def clave_sesion(relevamiento):
    """La identificacion del paso 1 vive en la sesion, por relevamiento."""
    return f"inscripcion_{relevamiento.pk}"
