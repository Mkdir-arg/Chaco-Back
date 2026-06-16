# core/monitoring.py
"""
Sistema de monitoreo avanzado
Integra métricas de sistema, aplicación y base de datos
"""
import time
import psutil
import threading
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from collections import defaultdict, deque
import json

class SystemMonitor:
    """Monitor de métricas del sistema"""
    
    def __init__(self):
        self.metrics_history = deque(maxlen=1000)  # Últimas 1000 métricas
        self.alerts = []
        self.start_time = time.time()
    
    def collect_system_metrics(self):
        """Recolecta métricas del sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Conexiones de red
            net_io = psutil.net_io_counters()
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'cpu': {
                    'percent': cpu_percent,
                    'count': psutil.cpu_count(),
                    'load_avg': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'percent': memory.percent,
                    'used': memory.used
                },
                'disk': {
                    'total': disk.total,
                    'used': disk.used,
                    'free': disk.free,
                    'percent': disk.percent
                },
                'network': {
                    'bytes_sent': net_io.bytes_sent,
                    'bytes_recv': net_io.bytes_recv,
                    'packets_sent': net_io.packets_sent,
                    'packets_recv': net_io.packets_recv
                }
            }
            
            # Guardar en cache para dashboard
            cache.set('system_metrics', metrics, 60)
            self.metrics_history.append(metrics)
            
            # Verificar alertas
            self._check_system_alerts(metrics)
            
            return metrics
            
        except Exception as e:
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    def collect_django_metrics(self):
        """Recolecta métricas específicas de Django"""
        try:
            # Conexiones de base de datos
            db_connections = len(connection.queries)
            
            # Cache stats
            cache_stats = self._get_cache_stats()
            
            # Sesiones activas (aproximado)
            active_sessions = self._get_active_sessions()
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'database': {
                    'queries_count': db_connections,
                    'slow_queries': self._count_slow_queries(),
                    'connection_pool': self._get_db_pool_stats()
                },
                'cache': cache_stats,
                'sessions': {
                    'active': active_sessions,
                    'total': self._get_total_sessions()
                },
                'uptime': time.time() - self.start_time
            }
            
            cache.set('django_metrics', metrics, 60)
            return metrics
            
        except Exception as e:
            return {'error': str(e), 'timestamp': timezone.now().isoformat()}
    
    def collect_application_metrics(self):
        """Recolecta métricas específicas de la aplicación"""
        try:
            from legajos.models import Ciudadano
            from conversaciones.models import Conversacion, Mensaje
            from users.models import User
            from django.db.models import Count, Q
            
            hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0)
            hace_24h = timezone.now() - timedelta(days=1)
            
            # Optimizado: Queries agregadas
            user_stats = User.objects.aggregate(
                total=Count('id'),
                active_today=Count('id', filter=Q(last_login__gte=hace_24h))
            )
            
            ciudadano_stats = Ciudadano.objects.aggregate(
                total=Count('id'),
                created_today=Count('id', filter=Q(creado__gte=hoy_inicio))
            )
            
            conversacion_stats = Conversacion.objects.aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(estado='ACTIVA'))
            )
            
            messages_today = Mensaje.objects.filter(fecha_envio__gte=hoy_inicio).count()
            
            metrics = {
                'timestamp': timezone.now().isoformat(),
                'users': {
                    'total': user_stats['total'],
                    'active_today': user_stats['active_today'],
                    'online_now': self._get_online_users()
                },
                'ciudadanos': ciudadano_stats,
                'conversaciones': {
                    'total': conversacion_stats['total'],
                    'active': conversacion_stats['active'],
                    'messages_today': messages_today
                },
                'performance': {
                    'avg_response_time': self._get_avg_response_time(),
                    'error_rate': self._get_error_rate(),
                    'throughput': self._get_throughput()
                }
            }
            
            cache.set('application_metrics', metrics, 60)
            return metrics
            
        except ImportError as e:
            import logging
            logging.error(f"Error importando modelos: {e}")
            return {'error': 'models_unavailable', 'timestamp': timezone.now().isoformat()}
        except Exception as e:
            import logging
            logging.error(f"Error recolectando métricas de aplicación: {e}", exc_info=True)
            return {'error': 'collection_failed', 'timestamp': timezone.now().isoformat()}
    
    def get_comprehensive_metrics(self):
        """Obtiene todas las métricas en un solo objeto"""
        return {
            'system': self.collect_system_metrics(),
            'django': self.collect_django_metrics(),
            'application': self.collect_application_metrics(),
            'alerts': self.get_active_alerts()
        }
    
    def get_active_alerts(self):
        """Obtiene alertas activas"""
        # Limpiar alertas viejas (más de 1 hora)
        cutoff = timezone.now() - timedelta(hours=1)
        self.alerts = [alert for alert in self.alerts if alert['timestamp'] > cutoff]
        return self.alerts
    
    def _check_system_alerts(self, metrics):
        """Verifica y genera alertas del sistema"""
        now = timezone.now()
        
        # CPU alto
        if metrics['cpu']['percent'] > 80:
            self._add_alert('high_cpu', f"CPU usage: {metrics['cpu']['percent']:.1f}%", 'warning')
        
        # Memoria alta
        if metrics['memory']['percent'] > 85:
            self._add_alert('high_memory', f"Memory usage: {metrics['memory']['percent']:.1f}%", 'warning')
        
        # Disco lleno
        if metrics['disk']['percent'] > 90:
            self._add_alert('disk_full', f"Disk usage: {metrics['disk']['percent']:.1f}%", 'critical')
    
    def _add_alert(self, alert_type, message, severity):
        """Añade una alerta"""
        alert = {
            'type': alert_type,
            'message': message,
            'severity': severity,
            'timestamp': timezone.now(),
            'resolved': False
        }
        self.alerts.append(alert)
    
    def _get_cache_stats(self):
        """Obtiene estadísticas del cache"""
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            return {
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'memory_used': info.get('used_memory', 0),
                'connected_clients': info.get('connected_clients', 0)
            }
        except ImportError:
            return {'hits': 0, 'misses': 0, 'memory_used': 0, 'connected_clients': 0, 'error': 'redis_unavailable'}
        except Exception as e:
            import logging
            logging.warning(f"Error obteniendo stats de Redis: {e}")
            return {'hits': 0, 'misses': 0, 'memory_used': 0, 'connected_clients': 0, 'error': str(e)}
    
    def _get_active_sessions(self):
        """Cuenta sesiones activas aproximadas"""
        try:
            from django.contrib.sessions.models import Session
            return Session.objects.filter(
                expire_date__gte=timezone.now()
            ).count()
        except:
            return 0
    
    def _get_total_sessions(self):
        """Cuenta total de sesiones"""
        try:
            from django.contrib.sessions.models import Session
            return Session.objects.count()
        except:
            return 0
    
    def _count_slow_queries(self):
        """Cuenta queries lentas"""
        slow_count = 0
        for query in connection.queries[-50:]:  # Últimas 50 queries
            if float(query.get('time', 0)) > 0.1:  # > 100ms
                slow_count += 1
        return slow_count
    
    def _get_db_pool_stats(self):
        """Estadísticas del pool de conexiones"""
        return {
            'active': len(connection.queries),
            'max_connections': 100  # Configurado en settings
        }
    
    def _get_online_users(self):
        """Usuarios online (últimos 5 minutos)"""
        try:
            from users.models import User
            return User.objects.filter(
                last_login__gte=timezone.now() - timedelta(minutes=5)
            ).count()
        except Exception as e:
            import logging
            logging.debug(f"Error contando usuarios online: {e}")
            return 0
    
    def _get_avg_response_time(self):
        """Tiempo promedio de respuesta"""
        # Obtener de middleware de performance
        metrics = cache.get('performance_metrics', {})
        return metrics.get('avg_response_time', 0)
    
    def _get_error_rate(self):
        """Tasa de errores"""
        metrics = cache.get('performance_metrics', {})
        return metrics.get('error_rate', 0)
    
    def _get_throughput(self):
        """Throughput (requests por segundo)"""
        metrics = cache.get('performance_metrics', {})
        return metrics.get('throughput', 0)

# Instancia global del monitor
system_monitor = SystemMonitor()

class MonitoringMiddleware:
    """Middleware para recolectar métricas de requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_times = deque(maxlen=1000)
        self.error_count = 0
        self.request_count = 0
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Calcular tiempo de respuesta
        response_time = time.time() - start_time
        self.request_times.append(response_time)
        self.request_count += 1
        
        # Contar errores
        if response.status_code >= 400:
            self.error_count += 1
        
        # Actualizar métricas en cache
        self._update_performance_metrics()
        
        return response
    
    def _update_performance_metrics(self):
        """Actualiza métricas de performance"""
        if self.request_times:
            avg_time = sum(self.request_times) / len(self.request_times)
            error_rate = (self.error_count / self.request_count) * 100 if self.request_count > 0 else 0
            throughput = len(self.request_times) / 60  # requests por minuto
            
            metrics = {
                'avg_response_time': avg_time,
                'error_rate': error_rate,
                'throughput': throughput,
                'total_requests': self.request_count,
                'total_errors': self.error_count
            }
            
            cache.set('performance_metrics', metrics, 300)