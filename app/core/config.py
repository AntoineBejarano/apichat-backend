# app/core/config.py

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import ConfigDict

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    APP_VERSION: str = os.getenv("APP_VERSION")

    # Base de datos (Neon o cualquier otra URL de SQLAlchemy)
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Seguridad de sesión
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "session_token")
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "True") == "True"
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_MAX_AGE: int = int(os.getenv("SESSION_COOKIE_MAX_AGE", 60 * 60 * 24 * 30))  # 30 días
    SESSION_SECRET_KEY: str = os.getenv("SESSION_SECRET_KEY")

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]  # Cambia esto en producción

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4-1106-preview")
    OPENAI_API_BASE: str = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
    OPENAI_API_TYPE: str = os.getenv("OPENAI_API_TYPE", "openai")  # o "azure"
    OPENAI_API_VERSION: str = os.getenv("OPENAI_API_VERSION", "2023-07-01-preview")
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", 0.7))
    LANGCHAIN_VERBOSE: bool = os.getenv("LANGCHAIN_VERBOSE", "False") == "True"

    # OAuth2 Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_METADATA_URL: str = os.getenv("GOOGLE_METADATA_URL", "https://accounts.google.com/.well-known/openid-configuration")
    GOOGLE_SCOPE: str = os.getenv("GOOGLE_SCOPE", "openid email profile")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL")

    # Seguridad extra (JWT o API key opcional)
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    DEFAULT_API_KEY: str = os.getenv("DEFAULT_API_KEY")

    # Stripe
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET")

    # Feature Flags para UX mejorada
    UX_FAST_PATH: bool = os.getenv("UX_FAST_PATH", "True") == "True"
    UX_DECISION_REQUEST: bool = os.getenv("UX_DECISION_REQUEST", "True") == "True"
    UX_PROGRESS_STREAMING: bool = os.getenv("UX_PROGRESS_STREAMING", "True") == "True"
    UX_CONFIRMATION_TIMEOUT: int = int(os.getenv("UX_CONFIRMATION_TIMEOUT", 30))  # segundos
    
    # 🔧 FASE 8: Fast Schema Path - Ajustar umbral temporalmente
    CONF_FAST: float = float(os.getenv("CONF_FAST", "0.6"))  # 🔧 FASE 8: Bajado de 0.7 a 0.6 temporalmente
    CONF_AMBIGUOUS: float = float(os.getenv("CONF_AMBIGUOUS", "0.4"))  # Umbral bajo para desambiguación
    FAST_PATH_RESPONSE_TIME_MS: int = int(os.getenv("FAST_PATH_RESPONSE_TIME_MS", "150"))  # Objetivo de respuesta
    
    # Fase 15 - Hardening: Timeouts y reintentos
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))  # Timeout para LLM
    DB_QUERY_TIMEOUT_SECONDS: int = int(os.getenv("DB_QUERY_TIMEOUT_SECONDS", "30"))  # Timeout para queries DB
    HTTP_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("HTTP_REQUEST_TIMEOUT_SECONDS", "30"))  # Timeout para HTTP
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))  # Máximo número de reintentos
    RETRY_BACKOFF_FACTOR: float = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))  # Factor de backoff exponencial
    RETRY_DELAY_SECONDS: float = float(os.getenv("RETRY_DELAY_SECONDS", "1.0"))  # Delay inicial entre reintentos

    model_config = ConfigDict(case_sensitive=True)


settings = Settings()
