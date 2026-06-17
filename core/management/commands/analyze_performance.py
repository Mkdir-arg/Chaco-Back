from django.core.management.base import BaseCommand
from core.performance.performance_analyzer import PerformanceAnalyzer
import json

class Command(BaseCommand):
    help = 'Analyze system performance and generate report'
    
    def add_arguments(self, parser):
        parser.add_argument('--output', choices=['console', 'json'], default='console')
    
    def handle(self, *args, **options):
        analyzer = PerformanceAnalyzer()
        report = analyzer.generate_report()
        
        if options['output'] == 'json':
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self.stdout.write('=== PERFORMANCE ANALYSIS REPORT ===')
            self.stdout.write(f'Total Queries: {report["total_queries"]}')
            self.stdout.write(f'Performance Score: {report["performance_score"]}/100')
            
            if report['n1_detected']:
                self.stdout.write(
                    self.style.ERROR(f'N+1 Detected: {report["similar_queries"]} similar queries')
                )
            else:
                self.stdout.write(self.style.SUCCESS('No N+1 patterns detected'))
            
            if report['slow_queries_count'] > 0:
                self.stdout.write(
                    self.style.WARNING(f'Slow Queries: {report["slow_queries_count"]}')
                )
            
            if report['recommendations']:
                self.stdout.write('\n=== RECOMMENDATIONS ===')
                for rec in report['recommendations']:
                    self.stdout.write(f'- {rec["suggestion"]} (Count: {rec["count"]})')