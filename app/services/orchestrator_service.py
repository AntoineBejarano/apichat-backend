# app/services/orchestrator_service.py
"""
OrchestratorService Refactorizado
─────────────────────────────────
Servicio principal que coordina los módulos especializados:
1. TokenBudgetManager: Control de presupuesto de tokens
2. ContextLoader: Carga de contexto paralelo
3. ResponseProcessor: Procesamiento de respuestas
4. ContextOptimizer: Optimización de contexto
5. GraphRunner: Ejecución de grafos
6. MessageHandler: Manejo de mensajes
7. AdvancedTelemetryService: Telemetría y KPIs (FASE 13)
"""
from __future__ import annotations

import logging
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID, uuid4
import re, difflib

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryCreate, ChatHistoryOut
from app.schemas.plan_schema import PlanModel
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context, memory_profiler
from app.core.database import SessionLocal
from app.common.ws_emitter import WebSocketEmitter
from app.common.enums import Mode
from app.core.config import settings

# Importar ReAct Orchestrator simplificado
from app.services.react_orchestrator import ReActOrchestrator

# Importar ChatHistoryManager
from app.services.orchestrator.chat_history_manager import ChatHistoryManager

# Importar AgentManager
from app.services.orchestrator.agent_manager import AgentManager

from app.utils.response_normalizer import normalize_assistant_response, validate_response_structure  # 🔧 FASE 10: Importar normalización
from app.services.ai.fallback_response_service import FallbackResponseService  # 🔧 FASE 11: Importar servicio de fallback

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Modelo auxiliar (por si lo sigues usando en PlanModel)
# ──────────────────────────────────────────────────────
class ActionModel(BaseModel):
    type: str = Field(..., description="db_query, api_function, mcp_tool")
    sql: Optional[str] = None
    question: Optional[str] = None
    function_id: Optional[int] = None
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    store_as: Optional[str] = None
    proxy_id: Optional[int] = None


