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
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.history_service = factory.get_chat_history_service()
        self.detailed_schema_cache_service = factory.get_detailed_schema_cache_service()
        self.app_descriptor_cache_service = factory.get_app_descriptor_cache_service()
        self.vector_search_service = factory.get_vector_search_service()
        self.intent_classifier_service = factory.get_intent_classifier_service()
        self.schema_explorer_service = factory.get_schema_explorer_service()
        
        logger.info(f"[ContextLoader] Initialized for user_id={self.user_id}")
    
    async def load_context_parallel(
        self, 
        chat_id: str, 
        message: ChatMessage, 
        db_ids: List[UUID], 
        app_ids: List[UUID], 
        explorer: bool = False
    ) -> Dict[str, Any]:
        """Carga todo el contexto en paralelo para optimizar rendimiento."""
        
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
            await self.history_service.store_user_message(chat_id, message)
            logger.debug(f"[ContextLoader] User message stored for chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"[ContextLoader] Error storing user message: {e}")
            return False
    
    async def _check_usage_limit_async(self):
        """Verifica el límite de uso de forma asíncrona."""
        try:
            # Aquí iría la lógica de verificación de uso
            return True
        except Exception as e:
            logger.error(f"[ContextLoader] Error checking usage limit: {e}")
            return False
    
    async def _load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Carga el historial de chat de forma asíncrona."""
        try:
            history = await self.history_service.get_chat_history(chat_id)
            logger.debug(f"[ContextLoader] Loaded {len(history)} chat history items")
            return history
        except Exception as e:
            logger.error(f"[ContextLoader] Error loading chat history: {e}")
            return []
    
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """Carga esquemas de base de datos de forma asíncrona."""
        try:
            schemas = {}
            for db_id in db_ids:
                schema = await self.detailed_schema_cache_service.get_schema(db_id)
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
            compact_schemas = {}
            for db_id in db_ids:
                # Usar el servicio de esquemas para obtener versión compacta
                schema = await self.schema_explorer_service.get_compact_schema(db_id)
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
            apps = []
            for app_id in app_ids:
                app_descriptor = await self.app_descriptor_cache_service.get_app_descriptor(app_id)
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
