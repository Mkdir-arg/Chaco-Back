import logging
import time
import threading
from collections import defaultdict, Counter
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import hashlib
import re
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class IntelligentQueryOptimizer:
    """Motor inteligente de optimización de queries"""
    
    def __init__(self):
        self.query_patterns = defaultdict(list)
        self.optimization_cache = {}
        self.performance_stats = defaultdict(dict)
        self.running = False
        self.thread = None
        
        # Patrones de optimización
        self.optimization_patterns = {
            'select_related': [
                r'SELECT.*FROM\s+(\w+).*JOIN\s+(\w+)',
                r'\.(\w+)_id\s*=\s*\w+\.id'
            ],
            'prefetch_related': [
                r'SELECT.*FROM\s+(\w+).*WHERE\s+\w+_id\s+IN\s*\(',
                r'\.filter\(\w+__in='
            ],
            'only_fields': [
                r'SELECT\s+\*\s+FROM',
                r'\.all\(\)\.values\('
            ],
            'bulk_operations': [
                r'INSERT\s+INTO.*VALUES.*,.*,',
                r'UPDATE.*WHERE.*IN\s*\('
            ]
        }
    
    def start_optimization_engine(self):
        """Inicia el motor de optimización"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._optimization_worker, daemon=True)
            self.thread.start()
            logger.info("Motor de optimización inteligente iniciado")
    
    def stop_optimization_engine(self):
        """Detiene el motor de optimización"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Motor de optimización detenido")
    
    def _optimization_worker(self):
        """Worker que analiza y optimiza queries continuamente"""
        while self.running:
            try:
                self.analyze_query_patterns()
                self.generate_optimization_suggestions()
                self.update_performance_metrics()
                time.sleep(300)  # Analizar cada 5 minutos
            except Exception as e:
                logger.error(f"Error en motor de optimización: {e}")
                time.sleep(60)
    
    def analyze_query_patterns(self):
        """Analiza patrones de queries en tiempo real"""
        try:
            with connection.cursor() as cursor:
                # Obtener queries recientes del performance_schema
                cursor.execute("""
                    SELECT 
                        digest_text,
                        count_star,
                        avg_timer_wait/1000000000 as avg_time_ms,
                        sum_timer_wait/1000000000 as total_time_ms,
                        sum_rows_examined,
                        sum_rows_sent
                    FROM performance_schema.events_statements_summary_by_digest 
                    WHERE digest_text IS NOT NULL 
                    AND count_star > 1
                    ORDER BY avg_timer_wait DESC 
                    LIMIT 100
                """)
                
                for row in cursor.fetchall():
                    query_text, count, avg_time, total_time, rows_examined, rows_sent = row
                    
                    # Analizar patrón de query
                    pattern_type = self._identify_query_pattern(query_text)
                    query_hash = hashlib.md5(query_text.encode()).hexdigest()
                    
                    # Almacenar estadísticas
                    self.performance_stats[query_hash] = {
                        'query': query_text,
                        'pattern_type': pattern_type,
                        'count': count,
                        'avg_time_ms': avg_time,
                        'total_time_ms': total_time,
                        'rows_examined': rows_examined,
                        'rows_sent': rows_sent,
                        'efficiency_ratio': rows_sent / max(rows_examined, 1),
                        'timestamp': time.time()
                    }
                    
                    # Detectar problemas
                    if avg_time > 100:  # Queries > 100ms
                        self._flag_slow_query(query_hash, query_text, avg_time)
                    
                    if rows_examined / max(rows_sent, 1) > 10:  # Ratio ineficiente
                        self._flag_inefficient_query(query_hash, query_text, rows_examined, rows_sent)
        
        except Exception as e:
            logger.error(f"Error analizando patrones de queries: {e}")
    
    def _identify_query_pattern(self, query_text: str) -> str:
        """Identifica el tipo de patrón de query"""
        query_lower = query_text.lower()
        
        if 'select' in query_lower and 'join' in query_lower:
            return 'join_query'
        elif 'select' in query_lower and 'where' in query_lower and 'in (' in query_lower:
            return 'in_query'
        elif 'select *' in query_lower:
            return 'select_all'
        elif 'insert' in query_lower and query_lower.count('values') > 1:
            return 'bulk_insert'
        elif 'update' in query_lower and 'where' in query_lower:
            return 'update_query'
        else:
            return 'other'
    
    def _flag_slow_query(self, query_hash: str, query_text: str, avg_time: float):
        """Marca una query como lenta y sugiere optimizaciones"""
        optimization = self._suggest_query_optimization(query_text)
        
        cache_key = f"slow_query_{query_hash}"
        cache.set(cache_key, {
            'query': query_text,
            'avg_time': avg_time,
            'optimization': optimization,
            'flagged_at': time.time()
        }, 3600)  # Cache por 1 hora
        
        logger.warning(f"Query lenta detectada ({avg_time:.2f}ms): {query_text[:100]}...")
    
    def _flag_inefficient_query(self, query_hash: str, query_text: str, examined: int, sent: int):
        """Marca una query como ineficiente"""
        ratio = examined / max(sent, 1)
        
        cache_key = f"inefficient_query_{query_hash}"
        cache.set(cache_key, {
            'query': query_text,
            'examined_rows': examined,
            'sent_rows': sent,
            'efficiency_ratio': ratio,
            'flagged_at': time.time()
        }, 3600)
        
        logger.warning(f"Query ineficiente detectada (ratio {ratio:.1f}): {query_text[:100]}...")
    
    def _suggest_query_optimization(self, query_text: str) -> Dict:
        """Sugiere optimizaciones para una query específica"""
        suggestions = []
        
        # Detectar necesidad de select_related
        if re.search(r'JOIN\s+\w+', query_text, re.IGNORECASE):
            suggestions.append({
                'type': 'select_related',
                'description': 'Usar select_related() para JOINs',
                'example': '.select_related("foreign_key_field")',
                'impact': 'High'
            })
        
        # Detectar necesidad de prefetch_related
        if re.search(r'WHERE\s+\w+_id\s+IN\s*\(', query_text, re.IGNORECASE):
            suggestions.append({
                'type': 'prefetch_related',
                'description': 'Usar prefetch_related() para relaciones inversas',
                'example': '.prefetch_related("reverse_field")',
                'impact': 'High'
            })
        
        # Detectar SELECT *
        if re.search(r'SELECT\s+\*', query_text, re.IGNORECASE):
            suggestions.append({
                'type': 'only_fields',
                'description': 'Limitar campos con only() o values()',
                'example': '.only("field1", "field2")',
                'impact': 'Medium'
            })
        
        # Detectar falta de índices
        if re.search(r'WHERE\s+\w+\s*=', query_text, re.IGNORECASE):
            suggestions.append({
                'type': 'index',
                'description': 'Considerar agregar índice en campo de filtro',
                'example': 'db_index=True en el modelo',
                'impact': 'High'
            })
        
        return {
            'suggestions': suggestions,
            'generated_at': time.time()
        }
    
    def generate_optimization_suggestions(self):
        """Genera sugerencias de optimización basadas en patrones"""
        try:
            # Analizar queries más frecuentes
            frequent_queries = sorted(
                self.performance_stats.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:20]
            
            # Analizar queries más lentas
            slow_queries = sorted(
                self.performance_stats.items(),
                key=lambda x: x[1]['avg_time_ms'],
                reverse=True
            )[:10]
            
            # Generar recomendaciones globales
            recommendations = {
                'frequent_optimizations': [],
                'slow_query_fixes': [],
                'index_suggestions': [],
                'generated_at': time.time()
            }
            
            for query_hash, stats in frequent_queries:
                if stats['avg_time_ms'] > 50:  # Queries frecuentes y lentas
                    optimization = self._suggest_query_optimization(stats['query'])
                    recommendations['frequent_optimizations'].append({
                        'query_hash': query_hash,
                        'count': stats['count'],
                        'avg_time': stats['avg_time_ms'],
                        'optimization': optimization
                    })
            
            for query_hash, stats in slow_queries:
                optimization = self._suggest_query_optimization(stats['query'])
                recommendations['slow_query_fixes'].append({
                    'query_hash': query_hash,
                    'avg_time': stats['avg_time_ms'],
                    'optimization': optimization
                })
            
            # Cache recomendaciones
            cache.set('query_optimization_recommendations', recommendations, 1800)  # 30 min
            
        except Exception as e:
            logger.error(f"Error generando sugerencias de optimización: {e}")
    
    def update_performance_metrics(self):
        """Actualiza métricas de performance"""
        try:
            metrics = {
                'total_queries_analyzed': len(self.performance_stats),
                'slow_queries_count': len([
                    s for s in self.performance_stats.values() 
                    if s['avg_time_ms'] > 100
                ]),
                'inefficient_queries_count': len([
                    s for s in self.performance_stats.values() 
                    if s['efficiency_ratio'] < 0.1
                ]),
                'avg_query_time': sum(
                    s['avg_time_ms'] for s in self.performance_stats.values()
                ) / max(len(self.performance_stats), 1),
                'updated_at': time.time()
            }
            
            cache.set('query_performance_metrics', metrics, 300)  # 5 min
            
        except Exception as e:
            logger.error(f"Error actualizando métricas: {e}")
    
    def get_optimization_report(self) -> Dict:
        """Obtiene reporte completo de optimización"""
        recommendations = cache.get('query_optimization_recommendations', {})
        metrics = cache.get('query_performance_metrics', {})
        
        return {
            'recommendations': recommendations,
            'metrics': metrics,
            'top_slow_queries': self._get_top_slow_queries(),
            'optimization_opportunities': self._get_optimization_opportunities()
        }
    
    def _get_top_slow_queries(self) -> List[Dict]:
        """Obtiene las queries más lentas"""
        return sorted(
            [
                {
                    'query': stats['query'][:200] + '...' if len(stats['query']) > 200 else stats['query'],
                    'avg_time_ms': stats['avg_time_ms'],
                    'count': stats['count'],
                    'pattern_type': stats['pattern_type']
                }
                for stats in self.performance_stats.values()
            ],
            key=lambda x: x['avg_time_ms'],
            reverse=True
        )[:10]
    
    def _get_optimization_opportunities(self) -> List[Dict]:
        """Identifica oportunidades de optimización"""
        opportunities = []
        
        # Buscar patrones N+1
        n1_patterns = [
            stats for stats in self.performance_stats.values()
            if stats['pattern_type'] == 'in_query' and stats['count'] > 10
        ]
        
        if n1_patterns:
            opportunities.append({
                'type': 'n1_queries',
                'count': len(n1_patterns),
                'description': 'Posibles patrones N+1 detectados',
                'impact': 'High'
            })
        
        # Buscar SELECT * frecuentes
        select_all = [
            stats for stats in self.performance_stats.values()
            if stats['pattern_type'] == 'select_all' and stats['count'] > 5
        ]
        
        if select_all:
            opportunities.append({
                'type': 'select_all',
                'count': len(select_all),
                'description': 'Queries con SELECT * que pueden optimizarse',
                'impact': 'Medium'
            })
        
        return opportunities

# Instancia global
query_optimizer = IntelligentQueryOptimizer()