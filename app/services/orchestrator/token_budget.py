"""
Token Budget Manager
───────────────────
Gestiona el presupuesto de tokens para optimizar el uso de contexto
y mantener los costos bajo control.
"""

import time
import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

logger = logging.getLogger(__name__)


class TokenBudgetManager:
    """Gestiona el presupuesto de tokens para el orchestrator."""
    
    # 🔒 CONTROL DE TOKENS - Presupuesto por llamada
    MAX_INPUT_TOKENS = 8000
    MAX_OUTPUT_TOKENS = 2048
    MAX_HISTORY_TURNS = 6
    MAX_SCHEMA_CHARS = 3000
    TOP_K_DBS = 2
    TOP_K_APPS = 2
    
    # 🔒 CONTROL DE TOKENS - Límites adicionales para trimming inteligente
    MAX_HISTORY_CHARS = 5000
    MAX_APP_DESCRIPTOR_CHARS = 2000
    MAX_FUNCTION_DESCRIPTION_CHARS = 100
    
    def __init__(self):
        # 🔒 CONTROL DE TOKENS - Token bucket para rate limiting
        self._token_bucket = {
            "tokens_used": 0,
            "window_start": time.time(),
            "window_size": 60,  # 1 minuto
            "max_tokens_per_window": 10000  # Límite de OpenAI
        }
        
        logger.info("[TokenBudgetManager] Initialized")
    
    def apply_token_budget_to_db_ids(self, db_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """Aplica presupuesto de tokens limitando el número de bases de datos."""
        if not db_ids:
            return db_ids
        
        if len(db_ids) > self.TOP_K_DBS:
            logger.info(f"[TokenBudgetManager] Limiting DBs from {len(db_ids)} to {self.TOP_K_DBS}")
            return db_ids[:self.TOP_K_DBS]
        
        return db_ids
    
    def apply_token_budget_to_app_ids(self, app_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """Aplica presupuesto de tokens limitando el número de aplicaciones."""
        if not app_ids:
            return app_ids
        
        if len(app_ids) > self.TOP_K_APPS:
            logger.info(f"[TokenBudgetManager] Limiting Apps from {len(app_ids)} to {self.TOP_K_APPS}")
            return app_ids[:self.TOP_K_APPS]
        
        return app_ids
    
    def check_token_bucket(self) -> bool:
        """Verifica si el token bucket permite más operaciones."""
        current_time = time.time()
        
        # Resetear ventana si ha expirado
        if current_time - self._token_bucket["window_start"] > self._token_bucket["window_size"]:
            self._token_bucket["tokens_used"] = 0
            self._token_bucket["window_start"] = current_time
            logger.debug("[TokenBudgetManager] Token bucket window reset")
        
        # Verificar si estamos dentro del límite
        if self._token_bucket["tokens_used"] >= self._token_bucket["max_tokens_per_window"]:
            logger.warning(f"[TokenBudgetManager] Token bucket limit exceeded: {self._token_bucket['tokens_used']}")
            return False
        
        return True
    
    def update_token_bucket(self, tokens_used: int):
        """Actualiza el token bucket con tokens consumidos."""
        self._token_bucket["tokens_used"] += tokens_used
        logger.debug(f"[TokenBudgetManager] Updated token bucket: {self._token_bucket['tokens_used']}")
    
    def estimate_tokens_for_context(self, context: Dict[str, Any]) -> int:
        """Estima el número de tokens para un contexto dado."""
        total_chars = 0
        
        # Contar caracteres en diferentes partes del contexto
        if "database_schemas" in context:
            for db_schema in context["database_schemas"].values():
                if isinstance(db_schema, list):
                    for table in db_schema:
                        if isinstance(table, dict):
                            total_chars += len(str(table.get("name", "")))
                            total_chars += len(str(table.get("description", "")))
        
        if "app_descriptors" in context:
            for app in context["app_descriptors"]:
                if isinstance(app, dict):
                    total_chars += len(str(app.get("name", "")))
                    total_chars += len(str(app.get("description", "")))
        
        if "chat_history" in context:
            for msg in context["chat_history"]:
                if isinstance(msg, dict):
                    total_chars += len(str(msg.get("content", "")))
        
        if "functions" in context:
            for func in context["functions"]:
                if isinstance(func, dict):
                    total_chars += len(str(func.get("name", "")))
                    total_chars += len(str(func.get("description", "")))
        
        # Estimación aproximada: 1 token ≈ 4 caracteres
        estimated_tokens = total_chars // 4
        logger.debug(f"[TokenBudgetManager] Estimated tokens: {estimated_tokens} from {total_chars} chars")
        
        return estimated_tokens
    
    def should_use_lite_payload(self, estimated_tokens: int) -> bool:
        """Determina si se debe usar un payload lite basado en tokens estimados."""
        return estimated_tokens > self.MAX_INPUT_TOKENS
    
    def apply_intelligent_context_trimming(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica trimming inteligente al contexto para optimizar tokens."""
        trimmed_context = context.copy()
        
        # Trimming de historial de chat
        if "chat_history" in trimmed_context:
            chat_history = trimmed_context["chat_history"]
            if len(chat_history) > self.MAX_HISTORY_TURNS:
                trimmed_context["chat_history"] = chat_history[-self.MAX_HISTORY_TURNS:]
                logger.info(f"[TokenBudgetManager] Trimmed chat history to {self.MAX_HISTORY_TURNS} turns")
        
        # Trimming de esquemas de base de datos
        if "database_schemas" in trimmed_context:
            for db_id, schema in trimmed_context["database_schemas"].items():
                if isinstance(schema, list) and len(schema) > 10:
                    # Mantener solo las primeras 10 tablas más relevantes
                    trimmed_context["database_schemas"][db_id] = schema[:10]
                    logger.info(f"[TokenBudgetManager] Trimmed DB schema to 10 tables for {db_id}")
        
        # Trimming de descriptores de apps
        if "app_descriptors" in trimmed_context:
            for app in trimmed_context["app_descriptors"]:
                if isinstance(app, dict) and "description" in app:
                    desc = app["description"]
                    if len(desc) > self.MAX_APP_DESCRIPTOR_CHARS:
                        app["description"] = desc[:self.MAX_APP_DESCRIPTOR_CHARS] + "..."
                        logger.debug(f"[TokenBudgetManager] Trimmed app description for {app.get('name', 'unknown')}")
        
        # Trimming de funciones
        if "functions" in trimmed_context:
            for func in trimmed_context["functions"]:
                if isinstance(func, dict) and "description" in func:
                    desc = func["description"]
                    if len(desc) > self.MAX_FUNCTION_DESCRIPTION_CHARS:
                        func["description"] = desc[:self.MAX_FUNCTION_DESCRIPTION_CHARS] + "..."
                        logger.debug(f"[TokenBudgetManager] Trimmed function description for {func.get('name', 'unknown')}")
        
        return trimmed_context
