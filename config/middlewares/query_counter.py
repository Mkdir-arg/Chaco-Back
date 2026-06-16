import logging
from django.db import connection
from django.conf import settings
from django.utils import timezone
from core.performance.performance_analyzer import PerformanceAnalyzer

logger = logging.getLogger(__name__)

class QueryCountMiddleware:
    """Advanced middleware para monitorear queries N+1 y performance"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.analyzer = PerformanceAnalyzer()
        # Global counters for production monitoring
        if not hasattr(self.__class__, 'session_stats'):
            self.__class__.session_stats = {
                'total_requests': 0,
                'total_queries': 0,
                'slow_requests': 0,
                'n1_detected_count': 0,
                'last_reset': timezone.now()
            }

    def __call__(self, request):
        queries_before = len(connection.queries) if settings.DEBUG else 0
        start_time = timezone.now()
        
        response = self.get_response(request)
        
        end_time = timezone.now()
        queries_after = len(connection.queries) if settings.DEBUG else 0
        query_count = queries_after - queries_before if settings.DEBUG else self._estimate_queries(request.path)
        response_time = (end_time - start_time).total_seconds()
        
        # Update session stats
        self.__class__.session_stats['total_requests'] += 1
        self.__class__.session_stats['total_queries'] += query_count
        if response_time > 1.0:
            self.__class__.session_stats['slow_requests'] += 1
        
        # Thresholds por tipo de vista (Phase 6 optimized)
        thresholds = {
            '/conversaciones/': 6,   # Phase 5 optimized (services improved)
            '/legajos/': 6,          # Phase 4 optimized
            '/dashboard/': 4,        # Phase 4 optimized
            '/core/': 2,             # Phase 5 optimized (audit service improved)
            '/users/': 5,            # Phase 2 optimized
            '/configuracion/': 6,    # Phase 3 optimized
            '/portal/': 4,           # Phase 4 optimized
            '/tramites/': 5,         # Phase 4 optimized
            '/admin/': 3,            # Phase 6 optimized (admin interfaces)
            '/api/': 4,              # Phase 3 optimized
        }
        
        threshold = 5   # Default (Phase 6 optimized)
        for path, limit in thresholds.items():
            if request.path.startswith(path):
                threshold = limit
                break
        
        if query_count > threshold:
            # Advanced analysis for high query counts
            if settings.DEBUG:
                recent_queries = connection.queries[queries_before:queries_after]
                analysis = self.analyzer.analyze_queries(recent_queries)
                if analysis['n1_detected']:
                    self.__class__.session_stats['n1_detected_count'] += 1
            
            alert_msg = (
                f"Performance Alert: {request.path} executed {query_count} queries "
                f"(threshold: {threshold}) in {response_time:.3f}s - User: {request.user}"
            )
            
            logger.warning(alert_msg)
        
        # Enhanced headers for debugging
        response['X-Query-Count'] = str(query_count)
        response['X-Response-Time'] = f'{response_time:.3f}s'
        response['X-Performance-Score'] = str(self._calculate_request_score(query_count, response_time))
        response['X-Path'] = request.path
        
        return response
    
    def _estimate_queries(self, path):
        """Estimate query count based on path for production monitoring"""
        estimates = {
            '/legajos/': 8,
            '/conversaciones/': 6,
            '/dashboard/': 4,
            '/admin/': 5,
            '/performance-dashboard/': 2,
        }
        
        for pattern, count in estimates.items():
            if path.startswith(pattern):
                return count
        return 3  # Default estimate
    
    @classmethod
    def get_session_stats(cls):
        """Get current session statistics"""
        return cls.session_stats.copy()
    
    def _calculate_request_score(self, query_count, response_time):
        """Calculate performance score for request (0-100)"""
        score = 100
        
        # Penalize for high query count
        if query_count > 10:
            score -= min(50, (query_count - 10) * 5)
        
        # Penalize for slow response
        if response_time > 1.0:
            score -= min(30, (response_time - 1.0) * 20)
        
        return max(0, int(score))