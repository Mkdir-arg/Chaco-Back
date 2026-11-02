"""Consultas sobre quién es agente de relevamiento (Cambio 409, QA C2-04)."""

from django.contrib.auth import get_user_model

from programas.services.inspecciones import CLAVE_ROL_AGENTE


def correo_es_de_un_agente(email):
    """``None`` si ningún usuario tiene ``email``; si lo tiene, ``True`` cuando es agente (rol sembrado).

    Es el mismo criterio con el que el buscador de agentes decide a quién muestra: quien tiene el
    correo pero no el rol no aparece ahí, y hay que mandarlo con el administrador del programa.
    """
    usuarios = get_user_model().objects.filter(email__iexact=email)
    if not usuarios.exists():
        return None
    return usuarios.filter(groups__meta__clave=CLAVE_ROL_AGENTE).exists()
