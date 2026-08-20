from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from core.rbac import puede

from ..models import AlertaCiudadano, Ciudadano, LegajoAtencion
from ..services import AlertasService, FiltrosUsuarioService


@login_required
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

    # Alertas de conversaciones si el usuario tiene permisos
    alertas_conversaciones = []
    if puede(request.user, "conversacion.operar"):
        from conversaciones.models import HistorialAlertaConversacion

        alertas_conversaciones = (
            HistorialAlertaConversacion.objects.filter(operador=request.user)
            .select_related("conversacion__usuario", "operador")
            .order_by("-creado")[:20]
        )

    # Estadísticas filtradas por usuario
    stats = FiltrosUsuarioService.obtener_estadisticas_usuario(request.user)

    context = {
        "alertas_criticas": alertas_criticas,
        "alertas_altas": alertas_altas,
        "alertas_medias": alertas_medias,
        "alertas_conversaciones": alertas_conversaciones,
        "stats": stats,
    }

    return render(request, "legajos/alertas_dashboard.html", context)


@login_required
def cerrar_alerta_ajax(request, alerta_id):
    """Cierra una alerta vía AJAX"""
    if request.method == "POST":
        success = AlertasService.cerrar_alerta(alerta_id, request.user)
        return JsonResponse({"success": success})

    return JsonResponse({"success": False})


@login_required
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
    except Exception as e:
        return JsonResponse({"error": str(e), "status": "error", "results": [], "count": 0})


@login_required
def debug_alertas(request):
    """Vista de debug para verificar el estado de las alertas"""
    from django.http import HttpResponse

    # Información de debug
    total_alertas = AlertaCiudadano.objects.count()
    alertas_activas_sistema = AlertaCiudadano.objects.filter(activa=True).count()
    alertas_usuario = FiltrosUsuarioService.obtener_alertas_usuario(request.user)
    alertas_activas_usuario = alertas_usuario.count()
    ciudadanos_count = Ciudadano.objects.count()
    legajos_count = LegajoAtencion.objects.count()

    # Información del usuario
    grupos_usuario = list(request.user.groups.values_list("name", flat=True))
    es_superuser = request.user.is_superuser
    rol = ", ".join(grupos_usuario) if grupos_usuario else "Sin roles"

    debug_info = f"""
    <h1>Debug - Sistema de Alertas</h1>
    <h2>Información del Usuario:</h2>
    <ul>
        <li><strong>Usuario:</strong> {request.user.username}</li>
        <li><strong>Superusuario:</strong> {es_superuser}</li>
        <li><strong>Grupos:</strong> {", ".join(grupos_usuario) if grupos_usuario else "Ninguno"}</li>
        <li><strong>Rol:</strong> {rol}</li>
    </ul>

    <h2>Estadísticas del Sistema:</h2>
    <ul>
        <li>Total de alertas: {total_alertas}</li>
        <li>Alertas activas (sistema): {alertas_activas_sistema}</li>
        <li><strong>Alertas visibles para ti: {alertas_activas_usuario}</strong></li>
        <li>Ciudadanos: {ciudadanos_count}</li>
        <li>Legajos: {legajos_count}</li>
    </ul>

    <h2>Endpoints disponibles:</h2>
    <ul>
        <li><a href="/legajos/alertas/count/">/legajos/alertas/count/</a></li>
        <li><a href="/legajos/alertas/preview/">/legajos/alertas/preview/</a></li>
        <li><a href="/legajos/alertas/">/legajos/alertas/</a> (Dashboard)</li>
        <li><a href="/api/legajos/alertas/">/api/legajos/alertas/</a> (API)</li>
    </ul>

    <h2>Últimas 5 alertas (filtradas para ti):</h2>
    """

    alertas = alertas_usuario.order_by("-creado")[:5]
    if alertas:
        debug_info += "<ul>"
        for alerta in alertas:
            debug_info += (
                f"<li><strong>{alerta.prioridad}</strong> - {alerta.ciudadano.nombre_completo}: {alerta.mensaje}</li>"
            )
        debug_info += "</ul>"
    else:
        debug_info += "<p>No hay alertas activas</p>"

    debug_info += """
    <h2>Crear alertas de prueba:</h2>
    <p>Ejecuta: <code>python manage.py crear_alertas_prueba</code></p>

    <script>
    // Test JavaScript
    console.log('Testing alertas endpoints...');

    fetch('/legajos/alertas/count/')
        .then(r => r.json())
        .then(d => console.log('Count endpoint:', d))
        .catch(e => console.error('Count error:', e));

    fetch('/legajos/alertas/preview/')
        .then(r => r.json())
        .then(d => console.log('Preview endpoint:', d))
        .catch(e => console.error('Preview error:', e));
    </script>
    """

    return HttpResponse(debug_info)


@login_required
def test_alertas_page(request):
    """Página de prueba interactiva para el sistema de alertas"""
    return render(request, "legajos/test_alertas.html")
