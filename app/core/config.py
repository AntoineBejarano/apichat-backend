# app/core/config.py

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "APIchat"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    API_V1_STR: str = "/api/v1"

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

    # Base de datos (Neon)
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]  # Ajusta en producción

    # Google OAuth2
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI")
    GOOGLE_METADATA_URL: str = os.getenv("GOOGLE_METADATA_URL")
    GOOGLE_SCOPE: str = os.getenv("GOOGLE_SCOPE", "openid email profile")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL")

    # Seguridad sesión
    SESSION_COOKIE_NAME: str = os.getenv("SESSION_COOKIE_NAME", "session_token")
    SESSION_COOKIE_SECURE: bool = os.getenv("SESSION_COOKIE_SECURE", "True") == "True"
    SESSION_COOKIE_SAMESITE: str = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_MAX_AGE: int = int(os.getenv("SESSION_COOKIE_MAX_AGE", 60 * 60 * 24 * 30))  # 30 días

    # JWT (opcional si usas)
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    DEFAULT_API_KEY: str = os.getenv("DEFAULT_API_KEY")

    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4-1106-preview"
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"  # o el endpoint de Azure si aplica
    OPENAI_API_TYPE: str = "openai"  # o "azure"
    OPENAI_API_VERSION: str = "2023-07-01-preview"  # si aplica para Azure
    OPENAI_TEMPERATURE=0.0
    LANGCHAIN_VERBOSE: bool = False



    class Config:
        case_sensitive = True


settings = Settings()
