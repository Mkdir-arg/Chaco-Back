"""
Sistema de particionamiento automático para tablas de alto volumen
"""
from django.db import connection
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class DatabasePartitioner:
    """Gestiona particionamiento automático de tablas por fecha"""
    
    PARTITIONED_TABLES = {
        'legajos_registroasistencia': 'fecha',
        'legajos_historialactividad': 'creado',
        'legajos_historialinscripto': 'creado',
        'legajos_alertaausentismo': 'creado',
    }
    
    @classmethod
    def create_monthly_partitions(cls, months_ahead=3):
        """Crea índices optimizados para tablas de alto volumen (MySQL compatible)"""
        with connection.cursor() as cursor:
            # Crear índices compuestos para optimizar consultas por fecha
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_registro_fecha_inscripto ON legajos_registroasistencia (fecha DESC, inscripto_id)",
                "CREATE INDEX IF NOT EXISTS idx_historial_act_fecha ON legajos_historialactividad (creado DESC, actividad_id)",
                "CREATE INDEX IF NOT EXISTS idx_historial_ins_fecha ON legajos_historialinscripto (creado DESC, inscripto_id)",
                "CREATE INDEX IF NOT EXISTS idx_alerta_activa_fecha ON legajos_alertaausentismo (activa, creado DESC)",
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                    logger.info(f"Índice creado: {index_sql.split()[5]}")
                except Exception as e:
                    logger.warning(f"Índice ya existe o error: {e}")
    
    @classmethod
    def archive_old_data(cls, months_old=12):
        """Archiva datos antiguos a tablas de archivo"""
        cutoff_date = datetime.now() - timedelta(days=30*months_old)
        
        with connection.cursor() as cursor:
            tables_to_archive = [
                ('legajos_historialactividad', 'creado'),
                ('legajos_historialinscripto', 'creado'),
                ('legajos_alertaausentismo', 'creado'),
            ]
            
            for table, date_field in tables_to_archive:
                archive_table = f"{table}_archivo"
                
                # Crear tabla de archivo si no existe
                cursor.execute(f"CREATE TABLE IF NOT EXISTS {archive_table} LIKE {table}")
                
                # Mover datos antiguos al archivo
                cursor.execute(f"""
                    INSERT IGNORE INTO {archive_table} 
                    SELECT * FROM {table} 
                    WHERE {date_field} < %s
                """, [cutoff_date])
                
                archived_count = cursor.rowcount
                
                # Eliminar solo después de archivar exitosamente
                if archived_count > 0:
                    cursor.execute(f"""
                        DELETE FROM {table} 
                        WHERE {date_field} < %s
                    """, [cutoff_date])
                
                logger.info(f"Datos archivados de {table}: {archived_count} registros")

    @classmethod
    def restore_from_archive(cls, table_name, months_back=6):
        """Restaura datos desde el archivo si es necesario"""
        restore_date = datetime.now() - timedelta(days=30*months_back)
        archive_table = f"{table_name}_archivo"
        
        with connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT IGNORE INTO {table_name}
                SELECT * FROM {archive_table}
                WHERE creado >= %s
            """, [restore_date])
            
            logger.info(f"Restaurados {cursor.rowcount} registros de {archive_table}")

class QueryOptimizer:
    """Optimizador de consultas para tablas particionadas"""
    
    @staticmethod
    def get_recent_records(model_class, days=30):
        """Obtiene registros recientes optimizado para particiones"""
        cutoff_date = datetime.now().date() - timedelta(days=days)
        return model_class.objects.filter(
            creado__date__gte=cutoff_date
        ).select_related().order_by('-creado')
    
    @staticmethod
    def bulk_create_optimized(model_class, objects, batch_size=1000):
        """Inserción masiva optimizada"""
        return model_class.objects.bulk_create(
            objects, 
            batch_size=batch_size,
            ignore_conflicts=True
        )