# app/services/cache_service.py
"""
CacheService - Cache Compartido entre Chats 🔒
─────────────────────────────────────────────
Servicio de cache que mantiene datos compartidos entre todos los chats de un usuario.
Cada usuario tiene su propio archivo de cache, con esquemas, funciones y preferencias compartidas.
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
    Servicio de cache compartido entre chats para máxima eficiencia y experiencia de usuario.
    Cada usuario tiene su propio archivo de cache con datos compartidos entre sesiones.
    """
    
    def __init__(self, cache_dir: str = "cache", factory=None):
        self.factory = factory
        self.db = getattr(factory, 'db', None) if factory else None
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # 🔒 SEGURIDAD: Cache aislado por usuario
        self.current_user_id = None
        self.user_cache_file = None
        self.user_cache = {}
        
        # 🔒 SEGURIDAD: Solo inicializar si hay usuario válido
        if self.factory and hasattr(self.factory, 'user') and self.factory.user:
            self._initialize_user_cache(self.factory.user.id)
        else:
            logger.warning("[CacheService] ⚠️ No hay usuario válido para inicializar cache")
    
    def _initialize_user_cache(self, user_id: UUID) -> None:
        """Inicializar cache para un usuario específico"""
        try:
            self.current_user_id = user_id
            user_id_str = str(user_id)
            
            # 🔒 SEGURIDAD: Archivo de cache único por usuario
            self.user_cache_file = self.cache_dir / f"user_{user_id_str}.json"
            
            # Cargar cache existente o crear nuevo
            self._load_user_cache()
            
            # 🔧 INTELIGENCIA: Detectar si es usuario nuevo
            if not self.user_cache or len(self.user_cache) == 0 or "user_id" not in self.user_cache:
                self._initialize_new_user_cache(user_id_str)
                logger.info(f"[CacheService] 🆕 Usuario nuevo: cache inicializado para {user_id_str[:8]}...")
            else:
                # Usuario existente, marcar como no nuevo
                if "is_new_user" in self.user_cache:
                    self.user_cache["is_new_user"] = False
                logger.info(f"[CacheService] 🔒 Cache cargado para usuario {user_id_str[:8]}...")
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error inicializando cache para usuario {user_id}: {e}")
            self.user_cache = {}
    
    def _initialize_new_user_cache(self, user_id_str: str) -> None:
        """Inicializar cache para un usuario completamente nuevo"""
        try:
            now = datetime.now().isoformat()
            
            self.user_cache = {
                "user_id": user_id_str,
                "created_at": now,
                "last_used": now,
                "is_new_user": True,
                
                # 🧠 CACHE INTELIGENTE: Estructura compartida entre chats
                "schema_cache": {},           # Esquemas de DBs compartidos
                "function_cache": {},         # Funciones de apps compartidas
                "preferences": {              # Preferencias del usuario
                    "default_mode": "explorer",
                    "timeout_seconds": 30,
                    "max_results": 10,
                    "cache_ttl_hours": 24
                },
                "chat_sessions": {},         # Metadatos de chats activos
                "statistics": {              # Estadísticas de uso
                    "total_chats": 0,
                    "total_cache_hits": 0,
                    "total_cache_misses": 0,
                    "cache_efficiency": 0.0
                }
            }
            
            # Guardar cache inicial
            self._save_user_cache()
            logger.info(f"[CacheService] ⚙️ Preferencias por defecto configuradas para usuario {user_id_str[:8]}...")
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error inicializando cache para usuario nuevo {user_id_str}: {e}")
            self.user_cache = {}
    
    def _load_user_cache(self) -> None:
        """Cargar cache del usuario actual desde su archivo específico"""
        try:
            if self.user_cache_file and self.user_cache_file.exists():
                with open(self.user_cache_file, 'r', encoding='utf-8') as f:
                    self.user_cache = json.load(f)
                
                # Actualizar timestamp de último uso
                self.user_cache["last_used"] = datetime.now().isoformat()
                
                logger.debug(f"[CacheService] 📂 Cache cargado para usuario {str(self.current_user_id)[:8]}...")
            else:
                self.user_cache = {}
                logger.debug(f"[CacheService] 🆕 Cache inicializado para usuario {str(self.current_user_id)[:8]}...")
                
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error cargando cache del usuario: {e}")
            self.user_cache = {}
    
    def _save_user_cache(self) -> None:
        """Guardar cache del usuario actual a su archivo específico"""
        try:
            if self.user_cache_file and self.current_user_id:
                # Actualizar timestamp antes de guardar
                self.user_cache["last_used"] = datetime.now().isoformat()
                
                # 🔧 FIX: Convertir UUIDs a strings antes de serializar
                cache_to_save = self._prepare_cache_for_save(self.user_cache)
                
                with open(self.user_cache_file, 'w', encoding='utf-8') as f:
                    json.dump(cache_to_save, f, indent=2, default=str)
                logger.debug(f"[CacheService] 💾 Cache guardado para usuario {str(self.current_user_id)[:8]}...")
                
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error guardando cache del usuario: {e}")
    
    def _prepare_cache_for_save(self, cache_data: Any) -> Any:
        """Preparar cache para serialización JSON convirtiendo UUIDs a strings"""
        if isinstance(cache_data, dict):
            return {key: self._prepare_cache_for_save(value) for key, value in cache_data.items()}
        elif isinstance(cache_data, list):
            return [self._prepare_cache_for_save(item) for item in cache_data]
        elif isinstance(cache_data, UUID):
            return str(cache_data)
        else:
            return cache_data
    
    def _validate_user_access(self, user_id: UUID) -> bool:
        """Validar que solo se acceda al cache del usuario actual"""
        if not self.current_user_id:
            logger.error("[CacheService] ❌ No hay usuario actual para validar acceso")
            return False
        
        if user_id != self.current_user_id:
            logger.error(f"[CacheService] ❌ Acceso denegado: usuario {user_id} no puede acceder al cache de {self.current_user_id}")
            return False
        
        return True
    
    def _get_db_cache_key(self, db_id: UUID) -> str:
        """Generar clave de cache para base de datos"""
        return str(db_id)
    
    def _get_app_cache_key(self, app_id: UUID) -> str:
        """Generar clave de cache para aplicación"""
        return str(app_id)
    
    def _generate_schema_hash(self, tables: List[Dict[str, Any]]) -> str:
        """Generar hash del esquema para detectar cambios"""
        schema_str = json.dumps(tables, sort_keys=True, default=str)
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
        
        # Obtener TTL desde preferencias del usuario
        ttl_hours = self.user_cache.get("preferences", {}).get("cache_ttl_hours", 24)
        ttl = timedelta(hours=ttl_hours)
        
        return datetime.now(last_updated.tzinfo) - last_updated < ttl
    
    def _update_chat_session(self, chat_id: str, increment_message: bool = False) -> None:
        """
        Actualizar metadatos de sesión de chat
        
        Args:
            chat_id: ID del chat
            increment_message: Si debe incrementar el contador de mensajes
        """
        try:
            now = datetime.now().isoformat()
            
            if "chat_sessions" not in self.user_cache:
                self.user_cache["chat_sessions"] = {}
            
            if chat_id not in self.user_cache["chat_sessions"]:
                # Nuevo chat
                self.user_cache["chat_sessions"][chat_id] = {
                    "created_at": now,
                    "last_used": now,
                    "message_count": 1 if increment_message else 0
                }
                # 🔧 FIX: Incrementar total_chats solo cuando se crea un nuevo chat
                if "statistics" not in self.user_cache:
                    self.user_cache["statistics"] = {
                        "total_chats": 0,
                        "total_cache_hits": 0,
                        "total_cache_misses": 0,
                        "cache_efficiency": 0.0
                    }
                self.user_cache["statistics"]["total_chats"] += 1
                logger.debug(f"[CacheService] 💬 Nuevo chat registrado: {chat_id}")
            else:
                # Chat existente
                self.user_cache["chat_sessions"][chat_id]["last_used"] = now
                if increment_message:
                    self.user_cache["chat_sessions"][chat_id]["message_count"] += 1
            
        except Exception as e:
            logger.warning(f"[CacheService] ⚠️ Error actualizando sesión de chat {chat_id}: {e}")
    
    def _update_cache_statistics(self, is_hit: bool) -> None:
        """Actualizar estadísticas de cache"""
        try:
            if "statistics" not in self.user_cache:
                self.user_cache["statistics"] = {
                    "total_chats": 0,
                    "total_cache_hits": 0,
                    "total_cache_misses": 0,
                    "cache_efficiency": 0.0
                }
            
            if is_hit:
                self.user_cache["statistics"]["total_cache_hits"] += 1
            else:
                self.user_cache["statistics"]["total_cache_misses"] += 1
            
            # Calcular eficiencia
            total_requests = self.user_cache["statistics"]["total_cache_hits"] + self.user_cache["statistics"]["total_cache_misses"]
            if total_requests > 0:
                efficiency = (self.user_cache["statistics"]["total_cache_hits"] / total_requests) * 100
                self.user_cache["statistics"]["cache_efficiency"] = round(efficiency, 1)
            
        except Exception as e:
            logger.warning(f"[CacheService] ⚠️ Error actualizando estadísticas: {e}")
    
    def get_cached_schema(self, user_id: UUID, db_id: UUID, chat_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener esquema cacheado para una base de datos específica.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            chat_id: ID del chat (opcional, para estadísticas)
            
        Returns:
            Lista de tablas si está cacheado y válido, None en caso contrario
        """
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return None
        
        # Actualizar sesión de chat si se proporciona
        if chat_id:
            self._update_chat_session(chat_id, increment_message=False)
        
        db_key = self._get_db_cache_key(db_id)
        schema_cache = self.user_cache.get("schema_cache", {})
        db_cache = schema_cache.get(db_key, {})
        
        if not self._is_cache_valid(db_cache):
            logger.debug(f"[CacheService] ⏰ Cache expirado para db={db_id}")
            self._update_cache_statistics(False)  # Cache miss
            return None
        
        tables = db_cache.get("tables", [])
        
        # Actualizar estadísticas y metadatos
        self._update_cache_statistics(True)  # Cache hit
        
        # Actualizar uso en chats
        if chat_id and "used_in_chats" not in db_cache:
            db_cache["used_in_chats"] = []
        if chat_id and chat_id not in db_cache.get("used_in_chats", []):
            db_cache["used_in_chats"].append(chat_id)
        
        logger.info(f"[CacheService] ✅ Cache hit: {len(tables)} tablas para db={db_id}")
        return tables
    
    def cache_schema(self, user_id: UUID, db_id: UUID, tables: List[Dict[str, Any]], chat_id: str = None) -> None:
        """
        Cachear esquema de una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            tables: Lista de tablas con su esquema
            chat_id: ID del chat (opcional, para metadatos)
        """
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return
        
        db_key = self._get_db_cache_key(db_id)
        
        # Inicializar schema_cache si no existe
        if "schema_cache" not in self.user_cache:
            self.user_cache["schema_cache"] = {}
        
        # Crear entrada de cache
        schema_hash = self._generate_schema_hash(tables)
        cache_entry = {
            "tables": tables,
            "last_updated": datetime.now().isoformat(),
            "schema_hash": schema_hash,
            "table_count": len(tables),
            "used_in_chats": [chat_id] if chat_id else []
        }
        
        self.user_cache["schema_cache"][db_key] = cache_entry
        
        # Actualizar sesión de chat si se proporciona
        if chat_id:
            self._update_chat_session(chat_id, increment_message=True)
        
        self._save_user_cache()
        
        logger.info(f"[CacheService] 💾 Cacheado: {len(tables)} tablas para db={db_id}")
        
        # 🔥 CACHE WARMING: Log para usuario nuevo
        if self.user_cache.get("is_new_user", False):
            logger.info(f"[CacheService] 🔥 Cache warming: DB {db_id} para usuario nuevo")
    
    def get_cached_functions(self, user_id: UUID, app_id: UUID, chat_id: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener funciones cacheadas para una aplicación específica.
        
        Args:
            user_id: ID del usuario
            app_id: ID de la aplicación
            chat_id: ID del chat (opcional, para estadísticas)
            
        Returns:
            Lista de funciones si está cacheado y válido, None en caso contrario
        """
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return None
        
        # Actualizar sesión de chat si se proporciona
        if chat_id:
            self._update_chat_session(chat_id)
        
        app_key = self._get_app_cache_key(app_id)
        function_cache = self.user_cache.get("function_cache", {})
        app_cache = function_cache.get(app_key, {})
        
        if not self._is_cache_valid(app_cache):
            logger.debug(f"[CacheService] ⏰ Cache de funciones expirado para app={app_id}")
            self._update_cache_statistics(False)  # Cache miss
            return None
        
        functions = app_cache.get("functions", [])
        
        # Actualizar estadísticas y metadatos
        self._update_cache_statistics(True)  # Cache hit
        
        # Actualizar uso en chats
        if chat_id and "used_in_chats" not in app_cache:
            app_cache["used_in_chats"] = []
        if chat_id and chat_id not in app_cache.get("used_in_chats", []):
            app_cache["used_in_chats"].append(chat_id)
        
        logger.info(f"[CacheService] ✅ Cache hit: {len(functions)} funciones para app={app_id}")
        return functions
    
    def cache_functions(self, user_id: UUID, app_id: UUID, functions: List[Dict[str, Any]], chat_id: str = None) -> None:
        """
        Cachear funciones de una aplicación.
        
        Args:
            user_id: ID del usuario
            app_id: ID de la aplicación
            functions: Lista de funciones con su información
            chat_id: ID del chat (opcional, para metadatos)
        """
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return
        
        app_key = self._get_app_cache_key(app_id)
        
        # Inicializar function_cache si no existe
        if "function_cache" not in self.user_cache:
            self.user_cache["function_cache"] = {}
        
        # Crear entrada de cache
        cache_entry = {
            "functions": functions,
            "last_updated": datetime.now().isoformat(),
            "function_count": len(functions),
            "used_in_chats": [chat_id] if chat_id else []
        }
        
        self.user_cache["function_cache"][app_key] = cache_entry
        
        # Actualizar sesión de chat si se proporciona
        if chat_id:
            self._update_chat_session(chat_id, increment_message=True)
        
        self._save_user_cache()
        
        logger.info(f"[CacheService] 💾 Cacheado: {len(functions)} funciones para app={app_id}")
    
    def get_user_preferences(self, user_id: UUID) -> Dict[str, Any]:
        """Obtener preferencias del usuario"""
        if not self._validate_user_access(user_id):
            return {}
        
        return self.user_cache.get("preferences", {})
    
    def update_user_preferences(self, user_id: UUID, preferences: Dict[str, Any]) -> bool:
        """Actualizar preferencias del usuario"""
        if not self._validate_user_access(user_id):
            return False
        
        try:
            if "preferences" not in self.user_cache:
                self.user_cache["preferences"] = {}
            
            self.user_cache["preferences"].update(preferences)
            self._save_user_cache()
            
            logger.info(f"[CacheService] ⚙️ Preferencias actualizadas para usuario {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error actualizando preferencias: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache del usuario actual"""
        if not self.current_user_id:
            return {"error": "No hay usuario actual"}
        
        stats = self.user_cache.get("statistics", {})
        schema_cache = self.user_cache.get("schema_cache", {})
        function_cache = self.user_cache.get("function_cache", {})
        chat_sessions = self.user_cache.get("chat_sessions", {})
        
        return {
            "current_user": str(self.current_user_id),
            "total_databases": len(schema_cache),
            "total_applications": len(function_cache),
            "total_chats": len(chat_sessions),
            "cache_file": str(self.user_cache_file) if self.user_cache_file else None,
            "cache_efficiency": stats.get("cache_efficiency", 0.0),
            "total_cache_hits": stats.get("total_cache_hits", 0),
            "total_cache_misses": stats.get("total_cache_misses", 0),
            "is_new_user": self.user_cache.get("is_new_user", False)
        }
    
    def get_cached_schemas_for_user(self, user_id: UUID, db_ids: List[UUID], chat_id: str = None) -> Dict[UUID, List[Dict[str, Any]]]:
        """
        Obtener esquemas cacheados para múltiples bases de datos de un usuario.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos
            chat_id: ID del chat (opcional, para estadísticas)
            
        Returns:
            Diccionario con esquemas cacheados: {db_id: [tables]}
        """
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return {}
        
        cached_schemas = {}
        
        for db_id in db_ids:
            schema = self.get_cached_schema(user_id, db_id, chat_id)
            if schema:
                cached_schemas[db_id] = schema
        
        logger.info(f"[CacheService] 📋 Esquemas cacheados: {len(cached_schemas)}/{len(db_ids)}")
        return cached_schemas
    
    def invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidar todo el cache de un usuario"""
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return
        
        # Mantener solo estructura básica
        basic_cache = {
            "user_id": str(user_id),
            "created_at": self.user_cache.get("created_at", datetime.now().isoformat()),
            "last_used": datetime.now().isoformat(),
            "is_new_user": False,
            "schema_cache": {},
            "function_cache": {},
            "preferences": self.user_cache.get("preferences", {}),
            "chat_sessions": {},
            "statistics": {
                "total_chats": 0,
                "total_cache_hits": 0,
                "total_cache_misses": 0,
                "cache_efficiency": 0.0
            }
        }
        
        self.user_cache = basic_cache
        self._save_user_cache()
        logger.info(f"[CacheService] 🗑️ Cache invalidado para usuario {user_id}")
    
    def invalidate_db_cache(self, user_id: UUID, db_id: UUID) -> None:
        """Invalidar cache de una base de datos específica"""
        # 🔒 SEGURIDAD: Validar acceso del usuario
        if not self._validate_user_access(user_id):
            return
        
        db_key = self._get_db_cache_key(db_id)
        schema_cache = self.user_cache.get("schema_cache", {})
        
        if db_key in schema_cache:
            del schema_cache[db_key]
            self._save_user_cache()
            logger.info(f"[CacheService] 🗑️ Cache invalidado para db={db_id}")
    
    def clear_all_cache(self) -> None:
        """Limpiar todo el cache del usuario actual"""
        if not self.current_user_id:
            return
        
        self.invalidate_user_cache(self.current_user_id)
        logger.info(f"[CacheService] 🧹 Cache limpiado para usuario {self.current_user_id}")
    
    # 🔒 COMPATIBILIDAD: Método get para compatibilidad con otros servicios
    def get(self, key: str, default: Any = None) -> Any:
        """
        Método get para compatibilidad con otros servicios.
        Busca en el cache del usuario actual por clave.
        
        Args:
            key: Clave a buscar
            default: Valor por defecto si no se encuentra
            
        Returns:
            Valor encontrado o default
        """
        try:
            # Buscar en cache de esquemas
            if ":" in key:  # Formato user_id:db_id
                parts = key.split(":", 1)
                if len(parts) == 2:
                    user_id, db_id = parts[0], parts[1]
                    # 🔒 SEGURIDAD: Solo permitir acceso al usuario actual
                    if user_id == str(self.current_user_id):
                        return self.get_cached_schema(UUID(user_id), UUID(db_id)) or default
                    else:
                        logger.warning(f"[CacheService] ⚠️ Acceso denegado a cache de usuario {user_id}")
                        return default
            
            # Buscar en cache general del usuario actual
            return self.user_cache.get(key, default)
            
        except Exception as e:
            logger.warning(f"[CacheService] ⚠️ Error en método get para clave '{key}': {e}")
            return default
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Método set para compatibilidad con otros servicios.
        
        Args:
            key: Clave a almacenar
            value: Valor a almacenar
            ttl: TTL en segundos (opcional)
            
        Returns:
            True si se almacenó correctamente
        """
        try:
            # Para esquemas, usar cache_schema
            if ":" in key and isinstance(value, dict) and "tables" in value:
                parts = key.split(":", 1)
                if len(parts) == 2:
                    user_id, db_id = parts[0], parts[1]
                    # 🔒 SEGURIDAD: Solo permitir acceso al usuario actual
                    if user_id == str(self.current_user_id):
                        self.cache_schema(UUID(user_id), UUID(db_id), value.get("tables", []))
                        return True
                    else:
                        logger.warning(f"[CacheService] ⚠️ Acceso denegado a cache de usuario {user_id}")
                        return False
            
            # Para otros tipos de datos
            self.user_cache[key] = value
            self._save_user_cache()
            return True
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error en método set para clave '{key}': {e}")
            return False
    
    def switch_user(self, new_user_id: UUID) -> None:
        """
        Cambiar al cache de otro usuario (útil para testing o admin)
        
        Args:
            new_user_id: ID del nuevo usuario
        """
        try:
            # Guardar cache actual si existe
            if self.current_user_id:
                self._save_user_cache()
            
            # Cambiar a nuevo usuario
            self._initialize_user_cache(new_user_id)
            logger.info(f"[CacheService] 🔄 Cambiado a usuario {new_user_id}")
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error cambiando usuario: {e}")
    
    def cleanup_old_cache_files(self, max_age_hours: int = 168) -> int:
        """
        Limpiar archivos de cache antiguos (solo para mantenimiento del sistema)
        
        Args:
            max_age_hours: Edad máxima en horas (por defecto 1 semana)
            
        Returns:
            Número de archivos eliminados
        """
        try:
            if not self.current_user_id:
                logger.warning("[CacheService] ⚠️ No se puede limpiar cache sin usuario actual")
                return 0
            
            max_age = timedelta(hours=max_age_hours)
            cutoff_time = datetime.now() - max_age
            deleted_count = 0
            
            for cache_file in self.cache_dir.glob("user_*.json"):
                try:
                    # Verificar edad del archivo
                    file_age = datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if file_age < cutoff_time:
                        cache_file.unlink()
                        deleted_count += 1
                        logger.debug(f"[CacheService] 🗑️ Cache antiguo eliminado: {cache_file.name}")
                except Exception as e:
                    logger.warning(f"[CacheService] ⚠️ Error procesando {cache_file.name}: {e}")
            
            logger.info(f"[CacheService] 🧹 Limpieza completada: {deleted_count} archivos eliminados")
            return deleted_count
            
        except Exception as e:
            logger.error(f"[CacheService] ❌ Error en limpieza de cache: {e}")
            return 0
