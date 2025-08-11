"""
Servicio para ejecutar planes aplicando guardrails de seguridad.
Integra SQLGuardrailsService y FunctionGuardrailsService.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
import asyncio
from pydantic import BaseModel

from app.core.service_factory import ServiceFactory
from app.schemas.plan_schema import PlanModel, PlanStep
from app.services.execution.sql_guardrails_service import SQLGuardrailsService, RiskLevel as SQLRiskLevel
from app.services.execution.function_guardrails import FunctionGuardrailsService, FunctionRiskLevel
from app.utils.logger import get_logger

logger = get_logger(__name__)


class StepExecutionResult(BaseModel):
    """Resultado de la ejecución de un paso."""
    step_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    guardrail_violations: List[Dict[str, Any]] = []
    requires_confirmation: bool = False


class PlanExecutionService:
    """Servicio para ejecutar planes aplicando guardrails de seguridad."""
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.sql_guardrails = factory.get_sql_guardrails_service()
        self.function_guardrails = factory.get_function_guardrails_service()
        
        logger.info("🚀 PlanExecutionService inicializado con guardrails")
    
    async def execute_plan(
        self, 
        plan: PlanModel, 
        context: Dict[str, Any],
        user_roles: List[str] = None,
        user_permissions: List[str] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta un plan completo aplicando guardrails en cada paso.
        
        Args:
            plan: Plan a ejecutar
            context: Contexto de ejecución
            user_roles: Roles del usuario
            user_permissions: Permisos del usuario
            
        Returns:
            Resultado de la ejecución del plan
        """
        logger.info(f"🚀 Ejecutando plan: {plan.title}")
        logger.info(f"  📋 Pasos: {len(plan.steps)}")
        logger.info(f"  ⚠️  Requiere confirmación: {plan.requires_confirmation}")
        
        # Valores por defecto para roles y permisos
        user_roles = user_roles or ["user"]
        user_permissions = user_permissions or ["read"]
        
        execution_results = []
        total_execution_time = 0.0
        guardrail_violations = []
        
        # Ejecutar cada paso del plan
        for i, step in enumerate(plan.steps):
            logger.info(f"🔄 Ejecutando paso {i+1}/{len(plan.steps)}: {step.step_id}")
            
            try:
                # Aplicar guardrails antes de ejecutar
                step_result = await self._execute_step_with_guardrails(
                    step=step,
                    context=context,
                    user_roles=user_roles,
                    user_permissions=user_permissions,
                    step_number=i+1,
                    total_steps=len(plan.steps)
                )
                
                execution_results.append(step_result)
                total_execution_time += step_result.execution_time
                
                # Si el paso falló, detener la ejecución
                if not step_result.success:
                    logger.error(f"❌ Paso {step.step_id} falló: {step_result.error}")
                    break
                
                # Si requiere confirmación, esperar
                if step_result.requires_confirmation:
                    logger.info(f"⏸️ Paso {step.step_id} requiere confirmación del usuario")
                    # Aquí se integraría con el sistema de decisiones
                    break
                
                logger.info(f"✅ Paso {step.step_id} ejecutado exitosamente")
                
            except Exception as e:
                logger.error(f"❌ Error ejecutando paso {step.step_id}: {e}")
                step_result = StepExecutionResult(
                    step_id=step.step_id,
                    success=False,
                    error=str(e),
                    execution_time=0.0
                )
                execution_results.append(step_result)
                break
        
        # Preparar resultado final
        successful_steps = [r for r in execution_results if r.success]
        failed_steps = [r for r in execution_results if not r.success]
        
        result = {
            "plan_title": plan.title,
            "plan_description": plan.description,
            "total_steps": len(plan.steps),
            "executed_steps": len(successful_steps),
            "failed_steps": len(failed_steps),
            "total_execution_time": total_execution_time,
            "success": len(failed_steps) == 0,
            "step_results": [r.model_dump() for r in execution_results],
            "guardrail_violations": guardrail_violations,
            "requires_confirmation": any(r.requires_confirmation for r in execution_results)
        }
        
        if result["success"]:
            logger.info(f"✅ Plan ejecutado exitosamente en {total_execution_time:.2f}s")
        else:
            logger.warning(f"⚠️ Plan ejecutado con {len(failed_steps)} fallos")
        
        return result
    
    async def _execute_step_with_guardrails(
        self,
        step: PlanStep,
        context: Dict[str, Any],
        user_roles: List[str],
        user_permissions: List[str],
        step_number: int,
        total_steps: int
    ) -> StepExecutionResult:
        """
        Ejecuta un paso individual aplicando guardrails.
        
        Args:
            step: Paso a ejecutar
            context: Contexto de ejecución
            user_roles: Roles del usuario
            user_permissions: Permisos del usuario
            step_number: Número del paso actual
            total_steps: Total de pasos en el plan
            
        Returns:
            Resultado de la ejecución del paso
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # 1. Aplicar guardrails SQL si hay consulta SQL
            if step.sql_query:
                sql_violation = await self._apply_sql_guardrails(step.sql_query, user_roles)
                if sql_violation:
                    return StepExecutionResult(
                        step_id=step.step_id,
                        success=False,
                        error=f"Violación de guardrail SQL: {sql_violation['message']}",
                        execution_time=0.0,
                        guardrail_violations=[sql_violation],
                        requires_confirmation=sql_violation.get('requires_confirmation', False)
                    )
            
            # 2. Aplicar guardrails de función si hay llamada a función
            if step.function_call:
                function_violation = await self._apply_function_guardrails(
                    step.function_call, 
                    user_roles, 
                    user_permissions
                )
                if function_violation:
                    return StepExecutionResult(
                        step_id=step.step_id,
                        success=False,
                        error=f"Violación de guardrail de función: {function_violation['message']}",
                        execution_time=0.0,
                        guardrail_violations=[function_violation],
                        requires_confirmation=function_violation.get('requires_confirmation', False)
                    )
            
            # 3. Ejecutar el paso (simulado por ahora)
            step_result = await self._execute_step_logic(step, context)
            
            execution_time = asyncio.get_event_loop().time() - start_time
            
            return StepExecutionResult(
                step_id=step.step_id,
                success=True,
                result=step_result,
                execution_time=execution_time,
                requires_confirmation=False
            )
            
        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            logger.error(f"❌ Error ejecutando paso {step.step_id}: {e}")
            
            return StepExecutionResult(
                step_id=step.step_id,
                success=False,
                error=str(e),
                execution_time=execution_time
            )
    
    async def _apply_sql_guardrails(
        self, 
        sql_query: str, 
        user_roles: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Aplica guardrails SQL a una consulta.
        
        Args:
            sql_query: Consulta SQL a validar
            user_roles: Roles del usuario
            
        Returns:
            Violación detectada o None si es segura
        """
        try:
            # Determinar tolerancia al riesgo basada en roles
            risk_tolerance = self._determine_user_risk_tolerance(user_roles)
            
            # Validar consulta
            is_allowed, violation, alternatives = self.sql_guardrails.validate_and_apply_guardrails(
                sql_query, risk_tolerance
            )
            
            if not is_allowed:
                return {
                    "type": "sql_guardrail",
                    "message": violation.message,
                    "risk_level": violation.risk_level.value,
                    "operation": violation.operation.value,
                    "requires_confirmation": violation.requires_confirmation,
                    "alternatives": alternatives
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error aplicando guardrails SQL: {e}")
            return {
                "type": "sql_guardrail_error",
                "message": f"Error validando consulta SQL: {str(e)}",
                "risk_level": "high",
                "requires_confirmation": True
            }
    
    async def _apply_function_guardrails(
        self, 
        function_call: str, 
        user_roles: List[str], 
        user_permissions: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Aplica guardrails de función a una llamada.
        
        Args:
            function_call: Llamada a función a validar
            user_roles: Roles del usuario
            user_permissions: Permisos del usuario
            
        Returns:
            Violación detectada o None si es segura
        """
        try:
            # Extraer nombre de función de la llamada
            function_name = self._extract_function_name(function_call)
            
            # Validar ejecución de función
            is_allowed, error_message, guardrail = self.function_guardrails.validate_function_execution(
                function_name=function_name,
                user_roles=user_roles,
                user_permissions=user_permissions
            )
            
            if not is_allowed:
                return {
                    "type": "function_guardrail",
                    "message": error_message,
                    "function_name": function_name,
                    "risk_level": guardrail.risk_level.value,
                    "category": guardrail.category.value,
                    "requires_confirmation": guardrail.requires_confirmation,
                    "required_permission": guardrail.required_permission.value
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error aplicando guardrails de función: {e}")
            return {
                "type": "function_guardrail_error",
                "message": f"Error validando función: {str(e)}",
                "risk_level": "high",
                "requires_confirmation": True
            }
    
    def _determine_user_risk_tolerance(self, user_roles: List[str]) -> SQLRiskLevel:
        """Determina la tolerancia al riesgo del usuario basada en sus roles."""
        if "admin" in user_roles or "super_admin" in user_roles:
            return SQLRiskLevel.MEDIUM
        elif "owner" in user_roles:
            return SQLRiskLevel.HIGH
        else:
            return SQLRiskLevel.LOW
    
    def _extract_function_name(self, function_call: str) -> str:
        """Extrae el nombre de la función de una llamada de función."""
        # Patrón simple: function_name(params)
        if "(" in function_call:
            return function_call.split("(")[0].strip()
        return function_call.strip()
    
    async def _execute_step_logic(self, step: PlanStep, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la lógica real del paso (simulado por ahora).
        
        Args:
            step: Paso a ejecutar
            context: Contexto de ejecución
            
        Returns:
            Resultado de la ejecución
        """
        # Simular ejecución
        await asyncio.sleep(0.1)  # Simular tiempo de procesamiento
        
        if step.sql_query:
            # Simular ejecución SQL
            return {
                "type": "sql_result",
                "rows_affected": 10,
                "query": step.sql_query,
                "status": "success"
            }
        elif step.function_call:
            # Simular ejecución de función
            return {
                "type": "function_result",
                "function": step.function_call,
                "status": "success",
                "output": f"Resultado de {step.function_call}"
            }
        else:
            # Paso de análisis o transformación
            return {
                "type": "analysis_result",
                "action": step.action,
                "status": "success",
                "description": step.description
            }
    
    def get_plan_summary(self, plan: PlanModel) -> Dict[str, Any]:
        """Obtiene un resumen del plan para mostrar al usuario."""
        high_risk_steps = [step for step in plan.steps if step.risk_level == "high"]
        medium_risk_steps = [step for step in plan.steps if step.risk_level == "medium"]
        
        return {
            "title": plan.title,
            "description": plan.description,
            "total_steps": len(plan.steps),
            "high_risk_steps": len(high_risk_steps),
            "medium_risk_steps": len(medium_risk_steps),
            "low_risk_steps": len(plan.steps) - len(high_risk_steps) - len(medium_risk_steps),
            "estimated_cost": plan.total_estimated_cost,
            "requires_confirmation": plan.requires_confirmation or len(high_risk_steps) > 0
        }
