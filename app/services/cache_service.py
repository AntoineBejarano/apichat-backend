# app/services/cache_service.py
"""
CacheService
────────────
Servicio modular para manejar cache de esquemas de base de datos.
Diseñado para ser fácilmente extensible (JSON → Redis → etc.)
"""

import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)


class CacheService:
    """
    Servicio de cache modular para esquemas de base de datos.
    Actualmente usa JSON como storage, preparado para migrar a Redis.
    """
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "schema_cache.json"
        self.cache_ttl_hours = 24  # 24 horas por defecto
        
        # Cargar cache existente
        self._load_cache()
        logger.info(f"[CacheService] ✅ Inicializado con TTL={self.cache_ttl_hours}h")
    
    def _load_cache(self) -> None:
        """Cargar cache desde archivo JSON"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"[CacheService] 📂 Cache cargado: {len(self.cache)} usuarios")
            else:
                self.cache = {}
                logger.info("[CacheService] 🆕 Cache inicializado")
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error cargando cache: {e}")
            self.cache = {}
    
    def _save_cache(self) -> None:
        """Guardar cache a archivo JSON"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, default=str)
            logger.debug("[CacheService] 💾 Cache guardado")
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error guardando cache: {e}")
    
    def _get_user_cache_key(self, user_id: UUID) -> str:
        """Generar clave de cache para usuario"""
        return str(user_id)
    
    def _get_db_cache_key(self, db_id: UUID) -> str:
        """Generar clave de cache para base de datos"""
        return str(db_id)
    
    def _generate_schema_hash(self, tables: List[Dict[str, Any]]) -> str:
        """Generar hash del esquema para detectar cambios"""
        schema_str = json.dumps(tables, sort_keys=True)
        return hashlib.md5(schema_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Verificar si el cache es válido (no expirado)"""
        if not cache_entry:
            return False
        
        last_updated = cache_entry.get("last_updated")
        if not last_updated:
            return False
        
        # Convertir string a datetime si es necesario
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        
        # Verificar TTL
        ttl = timedelta(hours=self.cache_ttl_hours)
        return datetime.now(last_updated.tzinfo) - last_updated < ttl
    
    def get_cached_schema(self, user_id: UUID, db_id: UUID) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener esquema cacheado para una base de datos específica.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Lista de tablas si está cacheado y válido, None en caso contrario
        """
        user_key = self._get_user_cache_key(user_id)
        db_key = self._get_db_cache_key(db_id)
        
        user_cache = self.cache.get(user_key, {})
        db_cache = user_cache.get(db_key, {})
        
        if not self._is_cache_valid(db_cache):
            logger.debug(f"[CacheService] ⏰ Cache expirado para user={user_id}, db={db_id}")
            return None
        
        tables = db_cache.get("tables", [])
        logger.info(f"[CacheService] ✅ Cache hit: {len(tables)} tablas para user={user_id}, db={db_id}")
        return tables
    
    def cache_schema(self, user_id: UUID, db_id: UUID, tables: List[Dict[str, Any]]) -> None:
        """
        Cachear esquema de una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            tables: Lista de tablas con su esquema
        """
        user_key = self._get_user_cache_key(user_id)
        db_key = self._get_db_cache_key(db_id)
        
        # Inicializar cache de usuario si no existe
        if user_key not in self.cache:
            self.cache[user_key] = {}
        
        # Crear entrada de cache
        schema_hash = self._generate_schema_hash(tables)
        cache_entry = {
            "tables": tables,
            "last_updated": datetime.now().isoformat(),
            "schema_hash": schema_hash,
            "table_count": len(tables)
        }
        
        self.cache[user_key][db_key] = cache_entry
        self._save_cache()
        
        logger.info(f"[CacheService] 💾 Cacheado: {len(tables)} tablas para user={user_id}, db={db_id}")
    
    def get_cached_schemas_for_user(self, user_id: UUID, db_ids: List[UUID]) -> Dict[UUID, List[Dict[str, Any]]]:
        """
        Obtener esquemas cacheados para múltiples bases de datos de un usuario.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos
            
        Returns:
            Diccionario con esquemas cacheados: {db_id: [tables]}
        """
        cached_schemas = {}
        
        for db_id in db_ids:
            schema = self.get_cached_schema(user_id, db_id)
            if schema:
                cached_schemas[db_id] = schema
        
        logger.info(f"[CacheService] 📋 Esquemas cacheados: {len(cached_schemas)}/{len(db_ids)} para user={user_id}")
        return cached_schemas
    
    def invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidar todo el cache de un usuario"""
        user_key = self._get_user_cache_key(user_id)
        if user_key in self.cache:
            del self.cache[user_key]
            self._save_cache()
            logger.info(f"[CacheService] 🗑️ Cache invalidado para user={user_id}")
    
    def invalidate_db_cache(self, user_id: UUID, db_id: UUID) -> None:
        """Invalidar cache de una base de datos específica"""
        user_key = self._get_user_cache_key(user_id)
        db_key = self._get_db_cache_key(db_id)
        
        if user_key in self.cache and db_key in self.cache[user_key]:
            del self.cache[user_key][db_key]
            self._save_cache()
            logger.info(f"[CacheService] 🗑️ Cache invalidado para user={user_id}, db={db_id}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache"""
        total_users = len(self.cache)
        total_dbs = sum(len(user_cache) for user_cache in self.cache.values())
        
        return {
            "total_users": total_users,
            "total_databases": total_dbs,
            "cache_file": str(self.cache_file),
            "ttl_hours": self.cache_ttl_hours
        }
    
    def clear_all_cache(self) -> None:
        """Limpiar todo el cache"""
        self.cache = {}
        self._save_cache()
        logger.info("[CacheService] 🧹 Todo el cache limpiado")
    
    # Métodos preparados para futura migración a Redis
    def _redis_get(self, key: str) -> Optional[str]:
        """Placeholder para Redis GET"""
        # TODO: Implementar cuando se migre a Redis
        pass
    
    def _redis_set(self, key: str, value: str, ttl: int = None) -> None:
        """Placeholder para Redis SET"""
        # TODO: Implementar cuando se migre a Redis
        pass
    
    def _redis_delete(self, key: str) -> None:
        """Placeholder para Redis DELETE"""
        # TODO: Implementar cuando se migre a Redis
        pass
