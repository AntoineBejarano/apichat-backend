from typing import Dict, Any, List, Optional, TypedDict
from uuid import UUID
from datetime import datetime, timezone

from langgraph.graph import StateGraph
from app.core.service_factory import ServiceFactory
from app.schemas.chat_schema import ChatMessage
from app.schemas.plan_schema import PlanModel
from app.models.app_model import App
from app.models.database_model import DatabaseConnection
from app.models.function_model import Function
from langchain_community.utilities.sql_database import SQLDatabase

import logging
import time

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
                                    dialect=introspected_schema.get('dialect', 'postgresql'),
                                    generated_at=datetime.now(timezone.utc)
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
            
            # 🔧 FIX: Asegurar que db_ids sean siempre strings para consistencia con compact_schemas
            # compact_schemas usa string keys, así que db_ids deben ser strings también
            normalized_db_ids = [str(db_id) for db_id in db_ids]
            
            return {
                **state,
                "db_ids": normalized_db_ids,  # 🔧 Siempre strings para consistencia
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
                
                # 🎯 FASE 8: Emitir propuesta de recursos si tenemos candidatos buenos
                user_message = state["message"].content
                db_ids = state.get("db_ids", [])
                apps = state.get("apps", [])
                
                # Solo emitir propuesta si tenemos recursos y el mensaje sugiere una tarea específica
                if db_ids and apps and self._should_propose_resources(user_message):
                    try:
                        # Obtener ResourceSelectorService
                        resource_selector = self.factory.get_resource_selector_service()
                        
                        # Preparar datos para el selector
                        all_dbs = []
                        for db_id in db_ids:
                            db_info = {
                                'id': str(db_id),
                                'name': f"Database {db_id[:8]}",
                                'description': f"Database connection {db_id[:8]}",
                                'table_count': 0,  # Se puede mejorar obteniendo metadata real
                                'size_mb': 0,
                                'last_updated': None,
                                'is_readonly': True,
                                'has_comments': False,
                                'has_constraints': False,
                                'has_indexes': False
                            }
                            all_dbs.append(db_info)
                        
                        all_apps = []
                        for app in apps:
                            app_info = {
                                'id': str(app.id),
                                'name': app.name,
                                'description': app.description or f"Application {app.name}",
                                'api_count': len(app.functions) if hasattr(app, 'functions') else 0,
                                'last_updated': app.updated_at.isoformat() if hasattr(app, 'updated_at') else None,
                                'requires_auth': True,
                                'has_rate_limiting': True,
                                'has_openapi_spec': True,
                                'has_examples': False,
                                'has_descriptions': True
                            }
                            all_apps.append(app_info)
                        
                        # Generar propuestas
                        proposals = await resource_selector.propose_for_explorer(user_message, all_dbs, all_apps)
                        
                        if proposals:
                            # Emitir propuesta de recursos
                            proposal_id = f"proposal_{state['chat_id']}_{int(time.time())}"
                            
                            # Formatear opciones para la UI
                            formatted_options = []
                            for i, proposal in enumerate(proposals, 1):
                                option = {
                                    "id": f"guided_option_{i}",
                                    "label": f"Opción {i}: {proposal['database']['name']} + {proposal['application']['name']}",
                                    "description": f"Score: {proposal['combined_score']:.2f} - {', '.join(proposal['selection_reasons'][:3])}",
                                    "action": f"guided_option_{i}",
                                    "data": {
                                        "database_id": proposal['database']['id'],
                                        "application_id": proposal['application']['id'],
                                        "combined_score": proposal['combined_score'],
                                        "reasons": proposal['selection_reasons']
                                    }
                                }
                                formatted_options.append(option)
                            
                            # Añadir opciones adicionales
                            formatted_options.extend([
                                {
                                    "id": "see_more",
                                    "label": "Ver más opciones",
                                    "description": "Explorar más combinaciones de recursos",
                                    "action": "see_more"
                                },
                                {
                                    "id": "explore_only",
                                    "label": "Solo explorar",
                                    "description": "Continuar en modo Explorer sin cambiar a Guided",
                                    "action": "explore_only"
                                }
                            ])
                            
                            # Emitir evento de propuesta
                            await self.factory.get_orchestrator_service().emit_resource_proposal(
                                proposal_id=proposal_id,
                                title="¿Te gustaría usar el modo Guided?",
                                description=f"He encontrado algunas combinaciones de recursos que podrían ser útiles para: '{user_message[:100]}...'",
                                options=formatted_options,
                                user_message=user_message,
                                timeout_seconds=60,
                                default_action="explore_only"
                            )
                            
                            logger.info(f"[ExplorationGraph] 🎯 Propuesta de recursos emitida: {len(proposals)} opciones")
                            
                            # Continuar con la ejecución normal (el usuario puede responder después)
                    
                    except Exception as e:
                        logger.warning(f"[ExplorationGraph] ⚠️ Error generando propuesta de recursos: {e}")
                        # Continuar sin propuesta
                
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
            
            # Obtener información básica del schema
            inspector = sql_instance.inspect()
            tables = inspector.get_table_names()
            
            schema_info = {
                "tables": tables,
                "table_count": len(tables),
                "dialect": sql_instance.dialect.name,
                "has_metadata": True
            }
            
            # Intentar obtener más metadatos si están disponibles
            try:
                # Obtener comentarios de tablas si están disponibles
                table_comments = {}
                for table in tables[:10]:  # Limitar a 10 tablas para evitar latencia
                    try:
                        comment = inspector.get_table_comment(table)
                        if comment and comment.get('text'):
                            table_comments[table] = comment['text']
                    except:
                        pass
                
                if table_comments:
                    schema_info["table_comments"] = table_comments
                    schema_info["has_comments"] = True
                
                # Obtener información de columnas para las primeras tablas
                columns_info = {}
                for table in tables[:5]:  # Limitar a 5 tablas
                    try:
                        columns = inspector.get_columns(table)
                        columns_info[table] = [
                            {
                                "name": col["name"],
                                "type": str(col["type"]),
                                "nullable": col.get("nullable", True),
                                "default": col.get("default"),
                                "comment": col.get("comment")
                            }
                            for col in columns[:20]  # Limitar a 20 columnas por tabla
                        ]
                    except:
                        pass
                
                if columns_info:
                    schema_info["columns_info"] = columns_info
                
            except Exception as e:
                logger.debug(f"[ExplorationGraph] ⚠️ No se pudieron obtener metadatos adicionales: {e}")
            
            return schema_info
            
        except Exception as e:
            logger.error(f"[ExplorationGraph] ❌ Error introspeccionando schema de DB {db_id}: {e}")
            return None
    
    def _should_propose_resources(self, user_message: str) -> bool:
        """
        Determina si se debe proponer recursos basándose en el mensaje del usuario.
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            True si se debe proponer recursos, False en caso contrario
        """
        message_lower = user_message.lower()
        
        # Palabras clave que sugieren una tarea específica
        task_keywords = [
            "buscar", "encontrar", "obtener", "extraer", "consultar", "analizar",
            "crear", "insertar", "actualizar", "modificar", "eliminar", "borrar",
            "generar", "calcular", "resumir", "comparar", "filtrar", "ordenar",
            "agrupar", "contar", "sumar", "promedio", "máximo", "mínimo",
            "reporte", "dashboard", "exportar", "importar", "sincronizar"
        ]
        
        # Palabras clave que sugieren exploración general
        exploration_keywords = [
            "qué hay", "qué contiene", "muéstrame", "explora", "investiga",
            "descubre", "revisa", "examina", "explora", "navega"
        ]
        
        # Si el mensaje contiene palabras de tarea específica, proponer recursos
        if any(keyword in message_lower for keyword in task_keywords):
            return True
        
        # Si el mensaje es muy general o solo exploratorio, no proponer
        if any(keyword in message_lower for keyword in exploration_keywords):
            return False
        
        # Si el mensaje es corto o muy general, no proponer
        if len(user_message.split()) <= 3:
            return False
        
        # Por defecto, proponer si el mensaje parece ser una pregunta o solicitud
        return "?" in user_message or any(word in message_lower for word in ["puedes", "ayúdame", "necesito", "quiero"])
