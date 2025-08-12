"""
Context Loader
─────────────
Gestiona la carga paralela y optimizada de todo el contexto necesario
para procesar un mensaje del usuario.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.schemas.chat_schema import ChatMessage

logger = logging.getLogger(__name__)


class ContextLoader:
    """Carga y gestiona el contexto necesario para el orchestrator."""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        
        # 🔒 VALIDACIÓN: Asegurar que user_id no sea None
        if hasattr(factory, 'user') and factory.user and hasattr(factory.user, 'id'):
            self.user_id = factory.user.id
            logger.info(f"[ContextLoader] Initialized for user_id={self.user_id}")
        else:
            # 🔒 FALLBACK: Crear un user_id por defecto para evitar errores
            from uuid import uuid4
            self.user_id = uuid4()
            logger.warning(f"[ContextLoader] ⚠️ No se pudo obtener user_id válido del factory, usando fallback: {self.user_id}")
        
        # Servicios necesarios
        self.history_service = factory.get_chat_history_service()
        self.detailed_schema_cache_service = factory.get_detailed_schema_cache_service()
        self.app_descriptor_cache_service = factory.get_app_descriptor_cache_service()
        self.vector_search_service = factory.get_vector_search_service()
        self.intent_classifier_service = factory.get_intent_classifier_service()
        self.schema_explorer_service = factory.get_schema_explorer_service()
        
        # 🔒 VALIDACIÓN: Verificar que los servicios críticos estén disponibles
        if not self.history_service:
            logger.error("[ContextLoader] ❌ ChatHistoryService no disponible")
        if not self.detailed_schema_cache_service:
            logger.error("[ContextLoader] ❌ DetailedSchemaCacheService no disponible")
        if not self.schema_explorer_service:
            logger.error("[ContextLoader] ❌ SchemaExplorerService no disponible")
    
    async def load_context_parallel(
        self, 
        chat_id: str, 
        message: ChatMessage, 
        db_ids: List[UUID], 
        app_ids: List[UUID], 
        explorer: bool = False
    ) -> Dict[str, Any]:
        """Carga todo el contexto en paralelo para optimizar rendimiento."""
        
        # 🔒 VALIDACIÓN: Verificar que chat_id sea válido
        if not chat_id:
            logger.error("[ContextLoader] ❌ chat_id no puede ser None o vacío")
            return {"error": "chat_id inválido"}
        
        # 🔒 VALIDACIÓN: Verificar que message sea válido
        if not message:
            logger.error("[ContextLoader] ❌ message no puede ser None")
            return {"error": "message inválido"}
        
        # Crear tareas para ejecutar en paralelo
        tasks = {
            "store_task": self._store_user_message_async(chat_id, message),
            "usage_task": self._check_usage_limit_async(),
            "chat_history": self._load_history_async(chat_id),
        }
        
        # Agregar tareas condicionales
        if db_ids:
            tasks["database_schemas"] = self._load_database_schemas_async(db_ids)
            tasks["compact_schemas"] = self._load_compact_schemas_async(db_ids)
        
        if app_ids:
            tasks["app_descriptors"] = self._load_apps_async(app_ids)
        
        if explorer:
            tasks["functions"] = self._load_functions_async()
            tasks["mcp_tools"] = self._load_mcp_tools_async()
        
        # Ejecutar todas las tareas en paralelo
        logger.info(f"[ContextLoader] Executing {len(tasks)} tasks in parallel")
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        
        # Procesar resultados y manejar excepciones
        context = {}
        for i, (key, result) in enumerate(zip(tasks.keys(), results)):
            if isinstance(result, Exception):
                logger.error(f"[ContextLoader] Error in {key}: {result}")
                context[key] = None
            else:
                context[key] = result
        
        logger.info(f"[ContextLoader] Context loaded successfully with keys: {list(context.keys())}")
        return context
    
    async def _store_user_message_async(self, chat_id: UUID, message: ChatMessage):
        """Almacena el mensaje del usuario de forma asíncrona."""
        try:
            # 🔒 VALIDACIÓN: Verificar que el servicio esté disponible
            if not self.history_service:
                logger.error("[ContextLoader] ❌ ChatHistoryService no disponible para almacenar mensaje")
                return False
            
            # 🔒 VALIDACIÓN: Verificar que el método exista
            if not hasattr(self.history_service, 'store_user_message'):
                logger.error("[ContextLoader] ❌ Método store_user_message no disponible en ChatHistoryService")
                return False
            
            # 🔒 COMPATIBILIDAD: store_user_message es síncrono, no usar await
            result = self.history_service.store_user_message(chat_id, message)
            logger.debug(f"[ContextLoader] User message stored for chat {chat_id}")
            return result
        except Exception as e:
            logger.error(f"[ContextLoader] Error storing user message: {e}")
            return False
    
    async def _check_usage_limit_async(self):
        """Verifica el límite de uso de forma asíncrona."""
        try:
            # 🔒 VALIDACIÓN: Verificar que user_id esté disponible
            if not self.user_id:
                logger.warning("[ContextLoader] ⚠️ user_id no disponible para verificar límite de uso")
                return True  # Permitir continuar si no se puede verificar
            
            # Aquí iría la lógica de verificación de uso
            return True
        except Exception as e:
            logger.error(f"[ContextLoader] Error checking usage limit: {e}")
            return False
    
    async def _load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Carga el historial de chat de forma asíncrona."""
        try:
            # 🔒 VALIDACIÓN: Verificar que el servicio esté disponible
            if not self.history_service:
                logger.error("[ContextLoader] ❌ ChatHistoryService no disponible para cargar historial")
                return []
            
            # 🔒 VALIDACIÓN: Verificar que el método exista
            if not hasattr(self.history_service, 'get_chat_history'):
                logger.error("[ContextLoader] ❌ Método get_chat_history no disponible en ChatHistoryService")
                return []
            
            history = self.history_service.get_chat_history(chat_id)
            logger.debug(f"[ContextLoader] Loaded {len(history)} chat history items")
            return history
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading chat history: {e}")
            return []
    
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """Carga esquemas de base de datos de forma asíncrona."""
        try:
            # 🔒 VALIDACIÓN: Verificar que el servicio esté disponible
            if not self.detailed_schema_cache_service:
                logger.error("[ContextLoader] ❌ DetailedSchemaCacheService no disponible para cargar esquemas")
                return {}
            
            # 🔒 VALIDACIÓN: Verificar que el método exista
            if not hasattr(self.detailed_schema_cache_service, 'get_schema'):
                logger.error("[ContextLoader] ❌ Método get_schema no disponible en DetailedSchemaCacheService")
                return {}
            
            # 🔒 VALIDACIÓN: Verificar que user_id esté disponible
            if not self.user_id:
                logger.warning("[ContextLoader] ⚠️ user_id no disponible para cargar esquemas de DB")
                return {}
            
            schemas = {}
            for db_id in db_ids:
                # 🔒 COMPATIBILIDAD: get_schema es síncrono, no usar await
                schema = self.detailed_schema_cache_service.get_schema(db_id)
                if schema:
                    schemas[db_id] = schema
                    logger.debug(f"[ContextLoader] Loaded schema for DB {db_id}")
                else:
                    logger.warning(f"[ContextLoader] No schema found for DB {db_id}")
            
            return schemas
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading database schemas: {e}")
            return {}
    
    async def _load_compact_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """Carga esquemas compactos para optimización de tokens."""
        try:
            # 🔒 VALIDACIÓN: Verificar que el servicio esté disponible
            if not self.schema_explorer_service:
                logger.error("[ContextLoader] ❌ SchemaExplorerService no disponible para cargar esquemas compactos")
                return {}
            
            # 🔒 VALIDACIÓN: Verificar que el método exista
            if not hasattr(self.schema_explorer_service, 'get_compact_schema'):
                logger.error("[ContextLoader] ❌ Método get_compact_schema no disponible en SchemaExplorerService")
                return {}
            
            compact_schemas = {}
            for db_id in db_ids:
                # 🔒 COMPATIBILIDAD: get_compact_schema es síncrono, no usar await
                schema = self.schema_explorer_service.get_compact_schema(db_id)
                if schema:
                    compact_schemas[db_id] = schema
                    logger.debug(f"[ContextLoader] Loaded compact schema for DB {db_id}")
            
            return compact_schemas
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading compact schemas: {e}")
            return {}
    
    async def _load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Carga descriptores de aplicaciones de forma asíncrona."""
        try:
            # 🔒 VALIDACIÓN: Verificar que el servicio esté disponible
            if not self.app_descriptor_cache_service:
                logger.error("[ContextLoader] ❌ AppDescriptorCacheService no disponible para cargar apps")
                return []
            
            # 🔒 VALIDACIÓN: Verificar que el método exista
            if not hasattr(self.app_descriptor_cache_service, 'get_app_descriptor'):
                logger.error("[ContextLoader] ❌ Método get_app_descriptor no disponible en AppDescriptorCacheService")
                return []
            
            apps = []
            for app_id in app_ids:
                # 🔒 COMPATIBILIDAD: get_app_descriptor es síncrono, no usar await
                app_descriptor = self.app_descriptor_cache_service.get_app_descriptor(app_id)
                if app_descriptor:
                    apps.append(app_descriptor)
                    logger.debug(f"[ContextLoader] Loaded app descriptor for {app_id}")
            
            return apps
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading app descriptors: {e}")
            return []
    
    async def _load_functions_async(self) -> List[Dict[str, Any]]:
        """Carga funciones disponibles de forma asíncrona."""
        try:
            # Aquí iría la lógica para cargar funciones
            # Por ahora retornamos una lista vacía
            logger.debug("[ContextLoader] Functions loading not implemented yet")
            return []
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading functions: {e}")
            return []
    
    async def _load_mcp_tools_async(self) -> Dict[str, Any]:
        """Carga herramientas MCP de forma asíncrona."""
        try:
            # Aquí iría la lógica para cargar herramientas MCP
            # Por ahora retornamos un dict vacío
            logger.debug("[ContextLoader] MCP tools loading not implemented yet")
            return {}
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading MCP tools: {e}")
            return {}
    
    def validate_compact_schemas(self, compact_schemas: Dict, db_ids: List) -> bool:
        """Valida que los esquemas compactos sean válidos."""
        if not compact_schemas:
            return False
        
        for db_id in db_ids:
            if db_id not in compact_schemas or not compact_schemas[db_id]:
                logger.warning(f"[ContextLoader] Missing or invalid compact schema for DB {db_id}")
                return False
        
        logger.debug(f"[ContextLoader] All {len(db_ids)} compact schemas are valid")
        return True
