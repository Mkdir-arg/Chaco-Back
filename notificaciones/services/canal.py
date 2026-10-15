"""Canal de correo de las campañas (Cambio 311, RNF-007-15).

Las campañas salen por un SMTP **propio** —Amazon SES, ``NOTIF_EMAIL_*``—, separado del SMTP
común del sistema (``EMAIL_*``, el de ECOM), para que la reputación y la cuota del correo masivo
no afecten a las credenciales, los avisos de resolución ni los comprobantes. Este módulo es el
único lugar que decide por dónde sale una campaña: lo usan el envío masivo y la prueba, así la
prueba llega por el mismo camino que el envío. Nada fuera de ``notificaciones`` lo toca.

- ``NOTIF_EMAIL_HOST`` vacía: canal **común** (``get_connection()`` y ``DEFAULT_FROM_EMAIL``),
  el comportamiento de antes. Es lo que pasa en dev, en el CI y en un ambiente sin configurar.
- ``NOTIF_EMAIL_HOST`` cargada: canal **masivo**, con su host, puerto, usuario, contraseña, TLS
  y timeout, y su remitente (``NOTIF_DEFAULT_FROM_EMAIL``, o ``DEFAULT_FROM_EMAIL`` si falta).

**Nunca abre un SMTP real en los tests.** El runner de Django pone ``EMAIL_BACKEND`` en
``locmem`` y los tests de notificaciones lo pisan con backends que heredan de él: si el backend
común es ``locmem`` o un derivado, el canal masivo usa **ese mismo backend** (con los parámetros
del masivo, que ``locmem`` acepta e ignora). Así un test elige el canal y puede ver qué parámetros
recibió, sin que exista un camino hacia SES.
"""

from __future__ import annotations

from email.utils import parseaddr

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends import locmem
from django.utils.module_loading import import_string

SMTP = "django.core.mail.backends.smtp.EmailBackend"
MASIVO = "masivo"
COMUN = "comun"


def configurado() -> bool:
    """¿Las campañas tienen su propio SMTP? Lo decide la presencia de ``NOTIF_EMAIL_HOST``."""
    return bool(getattr(settings, "NOTIF_EMAIL_HOST", ""))


def canal() -> str:
    """``"masivo"`` o ``"comun"``: por dónde sale hoy una campaña."""
    return MASIVO if configurado() else COMUN


def parametros() -> dict:
    """Los parámetros de conexión del canal masivo, tal como los recibe el backend SMTP.

    ``use_ssl`` va explícito en ``False``: si no, el backend lo toma de ``EMAIL_USE_SSL`` (el del
    canal común) y un 465 implícito de ECOM chocaría con el STARTTLS del 587 de SES.
    """
    return {
        "host": settings.NOTIF_EMAIL_HOST,
        "port": settings.NOTIF_EMAIL_PORT,
        "username": settings.NOTIF_EMAIL_HOST_USER,
        "password": settings.NOTIF_EMAIL_HOST_PASSWORD,
        "use_tls": settings.NOTIF_EMAIL_USE_TLS,
        "use_ssl": False,
        "timeout": settings.NOTIF_EMAIL_TIMEOUT,
    }


def en_memoria() -> bool:
    """¿El backend común guarda los correos en memoria (``locmem`` o un derivado, los tests)?"""
    try:
        clase = import_string(settings.EMAIL_BACKEND)
    except ImportError:
        return False
    return isinstance(clase, type) and issubclass(clase, locmem.EmailBackend)


def backend_masivo() -> str:
    """El backend del canal masivo: el SMTP real, salvo que el común sea uno en memoria."""
    return settings.EMAIL_BACKEND if en_memoria() else SMTP


def conexion_masiva():
    """Una conexión (sin abrir) por el canal de las campañas. Nunca silencia errores."""
    if not configurado():
        return get_connection(fail_silently=False)
    return get_connection(backend_masivo(), fail_silently=False, **parametros())


def remitente_masivo() -> str:
    """Remitente de las campañas (RN-007-17).

    Con el canal masivo, ``NOTIF_DEFAULT_FROM_EMAIL`` (o ``DEFAULT_FROM_EMAIL`` si está vacía).
    Sin él, siempre ``DEFAULT_FROM_EMAIL``: el SMTP común rechaza un From distinto del que
    autentica, así que un ``NOTIF_DEFAULT_FROM_EMAIL`` suelto no se usa.
    """
    if configurado():
        return getattr(settings, "NOTIF_DEFAULT_FROM_EMAIL", "") or settings.DEFAULT_FROM_EMAIL
    return settings.DEFAULT_FROM_EMAIL


def descripcion() -> str:
    """Una línea para la pantalla: por qué servicio sale la campaña y desde qué dirección."""
    direccion = parseaddr(remitente_masivo())[1] or remitente_masivo()
    if configurado():
        return f"Se envía por el servicio de correo masivo ({direccion})."
    return f"Se envía por el correo del sistema ({direccion})."
