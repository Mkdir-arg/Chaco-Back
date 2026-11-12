"""Reglas de vencimiento de la mesa de Emergencia (RN-2.7, RN-2.8, HU-2.5).

Se registran en ``core.services.vencimientos`` y las corre ``procesar_vencimientos``, junto
con las de Becas. El import lo dispara ``ProgramasConfig.ready()``.

1. ``emergencia.derivacion`` — la derivación ``PENDIENTE`` que pasó su ``vence_en`` sin que
   el dispositivo conteste pasa a ``VENCIDA`` y el caso vuelve a ``EN_GESTION`` con el mismo
   operador. Una ``ACEPTADA`` no vence nunca. ``vence_en`` se fijó al derivar: cambiar la
   vigencia en E7 no mueve las derivaciones que ya existen (RN-5.5).
2. ``emergencia.caso_sin_avance`` — el caso ``EN_GESTION`` cuya **última** ``TrazaCaso`` es
   anterior a ahora menos los «minutos sin avance» de E7 vuelve a ``NUEVO``, sin dueño. Con
   ``sin_avance_min = 0`` la regla está apagada.

Qué hace cada mitad
-------------------

``pendientes()`` es una **foto sin candado**: sirve para contar (``--dry-run``) y para
saber a quién ir a buscar. Filtra «vencido y todavía por procesar», y eso es lo que hace
idempotente a la regla.

``aplicar()`` va **fila por fila, cada una en su transacción**, y la transición la hace el
servicio (``programas.services.emergencia``), que bloquea caso → derivación y **vuelve a
leer el estado**. Si entre la foto y el candado el dispositivo aceptó (RN-3.3) o el
operador hizo algo, la fila se saltea sin error. Por eso las reglas se registran con
``transaccion_unica=False``: un solo ``atomic`` alrededor de todo retendría el candado de
cada caso hasta la última fila, con la mesa esperando detrás.

Una fila que falla queda en el log (``logger.exception``) y no frena a las demás. Lo que
devuelve ``aplicar`` son las filas que **cambiaron de verdad**, no las que se leyeron.

El orden entre las dos reglas no importa: la primera deja una traza en el caso, y esa
traza es actividad. Un caso que acaba de volver de una derivación vencida tiene un plazo
entero de «sin avance» por delante antes de que la segunda lo mire.
"""

from __future__ import annotations

import logging

from django.db.models import Exists, OuterRef, QuerySet
from django.utils import timezone

from core.services.vencimientos import ReglaVencimiento, registrar
from programas.models import CasoEmergencia, Derivacion, TrazaCaso
from programas.services import emergencia as servicio

logger = logging.getLogger(__name__)


def _aplicar_una_por_una(qs: QuerySet, transicion, que: str) -> int:
    """Corre ``transicion`` sobre cada fila de ``qs`` y cuenta las que cambiaron.

    Por pk, para que dos corridas simultáneas pidan los casos en el mismo orden. La
    transición abre su propia transacción: lo que falla deshace esa fila y nada más.
    """

    procesadas, salteadas = [], []
    for fila in qs.order_by("pk"):
        try:
            resultado = transicion(fila)
        except Exception:
            logger.exception("Vencimiento de Emergencia: falló %s (id=%s). Se sigue con las demás.", que, fila.pk)
            continue
        (procesadas if resultado is not None else salteadas).append(fila.pk)
    if procesadas:
        logger.info("Vencimiento de Emergencia: %s %s (ids=%s)", len(procesadas), que, procesadas)
    if salteadas:
        logger.info(
            "Vencimiento de Emergencia: %s %s no se tocaron porque cambiaron entre la lectura y el candado (ids=%s)",
            len(salteadas),
            que,
            salteadas,
        )
    return len(procesadas)


# --- Regla 1: derivación vencida sin respuesta (RN-2.7) -------------------------


def derivaciones_vencidas() -> QuerySet:
    """Las ``PENDIENTE`` con el plazo cumplido. **1 consulta**, por ``estado`` y ``vence_en``."""

    return Derivacion.objects.filter(estado=Derivacion.Estado.PENDIENTE, vence_en__lte=timezone.now())


def vencer_derivaciones(qs: QuerySet) -> int:
    return _aplicar_una_por_una(qs, servicio.vencer_derivacion, "derivación(es) vencida(s)")


# --- Regla 2: caso en gestión sin avance (RN-2.8) -------------------------------


def casos_sin_avance() -> QuerySet:
    """Los ``EN_GESTION`` sin ninguna traza desde el límite de inactividad.

    «La última traza es anterior al límite» se pregunta como «no existe una traza desde el
    límite»: un ``NOT EXISTS`` correlacionado por caso, resuelto por el motor en la misma
    consulta. Sin ``Max`` ni ``GROUP BY`` sobre las columnas JSON del caso, sin una
    consulta por caso y sin ``Trunc*`` (ECOM no tiene tablas de timezone).

    **2 consultas**: la del SLA y la de los casos (una más, la del programa, si su cache
    está frío). Apagada (``sin_avance_min = 0``) es solo la del SLA y un queryset vacío.
    """

    limite = servicio.limite_de_inactividad()
    if limite is None:
        return CasoEmergencia.objects.none()
    con_actividad = TrazaCaso.objects.filter(caso=OuterRef("pk"), creado_en__gte=limite)
    return CasoEmergencia.objects.filter(estado=CasoEmergencia.Estado.EN_GESTION).filter(~Exists(con_actividad))


def devolver_casos_a_bandeja(qs: QuerySet) -> int:
    return _aplicar_una_por_una(
        qs, servicio.devolver_a_bandeja_por_inactividad, "caso(s) devuelto(s) a la bandeja por inactividad"
    )


def registrar_reglas() -> None:
    registrar(
        ReglaVencimiento(
            slug="emergencia.derivacion",
            descripcion="Derivaciones sin respuesta vencidas → el caso vuelve a En gestión.",
            pendientes=derivaciones_vencidas,
            aplicar=vencer_derivaciones,
            transaccion_unica=False,
        )
    )
    registrar(
        ReglaVencimiento(
            slug="emergencia.caso_sin_avance",
            descripcion="Casos en gestión sin avance → vuelven a la bandeja.",
            pendientes=casos_sin_avance,
            aplicar=devolver_casos_a_bandeja,
            transaccion_unica=False,
        )
    )


registrar_reglas()
