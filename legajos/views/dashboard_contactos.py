"""Compatibilidad legacy para el dashboard de contactos.

Las vistas antiguas dependian de modelos retirados. La navegacion actual usa
``legajos.views.contactos_panel.dashboard_contactos_simple``.
"""

from .contactos_panel import dashboard_contactos_simple as dashboard_contactos


def metricas_contactos_api(request):
    from django.http import JsonResponse

    return JsonResponse(
        {
            "metricas_generales": {
                "total_contactos": 0,
                "contactos_mes": 0,
                "contactos_semana": 0,
                "total_vinculos": 0,
                "contactos_emergencia": 0,
            },
            "contactos_por_tipo": {},
            "contactos_por_estado": {},
            "profesionales_activos": [],
            "dispositivos_activos": [],
            "tendencia_semanal": [],
        }
    )


def metricas_red_contactos_api(request):
    from django.http import JsonResponse

    return JsonResponse(
        {
            "vinculos_por_tipo": {},
            "profesionales_por_rol": {},
            "ciudadanos_conectados": [],
        }
    )


def exportar_reporte_contactos(request):
    from django.http import HttpResponse

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="reporte_contactos.csv"'
    response.write("Fecha,Tipo,Estado,Ciudadano,Profesional,Duracion,Motivo\n")
    return response
