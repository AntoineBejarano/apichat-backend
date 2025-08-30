"""
APITriggeringService - Servicio de triggering automático de APIs
────────────────────────────────────────────────────────────────
Servicio que permite ejecutar funciones de API automáticamente basándose
en queries en lenguaje natural, utilizando búsqueda vectorial y configuración
personalizada por usuario.
"""

import logging
from typing import Dict, List, Optional, Any, Union
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime

from app.services.context.unified_vector_search_service import (
    UnifiedVectorSearchService,
    SearchContext,
    UnifiedSearchResult
)
from app.services.management.api_triggering_config_service import APITriggeringConfigService
from app.services.execution.function_executor_service import FunctionExecutor
from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


@dataclass
class TriggeringPlan:
    """Plan de ejecución para triggering automático"""
    function_id: UUID
    function_name: str
    endpoint: str
    method: str
    parameters: Dict[str, Any]
    confidence: float
    requires_confirmation: bool
    estimated_execution_time: int  # segundos


@dataclass
class TriggeringResult:
    """Resultado de ejecución de triggering"""
    function_name: str
    endpoint: str
    success: bool
    result: Any
    execution_time: float
    error: Optional[str] = None
    requires_rollback: bool = False


class APITriggeringService:
    """
    Servicio de triggering automático de APIs.
    Combina búsqueda vectorial, configuración de usuario y ejecución inteligente.
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        
        # Servicios dependientes
        self.unified_search_service = UnifiedVectorSearchService(factory)
        self.triggering_config_service = APITriggeringConfigService(factory)
        self.function_executor = FunctionExecutor(factory)
        
        # Cache de planes de ejecución
        self.execution_plans_cache = {}
        
        self.logger.info("[APITriggeringService] 🚀 Inicializado con triggering automático")
    
    async def process_triggering_request(
        self,
        query: str,
        user_id: UUID,
        app_id: Optional[UUID] = None,
        db_id: Optional[UUID] = None,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """
        Procesar solicitud de triggering automático.
        
        Args:
            query: Query en lenguaje natural
            user_id: ID del usuario
            app_id: ID de la app (opcional)
            db_id: ID de la base de datos (opcional)
            auto_execute: Si ejecutar automáticamente o solo planificar
            
        Returns:
            Resultado del procesamiento con planes y/o ejecuciones
        """
        try:
            self.logger.info(f"[APITriggeringService] 🎯 Procesando triggering: '{query}' para user_id={user_id}")
            
            # 1. Obtener configuración de triggering
            triggering_config = await self._get_triggering_config(user_id, app_id)
            
            # 2. Crear contexto de búsqueda
            search_context = SearchContext(
                user_id=user_id,
                app_id=app_id,
                db_id=db_id,
                search_types=["api"],  # Por ahora solo APIs
                confidence_threshold=triggering_config.confidence_threshold,
                max_results_per_type=triggering_config.max_auto_executions
            )
            
            # 3. Búsqueda vectorial unificada
            search_results = await self.unified_search_service.unified_search(query, search_context)
            
            # 4. Filtrar resultados de API
            api_results = [r for r in search_results if r.resource_type == "api"]
            
            if not api_results:
                return {
                    "success": False,
                    "message": "No se encontraron APIs relevantes para la consulta",
                    "suggestions": await self._get_search_suggestions(query, search_context)
                }
            
            # 5. Generar planes de ejecución
            execution_plans = await self._generate_execution_plans(
                query, api_results, triggering_config
            )
            
            if not execution_plans:
                return {
                    "success": False,
                    "message": "No se pudieron generar planes de ejecución válidos",
                    "search_results": api_results
                }
            
            # 6. Verificar permisos de ejecución
            authorized_plans = await self._authorize_execution_plans(
                execution_plans, triggering_config
            )
            
            if not authorized_plans:
                return {
                    "success": False,
                    "message": "No hay permisos para ejecutar las funciones encontradas",
                    "execution_plans": execution_plans
                }
            
            # 7. Ejecutar o retornar planes
            if auto_execute and triggering_config.auto_confirm:
                # Ejecutar automáticamente
                execution_results = await self._execute_plans(authorized_plans)
                return {
                    "success": True,
                    "message": f"Ejecutadas {len(execution_results)} funciones automáticamente",
                    "execution_results": execution_results,
                    "execution_plans": authorized_plans
                }
            else:
                # Retornar planes para confirmación
                return {
                    "success": True,
                    "message": f"Encontrados {len(authorized_plans)} planes de ejecución",
                    "execution_plans": authorized_plans,
                    "requires_confirmation": True,
                    "auto_execute_available": triggering_config.auto_confirm
                }
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error procesando triggering: {e}")
            return {
                "success": False,
                "message": f"Error procesando solicitud: {str(e)}",
                "error": str(e)
            }
    
    async def _get_triggering_config(self, user_id: UUID, app_id: Optional[UUID]) -> Any:
        """Obtener configuración de triggering para el usuario"""
        try:
            if app_id:
                config = self.triggering_config_service.get_config_by_user_and_app(user_id, app_id)
                if config:
                    return config
            
            # Usar configuración por defecto
            return self.triggering_config_service.get_default_config(app_id or UUID('00000000-0000-0000-0000-000000000000'))
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error obteniendo configuración: {e}")
            return self.triggering_config_service.get_default_config(app_id or UUID('00000000-0000-0000-0000-000000000000'))
    
    async def _generate_execution_plans(
        self,
        query: str,
        api_results: List[UnifiedSearchResult],
        triggering_config: Any
    ) -> List[TriggeringPlan]:
        """Generar planes de ejecución basados en los resultados de búsqueda"""
        try:
            plans = []
            
            for result in api_results:
                if result.similarity_score < triggering_config.confidence_threshold:
                    continue
                
                # Extraer información de la función
                function_id = result.metadata.get("function_id")
                if not function_id:
                    continue
                
                # Obtener función completa
                function = self.factory.get_function_service().get_by_id(function_id)
                if not function:
                    continue
                
                # Extraer parámetros de la query
                parameters = await self._extract_parameters_from_query(query, result)
                
                # Calcular tiempo estimado de ejecución
                estimated_time = self._estimate_execution_time(function, parameters)
                
                # Determinar si requiere confirmación
                requires_confirmation = (
                    triggering_config.require_explicit_consent or
                    result.similarity_score < 0.9 or
                    len(parameters) == 0
                )
                
                plan = TriggeringPlan(
                    function_id=function.id,
                    function_name=function.name,
                    endpoint=result.metadata.get("path", ""),
                    method=result.metadata.get("method", ""),
                    parameters=parameters,
                    confidence=result.similarity_score,
                    requires_confirmation=requires_confirmation,
                    estimated_execution_time=estimated_time
                )
                
                plans.append(plan)
            
            # Ordenar por confianza
            plans.sort(key=lambda p: p.confidence, reverse=True)
            
            return plans
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error generando planes: {e}")
            return []
    
    async def _extract_parameters_from_query(
        self,
        query: str,
        api_result: UnifiedSearchResult
    ) -> Dict[str, Any]:
        """Extraer parámetros de la query usando IA"""
        try:
            # TODO: Implementar extracción inteligente de parámetros usando LLM
            # Por ahora, extracción básica basada en patrones
            
            parameters = {}
            query_lower = query.lower()
            
            # Extraer email
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, query)
            if emails:
                parameters["email"] = emails[0]
            
            # Extraer números
            number_pattern = r'\b\d+\b'
            numbers = re.findall(number_pattern, query)
            if numbers:
                parameters["id"] = int(numbers[0])
            
            # Extraer nombres (básico)
            if "usuario" in query_lower or "user" in query_lower:
                # Buscar nombres después de palabras clave
                name_pattern = r'(?:usuario|user|nombre|name)\s+([A-Za-z]+)'
                name_match = re.search(name_pattern, query_lower)
                if name_match:
                    parameters["name"] = name_match.group(1).title()
            
            return parameters
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error extrayendo parámetros: {e}")
            return {}
    
    def _estimate_execution_time(self, function: Any, parameters: Dict[str, Any]) -> int:
        """Estimar tiempo de ejecución de una función"""
        try:
            # Tiempo base según el tipo de función
            base_time = 5  # segundos base
            
            # Ajustar según parámetros
            if len(parameters) > 3:
                base_time += 2
            
            # Ajustar según método HTTP
            if function.method == "POST":
                base_time += 3
            elif function.method == "PUT":
                base_time += 2
            
            return min(base_time, 30)  # Máximo 30 segundos
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error estimando tiempo: {e}")
            return 10  # Tiempo por defecto
    
    async def _authorize_execution_plans(
        self,
        plans: List[TriggeringPlan],
        triggering_config: Any
    ) -> List[TriggeringPlan]:
        """Verificar permisos de ejecución para los planes"""
        try:
            authorized_plans = []
            
            for plan in plans:
                endpoint_key = f"{plan.method}_{plan.endpoint}"
                
                # Verificar whitelist
                if (triggering_config.allowed_endpoints and 
                    endpoint_key not in triggering_config.allowed_endpoints):
                    continue
                
                # Verificar blacklist
                if (triggering_config.blocked_endpoints and 
                    endpoint_key in triggering_config.blocked_endpoints):
                    continue
                
                # Verificar límite de ejecuciones
                if len(authorized_plans) >= triggering_config.max_auto_executions:
                    break
                
                authorized_plans.append(plan)
            
            return authorized_plans
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error autorizando planes: {e}")
            return []
    
    async def _execute_plans(self, plans: List[TriggeringPlan]) -> List[TriggeringResult]:
        """Ejecutar planes de triggering"""
        try:
            results = []
            
            for plan in plans:
                start_time = datetime.now()
                
                try:
                    # Obtener función
                    function = self.factory.get_function_service().get_by_id(plan.function_id)
                    if not function:
                        raise ValueError(f"Función {plan.function_id} no encontrada")
                    
                    # Ejecutar función
                    result = await self.function_executor.execute(function, plan.parameters)
                    
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    results.append(TriggeringResult(
                        function_name=plan.function_name,
                        endpoint=plan.endpoint,
                        success=True,
                        result=result,
                        execution_time=execution_time
                    ))
                    
                    self.logger.info(f"[APITriggeringService] ✅ Función ejecutada: {plan.function_name}")
                    
                except Exception as e:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    results.append(TriggeringResult(
                        function_name=plan.function_name,
                        endpoint=plan.endpoint,
                        success=False,
                        result=None,
                        execution_time=execution_time,
                        error=str(e)
                    ))
                    
                    self.logger.error(f"[APITriggeringService] ❌ Error ejecutando {plan.function_name}: {e}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error ejecutando planes: {e}")
            return []
    
    async def _get_search_suggestions(
        self,
        query: str,
        search_context: SearchContext
    ) -> List[str]:
        """Obtener sugerencias de búsqueda"""
        try:
            return await self.unified_search_service.get_search_suggestions(
                query, search_context, max_suggestions=3
            )
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error obteniendo sugerencias: {e}")
            return []
    
    async def execute_confirmed_plan(
        self,
        plan: TriggeringPlan,
        user_id: UUID
    ) -> TriggeringResult:
        """Ejecutar un plan confirmado por el usuario"""
        try:
            self.logger.info(f"[APITriggeringService] 🎯 Ejecutando plan confirmado: {plan.function_name}")
            
            # Verificar configuración una vez más
            triggering_config = await self._get_triggering_config(user_id, None)
            
            # Autorizar plan individual
            authorized_plans = await self._authorize_execution_plans([plan], triggering_config)
            
            if not authorized_plans:
                raise ValueError("Plan no autorizado para ejecución")
            
            # Ejecutar
            results = await self._execute_plans(authorized_plans)
            
            if results:
                return results[0]
            else:
                raise ValueError("No se pudo ejecutar el plan")
                
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error ejecutando plan confirmado: {e}")
            return TriggeringResult(
                function_name=plan.function_name,
                endpoint=plan.endpoint,
                success=False,
                result=None,
                execution_time=0.0,
                error=str(e)
            )
    
    async def get_triggering_analytics(self, user_id: UUID) -> Dict[str, Any]:
        """Obtener analytics de triggering para un usuario"""
        try:
            # TODO: Implementar analytics detallados
            analytics = {
                "total_requests": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_confidence": 0.0,
                "most_triggered_functions": [],
                "execution_times": {
                    "average": 0.0,
                    "min": 0.0,
                    "max": 0.0
                }
            }
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"[APITriggeringService] ❌ Error obteniendo analytics: {e}")
            return {}
