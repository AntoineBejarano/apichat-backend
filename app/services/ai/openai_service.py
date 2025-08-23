# app/services/openai_service.py
import json
import logging
import asyncio
import re
from uuid import UUID
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING, NamedTuple
from functools import lru_cache
import time
from datetime import datetime

from fastapi import HTTPException
from openai import OpenAI, RateLimitError
from pydantic import ValidationError
from langchain.output_parsers import PydanticOutputParser

from app.core.config import settings
from app.schemas.chat_schema import ChatMessage
from app.schemas.chat_history_schema import ChatHistoryOut
from app.models.function_model import Function
from app.utils.text import truncate_words
from app.schemas.plan_schema import PlanModel  # ✅ evitar ciclos
from app.utils.performance_monitor import monitor_performance

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────
#   Constantes de prompt
# ──────────────────────────────────────────────────────
PROMPT_SQL_HEADER = "### SQL Schema (read-only)"
PROMPT_SQL_DIALECT_HEADER = "### SQL Dialect"
PROMPT_FUNCTIONS_HEADER = "### Functions disponibles"
PROMPT_MCP_HEADER = "### MCP Tools disponibles"
PROMPT_APPS_HEADER = "### Aplicaciones disponibles"

# 🔒 CONTROL DE TOKENS - Presupuesto por llamada
MAX_INPUT_TOKENS = 8000  # Presupuesto sugerido para input
MAX_OUTPUT_TOKENS = 2048  # Cap de output tokens
MAX_HISTORY_TURNS = 6     # Máximo de turnos de historial (reducido de 8 a 6)
MAX_SCHEMA_CHARS = 8000   # Aumentado para mantener contexto completo
TOP_K_DBS = 2             # Top-K bases de datos
TOP_K_APPS = 2            # Top-K aplicaciones

# ──────────────────────────────────────────────────────
#   Helpers
# ──────────────────────────────────────────────────────
def _json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    return str(obj)

REACT_AGENT_SYSTEM_PROMPT=(
"Eres un agente ReAct (Reasoning + Acting) especializado en bases de datos y APIs. Tu objetivo es ANALIZAR la consulta del usuario y decidir la mejor estrategia.\n\n"
"🎯 REGLAS DE DECISIÓN:\n"
"1. EXPLORACIÓN DE ESQUEMA (responder directamente):\n"
"   - \"¿Qué tablas tiene mi DB?\" → Lista las tablas del esquema\n"
"   - \"¿Qué columnas tiene la tabla X?\" → Describe la estructura\n"
"   - \"¿Cómo se relacionan las tablas?\" → Explica las relaciones del esquema\n\n"
"2. EXPLORACIÓN DE DATOS (generar plan de ejecución):\n"
"   - \"¿Qué hay en la tabla X?\" → Genera plan para consultar datos\n"
"   - \"Muéstrame las invitaciones de clubs\" → Genera plan para obtener datos reales\n"
"   - \"¿Cuántos usuarios hay?\" → Genera plan para contar registros\n"
"   - \"Busca clubs en Madrid\" → Genera plan para filtrar datos\n\n"
"3. ACCIONES COMPLEJAS (generar plan de ejecución):\n"
"   - Cualquier consulta que requiera FILTRAR, BUSCAR, CONTAR, AGRUPAR datos\n"
"   - Consultas que combinen múltiples tablas\n"
"   - Operaciones que requieran lógica de negocio\n\n"
"🔧 CUANDO GENERAR PLAN:\n"
"- SIEMPRE que se requiera acceder a DATOS REALES (no solo esquema)\n"
"- SIEMPRE que se necesite FILTRAR, BUSCAR o ANALIZAR contenido\n"
"- SIEMPRE que se requiera EJECUTAR consultas SQL o llamadas a API\n\n"
"📋 FORMATO DEL PLAN:\n"
"- Usa `db_query` para consultas SQL\n"
"- Usa `api_function` para llamadas a funciones\n"
"- Usa `mcp_tool` para herramientas externas\n"
"- Cada acción debe tener `store_as` para guardar resultados\n"
"- La `assistant_response` debe usar placeholders {{variable}} para referenciar datos\n\n"
"🛡️ SEGURIDAD SQL:\n"
"- SOLO usa tablas/columnas del esquema proporcionado\n"
"- NUNCA uses SELECT * (proyecta columnas específicas)\n"
"- SIEMPRE añade LIMIT (≤20) para consultas de exploración\n"
"- Usa ORDER BY created_at DESC o id DESC cuando sea apropiado\n\n"
"💡 EJEMPLOS:\n"
"- Usuario: \"¿Qué tablas tiene mi DB?\" → Respuesta directa (esquema)\n"
"- Usuario: \"Muéstrame las invitaciones de clubs\" → Plan con db_query\n"
"- Usuario: \"¿Cuántos usuarios hay?\" → Plan con db_query\n"
"- Usuario: \"Busca clubs en Madrid\" → Plan con db_query\n\n"
"🎯 RECUERDA: Si la consulta requiere DATOS REALES, GENERA UN PLAN. Si solo requiere ESQUEMA, RESPONDE DIRECTAMENTE.\n\n"
"🚨 REGLA CRÍTICA: SIEMPRE usa la función `return_plan` para generar planes.\n"
"NUNCA escribas JSON directamente en el contenido del mensaje.\n"
"SOLO function_call con return_plan es válido.\n"
) 

PROMPT_SUFFIX=(
"---\n"
"🚨 INSTRUCCIÓN OBLIGATORIA:\n"
"SIEMPRE usa la función `return_plan` para responder.\n"
"NUNCA escribas JSON directamente en el contenido del mensaje.\n"
"NUNCA escribas texto explicativo sin usar la función.\n\n"
"📋 ESQUEMA REQUERIDO para return_plan:\n"
f"{json.dumps(PlanModel.model_json_schema(), default=_json_default, indent=2)}\n\n"
"✅ EJEMPLO CORRECTO: Usar function_call con return_plan\n"
"❌ EJEMPLO INCORRECTO: Escribir JSON en el contenido\n"
"🔒 OBLIGATORIO: Solo function_call, nada más."
)

# ──────────────────────────────────────────────────────
#   Hints de dialectos SQL
# ──────────────────────────────────────────────────────
_DIALECT_HINTS = {
    "postgresql": "Usa PostgreSQL syntax. Para LIMIT usa LIMIT, para OFFSET usa OFFSET.",
    "mysql": "Usa MySQL syntax. Para LIMIT usa LIMIT, para OFFSET usa LIMIT offset, count.",
    "sqlite": "Usa SQLite syntax. Para LIMIT usa LIMIT, para OFFSET usa LIMIT offset, count.",
    "oracle": "Usa Oracle syntax. Para LIMIT usa ROWNUM, para OFFSET usa OFFSET-FETCH.",
    "sqlserver": "Usa SQL Server syntax. Para LIMIT usa TOP, para OFFSET usa OFFSET-FETCH.",
}

def _extract_dialect(schema: Optional[str]) -> Optional[str]:
    """Extrae el dialecto SQL del schema si está anotado"""
    if not schema:
        return None
    
    dialect_patterns = {
        "postgresql": r"postgresql|postgres",
        "mysql": r"mysql|mariadb",
        "sqlite": r"sqlite",
        "oracle": r"oracle",
        "sqlserver": r"sqlserver|mssql"
    }
    
    for dialect, pattern in dialect_patterns.items():
        if re.search(pattern, schema, re.IGNORECASE):
            return dialect
    
    return None

class CompletionResult(NamedTuple):
    content: str
    token_count: int

