import logging
import threading
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.cache import cache

from .advanced_partitioning import partition_manager
from .intelligent_query_optimizer import query_optimizer
from .advanced_connection_pool import connection_pool
from .intelligent_indexing import index_manager

logger = logging.getLogger(__name__)

class Phase2OptimizationManager:
    """Gestor central de todas las optimizaciones de Fase 2"""
    
    def __init__(self):
        self.components = {
            'partitioning': partition_manager,
            'query_optimizer': query_optimizer,
            'connection_pool': connection_pool,
            'index_manager': index_manager
        }
        self.running = False
        self.stats_thread = None
        
    def initialize_phase2(self):
        """Inicializa todos los componentes de Fase 2"""
        logger.info("🚀 Iniciando FASE 2 - Optimización Avanzada de Base de Datos")
        
        try:
            # 1. Inicializar Connection Pool
            logger.info("📊 Inicializando Connection Pool Avanzado...")
            self.components['connection_pool'].initialize_pools()
            
            # 2. Inicializar Particionamiento
            logger.info("🗂️ Iniciando Sistema de Particionamiento...")
            self.components['partitioning'].start_auto_partitioning()
            
            # 3. Inicializar Query Optimizer
            logger.info("⚡ Iniciando Motor de Optimización de Queries...")
            self.components['query_optimizer'].start_optimization_engine()
            
            # 4. Inicializar Index Manager
            logger.info("🔍 Iniciando Gestor Inteligente de Índices...")
            self.components['index_manager'].start_index_analyzer()
            
            # 5. Iniciar monitoreo de estadísticas
            self.start_stats_monitoring()
            
            # 6. Ejecutar optimizaciones iniciales
            self.run_initial_optimizations()
            
            logger.info("✅ FASE 2 inicializada correctamente")
            
        except Exception as e:
            logger.error(f"❌ Error inicializando Fase 2: {e}")
            raise
    
    def run_initial_optimizations(self):
        """Ejecuta optimizaciones iniciales"""
        logger.info("🔧 Ejecutando optimizaciones iniciales...")
        
        try:
            # Crear particiones futuras
            self.components['partitioning'].create_future_partitions()
            
            # Analizar modelos Django para índices
            self.components['index_manager'].analyze_django_models_for_indexes()
            
            # Generar reporte inicial
            self.generate_initial_report()
            
        except Exception as e:
            logger.error(f"Error en optimizaciones iniciales: {e}")
    
    def start_stats_monitoring(self):
        """Inicia el monitoreo de estadísticas consolidadas"""
        if not self.running:
            self.running = True
            self.stats_thread = threading.Thread(target=self._stats_worker, daemon=True)
            self.stats_thread.start()
            logger.info("📈 Monitoreo de estadísticas iniciado")
    
    def stop_stats_monitoring(self):
        """Detiene el monitoreo de estadísticas"""
        self.running = False
        if self.stats_thread:
            self.stats_thread.join()
    
    def _stats_worker(self):
        """Worker que consolida estadísticas cada 5 minutos"""
        while self.running:
            try:
                self.update_consolidated_stats()
                time.sleep(300)  # 5 minutos
            except Exception as e:
                logger.error(f"Error en worker de estadísticas: {e}")
                time.sleep(60)
    
    def update_consolidated_stats(self):
        """Actualiza estadísticas consolidadas de todos los componentes"""
        try:
            consolidated_stats = {
                'timestamp': time.time(),
                'partitioning': self.components['partitioning'].get_partition_stats(),
                'query_optimization': self.components['query_optimizer'].get_optimization_report(),
                'connection_pool': self.components['connection_pool'].get_stats(),
                'indexing': self.components['index_manager'].get_index_report(),
                'performance_summary': self._calculate_performance_summary()
            }
            
            # Cache estadísticas consolidadas
            cache.set('phase2_consolidated_stats', consolidated_stats, 600)  # 10 min
            
            # Log estadísticas importantes
            self._log_important_stats(consolidated_stats)
            
        except Exception as e:
            logger.error(f"Error actualizando estadísticas consolidadas: {e}")
    
    def _calculate_performance_summary(self):
        """Calcula resumen de performance general"""
        try:
            query_metrics = cache.get('query_performance_metrics', {})
            
            return {
                'avg_query_time_ms': query_metrics.get('avg_query_time', 0),
                'slow_queries_count': query_metrics.get('slow_queries_count', 0),
                'total_queries_analyzed': query_metrics.get('total_queries_analyzed', 0),
                'optimization_opportunities': query_metrics.get('inefficient_queries_count', 0),
                'performance_score': self._calculate_overall_score(query_metrics)
            }
        except:
            return {}
    
    def _calculate_overall_score(self, metrics):
        """Calcula score general de performance (0-100)"""
        if not metrics:
            return 50
        
        avg_time = metrics.get('avg_query_time', 100)
        slow_queries = metrics.get('slow_queries_count', 0)
        total_queries = metrics.get('total_queries_analyzed', 1)
        
        # Score basado en tiempo promedio y porcentaje de queries lentas
        time_score = max(0, 100 - (avg_time / 10))  # 100ms = score 90
        slow_ratio = slow_queries / max(total_queries, 1)
        slow_score = max(0, 100 - (slow_ratio * 200))  # 50% slow = score 0
        
        return int((time_score * 0.6 + slow_score * 0.4))
    
    def _log_important_stats(self, stats):
        """Log estadísticas importantes"""
        try:
            perf_summary = stats.get('performance_summary', {})
            
            if perf_summary.get('performance_score', 0) < 70:
                logger.warning(f"⚠️ Performance score bajo: {perf_summary['performance_score']}")
            
            if perf_summary.get('slow_queries_count', 0) > 10:
                logger.warning(f"⚠️ Muchas queries lentas detectadas: {perf_summary['slow_queries_count']}")
            
            # Log estadísticas de particionamiento
            partition_stats = stats.get('partitioning', {})
            total_partitions = sum(p.get('partition_count', 0) for p in partition_stats.values())
            if total_partitions > 0:
                logger.info(f"📊 Particiones activas: {total_partitions}")
            
        except Exception as e:
            logger.error(f"Error logging estadísticas: {e}")
    
    def generate_initial_report(self):
        """Genera reporte inicial de optimización"""
        try:
            report = {
                'phase2_initialization': {
                    'timestamp': time.time(),
                    'components_initialized': list(self.components.keys()),
                    'status': 'SUCCESS'
                },
                'initial_analysis': {
                    'django_model_suggestions': cache.get('django_model_index_suggestions', []),
                    'partition_tables_configured': len(partition_manager.PARTITION_TABLES),
                    'connection_pools_created': len(connection_pool.pools) if hasattr(connection_pool, 'pools') else 0
                },
                'recommendations': {
                    'immediate_actions': self._get_immediate_recommendations(),
                    'monitoring_setup': 'Monitoreo automático configurado cada 5 minutos',
                    'next_steps': [
                        'Monitorear dashboard de performance',
                        'Revisar sugerencias de índices en 30 minutos',
                        'Verificar creación de particiones automáticas'
                    ]
                }
            }
            
            cache.set('phase2_initial_report', report, 86400)  # 24 horas
            logger.info("📋 Reporte inicial de Fase 2 generado")
            
        except Exception as e:
            logger.error(f"Error generando reporte inicial: {e}")
    
    def _get_immediate_recommendations(self):
        """Obtiene recomendaciones inmediatas"""
        recommendations = []
        
        # Verificar si hay sugerencias de índices de modelos Django
        model_suggestions = cache.get('django_model_index_suggestions', [])
        high_priority = [s for s in model_suggestions if s.get('priority') == 'High']
        
        if high_priority:
            recommendations.append(f"Crear {len(high_priority)} índices de alta prioridad en ForeignKeys")
        
        recommendations.extend([
            "Monitorear queries lentas en los próximos 30 minutos",
            "Verificar uso de memoria después de inicializar connection pool",
            "Revisar logs para confirmar inicio de particionamiento automático"
        ])
        
        return recommendations
    
    def shutdown_phase2(self):
        """Apaga todos los componentes de Fase 2"""
        logger.info("🛑 Apagando componentes de Fase 2...")
        
        try:
            # Detener monitoreo de estadísticas
            self.stop_stats_monitoring()
            
            # Detener componentes
            self.components['partitioning'].stop_auto_partitioning()
            self.components['query_optimizer'].stop_optimization_engine()
            self.components['connection_pool'].stop_monitoring()
            self.components['index_manager'].stop_index_analyzer()
            
            logger.info("✅ Fase 2 apagada correctamente")
            
        except Exception as e:
            logger.error(f"Error apagando Fase 2: {e}")
    
    def get_phase2_status(self):
        """Obtiene estado actual de Fase 2"""
        return {
            'running': self.running,
            'components_status': {
                name: getattr(component, 'running', False) 
                for name, component in self.components.items()
            },
            'last_stats_update': cache.get('phase2_consolidated_stats', {}).get('timestamp'),
            'initial_report': cache.get('phase2_initial_report')
        }
    
    def force_optimization_cycle(self):
        """Fuerza un ciclo completo de optimización"""
        logger.info("🔄 Forzando ciclo de optimización...")
        
        try:
            # Forzar análisis de queries
            self.components['query_optimizer'].analyze_query_patterns()
            self.components['query_optimizer'].generate_optimization_suggestions()
            
            # Forzar análisis de índices
            self.components['index_manager'].analyze_query_patterns_for_indexes()
            self.components['index_manager'].generate_index_suggestions()
            
            # Forzar verificación de particiones
            self.components['partitioning'].create_future_partitions()
            
            # Actualizar estadísticas
            self.update_consolidated_stats()
            
            logger.info("✅ Ciclo de optimización completado")
            
        except Exception as e:
            logger.error(f"Error en ciclo de optimización: {e}")

# Instancia global del gestor
phase2_manager = Phase2OptimizationManager()