import logging

from django.core.management.base import BaseCommand

from core.performance.phase2_manager import phase2_manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Inicializa la Fase 2 de optimización avanzada de base de datos"

    def add_arguments(self, parser):
        parser.add_argument(
            "--auto-create-indexes",
            action="store_true",
            help="Crear automáticamente índices recomendados de alta prioridad",
        )

        parser.add_argument(
            "--skip-partitioning", action="store_true", help="Omitir inicialización de particionamiento automático"
        )

        parser.add_argument(
            "--force-optimization",
            action="store_true",
            help="Forzar ciclo completo de optimización después de inicializar",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Iniciando FASE 2 - Optimización Avanzada de Base de Datos"))

        try:
            # Inicializar Fase 2
            phase2_manager.initialize_phase2()

            # Crear índices automáticamente si se solicita
            if options["auto_create_indexes"]:
                self.stdout.write("🔍 Creando índices recomendados...")
                from core.performance.intelligent_indexing import index_manager

                created = index_manager.create_recommended_indexes(auto_create=True)
                self.stdout.write(self.style.SUCCESS(f"✅ Creados {len(created)} índices automáticamente"))

            # Forzar optimización si se solicita
            if options["force_optimization"]:
                self.stdout.write("⚡ Ejecutando ciclo de optimización...")
                phase2_manager.force_optimization_cycle()
                self.stdout.write(self.style.SUCCESS("✅ Ciclo de optimización completado"))

            # Mostrar estado final
            status = phase2_manager.get_phase2_status()
            self.stdout.write("\n📊 Estado de componentes:")

            for component, running in status["components_status"].items():
                status_icon = "✅" if running else "❌"
                self.stdout.write(f"  {status_icon} {component}: {'Activo' if running else 'Inactivo'}")

            self.stdout.write(self.style.SUCCESS("\n🎉 FASE 2 inicializada correctamente!"))

            self.stdout.write("\n📋 Próximos pasos:")
            self.stdout.write("  1. Monitorear dashboard: http://localhost:9000/performance-dashboard/")
            self.stdout.write("  2. Revisar sugerencias de índices en 30 minutos")
            self.stdout.write("  3. Verificar logs de particionamiento automático")
            self.stdout.write("  4. Monitorear métricas de performance")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error inicializando Fase 2: {e}"))
            logger.error(f"Error en comando initialize_phase2: {e}")
            raise
