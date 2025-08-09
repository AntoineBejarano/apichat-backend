from typing import Dict, Any, List, Optional, TypedDict
from uuid import UUID

from langgraph.graph import StateGraph
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage
from app.schemas.plan_schema import PlanModel
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from langchain_community.utilities.sql_database import SQLDatabase

import logging

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
#   Estado compartido del grafo
# ──────────────────────────────────────────────────────
class ExplorationState(TypedDict, total=False):
    chat_id: str
    message: ChatMessage
    history: List[Dict[str, Any]]

    # Recursos inferidos
    db_ids: List[str]
    db_conns: List[SQLDatabase]  # 🔧 Instancias SQL, no registros ORM
    db_dialect: Optional[str]
    apps: List[App]
    functions: List[Function]
    proxy_id: Optional[str]
    
    # Nuevos campos para modo explore mejorado
    compact_schemas: Dict[str, str]  # {db_id: compact_schema}
    cache_status: Optional[Dict[str, str]]  # Para debugging

    # Salidas posibles
    plan: PlanModel
    assistant_response: str
    error: str


# ──────────────────────────────────────────────────────
#   Grafo Exploration
# ──────────────────────────────────────────────────────
class ExplorationGraph:
    def __init__(self, factory: ServiceFactory, max_schema_chars: int = 80000):
        self.factory = factory
        self.max_schema_chars = max_schema_chars  # Configurable schema size limit

    async def run(self, context: ExplorationState) -> ExplorationState:
        builder = StateGraph(ExplorationState)

        # ── Nodo 1: inferir BDs, apps y funciones (NUEVO MODO EXPLORE) ───────────────────────────────
        async def infer_resources(state: ExplorationState) -> ExplorationState:
            message: ChatMessage = state["message"]
            
            # 🔧 Si ya vienen db_ids/apps en el state, respetarlos y salir
            if state.get("db_ids") or state.get("apps"):
                logger.info("[ExplorationGraph] 📥 Recursos ya proporcionados en state, saltando inferencia")
                return state
            
            logger.info("[ExplorationGraph] 🎯 Iniciando selección automática por descripciones")
            
            # a) Usar DescriptionSelectorService para seleccionar candidatos
            try:
                selector = self.factory.get_description_selector_service()
                picks = selector.select(message.content, top_k=2, threshold=0.55)
                
                db_candidates = picks.get("db_candidates", [])
                app_candidates = picks.get("app_candidates", [])
                
                # 🔧 Ordenar candidatos por score descendente para orden estable
                db_candidates.sort(key=lambda x: x[1], reverse=True)
                app_candidates.sort(key=lambda x: x[1], reverse=True)
                
                # 🔧 Corte explícito tras ordenar para asegurar top-k
                TOP_K_LIMIT = 2  # Configurable limit
                db_candidates = db_candidates[:TOP_K_LIMIT]
                app_candidates = app_candidates[:TOP_K_LIMIT]
                
                logger.info(f"[ExplorationGraph] 📋 Candidatos (top-{TOP_K_LIMIT}): {len(db_candidates)} DBs, {len(app_candidates)} apps")
                if db_candidates:
                    logger.info(f"[ExplorationGraph] 🗄️ Top DB scores: {[(db_id[:8], f'{score:.3f}') for db_id, score in db_candidates[:3]]}")
                if app_candidates:
                    logger.info(f"[ExplorationGraph] 📱 Top App scores: {[(app_id, f'{score:.3f}') for app_id, score in app_candidates[:3]]}")
                
            except Exception as e:
                logger.exception(f"[ExplorationGraph] ❌ Error en selección automática: {e}")
                db_candidates, app_candidates = [], []
            
            # b) Preparar db_ids y hacer warm-up de schemas
            db_ids: List[str] = []
            db_conns: List[SQLDatabase] = []
            db_dialect: Optional[str] = None
            compact_schemas: Dict[str, str] = {}
            cache_status: Dict[str, str] = {}
            
            database_service = self.factory.get_database_service()
            cache_service = self.factory.get_detailed_schema_cache_service()
            
            for db_id_str, score in db_candidates:
                try:
                    db_id_uuid = UUID(db_id_str)
                    
                    # c) Hacer warm-up del schema
                    logger.info(f"[ExplorationGraph] 🔥 Warm-up schema para DB {db_id_str[:8]}... (score: {score:.3f})")
                    
                    # Obtener cache existente
                    cache_entry = cache_service.get_schema_cache(self.factory.user.id, db_id_uuid)
                    
                    if cache_entry and cache_entry.compact and cache_entry.compact.strip():
                        # Cache hit - usar existente
                        logger.info(f"[ExplorationGraph] ✅ Cache hit para DB {db_id_str[:8]}")
                        cache_status[db_id_str] = "cache_hit"
                    else:
                        # Cache miss - crear nuevo
                        # Crear cache si no existe - usar introspección directa
                        logger.info(f"[ExplorationGraph] 🆕 Creando cache para DB {db_id_str[:8]}...")
                        try:
                            # Introspección directa sin dependencias externas
                            introspected_schema = self._introspect_database_schema(db_id_uuid)
                            
                            if introspected_schema and introspected_schema.get('tables'):
                                # Crear snapshot desde introspección
                                from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
                                snapshot = SchemaSnapshot(
                                    tables=introspected_schema['tables'],
                                    enrichment_level=EnrichmentLevel.BASIC,
                                    dialect=introspected_schema.get('dialect', 'postgresql')
                                )
                                
                                # Crear cache
                                cache_entry = cache_service.create_or_update_cache(
                                    user_id=self.factory.user.id,
                                    db_id=db_id_uuid,
                                    snapshot=snapshot,
                                    enrichment_level=EnrichmentLevel.BASIC
                                )
                            else:
                                cache_entry = None
                        except Exception as ce:
                            logger.exception(f"[ExplorationGraph] ❌ Error creando cache para DB {db_id_str[:8]}: {ce}")
                            cache_entry = None
                        
                        # Marcar cache status apropiado
                        if cache_entry and cache_entry.compact and cache_entry.compact.strip():
                            cache_status[db_id_str] = "cache_miss_created"
                        else:
                            cache_status[db_id_str] = "cache_miss_failed"
                    
                    if cache_entry and cache_entry.compact and cache_entry.compact.strip():
                        # Schema válido - incluir esta DB
                        db_ids.append(db_id_str)
                        compact_schemas[db_id_str] = cache_entry.compact
                        # cache_status ya está marcado arriba
                        
                        # d) Cargar instancia SQL (no registro ORM)
                        try:
                            sql_instance = database_service.get_sql_instance(db_id_uuid)
                            if sql_instance:
                                db_conns.append(sql_instance)
                                
                                # e) Inferir dialecto del primero (best-effort) - usando API pública
                                if not db_dialect:
                                    try:
                                        # Usar método público del database service
                                        db_dialect = database_service.get_dialect_name(db_id_uuid)
                                        
                                        if db_dialect:
                                            logger.info(f"[ExplorationGraph] 🧪 Dialecto inferido: {db_dialect}")
                                        else:
                                            # Fallback seguro
                                            db_dialect = "postgresql"
                                            logger.info(f"[ExplorationGraph] 🧪 Dialecto por defecto: {db_dialect}")
                                    except Exception as de:
                                        logger.debug(f"[ExplorationGraph] No se pudo inferir dialecto: {de}")
                                        db_dialect = "postgresql"  # Safe default
                        except Exception as ce:
                            logger.warning(f"[ExplorationGraph] ⚠️ Error cargando instancia SQL DB {db_id_str[:8]}: {ce}")
                        
                        logger.info(f"[ExplorationGraph] ✅ DB {db_id_str[:8]} ready (schema: {len(cache_entry.compact)} chars)")
                    # Si llegamos aquí sin cache_entry válido, ya está marcado en cache_status
                        
                except Exception as e:
                    logger.exception(f"[ExplorationGraph] ❌ Error procesando DB {db_id_str[:8]}: {e}")
                    cache_status[db_id_str] = "processing_error"
            
            # f) Cargar apps y functions de candidatos
            apps: List[App] = []
            functions: List[Function] = []
            proxy_id: Optional[str] = None
            
            app_service = self.factory.get_app_service()
            function_service = self.factory.get_function_service()
            
            for app_id_str, score in app_candidates:
                try:
                    # Convertir app_id a UUID (apps.id es UUID)
                    try:
                        app_id = UUID(app_id_str) if isinstance(app_id_str, str) else app_id_str
                    except ValueError:
                        logger.warning(f"[ExplorationGraph] ⚠️ Invalid app_id UUID format: {app_id_str}")
                        continue
                    
                    app = app_service.get_by_id(app_id)
                    if app:
                        apps.append(app)
                        
                        # Cargar functions de esta app
                        app_functions = function_service.get_by_app(app.id)
                        functions.extend(app_functions)
                        
                        # Conservar proxy_id si aplica
                        if app.proxy_id and not proxy_id:
                            proxy_id = app.proxy_id
                        
                        logger.info(f"[ExplorationGraph] ✅ App {app.name} loaded (score: {score:.3f}, functions: {len(app_functions)})")
                        
                except Exception as e:
                    logger.warning(f"[ExplorationGraph] ⚠️ Error cargando app {app_id_str[:8]}: {e}")
            
            # g) Log resumen
            logger.info(f"[ExplorationGraph] 🎯 Selección completada: {len(db_ids)} DBs, {len(apps)} apps, {len(functions)} functions")
            
            if compact_schemas:
                total_chars = sum(len(schema) for schema in compact_schemas.values())
                logger.info(f"[ExplorationGraph] 📋 Schemas listos: {total_chars} chars total")
            
            return {
                **state,
                "db_ids": db_ids,
                "db_conns": db_conns,
                "db_dialect": db_dialect,
                "apps": apps,
                "functions": functions,
                "proxy_id": proxy_id,
                "compact_schemas": compact_schemas,
                "cache_status": cache_status,
            }

        # ── Nodo 2: llamar a OpenAI y decidir ───────────────────────────────────
        async def plan_or_reply(state: ExplorationState) -> ExplorationState:
            try:
                logger.info("[ExplorationGraph] 🧠 Calling OpenAI with cache validation...")


                # 🔧 NUEVO FLUJO: Usar compact_schemas del contexto (ya warm)
                compact_schemas = state.get("compact_schemas", {})
                cache_status = state.get("cache_status", {})
                
                # Construir schema compacto combinado para el LLM
                db_schema = None
                if compact_schemas:
                    # Combinar todos los schemas compactos
                    schema_parts = []
                    for db_id, compact_schema in compact_schemas.items():
                        if compact_schema and compact_schema.strip():
                            schema_parts.append(f"-- DATABASE {db_id} --")
                            schema_parts.append(compact_schema)
                            schema_parts.append("")
                    
                    if schema_parts:
                        db_schema = "\n".join(schema_parts)
                        
                        # 🔧 Límite de tamaño del prompt para evitar tokens excesivos
                        # Configurable: 80k chars (~20K tokens) para schemas grandes
                        MAX_SCHEMA_CHARS = self.max_schema_chars
                        if len(db_schema) > MAX_SCHEMA_CHARS:
                            logger.warning(f"[ExplorationGraph] ⚠️ Schema muy grande ({len(db_schema)} chars), truncando a {MAX_SCHEMA_CHARS}")
                            db_schema = db_schema[:MAX_SCHEMA_CHARS] + "\n-- [SCHEMA TRUNCATED DUE TO SIZE] --"
                        
                        logger.info(f"[ExplorationGraph] ✅ Schema compacto listo: {len(compact_schemas)} DBs, {len(db_schema)} chars")
                        
                        # Log de cache status para debugging - conteo coherente
                        hits = sum(1 for status in cache_status.values() if status == "cache_hit")
                        misses_created = sum(1 for status in cache_status.values() if status == "cache_miss_created")
                        misses_failed = sum(1 for status in cache_status.values() if status == "cache_miss_failed")
                        errors = sum(1 for status in cache_status.values() if status == "processing_error")
                        
                        logger.info(f"[ExplorationGraph] 📊 Cache status: {hits} hits, {misses_created} created, {misses_failed} failed, {errors} errors")
                    else:
                        logger.warning("[ExplorationGraph] ⚠️ Compact schemas vacíos")
                else:
                    # Sin compact_schemas disponible - dejar que el modelo responda sin esquema
                    db_schema = None
                    logger.warning("[ExplorationGraph] ⚠️ No compact_schemas disponible - continuando sin schema")

                # Consultar AI con schema compacto garantizado
                logger.info(f"[ExplorationGraph] 🤖 Consultando AI con schema compacto ({len(db_schema) if db_schema else 0} chars)")
                result = await self.factory.get_openai_service().plan_actions(
                    chat_id=state["chat_id"],
                    user_message=state["message"],
                    db_schema=db_schema,  # Schema compacto optimizado para LLM
                    available_functions=state.get("functions", []),
                    available_mcp_tools=None,
                    history=state.get("history", []),
                    db_ids=[db_id if isinstance(db_id, UUID) else UUID(str(db_id)) for db_id in compact_schemas.keys()] if compact_schemas else [],  # Asegurar UUID
                    use_enriched_context=False,  # Ya manejamos el contexto aquí
                )

                # — Plan con acciones
                if result.get("actions"):
                    plan = PlanModel.model_validate(result)
                    logger.info("[ExplorationGraph] ✅ Plan generado (%d acciones)", len(plan.actions))
                    return {**state, "plan": plan}

                # — Respuesta simple
                if result.get("assistant_response"):
                    logger.info("[ExplorationGraph] ✅ Respuesta simple generada")
                    return {**state, "assistant_response": result["assistant_response"]}

                # — Fallback
                logger.warning("[ExplorationGraph] ⚠️ Modelo no devolvió contenido")
                return {**state, "assistant_response": "Disculpa, no he entendido tu mensaje."}

            except Exception as e:
                logger.exception("[ExplorationGraph] ❌ Error generando plan/respuesta")
                return {
                    **state,
                    "error": str(e),
                    "assistant_response": "Ha ocurrido un error interno. Inténtalo de nuevo.",
                }

        # ── Construcción del grafo ──────────────────────────────────────────────
        builder.add_node("infer_resources", infer_resources)
        builder.add_node("plan_or_reply", plan_or_reply)

        builder.set_entry_point("infer_resources")
        builder.add_edge("infer_resources", "plan_or_reply")
        builder.set_finish_point("plan_or_reply")

        graph = builder.compile()
        return await graph.ainvoke(context)

    def _introspect_database_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Introspección directa de schema de base de datos"""
        try:
            database_service = self.factory.get_database_service()
            sql_instance = database_service.get_sql_instance(db_id)
            
            if not sql_instance:
                return None
            
            # Query básica para obtener tablas y columnas
            tables_query = """
                SELECT 
                    table_name,
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position
            """
            
            # 🔧 Usar engine con text().mappings() para obtener dicts estables
            from sqlalchemy import text
            tables = {}
            
            # Obtener engine del sql_instance de forma pública
            # Usamos get_sql_instance que devuelve SQLDatabase, y accedemos al engine
            if hasattr(sql_instance, '_engine'):
                engine = sql_instance._engine
                
                with engine.connect() as conn:
                    result = conn.execute(text(tables_query))
                    rows = [dict(row._mapping) for row in result]
                    
                    # Procesar filas como diccionarios
                    for row in rows:
                        table_name = row['table_name']
                        column_name = row['column_name']
                        data_type = row['data_type']
                        is_nullable = row['is_nullable']
                        column_default = row['column_default']
                        
                        if table_name not in tables:
                            tables[table_name] = {
                                'columns': {},
                                'primary_keys': [],
                                'foreign_keys': [],
                                'indexes': []
                            }
                        
                        tables[table_name]['columns'][column_name] = {
                            'type': data_type,
                            'nullable': is_nullable == 'YES',
                            'default': column_default,
                            'primary_key': False
                        }
            else:
                logger.warning(f"[ExplorationGraph] ⚠️ No se pudo acceder al engine para DB {db_id}")
                return None
            
            # Inferir dialecto usando API pública
            dialect = 'postgresql'  # Default assumption
            try:
                dialect = database_service.get_dialect_name(db_id) or 'postgresql'
            except Exception as e:
                logger.debug(f"[ExplorationGraph] No se pudo inferir dialecto: {e}")
                dialect = 'postgresql'
            
            logger.info(f"[ExplorationGraph] 🔍 Introspección directa: {len(tables)} tablas, dialecto: {dialect}")
            
            return {
                'tables': tables,
                'dialect': dialect
            }
            
        except Exception as e:
            logger.exception(f"[ExplorationGraph] ❌ Error introspección directa DB {db_id}: {e}")
            return None
