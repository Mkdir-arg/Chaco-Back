from django.core.management.base import BaseCommand
from core.performance.database_optimizations import DatabaseOptimizer

class Command(BaseCommand):
    help = 'Optimiza la base de datos para mejor performance'
    
    def handle(self, *args, **options):
        self.stdout.write('Optimizando configuración MySQL...')
        DatabaseOptimizer.optimize_mysql_config()
        
        self.stdout.write('Analizando tablas...')
        DatabaseOptimizer.analyze_tables()
        
        self.stdout.write(
            self.style.SUCCESS('Optimización completada exitosamente')
        )