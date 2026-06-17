from django.db import connection
from django.conf import settings
from django.utils import timezone
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

class PerformanceAnalyzer:
    """Advanced performance analysis and N+1 detection"""
    
    def __init__(self):
        self.query_patterns = defaultdict(int)
        self.n1_patterns = []
        
    def analyze_queries(self, queries):
        """Analyze queries for N+1 patterns"""
        results = {
            'total_queries': len(queries),
            'n1_detected': False,
            'similar_queries': 0,
            'recommendations': []
        }
        
        # Group similar queries
        query_groups = defaultdict(list)
        for query in queries:
            sql = query.get('sql', '')
            # Normalize query by removing specific IDs
            normalized = re.sub(r'\b\d+\b', 'ID', sql)
            query_groups[normalized].append(query)
        
        # Detect N+1 patterns
        for normalized_sql, query_list in query_groups.items():
            if len(query_list) > 3:  # More than 3 similar queries
                results['n1_detected'] = True
                results['similar_queries'] += len(query_list)
                
                # Generate recommendation
                if 'SELECT' in normalized_sql and 'WHERE' in normalized_sql:
                    if 'JOIN' not in normalized_sql:
                        results['recommendations'].append({
                            'type': 'select_related',
                            'query': normalized_sql[:100],
                            'count': len(query_list),
                            'suggestion': 'Consider using select_related() for ForeignKey relationships'
                        })
                    else:
                        results['recommendations'].append({
                            'type': 'prefetch_related',
                            'query': normalized_sql[:100],
                            'count': len(query_list),
                            'suggestion': 'Consider using prefetch_related() for reverse relationships'
                        })
        
        return results
    
    def get_slow_queries(self, queries, threshold=0.1):
        """Identify slow queries"""
        slow_queries = []
        for query in queries:
            time = float(query.get('time', 0))
            if time > threshold:
                slow_queries.append({
                    'sql': query['sql'][:200],
                    'time': time,
                    'recommendation': 'Consider adding database indexes or optimizing query'
                })
        return slow_queries
    
    def generate_report(self):
        """Generate performance analysis report"""
        queries = connection.queries[-100:]  # Last 100 queries only
        analysis = self.analyze_queries(queries)
        slow_queries = self.get_slow_queries(queries)
        
        # Clear old queries to get fresh data
        if len(connection.queries) > 200:
            connection.queries = connection.queries[-50:]
        
        report = {
            'timestamp': timezone.now().isoformat(),
            'total_queries': len(queries),
            'n1_detected': analysis['n1_detected'],
            'similar_queries': analysis['similar_queries'],
            'slow_queries_count': len(slow_queries),
            'recommendations': analysis['recommendations'],
            'slow_queries': slow_queries[:5],
            'performance_score': self._calculate_score(analysis, slow_queries),
            'session_info': {
                'total_session_queries': len(connection.queries),
                'recent_activity': len(queries)
            }
        }
        
        return report
    
    def _calculate_score(self, analysis, slow_queries):
        """Calculate performance score (0-100)"""
        score = 100
        
        # Penalize for high query count
        if analysis['total_queries'] > 50:
            score -= min(30, analysis['total_queries'] - 50)
        
        # Penalize for N+1 queries
        if analysis['n1_detected']:
            score -= min(40, analysis['similar_queries'] * 2)
        
        # Penalize for slow queries
        score -= min(20, len(slow_queries) * 5)
        
        return max(0, score)

class QueryOptimizationSuggester:
    """Suggest optimizations based on query patterns"""
    
    @staticmethod
    def suggest_optimizations(model_name, query_pattern):
        """Generate optimization suggestions"""
        suggestions = []
        
        if 'SELECT' in query_pattern and 'WHERE' in query_pattern:
            if model_name:
                suggestions.append({
                    'type': 'select_related',
                    'code': f'{model_name}.objects.select_related("field_name")',
                    'description': 'Use select_related() for ForeignKey relationships'
                })
                
                suggestions.append({
                    'type': 'prefetch_related', 
                    'code': f'{model_name}.objects.prefetch_related("reverse_field")',
                    'description': 'Use prefetch_related() for reverse relationships'
                })
                
                suggestions.append({
                    'type': 'only_fields',
                    'code': f'{model_name}.objects.only("field1", "field2")',
                    'description': 'Use only() to limit fields when not all are needed'
                })
        
        return suggestions