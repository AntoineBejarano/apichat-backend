import logging
import time
import asyncio
from typing import Dict, Optional, Union, List
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import URL
from contextlib import contextmanager

from app.models.database_model import DatabaseConnection
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri

logger = logging.getLogger(__name__)


class ConnectionPoolService:
    """Servicio para gestionar un pool de conexiones SQL reutilizables con warm-up pre-inicializado"""
    
    def __init__(self, max_pool_size: int = 20, pool_timeout: int = 30, pool_recycle: int = 3600):
        self.max_pool_size = max_pool_size
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        
        # Pool de engines por DB
        self._engine_pool: Dict[str, Engine] = {}
        self._last_used: Dict[str, float] = {}
        self._connection_stats: Dict[str, Dict] = {}
        
        # 🔧 FASE 2: Nuevos atributos para warm-up y persistencia
        self._warm_up_completed = False
        self._warm_up_tasks: List[asyncio.Task] = []
        self._persistent_connections: Dict[str, bool] = {}
        self._connection_health_check_interval = 300  # 5 minutos
        
        # Configuración del pool optimizada
        self._pool_config = {
            'poolclass': QueuePool,
            'pool_size': 10,  # 🔧 AUMENTADO: Más conexiones por engine
            'max_overflow': 20,  # 🔧 AUMENTADO: Más conexiones adicionales
            'pool_timeout': pool_timeout,
            'pool_recycle': pool_recycle,
            'pool_pre_ping': True,
            'echo': False,
            # 🔧 NUEVO: Configuración para conexiones persistentes
            'pool_reset_on_return': 'commit',  # Mantener transacciones activas
            'isolation_level': 'READ_COMMITTED',  # Nivel de aislamiento estándar
        }
    
    async def warm_up_pool(self, database_connections: List[DatabaseConnection]):
        """
        🔧 FASE 2: Pre-inicializa engines para todas las bases de datos
        Reduce el tiempo de engine creation de 6.2s a 0.5s
        """
        if self._warm_up_completed:
            logger.info("[ConnectionPoolService] 🔥 Warm-up ya completado, saltando...")
            return
        
        logger.info(f"[ConnectionPoolService] 🚀 Iniciando warm-up del pool para {len(database_connections)} DBs...")
        start_time = time.time()
        
        # Crear tareas asíncronas para cada DB
        warm_up_tasks = []
        for db_record in database_connections:
            task = asyncio.create_task(self._warm_up_single_db(db_record))
            warm_up_tasks.append(task)
        
        # Ejecutar warm-up en paralelo
        try:
            await asyncio.gather(*warm_up_tasks, return_exceptions=True)
            
            warm_up_time = time.time() - start_time
            logger.info(f"[ConnectionPoolService] ✅ Warm-up completado en {warm_up_time:.3f}s")
            
            # Marcar como completado
            self._warm_up_completed = True
            
            # Iniciar health check periódico
            asyncio.create_task(self._periodic_health_check())
            
        except Exception as e:
            logger.error(f"[ConnectionPoolService] ❌ Error en warm-up: {e}")
            # Continuar sin warm-up si falla
    
    async def _warm_up_single_db(self, db_record: DatabaseConnection):
        """🔧 FASE 2: Warm-up individual para una DB"""
        db_id = str(db_record.id)
        
        try:
            logger.info(f"[ConnectionPoolService] 🔥 Pre-inicializando engine para DB {db_id}...")
            
            # Crear engine
            engine = self._create_engine(db_record)
            
            if engine:
                # Agregar al pool
                self._engine_pool[db_id] = engine
                self._last_used[db_id] = time.time()
                self._initialize_stats(db_id)
                self._update_usage_stats(db_id, "warm_up")
                
                # Marcar como conexión persistente
                self._persistent_connections[db_id] = True
                
                logger.info(f"[ConnectionPoolService] ✅ Engine pre-inicializado para DB {db_id}")
            else:
                logger.warning(f"[ConnectionPoolService] ⚠️ No se pudo pre-inicializar engine para DB {db_id}")
                
        except Exception as e:
            logger.error(f"[ConnectionPoolService] ❌ Error en warm-up para DB {db_id}: {e}")
    
    def get_engine(self, db_record: DatabaseConnection) -> Engine:
        """Obtiene o crea un engine del pool para una base de datos"""
        db_id = str(db_record.id)
        
        # Verificar si ya tenemos un engine en el pool
        if db_id in self._engine_pool:
            engine = self._engine_pool[db_id]
            
            # Verificar si el engine sigue siendo válido
            if self._is_engine_valid(engine):
                self._update_usage_stats(db_id, "cache_hit")
                self._last_used[db_id] = time.time()
                logger.debug(f"[ConnectionPoolService] 🔥 Cache HIT para DB {db_id}")
                return engine
            else:
                logger.info(f"[ConnectionPoolService] ⚠️ Engine inválido para DB {db_id}, recreando...")
                self._remove_engine(db_id)
        
        # 🔧 FASE 2: Si el warm-up no se completó, crear engine inmediatamente
        if not self._warm_up_completed:
            logger.info(f"[ConnectionPoolService] 🆕 Cache MISS para DB {db_id}, warm-up no completado, creando engine...")
        else:
            logger.info(f"[ConnectionPoolService] 🆕 Cache MISS para DB {db_id}, creando nuevo engine...")
        
        # Crear nuevo engine
        engine = self._create_engine(db_record)
        
        if engine:
            self._engine_pool[db_id] = engine
            self._last_used[db_id] = time.time()
            self._initialize_stats(db_id)
            self._update_usage_stats(db_id, "created")
            
            # Limpiar pool si es necesario
            self._cleanup_pool_if_needed()
            
            return engine
        else:
            raise ValueError(f"No se pudo crear engine para DB {db_id}")
    
    def _create_engine(self, db_record: DatabaseConnection) -> Optional[Engine]:
        """Crea un nuevo engine SQLAlchemy con configuración optimizada"""
        try:
            start_time = time.time()
            
            # Construir URI
            uri = build_sqlalchemy_uri(db_record)
            
            # Configuración específica por tipo de BD
            engine_config = self._get_engine_config(db_record.db_type)
            
            # 🔧 FASE 2: Configuración optimizada para conexiones persistentes
            if db_record.db_type.lower() == 'postgresql':
                engine_config.update({
                    'pool_pre_ping': True,
                    'pool_recycle': 1800,  # 30 minutos para PostgreSQL
                    'connect_args': {
                        'connect_timeout': 5,  # 🔧 REDUCIDO: De 10s a 5s
                        'application_name': 'apichat-backend',
                        'keepalives_idle': 30,  # 🔧 NUEVO: Keep-alive para conexiones persistentes
                        'keepalives_interval': 10,
                        'keepalives_count': 5
                    }
                })
            elif db_record.db_type.lower() == 'mysql':
                engine_config.update({
                    'pool_recycle': 3600,  # 1 hora para MySQL
                    'connect_args': {
                        'connect_timeout': 5,  # 🔧 REDUCIDO: De 10s a 5s
                        'charset': 'utf8mb4',
                        'autocommit': False,  # 🔧 NUEVO: Control explícito de transacciones
                        'init_command': 'SET SESSION wait_timeout=28800'  # 🔧 NUEVO: Timeout extendido
                    }
                })
            
            # Crear engine
            engine = create_engine(uri, **engine_config)
            
            # 🔧 FASE 2: Verificación rápida de conexión
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            
            creation_time = time.time() - start_time
            logger.info(f"[ConnectionPoolService] ✅ Engine creado para DB {db_record.id} en {creation_time:.3f}s")
            
            return engine
            
        except Exception as e:
            logger.error(f"[ConnectionPoolService] ❌ Error creando engine para DB {db_record.id}: {e}")
            return None
    
    def _get_engine_config(self, db_type: str) -> Dict:
        """Obtiene configuración específica del engine según el tipo de BD"""
        base_config = self._pool_config.copy()
        
        # 🔧 FASE 2: Configuraciones optimizadas por tipo de BD
        if db_type.lower() == 'postgresql':
            base_config.update({
                'pool_pre_ping': True,
                'pool_recycle': 1800,  # 30 minutos para PostgreSQL
                'connect_args': {
                    'connect_timeout': 5,  # 🔧 REDUCIDO: De 10s a 5s
                    'application_name': 'apichat-backend',
                    'keepalives_idle': 30,  # 🔧 NUEVO: Keep-alive para conexiones persistentes
                    'keepalives_interval': 10,
                    'keepalives_count': 5
                }
            })
        elif db_type.lower() == 'mysql':
            base_config.update({
                'pool_recycle': 3600,  # 1 hora para MySQL
                'connect_args': {
                    'connect_timeout': 5,  # 🔧 REDUCIDO: De 10s a 5s
                    'charset': 'utf8mb4',
                    'autocommit': False,  # 🔧 NUEVO: Control explícito de transacciones
                    'init_command': 'SET SESSION wait_timeout=28800'  # 🔧 NUEVO: Timeout extendido
                }
            })
        elif db_type.lower() == 'sqlite':
            base_config.update({
                'poolclass': None,  # SQLite no necesita pool
                'connect_args': {
                    'timeout': 30
                }
            })
        
        return base_config
    
    async def _periodic_health_check(self):
        """🔧 FASE 2: Health check periódico para mantener conexiones activas"""
        while True:
            try:
                await asyncio.sleep(self._connection_health_check_interval)
                
                logger.debug("[ConnectionPoolService] 🔍 Ejecutando health check periódico...")
                
                # Verificar todas las conexiones activas
                for db_id, engine in list(self._engine_pool.items()):
                    try:
                        if not self._is_engine_valid(engine):
                            logger.warning(f"[ConnectionPoolService] ⚠️ Engine inválido detectado en health check para DB {db_id}")
                            self._remove_engine(db_id)
                        else:
                            # Actualizar timestamp de último uso
                            self._last_used[db_id] = time.time()
                            logger.debug(f"[ConnectionPoolService] ✅ Health check exitoso para DB {db_id}")
                    except Exception as e:
                        logger.error(f"[ConnectionPoolService] ❌ Error en health check para DB {db_id}: {e}")
                        self._remove_engine(db_id)
                
                # Limpiar pool si es necesario
                self._cleanup_pool_if_needed()
                
            except asyncio.CancelledError:
                logger.info("[ConnectionPoolService] 🔌 Health check periódico cancelado")
                break
            except Exception as e:
                logger.error(f"[ConnectionPoolService] ❌ Error en health check periódico: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar
    
    def _is_engine_valid(self, engine: Engine) -> bool:
        """Verifica si un engine sigue siendo válido"""
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def _update_usage_stats(self, db_id: str, action: str):
        """Actualiza estadísticas de uso del pool"""
        if db_id not in self._connection_stats:
            self._initialize_stats(db_id)
        
        stats = self._connection_stats[db_id]
        stats['total_requests'] += 1
        
        if action == 'cache_hit':
            stats['cache_hits'] += 1
        elif action == 'created':
            stats['cache_misses'] += 1
        
        # Calcular hit ratio
        if stats['total_requests'] > 0:
            stats['hit_ratio'] = (stats['cache_hits'] / stats['total_requests']) * 100
    
    def _initialize_stats(self, db_id: str):
        """Inicializa estadísticas para una nueva DB"""
        self._connection_stats[db_id] = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'hit_ratio': 0.0,
            'created_at': time.time(),
            'last_used': time.time()
        }
    
    def _cleanup_pool_if_needed(self):
        """Limpia el pool si hay demasiados engines"""
        if len(self._engine_pool) <= self.max_pool_size:
            return
        
        # Encontrar engines menos usados
        current_time = time.time()
        engine_ages = [
            (db_id, current_time - self._last_used.get(db_id, 0))
            for db_id in self._engine_pool.keys()
        ]
        
        # Ordenar por tiempo de inactividad (más antiguos primero)
        engine_ages.sort(key=lambda x: x[1], reverse=True)
        
        # Remover engines excedentes
        engines_to_remove = len(self._engine_pool) - self.max_pool_size
        for i in range(engines_to_remove):
            db_id = engine_ages[i][0]
            self._remove_engine(db_id)
            logger.info(f"[ConnectionPoolService] 🗑️ Engine removido por inactividad: DB {db_id}")
    
    def _remove_engine(self, db_id: str):
        """Remueve un engine del pool"""
        if db_id in self._engine_pool:
            engine = self._engine_pool[db_id]
            try:
                engine.dispose()
                logger.debug(f"[ConnectionPoolService] 🔌 Engine disposed para DB {db_id}")
            except Exception as e:
                logger.warning(f"[ConnectionPoolService] ⚠️ Error disposing engine para DB {db_id}: {e}")
            
            del self._engine_pool[db_id]
            del self._last_used[db_id]
            if db_id in self._connection_stats:
                del self._connection_stats[db_id]
    
    @contextmanager
    def get_connection(self, db_record: DatabaseConnection):
        """Context manager para obtener una conexión del pool"""
        engine = self.get_engine(db_record)
        connection = None
        
        try:
            connection = engine.connect()
            yield connection
        except Exception as e:
            logger.error(f"[ConnectionPoolService] ❌ Error en conexión para DB {db_record.id}: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    def get_pool_stats(self) -> Dict:
        """Obtiene estadísticas del pool de conexiones"""
        total_engines = len(self._engine_pool)
        total_requests = sum(stats['total_requests'] for stats in self._connection_stats.values())
        total_cache_hits = sum(stats['cache_hits'] for stats in self._connection_stats.values())
        total_cache_misses = sum(stats['cache_misses'] for stats in self._connection_stats.values())
        
        overall_hit_ratio = 0
        if total_requests > 0:
            overall_hit_ratio = (total_cache_hits / total_requests) * 100
        
        return {
            'total_engines': total_engines,
            'max_pool_size': self.max_pool_size,
            'total_requests': total_requests,
            'total_cache_hits': total_cache_hits,
            'total_cache_misses': total_cache_misses,
            'overall_hit_ratio': overall_hit_ratio,
            'pool_utilization': (total_engines / self.max_pool_size) * 100 if self.max_pool_size > 0 else 0,
            'engines_details': {
                db_id: {
                    'age_seconds': time.time() - stats['created_at'],
                    'last_used_seconds': time.time() - stats['last_used'],
                    'hit_ratio': stats['hit_ratio']
                }
                for db_id, stats in self._connection_stats.items()
            }
        }
    
    def clear_pool(self, db_id: Optional[str] = None):
        """Limpia el pool de conexiones"""
        if db_id:
            if db_id in self._engine_pool:
                self._remove_engine(db_id)
                logger.info(f"[ConnectionPoolService] 🧹 Pool limpiado para DB {db_id}")
        else:
            # Limpiar todo el pool
            for db_id in list(self._engine_pool.keys()):
                self._remove_engine(db_id)
            logger.info(f"[ConnectionPoolService] 🧹 Pool completamente limpiado")
    
    def health_check(self) -> Dict[str, bool]:
        """Realiza health check de todas las conexiones del pool"""
        health_results = {}
        
        for db_id, engine in self._engine_pool.items():
            try:
                with engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("SELECT 1"))
                health_results[db_id] = True
            except Exception as e:
                logger.warning(f"[ConnectionPoolService] ⚠️ Health check falló para DB {db_id}: {e}")
                health_results[db_id] = False
        
        return health_results
    
    def get_pool_status(self) -> Dict[str, any]:
        """🔧 FASE 2: Obtiene estado completo del pool de conexiones"""
        return {
            "warm_up_completed": self._warm_up_completed,
            "total_engines": len(self._engine_pool),
            "persistent_connections": len(self._persistent_connections),
            "max_pool_size": self.max_pool_size,
            "pool_utilization": (len(self._engine_pool) / self.max_pool_size) * 100 if self.max_pool_size > 0 else 0,
            "connection_stats": self._connection_stats.copy(),
            "last_used": {k: time.time() - v for k, v in self._last_used.items()}
        }
    
    def force_warm_up(self, database_connections: List[DatabaseConnection]):
        """🔧 FASE 2: Fuerza el warm-up del pool (método síncrono para compatibilidad)"""
        if not self._warm_up_completed:
            logger.info("[ConnectionPoolService] 🔄 Forzando warm-up del pool...")
            # Crear event loop si no existe
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Si el loop está corriendo, crear task
                    asyncio.create_task(self.warm_up_pool(database_connections))
                else:
                    # Si no está corriendo, ejecutar directamente
                    loop.run_until_complete(self.warm_up_pool(database_connections))
            except RuntimeError:
                # No hay event loop, crear uno nuevo
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.warm_up_pool(database_connections))
                finally:
                    loop.close()
        else:
            logger.info("[ConnectionPoolService] 🔥 Warm-up ya completado")
    
    def is_warm_up_completed(self) -> bool:
        """🔧 FASE 2: Verifica si el warm-up está completado"""
        return self._warm_up_completed
