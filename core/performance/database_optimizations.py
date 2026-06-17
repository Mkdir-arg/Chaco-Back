from django.db import connection
from django.core.management.base import BaseCommand

class DatabaseOptimizer:
    """Optimizaciones avanzadas de base de datos"""
    
    @staticmethod
    def optimize_mysql_config():
        """Optimiza configuración MySQL 8.0 para mejor performance"""
        optimizations = [
            "SET GLOBAL tmp_table_size = 134217728;",  # 128MB
            "SET GLOBAL max_heap_table_size = 134217728;",  # 128MB
            "SET GLOBAL innodb_buffer_pool_instances = 4;",
            "SET GLOBAL innodb_log_buffer_size = 67108864;",  # 64MB
            "SET GLOBAL innodb_flush_log_at_trx_commit = 2;",
        ]
        
        with connection.cursor() as cursor:
            for sql in optimizations:
                try:
                    cursor.execute(sql)
                    print(f"Applied: {sql}")
                except Exception as e:
                    print(f"Skipped: {sql} - {e}")
    
    @staticmethod
    def analyze_tables():
        """Analiza tablas para optimizar estadísticas"""
        tables = [
            'legajos_legajoatencion',
            'conversaciones_conversacion',
            'conversaciones_mensaje',
            'legajos_ciudadano',
            'core_institucion'
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    cursor.execute(f"ANALYZE TABLE {table};")
                    print(f"Analyzed: {table}")
                except Exception as e:
                    print(f"Error analyzing {table}: {e}")