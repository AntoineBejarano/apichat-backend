from typing import Dict, Any, Optional, List
from uuid import UUID
import json
import hashlib
import logging
from datetime import datetime, timezone

from app.services.base_service import BaseService
from app.models.app_model import App
from app.models.function_model import Function

logger = logging.getLogger(__name__)


class AppDescriptorCacheService(BaseService):
    """
    Servicio para cachear y generar descriptores compactos de aplicaciones.
    Maneja el cache de información de Apps + Functions para uso en prompts del LLM.
    """
    
    def __init__(self, factory):
        super().__init__(factory)
        self._cache: Dict[str, Dict[str, Any]] = {}  # {app_id: cached_descriptor}
        self.max_descriptor_chars = 10000  # Límite por app descriptor
    
    def get_app_descriptors_compact(self, app_ids: List[UUID], max_total_chars: int = 40000) -> Dict[str, str]:
        """
        Obtiene descriptores compactos de múltiples apps para uso en prompts.
        
        Args:
            app_ids: Lista de IDs de aplicaciones
            max_total_chars: Límite total de caracteres para todos los descriptores
            
        Returns:
            Dict {app_id: descriptor_compact} para las apps válidas
        """
        if not app_ids:
            return {}
        
        descriptors = {}
        total_chars = 0
        
        for app_id in app_ids:
            try:
                app_id_str = str(app_id)
                descriptor = self._get_or_create_descriptor(app_id)
                
                if descriptor and descriptor.get("compact"):
                    compact_desc = descriptor["compact"]
                    
                    # Verificar límite total
                    if total_chars + len(compact_desc) > max_total_chars:
                        logger.warning(f"[AppDescriptorCache] ⚠️ Límite de chars alcanzado, truncando app {app_id_str}")
                        break
                    
                    descriptors[app_id_str] = compact_desc
                    total_chars += len(compact_desc)
                    logger.debug(f"[AppDescriptorCache] ✅ Descriptor app {app_id_str}: {len(compact_desc)} chars")
                else:
                    logger.warning(f"[AppDescriptorCache] ⚠️ No se pudo generar descriptor para app {app_id_str}")
                    
            except Exception as e:
                logger.exception(f"[AppDescriptorCache] ❌ Error procesando app {app_id}: {e}")
                continue
        
        logger.info(f"[AppDescriptorCache] 📱 Descriptores generados: {len(descriptors)} apps, {total_chars} chars total")
        return descriptors

    def get_app_descriptor(self, app_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el descriptor de una aplicación específica.
        Método para compatibilidad con ContextLoader.
        
        Args:
            app_id: ID de la aplicación
            
        Returns:
            Descriptor de la aplicación o None si no se puede obtener
        """
        try:
            descriptor = self._get_or_create_descriptor(app_id)
            if descriptor:
                return {
                    "app_id": str(app_id),
                    "descriptor": descriptor.get("compact", ""),
                    "fingerprint": descriptor.get("fingerprint", ""),
                    "generated_at": descriptor.get("generated_at")
                }
            return None
        except Exception as e:
            logger.error(f"[AppDescriptorCache] ❌ Error obteniendo descriptor para app {app_id}: {e}")
            return None
    
    def _get_or_create_descriptor(self, app_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene descriptor del cache o lo genera si no existe/está desactualizado"""
        app_id_str = str(app_id)
        
        # Verificar cache existente
        if app_id_str in self._cache:
            cached = self._cache[app_id_str]
            if self._is_cache_valid(cached, app_id):
                logger.debug(f"[AppDescriptorCache] 🎯 Cache hit para app {app_id_str}")
                return cached
        
        # Generar nuevo descriptor
        logger.debug(f"[AppDescriptorCache] 🔄 Generando descriptor para app {app_id_str}")
        descriptor = self._generate_descriptor(app_id)
        
        if descriptor:
            self._cache[app_id_str] = descriptor
        
        return descriptor
    
    def _is_cache_valid(self, cached_descriptor: Dict[str, Any], app_id: UUID) -> bool:
        """Verifica si el descriptor cacheado sigue siendo válido"""
        try:
            # Verificar que tenga los campos necesarios
            if not all(key in cached_descriptor for key in ["fingerprint", "compact", "generated_at"]):
                return False
            
            # Generar fingerprint actual y comparar
            current_fingerprint = self._generate_fingerprint(app_id)
            if not current_fingerprint:
                return False
            
            return cached_descriptor["fingerprint"] == current_fingerprint
            
        except Exception as e:
            logger.debug(f"[AppDescriptorCache] Error validando cache app {app_id}: {e}")
            return False
    
    def _generate_descriptor(self, app_id: UUID) -> Optional[Dict[str, Any]]:
        """Genera un descriptor completo para una aplicación"""
        try:
            app_service = self.factory.get_app_service()
            function_service = self.factory.get_function_service()
            
            # Obtener app
            app = app_service.get_by_id(app_id)
            if not app:
                logger.warning(f"[AppDescriptorCache] ⚠️ App {app_id} no encontrada")
                return None
            
            # Obtener funciones de la app
            functions = function_service.get_by_app(app_id)
            
            # Generar fingerprint
            fingerprint = self._generate_fingerprint(app_id)
            if not fingerprint:
                return None
            
            # Crear descriptor detallado
            detailed_descriptor = {
                "app_id": str(app_id),
                "name": app.name,
                "description": app.description or "",
                "functions": [],
                "total_functions": len(functions),
                "has_openapi": bool(app.openapi_json),
                "has_mcp": bool(app.mcp_integration_id),
                "has_proxy": bool(app.proxy_id)
            }
            
            # Procesar funciones
            for func in functions:
                if func.active and func.is_enabled:
                    func_desc = {
                        "name": func.name,
                        "description": func.description or "",
                        "method": func.method or "POST",
                        "url": func.url or "",
                        "parameters": func.parameters or {},
                        "execution_type": func.execution_type or "python"
                    }
                    detailed_descriptor["functions"].append(func_desc)
            
            # Generar versión compacta para prompts
            compact_descriptor = self._generate_compact_descriptor(detailed_descriptor)
            
            return {
                "fingerprint": fingerprint,
                "detailed": detailed_descriptor,
                "compact": compact_descriptor,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.exception(f"[AppDescriptorCache] ❌ Error generando descriptor app {app_id}: {e}")
            return None
    
    def _generate_compact_descriptor(self, detailed: Dict[str, Any]) -> str:
        """Genera versión compacta del descriptor para uso en prompts del LLM"""
        try:
            lines = []
            
            # Header de la app
            app_name = detailed["name"]
            app_desc = detailed["description"]
            total_funcs = detailed["total_functions"]
            
            lines.append(f"APP: {app_name}")
            if app_desc:
                lines.append(f"DESC: {app_desc[:200]}{'...' if len(app_desc) > 200 else ''}")
            
            # Información de integración
            integration_info = []
            if detailed["has_openapi"]:
                integration_info.append("OpenAPI")
            if detailed["has_mcp"]:
                integration_info.append("MCP")
            if detailed["has_proxy"]:
                integration_info.append("Proxy")
            
            if integration_info:
                lines.append(f"INTEGRATION: {', '.join(integration_info)}")
            
            lines.append(f"FUNCTIONS ({len(detailed['functions'])} active of {total_funcs} total):")
            
            # Listar funciones activas
            for func in detailed["functions"][:10]:  # Máximo 10 funciones para no saturar
                func_line = f"  - {func['name']}"
                if func["description"]:
                    func_line += f": {func['description'][:100]}{'...' if len(func['description']) > 100 else ''}"
                
                # Agregar método y URL si están disponibles
                if func["method"] and func["url"]:
                    func_line += f" [{func['method']} {func['url'][:50]}{'...' if len(func['url']) > 50 else ''}]"
                
                lines.append(func_line)
            
            # Indicar si hay más funciones
            if len(detailed["functions"]) > 10:
                lines.append(f"  ... and {len(detailed['functions']) - 10} more functions")
            
            compact = "\n".join(lines)
            
            # Aplicar límite de caracteres
            if len(compact) > self.max_descriptor_chars:
                compact = compact[:self.max_descriptor_chars - 50] + "\n... [TRUNCATED DUE TO SIZE]"
            
            return compact
            
        except Exception as e:
            logger.exception(f"[AppDescriptorCache] ❌ Error generando descriptor compacto: {e}")
            return f"APP: {detailed.get('name', 'Unknown')} (Error generating descriptor)"
    
    def _generate_fingerprint(self, app_id: UUID) -> Optional[str]:
        """Genera fingerprint para detectar cambios en la app"""
        try:
            app_service = self.factory.get_app_service()
            function_service = self.factory.get_function_service()
            
            app = app_service.get_by_id(app_id)
            if not app:
                return None
            
            functions = function_service.get_by_app(app_id)
            
            # Crear string para hash basado en campos relevantes
            fingerprint_data = {
                "app_name": app.name,
                "app_description": app.description or "",
                "app_updated_at": app.updated_at.isoformat() if app.updated_at else "",
                "has_openapi": bool(app.openapi_json),
                "has_mcp": bool(app.mcp_integration_id),
                "has_proxy": bool(app.proxy_id),
                "functions": []
            }
            
            # Incluir datos de funciones activas
            for func in functions:
                if func.active and func.is_enabled:
                    func_data = {
                        "name": func.name,
                        "description": func.description or "",
                        "method": func.method or "",
                        "url": func.url or "",
                        "updated_at": func.updated_at.isoformat() if func.updated_at else ""
                    }
                    fingerprint_data["functions"].append(func_data)
            
            # Generar hash MD5
            fingerprint_str = json.dumps(fingerprint_data, sort_keys=True, default=str)
            return hashlib.md5(fingerprint_str.encode()).hexdigest()
            
        except Exception as e:
            logger.exception(f"[AppDescriptorCache] ❌ Error generando fingerprint app {app_id}: {e}")
            return None
    
    def invalidate_cache(self, app_id: UUID):
        """Invalida el cache para una aplicación específica"""
        app_id_str = str(app_id)
        if app_id_str in self._cache:
            del self._cache[app_id_str]
            logger.info(f"[AppDescriptorCache] 🗑️ Cache invalidado para app {app_id_str}")
    
    def clear_cache(self):
        """Limpia todo el cache"""
        self._cache.clear()
        logger.info("[AppDescriptorCache] 🗑️ Cache completo limpiado")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        return {
            "cached_apps": len(self._cache),
            "total_memory_usage": sum(len(str(desc)) for desc in self._cache.values()),
            "cache_keys": list(self._cache.keys())
        }
