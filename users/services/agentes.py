"""Consultas sobre quién es agente de relevamiento (Cambio 409, QA C2-04; Cambio 408)."""

from django.contrib.auth import get_user_model

from core.rbac import GRUPO_CIUDADANO_PORTAL
from programas.services.inspecciones import CLAVE_ROL_AGENTE

DUENO_AGENTE = "agente"
DUENO_SUMABLE = "sumable"
DUENO_OTRO = "otro"


def dueno_del_correo(email):
    """``None`` si ningún usuario tiene ``email``; si lo tiene, cómo lo ve «Buscar agente».

    - ``DUENO_AGENTE``: alguien con el rol sembrado de agente (activo o no): aparece en la búsqueda.
    - ``DUENO_SUMABLE``: un usuario activo del backoffice sin el rol: aparece en la búsqueda como
      «Sumar como agente» (mismo universo que ``buscar_agentes``: ni superusuarios ni ciudadanos del portal).
    - ``DUENO_OTRO``: el resto (inactivo sin rol, superusuario, ciudadano del portal): no aparece ahí y hay
      que mandarlo con el administrador del programa.

    Si el correo está compartido (se permite), gana el que deja un camino en la búsqueda: agente, luego sumable.
    """
    usuarios = get_user_model().objects.filter(email__iexact=email)
    if not usuarios.exists():
        return None
    if usuarios.filter(groups__meta__clave=CLAVE_ROL_AGENTE).exists():
        return DUENO_AGENTE
    sumables = usuarios.filter(is_active=True, is_superuser=False).exclude(groups__name=GRUPO_CIUDADANO_PORTAL)
    if sumables.exists():
        return DUENO_SUMABLE
    return DUENO_OTRO
