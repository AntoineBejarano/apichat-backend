# app/dependencies.py

from app.services.openai_service import OpenAIService
from app.services.langchain_service import LangchainService

openai_client = OpenAIService()
langchain_client = LangchainService()

def get_openai_client():
    return openai_client

def get_langchain_client():
    return langchain_client

def is_admin(self) -> bool:
    """Verifica si el usuario autenticado es administrador."""
    return bool(getattr(self.factory.user, "is_admin", False))
