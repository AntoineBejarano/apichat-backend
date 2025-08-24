"""
🏭 Management Services Factory: Factory para servicios de gestión

Maneja servicios relacionados con:
- User Service
- Organization Service
- Agent Service
- Permission Service
"""

import logging
from typing import Optional

from .base_factory import BaseServiceFactory

logger = logging.getLogger(__name__)


class ManagementServicesFactory(BaseServiceFactory):
    """
    🏭 Factory para servicios de gestión
    
    Responsabilidades:
    - Gestión de usuarios
    - Gestión de organizaciones
    - Gestión de agentes
    - Gestión de permisos
    """
    
    def get_user_service(self):
        """Obtiene el servicio de gestión de usuarios"""
        try:
            from app.services.management.user_service import UserService
            return self._get_or_create_service(UserService, "user")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo UserService: {e}")
            return None
    
    def get_organization_service(self):
        """Obtiene el servicio de gestión de organizaciones"""
        try:
            from app.services.management.organization_service import OrganizationService
            return self._get_or_create_service(OrganizationService, "organization")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo OrganizationService: {e}")
            return None
    
    def get_agent_service(self):
        """Obtiene el servicio de gestión de agentes"""
        try:
            from app.services.management.agent_service import AgentService
            return self._get_or_create_service(AgentService, "agent")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo AgentService: {e}")
            return None
    
    def get_permission_service(self):
        """Obtiene el servicio de gestión de permisos"""
        try:
            from app.services.management.permission_service import PermissionService
            return self._get_or_create_service(PermissionService, "permission")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo PermissionService: {e}")
            return None
    
    def get_role_service(self):
        """Obtiene el servicio de gestión de roles"""
        try:
            from app.services.management.role_service import RoleService
            return self._get_or_create_service(RoleService, "role")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo RoleService: {e}")
            return None
    
    def get_audit_service(self):
        """Obtiene el servicio de auditoría"""
        try:
            from app.services.management.audit_service import AuditService
            return self._get_or_create_service(AuditService, "audit")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo AuditService: {e}")
            return None
    
    def get_schema_performance_service(self):
        """Obtiene el servicio de performance de schemas"""
        try:
            from app.services.monitoring.schema_performance_service import SchemaPerformanceService
            return self._get_or_create_service(SchemaPerformanceService, "schema_performance")
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo SchemaPerformanceService: {e}")
            return None
    
    def get_factory_info(self) -> dict:
        """Obtiene información de la factory de gestión"""
        try:
            return {
                "factory_type": "management_services",
                "available_services": [
                    "user_service",
                    "organization_service",
                    "agent_service",
                    "permission_service",
                    "role_service",
                    "audit_service",
                    "schema_performance_service"
                ],
                **self._get_service_info()
            }
        except Exception as e:
            logger.error(f"[ManagementServicesFactory] ❌ Error obteniendo info: {e}")
            return {"error": str(e)}
