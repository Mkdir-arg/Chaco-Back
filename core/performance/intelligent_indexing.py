import logging
import threading
import time
from collections import defaultdict, Counter
from django.db import connection, models
from django.apps import apps
from django.core.cache import cache
from typing import Dict, List, Tuple, Set
import re

logger = logging.getLogger(__name__)

class IntelligentIndexManager:
    """Gestor inteligente de índices que analiza patrones de uso"""
    
    def __init__(self):
        self.query_patterns = defaultdict(list)
        self.index_usage_stats = defaultdict(dict)
        self.suggested_indexes = {}
        self.running = False
        self.thread = None
        
        # Patrones de queries que se benefician de índices
        self.index_patterns = {
            'equality_filter': r'WHERE\s+(\w+)\s*=\s*',
            'range_filter': r'WHERE\s+(\w+)\s*[<>]=?\s*',
            'in_filter': r'WHERE\s+(\w+)\s+IN\s*\(',
            'like_filter': r'WHERE\s+(\w+)\s+LIKE\s*',
            'order_by': r'ORDER\s+BY\s+(\w+)',
            'group_by': r'GROUP\s+BY\s+(\w+)',
            'join_condition': r'JOIN\s+\w+\s+ON\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)'
        }
    
    def start_index_analyzer(self):
        """Inicia el analizador de índices"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._index_analyzer_worker, daemon=True)
            self.thread.start()
            logger.info("Analizador inteligente de índices iniciado")
    
    def stop_index_analyzer(self):
        """Detiene el analizador"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Analizador de índices detenido")
    
    def _index_analyzer_worker(self):
        """Worker que analiza uso de índices continuamente"""
        while self.running:
            try:
                self.analyze_query_patterns_for_indexes()
                self.analyze_existing_index_usage()
                self.generate_index_suggestions()
                self.cleanup_unused_indexes()
                time.sleep(1800)  # Analizar cada 30 minutos
            except Exception as e:
                logger.error(f"Error en analizador de índices: {e}")
                time.sleep(300)
    
    def analyze_query_patterns_for_indexes(self):
        """Analiza patrones de queries para sugerir índices"""
        try:
            with connection.cursor() as cursor:
                # Obtener queries que no usan índices eficientemente
                cursor.execute("""
                    SELECT 
                        digest_text,
                        count_star,
                        avg_timer_wait/1000000000 as avg_time_ms,
                        sum_rows_examined,
                        sum_rows_sent,
                        sum_select_scan,
                        sum_select_full_join
                    FROM performance_schema.events_statements_summary_by_digest 
                    WHERE digest_text IS NOT NULL 
                    AND (sum_select_scan > 0 OR sum_select_full_join > 0)
                    AND count_star > 5
                    ORDER BY sum_rows_examined DESC 
                    LIMIT 50
                """)
                
                for row in cursor.fetchall():
                    query_text, count, avg_time, rows_examined, rows_sent, scans, full_joins = row
                    
                    # Analizar query para identificar campos que necesitan índices
                    suggested_fields = self._analyze_query_for_indexes(query_text)
                    
                    if suggested_fields:
                        for table, fields in suggested_fields.items():
                            self._record_index_suggestion(table, fields, {
                                'query_count': count,
                                'avg_time_ms': avg_time,
                                'rows_examined': rows_examined,
                                'scan_count': scans,
                                'full_join_count': full_joins
                            })
        
        except Exception as e:
            logger.error(f"Error analizando patrones para índices: {e}")
    
    def _analyze_query_for_indexes(self, query_text: str) -> Dict[str, List[str]]:
        """Analiza una query específica para sugerir índices"""
        suggestions = defaultdict(list)
        
        # Buscar patrones de filtros WHERE
        for pattern_name, pattern in self.index_patterns.items():
            matches = re.findall(pattern, query_text, re.IGNORECASE)
            
            for match in matches:
                if isinstance(match, tuple):
                    # Para JOINs
                    for field in match:
                        table = self._extract_table_from_query(query_text, field)
                        if table:
                            suggestions[table].append(field)
                else:
                    # Para otros patrones
                    table = self._extract_table_from_query(query_text, match)
                    if table:
                        suggestions[table].append(match)
        
        return dict(suggestions)
    
    def _extract_table_from_query(self, query_text: str, field: str) -> str:
        """Extrae el nombre de la tabla de una query"""
        # Buscar patrón FROM table_name
        from_match = re.search(r'FROM\s+(\w+)', query_text, re.IGNORECASE)
        if from_match:
            return from_match.group(1)
        
        # Buscar patrón table.field
        table_field_match = re.search(rf'(\w+)\.{field}', query_text, re.IGNORECASE)
        if table_field_match:
            return table_field_match.group(1)
        
        return None
    
    def _record_index_suggestion(self, table: str, fields: List[str], stats: Dict):
        """Registra una sugerencia de índice"""
        for field in fields:
            key = f"{table}.{field}"
            
            if key not in self.suggested_indexes:
                self.suggested_indexes[key] = {
                    'table': table,
                    'field': field,
                    'suggestion_count': 0,
                    'total_query_count': 0,
                    'avg_impact_time': 0.0,
                    'first_suggested': time.time()
                }
            
            suggestion = self.suggested_indexes[key]
            suggestion['suggestion_count'] += 1
            suggestion['total_query_count'] += stats['query_count']
            
            # Calcular impacto promedio
            current_avg = suggestion['avg_impact_time']
            count = suggestion['suggestion_count']
            suggestion['avg_impact_time'] = (
                (current_avg * (count - 1) + stats['avg_time_ms']) / count
            )
    
    def analyze_existing_index_usage(self):
        """Analiza el uso de índices existentes"""
        try:
            with connection.cursor() as cursor:
                # Obtener estadísticas de uso de índices
                cursor.execute("""
                    SELECT 
                        object_schema,
                        object_name,
                        index_name,
                        count_read,
                        count_write,
                        count_fetch,
                        sum_timer_read,
                        sum_timer_write,
                        sum_timer_fetch
                    FROM performance_schema.table_io_waits_summary_by_index_usage
                    WHERE object_schema = DATABASE()
                    AND index_name IS NOT NULL
                """)
                
                for row in cursor.fetchall():
                    schema, table, index_name, reads, writes, fetches, read_time, write_time, fetch_time = row
                    
                    key = f"{table}.{index_name}"
                    self.index_usage_stats[key] = {
                        'table': table,
                        'index_name': index_name,
                        'read_count': reads,
                        'write_count': writes,
                        'fetch_count': fetches,
                        'read_time_ns': read_time,
                        'write_time_ns': write_time,
                        'fetch_time_ns': fetch_time,
                        'last_analyzed': time.time()
                    }
        
        except Exception as e:
            logger.error(f"Error analizando uso de índices existentes: {e}")
    
    def generate_index_suggestions(self):
        """Genera sugerencias finales de índices"""
        try:
            # Filtrar sugerencias por impacto y frecuencia
            high_impact_suggestions = []
            
            for key, suggestion in self.suggested_indexes.items():
                # Calcular score de prioridad
                priority_score = (
                    suggestion['suggestion_count'] * 0.3 +
                    suggestion['total_query_count'] * 0.4 +
                    (suggestion['avg_impact_time'] / 100) * 0.3  # Normalizar tiempo
                )
                
                if priority_score > 5:  # Umbral de prioridad
                    # Verificar si el índice ya existe
                    if not self._index_exists(suggestion['table'], suggestion['field']):
                        high_impact_suggestions.append({
                            **suggestion,
                            'priority_score': priority_score,
                            'recommended_action': 'CREATE'
                        })
            
            # Ordenar por prioridad
            high_impact_suggestions.sort(key=lambda x: x['priority_score'], reverse=True)
            
            # Cache sugerencias
            cache.set('intelligent_index_suggestions', high_impact_suggestions[:20], 3600)
            
            logger.info(f"Generadas {len(high_impact_suggestions)} sugerencias de índices")
            
        except Exception as e:
            logger.error(f"Error generando sugerencias de índices: {e}")
    
    def _index_exists(self, table: str, field: str) -> bool:
        """Verifica si un índice ya existe"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.statistics 
                    WHERE table_schema = DATABASE() 
                    AND table_name = %s 
                    AND column_name = %s
                """, [table, field])
                
                return cursor.fetchone()[0] > 0
        except:
            return False
    
    def cleanup_unused_indexes(self):
        """Identifica índices no utilizados para limpieza"""
        try:
            unused_indexes = []
            
            for key, stats in self.index_usage_stats.items():
                # Considerar índice no usado si tiene muy pocas lecturas
                if (stats['read_count'] < 10 and 
                    stats['fetch_count'] < 10 and
                    time.time() - stats['last_analyzed'] > 86400 * 7):  # 7 días
                    
                    unused_indexes.append({
                        'table': stats['table'],
                        'index_name': stats['index_name'],
                        'read_count': stats['read_count'],
                        'fetch_count': stats['fetch_count'],
                        'recommended_action': 'CONSIDER_DROP'
                    })
            
            if unused_indexes:
                cache.set('unused_indexes_report', unused_indexes, 3600)
                logger.info(f"Identificados {len(unused_indexes)} índices potencialmente no utilizados")
        
        except Exception as e:
            logger.error(f"Error identificando índices no utilizados: {e}")
    
    def create_recommended_indexes(self, auto_create: bool = False):
        """Crea índices recomendados"""
        suggestions = cache.get('intelligent_index_suggestions', [])
        created_indexes = []
        
        for suggestion in suggestions[:10]:  # Crear solo los top 10
            try:
                if auto_create or self._should_auto_create_index(suggestion):
                    index_name = f"idx_{suggestion['table']}_{suggestion['field']}"
                    
                    with connection.cursor() as cursor:
                        cursor.execute(f"""
                            CREATE INDEX {index_name} 
                            ON {suggestion['table']} ({suggestion['field']})
                        """)
                    
                    created_indexes.append({
                        'table': suggestion['table'],
                        'field': suggestion['field'],
                        'index_name': index_name,
                        'priority_score': suggestion['priority_score']
                    })
                    
                    logger.info(f"Índice creado: {index_name}")
            
            except Exception as e:
                logger.error(f"Error creando índice para {suggestion['table']}.{suggestion['field']}: {e}")
        
        return created_indexes
    
    def _should_auto_create_index(self, suggestion: Dict) -> bool:
        """Determina si un índice debe crearse automáticamente"""
        # Crear automáticamente solo si tiene muy alto impacto
        return (suggestion['priority_score'] > 20 and 
                suggestion['avg_impact_time'] > 200)  # Queries > 200ms
    
    def get_index_report(self) -> Dict:
        """Obtiene reporte completo de índices"""
        suggestions = cache.get('intelligent_index_suggestions', [])
        unused_indexes = cache.get('unused_indexes_report', [])
        
        return {
            'recommended_indexes': suggestions,
            'unused_indexes': unused_indexes,
            'index_usage_stats': dict(self.index_usage_stats),
            'analysis_summary': {
                'total_suggestions': len(suggestions),
                'high_priority_suggestions': len([s for s in suggestions if s['priority_score'] > 15]),
                'unused_indexes_count': len(unused_indexes),
                'last_analysis': time.time()
            }
        }
    
    def analyze_django_models_for_indexes(self):
        """Analiza modelos Django para sugerir índices basados en campos"""
        model_suggestions = []
        
        for model in apps.get_models():
            table_name = model._meta.db_table
            
            for field in model._meta.fields:
                # Sugerir índices para ForeignKeys sin índice
                if isinstance(field, models.ForeignKey) and not field.db_index:
                    model_suggestions.append({
                        'model': model.__name__,
                        'table': table_name,
                        'field': field.column,
                        'field_name': field.name,
                        'reason': 'ForeignKey without index',
                        'priority': 'High'
                    })
                
                # Sugerir índices para campos con unique=True pero sin db_index
                elif field.unique and not field.db_index and not field.primary_key:
                    model_suggestions.append({
                        'model': model.__name__,
                        'table': table_name,
                        'field': field.column,
                        'field_name': field.name,
                        'reason': 'Unique field without index',
                        'priority': 'Medium'
                    })
        
        cache.set('django_model_index_suggestions', model_suggestions, 7200)  # 2 horas
        return model_suggestions

# Instancia global
index_manager = IntelligentIndexManager()