import csv
from datetime import timedelta

from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from core.rbac import requiere
from ..services.linking import annotate_legajo_link_data
from ..models import LegajoAtencion
from programas.models import InscripcionPrograma

@login_required
def dashboard_contactos_simple(request):
    """Dashboard simple para probar"""
    return render(request, 'legajos/dashboard_simple.html', {
        'titulo': 'Dashboard de Contactos - Funcionando!'
    })

@login_required  
def test_api(request):
    """API de prueba"""
    return JsonResponse({
        'status': 'ok',
        'message': 'Las APIs funcionan correctamente'
    })


@login_required
@requiere("reporte.ver")
def reportes_view(request):
    """Vista liviana de reportes para mantener operativa la navegación del backoffice."""
    hace_7_dias = timezone.now().date() - timedelta(days=7)

    legajos = annotate_legajo_link_data(LegajoAtencion.objects.all())
    stats = {
        'total_legajos': legajos.count(),
        'legajos_activos': legajos.exclude(estado='CERRADO').count(),
        'riesgo_alto': legajos.filter(nivel_riesgo='ALTO').count(),
        'nuevos_semana': legajos.filter(fecha_admision__gte=hace_7_dias).count(),
        'por_estado': [
            {'codigo': item['estado'], 'label': item['estado'].replace('_', ' ').title(), 'total': item['total']}
            for item in legajos.values('estado').order_by('estado').annotate(total=models.Count('id'))
        ],
        'por_riesgo': [
            {'codigo': item['nivel_riesgo'], 'label': item['nivel_riesgo'].title(), 'total': item['total']}
            for item in legajos.values('nivel_riesgo').order_by('nivel_riesgo').annotate(total=models.Count('id'))
        ],
        'por_dispositivo': [
            {
                'nombre': item['programa__nombre'] or 'Sin programa',
                'tipo_label': 'Programa',
                'total': item['total'],
            }
            for item in InscripcionPrograma.objects.filter(legajo_id__isnull=False)
            .values('programa__nombre')
            .order_by('programa__nombre')
            .annotate(total=models.Count('legajo_id', distinct=True))[:10]
        ],
        'por_mes': [
            {'mes': item['mes'], 'total': item['total']}
            for item in legajos.annotate(mes=models.functions.TruncMonth('fecha_admision')).values('mes').order_by('-mes').annotate(total=models.Count('id'))[:6]
        ],
        'metricas_calidad': {
            'ttr_promedio': 0,
            'adherencia_adecuada': 0,
            'tasa_derivacion': 0,
            'eventos_por_100': 0,
            'cobertura_seguimiento': 0,
        },
    }
    return render(request, 'legajos/reportes.html', {'stats': stats})


@login_required
@requiere("reporte.ver")
def exportar_reportes_csv(request):
    """Exportación CSV básica de legajos para no romper la acción principal de reportes."""
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="reportes_legajos.csv"'

    writer = csv.writer(response)
    writer.writerow(['codigo', 'apellido', 'nombre', 'dni', 'estado', 'nivel_riesgo', 'fecha_admision'])

    legajos = annotate_legajo_link_data(LegajoAtencion.objects.all()).order_by('-fecha_admision')[:1000]
    for legajo in legajos:
        writer.writerow([
            legajo.codigo,
            legajo.linked_ciudadano_apellido or '',
            legajo.linked_ciudadano_nombre or '',
            legajo.linked_ciudadano_dni or '',
            legajo.estado,
            legajo.nivel_riesgo,
            legajo.fecha_admision,
        ])

    return response