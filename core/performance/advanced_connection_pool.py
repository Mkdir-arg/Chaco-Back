import logging
import threading
import time
from queue import Queue, Empty
from contextlib import contextmanager
from django.db import connections
from django.conf import settings
from typing import Optional, Dict, Any

try:
    import pymysql
except ImportError:  # pragma: no cover - dependencia opcional en entornos sin MySQL directo
    pymysql = None

logger = logging.getLogger(__name__)

class AdvancedConnectionPool:
    """Pool avanzado de conexiones con load balancing y failover"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pools = {}
        self.stats = {
            'total_connections': 0,
            'active_connections': 0,
            'failed_connections': 0,
            'queries_executed': 0,
            'avg_response_time': 0.0
        }
        self.lock = threading.RLock()
        self.monitoring_thread = None
        self.running = False
        
        # Configuración por defecto
        self.default_config = {
            'min_connections': 5,
            'max_connections': 20,
            'connection_timeout': 30,
            'idle_timeout': 300,
            'retry_attempts': 3,
            'health_check_interval': 60
        }
        
        # Merge configuración
        for key, value in self.default_config.items():
            if key not in self.config:
                self.config[key] = value
    
    def initialize_pools(self):
        """Inicializa pools para todas las bases de datos configuradas"""
        try:
            db_configs = getattr(settings, 'DATABASES', {})
            
            for db_alias, db_config in db_configs.items():
                if db_config['ENGINE'] == 'django.db.backends.mysql':
                    self.pools[db_alias] = DatabasePool(
                        db_alias=db_alias,
                        db_config=db_config,
                        pool_config=self.config
                    )
                    logger.info(f"Pool inicializado para base de datos: {db_alias}")
            
            self.start_monitoring()
            
        except Exception as e:
            logger.error(f"Error inicializando pools: {e}")
    
    def start_monitoring(self):
        """Inicia el monitoreo de salud de conexiones"""
        if not self.running:
            self.running = True
            self.monitoring_thread = threading.Thread(target=self._health_monitor, daemon=True)
            self.monitoring_thread.start()
            logger.info("Monitoreo de conexiones iniciado")
    
    def stop_monitoring(self):
        """Detiene el monitoreo"""
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join()
        logger.info("Monitoreo de conexiones detenido")
    
    def _health_monitor(self):
        """Monitor de salud que verifica conexiones periódicamente"""
        while self.running:
            try:
                for db_alias, pool in self.pools.items():
                    pool.health_check()
                
                self._update_global_stats()
                time.sleep(self.config['health_check_interval'])
                
            except Exception as e:
                logger.error(f"Error en monitor de salud: {e}")
                time.sleep(30)
    
    def _update_global_stats(self):
        """Actualiza estadísticas globales"""
        with self.lock:
            total_connections = sum(pool.get_stats()['total_connections'] for pool in self.pools.values())
            active_connections = sum(pool.get_stats()['active_connections'] for pool in self.pools.values())
            
            self.stats.update({
                'total_connections': total_connections,
                'active_connections': active_connections,
                'pool_count': len(self.pools)
            })
    
    @contextmanager
    def get_connection(self, db_alias: str = 'default'):
        """Obtiene una conexión del pool con manejo automático"""
        pool = self.pools.get(db_alias)
        if not pool:
            raise ValueError(f"Pool no encontrado para base de datos: {db_alias}")
        
        connection = None
        try:
            connection = pool.get_connection()
            yield connection
        finally:
            if connection:
                pool.return_connection(connection)
    
    def execute_query(self, query: str, params: tuple = None, db_alias: str = 'default'):
        """Ejecuta una query usando el pool de conexiones"""
        start_time = time.time()
        
        try:
            with self.get_connection(db_alias) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params or ())
                    result = cursor.fetchall()
                
                # Actualizar estadísticas
                execution_time = time.time() - start_time
                self._update_query_stats(execution_time)
                
                return result
                
        except Exception as e:
            self.stats['failed_connections'] += 1
            logger.error(f"Error ejecutando query: {e}")
            raise
    
    def _update_query_stats(self, execution_time: float):
        """Actualiza estadísticas de queries"""
        with self.lock:
            self.stats['queries_executed'] += 1
            
            # Calcular promedio móvil del tiempo de respuesta
            current_avg = self.stats['avg_response_time']
            query_count = self.stats['queries_executed']
            
            self.stats['avg_response_time'] = (
                (current_avg * (query_count - 1) + execution_time) / query_count
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas completas del pool"""
        with self.lock:
            pool_stats = {}
            for db_alias, pool in self.pools.items():
                pool_stats[db_alias] = pool.get_stats()
            
            return {
                'global_stats': self.stats.copy(),
                'pool_stats': pool_stats,
                'timestamp': time.time()
            }


