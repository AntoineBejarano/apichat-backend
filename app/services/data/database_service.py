import logging
from typing import List, Optional, TYPE_CHECKING, Union
from uuid import UUID

import sqlalchemy
from sqlalchemy.orm import Session
from langchain_community.utilities.sql_database import SQLDatabase

from app.models.database_model import DatabaseConnection
from app.schemas.database_schema import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
)
from app.utils.build_sqlalchemy_uri import build_sqlalchemy_uri
from .connection_pool_service import ConnectionPoolService

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, factory: "ServiceFactory") -> None:
        # 🔧 ROMPER CICLO RECURSIVO: No heredar de BaseService
        self.factory = factory
        self.user = factory.user
        # Inicializar pool de conexiones
        self.connection_pool = ConnectionPoolService()
        # 🔧 Obtener sesión directamente sin recursión
        self.db = factory.get_database_session()
        logger.info("[DatabaseService] ✅ Inicializado para user_id=%s", self.user.id)
    
    def get_db(self) -> Session:
        """Obtiene la sesión de base de datos"""
        return self.db

    # ───────────────── CRUD ─────────────────
    def create_connection(self, data: DatabaseConnectionCreate) -> DatabaseConnection:
        logger.info("[DatabaseService] ➕ Creando conexión DB para user_id=%s", self.user.id)
        
        # 🔧 NUEVO: Crear conexión con estado inicial "pending"
        connection = DatabaseConnection(
            user_id=self.user.id, 
            schema_status="pending",  # Estado inicial
            **data.model_dump()
        )
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        
        # 🔧 NUEVO: Lanzar generación de schema en background
        self._launch_schema_generation_background(connection.id)
        
        return connection

    def update_connection(self, db_id: Union[int, str, "UUID"], updates: DatabaseConnectionUpdate) -> DatabaseConnection:
        logger.info("[DatabaseService] 🔄 Actualizando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            raise ValueError("Database connection not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            setattr(conn, field, value)

        self.db.commit()
        self.db.refresh(conn)
        return conn

    def delete_connection(self, db_id: Union[int, str, "UUID"]) -> bool:
        logger.warning("[DatabaseService] 🗑️ Eliminando DB id=%s para user_id=%s", db_id, self.user.id)
        conn = self.get_record(db_id)
        if not conn:
            return False
        self.db.delete(conn)
        self.db.commit()
        return True

    # ─────────────── Queries / utils ───────────────
    def get_user_databases(self) -> List[DatabaseConnection]:
        logger.info("[DatabaseService] 📥 Listando todas las conexiones DB para user_id=%s", self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.user_id == self.user.id)
            .all()
        )

    # alias para compatibilidad con código antiguo
    def list_all_for_user(self) -> List[DatabaseConnection]:
        return self.get_user_databases()

    def get_record(self, db_id: Union[int, str, "UUID"]) -> Optional[DatabaseConnection]:
        logger.debug("[DatabaseService] 🔎 Buscando DB id=%s para user_id=%s", db_id, self.user.id)
        return (
            self.db.query(DatabaseConnection)
            .filter(DatabaseConnection.id == db_id, DatabaseConnection.user_id == self.user.id)
            .first()
        )

    def build_sqlalchemy_engine(self, record: DatabaseConnection):
        uri = build_sqlalchemy_uri(record)
        logger.debug("[DatabaseService] 🛠️ Construyendo engine para URI: %s", uri)
        return sqlalchemy.create_engine(uri)

    def get_sql_database_from_record(self, record: DatabaseConnection) -> Optional[SQLDatabase]:
        try:
            # Usar pool de conexiones en lugar de crear nuevo engine
            engine = self.connection_pool.get_engine(record)
            return SQLDatabase(engine)
        except Exception as exc:
            logger.error("[DatabaseService] ❌ Error creando SQLDatabase: %s", exc)
            return None
    
    def _launch_schema_generation_background(self, db_id: UUID) -> None:
        """
        Lanza la generación de schema en background usando FastAPI BackgroundTasks.
        
        Args:
            db_id: ID de la base de datos recién creada
        """
        try:
            logger.info(f"[DatabaseService] 🚀 Lanzando generación de schema en background para DB {db_id}")
            
            # 🔧 IMPLEMENTACIÓN: Usar FastAPI BackgroundTasks
            # Por ahora, solo logueamos. La implementación completa se hará en el router
            logger.info(f"[DatabaseService] ⏳ Schema generation scheduled for DB {db_id}")
            
        except Exception as e:
            logger.error(f"[DatabaseService] ❌ Error lanzando generación de schema: {e}")
    
    def _test_connection_immediately(self, data: DatabaseConnectionCreate) -> bool:
        """
        Test INMEDIATO de conexión antes de crear el registro.
        
        Args:
            data: Datos de la conexión a testear
            
        Returns:
            True si la conexión es exitosa, False en caso contrario
        """
        try:
            logger.info("[DatabaseService] 🧪 Iniciando test inmediato de conexión...")
            
            # Crear URI temporal para test
            test_uri = build_sqlalchemy_uri(data)
            logger.debug("[DatabaseService] 🔗 URI de test: %s", test_uri.replace(data.password, "***"))
            
            # Crear engine temporal con timeout corto
            test_engine = sqlalchemy.create_engine(
                test_uri, 
                connect_timeout=10,  # 10 segundos máximo
                pool_pre_ping=True   # Verificar conexión antes de usar
            )
            
            # Test de conexión
            with test_engine.connect() as conn:
                # Query simple para verificar conectividad
                result = conn.execute(sqlalchemy.text("SELECT 1 as test"))
                test_value = result.scalar()
                
                if test_value == 1:
                    logger.info("[DatabaseService] ✅ Test de conexión exitoso")
                    return True
                else:
                    logger.warning("[DatabaseService] ⚠️ Test de conexión falló - resultado inesperado")
                    return False
                    
        except sqlalchemy.exc.OperationalError as e:
            # Errores de conexión (host, puerto, credenciales)
            logger.error("[DatabaseService] ❌ Error operacional de conexión: %s", e)
            return False
            
        except sqlalchemy.exc.AuthenticationFailed as e:
            # Error de autenticación
            logger.error("[DatabaseService] ❌ Error de autenticación: %s", e)
            return False
            
        except Exception as e:
            # Otros errores
            logger.error("[DatabaseService] ❌ Error inesperado durante test de conexión: %s", e)
            return False
            
        finally:
            # Limpiar recursos
            try:
                if 'test_engine' in locals():
                    test_engine.dispose()
                    logger.debug("[DatabaseService] 🧹 Engine de test limpiado")
            except Exception as cleanup_error:
                logger.warning("[DatabaseService] ⚠️ Error limpiando engine de test: %s", cleanup_error)

    def get_sql_database_by_id(self, db_id: Union[int, str, "UUID"]) -> Optional[SQLDatabase]:
        logger.info("[DatabaseService] 🔄 Obteniendo SQLDatabase para DB id=%s", db_id)
        record = self.get_record(db_id)
        return self.get_sql_database_from_record(record) if record else None

    def get_sql_instance(self, db_id: Union[int, str, "UUID"]) -> SQLDatabase:
        logger.info("[DatabaseService] 🎯 Obteniendo instancia SQL para DB id=%s", db_id)
        db_instance = self.get_sql_database_by_id(db_id)
        if not db_instance:
            logger.error("[DatabaseService] ❌ No se pudo conectar a la base de datos id=%s", db_id)
            raise ValueError(f"No se pudo conectar a la base de datos {db_id}")
        return db_instance

    # Opcional: soporte de proxy (placeholder). Si no usas proxy real, deja que llame al normal.
    def get_sql_instance_with_proxy(self, db_id: Union[int, str, "UUID"], proxy_config: Optional[dict]) -> SQLDatabase:
        if proxy_config:
            logger.info("[DatabaseService] 🌐 Proxy DB recibido (no-op): %s", proxy_config)
        # Aquí podrías construir el engine usando túneles/SSH/DSN con proxy. Por ahora, directo:
        return self.get_sql_instance(db_id)

    def test_connection_by_id(self, db_id: Union[int, str, "UUID"]) -> bool:
        try:
            record = self.get_record(db_id)
            if not record:
                logger.warning("[DatabaseService] ⚠️ No existe conexión con id=%s", db_id)
                return False

            engine = self.build_sqlalchemy_engine(record)
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))

            logger.info("[DatabaseService] ✅ Conexión válida para DB id=%s", db_id)
            return True
        except Exception as e:
            logger.warning("[DatabaseService] ❌ Error al validar DB id=%s: %s", db_id, e)
            return False

    # Mantén este helper para llamadas antiguas desde otros servicios
    def get_sql_instance_from_action(self, action: dict, proxy_config: Optional[dict] = None) -> SQLDatabase:
        db_id = action.get("database_id") or action.get("db_id")
        if not db_id:
            raise ValueError("Acción db_query sin 'database_id'")

        logger.info("[DatabaseService] 📡 Obteniendo SQL instance para acción con DB id=%s", db_id)
        if proxy_config:
            return self.get_sql_instance_with_proxy(db_id, proxy_config)
        return self.get_sql_instance(db_id)

    def execute_sql(self, db_conn: SQLDatabase, sql: str) -> list:
        try:
            logger.info("[DatabaseService] 💾 Ejecutando SQL: %s", sql)
            result = db_conn.run(sql)
            logger.debug("[DatabaseService] ✅ Resultado: %s", result)
            return result
        except Exception as e:
            logger.error("[DatabaseService] ❌ Error al ejecutar SQL: %s", e)
            raise

    def get_dialect_name(self, db_id: int) -> Optional[str]:
            """
            Devuelve el nombre del dialecto (postgresql, mysql, mssql, sqlite, etc.)
            extraído del URI SQLAlchemy.
            """
            record = self.get_record(db_id)
            if not record:
                return None
            uri = build_sqlalchemy_uri(record)  # p.ej. "postgresql+psycopg2://..."
            scheme = uri.split("://", 1)[0]     # "postgresql+psycopg2"
            return scheme.split("+", 1)[0].lower()
    
    def get_connection_pool_stats(self) -> dict:
        """Obtiene estadísticas del pool de conexiones"""
        return self.connection_pool.get_pool_stats()
    
    def clear_connection_pool(self, db_id: Optional[str] = None):
        """Limpia el pool de conexiones"""
        self.connection_pool.clear_pool(db_id)
    
    def health_check_connections(self) -> dict:
        """Realiza health check de todas las conexiones del pool"""
        return self.connection_pool.health_check()

    def _clear_database_cache(self, db_id: Union[int, str, "UUID"]) -> None:
        """
        Limpia todo el cache relacionado con una base de datos específica.
        
        Args:
            db_id: ID de la base de datos
        """
        try:
            logger.info("[DatabaseService] 🧹 Limpiando cache para DB id=%s", db_id)
            
            # 🔧 NUEVO: Preparar Fase 4 (Orchestrator) para acceso a cache
            try:
                # Usar asyncio.run para ejecutar la función asíncrona en contexto síncrono
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self.factory.prepare_for_orchestrator())
                loop.close()
                logger.debug("[DatabaseService] ✅ Fase 4 (Orchestrator) preparada para cache")
            except Exception as e:
                logger.warning("[DatabaseService] ⚠️ No se pudo preparar Fase 4 para cache: %s", e)
                return
            
            # 1. Limpiar cache Redis (L1)
            try:
                # 🔧 CORREGIDO: Usar el método correcto del factory
                redis_cache = self.factory.get_redis_schema_cache()
                if redis_cache:
                    redis_cache.invalidate_schema(self.user.id, db_id)
                    logger.info("[DatabaseService] ✅ Cache Redis limpiado para DB %s", db_id)
                else:
                    logger.warning("[DatabaseService] ⚠️ Redis cache no disponible")
            except Exception as e:
                logger.warning("[DatabaseService] ⚠️ Error limpiando cache Redis: %s", e)
            
            # 2. Limpiar cache detallado (L2)
            try:
                # 🔧 CORREGIDO: Usar el método correcto del factory
                detailed_cache = self.factory.get_detailed_schema_cache_service()
                if detailed_cache:
                    detailed_cache.invalidate_cache(self.user.id, db_id)
                    logger.info("[DatabaseService] ✅ Cache detallado limpiado para DB %s", db_id)
                else:
                    logger.warning("[DatabaseService] ⚠️ Cache detallado no disponible")
            except Exception as e:
                logger.warning("[DatabaseService] ⚠️ Error limpiando cache detallado: %s", e)
            
            # 3. Limpiar cache en memoria (L3)
            try:
                # Buscar y eliminar entradas de cache en memoria relacionadas con esta DB
                from app.services.data.redis_cache_service import RedisCacheService
                redis_cache_service = RedisCacheService()
                cleared_count = redis_cache_service.clear_db_cache(str(db_id))
                if cleared_count > 0:
                    logger.info("[DatabaseService] ✅ Cache en memoria limpiado para DB %s (%d entradas)", db_id, cleared_count)
                else:
                    logger.info("[DatabaseService] ℹ️ No se encontraron entradas de cache en memoria para DB %s", db_id)
            except Exception as e:
                logger.warning("[DatabaseService] ⚠️ Error limpiando cache en memoria: %s", e)
                
            logger.info("[DatabaseService] 🧹 Limpieza de cache completada para DB %s", db_id)
            
        except Exception as e:
            logger.error("[DatabaseService] ❌ Error general limpiando cache de DB %s: %s", db_id, e)