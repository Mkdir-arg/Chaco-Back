"""Reglas de vencimiento por fecha del dominio de Becas.

Se registran en el registro genérico de ``core.services.vencimientos`` y las
corre el comando ``procesar_vencimientos``. El import lo dispara
``ProgramasConfig.ready()``.

Reglas:

1. ``becas.convocatoria`` — cierra las convocatorias cuya ``fecha_fin`` ya pasó
   (deja ``activo=False`` + marca de trazabilidad del cierre automático).
2. ``becas.relevamiento`` — los relevamientos todavía abiertos de una
   convocatoria vencida pasan a ``EN_REVISION`` (se corta el trabajo de campo).
   La regla se apoya en la fecha de la convocatoria (no en que ya se haya
   cerrado), así que es independiente e idempotente por sí misma.

El corte usa ``timezone.localdate()`` (hora Argentina, ``USE_TZ=True``): con
``fecha_fin = 31/07`` la convocatoria sigue vigente el 31 y vence el 01/08.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from core.services.vencimientos import ReglaVencimiento, registrar
from programas.models import Convocatoria, Relevamiento

# Estados de relevamiento que se consideran "abiertos" (todavía en campo o
# recién finalizados sin revisar). Los que ya están EN_REVISION o TERMINADO no
# se tocan.
ESTADOS_RELEVAMIENTO_ABIERTOS = (
    Relevamiento.Estado.ASIGNADO,
    Relevamiento.Estado.EN_CURSO,
    Relevamiento.Estado.FINALIZANDO,
    Relevamiento.Estado.FINALIZADO,
)


def _hoy():
    return timezone.localdate()


# --- Regla 1: cierre de convocatorias vencidas ---------------------------------


def convocatorias_vencidas() -> QuerySet:
    return Convocatoria.objects.filter(activo=True, fecha_fin__lt=_hoy())


def cerrar_convocatorias(qs: QuerySet) -> int:
    return qs.update(
        activo=False,
        cerrada_automaticamente=True,
        cerrada_el=timezone.now(),
        modificado=timezone.now(),
    )


# --- Regla 2: relevamientos de convocatoria vencida → en revisión --------------


def relevamientos_de_convocatoria_vencida() -> QuerySet:
    return Relevamiento.objects.filter(
        convocatoria__fecha_fin__lt=_hoy(),
        estado__in=ESTADOS_RELEVAMIENTO_ABIERTOS,
    )


def pasar_relevamientos_a_revision(qs: QuerySet) -> int:
    """Manda los relevamientos a ``EN_REVISION``. A los que no tenían
    ``fecha_finalizado`` se la sella ahora (registro de cuándo se cortó el
    campo). Se parten los ids antes de mutar para no depender del orden de las
    dos actualizaciones."""
    now = timezone.now()
    ids_sin_fecha = list(qs.filter(fecha_finalizado__isnull=True).values_list("pk", flat=True))
    ids_con_fecha = list(qs.filter(fecha_finalizado__isnull=False).values_list("pk", flat=True))

    Relevamiento.objects.filter(pk__in=ids_sin_fecha).update(
        estado=Relevamiento.Estado.EN_REVISION,
        fecha_finalizado=now,
        modificado=now,
    )
    Relevamiento.objects.filter(pk__in=ids_con_fecha).update(
        estado=Relevamiento.Estado.EN_REVISION,
        modificado=now,
    )
    return len(ids_sin_fecha) + len(ids_con_fecha)


def registrar_reglas() -> None:
    registrar(
        ReglaVencimiento(
            slug="becas.convocatoria",
            descripcion="Cierra convocatorias con fecha de fin vencida.",
            pendientes=convocatorias_vencidas,
            aplicar=cerrar_convocatorias,
        )
    )
    registrar(
        ReglaVencimiento(
            slug="becas.relevamiento",
            descripcion="Relevamientos abiertos de convocatoria vencida → En revisión.",
            pendientes=relevamientos_de_convocatoria_vencida,
            aplicar=pasar_relevamientos_a_revision,
        )
    )


registrar_reglas()
