"""
🔧 FASE 6: Variables de Entorno para Langsmith
──────────────────────────────────────────────
Configuración de variables de entorno para Langsmith.
Copia estas variables a tu archivo .env:

LANGSMITH_API_KEY=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
LANGSMITH_PROJECT=apichat-backend
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
"""

import os

# Variables de entorno para Langsmith
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "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")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "apichat-backend")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# Verificar si Langsmith está configurado
LANGSMITH_ENABLED = bool(LANGSMITH_API_KEY and LANGSMITH_API_KEY != "your_api_key_here")
