# app/services/user_service.py

import logging
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from typing import Optional, TYPE_CHECKING, Dict, Any

from app.models.user_model import User
from app.schemas.user_schema import UserCreate, UserUpdate, UserPreferencesUpdate, UserPreferences

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, factory: "ServiceFactory"):
        self.factory = factory
        self.db = factory.db

    def get_user_by_email(self, email: str) -> Optional[User]:
        logger.debug(f"🔎 Buscando usuario por email: {email}")
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        logger.debug(f"🔎 Buscando usuario por ID: {user_id}")
        return self.db.query(User).filter(User.id == user_id).first()

    def get_all_users(self) -> list[User]:
        logger.debug("📋 Obteniendo todos los usuarios")
        return self.db.query(User).all()

    def create_user(self, user_data: UserCreate) -> User:
        logger.info(f"👤 Intentando crear usuario con email: {user_data.email}")
        existing_user = self.get_user_by_email(user_data.email)
        if existing_user:
            logger.info(f"⚠️ Usuario ya existe con email: {user_data.email}")
            return existing_user

        # ✅ Crear solo con campos válidos del modelo SQLAlchemy
        user = User(
            email=user_data.email,
            name=user_data.name,
        )

        # ✅ Si hay contraseña, usar set_password
        if user_data.password:
            user.set_password(user_data.password)

        # 🎯 FASE 12: Aplicar preferencias si se proporcionan
        if user_data.preferences:
            user.update_preferences(**user_data.preferences.model_dump())

        try:
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"✅ Usuario creado exitosamente: {user.email}")
            return user
        except IntegrityError as e:
            self.db.rollback()
            logger.exception(f"❌ Error de integridad al crear usuario: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create user")

    def update_user(self, user_id: int, updates: UserUpdate) -> Optional[User]:
        logger.info(f"✏️ Solicitada actualización del usuario ID: {user_id}")
        user = self.get_user_by_id(user_id)
        if not user:
            logger.warning(f"❌ Usuario no encontrado para ID: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")

        for field, value in updates.model_dump(exclude_unset=True).items():
            if field == "password":
                user.set_password(value)
                logger.debug("🔒 Contraseña actualizada")
            elif field == "preferences" and value:
                # 🎯 FASE 12: Actualizar preferencias
                user.update_preferences(**value.model_dump())
                logger.debug("⚙️ Preferencias actualizadas")
            else:
                setattr(user, field, value)
                logger.debug(f"🔄 Campo actualizado: {field} = {value}")

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"✅ Usuario actualizado exitosamente: {user.email}")
        return user

    def get_or_create_user(self, user_data: UserCreate) -> User:
        logger.debug(f"📦 Ejecutando get_or_create_user para: {user_data.email}")
        user = self.get_user_by_email(user_data.email)
        if user:
            logger.debug(f"👤 Usuario existente reutilizado: {user.email}")
            return user
        return self.create_user(user_data)

    # 🎯 FASE 12: Métodos para manejo de preferencias
    def get_user_preferences(self, user_id: int) -> Optional[UserPreferences]:
        """Obtiene las preferencias del usuario."""
        user = self.get_user_by_id(user_id)
        if not user:
            return None
        
        return UserPreferences(**user.get_preferences())

    def update_user_preferences(
        self, 
        user_id: int, 
        preferences: UserPreferencesUpdate
    ) -> Optional[UserPreferences]:
        """Actualiza las preferencias del usuario."""
        user = self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Aplicar solo los campos que se proporcionan
        updates = preferences.model_dump(exclude_unset=True)
        if updates:
            user.update_preferences(**updates)
            self.db.commit()
            self.db.refresh(user)
            logger.info(f"✅ Preferencias actualizadas para usuario {user.email}")
        
        return UserPreferences(**user.get_preferences())

    def should_confirm_action(self, user_id: int, risk_level: str) -> bool:
        """Determina si se debe pedir confirmación basado en las preferencias del usuario."""
        user = self.get_user_by_id(user_id)
        if not user:
            return True  # Por defecto, pedir confirmación si no se encuentra el usuario
        
        return user.should_confirm_action(risk_level)

    def get_users_by_preference(
        self, 
        preference_field: str, 
        preference_value: Any
    ) -> list[User]:
        """Obtiene usuarios que tienen una preferencia específica."""
        if not hasattr(User, preference_field):
            raise ValueError(f"Campo de preferencia inválido: {preference_field}")
        
        return self.db.query(User).filter(
            getattr(User, preference_field) == preference_value
        ).all()

    def get_user_preferences_summary(self, user_id: int) -> Dict[str, Any]:
        """Obtiene un resumen de las preferencias del usuario."""
        user = self.get_user_by_id(user_id)
        if not user:
            return {}
        
        preferences = user.get_preferences()
        return {
            "user_id": user_id,
            "email": user.email,
            "preferences": preferences,
            "confirmation_required": user.confirmations,
            "risk_profile": {
                "tolerance": user.risk_tolerance,
                "requires_confirmation_for_medium": user.should_confirm_action("medium"),
                "requires_confirmation_for_high": user.should_confirm_action("high")
            }
        }
