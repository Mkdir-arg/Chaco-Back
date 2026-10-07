"""Selectors para la app de legajos."""

from .ciudadanos import (  # noqa: F401
    build_ciudadano_detail_context,
    get_ciudadanos_dashboard_metrics,
    get_ciudadanos_queryset,
)
from .contactos import (  # noqa: F401
    build_ciudadano_actividades_payload,
    build_ciudadano_archivos_payload,
    build_ciudadano_timeline_payload,
    build_legajo_archivos_payload,
    build_legajo_evolucion_payload,
    get_legajo_contactos_context,
)
from .legajos import (  # noqa: F401
    ESTADO_CERRADO,
    legajos_abiertos,
    resumen_legajos_atencion,
)
