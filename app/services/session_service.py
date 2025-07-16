# app/services/session_service.py

import uuid
import logging
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from app.models.session_model import Session as SessionModel
from app.models.user_model import User

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, user_id: int, request: Request) -> SessionModel:
        token = str(uuid.uuid4())
        logger.info(f"🆕 Creando sesión para user_id={user_id}")

        session = SessionModel(
            user_id=user_id,
            session_token=token,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        logger.info(f"✅ Sesión creada: {session.session_token}")
        return session

    def get_current_user(self, request: Request) -> User:
        logger.debug("🔍 Obteniendo token de sesión desde headers o cookies...")
        token = request.cookies.get("session_token") or request.headers.get("Authorization")

        if not token:
            logger.warning("❌ Token de sesión no proporcionado")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session token provided")

        logger.debug(f"🔐 Buscando sesión con token={token}")
        session = self.db.query(SessionModel).filter(SessionModel.session_token == token).first()

        if not session:
            logger.warning("❌ Token inválido: sesión no encontrada")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

        if session.expires_at < datetime.now(timezone.utc):
            logger.warning("⚠️ Token expirado")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        user = self.db.query(User).filter(User.id == session.user_id).first()
        if not user:
            logger.error(f"❌ Usuario con ID {session.user_id} no encontrado")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        logger.info(f"✅ Usuario autenticado: {user.email}")
        return user

    def delete_session(self, token: str) -> bool:
        logger.info(f"🗑️ Eliminando sesión con token={token}")
        session = self.db.query(SessionModel).filter(SessionModel.session_token == token).first()

        if not session:
            logger.warning("❌ Sesión no encontrada para eliminación")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        self.db.delete(session)
        self.db.commit()
        logger.info("✅ Sesión eliminada correctamente")
        return True
