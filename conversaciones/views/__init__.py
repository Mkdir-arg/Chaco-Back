"""Paquete de vistas para la app de conversaciones."""

from .backoffice import (
    api_conversacion_detalle,
    api_estadisticas_tiempo_real,
    api_metricas_tiempo_real,
    asignacion_automatica,
    asignar_conversacion,
    cerrar_conversacion,
    configurar_cola,
    detalle_conversacion,
    enviar_mensaje_operador,
    lista_conversaciones,
    metricas_conversaciones,
    reasignar_conversacion,
    tiene_permiso_conversaciones,
)
from .public import (
    evaluar_conversacion,
)
