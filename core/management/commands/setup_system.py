from django.core.management.base import BaseCommand
from django.core.management import call_command
from core.performance.database_optimizations import DatabaseOptimizer

class Command(BaseCommand):
    help = 'Configura el sistema completo con todas las optimizaciones'
    
    def handle(self, *args, **options):
        self.stdout.write('🚀 Configurando sistema...')
        
        # Migraciones
        self.stdout.write('📦 Aplicando migraciones...')
        call_command('migrate', verbosity=1)
        
        # Crear programas iniciales
        self.stdout.write('📋 Creando programas iniciales...')
        try:
            call_command('crear_programas')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'⚠️  Error creando programas: {e}'))
        
        # Optimizaciones DB
        self.stdout.write('⚡ Optimizando base de datos...')
        DatabaseOptimizer.optimize_mysql_config()
        DatabaseOptimizer.analyze_tables()
        
        # Archivos estáticos
        self.stdout.write('📁 Recolectando archivos estáticos...')
        call_command('collectstatic', interactive=False, clear=True, verbosity=0)
        
        # Reporte final
        self.stdout.write('📊 Generando reporte...')
        call_command('performance_report')
        
        self.stdout.write(
            self.style.SUCCESS('✅ Sistema configurado y optimizado')
        )