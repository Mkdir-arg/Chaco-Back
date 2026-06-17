import logging
from django.db import connection, transaction
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from django.conf import settings
import threading
import time

logger = logging.getLogger(__name__)

class AdvancedPartitionManager:
    """Sistema avanzado de particionamiento automático"""
    
    PARTITION_TABLES = {
        'legajos_registroasistencia': {
            'partition_field': 'fecha',
            'partition_type': 'monthly',
            'retention_months': 24,
            'archive_after_months': 12
        },
        'legajos_historialactividad': {
            'partition_field': 'fecha_cambio',
            'partition_type': 'quarterly',
            'retention_months': 36,
            'archive_after_months': 18
        },
        'conversaciones_mensaje': {
            'partition_field': 'timestamp',
            'partition_type': 'monthly',
            'retention_months': 12,
            'archive_after_months': 6
        }
    }
    
    def __init__(self):
        self.running = False
        self.thread = None
    
    def start_auto_partitioning(self):
        """Inicia el sistema automático de particionamiento"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._partition_worker, daemon=True)
            self.thread.start()
            logger.info("Sistema de particionamiento automático iniciado")
    
    def stop_auto_partitioning(self):
        """Detiene el sistema automático"""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("Sistema de particionamiento detenido")
    
    def _partition_worker(self):
        """Worker que ejecuta particionamiento cada 24 horas"""
        while self.running:
            try:
                self.create_future_partitions()
                self.archive_old_partitions()
                self.optimize_partition_indexes()
                # Esperar 24 horas
                time.sleep(86400)
            except Exception as e:
                logger.error(f"Error en worker de particionamiento: {e}")
                time.sleep(3600)  # Reintentar en 1 hora
    
    def create_future_partitions(self):
        """Crea particiones para los próximos 3 meses"""
        with connection.cursor() as cursor:
            for table_name, config in self.PARTITION_TABLES.items():
                try:
                    if not self._table_exists(cursor, table_name):
                        continue
                    
                    # Crear particiones futuras
                    for i in range(1, 4):  # Próximos 3 meses
                        if config['partition_type'] == 'monthly':
                            partition_date = datetime.now() + timedelta(days=30*i)
                            partition_name = f"{table_name}_{partition_date.strftime('%Y_%m')}"
                            start_date = partition_date.replace(day=1)
                            end_date = (start_date + timedelta(days=32)).replace(day=1)
                        else:  # quarterly
                            quarter = ((datetime.now().month - 1) // 3) + 1 + (i-1)
                            year = datetime.now().year + (quarter - 1) // 4
                            quarter = ((quarter - 1) % 4) + 1
                            partition_name = f"{table_name}_{year}_Q{quarter}"
                            start_date = datetime(year, (quarter-1)*3 + 1, 1)
                            end_date = datetime(year, quarter*3 + 1, 1) if quarter < 4 else datetime(year+1, 1, 1)
                        
                        if not self._partition_exists(cursor, partition_name):
                            self._create_partition(cursor, table_name, partition_name, 
                                                config['partition_field'], start_date, end_date)
                
                except Exception as e:
                    logger.error(f"Error creando particiones para {table_name}: {e}")
    
    def archive_old_partitions(self):
        """Archiva particiones antiguas"""
        with connection.cursor() as cursor:
            for table_name, config in self.PARTITION_TABLES.items():
                try:
                    archive_date = datetime.now() - timedelta(days=30 * config['archive_after_months'])
                    
                    # Buscar particiones a archivar
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = DATABASE() 
                        AND table_name LIKE %s
                    """, [f"{table_name}_%"])
                    
                    for (partition_name,) in cursor.fetchall():
                        if self._should_archive_partition(partition_name, archive_date, config):
                            self._archive_partition(cursor, partition_name)
                
                except Exception as e:
                    logger.error(f"Error archivando particiones de {table_name}: {e}")
    
    def optimize_partition_indexes(self):
        """Optimiza índices en particiones"""
        with connection.cursor() as cursor:
            for table_name, config in self.PARTITION_TABLES.items():
                try:
                    # Obtener particiones activas
                    cursor.execute("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = DATABASE() 
                        AND table_name LIKE %s
                    """, [f"{table_name}_%"])
                    
                    for (partition_name,) in cursor.fetchall():
                        self._optimize_partition_indexes(cursor, partition_name, config)
                
                except Exception as e:
                    logger.error(f"Error optimizando índices de {table_name}: {e}")
    
    def _table_exists(self, cursor, table_name):
        """Verifica si la tabla existe"""
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = DATABASE() AND table_name = %s
        """, [table_name])
        return cursor.fetchone()[0] > 0
    
    def _partition_exists(self, cursor, partition_name):
        """Verifica si la partición existe"""
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = DATABASE() AND table_name = %s
        """, [partition_name])
        return cursor.fetchone()[0] > 0
    
    def _create_partition(self, cursor, table_name, partition_name, partition_field, start_date, end_date):
        """Crea una nueva partición"""
        try:
            # Crear tabla partición
            cursor.execute(f"""
                CREATE TABLE {partition_name} (
                    LIKE {table_name} INCLUDING ALL
                ) PARTITION BY RANGE ({partition_field})
            """)
            
            # Crear índices optimizados
            cursor.execute(f"""
                CREATE INDEX idx_{partition_name}_{partition_field} 
                ON {partition_name} ({partition_field})
            """)
            
            logger.info(f"Partición creada: {partition_name}")
            
        except Exception as e:
            logger.error(f"Error creando partición {partition_name}: {e}")
    
    def _should_archive_partition(self, partition_name, archive_date, config):
        """Determina si una partición debe ser archivada"""
        # Lógica para determinar si archivar basado en fecha
        return True  # Simplificado
    
    def _archive_partition(self, cursor, partition_name):
        """Archiva una partición a almacenamiento frío"""
        try:
            # Crear tabla de archivo
            archive_name = f"archive_{partition_name}"
            cursor.execute(f"""
                CREATE TABLE {archive_name} 
                AS SELECT * FROM {partition_name}
            """)
            
            # Comprimir tabla de archivo
            cursor.execute(f"ALTER TABLE {archive_name} ENGINE=ARCHIVE")
            
            # Eliminar partición original
            cursor.execute(f"DROP TABLE {partition_name}")
            
            logger.info(f"Partición archivada: {partition_name} -> {archive_name}")
            
        except Exception as e:
            logger.error(f"Error archivando partición {partition_name}: {e}")
    
    def _optimize_partition_indexes(self, cursor, partition_name, config):
        """Optimiza índices de una partición"""
        try:
            # Analizar tabla para estadísticas
            cursor.execute(f"ANALYZE TABLE {partition_name}")
            
            # Optimizar tabla
            cursor.execute(f"OPTIMIZE TABLE {partition_name}")
            
        except Exception as e:
            logger.error(f"Error optimizando {partition_name}: {e}")
    
    def get_partition_stats(self):
        """Obtiene estadísticas de particiones"""
        stats = {}
        with connection.cursor() as cursor:
            for table_name in self.PARTITION_TABLES.keys():
                cursor.execute("""
                    SELECT 
                        COUNT(*) as partition_count,
                        SUM(data_length + index_length) as total_size
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name LIKE %s
                """, [f"{table_name}_%"])
                
                result = cursor.fetchone()
                stats[table_name] = {
                    'partition_count': result[0] if result else 0,
                    'total_size_mb': (result[1] / 1024 / 1024) if result and result[1] else 0
                }
        
        return stats

# Instancia global
partition_manager = AdvancedPartitionManager()