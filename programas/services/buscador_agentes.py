"""Buscador de agentes del modal «Asignar relevamiento» (Cambio 397).

Salió de ``inspecciones.py`` para no seguir engordándolo: usa de ahí la fuente de verdad de quién es asignable.
"""

from django.contrib.auth import get_user_model

from programas.services.inspecciones import (
    AGENTE_DEBE_SER_EXTERNO,
    CLAVE_ROL_AGENTE,
    agentes_asignables,
    personal_del_edificio,
)
from users.services.busqueda import (
    TOPE_RESULTADOS,
    enmascarar_correo,
    enmascarar_dni,
    filtrar_por_texto,
    formatear_dni,
    nombre_para_mostrar,
)

MOTIVO_AGENTE_INACTIVO = "Está inactivo: lo reactiva el administrador del programa."
MOTIVO_AGENTE_ES_PERSONAL = "Es personal de una institución de este edificio: no se le asigna su propio relevamiento."
MOTIVO_AGENTE_NO_RELEVA = "No tiene un rol activo que le permita relevar en Dispositivos."


def buscar_agentes_de_relevamiento(edificio, texto):
    """``(filas, hay_mas)``: agentes con el rol sembrado que coinciden con ``texto``, y si se pueden asignar.

    Es el buscador del modal «Asignar relevamiento» (Cambio 397). Solo mira a quien tiene el rol sembrado de
    agente (``RolMeta.clave = CLAVE_ROL_AGENTE``): un territorial de Becas o cualquier otro usuario no aparece.
    **Elegir a alguien no le da ningún rol ni permiso**: el resultado solo dice si esa persona ya es una opción
    válida del selector de ``edificio``. La asignabilidad sale de la misma fuente que llena ese selector
    (:func:`agentes_asignables`), no de una regla paralela. A quien no es asignable se le enmascaran DNI y correo.

    El llamador ya validó el largo mínimo y el alcance del operador sobre ``edificio``. Consultas acotadas:
    los candidatos, los asignables entre ellos y el personal del edificio (nada por fila).
    """

    candidatos = list(
        filtrar_por_texto(
            get_user_model().objects.filter(groups__meta__clave=CLAVE_ROL_AGENTE, is_superuser=False),
            texto,
        )
        .select_related("profile")
        .distinct()
        .order_by("last_name", "first_name", "pk")[: TOPE_RESULTADOS + 1]
    )
    hay_mas = len(candidatos) > TOPE_RESULTADOS
    candidatos = candidatos[:TOPE_RESULTADOS]
    ids = [usuario.pk for usuario in candidatos]
    asignables = set(agentes_asignables(edificio).filter(pk__in=ids).values_list("pk", flat=True))
    personal = set(personal_del_edificio(edificio).filter(rol__user__in=ids).values_list("rol__user", flat=True))

    filas = []
    for usuario in candidatos:
        asignable = usuario.pk in asignables
        if asignable:
            motivo = ""
        elif not usuario.is_active:
            motivo = MOTIVO_AGENTE_INACTIVO
        elif AGENTE_DEBE_SER_EXTERNO and usuario.pk in personal:
            motivo = MOTIVO_AGENTE_ES_PERSONAL
        else:
            # Invariante: asignable = activo ∧ rol activo del programa con ``inspeccion.relevar`` ∧ ¬personal del
            # edificio (``agentes_asignables``). Quien llega acá está activo y no es personal, así que lo único que
            # le falta es el rol. Si ``agentes_asignables`` suma otra exclusión, hay que sumar acá su motivo.
            motivo = MOTIVO_AGENTE_NO_RELEVA
        perfil = getattr(usuario, "profile", None)
        dni = (getattr(perfil, "dni", "") or "") if perfil else ""
        filas.append(
            {
                "id": usuario.pk,
                "nombre": nombre_para_mostrar(usuario),
                "dni": formatear_dni(dni) if asignable else enmascarar_dni(dni),
                "email": usuario.email if asignable else enmascarar_correo(usuario.email),
                "segmentos": [],
                "activo": usuario.is_active,
                "asignable": asignable,
                "motivo": motivo,
            }
        )
    return filas, hay_mas
