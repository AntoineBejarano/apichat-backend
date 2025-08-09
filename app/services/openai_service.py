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
from openai import OpenAI
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

PLANNER_SYSTEM_PROMPT_PREFIX = (
    "Tu tarea es actuar como un asistente conversacional inteligente capaz de generar planes de acción en formato JSON "
    "usando herramientas como funciones (`api_function`), consultas a base de datos (`db_query`) o herramientas MCP (`mcp_tool`).\n\n"
    "Cuando el mensaje del usuario sea trivial, social o no requiera ejecutar ninguna acción "
    "(por ejemplo: \"Hola\", \"¿Qué tal estás?\", \"¿Estás ahí?\", \"Gracias\"), responde de manera breve, amable y adaptándote al idioma del usuario. "
    "No generes un plan en estos casos.\n\n"
    "Cuando el mensaje del usuario implique resolver una necesidad, tomar decisiones complejas o acceder a datos, "
    "responde primero con: \"Estoy generando tu plan, dame un segundo...\" (en el idioma del usuario) y después devuelve un JSON con el plan "
    "llamando a la función `return_plan`. No incluyas texto fuera del JSON cuando generes un plan.\n\n"
    "IMPORTANTE: Cuando muestres listas de datos (como tablas, resultados de consultas, etc.), formatea la respuesta de manera clara y legible:\n"
    "- Usa viñetas (•) o numeración para listas\n"
    "- Agrupa información relacionada\n"
    "- Usa saltos de línea para separar secciones\n"
    "- Si hay muchos elementos, considera agruparlos por categorías\n"
    "- Mantén un formato consistente y fácil de leer\n\n"
    "VARIABLES DISPONIBLES: Cuando tengas resultados de consultas, usa estas variables:\n"
    "- {{variable}}: resultado raw\n"
    "- {{variable_list}}: lista simple de valores\n"
    "- {{variable_pretty}}: string con comas\n"
    "- {{variable_formatted}}: versión formateada y legible (RECOMENDADO para mostrar al usuario)\n\n"
    "CONSULTAS SQL - REGLAS ESTRICTAS:\n"
    "⚠️ CRÍTICO: NUNCA uses columnas que no estén en el esquema proporcionado\n"
    "1. SIEMPRE revisa el esquema de la tabla antes de escribir SQL\n"
    "2. SOLO usa columnas que aparezcan en el CREATE TABLE del esquema\n"
    "3. Ejemplo genérico: Si el esquema muestra: CREATE TABLE tabla (id INTEGER, nombre VARCHAR, direccion TEXT, descripcion TEXT)\n"
    "   ✅ CORRECTO: SELECT id FROM tabla WHERE nombre LIKE '%valor%' AND direccion LIKE '%ciudad%'\n"
    "   ❌ INCORRECTO: SELECT id FROM tabla WHERE nombre = 'valor' AND ciudad = 'ciudad' (ciudad no existe)\n"
    "4. Para buscar por ubicación, usa columnas como 'address', 'location', 'direccion', 'ubicacion', 'description', 'descripcion' que contengan la información\n"
    "5. Si necesitas buscar por ciudad pero no hay columna 'city' o 'ciudad', usa LIKE en 'address', 'direccion', 'location', 'ubicacion' o 'description', 'descripcion'\n"
    "6. NUNCA asumas columnas que no están en el esquema\n"
    "7. Si no estás seguro, primero ejecuta: DESCRIBE nombre_tabla o consulta el schema\n\n"
    "BÚSQUEDAS FLEXIBLES - IMPORTANTE:\n"
    "🔍 SIEMPRE usa búsquedas similares para nombres y ubicaciones:\n"
    "• Para nombres: usa LIKE '%nombre%' en lugar de = 'nombre'\n"
    "• Para ubicaciones: usa LIKE '%ciudad%' en lugar de = 'ciudad'\n"
    "• Ejemplos genéricos:\n"
    "  ✅ SELECT id FROM tabla WHERE nombre LIKE '%valor%' AND direccion LIKE '%ciudad%'\n"
    "  ✅ SELECT id FROM tabla WHERE nombre ILIKE '%valor%' AND descripcion LIKE '%ciudad%'\n"
    "  ❌ SELECT id FROM tabla WHERE nombre = 'valor' (puede fallar si el nombre no es exacto)\n"
    "• Usa ILIKE para búsquedas case-insensitive (PostgreSQL)\n"
    "• Usa LIKE para búsquedas case-sensitive (MySQL, SQLite)\n"
    "• Esto evita errores cuando el usuario no recuerda el nombre exacto\n\n"
    "VALIDACIÓN DE ESQUEMA:\n"
    "🔍 ANTES de escribir SQL, SIEMPRE:\n"
    "1. Lee el esquema completo proporcionado\n"
    "2. Identifica las tablas relevantes\n"
    "3. Lista las columnas disponibles para cada tabla\n"
    "4. Usa SOLO las columnas que aparecen en el esquema\n"
    "5. Si no encuentras una columna, busca alternativas en el esquema\n\n"
    "Si el mensaje del usuario es ambiguo, pide educadamente que aclare su intención.\n\n"
    "Si se proporciona un dialecto SQL, RESPÉTALO estrictamente y evita comandos de otros dialectos."
    "Cuando insertes variables del contexto en `assistant_response`, "
    "usa SIEMPRE el formato {{nombre_variable}} (doble llave). No uses {variable}.\n"
)

