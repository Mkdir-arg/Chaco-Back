"""Consultas sobre quién es agente de relevamiento (Cambio 409, QA C2-04; Cambio 408)."""

from django.contrib.auth import get_user_model

from programas.services.buscador_agentes import universo_buscar_agente

DUENO_AGENTE = "agente"
DUENO_SUMABLE = "sumable"
DUENO_OTRO = "otro"


def dueno_del_correo(email):
    """``None`` si ningún usuario tiene ``email``; si lo tiene, cómo lo ve «Buscar agente».

    La búsqueda sale de ``universo_buscar_agente`` (única fuente, sin regla paralela):

    - ``DUENO_AGENTE``: está en el universo con el rol sembrado de agente (activo o no).
    - ``DUENO_SUMABLE``: está en el universo sin el rol (usuario activo del backoffice): sale como «Sumar como agente».
    - ``DUENO_OTRO``: no está en el universo (inactivo sin rol, superusuario, ciudadano del portal): hay que
      mandarlo con el administrador del programa.

    Si el correo está compartido (se permite), gana el que deja un camino en la búsqueda: agente, luego sumable.
    """
    if not get_user_model().objects.filter(email__iexact=email).exists():
        return None
    en_la_busqueda = universo_buscar_agente().filter(email__iexact=email)
    if en_la_busqueda.filter(_con_rol=True).exists():
        return DUENO_AGENTE
    if en_la_busqueda.exists():
        return DUENO_SUMABLE
    return DUENO_OTRO
