"""
🔧 Cache Adapter - Provider-agnóstico para cache
────────────────────────────────────────────────
Implementa la Fase 9 del plan de refactorización:
- Redis (local/cloud)
- Upstash (serverless Redis)
- Configuración por ENV
- Fallbacks automáticos
"""

import os
import json
import logging
import time
from typing import Dict, Any, Optional, Union, List
from abc import ABC, abstractmethod

from .base_adapter import BaseAdapter, AdapterType, AdapterConfig


class CacheProvider(ABC):
    """Interfaz abstracta para proveedores de cache"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Establecer valor en cache con TTL opcional"""
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Eliminar clave del cache"""
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        """Verificar si existe una clave"""
        pass
    
    @abstractmethod
    def expire(self, key: str, ttl: int) -> bool:
        """Establecer TTL para una clave existente"""
        pass


class RedisProvider(CacheProvider):
    """Proveedor Redis (local/cloud)"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.redis")
        
        try:
            import redis
            self.redis_client = redis.Redis.from_url(
                config.url or "redis://localhost:6379/0",
                decode_responses=True,
                socket_timeout=config.timeout,
                socket_connect_timeout=config.timeout,
                retry_on_timeout=True,
                health_check_interval=30
            )
            self.logger.info(f"[RedisProvider] Conectado a {config.url or 'redis://localhost:6379/0'}")
        except ImportError:
            raise ImportError("Redis no está instalado. Ejecuta: pip install redis")
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error conectando a Redis: {e}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        try:
            value = self.redis_client.get(key)
            if value is not None:
                return json.loads(value)
            return None
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error obteniendo {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Establecer valor en cache con TTL opcional"""
        try:
            serialized_value = json.dumps(value, default=str)
            if ttl:
                return self.redis_client.setex(key, ttl, serialized_value)
            else:
                return self.redis_client.set(key, serialized_value)
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error estableciendo {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Eliminar clave del cache"""
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error eliminando {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Verificar si existe una clave"""
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error verificando {key}: {e}")
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Establecer TTL para una clave existente"""
        try:
            return bool(self.redis_client.expire(key, ttl))
        except Exception as e:
            self.logger.error(f"[RedisProvider] Error estableciendo TTL para {key}: {e}")
            return False


class UpstashProvider(CacheProvider):
    """Proveedor Upstash (serverless Redis)"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.upstash")
        
        try:
            from upstash_redis import Redis
            self.upstash_client = Redis.from_env()
            self.logger.info("[UpstashProvider] Conectado a Upstash desde variables de entorno")
        except ImportError:
            raise ImportError("Upstash Redis no está instalado. Ejecuta: pip install upstash-redis")
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error conectando a Upstash: {e}")
            raise
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        try:
            value = self.upstash_client.get(key)
            if value is not None:
                return json.loads(value)
            return None
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error obteniendo {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Establecer valor en cache con TTL opcional"""
        try:
            serialized_value = json.dumps(value, default=str)
            if ttl:
                return self.upstash_client.setex(key, ttl, serialized_value)
            else:
                return self.upstash_client.set(key, serialized_value)
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error estableciendo {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Eliminar clave del cache"""
        try:
            return bool(self.upstash_client.delete(key))
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error eliminando {key}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """Verificar si existe una clave"""
        try:
            return bool(self.upstash_client.exists(key))
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error verificando {key}: {e}")
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Establecer TTL para una clave existente"""
        try:
            return bool(self.upstash_client.expire(key, ttl))
        except Exception as e:
            self.logger.error(f"[UpstashProvider] Error estableciendo TTL para {key}: {e}")
            return False


class CacheAdapter(BaseAdapter):
    """
    🔧 Cache Adapter para la Fase 9
    
    Implementa:
    - Redis (local/cloud)
    - Upstash (serverless)
    - Configuración por ENV
    - Fallbacks automáticos
    """
    
    def __init__(self, config: Optional[AdapterConfig] = None):
        if config is None:
            config = self._load_config_from_env()
        
        super().__init__(AdapterType.CACHE, config)
        self.provider = self._create_provider()
        
        self.logger.info(f"[CacheAdapter] Inicializado con {config.provider}")
    
    def _load_config_from_env(self) -> AdapterConfig:
        """Cargar configuración desde variables de entorno"""
        provider = os.getenv("CACHE_PROVIDER", "redis").lower()
        url = os.getenv("CACHE_URL", "redis://localhost:6379/0")
        api_key = os.getenv("CACHE_API_KEY")
        timeout = int(os.getenv("CACHE_TIMEOUT", "10"))
        max_retries = int(os.getenv("CACHE_MAX_RETRIES", "3"))
        batch_size = int(os.getenv("CACHE_BATCH_SIZE", "100"))
        
        return AdapterConfig(
            provider=provider,
            url=url,
            api_key=api_key,
            timeout=timeout,
            max_retries=max_retries,
            batch_size=batch_size
        )
    
    def _create_provider(self) -> CacheProvider:
        """Crear proveedor de cache según configuración"""
        if self.config.provider == "redis":
            return RedisProvider(self.config)
        elif self.config.provider == "upstash":
            return UpstashProvider(self.config)
        else:
            raise ValueError(f"Proveedor de cache no soportado: {self.config.provider}")
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor del cache"""
        start_time = time.time()
        
        try:
            value = self.provider.get(key)
            self._update_metrics(True, time.time() - start_time)
            self._log_operation("get", key=key, success=True)
            return value
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("get", e, key=key)
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Establecer valor en cache con TTL opcional"""
        start_time = time.time()
        
        try:
            success = self.provider.set(key, value, ttl)
            self._update_metrics(success, time.time() - start_time)
            self._log_operation("set", key=key, ttl=ttl, success=success)
            return success
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("set", e, key=key, ttl=ttl)
            return False
    
    def delete(self, key: str) -> bool:
        """Eliminar clave del cache"""
        start_time = time.time()
        
        try:
            success = self.provider.delete(key)
            self._update_metrics(success, time.time() - start_time)
            self._log_operation("delete", key=key, success=success)
            return success
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("delete", e, key=key)
            return False
    
    def exists(self, key: str) -> bool:
        """Verificar si existe una clave"""
        start_time = time.time()
        
        try:
            exists = self.provider.exists(key)
            self._update_metrics(True, time.time() - start_time)
            self._log_operation("exists", key=key, result=exists)
            return exists
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("exists", e, key=key)
            return False
    
    def expire(self, key: str, ttl: int) -> bool:
        """Establecer TTL para una clave existente"""
        start_time = time.time()
        
        try:
            success = self.provider.expire(key, ttl)
            self._update_metrics(success, time.time() - start_time)
            self._log_operation("expire", key=key, ttl=ttl, success=success)
            return success
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("expire", e, key=key, ttl=ttl)
            return False
    
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Obtener múltiples valores del cache"""
        start_time = time.time()
        
        try:
            results = {}
            for key in keys:
                value = self.provider.get(key)
                if value is not None:
                    results[key] = value
            
            self._update_metrics(True, time.time() - start_time)
            self._log_operation("get_many", keys_count=len(keys), found_count=len(results))
            return results
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("get_many", e, keys_count=len(keys))
            return {}
    
    def set_many(self, data: Dict[str, Any], ttl: Optional[int] = None) -> Dict[str, bool]:
        """Establecer múltiples valores en cache"""
        start_time = time.time()
        
        try:
            results = {}
            for key, value in data.items():
                success = self.provider.set(key, value, ttl)
                results[key] = success
            
            success_count = sum(results.values())
            self._update_metrics(success_count > 0, time.time() - start_time)
            self._log_operation("set_many", keys_count=len(data), success_count=success_count)
            return results
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("set_many", e, keys_count=len(data))
            return {key: False for key in data.keys()}
    
    def clear_pattern(self, pattern: str) -> int:
        """Limpiar claves que coincidan con un patrón (solo Redis)"""
        if self.config.provider != "redis":
            self.logger.warning("[CacheAdapter] clear_pattern solo soportado en Redis")
            return 0
        
        start_time = time.time()
        
        try:
            # Implementar limpieza por patrón para Redis
            # Esto requiere acceso directo al cliente Redis
            if hasattr(self.provider, 'redis_client'):
                keys = self.provider.redis_client.keys(pattern)
                deleted = 0
                for key in keys:
                    if self.provider.delete(key):
                        deleted += 1
                
                self._update_metrics(True, time.time() - start_time)
                self._log_operation("clear_pattern", pattern=pattern, deleted_count=deleted)
                return deleted
            else:
                return 0
        except Exception as e:
            self._update_metrics(False, time.time() - start_time)
            self._log_error("clear_pattern", e, pattern=pattern)
            return 0
    
    def _health_check(self) -> bool:
        """Verificación de salud del adapter"""
        try:
            # Intentar una operación básica para verificar conectividad
            return self.provider.exists("health_check_test")
        except Exception as e:
            self.logger.error(f"[CacheAdapter] Health check falló: {e}")
            return False
    
    def initialize(self) -> bool:
        """Inicializar el adapter"""
        try:
            # Verificar conectividad básica
            health = self._health_check()
            if health:
                self.logger.info(f"[CacheAdapter] Inicializado correctamente con {self.config.provider}")
            return health
        except Exception as e:
            self.logger.error(f"[CacheAdapter] Error en inicialización: {e}")
            return False
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Obtener información del cache"""
        return {
            "provider": self.config.provider,
            "url": self.config.url,
            "timeout": self.config.timeout,
            "max_retries": self.config.max_retries,
            "batch_size": self.config.batch_size,
            "metrics": self.metrics.copy()
        }
