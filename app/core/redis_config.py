import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisConfig:
    """Configuración para Redis con fallback a memoria"""
    
    def __init__(self):
        # Configuración desde variables de entorno
        redis_host_raw = os.getenv('REDIS_HOST', 'localhost')
        
        # Extraer hostname de URL de Upstash si es necesario
        if redis_host_raw.startswith('https://'):
            self.redis_host = redis_host_raw.replace('https://', '').split('/')[0]
        elif redis_host_raw.startswith('http://'):
            self.redis_host = redis_host_raw.replace('http://', '').split('/')[0]
        else:
            self.redis_host = redis_host_raw
            
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_db = int(os.getenv('REDIS_DB', '0'))
        self.redis_password = os.getenv('REDIS_PASSWORD', None)
        self.redis_ssl = os.getenv('REDIS_SSL', 'true')  # Upstash requiere SSL
        self.redis_timeout = int(os.getenv('REDIS_TIMEOUT', '10'))
        
        # TTLs por defecto (en segundos)
        self.schema_ttl = int(os.getenv('REDIS_SCHEMA_TTL', '86400'))  # 24 horas
        self.query_result_ttl = int(os.getenv('REDIS_QUERY_TTL', '7200'))  # 2 horas
        self.ai_plan_ttl = int(os.getenv('REDIS_PLAN_TTL', '21600'))  # 6 horas
        self.service_ttl = int(os.getenv('REDIS_SERVICE_TTL', '43200'))  # 12 horas
        
        # Configuración de pool
        self.max_connections = int(os.getenv('REDIS_MAX_CONNECTIONS', '10'))
        self.retry_on_timeout = os.getenv('REDIS_RETRY_ON_TIMEOUT', 'true').lower() == 'true'
        
        # Fallback a memoria
        self.use_memory_fallback = os.getenv('REDIS_USE_MEMORY_FALLBACK', 'true').lower() == 'true'
        
        # Logging
        self.log_level = os.getenv('REDIS_LOG_LEVEL', 'INFO')
    
    def get_redis_url(self) -> str:
        """Construye la URL de conexión a Redis"""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        else:
            return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"
    
    def get_connection_params(self) -> dict:
        """Obtiene parámetros de conexión para Redis"""
        params = {
            'host': self.redis_host,
            'port': self.redis_port,
            'db': self.redis_db,
            'socket_timeout': self.redis_timeout,
            'socket_connect_timeout': self.redis_timeout,
            'max_connections': self.max_connections,
        }
        
        # Retry on timeout está deprecated desde Redis 6.0, TimeoutError se incluye por defecto
        # Solo incluir si es explícitamente False
        if not self.retry_on_timeout:
            params['retry_on_timeout'] = False
        
        if self.redis_password:
            params['password'] = self.redis_password
        
        if self.redis_ssl:
            params['ssl'] = True
            params['ssl_cert_reqs'] = None
        
        return params
    
    def is_redis_available(self) -> bool:
        """Verifica si Redis está disponible"""
        try:
            import redis
            # Intentar conexión de prueba
            test_client = redis.Redis(**self.get_connection_params())
            test_client.ping()
            test_client.close()
            return True
        except Exception as e:
            logger.warning(f"[RedisConfig] ⚠️ Redis no disponible: {e}")
            return False
    
    def get_ttl_config(self) -> dict:
        """Obtiene configuración de TTLs"""
        return {
            'schema': self.schema_ttl,
            'query_result': self.query_result_ttl,
            'ai_plan': self.ai_plan_ttl,
            'service': self.service_ttl,
        }
    
    def log_config(self):
        """Registra la configuración actual"""
        logger.info("[RedisConfig] 🔧 Configuración Redis:")
        logger.info(f"  Host: {self.redis_host}:{self.redis_port}")
        logger.info(f"  DB: {self.redis_db}")
        logger.info(f"  SSL: {self.redis_ssl}")
        logger.info(f"  Timeout: {self.redis_timeout}s")
        logger.info(f"  Max Connections: {self.max_connections}")
        logger.info(f"  Schema TTL: {self.schema_ttl}s ({self.schema_ttl/3600:.1f}h)")
        logger.info(f"  Query TTL: {self.query_result_ttl}s ({self.query_result_ttl/3600:.1f}h)")
        logger.info(f"  AI Plan TTL: {self.ai_plan_ttl}s ({self.ai_plan_ttl/3600:.1f}h)")
        logger.info(f"  Service TTL: {self.service_ttl}s ({self.service_ttl/3600:.1f}h)")
        logger.info(f"  Memory Fallback: {self.use_memory_fallback}")
    
    def validate_config(self) -> bool:
        """Valida la configuración de Redis"""
        try:
            # Validar host
            if not self.redis_host:
                logger.error("[RedisConfig] ❌ REDIS_HOST no puede estar vacío")
                return False
            
            # Validar puerto
            if not (1 <= self.redis_port <= 65535):
                logger.error(f"[RedisConfig] ❌ Puerto inválido: {self.redis_port}")
                return False
            
            # Validar DB
            if not (0 <= self.redis_db <= 15):
                logger.error(f"[RedisConfig] ❌ DB inválida: {self.redis_db}")
                return False
            
            # Validar TTLs
            if self.schema_ttl <= 0:
                logger.error(f"[RedisConfig] ❌ TTL de esquema inválido: {self.schema_ttl}")
                return False
            
            if self.query_result_ttl <= 0:
                logger.error(f"[RedisConfig] ❌ TTL de consulta inválido: {self.query_result_ttl}")
                return False
            
            logger.info("[RedisConfig] ✅ Configuración válida")
            return True
            
        except Exception as e:
            logger.error(f"[RedisConfig] ❌ Error validando configuración: {e}")
            return False


# Instancia global de configuración
redis_config = RedisConfig()


def get_redis_config() -> RedisConfig:
    """Obtiene la configuración global de Redis"""
    return redis_config


def init_redis_config():
    """Inicializa y valida la configuración de Redis"""
    try:
        if redis_config.validate_config():
            redis_config.log_config()
            
            # Verificar disponibilidad
            if redis_config.is_redis_available():
                logger.info("[RedisConfig] 🚀 Redis disponible y configurado")
            else:
                if redis_config.use_memory_fallback:
                    logger.warning("[RedisConfig] ⚠️ Redis no disponible, usando fallback a memoria")
                else:
                    logger.error("[RedisConfig] ❌ Redis no disponible y fallback deshabilitado")
        else:
            logger.error("[RedisConfig] ❌ Configuración de Redis inválida")
            
    except Exception as e:
        logger.error(f"[RedisConfig] ❌ Error inicializando configuración: {e}")


# Inicializar al importar el módulo
init_redis_config()
