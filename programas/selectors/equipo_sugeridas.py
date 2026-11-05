"""Sugerencias de «Persona — Rol» del modal «Sumar persona al Equipo» mientras se escribe (Cambio 417).

Lectura pura. Ofrece los mismos pares que ``pares_persona_rol`` (usuario activo × rol activo de Dispositivos que
la persona tiene, sin el rol de agente de relevamiento y sin quien ya está activo en ese Equipo), filtrados por lo
tecleado: cada palabra es prefijo de nombre o de apellido (``istartswith``, ``LIKE 'x%'``; nunca ``startswith``,
que en MySQL/MariaDB es ``LIKE BINARY``). Desde 3 caracteres, tope de 10 y aviso de que hay más.

Cada sugerencia lleva apellido, nombre, el rol, el ``valor`` del par (``"<usuario_pk>:<rol_pk>"``, lo que viaja
en el POST) y la ``etiqueta`` que se muestra. Nunca correo, teléfono ni DNI.
"""

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef

from programas.models import MiembroEquipoDispositivo
from programas.services.dispositivos import programa_dispositivos
from programas.services.inspecciones import CLAVE_ROL_AGENTE
from users.services.busqueda import (
    MIN_CARACTERES,
    TOPE_RESULTADOS,
    normalizar_tecleado,
    palabras_del_tecleado,
    q_prefijo_por_palabras,
)


def consulta_de_pares(dispositivo, palabras):
    """Los enlaces ``usuario × rol`` sumables a ``dispositivo`` cuyo nombre empieza con cada palabra."""

    ya_en_el_equipo = MiembroEquipoDispositivo.objects.filter(
        dispositivo=dispositivo, activo=True, usuario_id=OuterRef("user_id"), rol_id=OuterRef("group_id")
    )
    return (
        get_user_model()
        .groups.through.objects.filter(
            q_prefijo_por_palabras(palabras, "user__first_name", "user__last_name"),
            user__is_active=True,
            group__meta__activo=True,
            group__meta__programa=programa_dispositivos(),
        )
        .exclude(group__meta__clave=CLAVE_ROL_AGENTE)
        .exclude(Exists(ya_en_el_equipo))
        .order_by("user__last_name", "user__first_name", "user_id", "group__name")
        .values("user_id", "group_id", "user__first_name", "user__last_name", "group__name")
    )


def sugerir_pares_equipo(dispositivo, texto):
    """``{"resultados": [{apellido, nombre, rol, valor, etiqueta}], "hay_mas": bool}`` para lo que se lleva tecleado."""

    texto = normalizar_tecleado(texto)
    vacio = {"resultados": [], "hay_mas": False}
    if len(texto) < MIN_CARACTERES or programa_dispositivos() is None:
        return vacio
    palabras = palabras_del_tecleado(texto)
    filas = list(consulta_de_pares(dispositivo, palabras)[: TOPE_RESULTADOS + 1])
    resultados = []
    for fila in filas[:TOPE_RESULTADOS]:
        nombre, apellido, rol = fila["user__first_name"], fila["user__last_name"], fila["group__name"]
        resultados.append(
            {
                "apellido": apellido,
                "nombre": nombre,
                "rol": rol,
                "valor": f"{fila['user_id']}:{fila['group_id']}",
                "etiqueta": f"{f'{nombre} {apellido}'.strip()} — {rol}",
            }
        )
    return {"resultados": resultados, "hay_mas": len(filas) > TOPE_RESULTADOS}
