import logging
import json
import pickle
import time
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


class RedisCacheService:
    """Servicio de cache Redis para esquemas y resultados de consultas"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 default_ttl: int = 3600 * 24):  # 24 horas por defecto
        self.default_ttl = default_ttl
        
        if not REDIS_AVAILABLE:
            logger.warning("[RedisCacheService] ⚠️ Redis no disponible, usando cache en memoria")
            self._fallback_cache = {}
            self.redis_client = None
            return
        
        try:
            self.redis_client = redis.from_url(redis_url)
            # Test de conexión
            self.redis_client.ping()
            logger.info("[RedisCacheService] ✅ Conectado a Redis")
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error conectando a Redis: {e}")
            logger.warning("[RedisCacheService] ⚠️ Usando cache en memoria como fallback")
            self._fallback_cache = {}
            self.redis_client = None
    
    def _get_cache_key(self, cache_type: str, user_id: str, db_id: str, 
                       additional_key: str = None) -> str:
        """Genera una clave de cache consistente"""
        if additional_key:
            return f"apichat:{cache_type}:{user_id}:{db_id}:{additional_key}"
        return f"apichat:{cache_type}:{user_id}:{db_id}"
    
    def set_schema_cache(self, user_id: str, db_id: str, schema_data: Dict[str, Any], 
                        ttl: Optional[int] = None) -> bool:
        """Cachea el esquema de una base de datos"""
        cache_key = self._get_cache_key("schema", user_id, db_id)
        return self._set_cache(cache_key, schema_data, ttl or self.default_ttl)
    
    def get_schema_cache(self, user_id: str, db_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el esquema cacheado de una base de datos"""
        cache_key = self._get_cache_key("schema", user_id, db_id)
        return self._get_cache(cache_key)
    
    def has_schema_cache(self, user_id: str, db_id: str) -> bool:
        """Verifica si existe un esquema cacheado"""
        cache_key = self._get_cache_key("schema", user_id, db_id)
        return self._has_cache(cache_key)
    
    def set_query_result_cache(self, user_id: str, db_id: str, query_hash: str, 
                              result: Any, ttl: Optional[int] = None) -> bool:
        """Cachea el resultado de una consulta SQL"""
        cache_key = self._get_cache_key("query_result", user_id, db_id, query_hash)
        return self._set_cache(cache_key, result, ttl or (3600 * 2))  # 2 horas para resultados
    
    def get_query_result_cache(self, user_id: str, db_id: str, query_hash: str) -> Optional[Any]:
        """Obtiene el resultado cacheado de una consulta SQL"""
        cache_key = self._get_cache_key("query_result", user_id, db_id, query_hash)
        return self._get_cache(cache_key)
    
    def set_ai_plan_cache(self, user_id: str, question_hash: str, plan: Dict[str, Any], 
                          ttl: Optional[int] = None) -> bool:
        """Cachea el plan generado por la IA para una pregunta"""
        cache_key = self._get_cache_key("ai_plan", user_id, "global", question_hash)
        return self._set_cache(cache_key, plan, ttl or (3600 * 6))  # 6 horas para planes
    
    def get_ai_plan_cache(self, user_id: str, question_hash: str) -> Optional[Dict[str, Any]]:
        """Obtiene el plan cacheado de la IA para una pregunta"""
        cache_key = self._get_cache_key("ai_plan", user_id, "global", question_hash)
        return self._get_cache(cache_key)
    
    def set_service_cache(self, service_name: str, service_instance: Any, 
                         ttl: Optional[int] = None) -> bool:
        """Cachea una instancia de servicio"""
        cache_key = f"apichat:service:{service_name}"
        return self._set_cache(cache_key, service_instance, ttl or (3600 * 12))  # 12 horas para servicios
    
    def get_service_cache(self, service_name: str) -> Optional[Any]:
        """Obtiene una instancia de servicio cacheada"""
        cache_key = f"apichat:service:{service_name}"
        return self._get_cache(cache_key)
    
    def _set_cache(self, key: str, value: Any, ttl: int) -> bool:
        """Guarda un valor en cache con TTL"""
        try:
            if self.redis_client:
                # Serializar y guardar en Redis
                serialized = pickle.dumps(value)
                self.redis_client.setex(key, ttl, serialized)
                logger.debug(f"[RedisCacheService] 💾 Cache guardado: {key} (TTL: {ttl}s)")
                return True
            else:
                # Fallback a memoria
                self._fallback_cache[key] = {
                    'value': value,
                    'expires_at': time.time() + ttl
                }
                logger.debug(f"[RedisCacheService] 💾 Cache en memoria: {key} (TTL: {ttl}s)")
                return True
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error guardando cache {key}: {e}")
            return False
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Obtiene un valor del cache"""
        try:
            if self.redis_client:
                # Obtener de Redis
                data = self.redis_client.get(key)
                if data:
                    value = pickle.loads(data)
                    logger.debug(f"[RedisCacheService] 🔥 Cache HIT: {key}")
                    return value
                else:
                    logger.debug(f"[RedisCacheService] ❄️ Cache MISS: {key}")
                    return None
            else:
                # Fallback a memoria
                if key in self._fallback_cache:
                    cache_entry = self._fallback_cache[key]
                    if time.time() < cache_entry['expires_at']:
                        logger.debug(f"[RedisCacheService] 🔥 Cache HIT (memoria): {key}")
                        return cache_entry['value']
                    else:
                        # Expiró, remover
                        del self._fallback_cache[key]
                        logger.debug(f"[RedisCacheService] ⏰ Cache expirado: {key}")
                return None
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error obteniendo cache {key}: {e}")
            return None
    
    def _has_cache(self, key: str) -> bool:
        """Verifica si existe un valor en cache"""
        try:
            if self.redis_client:
                return self.redis_client.exists(key) > 0
            else:
                if key in self._fallback_cache:
                    cache_entry = self._fallback_cache[key]
                    if time.time() < cache_entry['expires_at']:
                        return True
                    else:
                        # Expiró, remover
                        del self._fallback_cache[key]
                return False
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error verificando cache {key}: {e}")
            return False
    
    def clear_user_cache(self, user_id: str) -> int:
        """Limpia todo el cache de un usuario"""
        try:
            if self.redis_client:
                # Buscar y eliminar todas las claves del usuario
                pattern = f"apichat:*:{user_id}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"[RedisCacheService] 🧹 Cache limpiado para usuario {user_id}: {len(keys)} entradas")
                    return len(keys)
                return 0
            else:
                # Fallback a memoria
                keys_to_remove = [
                    key for key in self._fallback_cache.keys()
                    if f":{user_id}:" in key
                ]
                for key in keys_to_remove:
                    del self._fallback_cache[key]
                logger.info(f"[RedisCacheService] 🧹 Cache en memoria limpiado para usuario {user_id}: {len(keys_to_remove)} entradas")
                return len(keys_to_remove)
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error limpiando cache del usuario {user_id}: {e}")
            return 0
    
    def clear_db_cache(self, db_id: str) -> int:
        """Limpia todo el cache de una base de datos específica"""
        try:
            if self.redis_client:
                # Buscar y eliminar todas las claves de la DB
                pattern = f"apichat:*:*:{db_id}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
                    logger.info(f"[RedisCacheService] 🧹 Cache limpiado para DB {db_id}: {len(keys)} entradas")
                    return len(keys)
                return 0
            else:
                # Fallback a memoria
                keys_to_remove = [
                    key for key in self._fallback_cache.keys()
                    if f":{db_id}:" in key
                ]
                for key in keys_to_remove:
                    del self._fallback_cache[key]
                logger.info(f"[RedisCacheService] 🧹 Cache en memoria limpiado para DB {db_id}: {len(keys_to_remove)} entradas")
                return len(keys_to_remove)
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error limpiando cache de la DB {db_id}: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        try:
            if self.redis_client:
                # Estadísticas de Redis
                info = self.redis_client.info()
                return {
                    'cache_type': 'redis',
                    'connected_clients': info.get('connected_clients', 0),
                    'used_memory_human': info.get('used_memory_human', 'N/A'),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'total_keys': sum(
                        int(db.get('keys', 0)) 
                        for db in info.get('keyspace', {}).values()
                    )
                }
            else:
                # Estadísticas de memoria
                total_keys = len(self._fallback_cache)
                expired_keys = sum(
                    1 for entry in self._fallback_cache.values()
                    if time.time() >= entry['expires_at']
                )
                return {
                    'cache_type': 'memory_fallback',
                    'total_keys': total_keys,
                    'expired_keys': expired_keys,
                    'active_keys': total_keys - expired_keys
                }
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error obteniendo estadísticas: {e}")
            return {'error': str(e)}
    
    def health_check(self) -> Dict[str, bool]:
        """Realiza health check del cache"""
        try:
            if self.redis_client:
                # Health check de Redis
                self.redis_client.ping()
                return {'redis': True}
            else:
                # Health check de memoria
                return {'memory_fallback': True}
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Health check falló: {e}")
            return {'error': str(e)}
    
    def warm_up_schema_cache(self, user_id: str, db_ids: list) -> Dict[str, bool]:
        """Pre-calienta el cache de esquemas para múltiples bases de datos"""
        results = {}
        
        for db_id in db_ids:
            if self.has_schema_cache(user_id, db_id):
                results[db_id] = True
                logger.info(f"[RedisCacheService] 🔥 Schema cache ya caliente para DB {db_id}")
            else:
                results[db_id] = False
                logger.info(f"[RedisCacheService] ❄️ Schema cache frío para DB {db_id}")
        
        return results
    
    def shutdown(self):
        """Apaga el servicio de cache"""
        try:
            if self.redis_client:
                self.redis_client.close()
                logger.info("[RedisCacheService] 🔌 Conexión Redis cerrada")
        except Exception as e:
            logger.error(f"[RedisCacheService] ❌ Error cerrando Redis: {e}")


# Función helper para generar hash de consultas
def generate_query_hash(query: str, params: Dict[str, Any] = None) -> str:
    """Genera un hash único para una consulta SQL y sus parámetros"""
    import hashlib
    
    # Combinar query y parámetros
    query_str = query.strip().lower()
    if params:
        param_str = json.dumps(params, sort_keys=True)
        query_str += param_str
    
    # Generar hash MD5
    return hashlib.md5(query_str.encode()).hexdigest()


# Función helper para generar hash de preguntas
def generate_question_hash(question: str, context: Dict[str, Any] = None) -> str:
    """Genera un hash único para una pregunta del usuario y su contexto"""
    import hashlib
    
    # Normalizar pregunta
    question_str = question.strip().lower()
    if context:
        context_str = json.dumps(context, sort_keys=True)
        question_str += context_str
    
    # Generar hash MD5
    return hashlib.md5(question_str.encode()).hexdigest()
