import time
import logging
from typing import Dict, Any, List
from uuid import UUID

from app.core.service_factory import ServiceFactory
from app.schemas.plan_schema import UserPlanOut
from ..state.exploration_state import ExplorationState
from ..utils.performance_metrics import PerformanceMetrics
from ..utils.resource_proposal import ResourceProposalHelper

logger = logging.getLogger(__name__)


class PlanningNode:
    """Nodo para generar planes usando OpenAI y manejar propuestas de recursos"""
    
    def __init__(self, factory: ServiceFactory, max_schema_chars: int = 80000):
        self.factory = factory
        self.max_schema_chars = max_schema_chars
        self.resource_helper = ResourceProposalHelper()
    
    async def run(self, state: ExplorationState, performance_metrics: PerformanceMetrics) -> ExplorationState:
        """Ejecuta la generación del plan"""
        node_start_time = time.time()
        
        try:
            logger.info("[PlanningNode] 🧠 Calling OpenAI with cache validation...")
            
            # Obtener datos del estado
            compact_schemas = state.get("compact_schemas", {})
            cache_status = state.get("cache_status", {})
            user_message = state["message"].content
            db_ids = state.get("db_ids", [])
            apps = state.get("apps", [])
            
            # Emitir propuesta de recursos si es apropiado
            if db_ids and apps and self.resource_helper.should_propose_resources(user_message):
                await self._emit_resource_proposal(state, user_message, db_ids, apps)
            
            # Construir schema compacto combinado para el LLM
            db_schema = self._build_combined_schema(compact_schemas)
            
            # Consultar AI con schema compacto garantizado
            logger.info(f"[PlanningNode] 🤖 Consultando AI con schema compacto ({len(db_schema) if db_schema else 0} chars)")
            result = await self.factory.get_openai_service().plan_actions(
                chat_id=state["chat_id"],
                user_message=state["message"],
                db_schema=db_schema,
                available_functions=state.get("functions", []),
                available_mcp_tools=None,
                history=state.get("history", []),
                db_ids=[db_id if isinstance(db_id, UUID) else UUID(str(db_id)) for db_id in compact_schemas.keys()] if compact_schemas else [],
                use_enriched_context=False,
            )
            
            # Procesar resultado
            if result.get("actions"):
                plan = PlanModel.model_validate(result)
                logger.info("[PlanningNode] ✅ Plan generado (%d acciones)", len(plan.actions))
                
                # Registrar métricas
                node_time = time.time() - node_start_time
                performance_metrics.record_node_time("openai_plan", node_time)
                
                return {**state, "plan": plan}
            
            elif result.get("assistant_response"):
                logger.info("[PlanningNode] ✅ Respuesta simple generada")
                
                # Registrar métricas
                node_time = time.time() - node_start_time
                performance_metrics.record_node_time("react_think", node_time)
                
                return {**state, "assistant_response": result["assistant_response"]}
            
            else:
                # Fallback
                logger.warning("[PlanningNode] ⚠️ Modelo no devolvió contenido")
                
                # Registrar métricas
                node_time = time.time() - node_start_time
                performance_metrics.record_node_time("react_think", node_time)
                
                return {**state, "assistant_response": "Disculpa, no he entendido tu mensaje."}
                
        except Exception as e:
            logger.exception("[PlanningNode] ❌ Error generando plan/respuesta")
            return {
                **state,
                "error": str(e),
                "assistant_response": "Ha ocurrido un error interno. Inténtalo de nuevo.",
            }
    
    def _build_combined_schema(self, compact_schemas: Dict[str, str]) -> str:
        """Construye el schema compacto combinado para el LLM"""
        if not compact_schemas:
            logger.warning("[PlanningNode] ⚠️ No compact_schemas disponible - continuando sin schema")
            return None
        
        # Combinar todos los schemas compactos
        schema_parts = []
        for db_id, compact_schema in compact_schemas.items():
            if compact_schema:
                if isinstance(compact_schema, str) and compact_schema.strip():
                    schema_parts.append(f"-- DATABASE {db_id} --")
                    schema_parts.append(compact_schema)
                    schema_parts.append("")
                elif isinstance(compact_schema, dict) and compact_schema.get("compact"):
                    compact_value = compact_schema.get("compact")
                    if isinstance(compact_value, str) and compact_value.strip():
                        schema_parts.append(f"-- DATABASE {db_id} --")
                        schema_parts.append(compact_value)
                        schema_parts.append("")
        
        if schema_parts:
            db_schema = "\n".join(schema_parts)
            
            # Límite de tamaño del prompt para evitar tokens excesivos
            if len(db_schema) > self.max_schema_chars:
                logger.warning(f"[PlanningNode] ⚠️ Schema muy grande ({len(db_schema)} chars), truncando a {self.max_schema_chars}")
                db_schema = db_schema[:self.max_schema_chars] + "\n-- [SCHEMA TRUNCATED DUE TO SIZE] --"
            
            logger.info(f"[PlanningNode] ✅ Schema compacto listo: {len(compact_schemas)} DBs, {len(db_schema)} chars")
            return db_schema
        else:
            logger.warning("[PlanningNode] ⚠️ Compact schemas vacíos")
            return None
    
    async def _emit_resource_proposal(self, state: ExplorationState, user_message: str, db_ids: List[str], apps: List[Any]):
        """Emite una propuesta de recursos para el modo Guided"""
        try:
            # Obtener ResourceSelectorService
            resource_selector = self._get_service_lazy("resource_selector_service", self.factory.get_resource_selector_service)
            if not resource_selector:
                return
            
            # Preparar datos para el selector
            all_dbs = self.resource_helper.prepare_database_info(db_ids)
            all_apps = self.resource_helper.prepare_application_info(apps)
            
            # Generar propuestas
            proposals = []
            try:
                proposals = await resource_selector.propose_for_explorer(user_message, all_dbs, all_apps)
            except Exception as e:
                logger.warning(f"[PlanningNode] ⚠️ Error generando propuestas: {e}")
                proposals = []
            
            if proposals:
                # Emitir propuesta de recursos
                proposal_id = f"proposal_{state['chat_id']}_{int(time.time())}"
                
                # Formatear opciones para la UI
                formatted_options = self.resource_helper.format_proposal_options(proposals)
                
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
                
                logger.info(f"[PlanningNode] 🎯 Propuesta de recursos emitida: {len(proposals)} opciones")
                
        except Exception as e:
            logger.warning(f"[PlanningNode] ⚠️ Error generando propuesta de recursos: {e}")
    
    def _get_service_lazy(self, service_name: str, service_factory_method):
        """Obtiene un servicio solo cuando se necesita"""
        try:
            return service_factory_method()
        except Exception as e:
            logger.warning(f"[PlanningNode] ⚠️ Error obteniendo {service_name}: {e}")
            return None
