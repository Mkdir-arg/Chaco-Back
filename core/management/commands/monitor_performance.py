from django.core.management.base import BaseCommand
from django.db import connection
from core.performance.performance_analyzer import PerformanceAnalyzer
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Monitor system performance in real-time'
    
    def add_arguments(self, parser):
        parser.add_argument('--duration', type=int, default=300, help='Monitoring duration in seconds')
        parser.add_argument('--threshold', type=int, default=10, help='Query count alert threshold')
    
    def handle(self, *args, **options):
        duration = options['duration']
        threshold = options['threshold']
        
        self.stdout.write(f'Starting performance monitoring for {duration} seconds...')
        
        analyzer = PerformanceAnalyzer()
        start_time = time.time()
        
        while time.time() - start_time < duration:
            queries_before = len(connection.queries)
            time.sleep(5)  # Check every 5 seconds
            queries_after = len(connection.queries)
            
            query_count = queries_after - queries_before
            
            if query_count > threshold:
                recent_queries = connection.queries[queries_before:queries_after]
                analysis = analyzer.analyze_queries(recent_queries)
                
                self.stdout.write(
                    self.style.WARNING(
                        f'Alert: {query_count} queries in 5s (threshold: {threshold})'
                    )
                )
                
                if analysis['n1_detected']:
                    self.stdout.write(
                        self.style.ERROR(
                            f'N+1 detected: {analysis["similar_queries"]} similar queries'
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('Monitoring completed'))