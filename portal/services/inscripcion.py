"""Servicios del formulario publico de inscripcion de Becas (#293, analisis #289).

Reglas del paso 1 del link: disponibilidad del relevamiento, control de
duplicados por convocatoria completa (RN-P5), rate limiting (RN-P11) y el
desafio anti-bot. El padron (RN-P14) vive en ``programas.services.padron`` y la
consulta de identidad en ``programas.services.personas``.

**Anti-bot (revisión de seguridad, 26/08/2026).** El desafío es reCAPTCHA v2 de
Google cuando hay claves configuradas. Sin claves se usa el desafío aritmético
propio, que un script resuelve leyendo la pregunta del HTML: alcanza para dev y
para no romper un entorno sin credenciales, pero no frena automatización real.
``captcha_activo()`` dice cuál está en juego.
"""

from __future__ import annotations

import logging
import random

import requests
from django.conf import settings
from django.utils import timezone

from core.performance.query_observability import instrument_external_call
from core.services.throttle import ip_cliente, rate_limit_excedido
from programas.models import Relevamiento
from programas.services.inscripcion_publica import dni_en_convocatoria
from programas.services.padron import normalizar_dni

logger = logging.getLogger(__name__)

# Rate limit del paso 1 (RN-P11): intentos por IP dentro de la ventana. Los
# rechazos por limite o captcha nunca llegan a consultar RENAPER/Gran Base.
MAX_INTENTOS_IP = getattr(settings, "INSCRIPCION_MAX_INTENTOS_IP", 10)
VENTANA_SEGUNDOS = getattr(settings, "INSCRIPCION_VENTANA_SEGUNDOS", 600)
# Segundo eje del límite: intentos sobre el MISMO documento, sin importar la IP.
# Rotar de IP deja de alcanzar para enumerar un DNI o barrer el padrón.
MAX_INTENTOS_DNI = getattr(settings, "INSCRIPCION_MAX_INTENTOS_DNI", 15)
VENTANA_DNI_SEGUNDOS = getattr(settings, "INSCRIPCION_VENTANA_DNI_SEGUNDOS", 3600)
# El paso 2 escribe en la base y recibe adjuntos: también necesita techo.
MAX_ENVIOS_PASO2 = getattr(settings, "INSCRIPCION_MAX_ENVIOS_PASO2", 20)
VENTANA_PASO2_SEGUNDOS = getattr(settings, "INSCRIPCION_VENTANA_PASO2_SEGUNDOS", 600)

SESSION_KEY_CAPTCHA = "inscripcion_captcha"
SESSION_KEY_CAPTCHA_PREGUNTA = "inscripcion_captcha_pregunta"

CAMPO_RECAPTCHA = "g-recaptcha-response"
RECAPTCHA_TIMEOUT = settings.RECAPTCHA_TIMEOUT


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
    """Cubeta por IP. Es el primer filtro, antes del captcha y de la red."""
    return rate_limit_excedido(request, "inscripcion_paso1", MAX_INTENTOS_IP, VENTANA_SEGUNDOS)


def documento_excedido(request, dni):
    """Cubeta por documento, **sin** la IP: rotar de IP no la evade.

    Se consume recién **después** del captcha. Si se contara antes, cualquiera
    podría quemarle la cuota a un documento ajeno con unos pocos POST y dejar a
    esa persona sin poder inscribirse en toda la convocatoria.
    """
    dni = normalizar_dni(dni)
    if not dni:
        return False
    return rate_limit_excedido(
        request,
        "inscripcion_paso1_dni",
        MAX_INTENTOS_DNI,
        VENTANA_DNI_SEGUNDOS,
        sufijo=dni,
        incluir_ip=False,
    )


def paso2_excedido(request, dni=""):
    """Techo del envío, por documento identificado y no por IP.

    Por IP dejaba afuera a la segunda persona que se inscribiera desde el mismo
    NAT —una escuela, un centro comunitario—, que es justo el escenario del
    trámite.
    """
    dni = normalizar_dni(dni)
    return rate_limit_excedido(
        request,
        "inscripcion_paso2",
        MAX_ENVIOS_PASO2,
        VENTANA_PASO2_SEGUNDOS,
        sufijo=dni,
        incluir_ip=not dni,
    )


# ── Anti-bot ──────────────────────────────────────────────────────────────────


def captcha_activo():
    """``"recaptcha"`` si hay claves de Google cargadas; si no, ``"aritmetico"``."""
    if getattr(settings, "RECAPTCHA_SITE_KEY", "") and getattr(settings, "RECAPTCHA_SECRET_KEY", ""):
        return "recaptcha"
    return "aritmetico"


def nuevo_captcha(request):
    """Desafio aritmetico anti-bot del paso 1 (solo sin claves de Google)."""
    a, b = random.randint(2, 9), random.randint(2, 9)
    request.session[SESSION_KEY_CAPTCHA] = a + b
    request.session[SESSION_KEY_CAPTCHA_PREGUNTA] = f"¿Cuánto es {a} + {b}?"
    return request.session[SESSION_KEY_CAPTCHA_PREGUNTA]


def pregunta_captcha(request):
    if captcha_activo() == "recaptcha":
        return ""
    return request.session.get(SESSION_KEY_CAPTCHA_PREGUNTA) or nuevo_captcha(request)


def _recaptcha_valido(request):
    """Verifica el token contra Google. Ante falla del servicio, rechaza.

    Rechazar es lo correcto acá: el captcha es lo único que separa al formulario
    de un script, y dejarlo pasar cuando Google no responde convierte una caída
    de red en una puerta abierta. La persona reintenta.
    """
    token = (request.POST.get(CAMPO_RECAPTCHA) or "").strip()
    if not token:
        return False
    datos = {"secret": settings.RECAPTCHA_SECRET_KEY, "response": token}
    ip = ip_cliente(request)
    if ip:
        datos["remoteip"] = ip
    try:
        respuesta = instrument_external_call(
            "recaptcha",
            requests.post,
            settings.RECAPTCHA_VERIFY_URL,
            data=datos,
            timeout=RECAPTCHA_TIMEOUT,
        )
        respuesta.raise_for_status()
        cuerpo = respuesta.json()
    except Exception:  # red, JSON inesperado, lo que sea: no verificado.
        logger.warning("No se pudo verificar el reCAPTCHA del formulario público")
        return False
    if not cuerpo.get("success"):
        # Los códigos de error de Google no son datos personales.
        logger.info("reCAPTCHA rechazado: %s", cuerpo.get("error-codes"))
        return False
    return True


def captcha_valido(request, respuesta):
    if captcha_activo() == "recaptcha":
        return _recaptcha_valido(request)
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
