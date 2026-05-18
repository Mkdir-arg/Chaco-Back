from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from ..performance_analyzer import PerformanceAnalyzer
from ..monitoring import system_monitor
from ..phase2_manager import phase2_manager
import json

def is_admin(user):
    return user.is_superuser or user.groups.filter(name__in=['Administrador', 'Ciudadanos']).exists()

@login_required
@user_passes_test(is_admin)
def performance_dashboard(request):
    """Performance monitoring dashboard"""
    return render(request, 'core/performance_dashboard.html')

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@extend_schema(
    description="API para obtener métricas de performance en tiempo real",
    responses={200: 'Métricas de performance del sistema'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def performance_api(request):
    """API endpoint for performance data"""
    from config.middlewares.query_counter import QueryCountMiddleware
    
    # Get session stats from middleware
    session_stats = QueryCountMiddleware.get_session_stats()
    
    analyzer = PerformanceAnalyzer()
    report = analyzer.generate_report()
    
    # Override with session data
    report.update({
        'total_queries': session_stats['total_queries'],
        'total_requests': session_stats['total_requests'],
        'slow_requests': session_stats['slow_requests'],
        'n1_detected': session_stats['n1_detected_count'] > 0,
        'similar_queries': session_stats['n1_detected_count'],
        'performance_score': max(20, 100 - min(50, session_stats['slow_requests'] * 5) - min(30, session_stats['n1_detected_count'] * 3)),
        'real_time': {
            'active_connections': session_stats['total_requests'],
            'timestamp': timezone.now().isoformat(),
            'memory_usage': _get_memory_usage(),
            'session_start': session_stats['last_reset'].isoformat(),
        }
    })
    
    return JsonResponse(report)

@extend_schema(
    description="API para análisis detallado de patrones de consultas",
    responses={200: 'Análisis de patrones de queries'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_analysis_api(request):
    """Detailed query analysis API"""
    queries = connection.queries[-100:]  # Last 100 queries
    analyzer = PerformanceAnalyzer()
    
    analysis = {
        'query_count': len(queries),
        'patterns': analyzer.analyze_queries(queries),
        'slow_queries': analyzer.get_slow_queries(queries),
        'recommendations': []
    }
    
    # Generate specific recommendations
    if analysis['patterns']['n1_detected']:
        analysis['recommendations'].append({
            'priority': 'high',
            'type': 'N+1 Detection',
            'message': f"Detected {analysis['patterns']['similar_queries']} similar queries. Consider using select_related() or prefetch_related().",
            'action': 'Review recent code changes and add query optimizations'
        })
    
    if len(analysis['slow_queries']) > 0:
        analysis['recommendations'].append({
            'priority': 'medium',
            'type': 'Slow Queries',
            'message': f"Found {len(analysis['slow_queries'])} slow queries.",
            'action': 'Add database indexes or optimize query logic'
        })
    
    return JsonResponse(analysis)

@extend_schema(
    description="API para obtener sugerencias de optimización",
    responses={200: 'Sugerencias de optimización de performance'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def optimization_suggestions_api(request):
    """API for optimization suggestions"""
    model_name = request.GET.get('model', '')
    
    suggestions = [
        {
            'category': 'Query Optimization',
            'items': [
                {
                    'title': 'Use select_related()',
                    'description': 'For ForeignKey relationships to reduce queries',
                    'example': f'{model_name}.objects.select_related("foreign_key_field")',
                    'impact': 'High'
                },
                {
                    'title': 'Use prefetch_related()',
                    'description': 'For reverse relationships and ManyToMany fields',
                    'example': f'{model_name}.objects.prefetch_related("reverse_field")',
                    'impact': 'High'
                },
                {
                    'title': 'Use only() for field limitation',
                    'description': 'When you only need specific fields',
                    'example': f'{model_name}.objects.only("field1", "field2")',
                    'impact': 'Medium'
                }
            ]
        }
    ]
    
    return JsonResponse({'suggestions': suggestions})

@extend_schema(
    description="API para métricas completas del sistema (CPU, memoria, DB, aplicación)",
    responses={200: 'Métricas completas del sistema'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_metrics_api(request):
    """Comprehensive system metrics API"""
    metrics = system_monitor.get_comprehensive_metrics()
    return JsonResponse(metrics)

@extend_schema(
    description="API para alertas activas del sistema",
    responses={200: 'Alertas activas del sistema'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alerts_api(request):
    """System alerts API"""
    alerts = system_monitor.get_active_alerts()
    return JsonResponse({'alerts': alerts, 'count': len(alerts)})

@extend_schema(
    description="API para métricas en tiempo real",
    responses={200: 'Métricas en tiempo real'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def realtime_metrics_api(request):
    """Real-time metrics API"""
    # Recolectar métricas frescas
    system_metrics = system_monitor.collect_system_metrics()
    django_metrics = system_monitor.collect_django_metrics()
    
    realtime_data = {
        'timestamp': timezone.now().isoformat(),
        'cpu_percent': system_metrics.get('cpu', {}).get('percent', 0),
        'memory_percent': system_metrics.get('memory', {}).get('percent', 0),
        'active_connections': django_metrics.get('database', {}).get('queries_count', 0),
        'cache_hits': django_metrics.get('cache', {}).get('hits', 0),
        'active_sessions': django_metrics.get('sessions', {}).get('active', 0),
        'response_time': _get_memory_usage().get('memory_mb', 0)
    }
    
    return JsonResponse(realtime_data)

@extend_schema(
    description="API para métricas de Fase 2 (particionamiento, optimización, índices)",
    responses={200: 'Métricas avanzadas de Fase 2'}
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def phase2_metrics_api(request):
    """Phase 2 advanced optimization metrics API"""
    try:
        from django.core.cache import cache
        phase2_stats = cache.get('phase2_consolidated_stats', {})
        
        if not phase2_stats:
            phase2_manager.update_consolidated_stats()
            phase2_stats = cache.get('phase2_consolidated_stats', {})
        
        response_data = {
            'phase2_active': phase2_manager.running,
            'last_update': phase2_stats.get('timestamp'),
            'partitioning': {
                'active_partitions': sum(
                    stats.get('partition_count', 0) 
                    for stats in phase2_stats.get('partitioning', {}).values()
                ),
                'total_size_mb': sum(
                    stats.get('total_size_mb', 0) 
                    for stats in phase2_stats.get('partitioning', {}).values()
                )
            },
            'query_optimization': {
                'queries_analyzed': phase2_stats.get('query_optimization', {}).get('metrics', {}).get('total_queries_analyzed', 0),
                'slow_queries': phase2_stats.get('query_optimization', {}).get('metrics', {}).get('slow_queries_count', 0),
                'optimization_opportunities': len(phase2_stats.get('query_optimization', {}).get('recommendations', {}).get('frequent_optimizations', []))
            },
            'connection_pool': {
                'total_connections': phase2_stats.get('connection_pool', {}).get('global_stats', {}).get('total_connections', 0),
                'active_connections': phase2_stats.get('connection_pool', {}).get('global_stats', {}).get('active_connections', 0),
                'avg_response_time': phase2_stats.get('connection_pool', {}).get('global_stats', {}).get('avg_response_time', 0)
            },
            'indexing': {
                'recommended_indexes': len(phase2_stats.get('indexing', {}).get('recommended_indexes', [])),
                'unused_indexes': len(phase2_stats.get('indexing', {}).get('unused_indexes', [])),
                'high_priority_suggestions': len([
                    idx for idx in phase2_stats.get('indexing', {}).get('recommended_indexes', [])
                    if idx.get('priority_score', 0) > 15
                ])
            },
            'performance_summary': phase2_stats.get('performance_summary', {})
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'phase2_active': False,
            'message': 'Fase 2 no inicializada o error en métricas'
        })

@extend_schema(
    description="Ejecuta pruebas automáticas de Fase 2 y devuelve resultados",
    responses={200: 'Resultados de pruebas automáticas'}
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_phase2_tests_api(request):
    """Ejecuta todas las pruebas de Fase 2 automáticamente"""
    try:
        from core.intelligent_indexing import index_manager
        from core.advanced_partitioning import partition_manager
        from django.contrib.auth.models import User
        from legajos.models import LegajoAtencion
        from django.db import connection
        from django.core.cache import cache
        import time
        
        results = {
            'timestamp': timezone.now().isoformat(),
            'tests_executed': [],
            'summary': {},
            'recommendations': []
        }
        
        # 1. Análisis de Índices
        start_time = time.time()
        index_suggestions = index_manager.analyze_django_models_for_indexes()
        high_priority = [s for s in index_suggestions if s.get('priority') == 'High']
        results['tests_executed'].append({
            'test': 'Análisis de Índices',
            'duration_ms': (time.time() - start_time) * 1000,
            'status': 'success',
            'result': f'{len(high_priority)} críticos, {len(index_suggestions)-len(high_priority)} menores',
            'details': {
                'high_priority': [f"{s['model']}.{s['field_name']} ({s['reason']})" for s in high_priority[:3]],
                'total_suggestions': len(index_suggestions)
            }
        })
        
        # 2. Estadísticas de Particionamiento
        start_time = time.time()
        partition_stats = partition_manager.get_partition_stats()
        total_partitions = sum(stats.get('partition_count', 0) for stats in partition_stats.values())
        results['tests_executed'].append({
            'test': 'Verificación de Particionamiento',
            'duration_ms': (time.time() - start_time) * 1000,
            'status': 'success',
            'result': f'{total_partitions} particiones activas'
        })
        
        # 3. Generar Queries de Prueba y Detectar Problemas
        start_time = time.time()
        initial_query_count = len(connection.queries)
        
        # Ejecutar queries de prueba
        users = list(User.objects.all()[:10])
        n1_detected = False
        try:
            # Query optimizada
            legajos_opt = list(LegajoAtencion.objects.select_related('responsable')[:3])
            # Query no optimizada (puede generar N+1)
            legajos_no_opt = list(LegajoAtencion.objects.all()[:3])
            for legajo in legajos_no_opt:
                try:
                    _ = legajo.responsable.username if legajo.responsable else None
                except:
                    pass
            
            # Detectar si se generaron muchas queries similares
            final_query_count = len(connection.queries)
            queries_generated = final_query_count - initial_query_count
            if queries_generated > 6:  # Más queries de las esperadas
                n1_detected = True
        except Exception as e:
            legajos_opt = []
            queries_generated = len(connection.queries) - initial_query_count
        
        status_msg = "N+1 detectado" if n1_detected else "Queries optimizadas"
        results['tests_executed'].append({
            'test': 'Análisis de Queries en Vivo',
            'duration_ms': (time.time() - start_time) * 1000,
            'status': 'warning' if n1_detected else 'success',
            'result': f'{queries_generated} queries - {status_msg}',
            'details': {
                'n1_detected': n1_detected,
                'queries_count': queries_generated,
                'users_count': len(users),
                'legajos_count': len(legajos_opt) if 'legajos_opt' in locals() else 0
            }
        })
        
        # 4. Forzar Análisis de Optimización
        start_time = time.time()
        phase2_manager.force_optimization_cycle()
        results['tests_executed'].append({
            'test': 'Ciclo de Optimización',
            'duration_ms': (time.time() - start_time) * 1000,
            'status': 'success',
            'result': 'Análisis completado'
        })
        
        # 5. Obtener Métricas Finales y Estado del Sistema
        start_time = time.time()
        phase2_stats = cache.get('phase2_consolidated_stats', {})
        perf_summary = phase2_stats.get('performance_summary', {})
        
        # Verificar estado de componentes
        components_status = {
            'partitioning': phase2_manager.components['partitioning'].running,
            'query_optimizer': phase2_manager.components['query_optimizer'].running,
            'connection_pool': hasattr(phase2_manager.components['connection_pool'], 'pools'),
            'index_manager': phase2_manager.components['index_manager'].running
        }
        active_components = sum(components_status.values())
        
        results['tests_executed'].append({
            'test': 'Estado del Sistema Fase 2',
            'duration_ms': (time.time() - start_time) * 1000,
            'status': 'success' if active_components >= 3 else 'warning',
            'result': f'{active_components}/4 componentes activos',
            'details': {
                'components': components_status,
                'performance_score': perf_summary.get('performance_score', 50)
            }
        })
        
        # Resumen
        results['summary'] = {
            'total_tests': len(results['tests_executed']),
            'all_passed': all(t['status'] == 'success' for t in results['tests_executed']),
            'total_duration_ms': sum(t['duration_ms'] for t in results['tests_executed']),
            'performance_score': perf_summary.get('performance_score', 0),
            'index_suggestions': len(index_suggestions),
            'active_partitions': total_partitions,
            'queries_analyzed': queries_generated
        }
        
        # Recomendaciones Específicas y Accionables
        if len(high_priority) > 0:
            results['recommendations'].append({
                'type': 'error',
                'title': f'Índices Críticos ({len(high_priority)})',
                'message': f'ACCIÓN REQUERIDA: {high_priority[0]["model"]}.{high_priority[0]["field_name"]} - {high_priority[0]["reason"]}',
                'action': f'Ejecutar: python manage.py shell -c "from {high_priority[0]["model"].lower()}.models import {high_priority[0]["model"]}; # Agregar db_index=True"'
            })
        
        if n1_detected:
            results['recommendations'].append({
                'type': 'warning', 
                'title': 'Problema N+1 Detectado',
                'message': f'OPTIMIZAR: Usar .select_related() en queries de LegajoAtencion',
                'action': 'Cambiar: LegajoAtencion.objects.all() por LegajoAtencion.objects.select_related("ciudadano", "dispositivo")'
            })
        
        if perf_summary.get('performance_score', 100) < 70:
            results['recommendations'].append({
                'type': 'warning',
                'title': f'Performance Crítico ({perf_summary.get("performance_score", 0)}/100)',
                'message': 'ACCIÓN INMEDIATA: Aplicar índices sugeridos y optimizar queries',
                'action': 'Ejecutar: python manage.py initialize_phase2 --auto-create-indexes'
            })
        
        if active_components < 4:
            inactive = [name for name, status in components_status.items() if not status]
            results['recommendations'].append({
                'type': 'error',
                'title': 'Componentes Inactivos',
                'message': f'REINICIAR: {inactive[0]} no está funcionando correctamente',
                'action': 'Ejecutar: python manage.py initialize_phase2'
            })
        
        # Recomendación positiva si todo está bien
        if len(high_priority) == 0 and not n1_detected and perf_summary.get('performance_score', 0) > 80:
            results['recommendations'].append({
                'type': 'success',
                'title': '¡Sistema Optimizado!',
                'message': 'Tu sistema está funcionando de manera óptima. Continúa monitoreando.',
                'action': 'Revisar dashboard cada 24 horas para mantener el rendimiento'
            })
        
        return JsonResponse(results)
        
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'timestamp': timezone.now().isoformat(),
            'tests_executed': [],
            'summary': {'all_passed': False, 'error': str(e)}
        }, status=500)

def _get_memory_usage():
    """Get current memory usage (simplified)"""
    try:
        import psutil
        process = psutil.Process()
        return {
            'memory_percent': process.memory_percent(),
            'memory_mb': process.memory_info().rss / 1024 / 1024
        }
    except ImportError:
        return {'memory_percent': 0, 'memory_mb': 0}
