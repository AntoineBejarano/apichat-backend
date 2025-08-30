import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.api_triggering_config_model import APITriggeringConfig
from app.schemas.api_triggering_config_schema import (
    APITriggeringConfigCreate, 
    APITriggeringConfigUpdate,
    APITriggeringConfigOut
)
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class APITriggeringConfigService(BaseService):
    """Servicio para gestionar configuración de triggering por usuario"""
    
    def __init__(self, factory: "ServiceFactory"):
        super().__init__(factory)
        self.logger = logging.getLogger(__name__)
    
    def create_config(self, config_data: APITriggeringConfigCreate) -> APITriggeringConfigOut:
        """Crear configuración de triggering para un usuario y app"""
        try:
            # Verificar que no existe ya
            existing = self.get_config_by_user_and_app(self.user.id, config_data.app_id)
            if existing:
                raise ValueError(f"Ya existe configuración para este usuario y app")
            
            # Crear nueva configuración
            config = APITriggeringConfig(
                user_id=self.user.id,
                app_id=config_data.app_id,
                enabled=config_data.enabled,
                confidence_threshold=config_data.confidence_threshold,
                max_auto_executions=config_data.max_auto_executions,
                timeout_seconds=config_data.timeout_seconds,
                allowed_endpoints=config_data.allowed_endpoints or [],
                blocked_endpoints=config_data.blocked_endpoints or [],
                auto_confirm=config_data.auto_confirm,
                require_explicit_consent=config_data.require_explicit_consent
            )
            
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
            
            self.logger.info(f"[APITriggeringConfigService] ✅ Configuración creada para user_id={self.user.id}, app_id={config_data.app_id}")
            return APITriggeringConfigOut.model_validate(config)
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"[APITriggeringConfigService] ❌ Error creando configuración: {e}")
            raise
    
    def get_config_by_user_and_app(self, user_id: UUID, app_id: UUID) -> Optional[APITriggeringConfigOut]:
        """Obtener configuración específica de un usuario y app"""
        try:
            config = (
                self.db.query(APITriggeringConfig)
                .filter(
                    APITriggeringConfig.user_id == user_id,
                    APITriggeringConfig.app_id == app_id
                )
                .first()
            )
            
            if config:
                return APITriggeringConfigOut.model_validate(config)
            return None
            
        except Exception as e:
            self.logger.error(f"[APITriggeringConfigService] ❌ Error obteniendo configuración: {e}")
            return None
    
    def get_user_configs(self, user_id: UUID) -> List[APITriggeringConfigOut]:
        """Obtener todas las configuraciones de un usuario"""
        try:
            configs = (
                self.db.query(APITriggeringConfig)
                .filter(APITriggeringConfig.user_id == user_id)
                .all()
            )
            
            return [APITriggeringConfigOut.model_validate(config) for config in configs]
            
        except Exception as e:
            self.logger.error(f"[APITriggeringConfigService] ❌ Error obteniendo configuraciones del usuario: {e}")
            return []
    
    def update_config(self, config_id: UUID, config_data: APITriggeringConfigUpdate) -> APITriggeringConfigOut:
        """Actualizar configuración existente"""
        try:
            config = (
                self.db.query(APITriggeringConfig)
                .filter(
                    APITriggeringConfig.id == config_id,
                    APITriggeringConfig.user_id == self.user.id  # Solo el propietario puede actualizar
                )
                .first()
            )
            
            if not config:
                raise ValueError("Configuración no encontrada o sin permisos")
            
            # Actualizar campos
            for field, value in config_data.model_dump(exclude_unset=True).items():
                setattr(config, field, value)
            
            self.db.commit()
            self.db.refresh(config)
            
            self.logger.info(f"[APITriggeringConfigService] ✅ Configuración actualizada: {config_id}")
            return APITriggeringConfigOut.model_validate(config)
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"[APITriggeringConfigService] ❌ Error actualizando configuración: {e}")
            raise
    
    def delete_config(self, config_id: UUID) -> bool:
        """Eliminar configuración"""
        try:
            config = (
                self.db.query(APITriggeringConfig)
                .filter(
                    APITriggeringConfig.id == config_id,
                    APITriggeringConfig.user_id == self.user.id  # Solo el propietario puede eliminar
                )
                .first()
            )
            
            if not config:
                raise ValueError("Configuración no encontrada o sin permisos")
            
            self.db.delete(config)
            self.db.commit()
            
            self.logger.info(f"[APITriggeringConfigService] ✅ Configuración eliminada: {config_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            self.logger.error(f"[APITriggeringConfigService] ❌ Error eliminando configuración: {e}")
            raise
    
    def get_default_config(self, app_id: UUID) -> APITriggeringConfigOut:
        """Obtener configuración por defecto si no existe"""
        from datetime import datetime
        import uuid
        
        return APITriggeringConfigOut(
            id=uuid.uuid4(),
            user_id=self.user.id,
            app_id=app_id,
            enabled=True,
            confidence_threshold=0.7,
            max_auto_executions=5,
            timeout_seconds=30,
            allowed_endpoints=[],
            blocked_endpoints=[],
            auto_confirm=False,
            require_explicit_consent=True,
            created_at=datetime.now(),
            updated_at=None
        )
