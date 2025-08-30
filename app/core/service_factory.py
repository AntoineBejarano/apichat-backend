"""
🏭 Service Factory Refactorizado: Factory principal simplificado

Factory principal que coordina todas las sub-factories especializadas,
reemplazando el ServiceFactory monolítico de 400+ líneas.
"""

import logging
from typing import Optional, Dict, Any, Union
from fastapi import Request, WebSocket

from app.models.user_model import User
from app.core.factories.core_services_factory import CoreServicesFactory
from app.core.factories.ai_services_factory import AIServicesFactory
from app.core.factories.cache_services_factory import CacheServicesFactory
from app.core.factories.data_services_factory import DataServicesFactory
from app.core.factories.management_services_factory import ManagementServicesFactory
from app.core.factories.background_services_factory import BackgroundServicesFactory

logger = logging.getLogger(__name__)


class ServiceFactory:
    """
    🏭 Service Factory Refactorizado (100 líneas)
    
    Coordina todas las sub-factories especializadas:
    - Core Services (DB, Auth, Config)
    - AI Services (Agents, Mode Detection)
    - Cache Services (Response, Redis, Schema)
    - Data Services (Database, App, Strategy)
    - Management Services (User, Org, Agent)
    - Background Services (Jobs, Scheduler, Queue)
    """
    
    def __init__(self, request: Union[Request, WebSocket], user: Optional[User] = None):
        """
        Inicializa el Service Factory refactorizado
        
        Args:
            request: Request de FastAPI o WebSocket
            user: Usuario autenticado (opcional para WebSockets)
        """
        self.request = request
        self.user = user
        
        # 🔧 NUEVO: Inicializar atributo db para servicios del orquestador
        try:
            from app.core.database import SessionLocal
            self.db = SessionLocal()
            logger.info(f"[ServiceFactory] ✅ Sesión de DB inicializada")
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error inicializando sesión de DB: {e}")
            self.db = None
        
        # 🔧 NUEVO: Atributos para gestión de fases (NO inicializar sub-factories aquí)
        self.readiness_registry = None
        self.phase_manager = None
        
        # 🔧 NUEVO: Flags para control de fases
        self._phase_1_core_ready = False
        self._phase_2_ai_ready = False
        self._phase_3_execution_ready = False
        self._phase_4_orchestrator_ready = False
        
        logger.info(f"[ServiceFactory] ✅ Inicialización básica completada (ligera)")
    
    # ─────────────────────────────────────────────
    #   🔧 MÉTODOS DE PREPARACIÓN POR FASES
    # ─────────────────────────────────────────────
    
    async def prepare_phase_1_core(self):
        """Prepara servicios core (DB, Auth, Config)"""
        if self._phase_1_core_ready:
            logger.info(f"[ServiceFactory] ✅ Fase 1 (Core) ya está lista")
            return
        
        try:
            logger.info(f"[ServiceFactory] 🚀 Iniciando Fase 1: Servicios Core")
            
            # Inicializar sub-factories core
            self.core = CoreServicesFactory(self)
            
            # Inicializar servicios de gestión de fases
            from app.services.management import ReadinessRegistry, PhaseDependencyManager
            self.readiness_registry = ReadinessRegistry(self)
            self.phase_manager = PhaseDependencyManager()
            
            # Marcar fase como completada
            await self.phase_manager.mark_phase_in_progress('phase_1_core')
            await self.phase_manager.mark_phase_completed('phase_1_core')
            
            self._phase_1_core_ready = True
            logger.info(f"[ServiceFactory] ✅ Fase 1 (Core) completada")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error en Fase 1 (Core): {e}")
            raise
    
    def _initialize_core_services(self):
        """Método auxiliar para inicializar servicios core (usado en tests)"""
        return CoreServicesFactory(self)
    
    async def prepare_phase_2_ai(self):
        """Prepara servicios AI (requiere core listo)"""
        if self._phase_2_ai_ready:
            logger.info(f"[ServiceFactory] ✅ Fase 2 (AI) ya está lista")
            return
        
        try:
            logger.info(f"[ServiceFactory] 🚀 Iniciando Fase 2: Servicios AI")
            
            # Asegurar que Fase 1 esté lista
            await self.prepare_phase_1_core()
            
            # Inicializar sub-factories AI
            self.ai = AIServicesFactory(self)
            
            # Marcar fase como completada
            await self.phase_manager.mark_phase_in_progress('phase_2_ai')
            await self.phase_manager.mark_phase_completed('phase_2_ai')
            
            self._phase_2_ai_ready = True
            logger.info(f"[ServiceFactory] ✅ Fase 2 (AI) completada")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error en Fase 2 (AI): {e}")
            raise
    
    def _initialize_ai_services(self):
        """Método auxiliar para inicializar servicios AI (usado en tests)"""
        return AIServicesFactory(self)
    
    async def prepare_phase_3_execution(self):
        """Prepara servicios de ejecución (requiere AI listo)"""
        if self._phase_3_execution_ready:
            logger.info(f"[ServiceFactory] ✅ Fase 3 (Execution) ya está lista")
            return
        
        try:
            logger.info(f"[ServiceFactory] 🚀 Iniciando Fase 3: Servicios de Ejecución")
            
            # Asegurar que Fase 2 esté lista
            await self.prepare_phase_2_ai()
            
            # Inicializar sub-factories de ejecución
            self.execution_services = True
            
            # Marcar fase como completada
            await self.phase_manager.mark_phase_in_progress('phase_3_execution')
            await self.phase_manager.mark_phase_completed('phase_3_execution')
            
            self._phase_3_execution_ready = True
            logger.info(f"[ServiceFactory] ✅ Fase 3 (Execution) completada")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error en Fase 3 (Execution): {e}")
            raise
    
    def _initialize_execution_services(self):
        """Método auxiliar para inicializar servicios de ejecución (usado en tests)"""
        return True
    
    async def prepare_phase_4_orchestrator(self):
        """Prepara servicios del orquestador (requiere todas las fases anteriores)"""
        if self._phase_4_orchestrator_ready:
            logger.info(f"[ServiceFactory] ✅ Fase 4 (Orchestrator) ya está lista")
            return
        
        try:
            logger.info(f"[ServiceFactory] 🚀 Iniciando Fase 4: Servicios del Orquestador")
            
            # Asegurar que todas las fases anteriores estén listas
            await self.prepare_phase_3_execution()
            
            # Inicializar sub-factories restantes
            self.cache = CacheServicesFactory(self)
            self.data = DataServicesFactory(self)
            self.management = ManagementServicesFactory(self)
            self.background = BackgroundServicesFactory(self)
            
            # Marcar fase como completada
            await self.phase_manager.mark_phase_in_progress('phase_4_orchestrator')
            await self.phase_manager.mark_phase_completed('phase_4_orchestrator')
            
            self._phase_4_orchestrator_ready = True
            logger.info(f"[ServiceFactory] ✅ Fase 4 (Orchestrator) completada")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error en Fase 4 (Orchestrator): {e}")
            raise
    
    def _initialize_orchestrator_services(self):
        """Método auxiliar para inicializar servicios del orquestador (usado en tests)"""
        return {
            'cache': CacheServicesFactory(self),
            'data': DataServicesFactory(self),
            'management': ManagementServicesFactory(self),
            'background': BackgroundServicesFactory(self)
        }
    
    async def prepare_for_chat(self):
        """Prepara factory para uso en chat (Fases 1-3)"""
        try:
            await self.prepare_phase_1_core()
            await self.prepare_phase_2_ai()
            await self.prepare_phase_3_execution()
            
            logger.info(f"[ServiceFactory] ✅ Factory preparado para chat")
            return True
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error preparando para chat: {e}")
            return False
    
    async def prepare_for_orchestrator(self):
        """Prepara factory para orquestador (todas las fases)"""
        try:
            await self.prepare_phase_4_orchestrator()
            
            logger.info(f"[ServiceFactory] ✅ Factory preparado para orquestador")
            return True
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error preparando para orquestador: {e}")
            return False
    
    # ─────────────────────────────────────────────
    #   🔧 CORE SERVICES (Delegación a CoreServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_database_service(self):
        """Obtiene el servicio de base de datos"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        return self.core.get_database_service()
    
    def get_database_session(self):
        """Obtiene la sesión de base de datos directamente"""
        try:
            from app.core.database import SessionLocal
            return SessionLocal()
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo sesión de DB: {e}")
            return None
    
    def get_auth_service(self):
        """Obtiene el servicio de autenticación"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        return self.core.get_auth_service()
    
    def get_config_service(self):
        """Obtiene el servicio de configuración"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        return self.core.get_config_service()
    
    def get_session_service(self):
        """Obtiene el servicio de sesión"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        return self.core.get_session_service()
    
    def get_ws_emitter(self):
        """Obtiene el emisor de WebSocket"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        return self.core.get_ws_emitter()
    
    def get_openai_service(self):
        """Obtiene el servicio de OpenAI"""
        if not self._phase_1_core_ready:
            raise RuntimeError("Fase 1 (Core) no está lista. Llama a prepare_phase_1_core() primero")
        
        # 🔧 NUEVO: Preparar automáticamente las fases necesarias para OpenAI
        try:
            if not self._phase_2_ai_ready:
                logger.info("[ServiceFactory] 🔧 Preparando automáticamente Fase 2 (AI) para OpenAI")
                # Usar asyncio.run para ejecutar la función asíncrona en contexto síncrono
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si ya hay un loop corriendo, usar create_task
                        loop.create_task(self.prepare_phase_2_ai())
                    else:
                        # Si no hay loop, usar run
                        asyncio.run(self.prepare_phase_2_ai())
                except RuntimeError:
                    # Si no hay loop, crear uno nuevo
                    asyncio.run(self.prepare_phase_2_ai())
            
            if not self._phase_3_execution_ready:
                logger.info("[ServiceFactory] 🔧 Preparando automáticamente Fase 3 (Execution) para OpenAI")
                # Usar asyncio.run para ejecutar la función asíncrona en contexto síncrono
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Si ya hay un loop corriendo, usar create_task
                        loop.create_task(self.prepare_phase_3_execution())
                    else:
                        # Si no hay loop, usar run
                        asyncio.run(self.prepare_phase_3_execution())
                except RuntimeError:
                    # Si no hay loop, crear uno nuevo
                    asyncio.run(self.prepare_phase_3_execution())
                
        except Exception as e:
            logger.warning(f"[ServiceFactory] ⚠️ No se pudo preparar fases automáticamente para OpenAI: {e}")
            # Continuar sin las fases adicionales
        
        return self.core.get_openai_service()
    
    def get_orchestrator_service(self):
        """Obtiene el servicio orquestador"""
        if not self._phase_4_orchestrator_ready:
            raise RuntimeError("Fase 4 (Orchestrator) no está lista. Llama a prepare_for_orchestrator() primero")
        
        try:
            from app.services.orchestrator.orchestrator_service import OrchestratorService
            return OrchestratorService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo OrchestratorService: {e}")
            return None
    
    def get_chat_service(self):
        """Obtiene el servicio de chat"""
        if not self._phase_3_execution_ready:
            raise RuntimeError("Fase 3 (Execution) no está lista. Llama a prepare_for_chat() primero")
        
        try:
            from app.services.data.chat_service import ChatService
            return ChatService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ChatService: {e}")
            return None
    
    def get_chat_history_service(self):
        """Obtiene el servicio de historial de chat"""
        if not self._phase_3_execution_ready:
            raise RuntimeError("Fase 3 (Execution) no está lista. Llama a prepare_for_chat() primero")
        
        try:
            from app.services.data.chat_history_service import ChatHistoryService
            return ChatHistoryService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ChatHistoryService: {e}")
            return None
    
    def get_decision_manager(self):
        """Obtiene el gestor de decisiones"""
        if not self._phase_3_execution_ready:
            raise RuntimeError("Fase 3 (Execution) no está lista. Llama a prepare_for_chat() primero")
        
        try:
            from app.services.orchestrator.decision_manager import DecisionManager
            return DecisionManager(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo DecisionManager: {e}")
            return None
    
    def get_resource_proposal_service(self):
        """Obtiene el servicio de propuestas de recursos"""
        if not self._phase_3_execution_ready:
            raise RuntimeError("Fase 3 (Execution) no está lista. Llama a prepare_for_chat() primero")
        
        try:
            from app.services.orchestrator.resource_proposal_service import ResourceProposalService
            return ResourceProposalService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ResourceProposalService: {e}")
            return None
    
    # 🔧 NUEVOS SERVICIOS CRÍTICOS PARA ORCHESTRATOR
    def get_advanced_telemetry_service(self):
        """Obtiene el servicio de telemetría avanzada"""
        if not self._phase_2_ai_ready:
            raise RuntimeError("Fase 2 (AI) no está lista. Llama a prepare_phase_2_ai() primero")
        
        try:
            from app.services.monitoring.performance_monitoring_service import PerformanceMonitoringService
            return PerformanceMonitoringService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo PerformanceMonitoringService: {e}")
            return None
    
    def get_function_service(self):
        """Obtiene el servicio de funciones"""
        if not self._phase_3_execution_ready:
            raise RuntimeError("Fase 3 (Execution) no está lista. Llama a prepare_for_chat() primero")
        
        try:
            from app.services.execution.function_service import FunctionService
            return FunctionService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo FunctionService: {e}")
            return None
    
    def get_mcp_integration_service(self):
        """Obtiene el servicio de integración MCP"""
        if not self._phase_4_orchestrator_ready:
            raise RuntimeError("Fase 4 (Orchestrator) no está lista. Llama a prepare_for_orchestrator() primero")
        
        try:
            from app.services.integration.mcp_integration_service import MCPIntegrationService
            return MCPIntegrationService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo MCPIntegrationService: {e}")
            return None
    
    def get_detailed_schema_cache_service(self):
        """Obtiene el servicio de cache de esquemas detallados"""
        if not self._phase_4_orchestrator_ready:
            raise RuntimeError("Fase 4 (Orchestrator) no está lista. Llama a prepare_for_orchestrator() primero")
        
        try:
            from app.services.context.detailed_schema_cache_service import DetailedSchemaCacheService
            return DetailedSchemaCacheService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo DetailedSchemaCacheService: {e}")
            return None
    
    def get_app_descriptor_cache_service(self):
        """Obtiene el servicio de cache de descriptores de apps"""
        if not self._phase_4_orchestrator_ready:
            raise RuntimeError("Fase 4 (Orchestrator) no está lista. Llama a prepare_for_orchestrator() primero")
        
        try:
            from app.services.context.app_descriptor_cache_service import AppDescriptorCacheService
            return AppDescriptorCacheService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo AppDescriptorCacheService: {e}")
            return None
    
    def get_vector_search_service(self):
        """Obtiene el servicio de búsqueda vectorial"""
        try:
            from app.services.context.vector_search_service import VectorSearchService
            return VectorSearchService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo VectorSearchService: {e}")
            return None
    
    def get_schema_explorer_service(self):
        """Obtiene el servicio de exploración de esquemas"""
        try:
            from app.services.context.schema_explorer_service import SchemaExplorerService
            return SchemaExplorerService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo SchemaExplorerService: {e}")
            return None
    
    def get_guided_service(self):
        """Obtiene el servicio de grafos guiados"""
        try:
            from app.services.execution.graphs.exploration_graph import ExplorationGraph
            return ExplorationGraph(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ExplorationGraph: {e}")
            return None
    
    def get_resource_selector_service(self):
        """Obtiene el servicio de selección de recursos"""
        try:
            from app.services.ai.resource_priority_service import ResourcePriorityService
            return ResourcePriorityService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ResourcePriorityService: {e}")
            return None
    
    def get_plan_builder_service(self):
        """Obtiene el servicio de construcción de planes"""
        try:
            from app.services.ai.plan_builder_service import PlanBuilderService
            return PlanBuilderService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo PlanBuilderService: {e}")
            return None
    
    def get_performance_monitoring_service(self):
        """Obtiene el servicio de monitoreo de performance"""
        try:
            from app.services.monitoring.performance_monitoring_service import PerformanceMonitoringService
            return PerformanceMonitoringService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo PerformanceMonitoringService: {e}")
            return None
    
    def get_usage_service(self):
        """Obtiene el servicio de uso"""
        try:
            from app.services.data.usage_service import UsageService
            return UsageService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo UsageService: {e}")
            return None
    
    def get_executed_strategy_service(self):
        """Obtiene el servicio de estrategias ejecutadas"""
        try:
            from app.services.data.executed_strategy_service import ExecutedStrategyService
            return ExecutedStrategyService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ExecutedStrategyService: {e}")
            return None
    
    def get_execution_engine_service(self):
        """Obtiene el servicio del motor de ejecución"""
        try:
            from app.services.ai.execution_planner_service import ExecutionPlannerService
            return ExecutionPlannerService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ExecutionPlannerService: {e}")
            return None
    
    def get_prompt_engineering_service(self):
        """Obtiene el servicio de ingeniería de prompts"""
        try:
            from app.services.ai.prompt_engineering_service import PromptEngineeringService
            return PromptEngineeringService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo PromptEngineeringService: {e}")
            return None
    
    def set_current_chat_id(self, chat_id: str):
        """Establece el ID del chat actual para tracking"""
        self.current_chat_id = chat_id
    
    # ─────────────────────────────────────────────
    #   🧠 AI SERVICES (Delegación a AIServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_agent_service(self):
        """Obtiene el servicio de gestión de agentes"""
        return self.ai.get_agent_service()
    
    def get_mode_detection_service(self):
        """Obtiene el servicio de detección de modo"""
        return self.ai.get_mode_detection_service()
    
    def get_mode_transition_service(self):
        """Obtiene el servicio de transiciones de modo"""
        return self.ai.get_mode_transition_service()
    
    def get_mode_transition_orchestrator(self):
        """Obtiene el orquestador de transiciones de modo"""
        return self.ai.get_mode_transition_orchestrator()
    
    def get_agent_router_service(self):
        """Obtiene el servicio de enrutamiento de agentes"""
        return self.ai.get_agent_router_service()
    
    def get_smart_ai_service(self):
        """Obtiene el servicio de Smart AI"""
        return self.ai.get_smart_ai_service()
    
    def get_intent_classifier_service(self):
        """Obtiene el servicio de clasificación de intenciones"""
        return self.ai.get_intent_classifier_service()
    
    def get_smart_rephrase_service(self):
        """Obtiene el servicio de rephrase inteligente"""
        return self.ai.get_smart_rephrase_service()
    
    def get_smart_ai_orchestrator(self):
        """Obtiene el orquestador de Smart AI"""
        return self.ai.get_smart_ai_orchestrator()
    
    def get_execution_planner_service(self):
        """Obtiene el servicio de planificación de ejecución"""
        return self.ai.get_execution_planner_service()
    
    def get_mode_detection_logger(self):
        """Obtiene el logger de detección de modo"""
        return self.ai.get_mode_detection_logger()
    
    def get_prompt_builder_service(self):
        """Obtiene el servicio de construcción de prompts"""
        return self.ai.get_prompt_builder_service()
    
    def get_resource_priority_service(self):
        """Obtiene el servicio de priorización de recursos"""
        return self.ai.get_resource_priority_service()
    
    def get_mode_indicator_service(self):
        """Obtiene el servicio de indicadores de modo"""
        return self.ai.get_mode_indicator_service()
    
    # ─────────────────────────────────────────────
    #   🚀 FASE 7: PRE-CARGA INTELIGENTE Y UX (Delegación a AIServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_intelligent_preload_service(self):
        """Obtiene el servicio de pre-carga inteligente"""
        return self.ai.get_intelligent_preload_service()
    
    def get_smart_fallback_service(self):
        """Obtiene el servicio de smart fallbacks"""
        return self.ai.get_smart_fallback_service()
    
    def get_performance_monitoring_service(self):
        """Obtiene el servicio de monitoreo de performance"""
        return self.ai.get_performance_monitoring_service()
    
    def get_user_experience_service(self):
        """Obtiene el servicio de experiencia de usuario"""
        return self.ai.get_user_experience_service()
    
    # ─────────────────────────────────────────────
    #   ⚡ CACHE SERVICES (Delegación a CacheServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_response_cache_service(self):
        """Obtiene el servicio de cache de respuestas"""
        return self.cache.get_response_cache_service()
    
    def get_response_pre_generation_service(self):
        """Obtiene el servicio de pre-generación de respuestas"""
        return self.cache.get_response_pre_generation_service()
    
    def get_instant_response_service(self):
        """Obtiene el servicio de respuestas instantáneas"""
        return self.cache.get_instant_response_service()
    
    def get_redis_schema_cache(self):
        """Obtiene el cache de Redis para esquemas"""
        return self.cache.get_redis_schema_cache()
    
    def get_detailed_schema_cache_service(self):
        """Obtiene el servicio de cache de esquemas detallados"""
        return self.cache.get_detailed_schema_cache_service()
    
    def get_schema_refresh_service(self):
        """Obtiene el servicio de refresco de esquemas"""
        return self.cache.get_schema_refresh_service()
    
    def get_schema_maintenance_service(self):
        """Obtiene el servicio de mantenimiento de esquemas"""
        return self.cache.get_schema_maintenance_service()
    
    # ─────────────────────────────────────────────
    #   🧠 FASE 8: CUSTOM SYSTEM PROMPTS INTELIGENTES
    # ─────────────────────────────────────────────
    
    def get_prompt_builder_service(self):
        """Obtiene el servicio de construcción de prompts"""
        return self.ai.get_prompt_builder_service()
    
    def get_premium_prompt_service(self):
        """Obtiene el servicio de prompts premium"""
        return self.ai.get_premium_prompt_service()
    
    def get_pattern_learning_service(self):
        """Obtiene el servicio de aprendizaje de patrones"""
        return self.ai.get_pattern_learning_service()
    
    # ─────────────────────────────────────────────
    #   🎯 FASE 9: PRIORIZACIÓN DE RECURSOS Y FALLBACK INTELIGENTE
    # ─────────────────────────────────────────────
    
    def get_resource_priority_service(self):
        """Obtiene el servicio de priorización de recursos"""
        return self.ai.get_resource_priority_service()
    
    def get_smart_fallback_service(self):
        """Obtiene el servicio de fallback inteligente"""
        return self.ai.get_smart_fallback_service()
    
    # ─────────────────────────────────────────────
    #   📊 DATA SERVICES (Delegación a DataServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_app_service(self):
        """Obtiene el servicio de aplicaciones"""
        return self.data.get_app_service()
    
    def get_strategy_service(self):
        """Obtiene el servicio de estrategias"""
        return self.data.get_strategy_service()
    
    def get_integration_service(self):
        """Obtiene el servicio de integraciones"""
        return self.data.get_integration_service()
    
    def get_api_cache_service(self):
        """Obtiene el servicio de cache de APIs"""
        return self.data.get_api_cache_service()
    
    def get_api_generation_service(self):
        """Obtiene el servicio de generación de APIs"""
        return self.data.get_api_generation_service()
    
    # ─────────────────────────────────────────────
    #   👥 MANAGEMENT SERVICES (Delegación a ManagementServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_user_service(self):
        """Obtiene el servicio de gestión de usuarios"""
        return self.management.get_user_service()
    
    def get_organization_service(self):
        """Obtiene el servicio de gestión de organizaciones"""
        return self.management.get_organization_service()
    
    def get_permission_service(self):
        """Obtiene el servicio de gestión de permisos"""
        return self.management.get_permission_service()
    
    def get_role_service(self):
        """Obtiene el servicio de gestión de roles"""
        return self.management.get_role_service()
    
    def get_audit_service(self):
        """Obtiene el servicio de auditoría"""
        return self.management.get_audit_service()
    
    def get_schema_performance_service(self):
        """Obtiene el servicio de performance de schemas"""
        return self.management.get_schema_performance_service()
    
    def get_resource_selection_service(self):
        """Obtiene el servicio de selección de recursos prioritarios"""
        try:
            from app.services.management.resource_selection_service import ResourceSelectionService
            return ResourceSelectionService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ResourceSelectionService: {e}")
            return None

    def get_environment_preparation_orchestrator(self):
        """Obtiene el orquestador de preparación del entorno"""
        try:
            from app.services.management.environment_preparation_orchestrator import EnvironmentPreparationOrchestrator
            return EnvironmentPreparationOrchestrator(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo EnvironmentPreparationOrchestrator: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   🚀 API TRIGGERING SERVICES (Nuevos servicios)
    # ─────────────────────────────────────────────
    
    def get_api_triggering_config_service(self):
        """Obtiene el servicio de configuración de triggering de APIs"""
        try:
            from app.services.management.api_triggering_config_service import APITriggeringConfigService
            return APITriggeringConfigService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo APITriggeringConfigService: {e}")
            return None
    
    def get_extensible_embedding_service(self):
        """Obtiene el servicio de embeddings extensible"""
        try:
            from app.services.context.extensible_embedding_service import ExtensibleEmbeddingService
            return ExtensibleEmbeddingService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo ExtensibleEmbeddingService: {e}")
            return None
    
    def get_unified_vector_search_service(self):
        """Obtiene el servicio de búsqueda vectorial unificada"""
        try:
            from app.services.context.unified_vector_search_service import UnifiedVectorSearchService
            return UnifiedVectorSearchService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo UnifiedVectorSearchService: {e}")
            return None
    
    def get_api_triggering_service(self):
        """Obtiene el servicio de triggering automático de APIs"""
        try:
            from app.services.ai.api_triggering_service import APITriggeringService
            return APITriggeringService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo APITriggeringService: {e}")
            return None
    
    def get_unified_chat_service(self):
        """Obtiene el servicio de chat unificado"""
        try:
            from app.services.ai.unified_chat_service import UnifiedChatService
            return UnifiedChatService(self)
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo UnifiedChatService: {e}")
            return None
    
    # ─────────────────────────────────────────────
    #   🔄 BACKGROUND SERVICES (Delegación a BackgroundServicesFactory)
    # ─────────────────────────────────────────────
    
    def get_background_task_service(self):
        """Obtiene el servicio de tareas en background"""
        return self.background.get_background_task_service()
    
    def get_scheduler_service(self):
        """Obtiene el servicio de programación de tareas"""
        return self.background.get_scheduler_service()
    
    def get_queue_service(self):
        """Obtiene el servicio de gestión de colas"""
        return self.background.get_queue_service()
    
    def get_worker_service(self):
        """Obtiene el servicio de workers"""
        return self.background.get_worker_service()
    
    def get_notification_service(self):
        """Obtiene el servicio de notificaciones"""
        return self.background.get_notification_service()
    
    def get_email_service(self):
        """Obtiene el servicio de email"""
        return self.background.get_email_service()
    
    # ─────────────────────────────────────────────
    #   📊 MÉTODOS DE INFORMACIÓN Y DIAGNÓSTICO
    # ─────────────────────────────────────────────
    
    def get_factory_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado completo de todas las factories
        
        Returns:
            Diccionario con información de todas las factories
        """
        try:
            return {
                "main_factory": {
                    "class": self.__class__.__name__,
                    "user_id": str(self.user.id),
                    "request_available": self.request is not None
                },
                "sub_factories": {
                    "core": self.core.get_factory_info(),
                    "ai": self.ai.get_factory_info(),
                    "cache": self.cache.get_factory_info(),
                    "data": self.data.get_factory_info(),
                    "management": self.management.get_factory_info(),
                    "background": self.background.get_factory_info()
                }
            }
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error obteniendo estado: {e}")
            return {"error": str(e)}
    
    def clear_all_caches(self):
        """Limpia el cache de todas las sub-factories"""
        try:
            logger.info("[ServiceFactory] 🧹 Limpiando cache de todas las factories")
            
            self.core._clear_service_cache()
            self.ai._clear_service_cache()
            self.cache._clear_service_cache()
            self.data._clear_service_cache()
            self.management._clear_service_cache()
            self.background._clear_service_cache()
            
            logger.info("[ServiceFactory] ✅ Cache de todas las factories limpiado")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error limpiando cache: {e}")
    
    def reset_all_factories(self):
        """Resetea todas las sub-factories"""
        try:
            logger.info("[ServiceFactory] 🔄 Reseteando todas las factories")
            
            self.core._reset_factory()
            self.ai._reset_factory()
            self.cache._reset_factory()
            self.data._reset_factory()
            self.management._reset_factory()
            self.background._reset_factory()
            
            logger.info("[ServiceFactory] ✅ Todas las factories reseteadas")
            
        except Exception as e:
            logger.error(f"[ServiceFactory] ❌ Error reseteando factories: {e}")
    
    # ─────────────────────────────────────────────
    #   🚀 MÉTODOS PARA API TRIGGERING SYSTEM
    # ─────────────────────────────────────────────
    
    def get_api_triggering_config_service(self):
        """Obtiene el servicio de configuración de API triggering"""
        from app.services.management.api_triggering_config_service import APITriggeringConfigService
        return APITriggeringConfigService(self)
    
    def get_extensible_embedding_service(self):
        """Obtiene el servicio de embeddings extensible"""
        from app.services.context.extensible_embedding_service import ExtensibleEmbeddingService
        return ExtensibleEmbeddingService(self)
    
    def get_unified_vector_search_service(self):
        """Obtiene el servicio de búsqueda vectorial unificada"""
        from app.services.context.unified_vector_search_service import UnifiedVectorSearchService
        return UnifiedVectorSearchService(self)
    
    def get_api_triggering_service(self):
        """Obtiene el servicio de API triggering"""
        from app.services.ai.api_triggering_service import APITriggeringService
        return APITriggeringService(self)
    
    def get_unified_chat_service(self):
        """Obtiene el servicio de chat unificado"""
        from app.services.ai.unified_chat_service import UnifiedChatService
        return UnifiedChatService(self)
    
    def get_embedding_adapter(self):
        """Obtiene el adaptador de embeddings"""
        return self.core.get_embedding_adapter()
    
    def get_vector_service(self):
        """Obtiene el servicio vectorial"""
        return self.data.get_vector_service()
    
    def get_function_executor_service(self):
        """Obtiene el servicio de ejecución de funciones"""
        return self.ai.get_function_executor_service()
    
    # ===== SERVICIOS DE PLANES Y TO-DOS =====
    
    def get_plan_generation_service(self):
        """Obtiene el servicio de generación de planes largos."""
        if not hasattr(self, '_plan_generation_service'):
            from app.services.ai.plan_generation_service import PlanGenerationService
            self._plan_generation_service = PlanGenerationService(self)
        return self._plan_generation_service
    
    def get_plan_detection_service(self):
        """Obtiene el servicio de detección de tipo de plan."""
        if not hasattr(self, '_plan_detection_service'):
            from app.services.ai.plan_detection_service import PlanDetectionService
            self._plan_detection_service = PlanDetectionService(self)
        return self._plan_detection_service
    
    def get_plan_service(self):
        """Obtiene el servicio de gestión de planes."""
        if not hasattr(self, '_plan_service'):
            from app.services.management.plan_service import PlanService
            self._plan_service = PlanService(self.db)
        return self._plan_service
    
    def get_plan_execution_service(self):
        """Obtiene el servicio de ejecución de planes."""
        if not hasattr(self, '_plan_execution_service'):
            from app.services.execution.plan_execution_service import PlanExecutionService
            self._plan_execution_service = PlanExecutionService(self)
        return self._plan_execution_service
    
    def get_plan_realtime_tracker(self):
        """Obtiene el servicio de seguimiento en tiempo real de planes."""
        if not hasattr(self, '_plan_realtime_tracker'):
            from app.services.execution.plan_realtime_tracker import PlanRealtimeTracker
            self._plan_realtime_tracker = PlanRealtimeTracker(self)
        return self._plan_realtime_tracker
    
    def get_plan_chat_integration_service(self):
        """Obtiene el servicio de integración de planes con chat."""
        if not hasattr(self, '_plan_chat_integration_service'):
            from app.services.chat.plan_chat_integration_service import PlanChatIntegrationService
            self._plan_chat_integration_service = PlanChatIntegrationService(self)
        return self._plan_chat_integration_service
    
    def get_plan_chat_commands_service(self):
        """Obtiene el servicio de comandos de chat para planes."""
        if not hasattr(self, '_plan_chat_commands_service'):
            from app.services.chat.plan_chat_commands_service import PlanChatCommandsService
            self._plan_chat_commands_service = PlanChatCommandsService(self)
        return self._plan_chat_commands_service
    
    def get_plan_outcome_service(self):
        """Obtiene el servicio de resultados de planes."""
        if not hasattr(self, '_plan_outcome_service'):
            from app.services.execution.plan_outcome_service import PlanOutcomeService
            self._plan_outcome_service = PlanOutcomeService(self)
        return self._plan_outcome_service
    
    def get_plan_recommendation_service(self):
        """Obtiene el servicio de recomendaciones de planes."""
        if not hasattr(self, '_plan_recommendation_service'):
            from app.services.ai.plan_recommendation_service import PlanRecommendationService
            self._plan_recommendation_service = PlanRecommendationService(self)
        return self._plan_recommendation_service
    
    def __repr__(self):
        """Representación string del ServiceFactory"""
        return f"<ServiceFactory(user_id={self.user.id}, sub_factories=6)>"
    
    def __str__(self):
        """String representation del ServiceFactory"""
        return f"ServiceFactory for user {self.user.id} with 6 sub-factories"


# ─────────────────────────────────────────────
#   🌐 FUNCIÓN GLOBAL PARA DEPENDENCIAS
# ─────────────────────────────────────────────

def get_factory() -> ServiceFactory:
    """
    Función de dependencia para FastAPI que crea una instancia de ServiceFactory
    para el usuario actual de la sesión.
    """
    # TODO: Implementar lógica para obtener el usuario actual de la sesión
    # Por ahora, creamos una instancia básica
    from app.models.user_model import User
    from uuid import uuid4
    
    # Crear un usuario temporal para testing
    temp_user = User(id=uuid4(), email="temp@example.com")
    return ServiceFactory(user=temp_user)
