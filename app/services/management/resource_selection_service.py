from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ResourceSelectionService:
    """Servicio para seleccionar recursos prioritarios del usuario"""
    
    def __init__(self, factory):
        self.factory = factory
        self.chat_service = None
        self.user_service = None
    
    def _get_chat_service(self):
        """Lazy loading del chat service"""
        if not self.chat_service:
            self.chat_service = self.factory.get_chat_service()
        return self.chat_service
    
    def _get_user_service(self):
        """Lazy loading del user service"""
        if not self.user_service:
            self.user_service = self.factory.get_user_service()
        return self.user_service
    
    async def get_priority_resources_from_headers(self, headers: Dict[str, str]) -> Dict[str, List[str]]:
        """Obtiene recursos prioritarios desde headers del WebSocket"""
        
        try:
            # 🔧 OPTIMIZADO: Solo extraer DBs y Apps (requieren preparación)
            priority_dbs = headers.get("X-User-Priority-DBs", "").split(",") if headers.get("X-User-Priority-DBs") else []
            priority_apps = headers.get("X-User-Priority-Apps", "").split(",") if headers.get("X-User-Priority-Apps") else []
            
            # 🔧 STRATEGIES: No van en headers (se activan cuando se necesitan)
            # 🔧 EXPLORER: No va en headers (cambio instantáneo)
            
            # Filtrar valores vacíos y limitar a máximo 2 de cada tipo
            priority_dbs = [db.strip() for db in priority_dbs if db.strip()][:2]
            priority_apps = [app.strip() for app in priority_apps if app.strip()][:2]
            
            resources = {
                "db_ids": priority_dbs,
                "app_ids": priority_apps
                # 🔧 STRATEGIES: Eliminados completamente (no se usan)
            }
            
            logger.info(f"Recursos prioritarios extraídos de headers: DBs={priority_dbs}, Apps={priority_apps}")
            return resources
            
        except Exception as e:
            logger.error(f"Error extrayendo recursos de headers: {e}")
            return {"db_ids": [], "app_ids": []}
    
    async def get_user_metadata_from_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Obtiene metadatos del usuario desde headers del WebSocket"""
        
        try:
            metadata = {
                "role": headers.get("X-User-Role", "user"),
                "name": headers.get("X-User-Name", "Usuario")
                # 🔧 EXPLORER: No va en headers (cambio instantáneo)
                # 🔧 STRATEGIES: No van en headers (se activan cuando se necesitan)
            }
            
            logger.info(f"Metadatos del usuario extraídos: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error extrayendo metadatos de headers: {e}")
            return {"role": "user", "name": "Usuario"}
    
    def has_resources_to_prepare(self, resources: Dict[str, List[str]]) -> bool:
        """Verifica si hay recursos para preparar"""
        # 🔧 OPTIMIZADO: Solo verificar DBs y Apps
        db_ids = resources.get("db_ids", [])
        app_ids = resources.get("app_ids", [])
        return len(db_ids) > 0 or len(app_ids) > 0
    
    def get_resources_summary(self, resources: Dict[str, List[str]]) -> str:
        """Obtiene un resumen legible de los recursos"""
        summary_parts = []
        
        if resources.get("db_ids"):
            summary_parts.append(f"{len(resources['db_ids'])} DB(s)")
        if resources.get("app_ids"):
            summary_parts.append(f"{len(resources['app_ids'])} App(s)")
        
        # 🔧 STRATEGIES: No se incluyen en el resumen (no se preparan proactivamente)
        
        if summary_parts:
            return ", ".join(summary_parts)
        else:
            return "sin recursos específicos"
