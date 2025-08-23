import logging
import time
import json
import hashlib
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)


class SchemaCacheService:
    """Cache persistente para esquemas SQL con TTL y optimizaciones"""
    
    def __init__(self, max_schemas: int = 100, ttl_hours: int = 24):
        self.max_schemas = max_schemas
        self.ttl_hours = ttl_hours
        
        # Cache de esquemas
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._timestamps: Dict[str, float] = {}
        self._access_count: Dict[str, int] = {}
        self._last_accessed: Dict[str, float] = {}
        self._schema_hashes: Dict[str, str] = {}  # Para detectar cambios
        
        # Lock para thread safety
        self._lock = Lock()
        
        # Estadísticas
        self._total_requests = 0
        self._total_cache_hits = 0
        self._total_cache_misses = 0
    
    def get_schema(self, user_id: str, db_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Obtiene un esquema del cache"""
        cache_key = f"{user_id}:{db_id}"
        
        with self._lock:
            self._total_requests += 1
            
            # Verificar si existe en cache y no ha expirado
            if not force_refresh and cache_key in self._schemas:
                if not self._is_expired(cache_key):
                    # Cache HIT
                    self._total_cache_hits += 1
                    self._access_count[cache_key] += 1
                    self._last_accessed[cache_key] = time.time()
                    
                    schema_data = self._schemas[cache_key]
                    logger.debug(f"[SchemaCacheService] 🔥 Cache HIT para DB {db_id} (usuario {user_id})")
                    
                    return schema_data
                else:
                    # Esquema expirado
                    logger.info(f"[SchemaCacheService] ⏰ Esquema expirado para DB {db_id} (usuario {user_id})")
                    self._remove_schema(cache_key)
            
            # Cache MISS
            self._total_cache_misses += 1
            logger.info(f"[SchemaCacheService] 🆕 Cache MISS para DB {db_id} (usuario {user_id})")
            return None
    
    def set_schema(self, user_id: str, db_id: str, schema_data: Dict[str, Any], 
                   schema_hash: Optional[str] = None) -> bool:
        """Guarda un esquema en el cache"""
        cache_key = f"{user_id}:{db_id}"
        
        with self._lock:
            try:
                # Calcular hash del esquema si no se proporciona
                if schema_hash is None:
                    schema_hash = self._calculate_schema_hash(schema_data)
                
                # Verificar si el esquema ha cambiado
                if cache_key in self._schema_hashes:
                    if self._schema_hashes[cache_key] == schema_hash:
                        logger.debug(f"[SchemaCacheService] 🔄 Esquema sin cambios para DB {db_id}")
                        # Actualizar timestamp de acceso
                        self._last_accessed[cache_key] = time.time()
                        return True
                    else:
                        logger.info(f"[SchemaCacheService] 🔄 Esquema actualizado para DB {db_id}")
                
                # Preparar entrada del cache
                cache_entry = {
                    'schema': schema_data,
                    'hash': schema_hash,
                    'created_at': datetime.utcnow().isoformat(),
                    'size_bytes': len(json.dumps(schema_data)),
                    'user_id': user_id,
                    'db_id': db_id
                }
                
                # Verificar si hay espacio en el cache
                if len(self._schemas) >= self.max_schemas:
                    self._evict_least_used()
                
                # Guardar en cache
                self._schemas[cache_key] = cache_entry
                self._timestamps[cache_key] = time.time()
                self._last_accessed[cache_key] = time.time()
                self._access_count[cache_key] = 1
                self._schema_hashes[cache_key] = schema_hash
                
                logger.info(f"[SchemaCacheService] ✅ Esquema cacheado para DB {db_id} (usuario {user_id})")
                logger.debug(f"[SchemaCacheService] 📊 Tamaño: {cache_entry['size_bytes']} bytes")
                
                return True
                
            except Exception as e:
                logger.error(f"[SchemaCacheService] ❌ Error cacheando esquema para DB {db_id}: {e}")
                return False
    
    def has_schema(self, user_id: str, db_id: str) -> bool:
        """Verifica si existe un esquema en cache"""
        cache_key = f"{user_id}:{db_id}"
        
        with self._lock:
            if cache_key in self._schemas:
                return not self._is_expired(cache_key)
            return False
    
    def get_schema_hash(self, user_id: str, db_id: str) -> Optional[str]:
        """Obtiene el hash del esquema cacheado"""
        cache_key = f"{user_id}:{db_id}"
        
        with self._lock:
            if cache_key in self._schema_hashes:
                return self._schema_hashes[cache_key]
            return None
    
    def _calculate_schema_hash(self, schema_data: Dict[str, Any]) -> str:
        """Calcula un hash del esquema para detectar cambios"""
        try:
            # Convertir a string ordenado para hash consistente
            schema_str = json.dumps(schema_data, sort_keys=True)
            return hashlib.md5(schema_str.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"[SchemaCacheService] ⚠️ Error calculando hash: {e}")
            return str(time.time())  # Fallback
    
    def _is_expired(self, cache_key: str) -> bool:
        """Verifica si un esquema ha expirado"""
        if cache_key not in self._timestamps:
            return True
        
        timestamp = self._timestamps[cache_key]
        expiration_time = timestamp + (self.ttl_hours * 3600)
        
        return time.time() > expiration_time
    
    def _evict_least_used(self):
        """Elimina el esquema menos usado del cache"""
        if not self._access_count:
            return
        
        # Encontrar esquema con menos accesos
        least_used = min(self._access_count.items(), key=lambda x: x[1])
        cache_key = least_used[0]
        
        logger.info(f"[SchemaCacheService] 🗑️ Evicting least used schema: {cache_key}")
        self._remove_schema(cache_key)
    
    def _remove_schema(self, cache_key: str):
        """Remueve un esquema del cache"""
        if cache_key in self._schemas:
            del self._schemas[cache_key]
        if cache_key in self._timestamps:
            del self._timestamps[cache_key]
        if cache_key in self._access_count:
            del self._access_count[cache_key]
        if cache_key in self._last_accessed:
            del self._last_accessed[cache_key]
        if cache_key in self._schema_hashes:
            del self._schema_hashes[cache_key]
    
    def clear_user_cache(self, user_id: str) -> int:
        """Limpia el cache para un usuario específico"""
        with self._lock:
            keys_to_remove = [
                key for key in self._schemas.keys()
                if key.startswith(f"{user_id}:")
            ]
            
            for key in keys_to_remove:
                self._remove_schema(key)
            
            logger.info(f"[SchemaCacheService] 🧹 Cache limpiado para usuario {user_id}: {len(keys_to_remove)} entradas removidas")
            return len(keys_to_remove)
    
    def clear_db_cache(self, db_id: str) -> int:
        """Limpia el cache para una base de datos específica"""
        with self._lock:
            keys_to_remove = [
                key for key in self._schemas.keys()
                if key.endswith(f":{db_id}")
            ]
            
            for key in keys_to_remove:
                self._remove_schema(key)
            
            logger.info(f"[SchemaCacheService] 🧹 Cache limpiado para DB {db_id}: {len(keys_to_remove)} entradas removidas")
            return len(keys_to_remove)
    
    def clear_all_cache(self) -> int:
        """Limpia todo el cache"""
        with self._lock:
            entries_count = len(self._schemas)
            
            self._schemas.clear()
            self._timestamps.clear()
            self._access_count.clear()
            self._last_accessed.clear()
            self._schema_hashes.clear()
            
            logger.info(f"[SchemaCacheService] 🧹 Cache completamente limpiado: {entries_count} entradas removidas")
            return entries_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        with self._lock:
            total_entries = len(self._schemas)
            total_size_bytes = sum(
                entry.get('size_bytes', 0) 
                for entry in self._schemas.values()
            )
            
            # Calcular hit ratio
            hit_ratio = 0
            if self._total_requests > 0:
                hit_ratio = (self._total_cache_hits / self._total_requests) * 100
            
            # Encontrar entradas más y menos accedidas
            most_accessed = max(self._access_count.items(), key=lambda x: x[1]) if self._access_count else None
            least_accessed = min(self._access_count.items(), key=lambda x: x[1]) if self._access_count else None
            
            return {
                'total_entries': total_entries,
                'max_entries': self.max_schemas,
                'total_size_bytes': total_size_bytes,
                'total_size_mb': total_size_bytes / (1024 * 1024),
                'total_requests': self._total_requests,
                'total_cache_hits': self._total_cache_hits,
                'total_cache_misses': self._total_cache_misses,
                'hit_ratio': hit_ratio,
                'ttl_hours': self.ttl_hours,
                'most_accessed_key': most_accessed[0] if most_accessed else None,
                'most_accessed_count': most_accessed[1] if most_accessed else 0,
                'least_accessed_key': least_accessed[0] if least_accessed else None,
                'least_accessed_count': least_accessed[1] if least_accessed else 0,
                'entries_details': {
                    cache_key: {
                        'age_seconds': time.time() - self._timestamps.get(cache_key, 0),
                        'last_accessed_seconds': time.time() - self._last_accessed.get(cache_key, 0),
                        'access_count': self._access_count.get(cache_key, 0),
                        'size_bytes': entry.get('size_bytes', 0),
                        'user_id': entry.get('user_id'),
                        'db_id': entry.get('db_id')
                    }
                    for cache_key, entry in self._schemas.items()
                }
            }
    
    def warm_up_cache(self, user_id: str, db_ids: list) -> Dict[str, bool]:
        """Pre-calienta el cache para múltiples bases de datos"""
        results = {}
        
        for db_id in db_ids:
            if self.has_schema(user_id, db_id):
                results[db_id] = True
                logger.info(f"[SchemaCacheService] 🔥 Cache ya caliente para DB {db_id}")
            else:
                results[db_id] = False
                logger.info(f"[SchemaCacheService] ❄️ Cache frío para DB {db_id}")
        
        return results
    
    def cleanup_expired(self) -> int:
        """Limpia esquemas expirados"""
        with self._lock:
            expired_keys = [
                key for key in self._schemas.keys()
                if self._is_expired(key)
            ]
            
            for key in expired_keys:
                self._remove_schema(key)
            
            if expired_keys:
                logger.info(f"[SchemaCacheService] 🧹 Limpiados {len(expired_keys)} esquemas expirados")
            
            return len(expired_keys)
    
    def get_schema_info(self, user_id: str, db_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información detallada de un esquema cacheado"""
        cache_key = f"{user_id}:{db_id}"
        
        with self._lock:
            if cache_key in self._schemas:
                entry = self._schemas[cache_key]
                return {
                    'cache_key': cache_key,
                    'user_id': entry.get('user_id'),
                    'db_id': entry.get('db_id'),
                    'created_at': entry.get('created_at'),
                    'size_bytes': entry.get('size_bytes', 0),
                    'age_seconds': time.time() - self._timestamps.get(cache_key, 0),
                    'last_accessed_seconds': time.time() - self._last_accessed.get(cache_key, 0),
                    'access_count': self._access_count.get(cache_key, 0),
                    'is_expired': self._is_expired(cache_key),
                    'hash': entry.get('hash')
                }
            return None