PROMPT_SUFFIX = (
    "---\n"
    "Devuelve SIEMPRE la llamada de función `return_plan` y un JSON que cumpla con este esquema:\n"
    f"{json.dumps(PlanModel.model_json_schema(), indent=2)}\n"
    "No incluyas texto fuera del JSON."
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

# ──────────────────────────────────────────────────────
#   Helpers
# ──────────────────────────────────────────────────────
def _json_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def _extract_dialect(schema: Optional[str]) -> Optional[str]:
    if not schema:
        return None
    match = re.search(r"-- DIALECT: (\w+)", schema, re.IGNORECASE)
    return match.group(1).lower() if match else None

# ──────────────────────────────────────────────────────
#   Resultado de completion
# ──────────────────────────────────────────────────────
class CompletionResult(NamedTuple):
    content: str
    token_count: int

# ──────────────────────────────────────────────────────
#   Servicio principal
# ──────────────────────────────────────────────────────
class OpenAIService:
    RETURN_PLAN_FUNC: Dict[str, Any] = {
        "name": "return_plan",
        "description": (
            "Devuelve el plan de acciones (`actions`) y el texto final "
            "(`assistant_response`) que el asistente mostrará al usuario."
        ),
        "parameters": PlanModel.model_json_schema(),
    }

    def __init__(self, factory: "ServiceFactory") -> None:
        self.factory = factory
        self.db = factory.db
        self.user = factory.user

        self.history_service = factory.get_chat_history_service()
        self.function_service = factory.get_function_service()

        # ⚡ OPTIMIZACIÓN: Configuración mejorada del cliente OpenAI
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            timeout=30.0,  # Timeout de 30 segundos
            max_retries=3,  # Reintentos automáticos
        )
        self.model = settings.OPENAI_MODEL
        self.parser = PydanticOutputParser(pydantic_object=PlanModel)
        
        # Cache para prompts
        self._prompt_cache = {}
        self._cache_ttl = 300  # 5 minutos

        logger.info("[OpenAIService] 🚀 Instanciado para user=%s", self.user.email)

    # ──────────────────────────────────────────────────
    #   PLAN ACTIONS (OPTIMIZADO)
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

        # ⚡ OPTIMIZACIÓN: Cache de prompts
        cache_key = self._generate_prompt_cache_key(
            db_schema, available_functions, available_mcp_tools, app_descriptors_compact
        )
        
        # 1) Contexto histórico (limitado para optimizar)
        if history is None:
            msgs = self.history_service.get_history(chat_id, limit=6)  # Reducido de 8 a 6
            history = [m.model_dump() for m in msgs]

        # 2) Construir contexto de esquema (SIMPLE - solo lista de tablas)
        if use_enriched_context and db_ids:
            logger.info(f"[OpenAIService] 📋 Usando lista simple de tablas para {len(db_ids)} DBs")
            try:
                # 🔧 Usar el nuevo sistema de cache detallado
                cache_service = self.factory.get_detailed_schema_cache_service()
                schemas = []
                for db_id in db_ids:
                    cache_entry = cache_service.get_schema_cache(self.factory.user.id, db_id)
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

        # 3) Construcción de mensajes optimizada
        messages = [
            {
                "role": "system",
                "content": self._get_cached_or_build_prompt(
                    cache_key, db_schema, available_functions, available_mcp_tools, app_descriptors_compact
                ),
            },
            *history,
            user_message.model_dump(),
        ]

        logger.info("[OpenAIService] 📝 Generando plan (msgs=%d)", len(messages))
        logger.debug("🔹 Contexto → %s", truncate_words(str(messages), 60))

        # ⚡ OPTIMIZACIÓN: Payload optimizado
        payload = {
            "model": self.model,
            "functions": [self.RETURN_PLAN_FUNC],
            "function_call": "auto",
            "temperature": settings.OPENAI_TEMPERATURE,
            "messages": messages,
            "max_tokens": 2000,  # Limitar tokens para respuesta más rápida
            "stream": False,  # Desactivar streaming para respuestas más rápidas
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

        # 3) Llamada asíncrona con retry
        resp = await self._call_openai_with_retry(safe)

        self.factory.get_usage_service().register_token_usage(
            model=self.model,
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
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
        history = self.history_service.get_history(chat_id, limit=6)  # Reducido de 8 a 6
        messages = [
            {"role": "system", "content": system_prompt or "You are a helpful assistant."},
            *[ChatHistoryOut.model_validate(m).model_dump() for m in history],
            user_message.model_dump(),
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.OPENAI_TEMPERATURE,
            "max_tokens": 1000,  # Limitar tokens
            "stream": False,  # Desactivar streaming
        }
        safe = json.loads(json.dumps(payload, default=_json_default))

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
    #   MÉTODOS DE OPTIMIZACIÓN
    # ──────────────────────────────────────────────────
    async def _call_openai_with_retry(self, payload: Dict[str, Any], max_retries: int = 3):
        """Llamada a OpenAI con retry automático"""
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(
                    None, lambda: self.client.chat.completions.create(**payload)
                )
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[OpenAIService] ❌ Error después de {max_retries} intentos: {e}")
                    raise HTTPException(500, f"Error en OpenAI: {str(e)}")
                
                wait_time = (2 ** attempt) * 0.5  # Exponential backoff
                logger.warning(f"[OpenAIService] ⚠️ Intento {attempt + 1} falló, reintentando en {wait_time}s: {e}")
                await asyncio.sleep(wait_time)

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

        parts: List[str] = [PLANNER_SYSTEM_PROMPT_PREFIX.strip()]

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

        # Esquema SQL (limitado para optimizar)
        if db_schema:
            # ⚡ OPTIMIZACIÓN: Limitar tamaño del schema
            truncated_schema = db_schema[:400]  # Reducido de 600 a 400
            parts.append(f"{PROMPT_SQL_HEADER}\n{truncated_schema}")

        # Funciones disponibles (limitado)
        if functions:
            # ⚡ OPTIMIZACIÓN: Limitar número de funciones mostradas
            limited_functions = functions[:10]  # Máximo 10 funciones
            fx = [f"• {f.name}: {truncate_words(f.description or '', 10)}"  # Reducido de 12 a 10
                  for f in limited_functions]
            parts.append(f"{PROMPT_FUNCTIONS_HEADER}\n" + "\n".join(fx))

        # Herramientas MCP (limitado)
        if mcp_tools and mcp_tools.get("tools"):
            # ⚡ OPTIMIZACIÓN: Limitar número de herramientas
            limited_tools = mcp_tools["tools"][:5]  # Máximo 5 herramientas
            tl = [f"• {t['name']}: {t.get('description', '')[:50]}"  # Limitar descripción
                  for t in limited_tools]
            parts.append(f"{PROMPT_MCP_HEADER}\n" + "\n".join(tl))

        # 🆕 Descriptores de aplicaciones
        if app_descriptors_compact:
            parts.append(f"{PROMPT_APPS_HEADER}\n{app_descriptors_compact}")

        parts.append(PROMPT_SUFFIX)
        return "\n\n".join(parts)
