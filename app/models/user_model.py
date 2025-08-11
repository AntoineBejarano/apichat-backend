from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from app.models.base_model import Base
from app.models.role_model import user_roles
from passlib.context import CryptContext
import uuid

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)

    # 🎯 FASE 12: Preferencias de usuario (persistentes)
    response_format = Column(String(50), default="detailed", nullable=False)  # detailed, concise, minimal
    detail_level = Column(String(50), default="medium", nullable=False)      # low, medium, high
    risk_tolerance = Column(String(50), default="medium", nullable=False)    # low, medium, high
    confirmations = Column(Boolean, default=True, nullable=False)           # Si requiere confirmaciones
    language = Column(String(10), default="es", nullable=False)             # es, en, fr, de
    timezone = Column(String(50), default="UTC", nullable=False)            # Zona horaria

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relación con Plan (opcional)
    plan_id = Column(ForeignKey("plans.id"), nullable=True)
    plan = relationship("Plan")

    # Relaciones 1:N
    agents = relationship("Agent", back_populates="user", cascade="all, delete-orphan")
    apps = relationship("App", back_populates="user", cascade="all, delete-orphan")
    databases = relationship("DatabaseConnection", back_populates="user", cascade="all, delete-orphan")
    strategies = relationship("Strategy", back_populates="user", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="user", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="user", cascade="all, delete-orphan")
    token_usages = relationship("TokenUsage", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("Chat", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    openapi_integrations = relationship("OpenAPIIntegration", back_populates="user", cascade="all, delete-orphan")
    proxies = relationship("Proxy", back_populates="user", cascade="all, delete-orphan")

    # Relaciones N:M
    roles = relationship("Role", secondary=user_roles, back_populates="users")

    def __init__(self, **kwargs):
        """Constructor personalizado para inicializar preferencias por defecto."""
        super().__init__(**kwargs)
        
        # 🎯 FASE 12: Inicializar preferencias por defecto si no se proporcionan
        if not hasattr(self, 'response_format') or self.response_format is None:
            self.response_format = "detailed"
        if not hasattr(self, 'detail_level') or self.detail_level is None:
            self.detail_level = "medium"
        if not hasattr(self, 'risk_tolerance') or self.risk_tolerance is None:
            self.risk_tolerance = "medium"
        if not hasattr(self, 'confirmations') or self.confirmations is None:
            self.confirmations = True
        if not hasattr(self, 'language') or self.language is None:
            self.language = "es"
        if not hasattr(self, 'timezone') or self.timezone is None:
            self.timezone = "UTC"

    # Métodos para gestionar contraseñas
    def set_password(self, password: str):
        self.hashed_password = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        if not self.hashed_password:
            return False
        return pwd_context.verify(password, self.hashed_password)

    # 🎯 FASE 12: Métodos para gestionar preferencias
    def update_preferences(self, **preferences):
        """Actualiza las preferencias del usuario."""
        valid_fields = {
            'response_format', 'detail_level', 'risk_tolerance', 
            'confirmations', 'language', 'timezone'
        }
        
        for field, value in preferences.items():
            if field in valid_fields:
                setattr(self, field, value)
        
        self.updated_at = func.now()
    
    def get_preferences(self) -> dict:
        """Retorna las preferencias actuales del usuario."""
        return {
            'response_format': self.response_format,
            'detail_level': self.detail_level,
            'risk_tolerance': self.risk_tolerance,
            'confirmations': self.confirmations,
            'language': self.language,
            'timezone': self.timezone
        }
    
    def should_confirm_action(self, risk_level: str) -> bool:
        """Determina si se debe pedir confirmación basado en preferencias."""
        if not self.confirmations:
            return False
        
        risk_mapping = {'low': 1, 'medium': 2, 'high': 3}
        user_risk = risk_mapping.get(self.risk_tolerance, 2)
        action_risk = risk_mapping.get(risk_level, 2)
        
        # Lógica: se requiere confirmación si la acción es igual o más riesgosa
        # que la tolerancia del usuario
        return action_risk >= user_risk
