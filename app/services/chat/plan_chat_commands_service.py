"""
PlanChatCommandsService - Servicio para comandos de chat relacionados con planes.
Maneja comandos específicos como "ejecutar plan", "pausar", "estado", etc.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timezone

from app.services.chat.plan_chat_integration_service import PlanChatIntegrationService
from app.services.ai.unified_chat_service import ChatResponse

logger = logging.getLogger(__name__)


class PlanChatCommandsService:
    """
    Servicio para procesar comandos de chat relacionados con planes.
    Detecta y procesa comandos específicos del usuario.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        
        # Servicio de integración de planes
        self.plan_chat_service = PlanChatIntegrationService(factory)
        
        # Patrones de comandos
        self.command_patterns = {
            "execute_plan": [
                r"ejecutar plan",
                r"ejecuta plan",
                r"correr plan",
                r"iniciar plan",
                r"empezar plan",
                r"run plan",
                r"start plan"
            ],
            "pause_execution": [
                r"pausar ejecución",
                r"pausar plan",
                r"parar ejecución",
                r"pausar",
                r"pause",
                r"stop"
            ],
            "resume_execution": [
                r"reanudar ejecución",
                r"continuar ejecución",
                r"reanudar plan",
                r"continuar plan",
                r"resume",
                r"continue"
            ],
            "cancel_execution": [
                r"cancelar ejecución",
                r"cancelar plan",
                r"terminar ejecución",
                r"cancelar",
                r"cancel",
                r"abort"
            ],
            "plan_status": [
                r"estado del plan",
                r"estado de ejecución",
                r"progreso del plan",
                r"estado",
                r"status",
                r"progress"
            ],
            "list_plans": [
                r"listar planes",
                r"mostrar planes",
                r"ver planes",
                r"planes",
                r"list plans",
                r"show plans"
            ],
            "create_plan": [
                r"crear plan",
                r"generar plan",
                r"hacer plan",
                r"plan para",
                r"create plan",
                r"generate plan"
            ]
        }
        
        self.logger.info("[PlanChatCommands] 🎯 Inicializado con comandos de planes")
    
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
        Procesa mensaje de chat detectando comandos de planes.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            chat_id: ID del chat
            app_id: ID de la aplicación
            db_id: ID de la base de datos
            auto_execute_apis: Si ejecutar APIs automáticamente
            
        Returns:
            ChatResponse con el resultado del comando o procesamiento normal
        """
        try:
            self.logger.info(f"[PlanChatCommands] 💬 Procesando mensaje: '{message[:50]}...' para user_id={user_id}")
            
            # 1. Detectar si es un comando de plan
            command_result = await self._detect_plan_command(message, user_id)
            
            if command_result['is_command']:
                self.logger.info(f"[PlanChatCommands] 🎯 Comando detectado: {command_result['command_type']}")
                return await self._execute_plan_command(
                    command_result, message, user_id, chat_id, app_id, db_id
                )
            
            # 2. Si no es comando, usar el procesamiento normal de planes
            return await self.plan_chat_service.process_chat_message(
                message, user_id, chat_id, app_id, db_id, auto_execute_apis
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error procesando mensaje: {e}")
            return ChatResponse(
                success=False,
                message=f"Error procesando mensaje: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _detect_plan_command(
        self,
        message: str,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Detecta si el mensaje contiene un comando de plan.
        
        Args:
            message: Mensaje del usuario
            user_id: ID del usuario
            
        Returns:
            Dict con información del comando detectado
        """
        try:
            message_lower = message.lower().strip()
            
            # Buscar patrones de comandos
            for command_type, patterns in self.command_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, message_lower):
                        # Extraer parámetros del comando
                        params = await self._extract_command_parameters(message, command_type)
                        
                        return {
                            "is_command": True,
                            "command_type": command_type,
                            "pattern_matched": pattern,
                            "parameters": params,
                            "confidence": 0.9
                        }
            
            return {
                "is_command": False,
                "command_type": None,
                "confidence": 0.0
            }
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error detectando comando: {e}")
            return {
                "is_command": False,
                "command_type": None,
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def _extract_command_parameters(
        self,
        message: str,
        command_type: str
    ) -> Dict[str, Any]:
        """
        Extrae parámetros del comando.
        
        Args:
            message: Mensaje del usuario
            command_type: Tipo de comando
            
        Returns:
            Dict con parámetros extraídos
        """
        try:
            params = {}
            message_lower = message.lower()
            
            if command_type == "execute_plan":
                # Buscar ID de plan o nombre
                plan_id_match = re.search(r'plan[:\s]+([a-f0-9-]{36})', message_lower)
                if plan_id_match:
                    params['plan_id'] = plan_id_match.group(1)
                
                # Buscar auto_confirm
                if any(word in message_lower for word in ['automático', 'auto', 'automático']):
                    params['auto_confirm'] = True
            
            elif command_type in ["pause_execution", "resume_execution", "cancel_execution", "plan_status"]:
                # Buscar ID de ejecución
                execution_id_match = re.search(r'ejecución[:\s]+([a-f0-9-]{36})', message_lower)
                if execution_id_match:
                    params['execution_id'] = execution_id_match.group(1)
                
                # Buscar ID de plan
                plan_id_match = re.search(r'plan[:\s]+([a-f0-9-]{36})', message_lower)
                if plan_id_match:
                    params['plan_id'] = plan_id_match.group(1)
            
            elif command_type == "create_plan":
                # Extraer el objetivo del plan
                plan_text_match = re.search(r'plan para[:\s]+(.+)', message_lower)
                if plan_text_match:
                    params['plan_objective'] = plan_text_match.group(1).strip()
            
            return params
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error extrayendo parámetros: {e}")
            return {}
    
    async def _execute_plan_command(
        self,
        command_result: Dict[str, Any],
        message: str,
        user_id: UUID,
        chat_id: Optional[UUID],
        app_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> ChatResponse:
        """
        Ejecuta el comando de plan detectado.
        
        Args:
            command_result: Resultado de la detección del comando
            message: Mensaje original del usuario
            user_id: ID del usuario
            chat_id: ID del chat
            app_id: ID de la aplicación
            db_id: ID de la base de datos
            
        Returns:
            ChatResponse con el resultado del comando
        """
        try:
            command_type = command_result['command_type']
            params = command_result['parameters']
            
            if command_type == "execute_plan":
                return await self._handle_execute_plan_command(params, user_id, chat_id)
            
            elif command_type == "pause_execution":
                return await self._handle_pause_execution_command(params, user_id)
            
            elif command_type == "resume_execution":
                return await self._handle_resume_execution_command(params, user_id)
            
            elif command_type == "cancel_execution":
                return await self._handle_cancel_execution_command(params, user_id)
            
            elif command_type == "plan_status":
                return await self._handle_plan_status_command(params, user_id)
            
            elif command_type == "list_plans":
                return await self._handle_list_plans_command(user_id)
            
            elif command_type == "create_plan":
                return await self._handle_create_plan_command(params, message, user_id, app_id, db_id)
            
            else:
                return ChatResponse(
                    success=False,
                    message="Comando no reconocido",
                    response_type="error",
                    data={"error": "Unknown command"}
                )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error ejecutando comando: {e}")
            return ChatResponse(
                success=False,
                message=f"Error ejecutando comando: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    # ===== MANEJADORES DE COMANDOS =====
    
    async def _handle_execute_plan_command(
        self,
        params: Dict[str, Any],
        user_id: UUID,
        chat_id: Optional[UUID]
    ) -> ChatResponse:
        """Maneja el comando de ejecutar plan."""
        try:
            plan_id = params.get('plan_id')
            auto_confirm = params.get('auto_confirm', False)
            
            if not plan_id:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el ID del plan. Usa: 'ejecutar plan: [ID_DEL_PLAN]'",
                    response_type="error",
                    data={"error": "Plan ID required"}
                )
            
            # Ejecutar plan
            return await self.plan_chat_service.execute_plan_from_chat(
                plan_id=UUID(plan_id),
                user_id=user_id,
                auto_confirm=auto_confirm,
                chat_id=chat_id
            )
            
        except ValueError:
            return ChatResponse(
                success=False,
                message="❌ ID de plan inválido. Debe ser un UUID válido.",
                response_type="error",
                data={"error": "Invalid plan ID"}
            )
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error ejecutando plan: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error ejecutando plan: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_pause_execution_command(
        self,
        params: Dict[str, Any],
        user_id: UUID
    ) -> ChatResponse:
        """Maneja el comando de pausar ejecución."""
        try:
            execution_id = params.get('execution_id')
            
            if not execution_id:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el ID de ejecución. Usa: 'pausar ejecución: [ID_EJECUCION]'",
                    response_type="error",
                    data={"error": "Execution ID required"}
                )
            
            # Pausar ejecución
            success = await self.plan_chat_service.plan_execution_service.pause_execution(
                execution_id, user_id
            )
            
            if success:
                return ChatResponse(
                    success=True,
                    message="⏸️ Ejecución pausada exitosamente",
                    response_type="execution_paused",
                    data={"execution_id": execution_id, "paused": True}
                )
            else:
                return ChatResponse(
                    success=False,
                    message="❌ Error pausando la ejecución",
                    response_type="error",
                    data={"error": "Failed to pause execution"}
                )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error pausando ejecución: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error pausando ejecución: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_resume_execution_command(
        self,
        params: Dict[str, Any],
        user_id: UUID
    ) -> ChatResponse:
        """Maneja el comando de reanudar ejecución."""
        try:
            execution_id = params.get('execution_id')
            
            if not execution_id:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el ID de ejecución. Usa: 'reanudar ejecución: [ID_EJECUCION]'",
                    response_type="error",
                    data={"error": "Execution ID required"}
                )
            
            # Reanudar ejecución
            success = await self.plan_chat_service.plan_execution_service.resume_execution(
                execution_id, user_id
            )
            
            if success:
                return ChatResponse(
                    success=True,
                    message="▶️ Ejecución reanudada exitosamente",
                    response_type="execution_resumed",
                    data={"execution_id": execution_id, "resumed": True}
                )
            else:
                return ChatResponse(
                    success=False,
                    message="❌ Error reanudando la ejecución",
                    response_type="error",
                    data={"error": "Failed to resume execution"}
                )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error reanudando ejecución: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error reanudando ejecución: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_cancel_execution_command(
        self,
        params: Dict[str, Any],
        user_id: UUID
    ) -> ChatResponse:
        """Maneja el comando de cancelar ejecución."""
        try:
            execution_id = params.get('execution_id')
            
            if not execution_id:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el ID de ejecución. Usa: 'cancelar ejecución: [ID_EJECUCION]'",
                    response_type="error",
                    data={"error": "Execution ID required"}
                )
            
            # Cancelar ejecución
            success = await self.plan_chat_service.plan_execution_service.cancel_execution(
                execution_id, user_id
            )
            
            if success:
                return ChatResponse(
                    success=True,
                    message="🛑 Ejecución cancelada exitosamente",
                    response_type="execution_cancelled",
                    data={"execution_id": execution_id, "cancelled": True}
                )
            else:
                return ChatResponse(
                    success=False,
                    message="❌ Error cancelando la ejecución",
                    response_type="error",
                    data={"error": "Failed to cancel execution"}
                )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error cancelando ejecución: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error cancelando ejecución: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_plan_status_command(
        self,
        params: Dict[str, Any],
        user_id: UUID
    ) -> ChatResponse:
        """Maneja el comando de estado del plan."""
        try:
            execution_id = params.get('execution_id')
            
            if not execution_id:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el ID de ejecución. Usa: 'estado ejecución: [ID_EJECUCION]'",
                    response_type="error",
                    data={"error": "Execution ID required"}
                )
            
            # Obtener estado
            return await self.plan_chat_service.get_plan_status_from_chat(execution_id, user_id)
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error obteniendo estado: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error obteniendo estado: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_list_plans_command(
        self,
        user_id: UUID
    ) -> ChatResponse:
        """Maneja el comando de listar planes."""
        try:
            # Obtener planes del usuario
            plans = await self.plan_chat_service.plan_service.list_plans(
                user_id, 
                {"user_id": user_id, "limit": 10, "offset": 0}
            )
            
            if not plans.plans:
                return ChatResponse(
                    success=True,
                    message="📋 No tienes planes creados aún.",
                    response_type="plans_list",
                    data={"plans": [], "total": 0}
                )
            
            # Crear lista legible
            plans_list = []
            for plan in plans.plans:
                plans_list.append(f"• **{plan.title}** (ID: {plan.id})")
                plans_list.append(f"  - Estado: {plan.status}")
                plans_list.append(f"  - Prioridad: {plan.priority}")
                plans_list.append(f"  - Creado: {plan.created_at}")
                plans_list.append("")
            
            return ChatResponse(
                success=True,
                message=f"📋 **Tus planes:**\n\n" + "\n".join(plans_list),
                response_type="plans_list",
                data={"plans": plans.plans, "total": plans.total}
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error listando planes: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error listando planes: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
    
    async def _handle_create_plan_command(
        self,
        params: Dict[str, Any],
        message: str,
        user_id: UUID,
        app_id: Optional[UUID],
        db_id: Optional[UUID]
    ) -> ChatResponse:
        """Maneja el comando de crear plan."""
        try:
            plan_objective = params.get('plan_objective')
            
            if not plan_objective:
                return ChatResponse(
                    success=False,
                    message="❌ No se especificó el objetivo del plan. Usa: 'crear plan para: [OBJETIVO]'",
                    response_type="error",
                    data={"error": "Plan objective required"}
                )
            
            # Crear plan usando el servicio de integración
            return await self.plan_chat_service.process_chat_message(
                message=plan_objective,
                user_id=user_id,
                app_id=app_id,
                db_id=db_id
            )
            
        except Exception as e:
            self.logger.error(f"[PlanChatCommands] ❌ Error creando plan: {e}")
            return ChatResponse(
                success=False,
                message=f"❌ Error creando plan: {str(e)}",
                response_type="error",
                data={"error": str(e)}
            )