class DatabasePool:
    """Pool de conexiones para una base de datos específica"""
    
    def __init__(self, db_alias: str, db_config: Dict, pool_config: Dict):
        self.db_alias = db_alias
        self.db_config = db_config
        self.pool_config = pool_config
        
        self.available_connections = Queue(maxsize=pool_config['max_connections'])
        self.active_connections = set()
        self.connection_stats = {}
        self.lock = threading.RLock()
        
        # Crear conexiones iniciales
        self._create_initial_connections()
    
    def _create_initial_connections(self):
        """Crea el número mínimo de conexiones"""
        for _ in range(self.pool_config['min_connections']):
            try:
                conn = self._create_connection()
                self.available_connections.put(conn)
            except Exception as e:
                logger.error(f"Error creando conexión inicial: {e}")
    
    def _create_connection(self):
        """Crea una nueva conexión a la base de datos"""
        try:
            if pymysql is None:
                raise RuntimeError("pymysql no está instalado")

            connection = pymysql.connect(
                host=self.db_config['HOST'],
                port=int(self.db_config.get('PORT', 3306)),
                user=self.db_config['USER'],
                password=self.db_config['PASSWORD'],
                database=self.db_config['NAME'],
                charset='utf8mb4',
                autocommit=True,
                connect_timeout=self.pool_config['connection_timeout'],
                read_timeout=30,
                write_timeout=30
            )
            
            # Configurar conexión
            with connection.cursor() as cursor:
                cursor.execute("SET SESSION sql_mode='STRICT_TRANS_TABLES'")
                cursor.execute("SET SESSION innodb_lock_wait_timeout=10")
            
            connection_id = id(connection)
            self.connection_stats[connection_id] = {
                'created_at': time.time(),
                'last_used': time.time(),
                'query_count': 0,
                'total_time': 0.0
            }
            
            return connection
            
        except Exception as e:
            logger.error(f"Error creando conexión para {self.db_alias}: {e}")
            raise
    
    def get_connection(self, timeout: float = 10.0):
        """Obtiene una conexión del pool"""
        try:
            # Intentar obtener conexión disponible
            connection = self.available_connections.get(timeout=timeout)
            
            # Verificar si la conexión sigue siendo válida
            if not self._is_connection_valid(connection):
                connection.close()
                connection = self._create_connection()
            
            with self.lock:
                self.active_connections.add(connection)
                connection_id = id(connection)
                if connection_id in self.connection_stats:
                    self.connection_stats[connection_id]['last_used'] = time.time()
            
            return connection
            
        except Empty:
            # Si no hay conexiones disponibles, crear una nueva si es posible
            with self.lock:
                total_connections = (
                    self.available_connections.qsize() + 
                    len(self.active_connections)
                )
                
                if total_connections < self.pool_config['max_connections']:
                    connection = self._create_connection()
                    self.active_connections.add(connection)
                    return connection
                else:
                    raise Exception(f"Pool de conexiones agotado para {self.db_alias}")
    
    def return_connection(self, connection):
        """Devuelve una conexión al pool"""
        with self.lock:
            if connection in self.active_connections:
                self.active_connections.remove(connection)
                
                # Verificar si la conexión sigue siendo válida
                if self._is_connection_valid(connection):
                    try:
                        self.available_connections.put_nowait(connection)
                    except:
                        # Pool lleno, cerrar conexión
                        connection.close()
                        connection_id = id(connection)
                        if connection_id in self.connection_stats:
                            del self.connection_stats[connection_id]
                else:
                    connection.close()
                    connection_id = id(connection)
                    if connection_id in self.connection_stats:
                        del self.connection_stats[connection_id]
    
    def _is_connection_valid(self, connection) -> bool:
        """Verifica si una conexión sigue siendo válida"""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except:
            return False
    
    def health_check(self):
        """Verifica la salud de todas las conexiones"""
        with self.lock:
            # Verificar conexiones activas
            invalid_connections = []
            for conn in list(self.active_connections):
                if not self._is_connection_valid(conn):
                    invalid_connections.append(conn)
            
            # Remover conexiones inválidas
            for conn in invalid_connections:
                self.active_connections.remove(conn)
                conn.close()
                connection_id = id(conn)
                if connection_id in self.connection_stats:
                    del self.connection_stats[connection_id]
            
            # Verificar conexiones disponibles
            available_connections = []
            while not self.available_connections.empty():
                try:
                    conn = self.available_connections.get_nowait()
                    if self._is_connection_valid(conn):
                        available_connections.append(conn)
                    else:
                        conn.close()
                        connection_id = id(conn)
                        if connection_id in self.connection_stats:
                            del self.connection_stats[connection_id]
                except Empty:
                    break
            
            # Devolver conexiones válidas al pool
            for conn in available_connections:
                self.available_connections.put_nowait(conn)
            
            # Asegurar número mínimo de conexiones
            current_total = len(available_connections) + len(self.active_connections)
            if current_total < self.pool_config['min_connections']:
                needed = self.pool_config['min_connections'] - current_total
                for _ in range(needed):
                    try:
                        conn = self._create_connection()
                        self.available_connections.put_nowait(conn)
                    except Exception as e:
                        logger.error(f"Error creando conexión en health_check: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del pool"""
        with self.lock:
            return {
                'db_alias': self.db_alias,
                'available_connections': self.available_connections.qsize(),
                'active_connections': len(self.active_connections),
                'total_connections': self.available_connections.qsize() + len(self.active_connections),
                'max_connections': self.pool_config['max_connections'],
                'min_connections': self.pool_config['min_connections'],
                'connection_stats_count': len(self.connection_stats)
            }

# Instancia global del pool
connection_pool = AdvancedConnectionPool({
    'min_connections': 10,
    'max_connections': 50,
    'connection_timeout': 30,
    'idle_timeout': 300,
    'retry_attempts': 3,
    'health_check_interval': 60
})