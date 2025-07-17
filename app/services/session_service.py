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
        now = datetime.now(timezone.utc)
        logger.info(f"🆕 Creando sesión para user_id={user_id}")

        session = SessionModel(
            user_id=user_id,
            session_token=token,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent"),
            created_at=now,
            expires_at=now + timedelta(days=30),
            last_used_at=now
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

        # ✅ Actualizar last_used_at
        session.last_used_at = datetime.now(timezone.utc)
        self.db.commit()

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

    def get_user_sessions(self, user_id: int) -> list[SessionModel]:
        logger.info(f"📄 Obteniendo sesiones activas para user_id={user_id}")
        return self.db.query(SessionModel).filter(SessionModel.user_id == user_id).all()

    def revoke_all_except(self, user_id: int, current_token: str) -> int:
        logger.info(f"🧹 Revocando todas las sesiones de user_id={user_id} excepto la actual")
        sessions = self.db.query(SessionModel).filter(SessionModel.user_id == user_id).all()
        revoked_count = 0

        for session in sessions:
            if session.session_token != current_token:
                self.db.delete(session)
                revoked_count += 1

        self.db.commit()
        logger.info(f"✅ {revoked_count} sesiones revocadas")
        return revoked_count

    def validate_session(self, token: str) -> SessionModel:
        logger.info(f"🔍 Validando sesión con token={token}")
        session = self.db.query(SessionModel).filter(SessionModel.session_token == token).first()

        if not session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token")

        if session.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

        # Opcional: actualizar `last_used_at` si se desea al validar sin autenticar
        return session

    def revoke_session_by_token(self, token: str, user_id: int) -> bool:
        logger.info(f"🗑️ Revocando sesión específica token={token} para user_id={user_id}")
        session = self.db.query(SessionModel).filter(SessionModel.session_token == token).first()

        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this session")

        self.db.delete(session)
        self.db.commit()
        logger.info("✅ Sesión específica revocada")
        return True
