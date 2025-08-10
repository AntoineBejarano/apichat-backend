"""
AppFunctionManager - Manejo de Aplicaciones y Funciones
───────────────────────────────────────────────────────
Módulo especializado para:
- Carga de aplicaciones
- Carga de funciones
- Carga de herramientas MCP
- Optimización de payloads
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context

logger = logging.getLogger(__name__)


class AppFunctionManager:
    """Maneja todas las operaciones relacionadas con aplicaciones y funciones"""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        
        # Servicios necesarios
        self.app_service = factory.get_app_service()
        self.function_service = factory.get_function_service()
        self.mcp_integration_service = factory.get_mcp_integration_service()
    
    @monitor_performance("load_apps")
    @profile_function("load_apps")
    async def load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Carga aplicaciones de forma asíncrona"""
        try:
            with performance_context("app_loading"):
                if not app_ids:
                    return []
                
                # 🔒 CONTROL DE TOKENS - Aplicar límites
                limited_app_ids = self._apply_token_budget_to_app_ids(app_ids)
                
                apps = []
                for app_id in limited_app_ids:
                    try:
                        app = await self._load_single_app(app_id)
                        if app:
                            # 🔒 CONTROL DE TOKENS - Optimizar descriptor
                            optimized_app = self._optimize_app_descriptor(app)
                            apps.append(optimized_app)
                    except Exception as e:
                        logger.error(f"Error cargando app {app_id}: {e}")
                
                logger.info(f"Aplicaciones cargadas: {len(apps)} de {len(app_ids)} solicitadas")
                return apps
                
        except Exception as e:
            logger.error(f"Error en load_apps_async: {e}")
            return []
    
    async def _load_single_app(self, app_id: UUID) -> Optional[Dict[str, Any]]:
        """Carga una aplicación individual"""
        try:
            app = await self.app_service.get_app(app_id)
            if not app:
                return None
            
            # Convertir a formato compatible
            app_dict = self._convert_app_to_dict(app)
            return app_dict
            
        except Exception as e:
            logger.error(f"Error cargando app {app_id}: {e}")
            return None
    
    def _convert_app_to_dict(self, app: Any) -> Dict[str, Any]:
        """Convierte objeto de aplicación a diccionario"""
        try:
            if hasattr(app, 'to_dict'):
                return app.to_dict()
            elif hasattr(app, '__dict__'):
                return self._safe_sqlalchemy_to_dict(app)
            else:
                return dict(app) if app else {}
        except Exception as e:
            logger.error(f"Error convirtiendo app a dict: {e}")
            return {}
    
    def _safe_sqlalchemy_to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convierte objeto SQLAlchemy a dict de forma segura"""
        try:
            if hasattr(obj, '__dict__'):
                result = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_'):
                        if hasattr(value, 'isoformat'):  # Para fechas
                            result[key] = value.isoformat()
                        elif isinstance(value, UUID):
                            result[key] = str(value)
                        else:
                            result[key] = value
                return result
            else:
                return {}
        except Exception as e:
            logger.error(f"Error convirtiendo objeto a dict: {e}")
            return {}
    
    def _optimize_app_descriptor(self, app: Dict[str, Any]) -> Dict[str, Any]:
        """Optimiza el descriptor de la aplicación para reducir tokens"""
        try:
            if not app:
                return app
            
            optimized_app = app.copy()
            
            # 🔒 CONTROL DE TOKENS - Limitar descripción
            max_description_chars = 2000
            description = app.get('description', '')
            if len(description) > max_description_chars:
                optimized_app['description'] = description[:max_description_chars] + "..."
                optimized_app['description_truncated'] = True
            
            # 🔒 CONTROL DE TOKENS - Limitar metadatos innecesarios
            metadata_fields_to_keep = ['version', 'author', 'category']
            if 'metadata' in optimized_app:
                filtered_metadata = {}
                for field in metadata_fields_to_keep:
                    if field in optimized_app['metadata']:
                        filtered_metadata[field] = optimized_app['metadata'][field]
                optimized_app['metadata'] = filtered_metadata
            
            return optimized_app
            
        except Exception as e:
            logger.error(f"Error optimizando app descriptor: {e}")
            return app
    
    def _apply_token_budget_to_app_ids(self, app_ids: List[UUID]) -> List[UUID]:
        """Aplica presupuesto de tokens a IDs de aplicaciones"""
        try:
            if not app_ids:
                return []
            
            # 🔒 CONTROL DE TOKENS - Top-K aplicaciones
            top_k_apps = 2
            
            if len(app_ids) <= top_k_apps:
                return app_ids
            
            # Por ahora, tomar las primeras K aplicaciones
            # En el futuro, podrías implementar ranking de relevancia
            limited_app_ids = app_ids[:top_k_apps]
            
            logger.info(f"Aplicaciones limitadas por presupuesto: {len(app_ids)} -> {len(limited_app_ids)}")
            return limited_app_ids
            
        except Exception as e:
            logger.error(f"Error aplicando presupuesto de tokens a apps: {e}")
            return app_ids[:2] if app_ids else []
    
    @monitor_performance("load_functions")
    @profile_function("load_functions")
    async def load_functions_async(self) -> List[Dict[str, Any]]:
        """Carga funciones de forma asíncrona"""
        try:
            with performance_context("function_loading"):
                # Cargar funciones desde el servicio
                functions = await self.function_service.get_functions()
                
                if not functions:
                    return []
                
                # 🔒 CONTROL DE TOKENS - Optimizar funciones
                optimized_functions = []
                for func in functions:
                    try:
                        optimized_func = self._optimize_function_description(func)
                        if optimized_func:
                            optimized_functions.append(optimized_func)
                    except Exception as e:
                        logger.error(f"Error optimizando función: {e}")
                
                logger.info(f"Funciones cargadas: {len(optimized_functions)}")
                return optimized_functions
                
        except Exception as e:
            logger.error(f"Error en load_functions_async: {e}")
            return []
    
    def _optimize_function_description(self, func: Any) -> Optional[Dict[str, Any]]:
        """Optimiza la descripción de una función para reducir tokens"""
        try:
            if not func:
                return None
            
            # Convertir a dict si es necesario
            if hasattr(func, 'to_dict'):
                func_dict = func.to_dict()
            elif hasattr(func, '__dict__'):
                func_dict = self._safe_sqlalchemy_to_dict(func)
            else:
                func_dict = dict(func) if func else {}
            
            if not func_dict:
                return None
            
            # 🔒 CONTROL DE TOKENS - Limitar descripción
            max_description_chars = 100
            description = func_dict.get('description', '')
            if len(description) > max_description_chars:
                func_dict['description'] = description[:max_description_chars] + "..."
                func_dict['description_truncated'] = True
            
            # 🔒 CONTROL DE TOKENS - Limitar parámetros
            if 'parameters' in func_dict:
                params = func_dict['parameters']
                if isinstance(params, dict) and len(params) > 10:
                    # Mantener solo los primeros 10 parámetros
                    limited_params = dict(list(params.items())[:10])
                    func_dict['parameters'] = limited_params
                    func_dict['parameters_truncated'] = True
            
            return func_dict
            
        except Exception as e:
            logger.error(f"Error optimizando función: {e}")
            return None
    
    @monitor_performance("load_mcp_tools")
    @profile_function("load_mcp_tools")
    async def load_mcp_tools_async(self) -> Dict[str, Any]:
        """Carga herramientas MCP de forma asíncrona"""
        try:
            with performance_context("mcp_tools_loading"):
                # Cargar herramientas MCP desde el servicio
                mcp_tools = await self.mcp_integration_service.get_mcp_tools()
                
                if not mcp_tools:
                    return {}
                
                # 🔒 CONTROL DE TOKENS - Optimizar herramientas MCP
                optimized_tools = {}
                for tool_name, tool_info in mcp_tools.items():
                    try:
                        optimized_tool = self._optimize_mcp_tool(tool_info)
                        if optimized_tool:
                            optimized_tools[tool_name] = optimized_tool
                    except Exception as e:
                        logger.error(f"Error optimizando herramienta MCP {tool_name}: {e}")
                
                logger.info(f"Herramientas MCP cargadas: {len(optimized_tools)}")
                return optimized_tools
                
        except Exception as e:
            logger.error(f"Error en load_mcp_tools_async: {e}")
            return {}
    
    def _optimize_mcp_tool(self, tool_info: Any) -> Optional[Dict[str, Any]]:
        """Optimiza información de herramienta MCP"""
        try:
            if not tool_info:
                return None
            
            # Convertir a dict si es necesario
            if isinstance(tool_info, dict):
                tool_dict = tool_info
            elif hasattr(tool_info, 'to_dict'):
                tool_dict = tool_info.to_dict()
            elif hasattr(tool_info, '__dict__'):
                tool_dict = self._safe_sqlalchemy_to_dict(tool_info)
            else:
                tool_dict = {}
            
            if not tool_dict:
                return None
            
            # 🔒 CONTROL DE TOKENS - Limitar descripción
            max_description_chars = 150
            description = tool_dict.get('description', '')
            if len(description) > max_description_chars:
                tool_dict['description'] = description[:max_description_chars] + "..."
                tool_dict['description_truncated'] = True
            
            # 🔒 CONTROL DE TOKENS - Limitar esquema
            if 'schema' in tool_dict:
                schema = tool_dict['schema']
                if isinstance(schema, dict) and len(str(schema)) > 500:
                    # Simplificar esquema complejo
                    tool_dict['schema'] = {
                        'type': 'object',
                        'simplified': True,
                        'original_size': len(str(schema))
                    }
                    tool_dict['schema_truncated'] = True
            
            return tool_dict
            
        except Exception as e:
            logger.error(f"Error optimizando herramienta MCP: {e}")
            return None
    
    def estimate_app_function_tokens(self, apps: List[Dict[str, Any]], functions: List[Dict[str, Any]], mcp_tools: Dict[str, Any]) -> int:
        """Estima el número de tokens de apps, funciones y herramientas MCP"""
        try:
            total_tokens = 0
            
            # Estimar tokens de aplicaciones
            for app in apps:
                app_content = str(app.get('name', '')) + str(app.get('description', ''))
                total_tokens += len(app_content) // 4
            
            # Estimar tokens de funciones
            for func in functions:
                func_content = str(func.get('name', '')) + str(func.get('description', ''))
                total_tokens += len(func_content) // 4
            
            # Estimar tokens de herramientas MCP
            for tool_name, tool_info in mcp_tools.items():
                tool_content = str(tool_name) + str(tool_info.get('description', ''))
                total_tokens += len(tool_content) // 4
            
            return total_tokens
            
        except Exception as e:
            logger.error(f"Error estimando tokens de apps/funciones: {e}")
            return 0
    
    def create_lite_payload(self, apps: List[Dict[str, Any]], functions: List[Dict[str, Any]], mcp_tools: Dict[str, Any]) -> Dict[str, Any]:
        """Crea un payload lite para reducir tokens"""
        try:
            lite_payload = {
                "apps": [],
                "functions": [],
                "mcp_tools": {}
            }
            
            # 🔒 CONTROL DE TOKENS - Apps lite
            for app in apps[:2]:  # Solo primeras 2 apps
                lite_app = {
                    "id": app.get("id"),
                    "name": app.get("name"),
                    "description": app.get("description", "")[:100] + "..." if len(app.get("description", "")) > 100 else app.get("description", "")
                }
                lite_payload["apps"].append(lite_app)
            
            # 🔒 CONTROL DE TOKENS - Funciones lite
            for func in functions[:5]:  # Solo primeras 5 funciones
                lite_func = {
                    "id": func.get("id"),
                    "name": func.get("name"),
                    "description": func.get("description", "")[:50] + "..." if len(func.get("description", "")) > 50 else func.get("description", "")
                }
                lite_payload["functions"].append(lite_func)
            
            # 🔒 CONTROL DE TOKENS - MCP tools lite
            for tool_name, tool_info in list(mcp_tools.items())[:3]:  # Solo primeras 3 herramientas
                lite_tool = {
                    "description": tool_info.get("description", "")[:80] + "..." if len(tool_info.get("description", "")) > 80 else tool_info.get("description", "")
                }
                lite_payload["mcp_tools"][tool_name] = lite_tool
            
            lite_payload["payload_type"] = "lite"
            lite_payload["optimization_applied"] = True
            
            return lite_payload
            
        except Exception as e:
            logger.error(f"Error creando payload lite: {e}")
            return {"apps": [], "functions": [], "mcp_tools": {}, "error": str(e)}
