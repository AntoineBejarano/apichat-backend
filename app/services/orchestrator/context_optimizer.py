"""
Context Optimizer Module
────────────────────────
Maneja la optimización y gestión del contexto del orchestrator.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class ContextOptimizer:
    """
    Optimiza y gestiona el contexto del orchestrator para minimizar el uso de tokens.
    """
    
    def __init__(self):
        # Límites de caracteres para trimming inteligente
        self.MAX_HISTORY_CHARS = 5000
        self.MAX_APP_DESCRIPTOR_CHARS = 2000
        self.MAX_FUNCTION_DESCRIPTION_CHARS = 100
        self.MAX_SCHEMA_CHARS = 3000
    
    def apply_intelligent_context_trimming(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica trimming inteligente al contexto para optimizar el uso de tokens.
        
        Args:
            context: Contexto a optimizar
            
        Returns:
            Contexto optimizado
        """
        logger.info("[ContextOptimizer] 🔧 Aplicando trimming inteligente al contexto")
        
        optimized_context = context.copy()
        
        # Optimizar historial de chat
        if "chat_history" in optimized_context:
            optimized_context["chat_history"] = self._trim_chat_history(
                optimized_context["chat_history"]
            )
        
        # Optimizar descriptores de aplicaciones
        if "apps" in optimized_context:
            optimized_context["apps"] = self._trim_app_descriptors(
                optimized_context["apps"]
            )
        
        # Optimizar descripciones de funciones
        if "functions" in optimized_context:
            optimized_context["functions"] = self._trim_function_descriptions(
                optimized_context["functions"]
            )
        
        # Optimizar esquemas de base de datos
        if "database_schemas" in optimized_context:
            optimized_context["database_schemas"] = self._trim_database_schemas(
                optimized_context["database_schemas"]
            )
        
        logger.info("[ContextOptimizer] ✅ Contexto optimizado")
        return optimized_context
    
    def _trim_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Recorta el historial de chat para mantener solo los mensajes más relevantes.
        
        Args:
            history: Historial de chat
            
        Returns:
            Historial optimizado
        """
        if not history:
            return history
        
        # Mantener solo los últimos mensajes más relevantes
        trimmed_history = []
        total_chars = 0
        
        for message in reversed(history):
            message_content = str(message.get("content", ""))
            message_chars = len(message_content)
            
            if total_chars + message_chars <= self.MAX_HISTORY_CHARS:
                trimmed_history.insert(0, message)
                total_chars += message_chars
            else:
                break
        
        logger.info(f"[ContextOptimizer] 📝 Historial recortado: {len(trimmed_history)}/{len(history)} mensajes")
        return trimmed_history
    
    def _trim_app_descriptors(self, apps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Recorta los descriptores de aplicaciones.
        
        Args:
            apps: Lista de aplicaciones
            
        Returns:
            Aplicaciones con descriptores optimizados
        """
        if not apps:
            return apps
        
        optimized_apps = []
        for app in apps:
            optimized_app = app.copy()
            
            # Recortar descripción si es muy larga
            if "description" in optimized_app and optimized_app["description"]:
                description = optimized_app["description"]
                if len(description) > self.MAX_APP_DESCRIPTOR_CHARS:
                    optimized_app["description"] = description[:self.MAX_APP_DESCRIPTOR_CHARS] + "..."
            
            optimized_apps.append(optimized_app)
        
        logger.info(f"[ContextOptimizer] 📱 Descriptores de apps optimizados: {len(optimized_apps)} apps")
        return optimized_apps
    
    def _trim_function_descriptions(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Recorta las descripciones de funciones.
        
        Args:
            functions: Lista de funciones
            
        Returns:
            Funciones con descripciones optimizadas
        """
        if not functions:
            return functions
        
        optimized_functions = []
        for function in functions:
            optimized_function = function.copy()
            
            # Recortar descripción si es muy larga
            if "description" in optimized_function and optimized_function["description"]:
                description = optimized_function["description"]
                if len(description) > self.MAX_FUNCTION_DESCRIPTION_CHARS:
                    optimized_function["description"] = description[:self.MAX_FUNCTION_DESCRIPTION_CHARS] + "..."
            
            optimized_functions.append(optimized_function)
        
        logger.info(f"[ContextOptimizer] ⚙️ Descripciones de funciones optimizadas: {len(optimized_functions)} functions")
        return optimized_functions
    
    def _trim_database_schemas(self, schemas: Dict[UUID, List[Dict[str, Any]]]) -> Dict[UUID, List[Dict[str, Any]]]:
        """
        Recorta los esquemas de base de datos.
        
        Args:
            schemas: Esquemas de base de datos
            
        Returns:
            Esquemas optimizados
        """
        if not schemas:
            return schemas
        
        optimized_schemas = {}
        for db_id, tables in schemas.items():
            optimized_tables = []
            total_chars = 0
            
            for table in tables:
                table_str = str(table)
                table_chars = len(table_str)
                
                if total_chars + table_chars <= self.MAX_SCHEMA_CHARS:
                    optimized_tables.append(table)
                    total_chars += table_chars
                else:
                    break
            
            optimized_schemas[db_id] = optimized_tables
        
        logger.info(f"[ContextOptimizer] 🗄️ Esquemas de DB optimizados: {len(optimized_schemas)} DBs")
        return optimized_schemas
    
    def should_use_lite_payload(self, estimated_tokens: int) -> bool:
        """
        Determina si se debe usar un payload lite basado en la estimación de tokens.
        
        Args:
            estimated_tokens: Tokens estimados
            
        Returns:
            True si se debe usar payload lite
        """
        # Usar payload lite si se estiman más de 6000 tokens
        return estimated_tokens > 6000
    
    async def build_lite_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye un payload lite con solo la información esencial.
        
        Args:
            context: Contexto completo
            
        Returns:
            Payload lite optimizado
        """
        logger.info("[ContextOptimizer] 🚀 Construyendo payload lite")
        
        lite_payload = {
            "message": context.get("message", ""),
            "chat_history": self._get_lite_chat_history(context.get("chat_history", [])),
            "database_schemas": self._get_lite_database_schemas(context.get("database_schemas", {})),
            "apps": self._get_lite_apps(context.get("apps", [])),
            "functions": self._get_lite_functions(context.get("functions", [])),
            "mcp_tools": self._get_lite_mcp_tools(context.get("mcp_tools", {}))
        }
        
        logger.info("[ContextOptimizer] ✅ Payload lite construido")
        return lite_payload
    
    def _get_lite_chat_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Obtiene historial de chat lite (solo últimos 2 mensajes)."""
        if not history:
            return []
        return history[-2:] if len(history) > 2 else history
    
    def _get_lite_database_schemas(self, schemas: Dict[UUID, List[Dict[str, Any]]]) -> Dict[UUID, List[Dict[str, Any]]]:
        """Obtiene esquemas de DB lite (solo primeras 3 tablas por DB)."""
        if not schemas:
            return {}
        
        lite_schemas = {}
        for db_id, tables in schemas.items():
            lite_schemas[db_id] = tables[:3] if len(tables) > 3 else tables
        
        return lite_schemas
    
    def _get_lite_apps(self, apps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Obtiene apps lite (solo nombre y descripción corta)."""
        if not apps:
            return []
        
        lite_apps = []
        for app in apps[:2]:  # Solo primeras 2 apps
            lite_app = {
                "id": app.get("id"),
                "name": app.get("name"),
                "description": app.get("description", "")[:100] + "..." if len(app.get("description", "")) > 100 else app.get("description", "")
            }
            lite_apps.append(lite_app)
        
        return lite_apps
    
    def _get_lite_functions(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Obtiene funciones lite (solo nombre y descripción corta)."""
        if not functions:
            return []
        
        lite_functions = []
        for function in functions[:3]:  # Solo primeras 3 funciones
            lite_function = {
                "id": function.get("id"),
                "name": function.get("name"),
                "description": function.get("description", "")[:50] + "..." if len(function.get("description", "")) > 50 else function.get("description", "")
            }
            lite_functions.append(lite_function)
        
        return lite_functions
    
    def _get_lite_mcp_tools(self, tools: Dict[str, Any]) -> Dict[str, Any]:
        """Obtiene herramientas MCP lite (solo nombres)."""
        if not tools:
            return {}
        
        lite_tools = {}
        for tool_name, tool_info in list(tools.items())[:2]:  # Solo primeras 2 herramientas
            lite_tools[tool_name] = {"name": tool_name}
        
        return lite_tools