class OpenAIService:
    RETURN_PLAN_FUNC: Dict[str, Any] = {
        "name": "return_plan",
        "description": "Devuelve un plan de acciones para resolver la consulta del usuario",
        "parameters": PlanModel.model_json_schema(),
    }

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_BASE,
        )
        self.model = settings.OPENAI_MODEL
        self.history_service = factory.get_chat_history_service()
        self.parser = PydanticOutputParser(pydantic_object=PlanModel)
        
        # Cache de prompts para optimizar
        self._prompt_cache = {}
        self._cache_ttl = 300  # 5 minutos
        
        # 🔒 CONTROL DE TOKENS - Token bucket para rate limiting
        self._token_bucket = {
            "tokens_used": 0,
            "window_start": time.time(),
            "window_size": 60,  # 1 minuto
            "max_tokens_per_window": 10000  # Límite de OpenAI
        }
        
        logger.info(f"[OpenAIService] Initialized with model={self.model}")

    # ──────────────────────────────────────────────────
    #   PLAN ACTIONS (OPTIMIZADO CON CONTROL DE TOKENS)
    # ──────────────────────────────────────────────────
    @monitor_performance("openai_plan_actions")
    async def plan_actions(
        self,
        chat_id: UUID,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        database_schemas: Optional[Dict[str, Any]] = None,  # Nuevo parámetro
        db_ids: Optional[List[UUID]] = None,  # Para el contexto enriquecido
        use_enriched_context: bool = True,  # Flag para usar contexto enriquecido
        app_descriptors_compact: Optional[str] = None,  # NUEVO: Descriptores de apps
    ) -> Dict[str, Any]:

        # Validar que user_message no sea None
        if not user_message:
            logger.error("[OpenAIService] ❌ user_message es None")
            return {
                "actions": [],
                "assistant_response": "Error: No se proporcionó mensaje del usuario."
            }

        # 🔒 CONTROL DE TOKENS: Verificar token bucket antes de proceder
        if not self._check_token_bucket():
            logger.warning("[OpenAIService] 🔒 Token bucket limitado - usando payload lite")
            return await self._plan_actions_with_lite_payload(
                chat_id, user_message, db_schema, available_functions, 
                available_mcp_tools, history, database_schemas, db_ids, 
                use_enriched_context, app_descriptors_compact
            )

        # ⚡ OPTIMIZACIÓN: Cache de prompts
        cache_key = self._generate_prompt_cache_key(
            db_schema, available_functions, available_mcp_tools, app_descriptors_compact
        )
        
        # 1) Contexto histórico (limitado para optimizar)
        if history is None:
            msgs = self.history_service.get_history(chat_id, limit=MAX_HISTORY_TURNS)
            history = [m.model_dump() for m in msgs]

        # 2) Construir contexto de esquema (SIMPLE - solo lista de tablas)
        if use_enriched_context and db_ids:
            logger.info(f"[OpenAIService] 📋 Usando lista simple de tablas para {len(db_ids)} DBs")
            try:
                # 🔧 Usar el nuevo sistema de cache detallado
                cache_service = self.factory.get_detailed_schema_cache_service()
                schemas = []
                for db_id in db_ids:
                    cache_entry = await cache_service.get_schema_cache(self.factory.user.id, db_id)
                    if cache_entry and cache_entry.compact:
                        schemas.append(f"-- DATABASE {db_id} --\n{cache_entry.compact}")
                
                db_schema = "\n\n".join(schemas) if schemas else "No hay esquemas disponibles"
                logger.info(f"[OpenAIService] ✨ Schema compacto generado: {len(db_schema)} caracteres")
            except Exception as e:
                logger.exception(f"[OpenAIService] ❌ Error generando lista de tablas: {e}")
                # Fallback al método tradicional
                use_enriched_context = False
        
        # Fallback: usar método tradicional si el enriquecido falla o está deshabilitado
        if not use_enriched_context:
            if database_schemas and not db_schema:
                logger.info(f"[OpenAIService] 🔍 Construyendo esquema desde cache: {len(database_schemas)} DBs")
                db_schema = self._build_schema_from_cache(database_schemas)
                logger.info(f"[OpenAIService] 📋 Esquema generado: {len(db_schema)} caracteres")
                logger.debug(f"[OpenAIService] 📋 Esquema completo: {db_schema}")
            elif database_schemas and db_schema:
                logger.info(f"[OpenAIService] 🔍 Usando esquema existente + cache: {len(database_schemas)} DBs")
                # Combinar esquema existente con cache
                cache_schema = self._build_schema_from_cache(database_schemas)
                db_schema = f"{db_schema}\n\n{cache_schema}"
            elif not database_schemas and db_schema:
                logger.info(f"[OpenAIService] 📋 Usando esquema existente: {len(db_schema)} caracteres")
            else:
                logger.warning(f"[OpenAIService] ⚠️ No hay esquema disponible")

        # 🔒 CONTROL DE TOKENS: Aplicar trimming dinámico antes de construir mensajes
        trimmed_context = self._apply_token_budget_trimming(
            history, db_schema, available_functions, available_mcp_tools, app_descriptors_compact
        )

        # 🔍 DETECTAR SI DEBE FORZARSE EL PLAN
        should_force_plan = self._should_force_plan(user_message.content, db_schema, available_functions)
        if should_force_plan:
            logger.info("[OpenAIService] 🔍 Forzando generación de plan por intención de base de datos")
        
        # 3) Construcción de mensajes optimizada
        messages = [
            {
                "role": "system",
                "content": self._get_cached_or_build_prompt(
                    cache_key, trimmed_context["db_schema"], trimmed_context["functions"], 
                    trimmed_context["mcp_tools"], trimmed_context["app_descriptors"]
                ),
            },
            *trimmed_context["history"],
            user_message.model_dump(),
        ]

        # 🔒 CONTROL DE TOKENS: Estimar tokens antes de la llamada
        estimated_tokens = self._estimate_tokens_for_messages(messages)
        context_tokens = self._estimate_tokens_for_context(
            trimmed_context["history"], 
            trimmed_context["db_schema"], 
            trimmed_context["functions"], 
            trimmed_context["mcp_tools"], 
            trimmed_context["app_descriptors"]
        )
        
        # 📊 TELEMETRÍA ÚTIL
        logger.info(f"[OpenAIService] 🔍 Tokens estimados: mensajes={estimated_tokens}, contexto_total={context_tokens}")
        logger.info(f"[OpenAIService] 📊 Métricas de trimming: hist_turns={len(trimmed_context['history'])}, schema_chars={len(trimmed_context['db_schema']) if trimmed_context['db_schema'] else 0}, functions={len(trimmed_context['functions'])}, mcp_tools={len(trimmed_context['mcp_tools'].get('tools', [])) if trimmed_context['mcp_tools'] else 0}")
        
        if estimated_tokens > MAX_INPUT_TOKENS:
            logger.warning(f"[OpenAIService] 🔒 Tokens estimados ({estimated_tokens}) exceden límite ({MAX_INPUT_TOKENS}) - usando payload lite")
            return await self._plan_actions_with_lite_payload(
                chat_id, user_message, db_schema, available_functions, 
                available_mcp_tools, history, database_schemas, db_ids, 
                use_enriched_context, app_descriptors_compact
            )

        logger.info("[OpenAIService] 📝 Generando plan (msgs=%d)", len(messages))
        logger.debug("🔹 Contexto → %s", truncate_words(str(messages), 60))

        # ⚡ OPTIMIZACIÓN: Payload optimizado
        payload = {
            "model": self.model,
            "functions": [self.RETURN_PLAN_FUNC],
            "function_call": {"name": "return_plan"},  # 🔒 FORZAR uso de la función
            "temperature": settings.OPENAI_TEMPERATURE,
            "messages": messages,
            "max_tokens": MAX_OUTPUT_TOKENS,  # Usar constante de control de tokens
            "stream": False,  # Desactivar streaming para respuestas más rápidas
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

        # 🔒 CONTROL DE TOKENS: Actualizar token bucket
        self._update_token_bucket(estimated_tokens)

        # 3) Llamada asíncrona con retry inteligente
        resp = await self._call_openai_with_retry(safe)

        # 📊 TELEMETRÍA Y REGISTRO DE USO
        actual_prompt_tokens = resp.usage.prompt_tokens
        actual_completion_tokens = resp.usage.completion_tokens
        
        logger.info(f"[OpenAIService] 📊 Tokens reales vs estimados: prompt={actual_prompt_tokens}/{estimated_tokens} ({((actual_prompt_tokens/estimated_tokens)*100):.1f}%), completion={actual_completion_tokens}")
        
        # 🔒 ACTUALIZAR TOKEN BUCKET con tokens reales
        self._update_token_bucket(actual_prompt_tokens + actual_completion_tokens)
        
        # 📊 TELEMETRÍA AVANZADA
        logger.info(f"[OpenAIService] 📊 Métricas de rendimiento: trim_levels=completo, hist_turns_used={len(trimmed_context['history'])}, schema_chars_used={len(trimmed_context['db_schema']) if trimmed_context['db_schema'] else 0}, functions_used={len(trimmed_context['functions'])}, mcp_tools_used={len(trimmed_context['mcp_tools'].get('tools', [])) if trimmed_context['mcp_tools'] else 0}")
        logger.info(f"[OpenAIService] 📊 Control de tokens: bucket_available={self._token_bucket['max_tokens_per_window'] - self._token_bucket['tokens_used']}, force_plan={should_force_plan}")
        
        self.factory.get_usage_service().register_token_usage(
            model=self.model,
            prompt_tokens=actual_prompt_tokens,
            completion_tokens=actual_completion_tokens,
        )

        choice = resp.choices[0]
        function_call = getattr(choice.message, "function_call", None)
        content = (choice.message.content or "").strip()

        # 4) Interpretación de la respuesta
        if function_call:
            args_raw = function_call.arguments or "{}"
            try:
                plan_obj = self.parser.parse(args_raw)
                logger.info("[OpenAIService] ✅ Plan validado (%d acciones)", len(plan_obj.actions))
                return plan_obj.model_dump()
            except ValidationError as ve:
                logger.error("❌ Plan inválido: %s", ve)
                raise HTTPException(500, "Plan devuelto no es válido")

        if content:
            logger.info("[OpenAIService] ✅ Respuesta simple generada")
            
            # 🔧 NUEVO: Detectar si es una consulta de exploración de base de datos
            if self._is_database_exploration_query(user_message.content):
                logger.info("[OpenAIService] 🔍 Detectada consulta de exploración - generando respuesta directa")
                exploration_response = self._generate_database_exploration_response(user_message.content, db_schema)
                return {"actions": [], "assistant_response": exploration_response}
            
            return {"actions": [], "assistant_response": content}

        logger.warning("[OpenAIService] ⚠️ Sin respuesta del modelo")
        return {
            "actions": [],
            "assistant_response": (
                "Disculpa, no he entendido tu mensaje. ¿Podrías reformularlo?"
            ),
        }

    # ──────────────────────────────────────────────────
    #   CHAT COMPLETION (OPTIMIZADO)
    # ──────────────────────────────────────────────────
    @monitor_performance("openai_chat_completion")
    async def chat_completion(
        self,
        chat_id: UUID,
        system_prompt: str,
        user_message: ChatMessage,
    ) -> CompletionResult:

        # ⚡ OPTIMIZACIÓN: Historial limitado
        history = self.history_service.get_history(chat_id, limit=MAX_HISTORY_TURNS)
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            *[ChatHistoryOut.model_validate(m).model_dump() for m in history],
            user_message.model_dump(),
        ]

        # 🔒 CONTROL DE TOKENS: Estimar tokens antes de la llamada
        estimated_tokens = self._estimate_tokens_for_messages(messages)
        logger.info(f"[OpenAIService] 🔍 Tokens estimados para chat: {estimated_tokens}")
        
        if estimated_tokens > MAX_INPUT_TOKENS:
            logger.warning(f"[OpenAIService] 🔒 Tokens estimados ({estimated_tokens}) exceden límite ({MAX_INPUT_TOKENS}) - usando payload lite")
            messages = self._apply_lite_trimming_to_messages(messages)

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.OPENAI_TEMPERATURE,
            "max_tokens": MAX_OUTPUT_TOKENS,  # Usar constante de control de tokens
            "stream": False,  # Desactivar streaming
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

        # 🔒 CONTROL DE TOKENS: Actualizar token bucket
        self._update_token_bucket(estimated_tokens)

        # ⚡ OPTIMIZACIÓN: Llamada con retry
        resp = await self._call_openai_with_retry(safe)

        self.factory.get_usage_service().register_token_usage(
            model=self.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
        )

        choice = resp.choices[0]
        return CompletionResult(
            content=choice.message.content or "",
            token_count=resp.usage.total_tokens,
        )

    # ──────────────────────────────────────────────────
    #   MÉTODOS DE OPTIMIZACIÓN Y CONTROL DE TOKENS
    # ──────────────────────────────────────────────────
    async def _call_openai_with_retry(self, payload: Dict[str, Any], max_retries: int = 3):
        """Llamada a OpenAI con retry automático e inteligente para errores 429"""
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, lambda: self.client.chat.completions.create(**payload)
                )
            except RateLimitError as e:
                # 🔒 FALLBACK INTELIGENTE: Detectar si es error de tokens
                if self._is_token_rate_limit_error(e):
                    logger.warning(f"[OpenAIService] 🔒 Error 429 por tokens - no reintentar con mismo payload")
                    if attempt == 0:  # Solo un reintento con payload lite
                        logger.info("[OpenAIService] 🔄 Reintentando con payload lite...")
                        lite_payload = self._build_lite_payload(payload)
                        
                        # 🔒 ACTUALIZAR TOKEN BUCKET para el payload lite
                        lite_tokens = self._estimate_tokens_for_messages(lite_payload.get("messages", []))
                        self._update_token_bucket(lite_tokens)
                        
                        # 📊 TELEMETRÍA DE FALLBACK
                        logger.info(f"[OpenAIService] 📊 Fallback a payload lite: {lite_tokens} tokens vs {self._estimate_tokens_for_messages(payload.get('messages', []))} original")
                        
                        try:
                            return await loop.run_in_executor(
                                None, lambda: self.client.chat.completions.create(**lite_payload)
                            )
                        except Exception as lite_error:
                            logger.error(f"[OpenAIService] ❌ Error con payload lite: {lite_error}")
                            # Fallback final: mensaje controlado al usuario
                            raise HTTPException(
                                429, 
                                "Estoy reduciendo contexto para cumplir límites. Un momento..."
                            )
                    else:
                        # Ya se intentó con payload lite, no reintentar más
                        raise HTTPException(
                            429, 
                            "Límite de tokens excedido. Por favor, reformula tu consulta de manera más específica."
                        )
                else:
                    # Error 429 no relacionado con tokens - aplicar backoff normal
                    if attempt == max_retries - 1:
                        logger.error(f"[OpenAIService] ❌ Error después de {max_retries} intentos: {e}")
                        raise HTTPException(500, f"Error en OpenAI: {str(e)}")
                    
                    wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                    logger.warning(f"[OpenAIService] ⚠️ Intento {attempt + 1} falló, reintentando en {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[OpenAIService] ❌ Error después de {max_retries} intentos: {e}")
                    raise HTTPException(500, f"Error en OpenAI: {str(e)}")
                
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                logger.warning(f"[OpenAIService] ⚠️ Intento {attempt + 1} falló, reintentando en {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

    def _is_token_rate_limit_error(self, error: RateLimitError) -> bool:
        """Detecta si el error 429 es por límite de tokens"""
        try:
            error_message = str(error)
            # Detectar patrones de error de tokens
            token_patterns = [
                "Request too large",
                "tokens must be reduced",
                "input or output tokens must be reduced",
                "Limit",
                "Requested"
            ]
            return any(pattern.lower() in error_message.lower() for pattern in token_patterns)
        except:
            return False

    def _build_lite_payload(self, original_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Construye un payload lite para evitar exceder límites de tokens"""
        logger.info("[OpenAIService] 🔒 Construyendo payload lite para control de tokens")
        
        lite_payload = original_payload.copy()
        
        # 1. Limitar historial a últimos turnos
        messages = original_payload.get("messages", [])
        if len(messages) > MAX_HISTORY_TURNS + 2:  # +2 para system y user message
            # Mantener system message, user message y últimos turnos de historial
            system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
            user_msg = messages[-1] if messages else None
            
            if system_msg and user_msg:
                # Obtener últimos turnos de historial (excluyendo system y user)
                history_messages = messages[1:-1]
                limited_history = history_messages[-MAX_HISTORY_TURNS:]
                
                lite_payload["messages"] = [system_msg] + limited_history + [user_msg]
                logger.info(f"[OpenAIService] 🔒 Historial recortado: {len(history_messages)} → {len(limited_history)} turnos")
        
        # 2. Limitar max_tokens de salida
        lite_payload["max_tokens"] = min(original_payload.get("max_tokens", MAX_OUTPUT_TOKENS), 1024)
        
        # 3. Reducir temperature para respuestas más concisas
        lite_payload["temperature"] = min(original_payload.get("temperature", 0.7), 0.3)
        
        # 4. 🔒 TRIMMING ADICIONAL DEL SYSTEM PROMPT si es muy largo
        system_message = lite_payload.get("messages", [{}])[0] if lite_payload.get("messages") else {}
        if system_message.get("role") == "system" and len(system_message.get("content", "")) > 2000:
            original_content = system_message["content"]
            # Mantener solo las instrucciones esenciales
            essential_parts = [
                "Actúa como un asistente que decide entre responder directamente o generar un plan JSON",
                "Para consultas de exploración: responde directamente sin plan",
                "Si requiere acceder a datos: genera plan con return_plan",
                "Usa placeholders {{variable}} en assistant_response"
            ]
            system_message["content"] = "\n".join(essential_parts)
            logger.info(f"[OpenAIService] 🔒 System prompt recortado: {len(original_content)} → {len(system_message['content'])} caracteres")
        
        # 5. 🔍 VERIFICAR TOKENS DEL PAYLOAD LITE
        lite_tokens = self._estimate_tokens_for_messages(lite_payload.get("messages", []))
        logger.info(f"[OpenAIService] 🔒 Payload lite construido: {lite_tokens} tokens estimados")
        
        return lite_payload

    def _generate_prompt_cache_key(
        self, 
        db_schema: Optional[str], 
        functions: List[Function], 
        mcp_tools: Optional[dict],
        app_descriptors_compact: Optional[str] = None
    ) -> str:
        """Genera clave única para cache de prompts"""
        function_ids = [str(f.id) for f in functions]
        mcp_tool_names = list(mcp_tools.get("tools", [])) if mcp_tools else []
        
        return f"{hash(db_schema)}_{hash(tuple(function_ids))}_{hash(tuple(mcp_tool_names))}_{hash(app_descriptors_compact)}"

    def _get_cached_or_build_prompt(
        self, 
        cache_key: str, 
        db_schema: Optional[str], 
        functions: List[Function], 
        mcp_tools: Optional[dict],
        app_descriptors_compact: Optional[str] = None
    ) -> str:
        """Obtiene prompt desde cache o lo construye"""
        current_time = time.time()
        
        # Verificar cache
        if cache_key in self._prompt_cache:
            cached_prompt, timestamp = self._prompt_cache[cache_key]
            if current_time - timestamp < self._cache_ttl:
                logger.debug("[OpenAIService] 📋 Usando prompt cacheado")
                return cached_prompt
        
        # Construir nuevo prompt
        prompt = self._build_combined_planner_prompt(db_schema, functions, mcp_tools, app_descriptors_compact)
        
        # Guardar en cache
        self._prompt_cache[cache_key] = (prompt, current_time)
        
        # Limpiar cache si es muy grande
        if len(self._prompt_cache) > 50:
            self._prompt_cache.clear()
            logger.debug("[OpenAIService] 🧹 Cache de prompts limpiado")
        
        return prompt

    def _build_schema_from_cache(self, database_schemas: Dict[str, Any]) -> str:
        """Construir esquema de BD desde el cache"""
        if not database_schemas:
            return ""
        
        schema_parts = []
        schema_parts.append("-- ESQUEMA DE BASE DE DATOS DISPONIBLE")
        schema_parts.append("-- ⚠️ SOLO usa las columnas que aparecen en este esquema")
        schema_parts.append("-- 🔍 USA SIEMPRE búsquedas flexibles (LIKE/ILIKE) para nombres y ubicaciones")
        schema_parts.append("-- 📋 VALIDA SIEMPRE las columnas antes de escribir SQL")
        schema_parts.append("")
        
        for db_id, tables in database_schemas.items():
            if tables:
                schema_parts.append(f"-- Database: {db_id}")
                schema_parts.append("")
                for table in tables:
                    table_name = table.get("name", "unknown")
                    columns = table.get("columns", [])
                    
                    if columns:
                        column_defs = []
                        column_list = []
                        for col in columns:
                            col_name = col.get("name", "unknown")
                            col_type = col.get("type", "TEXT")
                            nullable = "NOT NULL" if not col.get("nullable", True) else ""
                            primary_key = "PRIMARY KEY" if col.get("primary_key", False) else ""
                            
                            parts = [col_name, col_type]
                            if nullable:
                                parts.append(nullable)
                            if primary_key:
                                parts.append(primary_key)
                            
                            column_defs.append("  " + " ".join(parts))
                            column_list.append(col_name)
                        
                        schema_parts.append(f"-- Tabla: {table_name}")
                        schema_parts.append(f"-- Columnas disponibles: {', '.join(column_list)}")
                        schema_parts.append(f"CREATE TABLE {table_name} (")
                        schema_parts.append(",\n".join(column_defs))
                        schema_parts.append(");")
                        
                        # Generar ejemplos de búsquedas flexibles dinámicamente
                        schema_parts.append("")
                        schema_parts.append("-- EJEMPLOS DE BÚSQUEDAS FLEXIBLES PARA ESTA TABLA:")
                        
                        # Buscar columnas que podrían contener nombres o identificadores
                        name_columns = [col for col in column_list if any(keyword in col.lower() for keyword in ['name', 'title', 'nombre', 'titulo', 'nom', 'tit'])]
                        location_columns = [col for col in column_list if any(keyword in col.lower() for keyword in ['address', 'location', 'city', 'ciudad', 'direccion', 'ubicacion', 'addr', 'loc', 'place', 'lugar'])]
                        description_columns = [col for col in column_list if any(keyword in col.lower() for keyword in ['description', 'desc', 'descripcion', 'comentario', 'comment', 'notes', 'notas', 'info'])]
                        id_columns = [col for col in column_list if col.lower() == 'id' or 'id' in col.lower()]
                        email_columns = [col for col in column_list if any(keyword in col.lower() for keyword in ['email', 'mail', 'correo', 'e-mail'])]
                        phone_columns = [col for col in column_list if any(keyword in col.lower() for keyword in ['phone', 'telefono', 'tel', 'mobile', 'movil'])]
                        
                        # Ejemplos de búsquedas por nombre
                        if name_columns:
                            name_col = name_columns[0]
                            schema_parts.append(f"-- ✅ Buscar por {name_col} (búsqueda flexible):")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {name_col} LIKE '%valor%'")
                        
                        # Ejemplos de búsquedas por ubicación
                        if location_columns:
                            location_col = location_columns[0]
                            schema_parts.append(f"-- ✅ Buscar por ubicación en {location_col}:")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {location_col} LIKE '%ciudad%'")
                        
                        # Ejemplos de búsquedas por descripción
                        if description_columns:
                            desc_col = description_columns[0]
                            schema_parts.append(f"-- ✅ Buscar por descripción en {desc_col}:")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {desc_col} LIKE '%texto%'")
                        
                        # Ejemplos de búsquedas por email
                        if email_columns:
                            email_col = email_columns[0]
                            schema_parts.append(f"-- ✅ Buscar por email en {email_col}:")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {email_col} LIKE '%@dominio.com%'")
                        
                        # Ejemplos de búsquedas combinadas
                        if name_columns and location_columns:
                            name_col = name_columns[0]
                            location_col = location_columns[0]
                            schema_parts.append(f"-- ✅ Combinar búsquedas:")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {name_col} LIKE '%nombre%' AND {location_col} LIKE '%ubicacion%'")
                        
                        # Ejemplo genérico si no hay columnas específicas
                        if not (name_columns or location_columns or description_columns or email_columns) and len(column_list) > 0:
                            first_col = column_list[0]
                            schema_parts.append(f"-- ✅ Buscar por {first_col}:")
                            schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {first_col} LIKE '%valor%'")
                            if len(column_list) > 1:
                                second_col = column_list[1]
                                schema_parts.append(f"-- ✅ Buscar por {second_col}:")
                                schema_parts.append(f"--    SELECT * FROM {table_name} WHERE {second_col} LIKE '%valor%'")
                        
                        schema_parts.append("")
                        schema_parts.append("-- ⚠️ IMPORTANTE: Solo usa las columnas listadas arriba")
                        schema_parts.append("")
                    else:
                        schema_parts.append(f"-- Table: {table_name} (no schema available)")
                        schema_parts.append("")
        
        return "\n".join(schema_parts)

    # ──────────────────────────────────────────────────
    #   Prompt builder (OPTIMIZADO)
    # ──────────────────────────────────────────────────
    def _build_combined_planner_prompt(
        self,
        db_schema: Optional[str],
        functions: List[Function],
        mcp_tools: Optional[dict],
        app_descriptors_compact: Optional[str] = None,
    ) -> str:

        parts: List[str] = [REACT_AGENT_SYSTEM_PROMPT.strip()]

        # Extraer dialecto del schema (si viene anotado)
        dialect = _extract_dialect(db_schema)
        if dialect:
            logger.info("[OpenAIService] 🎛️ Dialecto detectado en schema: %s", dialect)
            hint = _DIALECT_HINTS.get(dialect, f"Usa SQL válido para {dialect}.")
            parts.append(f"{PROMPT_SQL_DIALECT_HEADER}\nDialect: {dialect}\n{hint}")

        # Prompt del agente (si existe)
        try:
            agent_prompt = self.factory.get_agent_service().get_prompt_from_history()
            if agent_prompt:
                parts.append(agent_prompt.strip())
        except Exception as e:
            logger.warning("⚠️ No se pudo obtener prompt de agente: %s", e)

        # Esquema SQL (optimizado inteligentemente)
        if db_schema:
            # 🎯 OPTIMIZACIÓN INTELIGENTE: Priorizar tablas relevantes para la consulta
            try:
                # 🔧 Obtener el mensaje del usuario del contexto actual
                user_message = ""
                if hasattr(self, '_current_user_message'):
                    user_message = self._current_user_message
                elif hasattr(self, '_last_user_message'):
                    user_message = self._last_user_message
                
                # 🧹 SIEMPRE limpiar el schema, incluso sin user_message
                optimized_schema = self._optimize_schema_for_query(db_schema, user_message)
                parts.append(f"{PROMPT_SQL_HEADER}\n{optimized_schema}")
                logger.info(f"[OpenAIService] 🎯 Schema optimizado y LIMPIO aplicado: {len(db_schema)} → {len(optimized_schema)} caracteres")
            except Exception as e:
                logger.warning(f"[OpenAIService] ⚠️ Error en optimización de schema, usando truncado básico: {e}")
                # Fallback al método anterior
                truncated_schema = db_schema[:MAX_SCHEMA_CHARS]
                parts.append(f"{PROMPT_SQL_HEADER}\n{truncated_schema}")

        # Funciones disponibles (limitado)
        if functions:
            # ⚡ OPTIMIZACIÓN: Limitar número de funciones mostradas
            limited_functions = functions[:TOP_K_APPS]  # Máximo 10 funciones
            fx = [f"• {f.name}: {truncate_words(f.description or '', 10)}"  # Reducido de 12 a 10
                  for f in limited_functions]
            parts.append(f"{PROMPT_FUNCTIONS_HEADER}\n" + "\n".join(fx))

        # Herramientas MCP (limitado)
        if mcp_tools and mcp_tools.get("tools"):
            # ⚡ OPTIMIZACIÓN: Limitar número de herramientas
            limited_tools = mcp_tools["tools"][:3]  # Máximo 5 herramientas
            tl = [f"• {t['name']}: {t.get('description', '')[:50]}"  # Limitar descripción
                  for t in limited_tools]
            parts.append(f"{PROMPT_MCP_HEADER}\n" + "\n".join(tl))

        # 🆕 Descriptores de aplicaciones
        if app_descriptors_compact:
            parts.append(f"{PROMPT_APPS_HEADER}\n{app_descriptors_compact}")

        parts.append(PROMPT_SUFFIX)
        return "\n\n".join(parts)

    def _is_database_exploration_query(self, user_message: str) -> bool:
        """
        Detecta si el mensaje del usuario es SOLO exploración de esquema.
        Estas consultas se responden directamente sin generar un plan.
        
        IMPORTANTE: Si la consulta también requiere datos reales, NO es solo exploración.
        """
        # Palabras clave que indican SOLO exploración de esquema
        pure_exploration_keywords = [
            "qué tablas", "que tablas", "tablas que", "tablas disponibles",
            "qué tablas tiene", "que tablas tiene", "tablas de mi", "tablas en mi",
            "estructura de", "esquema de", "schema de", "columnas de",
            "qué columnas", "que columnas", "campos de", "campos disponibles",
            "describe", "muestra", "listar", "enumerar", "cuáles son",
            "cuáles tablas", "cuales tablas", "cómo se relacionan", "como se relacionan",
            "relaciones entre", "relación entre", "conectan", "conecta"
        ]
        
        # Palabras clave que indican que se requieren DATOS REALES
        data_requirement_keywords = [
            "dónde puedo ver", "donde puedo ver", "muéstrame", "muestrame", "dame",
            "obtén", "obten", "consulta", "busca", "encuentra", "cuántos", "cuantos",
            "cuántas", "cuantas", "qué hay", "que hay", "datos de", "información de",
            "registros de", "filas de", "resultados de", "invitaciones", "clubs",
            "usuarios", "contenido", "valores", "ejemplos"
        ]
        
        user_lower = user_message.lower()
        
        # Si contiene palabras de exploración PURA (sin datos)
        has_pure_exploration = any(keyword in user_lower for keyword in pure_exploration_keywords)
        
        # Si contiene palabras que requieren datos reales
        requires_data = any(keyword in user_lower for keyword in data_requirement_keywords)
        
        # Es solo exploración si NO requiere datos reales
        is_pure_exploration = has_pure_exploration and not requires_data
        
        logger.info(f"[OpenAIService] 🔍 Análisis de consulta: pure_exploration={has_pure_exploration}, requires_data={requires_data}, is_pure_exploration={is_pure_exploration}")
        
        return is_pure_exploration

    def _should_force_plan(self, user_message: str, db_schema: Optional[str], available_functions: List[Function]) -> bool:
        """
        Determina si se debe forzar la generación de un plan basado en el contexto.
        Reglas:
        - Si hay intención de db_read y db_schema presente → forzar plan
        - Si hay funciones disponibles y la consulta requiere acciones → forzar plan
        - Si es solo exploración o charla → no forzar plan
        """
        try:
            user_lower = user_message.lower()
            
            # 1. Detectar intención de lectura de base de datos
            db_read_keywords = [
                "muéstrame", "muestrame", "dame", "obtén", "obten", "consulta", "busca", "encuentra",
                "cuántos", "cuantos", "cuántas", "cuantas", "cuál es", "cual es", "qué hay", "que hay",
                "datos de", "información de", "registros de", "filas de", "resultados de"
            ]
            
            has_db_read_intent = any(keyword in user_lower for keyword in db_read_keywords)
            
            # 2. Detectar si requiere acciones (funciones)
            action_keywords = [
                "ejecuta", "ejecutar", "llama", "llamar", "invoca", "invocar", "usa", "usar",
                "aplica", "aplicar", "procesa", "procesar", "calcula", "calcular", "genera", "generar"
            ]
            
            requires_actions = any(keyword in user_lower for keyword in action_keywords)
            
            # 3. Reglas de decisión
            if has_db_read_intent and db_schema:
                logger.info("[OpenAIService] 🔍 Intención de lectura de DB detectada - forzando plan")
                return True
            
            if requires_actions and available_functions:
                logger.info("[OpenAIService] 🔍 Acciones requeridas detectadas - forzando plan")
                return True
            
            # 4. Excepciones: consultas de exploración
            if self._is_database_exploration_query(user_message):
                logger.info("[OpenAIService] 🔍 Consulta de exploración detectada - NO forzando plan")
                return False
            
            # 5. Por defecto, no forzar plan para charla simple
            logger.info("[OpenAIService] 🔍 Consulta simple detectada - NO forzando plan")
            return False
            
        except Exception as e:
            logger.warning(f"[OpenAIService] ⚠️ Error detectando si forzar plan: {e}")
            return False  # Por defecto, no forzar

    def _generate_database_exploration_response(self, user_message: str, db_schema: Optional[str]) -> str:
        """
        Genera una respuesta directa para consultas de exploración de base de datos.
        Lista tablas, confirma existencia y proporciona información útil.
        """
        try:
            if not db_schema:
                return "No tengo acceso al esquema de la base de datos en este momento. ¿Podrías especificar qué información necesitas?"
            
            # Extraer información de tablas del esquema
            tables_info = self._extract_tables_from_schema(db_schema)
            
            if not tables_info:
                return "No pude extraer información de las tablas del esquema proporcionado."
            
            # Construir respuesta estructurada
            response_parts = []
            
            # Detectar si el usuario pregunta por una tabla específica
            user_lower = user_message.lower()
            specific_table = None
            for table_name in tables_info.keys():
                if table_name.lower() in user_lower:
                    specific_table = table_name
                    break
            
            if specific_table:
                # Confirmar tabla específica
                table_info = tables_info[specific_table]
                response_parts.append(f"✅ **Confirmado**: La tabla `{specific_table}` existe en tu base de datos.")
                
                if table_info.get('columns'):
                    response_parts.append(f"\n📋 **Columnas disponibles**: {', '.join(table_info['columns'])}")
                
                if table_info.get('row_count'):
                    response_parts.append(f"\n📊 **Registros**: {table_info['row_count']} filas")
                
                response_parts.append(f"\n💡 **Ejemplo de consulta**: `SELECT * FROM {specific_table} LIMIT 5`")
            
            else:
                # Listar todas las tablas
                response_parts.append("📋 **Tablas disponibles en tu base de datos**:")
                
                for table_name, table_info in tables_info.items():
                    table_desc = f"• `{table_name}`"
                    if table_info.get('columns'):
                        table_desc += f" ({len(table_info['columns'])} columnas)"
                    if table_info.get('row_count'):
                        table_desc += f" - {table_info['row_count']} registros"
                    response_parts.append(table_desc)
                
                response_parts.append(f"\n💡 **Total**: {len(tables_info)} tablas disponibles")
                response_parts.append("\n🔍 **Para explorar una tabla específica**, puedes preguntar por su nombre o contenido.")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"[OpenAIService] ❌ Error generando respuesta de exploración: {e}")
            return "Disculpa, tuve un problema generando la información de la base de datos. ¿Podrías reformular tu pregunta?"

    def _extract_tables_from_schema(self, db_schema: str) -> Dict[str, Dict[str, Any]]:
        """
        Extrae información estructurada de las tablas del esquema de base de datos.
        """
        tables_info = {}
        
        try:
            # Buscar patrones de tablas en el esquema
            import re
            
            # Patrón para encontrar definiciones de tablas
            table_pattern = r'--\s*Table:\s*(\w+)\s*(?:\(([^)]+)\))?'
            matches = re.findall(table_pattern, db_schema, re.IGNORECASE)
            
            for table_name, table_details in matches:
                table_info = {
                    'name': table_name,
                    'columns': [],
                    'row_count': None,
                    'description': table_details.strip() if table_details else None
                }
                
                # Buscar columnas en el esquema
                column_pattern = rf'--\s*{table_name}.*?--\s*Columns:(.*?)(?:--|$)'
                column_match = re.search(column_pattern, db_schema, re.DOTALL | re.IGNORECASE)
                
                if column_match:
                    columns_text = column_match.group(1)
                    # Extraer nombres de columnas
                    column_names = re.findall(r'(\w+):', columns_text)
                    table_info['columns'] = column_names
                
                # Buscar información de conteo de filas
                count_pattern = rf'--\s*{table_name}.*?(\d+)\s*rows?'
                count_match = re.search(count_pattern, db_schema, re.IGNORECASE)
                if count_match:
                    table_info['row_count'] = int(count_match.group(1))
                
                tables_info[table_name] = table_info
            
            # Si no se encontraron tablas con el patrón, intentar extraer de manera más simple
            if not tables_info:
                # Buscar líneas que contengan "Table:" o "CREATE TABLE"
                lines = db_schema.split('\n')
                for line in lines:
                    if 'table:' in line.lower() or 'create table' in line.lower():
                        # Extraer nombre de tabla
                        table_match = re.search(r'(\w+)', line, re.IGNORECASE)
                        if table_match:
                            table_name = table_match.group(1)
                            if table_name not in tables_info:
                                tables_info[table_name] = {
                                    'name': table_name,
                                    'columns': [],
                                    'row_count': None,
                                    'description': 'Información limitada disponible'
                                }
            
            logger.info(f"[OpenAIService] 🔍 Extraídas {len(tables_info)} tablas del esquema")
            return tables_info
            
        except Exception as e:
            logger.error(f"[OpenAIService] ❌ Error extrayendo tablas del esquema: {e}")
            return {}

    def _apply_token_budget_trimming(
        self, 
        history: List[Dict[str, Any]], 
        db_schema: Optional[str], 
        functions: List[Function], 
        mcp_tools: Optional[dict], 
        app_descriptors: Optional[str]
    ) -> Dict[str, Any]:
        """Aplica trimming dinámico basado en presupuesto de tokens de forma inteligente"""
        trimmed_context = {
            "history": history,
            "db_schema": db_schema,
            "functions": functions,
            "mcp_tools": mcp_tools,
            "app_descriptors": app_descriptors
        }
        
        # 🔍 ESTIMAR TOKENS INICIALES
        initial_tokens = self._estimate_tokens_for_context(
            history, db_schema, functions, mcp_tools, app_descriptors
        )
        logger.info(f"[OpenAIService] 🔍 Tokens iniciales estimados: {initial_tokens}")
        
        # Si ya está dentro del presupuesto, no hacer trimming
        if initial_tokens <= MAX_INPUT_TOKENS:
            logger.info(f"[OpenAIService] ✅ Contexto dentro del presupuesto ({initial_tokens} ≤ {MAX_INPUT_TOKENS})")
            return trimmed_context
        
        logger.warning(f"[OpenAIService] 🔒 Contexto excede presupuesto ({initial_tokens} > {MAX_INPUT_TOKENS}) - aplicando trimming inteligente")
        
        # 🔒 NIVEL 1: Trimming básico
        # 1. Limitar historial a últimos turnos
        if len(history) > MAX_HISTORY_TURNS:
            trimmed_context["history"] = history[-MAX_HISTORY_TURNS:]
            logger.info(f"[OpenAIService] 🔒 Historial recortado: {len(history)} → {len(trimmed_context['history'])} turnos")
        
        # 2. Limitar schema a caracteres máximos
        if db_schema and len(db_schema) > MAX_SCHEMA_CHARS:
            trimmed_context["db_schema"] = db_schema[:MAX_SCHEMA_CHARS] + "\n\n... (schema truncado por límite de tokens)"
            logger.info(f"[OpenAIService] 🔒 Schema recortado: {len(db_schema)} → {MAX_SCHEMA_CHARS} caracteres")
        
        # 3. Limitar funciones a TOP-K
        if len(functions) > TOP_K_APPS:
            trimmed_context["functions"] = functions[:TOP_K_APPS]
            logger.info(f"[OpenAIService] 🔒 Funciones limitadas: {len(functions)} → {len(trimmed_context['functions'])}")
        
        # 4. Limitar herramientas MCP
        if mcp_tools and mcp_tools.get("tools") and len(mcp_tools["tools"]) > 3:
            trimmed_context["mcp_tools"] = {
                "tools": mcp_tools["tools"][:3]
            }
            logger.info(f"[OpenAIService] 🔒 MCP tools limitadas: {len(mcp_tools['tools'])} → 3")
        
        # 🔍 VERIFICAR SI EL TRIMMING BÁSICO ES SUFICIENTE
        tokens_after_basic = self._estimate_tokens_for_context(
            trimmed_context["history"], 
            trimmed_context["db_schema"], 
            trimmed_context["functions"], 
            trimmed_context["mcp_tools"], 
            trimmed_context["app_descriptors"]
        )
        
        if tokens_after_basic <= MAX_INPUT_TOKENS:
            logger.info(f"[OpenAIService] ✅ Trimming básico suficiente: {tokens_after_basic} ≤ {MAX_INPUT_TOKENS}")
            return trimmed_context
        
        # 🔒 NIVEL 2: Trimming agresivo
        logger.warning(f"[OpenAIService] 🔒 Trimming básico insuficiente ({tokens_after_basic} > {MAX_INPUT_TOKENS}) - aplicando trimming agresivo")
        
        # 1. Historial más agresivo
        if len(trimmed_context["history"]) > 3:
            trimmed_context["history"] = trimmed_context["history"][-3:]
            logger.info(f"[OpenAIService] 🔒 Historial recortado agresivamente: → 3 turnos")
        
        # 2. Schema más agresivo
        if trimmed_context["db_schema"] and len(trimmed_context["db_schema"]) > 1500:
            trimmed_context["db_schema"] = trimmed_context["db_schema"][:1500] + "\n\n... (schema truncado agresivamente)"
            logger.info(f"[OpenAIService] 🔒 Schema recortado agresivamente: → 1500 caracteres")
        
        # 3. Funciones más agresivo
        if len(trimmed_context["functions"]) > 2:
            trimmed_context["functions"] = trimmed_context["functions"][:2]
            logger.info(f"[OpenAIService] 🔒 Funciones limitadas agresivamente: → 2")
        
        # 4. MCP tools más agresivo
        if trimmed_context["mcp_tools"] and trimmed_context["mcp_tools"].get("tools") and len(trimmed_context["mcp_tools"]["tools"]) > 2:
            trimmed_context["mcp_tools"] = {
                "tools": trimmed_context["mcp_tools"]["tools"][:2]
            }
            logger.info(f"[OpenAIService] 🔒 MCP tools limitadas agresivamente: → 2")
        
        # 🔍 VERIFICAR TOKENS FINALES
        final_tokens = self._estimate_tokens_for_context(
            trimmed_context["history"], 
            trimmed_context["db_schema"], 
            trimmed_context["functions"], 
            trimmed_context["mcp_tools"], 
            trimmed_context["app_descriptors"]
        )
        
        logger.info(f"[OpenAIService] 🔒 Trimming completado: {initial_tokens} → {final_tokens} tokens")
        
        return trimmed_context

    def _apply_lite_trimming_to_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Aplica trimming lite a mensajes para chat completion"""
        if len(messages) <= MAX_HISTORY_TURNS + 2:  # +2 para system y user message
            return messages
        
        # Mantener system message, user message y últimos turnos de historial
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        user_msg = messages[-1] if messages else None
        
        if system_msg and user_msg:
            # Obtener últimos turnos de historial (excluyendo system y user)
            history_messages = messages[1:-1]
            limited_history = history_messages[-MAX_HISTORY_TURNS:]
            
            trimmed_messages = [system_msg] + limited_history + [user_msg]
            logger.info(f"[OpenAIService] 🔒 Mensajes recortados: {len(messages)} → {len(trimmed_messages)}")
            return trimmed_messages
        
        return messages

    def _estimate_tokens_for_messages(self, messages: List[Dict[str, Any]]) -> int:
        """Estima el número de tokens para una lista de mensajes"""
        try:
            # Estimación aproximada: 1 token ≈ 4 caracteres
            total_chars = 0
            for msg in messages:
                content = msg.get("content", "")
                total_chars += len(content)
            
            estimated_tokens = total_chars // 4
            return estimated_tokens
        except Exception as e:
            logger.warning(f"[OpenAIService] ⚠️ Error estimando tokens: {e}")
            return 0

    def _estimate_tokens_for_context(
        self, 
        history: List[Dict[str, Any]], 
        db_schema: Optional[str], 
        functions: List[Function], 
        mcp_tools: Optional[dict], 
        app_descriptors: Optional[str]
    ) -> int:
        """Estima el número total de tokens para todo el contexto"""
        try:
            total_tokens = 0
            
            # 1. Tokens del historial
            history_tokens = self._estimate_tokens_for_messages(history)
            total_tokens += history_tokens
            
            # 2. Tokens del schema de base de datos
            if db_schema:
                schema_tokens = len(db_schema) // 4
                total_tokens += schema_tokens
            
            # 3. Tokens de las funciones
            if functions:
                function_tokens = sum(len(str(f.model_dump())) // 4 for f in functions)
                total_tokens += function_tokens
            
            # 4. Tokens de las herramientas MCP
            if mcp_tools and mcp_tools.get("tools"):
                mcp_tokens = sum(len(str(tool)) // 4 for tool in mcp_tools["tools"])
                total_tokens += mcp_tokens
            
            # 5. Tokens de los descriptores de apps
            if app_descriptors:
                app_tokens = len(app_descriptors) // 4
                total_tokens += app_tokens
            
            logger.debug(f"[OpenAIService] 🔍 Tokens estimados por componente: historial={history_tokens}, schema={schema_tokens if db_schema else 0}, funciones={function_tokens if functions else 0}, MCP={mcp_tokens if mcp_tools else 0}, apps={app_tokens if app_descriptors else 0}")
            
            return total_tokens
            
        except Exception as e:
            logger.warning(f"[OpenAIService] ⚠️ Error estimando tokens del contexto: {e}")
            return 0

    def _optimize_schema_for_query(self, db_schema: str, user_message: str = "") -> str:
        """
        Optimiza el esquema de la base de datos basándose en la relevancia de la consulta del usuario.
        LIMPIA información innecesaria y prioriza tablas relevantes.
        
        Args:
            db_schema: Esquema completo de la base de datos
            user_message: Mensaje del usuario para determinar relevancia (opcional)
            
        Returns:
            Esquema optimizado y limpio que prioriza las tablas más relevantes
        """
        try:
            if not db_schema:
                return db_schema
            
            # 🧹 SIEMPRE limpiar el schema, incluso sin user_message
            logger.info(f"[OpenAIService] 🧹 Limpiando schema de {len(db_schema)} caracteres")
            
            # Extraer palabras clave de la consulta del usuario
            user_lower = user_message.lower()
            
            # Definir categorías de tablas y sus palabras clave
            table_categories = {
                "clubs": ["club", "clubs", "invitación", "invitaciones", "membership", "miembro"],
                "users": ["usuario", "usuarios", "user", "users", "persona", "gente"],
                "content": ["blog", "post", "artículo", "contenido", "publicación"],
                "location": ["ciudad", "cities", "país", "country", "ubicación", "dirección"],
                "commerce": ["producto", "product", "venta", "sale", "categoría", "category"],
                "communication": ["mensaje", "message", "contacto", "contact", "email"],
                "system": ["configuración", "setting", "config", "rol", "role", "permiso"]
            }
            
            # Analizar el esquema para extraer información de tablas
            lines = db_schema.split('\n')
            table_info = {}
            current_table = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('📋') and 'cols' in line:
                    # Nueva tabla encontrada
                    table_name = line.split('📋')[1].split('(')[0].strip()
                    current_table = table_name
                    table_info[table_name] = {
                        'lines': [],
                        'relevance_score': 0,
                        'category': 'other'
                    }
                elif current_table and line:
                    table_info[current_table]['lines'].append(line)
            
            # Calcular puntuación de relevancia para cada tabla
            for table_name, info in table_info.items():
                table_lower = table_name.lower()
                
                # 🔍 Si hay user_message, calcular relevancia
                if user_message:
                    # Verificar si la tabla coincide con categorías relevantes
                    for category, keywords in table_categories.items():
                        if any(keyword in user_lower for keyword in keywords):
                            # Si la consulta menciona palabras clave de esta categoría
                            if any(keyword in table_lower for keyword in keywords):
                                info['relevance_score'] += 10  # Alta relevancia
                                info['category'] = category
                            else:
                                info['relevance_score'] += 5   # Relevancia media
                    
                    # Bonus por coincidencias exactas en el nombre de la tabla
                    for keyword in user_lower.split():
                        if keyword in table_lower:
                            info['relevance_score'] += 3
                    
                    # Bonus por tablas que contienen palabras clave importantes
                    if any(word in table_lower for word in ['invitation', 'request', 'club', 'user']):
                        info['relevance_score'] += 2
                else:
                    # 🧹 Sin user_message, priorizar tablas comunes por defecto
                    if any(word in table_lower for word in ['invitation', 'request', 'club', 'user']):
                        info['relevance_score'] += 5
                    elif any(word in table_lower for word in ['amenity', 'city', 'country']):
                        info['relevance_score'] += 3
            
            # Ordenar tablas por relevancia
            sorted_tables = sorted(table_info.items(), key=lambda x: x[1]['relevance_score'], reverse=True)
            
            # Construir esquema optimizado y LIMPIO
            optimized_schema_lines = []
            total_chars = 0
            max_chars = MAX_SCHEMA_CHARS
            
            # Agregar encabezado
            header = "-- DATABASE SCHEMA (OPTIMIZADO Y LIMPIO) --"
            optimized_schema_lines.append(header)
            total_chars += len(header)
            
            # Agregar tablas por orden de relevancia
            for table_name, info in sorted_tables:
                if total_chars >= max_chars:
                    break
                
                # 🧹 LIMPIAR y optimizar la información de la tabla
                cleaned_table_lines = self._clean_table_schema(table_name, info['lines'])
                
                # Agregar tabla limpia
                table_lines = [f"\n📋 {table_name} ({len(cleaned_table_lines)} cols)"]
                table_lines.extend(cleaned_table_lines)
                
                # Verificar si cabe en el límite
                table_content = '\n'.join(table_lines)
                if total_chars + len(table_content) <= max_chars:
                    optimized_schema_lines.extend(table_lines)
                    total_chars += len(table_content)
                else:
                    # Agregar solo el nombre de la tabla si no cabe todo
                    optimized_schema_lines.append(f"\n📋 {table_name} (información truncada)")
                    break
            
            # Agregar resumen de optimización
            summary = f"\n\n-- OPTIMIZACIÓN: {len(optimized_schema_lines)} líneas, {total_chars} caracteres --"
            summary += f"\n-- Tablas más relevantes: {', '.join([t[0] for t in sorted_tables[:5]])} --"
            
            optimized_schema = '\n'.join(optimized_schema_lines) + summary
            
            logger.info(f"[OpenAIService] 🎯 Schema optimizado y LIMPIO: {len(db_schema)} → {len(optimized_schema)} caracteres")
            logger.info(f"[OpenAIService] 🎯 Tablas prioritarias: {', '.join([t[0] for t in sorted_tables[:3]])}")
            
            return optimized_schema
            
        except Exception as e:
            logger.warning(f"[OpenAIService] ⚠️ Error optimizando schema: {e}")
            return db_schema

    def _clean_table_schema(self, table_name: str, column_lines: List[str]) -> List[str]:
        """
        🧹 LIMPIA la información de columnas eliminando datos innecesarios.
        
        Args:
            table_name: Nombre de la tabla
            column_lines: Líneas con información de columnas
            
        Returns:
            Lista de líneas limpias con solo información esencial
        """
        cleaned_lines = []
        
        for line in column_lines:
            if not line.strip():
                continue
                
            # 🎯 PATRÓN: "• column_name: type NOT NULL" → "• column_name: type"
            if line.startswith('•') and ':' in line:
                parts = line.split(':')
                if len(parts) == 2:
                    column_name = parts[0].replace('•', '').strip()
                    type_info = parts[1].strip()
                    
                    # 🧹 LIMPIAR tipo de datos
                    cleaned_type = self._clean_column_type(type_info)
                    
                    # 🧹 ELIMINAR "NOT NULL" redundante
                    if 'NOT NULL' in cleaned_type:
                        cleaned_type = cleaned_type.replace('NOT NULL', '').strip()
                    
                    # 🧹 ELIMINAR información de restricciones innecesaria
                    if 'PRIMARY KEY' in cleaned_type:
                        cleaned_type = cleaned_type.replace('PRIMARY KEY', '').strip()
                    if 'UNIQUE' in cleaned_type:
                        cleaned_type = cleaned_type.replace('UNIQUE', '').strip()
                    
                    # 🧹 ELIMINAR espacios extra y comas
                    cleaned_type = cleaned_type.replace('  ', ' ').strip()
                    if cleaned_type.endswith(','):
                        cleaned_type = cleaned_type[:-1]
                    
                    # 🎯 SOLO incluir columnas con información útil
                    if cleaned_type and not self._is_useless_column(column_name, cleaned_type):
                        cleaned_line = f"  • {column_name}: {cleaned_type}"
                        cleaned_lines.append(cleaned_line)
        
        return cleaned_lines

    def _clean_column_type(self, type_info: str) -> str:
        """
        🧹 LIMPIA y simplifica los tipos de datos de columnas.
        
        Args:
            type_info: Información del tipo de columna
            
        Returns:
            Tipo de dato limpio y simplificado
        """
        # 🧹 Simplificar tipos verbosos
        type_mappings = {
            'character varying': 'varchar',
            'character': 'char',
            'timestamp without time zone': 'timestamp',
            'timestamp with time zone': 'timestamptz',
            'numeric': 'decimal',
            'double precision': 'float8',
            'real': 'float4',
            'integer': 'int',
            'bigint': 'int8',
            'smallint': 'int2'
        }
        
        cleaned_type = type_info
        for verbose_type, simple_type in type_mappings.items():
            if verbose_type in cleaned_type:
                cleaned_type = cleaned_type.replace(verbose_type, simple_type)
        
        return cleaned_type

    def _is_useless_column(self, column_name: str, column_type: str) -> bool:
        """
        🚫 Determina si una columna es inútil para el contexto del AI.
        
        Args:
            column_name: Nombre de la columna
            column_type: Tipo de la columna
            
        Returns:
            True si la columna no aporta valor al AI
        """
        # 🚫 Columnas que no aportan valor al AI
        useless_patterns = [
            'created_at', 'updated_at', 'deleted_at', 'modified_at',
            'created_by', 'updated_by', 'deleted_by', 'modified_by',
            'version', 'revision', 'checksum', 'hash',
            'metadata', 'config', 'settings', 'options',
            'flags', 'status', 'state', 'active'
        ]
        
        # 🚫 Tipos de datos que no aportan valor
        useless_types = [
            'blob', 'bytea', 'binary', 'longblob',
            'geometry', 'geography', 'point', 'polygon'
        ]
        
        # 🚫 Verificar patrones inútiles
        column_lower = column_name.lower()
        for pattern in useless_patterns:
            if pattern in column_lower:
                return True
        
        # 🚫 Verificar tipos inútiles
        type_lower = column_type.lower()
        for useless_type in useless_types:
            if useless_type in type_lower:
                return True
        
        return False

    def _check_token_bucket(self) -> bool:
        """Verifica si hay tokens disponibles en el bucket"""
        current_time = time.time()
        
        # Resetear bucket si ha pasado la ventana de tiempo
        if current_time - self._token_bucket["window_start"] > self._token_bucket["window_size"]:
            self._token_bucket["tokens_used"] = 0
            self._token_bucket["window_start"] = current_time
            logger.debug("[OpenAIService] 🔒 Token bucket reseteado")
        
        # Verificar si hay tokens disponibles
        available_tokens = self._token_bucket["max_tokens_per_window"] - self._token_bucket["tokens_used"]
        
        if available_tokens < MAX_INPUT_TOKENS:
            logger.warning(f"[OpenAIService] 🔒 Token bucket limitado: {available_tokens} disponibles, {MAX_INPUT_TOKENS} necesarios")
            return False
        
        return True

    def _update_token_bucket(self, tokens_used: int):
        """Actualiza el token bucket con los tokens utilizados"""
        self._token_bucket["tokens_used"] += tokens_used
        logger.debug(f"[OpenAIService] 🔒 Token bucket actualizado: {self._token_bucket['tokens_used']} tokens usados")

    async def _plan_actions_with_lite_payload(
        self,
        chat_id: UUID,
        user_message: ChatMessage,
        db_schema: Optional[str],
        available_functions: List[Function],
        available_mcp_tools: Optional[dict] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        database_schemas: Optional[Dict[str, Any]] = None,
        db_ids: Optional[List[UUID]] = None,
        use_enriched_context: bool = True,
        app_descriptors_compact: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Plan de acciones usando payload lite para evitar exceder límites de tokens"""
        logger.info("[OpenAIService] 🔒 Usando payload lite para plan de acciones")
        
        # Construir contexto mínimo
        if history is None:
            msgs = self.history_service.get_history(chat_id, limit=3)  # Solo 3 turnos
            history = [m.model_dump() for m in msgs]
        
        # Truncar schema si es muy largo
        if db_schema and len(db_schema) > 2000:
            db_schema = db_schema[:2000] + "\n\n... (schema truncado por límite de tokens)"
        
        # Limitar funciones
        limited_functions = available_functions[:3] if available_functions else []
        
        # Construir mensajes mínimos
        messages = [
            {
                "role": "system",
                "content": "Eres un asistente que genera planes JSON. Responde de forma concisa y directa."
            },
            *history[-2:],  # Solo últimos 2 turnos
            user_message.model_dump(),
        ]
        
        payload = {
            "model": self.model,
            "functions": [self.RETURN_PLAN_FUNC],
            "function_call": "auto",
            "temperature": 0.3,  # Más determinístico
            "messages": messages,
            "max_tokens": 1024,  # Límite estricto
            "stream": False,
        }
        
        try:
            resp = await self._call_openai_with_retry(payload, max_retries=1)  # Solo 1 intento
            
            choice = resp.choices[0]
            function_call = getattr(choice.message, "function_call", None)
            content = (choice.message.content or "").strip()
            
            if function_call:
                args_raw = function_call.arguments or "{}"
                try:
                    plan_obj = self.parser.parse(args_raw)
                    logger.info("[OpenAIService] ✅ Plan lite validado (%d acciones)", len(plan_obj.actions))
                    return plan_obj.model_dump()
                except ValidationError:
                    pass
            
            if content:
                return {"actions": [], "assistant_response": content}
            
            return {
                "actions": [],
                "assistant_response": "He generado un plan simplificado debido a limitaciones de contexto."
            }
            
        except Exception as e:
            logger.error(f"[OpenAIService] ❌ Error con payload lite: {e}")
            return {
                "actions": [],
                "assistant_response": "Estoy reduciendo contexto para cumplir límites. Por favor, reformula tu consulta de manera más específica."
            }