# ──────────────────────────────────────────────────────
#   Servicio
# ──────────────────────────────────────────────────────
class OrchestratorService:
    # 🔒 CONTROL DE TOKENS - Presupuesto por llamada (actualizado)
    MAX_INPUT_TOKENS = 8000  # Presupuesto sugerido para input
    MAX_OUTPUT_TOKENS = 2048  # Cap de output tokens
    MAX_HISTORY_TURNS = 6     # Máximo de turnos de historial (reducido de 8 a 6)
    MAX_SCHEMA_CHARS = 3000   # Máximo de caracteres de schema (reducido de 4000 a 3000)
    TOP_K_DBS = 2             # Top-K bases de datos
    TOP_K_APPS = 2            # Top-K aplicaciones
    
    # 🔒 CONTROL DE TOKENS - Límites adicionales para trimming inteligente
    MAX_HISTORY_CHARS = 5000  # Máximo de caracteres de historial
    MAX_APP_DESCRIPTOR_CHARS = 2000  # Máximo de caracteres de descriptores de apps
    MAX_FUNCTION_DESCRIPTION_CHARS = 100  # Máximo de caracteres por descripción de función

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user_id = factory.user.id
        
        # 🧠 ReAct Orchestrator simplificado
        self.react_orchestrator = ReActOrchestrator(factory)
        
        # 🔧 Configuración básica para compatibilidad
        self._token_bucket = {
            "max_tokens_per_window": 10000,
            "tokens_used": 0,
            "window_start": time.time(),
            "window_size": 3600  # 1 hora
        }
        
        # 🆕 WEBSOCKET EMITTER para eventos en tiempo real
        self.ws_emitter: Optional[WebSocketEmitter] = factory.get_ws_emitter()
        
        # 🆕 CHAT HISTORY MANAGER para manejo de historial
        self.chat_history_manager = ChatHistoryManager(factory)
        
        # 🆕 AGENT MANAGER para manejo de agentes
        self.agent_manager = AgentManager(factory)
        
        # 🔧 TEMPORAL: Inicializar servicios faltantes como None para evitar errores
        self.iterative_rag_handler = None
        self.schema_validator = None
        self.response_formatter = None
        self.app_function_manager = None
        self.schema_manager = None
        self.graph_runner = None
        self.response_processor = None
        self.token_budget = None
        
        # 🎯 FASE 13: SERVICIO DE TELEMETRÍA AVANZADO
        self.telemetry_service = factory.get_advanced_telemetry_service()
        self.current_telemetry_context = None
        
        # 🔧 FASE 11: Inicializar servicio de fallback
        self.fallback_service = FallbackResponseService()
        
        logger.info(f"[OrchestratorService] Initialized for user_id={self.user_id}")
        logger.info("[OrchestratorService] ✅ Módulos especializados cargados")
        if self.ws_emitter:
            logger.info("[OrchestratorService] ✅ WebSocket emitter habilitado")
        else:
            logger.info("[OrchestratorService] ℹ️ WebSocket emitter no disponible (modo HTTP)")
        if self.telemetry_service:
            logger.info("[OrchestratorService] ✅ Servicio de telemetría habilitado")
        else:
            logger.info("[OrchestratorService] ℹ️ Servicio de telemetría no disponible")

        # ===================================================
    #  PUBLIC ENTRY-POINT
    # ===================================================
    @monitor_performance("orchestrator_handle_message")
    async def handle_user_message(
        self,
        chat_id: UUID,
        db_ids: Optional[List[UUID]],
        app_ids: Optional[List[UUID]],
        explorer: bool,
        agent_id: Optional[UUID],
        message: ChatMessage,
    ) -> Dict[str, Any]:
        """
        🧠 Maneja mensajes de usuario usando ReAct Orchestrator simplificado
        """
        start_time = time.time()
        logger.info(f"[OrchestratorService] 🧠 ReAct: Procesando mensaje para chat_id={chat_id}")
        
        try:
            # 🧠 Usar ReAct Orchestrator para procesar el mensaje
            react_response = await self.react_orchestrator.handle_message(
                chat_id=chat_id,
                message=message,
                db_ids=db_ids,
                app_ids=app_ids,
                explorer=explorer
            )
            
            # Guardar mensaje del usuario
            await self._store_user_message_async(chat_id, message)
            
            # Guardar respuesta del asistente
            await self._save_assistant_message_async(
                chat_id, 
                react_response.get('content', 'Respuesta generada por ReAct'),
                None,  # No contamos tokens en ReAct por ahora
                None
            )
            
            # Emitir resultado final
            await self.emit_result_final(
                summary=react_response.get('content', 'Consulta procesada por ReAct'),
                data=react_response,
                next_actions=[
                    "Pregunta algo más específico",
                    "Explora los datos disponibles",
                    "Verifica la estructura de las tablas"
                ],
                usage_stats={
                    'response_time_ms': react_response.get('response_time_ms', 0),
                    'iterations': react_response.get('iterations', 0),
                    'method': react_response.get('method', 'react_hybrid'),
                    'mode': 'react_orchestrator'
                }
            )
            
            # 🎯 FASE 13: TRACKING DE TELEMETRÍA (si está disponible)
            if hasattr(self, 'telemetry_service') and self.telemetry_service:
                try:
                    # 🔧 FIX: Usar track_event en lugar de track_conversation_metrics
                    self.telemetry_service.track_event(
                        event_name="conversation_completed",
                        metadata={
                            "conversation_id": str(uuid4()),
                            "user_id": str(self.user_id),
                            "chat_id": str(chat_id),
                            "mode": "explorer" if explorer else "guided",
                            "total_tokens": react_response.get("iterations", 0) * 100,  # Estimación
                            "execution_time_ms": react_response.get("response_time_ms", 0),
                            "success": True,
                            "method": "react_hybrid",
                            "iterations": react_response.get("iterations", 0),
                            "source": react_response.get("source", "react_orchestrator")
                        }
                    )
                except Exception as e:
                    logger.warning(f"[OrchestratorService] ⚠️ Error en tracking de telemetría: {e}")
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[OrchestratorService] ✅ ReAct completado en {execution_time_ms}ms")
            
            return {
                "assistant_response": react_response.get("content", "Respuesta generada por ReAct"),
                "execution_results": react_response,
                "execution_time_ms": execution_time_ms,
                "method": "react_hybrid",
                "status": "completed"
            }
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error en ReAct: {e}")
            
            # Respuesta de error
            error_response = {
                "assistant_response": "🤖 Error interno del sistema. Por favor, contacta soporte.",
                "error": str(e),
                "status": "error",
                "method": "react_hybrid"
            }
            
            await self.emit_error_user_facing(
                code="REACT_ERROR",
                human_message="Error procesando la consulta con ReAct",
                suggested_actions=[
                    "Intentar nuevamente",
                    "Contactar soporte si el problema persiste"
                ],
                technical_details=str(e)
            )
            
            return error_response

    def _is_schema_intent(self, execution_results: Dict[str, Any], user_message: str) -> bool:
        """
        Determina si la intención del usuario es consultar el esquema de la base de datos.
        """
        intent_str = (execution_results.get("intent") or "").lower()
        user_lower = (user_message or "").lower()
        schema_keywords = [
            "tabla", "tablas", "columnas", "columna", "esquema", "schema",
            "estructura", "describe", "ddl", "keys", "primary key", "foreign key"
        ]
        
        return (
            intent_str in ["db_schema", "schema", "describe_schema", "schema_question", "db_read_schema"]
            or any(k in user_lower for k in schema_keywords)
        )

    def _is_schema_lookup_intent(self, user_message: str) -> bool:
        """
        Determina si la intención del usuario es una consulta de esquema simple
        que puede ser resuelta rápidamente sin LLM (Fast Schema Path).
        
        Este método es más específico que _is_schema_intent y se enfoca en
        consultas que pueden ser respondidas usando índices léxicos y cache.
        """
        if not user_message:
            return False
            
        user_lower = user_message.lower().strip()
        
        # Patrones de consulta que pueden ser resueltos rápidamente
        fast_schema_patterns = [
            # Consultas de estructura básica
            "qué tablas hay", "que tablas hay", "qué tablas existen", "que tablas existen",
            "muéstrame las tablas", "muestrame las tablas", "dame las tablas", "obtén las tablas",
            "listar tablas", "listar todas las tablas", "ver tablas", "ver todas las tablas",
            
            # Consultas de columnas específicas
            "qué columnas tiene", "que columnas tiene", "qué campos tiene", "que campos tiene",
            "estructura de", "esquema de", "describe", "ddl de",
            
            # Consultas de relaciones
            "qué claves tiene", "que claves tiene", "primary key", "foreign key",
            "relaciones de", "dependencias de", "referencias de",
            
            # Consultas de búsqueda simple
            "buscar tabla", "encontrar tabla", "tabla llamada", "tabla con nombre",
            "columna llamada", "campo llamado", "atributo llamado",
            
            # Consultas de conteo y resumen
            "cuántas tablas", "cuantas tablas", "cuántas columnas", "cuantas columnas",
            "total de tablas", "total de columnas", "resumen de esquema",
            
            # Consultas de validación
            "existe la tabla", "existe la columna", "está la tabla", "está la columna",
            "hay tabla", "hay columna", "tiene tabla", "tiene columna"
        ]
        
        # Verificar patrones exactos
        for pattern in fast_schema_patterns:
            if pattern in user_lower:
                return True
        
        # Verificar palabras clave individuales que indican consulta de esquema
        schema_keywords = [
            "tabla", "tablas", "columna", "columnas", "campo", "campos",
            "esquema", "schema", "estructura", "ddl", "describe",
            "primary", "foreign", "key", "keys", "relación", "relaciones"
        ]
        
        # Contar cuántas palabras clave están presentes
        keyword_count = sum(1 for keyword in schema_keywords if keyword in user_lower)
        
        # Si hay 2 o más palabras clave de esquema, es probablemente una consulta de esquema
        if keyword_count >= 2:
            return True
        
        # Verificar si la consulta es muy corta (menos de 50 caracteres) y contiene palabras de esquema
        if len(user_message) < 50 and keyword_count >= 1:
            return True
        
        # Verificar si la consulta termina con signos de interrogación y contiene palabras de esquema
        if user_lower.endswith("?") and keyword_count >= 1:
            return True
        
        return False

    def _generate_schema_response(self, context: Dict[str, Any], db_ids: Optional[List[UUID]], user_message: str) -> str:
        """
        Genera una respuesta para consultas de esquema usando el contexto ya cargado.
        """
        table_names: List[str] = []
        db_schemas = context.get("database_schemas", {}) or {}
        
        if db_ids:
            for _dbid in db_ids:
                schema_list = db_schemas.get(_dbid)
                if isinstance(schema_list, list):
                    for t in schema_list:
                        if isinstance(t, dict) and t.get("name"):
                            table_names.append(str(t["name"]))

        # Deduplicar preservando orden
        seen = set()
        unique_tables: List[str] = []
        for n in table_names:
            if n not in seen:
                seen.add(n)
                unique_tables.append(n)

        # Sugerir tablas candidatas de forma GENÉRICA (sin dominios fijos)
        query_tokens = {t for t in re.split(r"[^a-z0-9_]+", user_message.lower()) if len(t) >= 3}
        scores = []
        for name in unique_tables:
            nl = name.lower()
            # señal 1: hay algún token de la pregunta como substring en el nombre de tabla
            hit = any(tok in nl for tok in query_tokens)
            # señal 2: similitud difusa
            ratio = difflib.SequenceMatcher(None, " ".join(sorted(query_tokens)), nl).ratio() if query_tokens else 0.0
            score = (1.0 if hit else 0.0) + ratio
            scores.append((score, name))

        scores.sort(reverse=True)
        candidates = [n for sc, n in scores[:3] if sc > 0.3]

        preview_count = min(10, len(unique_tables))
        lines: List[str] = []
        if preview_count > 0:
            lines.append(f"Estas son algunas tablas de tu base (mostrando las primeras {preview_count}):")
            for n in unique_tables[:preview_count]:
                lines.append(f"- {n}")
            if len(unique_tables) > preview_count:
                lines.append(f"... y {len(unique_tables) - preview_count} más.")
        else:
            lines.append("No pude leer nombres de tablas del caché en este momento.")

        if candidates:
            lines.append("")
            lines.append("Tablas más relacionadas con tu pregunta:")
            for c in candidates:
                lines.append(f"- {c}")
            lines.append("")
            lines.append(f"Ejemplo rápido: `SELECT * FROM {candidates[0]} LIMIT 3;`")

        return "\n".join(lines)

    async def run_iterative_rag(
        self,
        chat_id: UUID,
        message: "ChatMessage",
        db_ids: List[UUID],
        app_ids: List[str],
        explorer: bool = False,
        max_iterations: int = 3
    ) -> Dict[str, Any]:
        """
        Versión iterativa del orchestrator que usa RAG para replanificar
        basándose en resultados intermedios.
        """
        logger.info(f"[OrchestratorService] 🔄 Delegando RAG iterativo al módulo especializado")
        
        # 🔄 REFACTORIZADO: Usar módulo especializado IterativeRAGHandler
        if self.iterative_rag_handler:
            return await self.iterative_rag_handler.run_iterative_rag(
                chat_id=chat_id,
                message=message,
                db_ids=db_ids,
                app_ids=app_ids,
                context_loader=self.context_loader,
                graph_runner=self.graph_runner,
                explorer=explorer,
                max_iterations=max_iterations
            )
        else:
            logger.warning("[OrchestratorService] ⚠️ iterative_rag_handler no disponible")
            return {"error": "IterativeRAGHandler no disponible"}

    def _validate_compact_schemas(self, compact_schemas: Dict, db_ids: List) -> bool:
        """Validar que hay compact_schemas válidos para las DBs solicitadas"""
        # 🔄 REFACTORIZADO: Usar módulo especializado SchemaValidator
        if self.schema_validator:
            return self.schema_validator.validate_compact_schemas(compact_schemas, db_ids)
        else:
            logger.warning("[OrchestratorService] ⚠️ schema_validator no disponible")
            return compact_schemas

    async def _generate_final_answer(
        self, 
        question: str, 
        accumulated_results: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> str:
        """
        Genera la respuesta final basándose en todos los resultados acumulados.
        """
        logger.info("[OrchestratorService] 📝 Delegando generación de respuesta final al módulo especializado")
        
        # 🔄 REFACTORIZADO: Usar módulo especializado IterativeRAGHandler
        if self.iterative_rag_handler:
            return await self.iterative_rag_handler._generate_final_answer(
                question, accumulated_results, context
            )
        else:
            logger.warning("[OrchestratorService] ⚠️ iterative_rag_handler no disponible")
            return {"error": "IterativeRAGHandler no disponible"}

    def _format_results_for_final_answer(self, results: Dict[str, Any]) -> str:
        """Formatea los resultados acumulados para la respuesta final"""
        # 🔄 REFACTORIZADO: Usar módulo especializado ResponseFormatter
        if self.response_formatter:
            return self.response_formatter.format_results_for_final_answer(results)
        else:
            logger.warning("[OrchestratorService] ⚠️ response_formatter no disponible")
            return str(results)

    # ===================================================
    #  ASYNC HELPERS (con sesiones separadas)
    # ===================================================
    @monitor_performance("check_usage_limit")
    @profile_function("check_usage_limit")
    async def _check_usage_limit_async(self):
        """Verificar límite de uso con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                usage_service = temp_factory.get_usage_service()
                
                # Verificar límite de uso
                usage_ok = usage_service.check_limit()
                
                logger.info(f"[OrchestratorService] Usage limit checked with separate session: {usage_ok}")
                return usage_ok
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to check usage limit: {e}")
            return True  # Permitir por defecto si falla la verificación

    @monitor_performance("store_user_message")
    @profile_function("store_user_message")
    async def _store_user_message_async(self, chat_id: UUID, message: ChatMessage):
        """Almacenar mensaje del usuario usando ChatHistoryManager"""
        if self.chat_history_manager:
            await self.chat_history_manager.store_user_message_async(chat_id, message)
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")

    @monitor_performance("save_assistant_message")
    @profile_function("save_assistant_message")
    async def _save_assistant_message_async(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ):
        """Guardar mensaje del asistente usando ChatHistoryManager"""
        if self.chat_history_manager:
            await self.chat_history_manager.save_assistant_message_async(
                chat_id, content, token_count, executed_strategy_id
            )
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")

    @monitor_performance("load_context_parallel")
    @profile_function("load_context_parallel")
    async def _load_context_parallel(
        self, 
        chat_id: str, 
        message: ChatMessage, 
        db_ids: List[UUID], 
        app_ids: List[UUID], 
        explorer: bool = False
    ) -> Dict[str, Any]:
        """Cargar contexto en paralelo con optimizaciones avanzadas y sesiones separadas"""
        try:
            # Crear loop para operaciones asíncronas
            loop = asyncio.get_running_loop()  # 🔧 Python 3.11+ compatible
            
            # 🔧 FIX: Crear sesiones separadas para cada tarea para evitar conflictos de concurrencia
            from app.core.database import SessionLocal
            
            # Tareas paralelas optimizadas - cada una con su propia sesión
            tasks = [
                self._store_user_message_async(chat_id, message),
                self._load_history_async(chat_id),
                self._check_usage_limit_async(),
                self._load_database_schemas_async(db_ids),
                self._load_apps_async(app_ids)
            ]
            
            # 🔧 FIX: Ejecutar con timeout para evitar bloqueos
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=30.0  # 30 segundos timeout
                )
            except asyncio.TimeoutError:
                logger.error("[OrchestratorService] ⏰ Timeout en _load_context_parallel - usando valores por defecto")
                results = [False, [], True, {'schemas': {}, 'compact_schemas': {}, 'cache_status': {}}, []]
            
            # Procesar resultados
            user_message_stored = results[0] if not isinstance(results[0], Exception) else False
            history = results[1] if not isinstance(results[1], Exception) else []
            usage_ok = results[2] if not isinstance(results[2], Exception) else True
            schema_result = results[3] if not isinstance(results[3], Exception) else {
                'schemas': {}, 'compact_schemas': {}, 'cache_status': {}
            }
            apps = results[4] if not isinstance(results[4], Exception) else []
            
            # Extraer componentes del schema result
            database_schemas = schema_result.get('schemas', {})  # Legacy format
            compact_schemas = schema_result.get('compact_schemas', {})  # Para LLM
            cache_status = schema_result.get('cache_status', {})  # Para debugging
            
            # Construir contexto básico - sin optimizaciones complejas por ahora
            context = {
                "chat_id": chat_id,
                "message": message,
                "history": history,
                "database_schemas": database_schemas,  # Legacy format (mantener compatibilidad)
                "compact_schemas": compact_schemas,  # 🔧 NUEVO: Para el LLM
                "cache_status": cache_status,  # Para debugging
                "apps": apps,
                "explorer": explorer,
                # 🔧 FIX: Incluir db_ids y app_ids para que el grafo los reconozca
                "db_ids": db_ids,
                "app_ids": app_ids,
                # Servicios básicos - se cargarán solo si se necesitan
                "functions": [],  # Se cargará solo si el usuario pide funciones
                "available_mcp_tools": {}  # Se cargará solo si el usuario pide MCP tools
            }
            
            logger.info(f"[OrchestratorService] 📊 Contexto básico cargado: {len(database_schemas)} DBs")
            return context
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error cargando contexto: {e}")
            # Fallback a contexto básico
            return {
                "chat_id": chat_id,
                "message": message,
                "history": [],
                "database_schemas": {},
                "apps": [],
                "functions": [],
                "available_mcp_tools": {},
                "explorer": explorer,
                # 🔧 FIX: Incluir db_ids y app_ids en fallback también
                "db_ids": db_ids,
                "app_ids": app_ids
            }
    
    # 🔒 CONTROL DE TOKENS - Métodos de presupuesto
    def _apply_token_budget_to_db_ids(self, db_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """
        Aplica presupuesto de tokens limitando el número de bases de datos.
        """
        if not db_ids:
            return db_ids
        
        # Limitar a TOP_K_DBS para controlar tokens
        limited_db_ids = db_ids[:self.TOP_K_DBS]
        
        if len(limited_db_ids) < len(db_ids):
            logger.info(f"[OrchestratorService] 🔒 Token budget: limitando DBs de {len(db_ids)} a {len(limited_db_ids)}")
        
        return limited_db_ids
    
    def _apply_token_budget_to_app_ids(self, app_ids: Optional[List[UUID]]) -> Optional[List[UUID]]:
        """Aplicar token budget a app IDs usando AppFunctionManager"""
        if not app_ids:
            return None
        
        # Limitar a TOP_K_APPS para control de tokens
        limited_app_ids = app_ids[:self.TOP_K_APPS]
        
        if len(limited_app_ids) < len(app_ids):
            logger.info(f"[OrchestratorService] 🔒 Token budget: apps limitados de {len(app_ids)} a {len(limited_app_ids)}")
        
        return limited_app_ids
    
    def _estimate_tokens_for_context(self, context: Dict[str, Any]) -> int:
        """Estima el número de tokens para un contexto dado usando los managers especializados"""
        try:
            total_chars = 0
            
            # 1. Historial usando ChatHistoryManager
            if "history" in context:
                history = context["history"]
                if self.chat_history_manager:
                    total_chars += self.chat_history_manager.estimate_history_tokens(history)
                else:
                    logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible para estimación de tokens")
            
            # 2. Esquemas de base de datos
            if "compact_schemas" in context:
                for db_id, schema_data in context["compact_schemas"].items():
                    if isinstance(schema_data, dict) and "compact" in schema_data:
                        total_chars += len(schema_data["compact"])
            
            # 3. Descriptores de apps
            if "app_descriptors_compact" in context and context["app_descriptors_compact"]:
                total_chars += len(context["app_descriptors_compact"])
            
            # 4. Funciones y apps usando AppFunctionManager
            if "functions" in context or "apps" in context or "mcp_tools" in context:
                apps = context.get("apps", [])
                functions = context.get("functions", [])
                mcp_tools = context.get("mcp_tools", {})
                if self.app_function_manager:
                    total_chars += self.app_function_manager.estimate_app_function_tokens(apps, functions, mcp_tools)
                else:
                    logger.warning("[OrchestratorService] ⚠️ app_function_manager no disponible para estimación de tokens")
            
            # Estimación aproximada: 1 token ≈ 4 caracteres
            estimated_tokens = total_chars // 4
            logger.debug(f"[OrchestratorService] 🔍 Tokens estimados para contexto: {estimated_tokens}")
            return estimated_tokens
            
        except Exception as e:
            logger.warning(f"[OrchestratorService] ⚠️ Error estimando tokens del contexto: {e}")
            return 0
    
    def _should_use_lite_payload(self, estimated_tokens: int) -> bool:
        """Determinar si usar payload lite basado en tokens estimados"""
        return estimated_tokens > self.MAX_INPUT_TOKENS
    
    async def _build_lite_payload(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Construir payload lite usando AppFunctionManager"""
        apps = context.get('apps', [])
        functions = context.get('functions', [])
        mcp_tools = context.get('mcp_tools', {})
        
        if self.app_function_manager:
            return self.app_function_manager.create_lite_payload(apps, functions, mcp_tools)
        else:
            logger.warning("[OrchestratorService] ⚠️ app_function_manager no disponible")
            return {"error": "AppFunctionManager no disponible"}

    async def _optimize_context_with_ai(
        self, 
        user_query: str, 
        database_schemas: Dict[UUID, List[Dict[str, Any]]], 
        db_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Optimizar contexto usando Vector Search y Prompt Engineering.
        
        Args:
            user_query: Query del usuario
            database_schemas: Esquemas de base de datos
            db_ids: IDs de las bases de datos
            
        Returns:
            Contexto optimizado con información semántica
        """
        try:
            vector_search = self.factory.get_vector_search_service()
            prompt_engineering = self.factory.get_prompt_engineering_service()
            
            optimized_context = {
                "optimized_schema": {},
                "semantic_hints": [],
                "prompt_optimization": {}
            }
            
            # Para cada base de datos, optimizar el contexto
            for db_id in db_ids:
                if db_id in database_schemas:
                    # 1. Búsqueda vectorial para encontrar elementos relevantes
                    search_results = await vector_search.semantic_search(
                        db_id, user_query, top_k=5
                    )
                    
                    # 2. Optimizar esquema basado en resultados de búsqueda
                    if self.schema_manager:
                        optimized_schema = self._optimize_schema_with_search_results(
                            database_schemas[db_id], search_results
                        )
                    else:
                        logger.warning("[OrchestratorService] ⚠️ schema_manager no disponible para optimización")
                        optimized_schema = database_schemas[db_id]
                    
                    # 3. Optimizar prompt para la query específica
                    optimized_prompt = prompt_engineering.optimize_prompt_for_query(
                        user_query, optimized_schema, search_results
                    )
                    
                    # 4. Agregar al contexto optimizado
                    optimized_context["optimized_schema"][db_id] = optimized_schema  # 🔧 UUID como clave
                    optimized_context["semantic_hints"].extend(optimized_prompt.semantic_hints)
                    optimized_context["prompt_optimization"][db_id] = {  # 🔧 UUID como clave
                        "system_prompt": optimized_prompt.system_prompt,
                        "user_prompt": optimized_prompt.user_prompt,
                        "confidence_score": optimized_prompt.confidence_score,
                        "optimization_notes": optimized_prompt.optimization_notes
                    }
            
            logger.info(f"[OrchestratorService] 🦄 Contexto optimizado para {len(db_ids)} DBs")
            return optimized_context
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error optimizando contexto: {e}")
            return {
                "optimized_schema": {},
                "semantic_hints": [],
                "prompt_optimization": {}
            }
    
    def _optimize_schema_with_search_results(
        self, 
        schema: List[Dict[str, Any]], 
        search_results: List[Any]
    ) -> Dict[str, Any]:
        """Optimizar esquema con resultados de búsqueda usando SchemaManager"""
        if self.schema_manager:
            return self.schema_manager.optimize_schema_with_search_results(schema, search_results)
        else:
            logger.warning("[OrchestratorService] ⚠️ schema_manager no disponible")
            return schema

    @monitor_performance("load_database_schemas")
    @profile_function("load_database_schemas")
    async def _load_database_schemas_async(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Cargar esquemas de base de datos usando SchemaManager.
        
        Returns:
            Dict con:
            - 'schemas': Dict[UUID, List[Dict]] - Esquemas detallados (legacy)
            - 'compact_schemas': Dict[UUID, str] - Esquemas compactos para LLM
            - 'cache_status': Dict[UUID, str] - Estado del cache por DB
        """
        if self.schema_manager:
            return await self.schema_manager.load_database_schemas_async(db_ids)
        else:
            logger.warning("[OrchestratorService] ⚠️ schema_manager no disponible")
            return {'schemas': {}, 'compact_schemas': {}, 'cache_status': {}}
    
    def _introspect_minimal_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección mínima de esquema usando SchemaManager"""
        if self.schema_manager:
            return self.schema_manager._introspect_minimal_schema(db_id)
        else:
            logger.warning("[OrchestratorService] ⚠️ schema_manager no disponible")
            return None

    def _convert_snapshot_to_legacy(self, snapshot_tables: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convertir snapshot a formato legacy usando SchemaManager"""
        if self.schema_manager:
            return self.schema_manager._convert_snapshot_to_legacy(snapshot_tables)
        else:
            logger.warning("[OrchestratorService] ⚠️ schema_manager no disponible")
            return []

    @monitor_performance("load_agent_prompt")
    @profile_function("load_agent_prompt")
    async def _load_agent_prompt_async(self, agent_id: UUID) -> str:
        """Cargar prompt del agente con sesión separada para evitar conflictos de concurrencia"""
        try:
            # 🔧 FIX: Crear sesión separada para evitar conflictos
            from app.core.database import SessionLocal
            db = SessionLocal()
            
            try:
                # Crear una nueva instancia del servicio con la sesión separada
                from app.core.service_factory import ServiceFactory
                temp_factory = ServiceFactory(db=db, request=self.factory.request)
                agent_service = temp_factory.get_agent_service()
                
                # Obtener prompt del agente
                agent = agent_service.get_agent(agent_id)
                if agent and agent.prompt:
                    logger.info(f"[OrchestratorService] Agent prompt loaded with separate session for agent {agent_id}")
                    return agent.prompt
                else:
                    logger.warning(f"[OrchestratorService] No prompt found for agent {agent_id}")
                    return ""
            finally:
                db.close()
        except Exception as e:
            logger.exception(f"[OrchestratorService] Failed to load agent prompt: {e}")
            return ""

    @monitor_performance("load_history")
    @profile_function("load_history")
    async def _load_history_async(self, chat_id: UUID) -> List[Dict[str, Any]]:
        """Cargar historial del chat usando ChatHistoryManager"""
        if self.chat_history_manager:
            return await self.chat_history_manager.load_history_async(chat_id)
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")
            return []

    @monitor_performance("load_apps")
    @profile_function("load_apps")
    async def _load_apps_async(self, app_ids: List[UUID]) -> List[Dict[str, Any]]:
        """Cargar aplicaciones usando AppFunctionManager"""
        if self.app_function_manager:
            return await self.app_function_manager.load_apps_async(app_ids)
        else:
            logger.warning("[OrchestratorService] ⚠️ app_function_manager no disponible")
            return []

    @monitor_performance("load_functions")
    @profile_function("load_functions")
    async def _load_functions_async(self) -> List[Dict[str, Any]]:
        """Cargar funciones disponibles usando AppFunctionManager"""
        if self.app_function_manager:
            return await self.app_function_manager.load_functions_async()
        else:
            logger.warning("[OrchestratorService] ⚠️ app_function_manager no disponible")
            return []

    @monitor_performance("load_mcp_tools")
    @profile_function("load_mcp_tools")
    async def _load_mcp_tools_async(self) -> Dict[str, Any]:
        """Cargar herramientas MCP disponibles usando AppFunctionManager"""
        if self.app_function_manager:
            return await self.app_function_manager.load_mcp_tools_async()
        else:
            logger.warning("[OrchestratorService] ⚠️ app_function_manager no disponible")
            return {}

    # ===================================================
    #  MÉTODOS DE CONTROL DE TOKENS MEJORADOS
    # ===================================================
    def _check_token_bucket(self) -> bool:
        """Verifica si hay tokens disponibles en el bucket"""
        current_time = time.time()
        
        # Resetear bucket si ha pasado la ventana de tiempo
        if current_time - self._token_bucket["window_start"] > self._token_bucket["window_size"]:
            self._token_bucket["tokens_used"] = 0
            self._token_bucket["window_start"] = current_time
            logger.debug("[OrchestratorService] 🔒 Token bucket reseteado")
        
        # Verificar si hay tokens disponibles
        available_tokens = self._token_bucket["max_tokens_per_window"] - self._token_bucket["tokens_used"]
        
        if available_tokens < self.MAX_INPUT_TOKENS:
            logger.warning(f"[OrchestratorService] 🔒 Token bucket limitado: {available_tokens} disponibles, {self.MAX_INPUT_TOKENS} necesarios")
            return False
        
        return True

    def _update_token_bucket(self, tokens_used: int):
        """Actualiza el token bucket con los tokens utilizados"""
        self._token_bucket["tokens_used"] += tokens_used
        logger.debug(f"[OrchestratorService] 🔒 Token bucket actualizado: {self._token_bucket['tokens_used']} tokens usados")

    def _apply_intelligent_context_trimming(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aplicar trimming inteligente usando los managers especializados"""
        trimmed_context = context.copy()
        
        # Trimming de historial usando ChatHistoryManager
        if 'chat_history' in trimmed_context:
            history = trimmed_context['chat_history']
            if self.chat_history_manager:
                estimated_tokens = self.chat_history_manager.estimate_history_tokens(history)
                if estimated_tokens > self.MAX_HISTORY_CHARS:
                    # Aplicar trimming inteligente
                    trimmed_context['chat_history'] = self.chat_history_manager._apply_intelligent_history_trimming(history)
                    logger.info(f"[OrchestratorService] 🔒 Token budget: historial optimizado de {estimated_tokens} a {self.MAX_HISTORY_CHARS} chars")
            else:
                logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible para trimming de historial")
                estimated_tokens = 0
        
        # Trimming de esquemas usando SchemaManager
        if 'database_schemas' in trimmed_context:
            schemas = trimmed_context['database_schemas']
            for db_id, schema in schemas.items():
                if isinstance(schema, str) and len(schema) > self.MAX_SCHEMA_CHARS:
                    trimmed_context['database_schemas'][db_id] = schema[:self.MAX_SCHEMA_CHARS] + "... [truncado]"
                    logger.info(f"[OrchestratorService] 🔒 Token budget: schema DB {db_id} truncado a {self.MAX_SCHEMA_CHARS} chars")
        
        # Trimming de apps usando AppFunctionManager
        if 'apps' in trimmed_context:
            apps = trimmed_context['apps']
            for app in apps:
                if 'description' in app and len(app['description']) > self.MAX_APP_DESCRIPTOR_CHARS:
                    app['description'] = app['description'][:self.MAX_APP_DESCRIPTOR_CHARS] + "... [truncado]"
        
        # Trimming de funciones usando AppFunctionManager
        if 'functions' in trimmed_context:
            functions = trimmed_context['functions']
            for func in functions:
                if 'description' in func and len(func['description']) > self.MAX_FUNCTION_DESCRIPTION_CHARS:
                    func['description'] = func['description'][:self.MAX_FUNCTION_DESCRIPTION_CHARS] + "... [truncado]"
        
        return trimmed_context

    def _should_force_plan(self, db_ids: Optional[List[UUID]], user_message: str, execution_results: Dict[str, Any]) -> bool:
        """Determina si se debe forzar la generación de un plan basado en la intención del usuario"""
        # ⛔ Si la intención es de ESQUEMA, no forzar plan
        intent_str = (execution_results.get("intent") or "").lower()
        if intent_str in ["db_schema", "schema", "describe_schema", "schema_question", "db_read_schema"]:
            logger.info("[OrchestratorService] ⛔ No se fuerza plan: intención de esquema")
            return False

        # 1. Si hay bases de datos especificadas, forzar plan
        if db_ids:
            logger.info("[OrchestratorService] 🔒 Forzando plan por presencia de bases de datos")
            return True
        
        # 2. Si el mensaje contiene palabras clave de consulta de base de datos
        db_keywords = [
            "consulta", "query", "select", "buscar", "encontrar", "mostrar", "listar",
            "cuántos", "cuántas", "dónde", "cuándo", "datos", "información",
            "tabla", "registro", "fila", "columna", "base de datos", "database"
        ]
        
        user_message_lower = user_message.lower()
        has_db_intention = any(keyword in user_message_lower for keyword in db_keywords)
        
        if has_db_intention:
            logger.info("[OrchestratorService] 🔒 Forzando plan por palabras clave de consulta de base de datos")
            return True
        
        # 3. Si ya hay un plan generado, no forzar
        if execution_results.get("plan"):
            return False
        
        # 4. Por defecto, no forzar (dejar que el LLM decida)
        return False

    def _generate_minimal_plan_for_db_intention(self, user_message: str, db_ids: List[UUID]) -> Dict[str, Any]:
        """Genera un plan mínimo cuando se detecta intención de base de datos"""
        logger.info("[OrchestratorService] 🔒 Generando plan mínimo para intención de base de datos")
        
        # Crear un plan básico con una acción de consulta y steps
        plan = {
            "actions": [
                {
                    "type": "db_query",
                    "question": user_message,
                    "store_as": "query_result"
                }
            ],
            "steps": [
                {
                    "type": "step",
                    "message": "Consultando base de datos para obtener la información solicitada",
                    "status": "in_progress"
                },
                {
                    "type": "step", 
                    "message": "Resultados obtenidos: {query_result}",
                    "status": "pending",
                    "depends_on": "query_result",
                    "template": "Resultados obtenidos: {query_result}"
                }
            ]
        }
        
        logger.info(f"[OrchestratorService] ✅ Plan mínimo generado con {len(plan['actions'])} acción(es) y {len(plan['steps'])} steps")
        return plan

    async def _handle_message_with_minimal_context(
        self,
        chat_id: UUID,
        db_ids: Optional[List[UUID]],
        app_ids: Optional[List[UUID]],
        explorer: bool,
        agent_id: Optional[UUID],
        message: ChatMessage
    ) -> Dict[str, Any]:
        """
        Maneja mensajes con contexto mínimo cuando falla el ContextLoader.
        
        Args:
            chat_id: ID del chat
            db_ids: IDs de bases de datos
            app_ids: IDs de aplicaciones
            explorer: Si está en modo explorador
            agent_id: ID del agente
            message: Mensaje del usuario
            
        Returns:
            Respuesta básica con contexto mínimo
        """
        try:
            logger.info("[OrchestratorService] 🔒 Usando contexto mínimo debido a fallo en ContextLoader")
            
            # Crear contexto mínimo
            minimal_context = {
                "chat_history": [],
                "database_schemas": {},
                "compact_schemas": {},
                "app_descriptors": [],
                "functions": [],
                "mcp_tools": {},
                "explorer": explorer,
                "error": "context_loader_failed"
            }
            
            # Intentar ejecutar con contexto mínimo
            try:
                if self.graph_runner:
                    execution_results = await self.graph_runner.run_graph(explorer, chat_id, message.content, minimal_context)
                    execution_results = self.graph_runner.normalize_graph_output(execution_results)
                else:
                    logger.warning("[OrchestratorService] ⚠️ graph_runner no disponible")
                    execution_results = {"error": "GraphRunner no disponible"}
                
                # Procesar respuesta
                if self.response_processor:
                    processed_response = await self.response_processor.process_response(
                        execution_results, minimal_context, message.content
                    )
                else:
                    logger.warning("[OrchestratorService] ⚠️ response_processor no disponible")
                    processed_response = execution_results
                
                return {
                    "assistant_response": processed_response.get("response", "Lo siento, estoy experimentando problemas técnicos. Por favor, intenta nuevamente."),
                    "context_used": "minimal",
                    "warning": "Se usó contexto mínimo debido a problemas técnicos"
                }
                
            except Exception as e:
                logger.error(f"[OrchestratorService] ❌ Error ejecutando con contexto mínimo: {e}")
                
                # Respuesta de emergencia
                return {
                    "assistant_response": "Lo siento, estoy experimentando problemas técnicos temporales. Por favor, intenta nuevamente en unos momentos o contacta soporte si el problema persiste.",
                    "error": "execution_failed",
                    "context_used": "minimal",
                    "technical_details": str(e)
                }
                
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error en manejo de contexto mínimo: {e}")
            return {
                "assistant_response": "Error interno del sistema. Por favor, contacta soporte.",
                "error": "internal_error",
                "technical_details": str(e)
            }

    # ===================================================
    #  HELPERS (mantienen la funcionalidad original)
    # ===================================================
    def _select_graph_runner(self, explorer: bool):
        from app.services.execution.graphs.exploration_graph import ExplorationGraph
        from app.services.execution.graphs.guided_graph import GuidedGraph
        GraphClass = ExplorationGraph if explorer else GuidedGraph
        logger.info("[OrchestratorService] Using graph: %s", GraphClass.__name__)
        return GraphClass(self.factory)

    def _normalize_graph_output(self, output: Any) -> Dict[str, Any]:
        """
        Normaliza la salida del grafo para que siempre sea un diccionario.
        Esto asegura que las claves de acceso sean consistentes.
        """
        if isinstance(output, dict):
            # 🔧 FIX: Normalizar también el message anidado si existe
            normalized = output.copy()
            if "message" in normalized and hasattr(normalized["message"], "model_dump"):
                # Si message es un ChatMessage, convertirlo a dict también
                normalized["message"] = normalized["message"].model_dump()
            return normalized
        elif hasattr(output, 'model_dump'):  # Pydantic models como ChatMessage
            # Convertir Pydantic model a dict
            normalized = output.model_dump()
            # Si es un ChatMessage, extraer el contenido principal
            if hasattr(output, 'content') and hasattr(output, 'role'):
                if output.role == 'assistant':
                    normalized['assistant_response'] = output.content
                else:
                    normalized['message'] = output.content
            return normalized
        elif hasattr(output, 'content'):  # Objetos con atributo content
            return {
                'assistant_response': str(output.content),
                'result': output
            }
        elif isinstance(output, list):
            return {"results": output}
        elif output is None:
            return {}
        else:
            # Para cualquier otro tipo, convertirlo a string y guardarlo
            return {
                'assistant_response': str(output),
                'result': output
            }

    def _calculate_content_length(self, data: Dict[str, Any]) -> int:
        """Calcula la longitud del contenido de la respuesta del asistente."""
        if "assistant_response" in data:
            response_content = data["assistant_response"]
            if isinstance(response_content, dict) and "content" in response_content:
                return len(str(response_content["content"]))
            return len(str(response_content))
        elif "response" in data:
            return len(str(data["response"]))
        elif "content" in data:
            return len(str(data["content"]))
        elif "message" in data:
            return len(str(data["message"]))
        return 0

    def _store_user_message(self, chat_id: UUID, message: ChatMessage) -> None:
        """Almacenar mensaje del usuario usando ChatHistoryManager"""
        if self.chat_history_manager:
            asyncio.create_task(self.chat_history_manager.store_user_message_async(chat_id, message))
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")

    def _save_assistant_message(
        self,
        chat_id: UUID,
        content: str,
        token_count: Optional[int],
        executed_strategy_id: Optional[UUID] = None,
    ) -> None:
        """Guardar mensaje del asistente usando ChatHistoryManager"""
        if self.chat_history_manager:
            asyncio.create_task(self.chat_history_manager.save_assistant_message_async(
                chat_id, content, token_count, executed_strategy_id
            ))
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")

    def _load_history_with_session(self, chat_id: UUID) -> List[Any]:
        """Cargar historial con sesión usando ChatHistoryManager"""
        if self.chat_history_manager:
            return self.chat_history_manager._load_history_with_session(chat_id)
        else:
            logger.warning("[OrchestratorService] ⚠️ chat_history_manager no disponible")
            return []

    def _load_agent_prompt(self, agent_id: Optional[UUID]) -> str:
        """Cargar prompt del agente usando AgentManager"""
        if not agent_id:
            return ""
        if not self.agent_manager:
            logger.warning("[OrchestratorService] ⚠️ agent_manager no disponible")
            return ""
        try:
            return self.agent_manager.get_agent_prompt(agent_id)
        except Exception as e:
            logger.warning(f"[OrchestratorService] Agent prompt load failed: {e}")
            return ""

    def _check_usage_limit(self) -> None:
        """Verificar límites de uso usando UsageService"""
        try:
            usage_service = self.factory.get_usage_service()
            if usage_service:
                usage_service.check_limit()
            else:
                logger.warning("[OrchestratorService] ⚠️ usage_service no disponible")
        except Exception as e:
            logger.warning(f"[OrchestratorService] Usage limit check failed: {e}")

    def _extract_assistant_response(self, execution_results: Dict[str, Any]) -> str:
        """Extraer la respuesta del asistente de los resultados de ejecución"""
        logger.info(f"[OrchestratorService] 🔍 Extrayendo respuesta del resultado (keys: {list(execution_results.keys())}")
        
        # 🛡️ GUARD CLAUSE: Si hay plan ejecutado, SIEMPRE priorizar sobre stub
        if execution_results.get("plan") and execution_results.get("variables"):
            logger.info(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Plan ejecutado detectado - priorizando sobre cualquier stub")
            
            # Buscar respuesta del plan ejecutado
            variables = execution_results.get("variables", {})
            for var_name, var_value in variables.items():
                if var_name in ["query_result", "result", "answer", "response"] and var_value:
                    if "stub temporal" not in str(var_value).lower():
                        normalized = normalize_assistant_response(var_value)
                        logger.info(f"[OrchestratorService] 🛡️ PLAN REAL: Variable {var_name} priorizada: '{normalized}'")
                        return normalized
        
        # 🛡️ GUARD CLAUSE: Si hay bases de datos, nunca devolver stub temporal
        has_databases = (
            execution_results.get("db_ids") or 
            execution_results.get("databases") or
            execution_results.get("selected_database")
        )
        
        if has_databases:
            logger.info(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Bases de datos detectadas - evitando stub temporal")
        
        # 🔧 FASE 10: Usar normalización centralizada
        try:
            # Intentar normalizar directamente si hay assistant_response (y no es stub)
            if "assistant_response" in execution_results and execution_results["assistant_response"]:
                response_text = str(execution_results["assistant_response"])
                if has_databases and "stub temporal" in response_text.lower():
                    logger.warning(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Rechazando assistant_response por contener stub temporal con DB presente")
                else:
                    normalized = normalize_assistant_response(execution_results["assistant_response"])
                    logger.info(f"[OrchestratorService] 🔧 FASE 10: assistant_response normalizado: '{normalized}'")
                    return normalized
            
            # Si no hay assistant_response, buscar en otros campos (evitando stub si hay DB)
            for field in ["response", "message", "content"]:
                if field in execution_results and execution_results[field]:
                    field_text = str(execution_results[field])
                    if has_databases and "stub temporal" in field_text.lower():
                        logger.warning(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Rechazando {field} por contener stub temporal con DB presente")
                        continue
                    normalized = normalize_assistant_response(execution_results[field])
                    logger.info(f"[OrchestratorService] 🔧 FASE 10: {field} normalizado: '{normalized}'")
                    return normalized
            
            # 🔧 FASE 10: Buscar en variables como fallback (evitando stub si hay DB)
            if "variables" in execution_results and execution_results["variables"]:
                variables = execution_results["variables"]
                for var_name, var_value in variables.items():
                    if var_name in ["query_result", "result", "answer"] and var_value:
                        var_text = str(var_value)
                        if has_databases and "stub temporal" in var_text.lower():
                            logger.warning(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Rechazando variable {var_name} por contener stub temporal con DB presente")
                            continue
                        normalized = normalize_assistant_response(var_value)
                        logger.info(f"[OrchestratorService] 🔧 FASE 10: Variable {var_name} normalizada: '{normalized}'")
                        return normalized
            
            # 🛡️ GUARD CLAUSE: Si hay bases de datos, generar respuesta específica en lugar de fallback genérico
            if has_databases:
                logger.warning(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Con DB presente, generando respuesta específica en lugar de fallback")
                return "He procesado tu consulta sobre la base de datos. Los resultados están disponibles en el contexto de ejecución."
            
            # 🔧 FASE 11: Si no hay respuesta válida, usar servicio de fallback
            logger.warning(f"[OrchestratorService] 🔧 FASE 11: No hay respuesta válida, usando servicio de fallback")
            if self.fallback_service:
                fallback_response = self.fallback_service.generate_fallback_response(
                    execution_results=execution_results,
                    user_message="",  # Se pasará desde el método que llama
                    context=None
                )
            else:
                logger.warning("[OrchestratorService] ⚠️ fallback_service no disponible")
                fallback_response = "Lo siento, no pude procesar tu solicitud. Por favor, intenta nuevamente."
            return fallback_response
            
        except Exception as e:
            logger.error(f"[OrchestratorService] 🔧 FASE 10: Error normalizando respuesta: {e}")
            
            # 🛡️ GUARD CLAUSE: Si hay bases de datos, evitar fallback genérico incluso en error
            if has_databases:
                logger.warning(f"[OrchestratorService] 🛡️ GUARD CLAUSE: Error con DB presente, generando respuesta específica")
                return f"Se produjo un error procesando la consulta de base de datos: {str(e)}"
            
            # 🔧 FASE 11: En caso de error, usar fallback
            return self.fallback_service.generate_fallback_response(
                execution_results={"error": str(e)},
                user_message="",
                context=None
            )

    # ===================================================
    #  MÉTODOS STUB DE EMISIÓN WEBSOCKET (FASE 0)
    # ===================================================
    
    async def emit_status_typing(self, is_typing: bool = True) -> bool:
        """Emite evento de estado de escritura (stub)."""
        if self.ws_emitter:
            if self.ws_emitter:
                return await self.ws_emitter.emit_status_typing(is_typing)
            else:
                logger.warning("[OrchestratorService] ⚠️ ws_emitter no disponible")
                return False
        return False
    
    async def emit_status_progress(
        self, 
        step: int, 
        total_steps: int, 
        message: str, 
        percentage: Optional[float] = None
    ) -> bool:
        """Emite evento de progreso (stub)."""
        if self.ws_emitter:
            if self.ws_emitter:
                return await self.ws_emitter.emit_status_progress(step, total_steps, message, percentage)
            else:
                logger.warning("[OrchestratorService] ⚠️ ws_emitter no disponible")
                return False
        return False
    
    async def emit_decision_request(
        self,
        decision_id: str,
        title: str,
        description: str,
        options: list,
        timeout_seconds: int = 30,
        default_action: str = "cancel"
    ) -> bool:
        """Emite solicitud de decisión (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_decision_request(
                decision_id, title, description, options, timeout_seconds, default_action
            )
        return False
    
    async def emit_result_partial(
        self,
        step: int,
        data: Dict[str, Any],
        preview: Optional[str] = None
    ) -> bool:
        """Emite resultado parcial (stub)."""
        if self.ws_emitter:
            if self.ws_emitter:
                return await self.ws_emitter.emit_result_partial(step, data, preview)
            else:
                logger.warning("[OrchestratorService] ⚠️ ws_emitter no disponible")
                return False
        return False
    
    async def emit_result_final(
        self,
        summary: str,
        data: Dict[str, Any],
        next_actions: list,
        usage_stats: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emite resultado final (stub)."""
        if self.ws_emitter:
            if self.ws_emitter:
                return await self.ws_emitter.emit_result_final(summary, data, next_actions, usage_stats)
            else:
                logger.warning("[OrchestratorService] ⚠️ ws_emitter no disponible")
                return False
        return False
    
    async def emit_notice_info(
        self,
        message: str,
        level: str = "info",
        actions: Optional[list] = None
    ) -> bool:
        """Emite notificación informativa (stub)."""
        if self.ws_emitter:
            if self.ws_emitter:
                return await self.ws_emitter.emit_notice_info(message, level, actions)
            else:
                logger.warning("[OrchestratorService] ⚠️ ws_emitter no disponible")
                return False
        return False
    
    async def emit_error_user_facing(
        self,
        code: str,
        human_message: str,
        suggested_actions: list,
        technical_details: Optional[str] = None
    ) -> bool:
        """Emite error para el usuario (stub)."""
        if self.ws_emitter:
            return await self.ws_emitter.emit_error_user_facing(
                code, human_message, suggested_actions, technical_details
            )
        return False
    
    async def emit_telemetry_snapshot(
        self,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cache_hit_ratio: float,
        steps_executed: int,
        confirmations_required: int,
        mode: Mode
    ) -> bool:
        """Emite snapshot de telemetría al finalizar la ejecución."""
        try:
            event = {
                "type": "telemetry.snapshot",
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "latency_ms": latency_ms,
                "cache_hit_ratio": cache_hit_ratio,
                "steps_executed": steps_executed,
                "confirmations_required": confirmations_required,
                "mode": mode.value,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.ws_emitter.emit(event)
            logger.info(f"[OrchestratorService] 📊 Telemetría emitida: {latency_ms:.1f}ms, {tokens_in}+{tokens_out} tokens")
            return True
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error emitiendo telemetría: {e}")
            return False
    
    async def emit_resource_proposal(
        self,
        proposal_id: str,
        title: str,
        description: str,
        options: List[Dict[str, Any]],
        user_message: str,
        timeout_seconds: int = 60,
        default_action: str = "explore_only"
    ) -> bool:
        """Emite propuesta de recursos para modo Explorer."""
        try:
            event = {
                "type": "resource.proposal",
                "proposal_id": proposal_id,
                "title": title,
                "description": description,
                "options": options,
                "user_message": user_message,
                "timeout_seconds": timeout_seconds,
                "default_action": default_action,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.ws_emitter.emit(event)
            logger.info(f"[OrchestratorService] 🎯 Propuesta de recursos emitida: {proposal_id}")
            return True
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error emitiendo propuesta de recursos: {e}")
            return False

    async def handle_token_budget_mode_change(
        self,
        chat_id: UUID,
        new_mode: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🎯 FASE 10: Maneja cambios de modo de TokenBudget (rápido/equilibrado/preciso).
        
        Args:
            chat_id: ID del chat
            new_mode: Nuevo modo solicitado
            context: Contexto actual
            
        Returns:
            Dict con información del cambio de modo
        """
        try:
            logger.info(f"[OrchestratorService] 🎯 FASE 10: Cambiando modo a '{new_mode}' para chat {chat_id}")
            
            # Aplicar límites del nuevo modo
            if new_mode == "rápido":
                # Modo rápido: límites más estrictos
                self.token_budget.MAX_INPUT_TOKENS = 4800  # 60% del original
                self.token_budget.MAX_HISTORY_TURNS = 3
                self.token_budget.MAX_SCHEMA_CHARS = 1800
                self.token_budget.TOP_K_DBS = 1
                self.token_budget.TOP_K_APPS = 1
                
            elif new_mode == "equilibrado":
                # Modo equilibrado: límites moderados
                self.token_budget.MAX_INPUT_TOKENS = 6400  # 80% del original
                self.token_budget.MAX_HISTORY_TURNS = 4
                self.token_budget.MAX_SCHEMA_CHARS = 2400
                self.token_budget.TOP_K_DBS = 2
                self.token_budget.TOP_K_APPS = 1
                
            elif new_mode == "preciso":
                # Modo preciso: límites originales
                self.token_budget.MAX_INPUT_TOKENS = 8000  # 100% del original
                self.token_budget.MAX_HISTORY_TURNS = 6
                self.token_budget.MAX_SCHEMA_CHARS = 3000
                self.token_budget.TOP_K_DBS = 2
                self.token_budget.TOP_K_APPS = 2
                
            else:
                raise ValueError(f"Modo no válido: {new_mode}")
            
            # Re-aplicar trimming con nuevos límites
            re_trimmed_context = self.token_budget.apply_intelligent_context_trimming(context)
            
            # Emitir confirmación del cambio
            await self.emit_notice_info(
                message=f"✅ Modo cambiado a '{new_mode}'. Límites ajustados para optimizar rendimiento.",
                level="success",
                actions=[
                    {"label": "Ver límites actuales", "action": "show_current_limits"},
                    {"label": "Cambiar modo nuevamente", "action": "change_mode_again"},
                    {"label": "Continuar", "action": "continue_with_new_mode"}
                ]
            )
            
            # Calcular tokens estimados con nuevo modo
            estimated_tokens = self.token_budget.estimate_tokens_for_context(re_trimmed_context)
            budget_usage = (estimated_tokens / self.token_budget.MAX_INPUT_TOKENS) * 100
            
            logger.info(f"[OrchestratorService] 🎯 FASE 10: Modo '{new_mode}' aplicado - {budget_usage:.1f}% de uso")
            
            return {
                "mode_changed": True,
                "new_mode": new_mode,
                "estimated_tokens": estimated_tokens,
                "budget_usage_percent": budget_usage,
                "context_optimized": True,
                "trimmed_context": re_trimmed_context
            }
            
        except Exception as e:
            logger.error(f"[OrchestratorService] ❌ Error cambiando modo de TokenBudget: {e}")
            await self.emit_error_user_facing(
                code="MODE_CHANGE_ERROR",
                human_message=f"No se pudo cambiar al modo '{new_mode}'. Usando configuración por defecto.",
                suggested_actions=[
                    "Intentar cambiar modo nuevamente",
                    "Continuar con modo actual",
                    "Contactar soporte si el problema persiste"
                ],
                technical_details=str(e)
            )
            
            return {
                "mode_changed": False,
                "error": str(e),
                "context_optimized": False
            }

    async def process_chat_message(self, chat_id: UUID, user_message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        🧠 Procesar mensaje de chat usando ReAct Orchestrator simplificado
        
        Args:
            chat_id: ID del chat
            user_message: Mensaje del usuario
            context: Contexto opcional
            
        Returns:
            Respuesta procesada con ReAct
        """
        try:
            start_time = time.time()
            logger.info(f"[OrchestratorService] 🧠 Iniciando ReAct para chat_id={chat_id}")
            
            # Crear ChatMessage para ReAct
            message = ChatMessage(
                content=user_message,
                role="user",
                chat_id=chat_id,
                user_id=self.user_id
            )
            
            # Extraer db_ids y app_ids del contexto si están disponibles
            db_ids = context.get("db_ids") if context else None
            app_ids = context.get("app_ids") if context else None
            explorer = context.get("explorer", False) if context else False
            
            # 🧠 Usar ReAct Orchestrator para procesar el mensaje
            react_response = await self.react_orchestrator.handle_message(
                chat_id=chat_id,
                message=message,
                db_ids=db_ids,
                app_ids=app_ids,
                explorer=explorer
            )
            
            # Calcular tiempo de ejecución
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            # Construir respuesta final compatible
            final_response = {
                "message": react_response.get("content", "Respuesta generada por ReAct"),
                "chat_id": str(chat_id),
                "assistant_response": react_response.get("content", "Respuesta generada por ReAct"),
                "execution_summary": {
                    "total_tokens": react_response.get("iterations", 0) * 100,  # Estimación
                    "execution_time_ms": execution_time_ms,
                    "steps_executed": react_response.get("iterations", 0),
                    "status": "completed",
                    "method": "react_hybrid"
                },
                "react_info": {
                    "iterations": react_response.get("iterations", 0),
                    "method": react_response.get("method", "react_hybrid"),
                    "source": react_response.get("source", "react_orchestrator"),
                    "history": react_response.get("react_history", [])
                }
            }
            
            # Añadir información de contexto si está disponible
            if react_response.get("context_used"):
                final_response["context_used"] = react_response["context_used"]
            
            logger.info(f"[OrchestratorService] ✅ ReAct completado en {execution_time_ms}ms, {react_response.get('iterations', 0)} iteraciones")
            return final_response
            
        except Exception as e:
            logger.exception(f"[OrchestratorService] ❌ Error en ReAct: {e}")
            
            # Respuesta de error simplificada
            error_response = {
                "message": "🤖 Error interno del sistema. Por favor, contacta soporte.",
                "chat_id": str(chat_id),
                "assistant_response": "🤖 Error interno del sistema. Por favor, contacta soporte.",
                "error": str(e),
                "status": "error",
                "execution_summary": {
                    "total_tokens": 0,
                    "execution_time_ms": 0,
                    "steps_executed": 0,
                    "status": "error"
                }
            }
            return error_response

