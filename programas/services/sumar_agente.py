"""Sumar el rol de agente de relevamiento a quien ya tiene cuenta (Cambio 404).

Lo usa el paso «Buscar agente» del modal de alta rápida de Dispositivos: si la persona existe pero no tiene el rol
sembrado «Dispositivos — Agente de relevamiento», el operador con ``inspeccion.agente.crear`` se lo suma.

**Da únicamente ese grupo.** Ninguna otra capacidad, ni contraseña, ni datos de la persona. El rol es global (no del
edificio): el edificio solo sirve para decir, en la respuesta, si la persona queda como opción válida de ese
relevamiento (:func:`agentes_asignables`); el personal de una institución del edificio recibe el rol igual y sigue
sin poder ser su agente.
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction

from core import rbac
from programas.services.inspecciones import CLAVE_ROL_AGENTE, agentes_asignables
from users.models import RolMeta

logger = logging.getLogger(__name__)

#: En Dispositivos `programa.configurar` es delegable a propósito (da alcance total de configurador:
#: `puede_configurar_dispositivos`, `dispositivos_en_alcance`), así que `puede_asignar_capacidades` no la frena.
#: Un rol de agente que la tenga convertiría el alta en una vía para fabricar configuradores.
CAPS_PROHIBIDAS_EN_ROL_DE_AGENTE = frozenset({"programa.configurar"})


class RolDeAgenteNoDisponible(Exception):
    """El rol sembrado de agente falta, está inactivo o dejó de ser seguro de repartir."""


class UsuarioNoSumable(Exception):
    """No se puede sumar a este usuario: ``motivo`` es el texto para el operador, ``estado`` el HTTP."""

    def __init__(self, motivo, estado):
        super().__init__(motivo)
        self.motivo = motivo
        self.estado = estado


def rol_de_agente():
    """El grupo sembrado de agente (por clave) o ``None`` si no se lo puede dar de forma segura.

    Se descarta si está inactivo, si dejó de ser de Dispositivos o si alguien le tildó una capacidad
    que un operador de programa no puede repartir: el alta y este servicio solo están pensados para dar el
    rol de agente, no para fabricar administradores.
    """
    meta = RolMeta.objects.filter(clave=CLAVE_ROL_AGENTE, activo=True).select_related("grupo", "programa").first()
    if meta is None or meta.categoria != rbac.CATEGORIA_PROGRAMA or meta.programa is None:
        return None
    if meta.programa.codigo != rbac.CODIGO_PROGRAMA_DISPOSITIVOS:
        return None
    capacidades = set(rbac.capacidades_de_grupo(meta.grupo))
    if capacidades & CAPS_PROHIBIDAS_EN_ROL_DE_AGENTE:
        return None
    if not rbac.puede_asignar_capacidades(meta.programa, capacidades):
        return None
    return meta.grupo


def sumar_rol_de_agente(operador, edificio, user_id):
    """Suma el rol de agente a ``user_id``. Devuelve ``(usuario, sumado, asignable)``.

    ``sumado`` es ``False`` si ya lo tenía (idempotente: no duplica ni escribe). ``asignable`` dice si, con el rol
    puesto, la persona es una opción válida del selector de ``edificio``.

    El llamador ya validó la capacidad del operador y su alcance sobre ``edificio``. Acá se rechaza, con
    :class:`UsuarioNoSumable`, a quien no existe, está inactivo, es superusuario o ciudadano del portal. La fila del
    usuario se lee **con candado**: una desactivación que corre en paralelo no se cruza con esta alta.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise UsuarioNoSumable("No podés sumar a este usuario.", 403) from None
    with transaction.atomic():
        rol = rol_de_agente()
        if rol is None:
            raise RolDeAgenteNoDisponible()
        usuario = get_user_model().objects.select_for_update().filter(pk=user_id).first()
        if usuario is None or usuario.is_superuser or rbac.es_ciudadano_portal(usuario):
            raise UsuarioNoSumable("No podés sumar a este usuario.", 403)
        if not usuario.is_active:
            raise UsuarioNoSumable("Está inactivo: lo reactiva el administrador del programa.", 409)
        sumado = not usuario.groups.filter(pk=rol.pk).exists()
        if sumado:
            usuario.groups.add(rol)
            # Solo ids, sin nombre, DNI ni correo. Falta una traza persistente de cambios de roles (Cambio 404).
            logger.info(
                "Rol de agente de relevamiento sumado: operador_id=%s usuario_id=%s rol_id=%s edificio_id=%s",
                operador.pk,
                usuario.pk,
                rol.pk,
                edificio.pk,
            )
    asignable = agentes_asignables(edificio).filter(pk=usuario.pk).exists()
    return usuario, sumado, asignable
