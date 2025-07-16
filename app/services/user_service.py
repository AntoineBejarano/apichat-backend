import logging
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import Optional

from app.models.user_model import User
from app.models.session_model import Session as SessionModel
from app.schemas.user_schema import UserCreate, UserUpdate
from app.schemas.session_schema import SessionCreate
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory
    
logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.db = factory.db

    def get_user_by_email(self, email: str) -> Optional[User]:
        logger.debug(f"🔎 Buscando usuario por email: {email}")
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        logger.debug(f"🔎 Buscando usuario por ID: {user_id}")
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(self, user_data: UserCreate) -> User:
        logger.info(f"👤 Intentando crear usuario con email: {user_data.email}")
        existing_user = self.get_user_by_email(user_data.email)
        if existing_user:
            logger.info(f"⚠️ Usuario ya existe con email: {user_data.email}")
            return existing_user

        user = User(**user_data.model_dump())
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
            setattr(user, field, value)
            logger.debug(f"🔄 Campo actualizado: {field} = {value}")

        self.db.commit()
        self.db.refresh(user)
        logger.info(f"✅ Usuario actualizado exitosamente: {user.email}")
        return user

    def create_session(self, session_data: SessionCreate) -> SessionModel:
        logger.info(f"🆕 Creando sesión para user_id={session_data.user_id}")
        session = SessionModel(**session_data.model_dump())
        try:
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            logger.info(f"✅ Sesión creada con token: {session.session_token}")
            return session
        except Exception as e:
            self.db.rollback()
            logger.exception(f"❌ Error al crear sesión: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to create session")

    def get_or_create_user(self, user_data: UserCreate) -> User:
        logger.debug(f"📦 Ejecutando get_or_create_user para: {user_data.email}")
        user = self.get_user_by_email(user_data.email)
        if user:
            logger.debug(f"👤 Usuario existente reutilizado: {user.email}")
            return user
        return self.create_user(user_data)
