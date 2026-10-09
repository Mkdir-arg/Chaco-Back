import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from core.rbac import requiere

from ..services import AlertasService, FiltrosUsuarioService
from .mensajes import ERROR_GENERICO

logger = logging.getLogger(__name__)

# Acá vivían `debug_alertas` y `test_alertas_page`, las vistas de las rutas
# `alertas/debug/` y `alertas/test/`. La primera armaba el HTML con f-strings e
# interpolaba sin escapar el nombre del ciudadano, el mensaje de la alerta, el
# username y los nombres de grupo: XSS almacenado para cualquier usuario logueado,
# incluso sin roles (SEC-19, auditoría oct-2026). La segunda renderizaba una
# plantilla de prueba que ya ni existía en el repo (respondía 500).
#
# Las cuatro vistas de este módulo llevaban solo `@login_required`: el dashboard
# y el preview traían el **nombre del ciudadano y el texto de la alerta** a
# cualquier cuenta de backoffice, y `cerrar-ajax/` con `n = 1..N` silenciaba las
# alertas de todo el sistema (SEC-18, auditoría oct-2026). SEC-18 les puso
# `ciudadano.ver`; el alcance de qué alertas entran lo sigue poniendo
# `FiltrosUsuarioService`.
#
# Desde el Cambio 179 (ronda 2) piden `ciudadano.sensible`, no `ciudadano.ver`.
# **D-11 vale por canal de transporte, no por pantalla**: el mensaje de una
# alerta —«Riesgo Suicida», «Violencia», el nombre del ciudadano— es el mismo
# dato que el WebSocket entrega con `ciudadano.sensible` y que
# `alertas_ciudadano_api` devuelve con `ciudadano.sensible`. Mientras el
# dashboard, el contador y el preview se quedaran en `ciudadano.ver`, el
# «Operador de backoffice» de `seed_rbac` seguía leyendo por HTTP exactamente lo
# que G1c-04 le cerró por WS, y —si además tiene `config.administrar`, que es lo
# que `FiltrosUsuarioService.tiene_alcance_global` mira— de **todo** el padrón.
# Va sin migración de datos: si el PM decide que el Operador siga viendo
# alertas, se tilda `ciudadano.sensible` en el ABM de Roles.


@login_required
@requiere("ciudadano.sensible")
def alertas_dashboard(request):
    """Vista principal del dashboard de alertas"""
    # Obtener alertas filtradas por usuario
    alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(request.user)

    alertas_criticas = (
        alertas_usuario.filter(prioridad="CRITICA")
        .select_related("ciudadano", "legajo", "cerrada_por")
        .order_by("-creado")[:10]
    )

    alertas_altas = (
        alertas_usuario.filter(prioridad="ALTA")
        .select_related("ciudadano", "legajo", "cerrada_por")
        .order_by("-creado")[:10]
    )

    alertas_medias = (
        alertas_usuario.filter(prioridad="MEDIA")
        .select_related("ciudadano", "legajo", "cerrada_por")
        .order_by("-creado")[:10]
    )

    # G1-01 fase 2: acá se traía `alertas_conversaciones` (el `HistorialAlertaConversacion`
    # del operador) para una tabla al pie de la pantalla que enlazaba a
    # `conversaciones:detalle`. Se fue con el apagado de la app.

    # Estadísticas filtradas por usuario
    stats = FiltrosUsuarioService.obtener_estadisticas_usuario(request.user)

    context = {
        "alertas_criticas": alertas_criticas,
        "alertas_altas": alertas_altas,
        "alertas_medias": alertas_medias,
        "stats": stats,
    }

    return render(request, "legajos/alertas_dashboard.html", context)


@login_required
@requiere("ciudadano.sensible")
def cerrar_alerta_ajax(request, alerta_id):
    """Cierra una alerta vía AJAX.

    Sube con el dashboard, que es su única superficie: dejarla en
    `ciudadano.ver` habilitaba a mutar por id alertas que ya no se pueden leer.
    """
    if request.method == "POST":
        success = AlertasService.cerrar_alerta(alerta_id, request.user)
        return JsonResponse({"success": success})

    return JsonResponse({"success": False})


@login_required
@requiere("ciudadano.sensible")
def alertas_count_ajax(request):
    """Obtiene el contador de alertas para el navbar (polled: cacheado 30 s)."""
    from django.core.cache import cache
    from django.db.models import Count, Q

    def calcular():
        alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(request.user)
        return alertas_usuario.aggregate(
            count=Count("id"),
            criticas=Count("id", filter=Q(prioridad="CRITICA")),
        )

    data = cache.get_or_set(f"alertas_count:{request.user.id}", calcular, 30)
    return JsonResponse(data)


@login_required
@requiere("ciudadano.sensible")
def alertas_preview_ajax(request):
    """Obtiene las últimas 5 alertas para el preview del navbar"""
    try:
        # Filtrar alertas por usuario
        alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(request.user)
        alertas = alertas_usuario.select_related("ciudadano", "legajo", "cerrada_por").order_by("-creado")[:5]

        alertas_data = []
        for alerta in alertas:
            alertas_data.append(
                {
                    "id": alerta.id,
                    "ciudadano_nombre": alerta.ciudadano.nombre_completo,
                    "mensaje": alerta.mensaje,
                    "prioridad": alerta.prioridad,
                    "tipo": alerta.tipo,
                    "creado": alerta.creado.isoformat(),
                    "legajo_id": alerta.legajo.id if alerta.legajo else None,
                }
            )

        return JsonResponse({"results": alertas_data, "count": len(alertas_data), "status": "success"})
    except Exception:
        # Antes: `str(e)` con HTTP 200. El `FieldError` del Cambio 66 vivió meses
        # porque desde afuera la pantalla "andaba" (RED-06): ahora el fallo queda
        # en el log con traza y el cliente ve un 500, no el detalle interno.
        logger.exception("Error armando el preview de alertas")
        return JsonResponse({"error": ERROR_GENERICO, "status": "error", "results": [], "count": 0}, status=500)
