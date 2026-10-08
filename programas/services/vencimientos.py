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

import logging

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.services.vencimientos import ReglaVencimiento, registrar
from programas.models import Convocatoria, Relevamiento

logger = logging.getLogger(__name__)

# Estados de relevamiento que se consideran "abiertos" (todavía en campo o
# recién finalizados sin revisar). Los que ya están EN_REVISION o TERMINADO no
# se tocan.
ESTADOS_RELEVAMIENTO_ABIERTOS = (
    Relevamiento.Estado.ASIGNADO,
    Relevamiento.Estado.EN_CURSO,
    Relevamiento.Estado.FINALIZANDO,
    Relevamiento.Estado.FINALIZADO,
)

# La otra mitad de la partición: lo que el cierre automático no toca. No la usa
# la regla —filtra por los abiertos—, pero deja explícito que todo estado del
# enum cae en exactamente una de las dos tuplas. Un estado nuevo que no se
# clasifique rompe `test_la_particion_de_estados_cubre_el_enum` (RED-28) en vez
# de quedarse afuera del cron en silencio.
ESTADOS_RELEVAMIENTO_CERRADOS = (
    Relevamiento.Estado.EN_REVISION,
    Relevamiento.Estado.TERMINADO,
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
        Q(
            convocatoria__fecha_fin__lt=_hoy(),
            estado__in=ESTADOS_RELEVAMIENTO_ABIERTOS,
        )
        | Q(
            fecha_hasta__lt=timezone.now(),
            estado__in=(Relevamiento.Estado.ASIGNADO, Relevamiento.Estado.EN_CURSO),
        )
    )


def pasar_relevamientos_a_revision(qs: QuerySet) -> int:
    """Manda los relevamientos a ``EN_REVISION``. A los que no tenían
    ``fecha_finalizado`` se la sella ahora (registro de cuándo se cortó el
    campo). Se parten los ids antes de mutar para no depender del orden de las
    actualizaciones.

    BEC-22: cada ``update()`` vuelve a filtrar por estado y el total son las
    filas **afectadas**, no los ids leídos. Entre la lectura y la escritura el
    estado puede haber cambiado —un coordinador que termina el relevamiento
    desde la pantalla—, y contar los ids informaba un cierre que no ocurrió.

    G1-04: cada transición queda en el log. El relevamiento no tiene traza
    propia como los casos (Cambio 54), y sin esto un territorial encuentra su
    relevamiento cerrado sin ningún registro de quién o qué lo cerró —que es la
    mitad invisible del problema de la sincronización tardía—.

    El log nombra los ids que **efectivamente** cerró este ``update()``, no los
    que se leyeron: son justo los casos de BEC-22 los que los separan, y ahí el
    rastro decía que se cerró un relevamiento que nadie tocó. Los que se
    saltearon porque cambiaron de estado en el medio salen en su propia línea,
    que es el dato que explica la diferencia cuando alguien va a buscarla.

    Cuáles cerró se resuelve **actualizando de a un id**: ``update()`` devuelve
    cuántas filas tocó y no cuáles, y releer por estado después no distingue el
    que cerró esta corrida del que cerró otro proceso en el medio —el coordinador
    que termina el relevamiento desde la pantalla llega a `EN_REVISION` igual—,
    así que el rastro se atribuía cierres ajenos. Con el filtro de estado dentro
    de cada ``UPDATE``, un ``1`` es una fila que estaba abierta y la cerró esta
    llamada; no hay ventana entre decidir y escribir. Son tantas consultas como
    relevamientos vencidos, que es lo que el cron de las 03:10 procesa por noche.
    """
    now = timezone.now()
    ids_sin_fecha = list(qs.filter(fecha_finalizado__isnull=True).values_list("pk", flat=True))
    ids_con_fecha = list(qs.filter(fecha_finalizado__isnull=False).values_list("pk", flat=True))
    leidos = sorted({*ids_sin_fecha, *ids_con_fecha})

    abiertos = Relevamiento.objects.filter(estado__in=ESTADOS_RELEVAMIENTO_ABIERTOS)
    cerrados_ahora = set()
    for pks, extra in ((ids_sin_fecha, {"fecha_finalizado": now}), (ids_con_fecha, {})):
        for pk in pks:
            if abiertos.filter(pk=pk).update(estado=Relevamiento.Estado.EN_REVISION, modificado=now, **extra):
                cerrados_ahora.add(pk)
    cerrados = len(cerrados_ahora)
    ids_cerrados = sorted(cerrados_ahora)
    if ids_cerrados:
        logger.info(
            "Vencimiento: %s relevamiento(s) a EN_REVISION por fecha (ids=%s)",
            len(ids_cerrados),
            ids_cerrados,
        )
    salteados = [pk for pk in leidos if pk not in cerrados_ahora]
    if salteados:
        logger.info(
            "Vencimiento: %s relevamiento(s) no se cerraron porque cambiaron de estado entre la lectura "
            "y la escritura (ids=%s)",
            len(salteados),
            salteados,
        )
    return cerrados


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
