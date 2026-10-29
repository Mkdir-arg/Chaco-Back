"""Buscar y asignar a un territorial que ya tiene cuenta (Cambio 355, PR 2).

El modal de alta rápida del territorial primero busca a la persona: si ya existe, se le
suma el segmento destino en vez de crear una cuenta nueva. Acá vive la lógica; las vistas
(``users/views/quick_create.py``) solo orquestan HTTP.

Reglas:

* El universo de búsqueda son los usuarios con un rol activo de Becas que otorga
  ``becas.campo``, activos e inactivos, sin superusuarios. Un gestor acotado
  (Coordinador, Referente) ve **solo territoriales puros**, el mismo criterio de
  ``usuarios_visibles_para``.
* Nombre y apellido: coincidencia parcial. DNI y correo: **solo exactos**, para que el
  buscador no sirva para barrer el padrón de a pedazos.
* A quien no tiene ningún segmento en el alcance del operador se le enmascaran DNI y
  correo. El admin nunca enmascara.
"""

from django.contrib.auth.models import Group, User
from django.db import transaction

from core import rbac
from programas.models import AsignacionTerritorial, Segmento
from programas.services.autorizacion import (
    grupos_territoriales_becas,
    segmentos_de_territoriales_en_lote,
    segmentos_para_gestion_territoriales,
)
from users.selectors.roles import es_gestor_territorial
from users.services.busqueda import (
    TOPE_RESULTADOS,
    enmascarar_correo,
    enmascarar_dni,
    filtrar_por_texto,
    formatear_dni,
    nombre_para_mostrar,
)


class TerritorialFueraDeAlcance(Exception):
    """El usuario no está en el universo del buscador para este operador."""


class TerritorialInactivo(Exception):
    """El usuario está inactivo: lo reactiva el administrador del programa."""


def _es_acotado(operador):
    return not operador.is_superuser and es_gestor_territorial(operador)


def universo_territoriales(operador):
    """Usuarios que el buscador puede devolver a ``operador`` (activos e inactivos)."""
    territoriales = grupos_territoriales_becas()
    universo = User.objects.filter(groups__in=territoriales, is_superuser=False)
    if _es_acotado(operador):
        # Puro: ningún rol fuera de los territoriales (alguien que además coordina no entra).
        universo = universo.exclude(groups__in=Group.objects.exclude(pk__in=territoriales))
    return universo.distinct()


def buscar_territoriales(operador, texto, segmento_destino):
    """``(filas, hay_mas)`` con hasta ``TOPE_RESULTADOS`` coincidencias para ``texto``.

    El llamador ya validó el largo mínimo. Consultas acotadas: una por los usuarios, una por
    sus segmentos y una por los nombres de esos segmentos (nada por fila).
    """
    candidatos = list(
        filtrar_por_texto(universo_territoriales(operador), texto)
        .select_related("profile")
        .order_by("last_name", "first_name", "pk")[: TOPE_RESULTADOS + 1]
    )
    hay_mas = len(candidatos) > TOPE_RESULTADOS
    candidatos = candidatos[:TOPE_RESULTADOS]

    por_usuario = segmentos_de_territoriales_en_lote([u.pk for u in candidatos])
    nombres = dict(
        Segmento.objects.filter(pk__in={s for ids in por_usuario.values() for s in ids}).values_list("pk", "nombre")
    )
    acotado = _es_acotado(operador)
    alcance = set(segmentos_para_gestion_territoriales(operador).values_list("pk", flat=True)) if acotado else set()

    filas = []
    for usuario in candidatos:
        segmentos = por_usuario.get(usuario.pk, [])
        en_alcance = (not acotado) or bool(alcance.intersection(segmentos))
        perfil = getattr(usuario, "profile", None)
        dni = (getattr(perfil, "dni", "") or "") if perfil else ""
        filas.append(
            {
                "id": usuario.pk,
                "nombre": nombre_para_mostrar(usuario),
                "dni": formatear_dni(dni) if en_alcance else enmascarar_dni(dni),
                "email": usuario.email if en_alcance else enmascarar_correo(usuario.email),
                "segmentos": sorted(nombres[s] for s in segmentos if s in nombres),
                "activo": usuario.is_active,
                "ya_asignado": segmento_destino.pk in segmentos,
                "en_alcance": en_alcance,
            }
        )
    return filas, hay_mas


@transaction.atomic
def asignar_segmento(operador, user_id, segmento):
    """Suma ``segmento`` al territorial ``user_id`` (idempotente) y devuelve ``(usuario, ids)``.

    Mismo candado que el guardado del ABM: una edición del usuario que corre en paralelo
    (le quita el rol, lo desactiva) no se cruza con esta alta. La pertenencia al universo y
    el estado activo se leen **con el candado tomado**.
    """
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise TerritorialFueraDeAlcance() from None
    rbac.tomar_candado_de_administracion()
    usuario = universo_territoriales(operador).filter(pk=user_id).first()
    if usuario is None:
        raise TerritorialFueraDeAlcance()
    if not usuario.is_active:
        raise TerritorialInactivo()
    AsignacionTerritorial.objects.get_or_create(
        territorial=usuario, segmento=segmento, defaults={"asignado_por": operador}
    )
    ids = list(
        AsignacionTerritorial.objects.filter(territorial=usuario).order_by("pk").values_list("segmento_id", flat=True)
    )
    return usuario, ids
