"""
PlanChatIntegrationService - Integración de planes con el chat.
Extiende UnifiedChatService para detectar y manejar consultas que requieren planes.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.services.ai.unified_chat_service import UnifiedChatService, ChatResponse
from app.services.ai.plan_detection_service import PlanDetectionService
from app.services.ai.plan_generation_service import PlanGenerationService
from app.services.execution.plan_execution_service import PlanExecutionService
from app.services.execution.plan_realtime_tracker import PlanRealtimeTracker
from app.services.management.plan_service import PlanService
from app.schemas.plan_schema import (
    PlanGenerationRequest, PlanGenerationResponse,
    PlanExecutionRequest, PlanExecutionResponse
)

logger = logging.getLogger(__name__)


class PlanChatIntegrationService(UnifiedChatService):
    """
    Servicio de chat extendido que integra el sistema de planes.
    Detecta automáticamente cuando una consulta requiere un plan complejo.
    """
    
    def __init__(self, factory):
        super().__init__(factory)
        self.logger = logging.getLogger(__name__)
        
        # Servicios de planes
        self.plan_detection_service = PlanDetectionService(factory)
        self.plan_generation_service = PlanGenerationService(factory)
        self.plan_execution_service = PlanExecutionService(factory)
        self.plan_realtime_tracker = PlanRealtimeTracker(factory)
        self.plan_service = PlanService(factory.db)
        
        self.logger.info("[PlanChatIntegration] 🎯 Inicializado con integración de planes")
    
    async def process_chat_message(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID] = None,
        app_id: Optional[UUID] = None,
        db_id: Optional[UUID] = None,
        auto_execute_apis: bool = False
    ) -> ChatResponse:
        """
        Procesar mensaje de chat con detección de planes.
        Extiende el método base para incluir detección de planes complejos.
        """
        try:
            self.logger.info(f"[PlanChatIntegration] 💬 Procesando mensaje: '{message[:50]}...' para user_id={user_id}")
            
            # 1. Detectar si requiere un plan complejo
            plan_detection = await self._detect_plan_requirement(message, user_id, app_id, db_id)
            
            if plan_detection['requires_plan']:
                self.logger.info(f"[PlanChatIntegration] 🎯 Plan requerido: {plan_detection['complexity']} (confianza: {plan_detection['confidence']:.2f})")
                return await self._handle_plan_intent(message, user_id, chat_id, app_id, db_id, plan_detection)
            
            # 2. Si no requiere plan, usar el procesamiento normal
            return await super().process_chat_message(message, user_id, chat_id, app_id, db_id, auto_execute_apis)
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error procesando mensaje: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando mensaje: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _detect_plan_requirement(
        self,
        message: str,
        user_id: UUID,
        app_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> Dict[str, Any]:
        """
        Detecta si el mensaje requiere un plan complejo.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            app_id: ID de la aplicación
            db_id: ID de la base de datos
            
        Returns:
            Dict con información sobre si requiere plan y su complejidad
        """
        try:
            # Preparar contexto
            context = {
                "user_id": str(user_id),
                "app_id": str(app_id) if app_id else None,
                "db_id": str(db_id) if db_id else None,
                "message_length": len(message),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Obtener información de recursos disponibles
            database_info = await self._get_database_info(db_id, user_id)
            application_info = await self._get_application_info(app_id, user_id)
            api_info = await self._get_api_info(app_id, user_id)
            
            # Detectar tipo de plan
            detection_result = self.plan_detection_service.detect_plan_type(
                user_prompt=message,
                context=context,
                user_id=user_id,
                database_info=database_info,
                application_info=application_info,
                api_info=api_info
            )
            
            return {
                "requires_plan": not detection_result.should_use_existing,
                "complexity": detection_result.complexity.value,
                "confidence": detection_result.confidence,
                "reasoning": detection_result.reasoning,
                "estimated_steps": detection_result.estimated_steps,
                "detection_result": detection_result
            }
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error detectando plan: {e}")
            return {
                "requires_plan": False,
                "complexity": "simple",
                "confidence": 0.1,
                "reasoning": f"Error en detección: {str(e)}",
                "estimated_steps": 1
            }
    
    async def _handle_plan_intent(
        self,
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID],
        app_id: Optional[UUID],
        db_id: Optional[UUID],
        plan_detection: Dict[str, Any]
    ) -> ChatResponse:
        """
        Maneja la intención de crear un plan complejo.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            chat_id: ID del chat
            app_id: ID de la aplicación
            db_id: ID de la base de datos
            plan_detection: Resultado de la detección de plan
            
        Returns:
            ChatResponse con el plan generado o propuesta de plan
        """
        try:
            self.logger.info(f"[PlanChatIntegration] 🎯 Generando plan complejo para: '{message[:50]}...'")
            
            # 1. Generar el plan
            generated_plan = await self._generate_plan(message, user_id, app_id, db_id, plan_detection)
            
            if not generated_plan:
                return ChatResponse(
                    success=False,
                    message="No se pudo generar un plan para tu consulta. Intenta reformular tu solicitud.",
                    response_type="error",
                    data={"error": "Plan generation failed"}
                )
            
            # 2. Crear respuesta con el plan
            plan_summary = self._create_plan_summary(generated_plan)
            
            return ChatResponse(
                success=True,
                message=f"🎯 He creado un plan con {len(generated_plan.tasks)} pasos para lograr tu objetivo:\n\n{plan_summary}",
                response_type="plan",
                data={
                    "plan": generated_plan,
                    "detection": plan_detection,
                    "requires_confirmation": generated_plan.requires_confirmation
                },
                requires_confirmation=generated_plan.requires_confirmation,
                suggestions=[
                    "✅ Ejecutar plan automáticamente",
                    "⏸️ Revisar plan antes de ejecutar",
                    "✏️ Modificar plan",
                    "❌ Cancelar plan"
                ]
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error manejando plan: {e}")
            return ChatResponse(
                success=False,
                message=f"Error generando plan: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _generate_plan(
        self,
        message: str,
        user_id: UUID,
        app_id: Optional[UUID],
        db_id: Optional[UUID],
        plan_detection: Dict[str, Any]
    ) -> Optional[Any]:
        """
        Genera un plan complejo usando el PlanGenerationService.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            app_id: ID de la aplicación
            db_id: ID de la base de datos
            plan_detection: Resultado de la detección
            
        Returns:
            Plan generado o None si falla
        """
        try:
            # Preparar contexto
            context = {
                "user_id": str(user_id),
                "app_id": str(app_id) if app_id else None,
                "db_id": str(db_id) if db_id else None,
                "detection": plan_detection,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Obtener información de recursos
            database_info = await self._get_database_info(db_id, user_id)
            application_info = await self._get_application_info(app_id, user_id)
            api_info = await self._get_api_info(app_id, user_id)
            
            # Generar plan
            generated_plan = await self.plan_generation_service.generate_plan(
                user_prompt=message,
                user_id=user_id,
                context=context,
                database_info=database_info,
                application_info=application_info,
                api_info=api_info
            )
            
            return generated_plan
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error generando plan: {e}")
            return None
    
    def _create_plan_summary(self, plan: Any) -> str:
        """
        Crea un resumen legible del plan para mostrar al usuario.
        
        Args:
            plan: Plan generado
            
        Returns:
            Resumen del plan en formato legible
        """
        try:
            summary_parts = [
                f"**📋 {plan.title}**",
                f"_{plan.description}_",
                "",
                f"**🎯 Objetivo:** {plan.description}",
                f"**⏱️ Tiempo estimado:** {plan.total_estimated_effort} minutos",
                f"**📊 Complejidad:** {plan.complexity.value}",
                "",
                "**📝 Pasos del plan:**"
            ]
            
            for i, task in enumerate(plan.tasks, 1):
                summary_parts.append(f"{i}. **{task.title}**")
                summary_parts.append(f"   - {task.description}")
                summary_parts.append(f"   - ⏱️ {task.estimated_effort} min | 🎯 {task.action_type} | ⚠️ {task.risk_level}")
                if task.dependencies:
                    summary_parts.append(f"   - 🔗 Depende de: {', '.join(task.dependencies)}")
                summary_parts.append("")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error creando resumen: {e}")
            return f"Plan: {plan.title} con {len(plan.tasks)} tareas"
    
    # ===== MÉTODOS DE UTILIDAD =====
    
    async def _get_database_info(self, db_id: Optional[UUID], user_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información de la base de datos."""
        if not db_id:
            return None
        
        try:
            # TODO: Implementar obtención de información de DB
            return {
                "db_id": str(db_id),
                "user_id": str(user_id),
                "tables": [],  # TODO: Obtener tablas reales
                "schema_status": "ready"
            }
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error obteniendo info de DB: {e}")
            return None
    
    async def _get_application_info(self, app_id: Optional[UUID], user_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información de la aplicación."""
        if not app_id:
            return None
        
        try:
            # TODO: Implementar obtención de información de app
            return {
                "app_id": str(app_id),
                "user_id": str(user_id),
                "functions": [],  # TODO: Obtener funciones reales
                "endpoints": []   # TODO: Obtener endpoints reales
            }
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error obteniendo info de app: {e}")
            return None
    
    async def _get_api_info(self, app_id: Optional[UUID], user_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene información de APIs disponibles."""
        try:
            # TODO: Implementar obtención de información de APIs
            return {
                "available_apis": [],  # TODO: Obtener APIs reales
                "user_config": {}      # TODO: Obtener configuración del usuario
            }
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error obteniendo info de APIs: {e}")
            return None
    
    # ===== MÉTODOS DE EJECUCIÓN =====
    
    async def execute_plan_from_chat(
        self,
        plan_id: UUID,
        user_id: UUID,
        auto_confirm: bool = False,
        chat_id: Optional[UUID] = None
    ) -> ChatResponse:
        """
        Ejecuta un plan desde el chat.
        
        Args:
            plan_id: ID del plan a ejecutar
            user_id: ID del usuario
            auto_confirm: Si confirmar automáticamente las tareas
            chat_id: ID del chat
            
        Returns:
            ChatResponse con el resultado de la ejecución
        """
        try:
            self.logger.info(f"[PlanChatIntegration] 🚀 Ejecutando plan {plan_id} desde chat")
            
            # Iniciar ejecución
            execution_result = await self.plan_execution_service.start_plan_execution(
                plan_id=plan_id,
                user_id=user_id,
                auto_confirm=auto_confirm
            )
            
            # Notificar inicio de ejecución
            await self.plan_realtime_tracker.notify_execution_started(
                user_id=user_id,
                execution_id=execution_result.execution_id,
                plan_id=plan_id,
                total_tasks=execution_result.total_tasks
            )
            
            return ChatResponse(
                success=True,
                message=f"🚀 Ejecución iniciada: {execution_result.message}",
                response_type="execution_started",
                data={
                    "execution_id": execution_result.execution_id,
                    "plan_id": str(plan_id),
                    "status": execution_result.status.value,
                    "total_tasks": execution_result.total_tasks,
                    "current_task_index": execution_result.current_task_index
                },
                suggestions=[
                    "📊 Ver progreso en tiempo real",
                    "⏸️ Pausar ejecución",
                    "🛑 Cancelar ejecución"
                ]
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error ejecutando plan: {e}")
            return ChatResponse(
                success=False,
                message=f"Error ejecutando plan: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def get_plan_status_from_chat(
        self,
        execution_id: str,
        user_id: UUID
    ) -> ChatResponse:
        """
        Obtiene el estado de una ejecución desde el chat.
        
        Args:
            execution_id: ID de la ejecución
            user_id: ID del usuario
            
        Returns:
            ChatResponse con el estado de la ejecución
        """
        try:
            status = await self.plan_execution_service.get_execution_status(execution_id, user_id)
            
            if not status:
                return ChatResponse(
                    success=False,
                    message="Ejecución no encontrada",
                    response_type="error",
                    data={"error": "Execution not found"}
                )
            
            return ChatResponse(
                success=True,
                message=f"📊 Estado de ejecución: {status.get('status', 'unknown')}",
                response_type="execution_status",
                data=status
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatIntegration] ❌ Error obteniendo estado: {e}")
            return ChatResponse(
                success=False,
                message=f"Error obteniendo estado: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
