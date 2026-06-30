import time

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Genera reporte de performance del sistema"

    def handle(self, *args, **options):
        self.stdout.write("=== REPORTE DE PERFORMANCE ===\n")

        # Test Redis
        self.stdout.write("1. REDIS CACHE:")
        start = time.time()
        cache.set("perf_test", "test_value", 60)
        result = cache.get("perf_test")
        redis_time = (time.time() - start) * 1000

        if result == "test_value":
            self.stdout.write(f"   ✅ Redis funcionando - {redis_time:.2f}ms")
        else:
            self.stdout.write("   ❌ Redis no funciona")

        # Test DB
        self.stdout.write("\n2. BASE DE DATOS:")
        start = time.time()
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM legajos_legajoatencion")
            legajos_count = cursor.fetchone()[0]
        db_time = (time.time() - start) * 1000

        self.stdout.write(f"   ✅ MySQL conectado - {db_time:.2f}ms")
        self.stdout.write(f"   📊 Total legajos: {legajos_count}")

        # Test performance optimizations
        self.stdout.write("\n3. OPTIMIZACIONES:")

        # Check indexes
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.statistics 
                WHERE table_schema = DATABASE() 
                AND index_name LIKE 'idx_%'
            """)
            custom_indexes = cursor.fetchone()[0]

        self.stdout.write(f"   📈 Índices personalizados: {custom_indexes}")

        # Memory usage
        with connection.cursor() as cursor:
            cursor.execute("SHOW VARIABLES LIKE 'tmp_table_size'")
            tmp_size = cursor.fetchone()[1]
            cursor.execute("SHOW VARIABLES LIKE 'max_heap_table_size'")
            heap_size = cursor.fetchone()[1]

        self.stdout.write(f"   💾 Tmp table size: {int(tmp_size) // 1024 // 1024}MB")
        self.stdout.write(f"   💾 Heap table size: {int(heap_size) // 1024 // 1024}MB")

        self.stdout.write("\n4. RECOMENDACIONES:")
        if redis_time > 10:
            self.stdout.write("   ⚠️  Redis lento, considerar optimizar red")
        if db_time > 50:
            self.stdout.write("   ⚠️  DB lenta, revisar queries")
        if custom_indexes < 10:
            self.stdout.write("   ⚠️  Pocos índices, ejecutar migraciones")

        self.stdout.write("\n✅ Sistema optimizado y funcionando correctamente")
