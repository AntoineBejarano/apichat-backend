"""
Graph Runner Module
───────────────────
Maneja la ejecución de los grafos de exploración y guía.
"""

import logging
from typing import Any, Dict, Optional, List
from uuid import UUID
import uuid

from .response_processor import ResponseProcessor

logger = logging.getLogger(__name__)


class GraphRunner:
    """
    Ejecuta los grafos de exploración y guía del orchestrator.
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.exploration_service = factory.get_strategy_service()
        self.guided_service = factory.get_guided_service()  # Servicio real de grafos guiados
    
    def select_graph_runner(self, explorer: bool):
        """
        Selecciona el runner apropiado basado en el modo.
        
        Args:
            explorer: True para modo exploración, False para modo guiado
            
        Returns:
            Servicio apropiado para ejecutar el grafo
        """
        if explorer:
            logger.info("[GraphRunner] 🧭 Usando modo exploración")
            return self.exploration_service
        else:
            logger.info("[GraphRunner] 🎯 Usando modo guiado")
            return self.guided_service
    
    def normalize_graph_output(self, output: Any) -> Dict[str, Any]:
        """
        Normaliza la salida del grafo para asegurar consistencia.
        
        Args:
            output: Salida del grafo
            
        Returns:
            Salida normalizada
        """
        logger.info(f"[GraphRunner] 🔄 Normalizando salida del grafo: {type(output)}")
        
        if isinstance(output, dict):
            normalized = output.copy()
        elif hasattr(output, 'model_dump'):
            # Objeto Pydantic
            normalized = output.model_dump()
        elif hasattr(output, '__dict__'):
            # Objeto con atributos
            normalized = {}
            for key, value in output.__dict__.items():
                if not key.startswith('_'):
                    normalized[key] = value
        else:
            # Otro tipo - convertir a string
            normalized = {"content": str(output)}
        
        # Asegurar que siempre tenga un campo 'content'
        if "content" not in normalized:
            if "result" in normalized:
                normalized["content"] = normalized["result"]
            elif "output" in normalized:
                normalized["content"] = normalized["output"]
            else:
                normalized["content"] = str(normalized)
        
        logger.info(f"[GraphRunner] ✅ Salida normalizada: {list(normalized.keys())}")
        return normalized
    
    async def run_exploration_graph(
        self,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo de exploración.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado de la exploración
        """
        logger.info("[GraphRunner] 🧭 Ejecutando grafo de exploración")
        
        try:
            # Ejecutar el grafo de exploración
            result = await self.exploration_service.run_exploration_graph(
                chat_id=chat_id,
                user_message=message,
                context=context
            )
            
            # Normalizar la salida
            normalized_result = self.normalize_graph_output(result)
            
            logger.info("[GraphRunner] ✅ Grafo de exploración ejecutado exitosamente")
            return normalized_result
            
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error ejecutando grafo de exploración: {e}")
            return {
                "error": f"Error en exploración: {str(e)}",
                "content": "No se pudo procesar la consulta en modo exploración."
            }
    
    async def run_guided_graph(
        self,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo guiado con selección automática de recursos y confirmación.
        
        Args:
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado del grafo guiado
        """
        logger.info("[GraphRunner] 🎯 Ejecutando grafo guiado con selección automática de recursos")
        
        try:
            # 🚀 FASE 2: Selección automática de recursos usando ResourceSelectorService
            resource_selector = self.factory.get_resource_selector_service()
            
            # Obtener candidatos de DBs y Apps del contexto
            candidate_dbs = context.get('databases', [])
            candidate_apps = context.get('apps', [])
            
            if not candidate_dbs or not candidate_apps:
                logger.warning("[GraphRunner] ⚠️ No hay candidatos de recursos en el contexto")
                # Fallback al comportamiento original
                result = await self.guided_service.run_guided_graph(
                    chat_id=chat_id,
                    user_message=message,
                    context=context
                )
            else:
                # Seleccionar automáticamente 1 DB + 1 App
                logger.info(f"[GraphRunner] 🔍 Seleccionando recursos de {len(candidate_dbs)} DBs y {len(candidate_apps)} Apps")
                
                resource_selection = await resource_selector.select_for_guided(
                    prompt=message,
                    candidate_dbs=candidate_dbs,
                    candidate_apps=candidate_apps
                )
                
                # 🚀 FASE 3: Confirmación amable de recursos seleccionados
                logger.info("[GraphRunner] 🔄 Solicitando confirmación de recursos seleccionados")
                
                # Crear opciones de confirmación
                confirm_options = [
                    {
                        "id": "confirm",
                        "label": "✅ Confirmar y continuar",
                        "description": "Usar estos recursos para ejecutar la consulta"
                    },
                    {
                        "id": "edit",
                        "label": "✏️ Editar selección",
                        "description": "Cambiar la selección de recursos"
                    },
                    {
                        "id": "cancel",
                        "label": "❌ Cancelar",
                        "description": "Abortar la operación"
                    }
                ]
                
                # Emitir solicitud de decisión
                decision_id = str(uuid.uuid4())
                
                # Obtener el orchestrator service del factory
                orchestrator_service = self.factory.get_orchestrator_service()
                
                await orchestrator_service.emit_decision_request(
                    decision_id=decision_id,
                    title="Confirmar recursos seleccionados",
                    description=f"Se han seleccionado automáticamente:\n\n🗄️ **Base de datos**: {resource_selection.database.resource_name} (confianza: {resource_selection.database.score:.1%})\n📱 **Aplicación**: {resource_selection.application.resource_name} (confianza: {resource_selection.application.score:.1%})\n\n**Razones de selección**:\n" + "\n".join([f"• {reason}" for reason in resource_selection.selection_reasons[:3]]),
                    options=confirm_options,
                    timeout_seconds=30,
                    default_action="cancel"
                )
                
                # Esperar confirmación del usuario
                decision_manager = orchestrator_service.decision_manager
                user_action = await decision_manager.request_decision(
                    title="Confirmar recursos seleccionados",
                    description=f"Se han seleccionado automáticamente:\n\n🗄️ **Base de datos**: {resource_selection.database.resource_name} (confianza: {resource_selection.database.score:.1%})\n📱 **Aplicación**: {resource_selection.application.resource_name} (confianza: {resource_selection.application.score:.1%})\n\n**Razones de selección**:\n" + "\n".join([f"• {reason}" for reason in resource_selection.selection_reasons[:3]]),
                    options=confirm_options,
                    timeout_seconds=30,
                    default_action="cancel"
                )
                
                # Procesar la decisión del usuario
                if user_action == "cancel":
                    logger.info("[GraphRunner] ❌ Usuario canceló la operación")
                    return {
                        "content": "Operación cancelada por el usuario.",
                        "cancelled": True,
                        "reason": "user_cancelled"
                    }
                elif user_action == "edit":
                    logger.info("[GraphRunner] ✏️ Usuario solicitó editar la selección")
                    # Por ahora, fallback a comportamiento original
                    # TODO: Implementar lógica de edición en Fase 8
                    return {
                        "content": "Función de edición de selección estará disponible próximamente. Por favor, inténtalo de nuevo.",
                        "cancelled": True,
                        "reason": "edit_not_implemented"
                    }
                elif user_action == "confirm":
                    logger.info("[GraphRunner] ✅ Usuario confirmó los recursos seleccionados")
                    
                    # Actualizar el contexto con la selección confirmada
                    guided_context = context.copy()
                    guided_context['selected_database'] = resource_selection.database.metadata
                    guided_context['selected_application'] = resource_selection.application.metadata
                    guided_context['resource_selection'] = {
                        'database': {
                            'id': resource_selection.database.resource_id,
                            'name': resource_selection.database.resource_name,
                            'score': resource_selection.database.score,
                            'reasons': resource_selection.database.reasons
                        },
                        'application': {
                            'id': resource_selection.application.resource_id,
                            'name': resource_selection.application.resource_name,
                            'score': resource_selection.application.score,
                            'reasons': resource_selection.application.reasons
                        },
                        'combined_score': resource_selection.combined_score,
                        'confidence': resource_selection.confidence
                    }
                    
                    logger.info(f"[GraphRunner] ✅ Recursos confirmados:")
                    logger.info(f"  🗄️  DB: {resource_selection.database.resource_name} (score: {resource_selection.database.score:.2f})")
                    logger.info(f"  📱 App: {resource_selection.application.resource_name} (score: {resource_selection.application.score:.2f})")
                    logger.info(f"  🎯 Score combinado: {resource_selection.combined_score:.2f}")
                    
                    # 🚀 FASE 4: Generar plan de ejecución
                    logger.info("[GraphRunner] 🚀 Generando plan de ejecución...")
                    try:
                        plan_builder = self.factory.get_plan_builder_service()
                        
                        # Preparar contexto para el plan
                        plan_context = {
                            'database_schema': guided_context.get('database_schema', ''),
                            'app_functions': guided_context.get('app_functions', [])
                        }
                        
                        # Generar plan usando el LLM
                        guided_plan = await plan_builder.build_guided_plan(
                            context=plan_context,
                            database_info={
                                'resource_name': resource_selection.database.resource_name,
                                'description': resource_selection.database.metadata.get('description', 'Sin descripción')
                            },
                            application_info={
                                'resource_name': resource_selection.application.resource_name,
                                'description': resource_selection.application.metadata.get('description', 'Sin descripción')
                            },
                            user_prompt=message
                        )
                        
                        # Añadir el plan al contexto
                        guided_context['execution_plan'] = guided_plan.model_dump()
                        guided_context['plan_metadata'] = {
                            'title': guided_plan.title,
                            'description': guided_plan.description,
                            'total_steps': len(guided_plan.steps),
                            'estimated_cost': guided_plan.total_estimated_cost,
                            'requires_confirmation': guided_plan.requires_confirmation
                        }
                        
                        logger.info(f"[GraphRunner] ✅ Plan generado: {guided_plan.title}")
                        logger.info(f"  📋 Pasos: {len(guided_plan.steps)}")
                        logger.info(f"  💰 Costo estimado: {guided_plan.total_estimated_cost}")
                        logger.info(f"  ⚠️  Requiere confirmación: {guided_plan.requires_confirmation}")
                        
                        # Si el plan requiere confirmación, solicitar al usuario
                        if guided_plan.requires_confirmation:
                            logger.info("[GraphRunner] ⚠️ Plan requiere confirmación del usuario")
                            
                            # Crear opciones de confirmación del plan
                            plan_confirm_options = [
                                {"id": "confirm_plan", "label": "✅ Ejecutar Plan", "description": "Proceder con la ejecución"},
                                {"id": "cancel_plan", "label": "❌ Cancelar", "description": "Cancelar la operación"}
                            ]
                            
                            # Solicitar confirmación del plan
                            plan_decision_id = str(uuid.uuid4())
                            await orchestrator_service.emit_decision_request(
                                decision_id=plan_decision_id,
                                title="Confirmar Plan de Ejecución",
                                description=f"**Plan**: {guided_plan.title}\n\n{guided_plan.description}\n\n**Pasos**:\n" + "\n".join([f"{i+1}. {step.description}" for i, step in enumerate(guided_plan.steps)]) + f"\n\n**Costo estimado**: {guided_plan.total_estimated_cost}\n**Riesgo**: {max([step.risk_level for step in guided_plan.steps])}",
                                options=plan_confirm_options,
                                timeout_seconds=45,
                                default_action="cancel_plan"
                            )
                            
                            # Esperar confirmación del plan
                            plan_user_action = await decision_manager.request_decision(
                                title="Confirmar Plan de Ejecución",
                                description=f"**Plan**: {guided_plan.title}\n\n{guided_plan.description}\n\n**Pasos**:\n" + "\n".join([f"{i+1}. {step.description}" for i, step in enumerate(guided_plan.steps)]) + f"\n\n**Costo estimado**: {guided_plan.total_estimated_cost}\n**Riesgo**: {max([step.risk_level for step in guided_plan.steps])}",
                                options=plan_confirm_options,
                                timeout_seconds=45,
                                default_action="cancel_plan"
                            )
                            
                            if plan_user_action == "cancel_plan":
                                logger.info("[GraphRunner] ❌ Usuario canceló el plan de ejecución")
                                return {
                                    "content": "Plan de ejecución cancelado por el usuario.",
                                    "cancelled": True,
                                    "reason": "plan_cancelled"
                                }
                            elif plan_user_action == "confirm_plan":
                                logger.info("[GraphRunner] ✅ Usuario confirmó el plan de ejecución")
                            else:
                                logger.warning(f"[GraphRunner] ⚠️ Acción desconocida del plan: {plan_user_action}, cancelando")
                                return {
                                    "content": "Operación cancelada debido a una respuesta inesperada del plan.",
                                    "cancelled": True,
                                    "reason": "unknown_plan_action"
                                }
                        
                        # Ejecutar el grafo guiado con el contexto actualizado (incluyendo el plan)
                        logger.info("[GraphRunner] 🚀 Ejecutando plan paso a paso con streaming...")
                        
                        # 🚀 FASE 6: Ejecución con streaming por cada paso
                        if guided_plan.steps:
                            # Emitir progreso inicial
                            await orchestrator_service.emit_status_progress(
                                chat_id=chat_id,
                                step=1,
                                total_steps=len(guided_plan.steps),
                                message="Iniciando ejecución del plan..."
                            )
                            
                            # Ejecutar cada paso del plan con streaming
                            step_results = []
                            for i, step in enumerate(guided_plan.steps):
                                step_number = i + 1
                                total_steps = len(guided_plan.steps)
                                
                                # Emitir progreso del paso actual
                                await orchestrator_service.emit_status_progress(
                                    chat_id=chat_id,
                                    step=step_number,
                                    total_steps=total_steps,
                                    message=f"Ejecutando paso {step_number}: {step.description}"
                                )
                                
                                try:
                                    # Ejecutar el paso individual
                                    step_result = await self._execute_single_step(
                                        step=step,
                                        context=guided_context,
                                        chat_id=chat_id
                                    )
                                    
                                    # Emitir resultado parcial del paso
                                    await orchestrator_service.emit_result_partial(
                                        chat_id=chat_id,
                                        step_number=step_number,
                                        step_description=step.description,
                                        result=step_result,
                                        preview=self._generate_step_preview(step_result)
                                    )
                                    
                                    step_results.append({
                                        'step_number': step_number,
                                        'description': step.description,
                                        'result': step_result,
                                        'status': 'completed'
                                    })
                                    
                                    logger.info(f"[GraphRunner] ✅ Paso {step_number} completado: {step.description}")
                                    
                                except Exception as step_error:
                                    logger.error(f"[GraphRunner] ❌ Error en paso {step_number}: {step_error}")
                                    
                                    step_results.append({
                                        'step_number': step_number,
                                        'description': step.description,
                                        'error': str(step_error),
                                        'status': 'failed'
                                    })
                                    
                                    # Emitir error del paso
                                    await orchestrator_service.emit_error_user_facing(
                                        chat_id=chat_id,
                                        code="step_execution_error",
                                        human_message=f"Error ejecutando paso {step_number}: {step.description}",
                                        suggested_actions=["Reintentar", "Continuar con siguiente paso", "Cancelar ejecución"]
                                    )
                            
                            # Emitir resultado final con resumen
                            final_result = {
                                'plan_title': guided_plan.title,
                                'plan_description': guided_plan.description,
                                'total_steps': total_steps,
                                'completed_steps': len([r for r in step_results if r['status'] == 'completed']),
                                'failed_steps': len([r for r in step_results if r['status'] == 'failed']),
                                'step_results': step_results,
                                'estimated_cost': guided_plan.total_estimated_cost,
                                'next_actions': self._generate_next_actions(step_results, guided_context)
                            }
                            
                            # 🎯 FASE 9: Usar ResponseProcessor para formatear respuesta final
                            response_processor = ResponseProcessor()
                            summary = response_processor.format_guided_execution(
                                plan=guided_plan,
                                outcomes=step_results,
                                audit_id=str(chat_id),
                                usage={
                                    'tokens_used': final_result.get('estimated_cost', 0),
                                    'execution_time': final_result.get('total_steps', 0) * 0.5,  # Estimación
                                    'estimated_cost': final_result.get('estimated_cost', 'N/A')
                                },
                                next_actions=final_result['next_actions']
                            )
                            
                            await orchestrator_service.emit_result_final(
                                summary=summary,
                                data=final_result,
                                next_actions=final_result['next_actions'],
                                usage_stats={
                                    'tokens_used': final_result.get('estimated_cost', 0),
                                    'execution_time': final_result.get('total_steps', 0) * 0.5,
                                    'estimated_cost': final_result.get('estimated_cost', 'N/A')
                                }
                            )
                            
                            logger.info(f"[GraphRunner] ✅ Plan ejecutado: {final_result['completed_steps']}/{total_steps} pasos completados")
                            
                            # Normalizar y retornar resultado
                            normalized_result = self.normalize_graph_output(final_result)
                            return normalized_result
                        
                        else:
                            # Si no hay pasos, ejecutar normalmente
                            logger.info("[GraphRunner] 📋 No hay pasos en el plan, ejecutando normalmente")
                            result = await self.guided_service.run_guided_graph(
                                chat_id=chat_id,
                                user_message=message,
                                context=guided_context
                            )
                        
                    except Exception as plan_error:
                        logger.error(f"[GraphRunner] ❌ Error generando plan: {plan_error}")
                        # Continuar sin plan, usando comportamiento original
                        logger.info("[GraphRunner] 🆘 Continuando sin plan de ejecución")
                        result = await self.guided_service.run_guided_graph(
                            chat_id=chat_id,
                            user_message=message,
                            context=guided_context
                        )
            
            # Normalizar la salida
            normalized_result = self.normalize_graph_output(result)
            
            logger.info("[GraphRunner] ✅ Grafo guiado ejecutado exitosamente")
            return normalized_result
            
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error ejecutando grafo guiado: {e}")
            return {
                "error": f"Error en modo guiado: {str(e)}",
                "content": "No se pudo procesar la consulta en modo guiado."
            }
    
    async def _execute_single_step(
        self,
        step: Any,
        context: Dict[str, Any],
        chat_id: UUID
    ) -> Dict[str, Any]:
        """
        Ejecuta un paso individual del plan.
        
        Args:
            step: Paso del plan a ejecutar
            context: Contexto de ejecución
            chat_id: ID del chat
            
        Returns:
            Resultado de la ejecución del paso
        """
        logger.info(f"[GraphRunner] 🔧 Ejecutando paso: {step.description}")
        
        try:
            # Por ahora, simulamos la ejecución del paso
            # TODO: Integrar con ExecutionEngineService en Fase 7
            if hasattr(step, 'action_type'):
                if step.action_type == 'database_query':
                    # Simular consulta a base de datos
                    return {
                        'type': 'database_query',
                        'result': f"Resultado simulado de consulta: {step.description}",
                        'rows_affected': 0,
                        'execution_time': 0.1
                    }
                elif step.action_type == 'api_call':
                    # Simular llamada a API
                    return {
                        'type': 'api_call',
                        'result': f"Resultado simulado de API: {step.description}",
                        'status_code': 200,
                        'execution_time': 0.2
                    }
                else:
                    # Paso genérico
                    return {
                        'type': 'generic',
                        'result': f"Paso completado: {step.description}",
                        'execution_time': 0.1
                    }
            else:
                # Paso sin tipo específico
                return {
                    'type': 'unknown',
                    'result': f"Paso ejecutado: {step.description}",
                    'execution_time': 0.1
                }
                
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error ejecutando paso: {e}")
            raise
    
    def _generate_step_preview(self, step_result: Dict[str, Any]) -> str:
        """
        Genera una vista previa del resultado de un paso.
        
        Args:
            step_result: Resultado del paso
            
        Returns:
            Vista previa como string
        """
        try:
            if step_result.get('type') == 'database_query':
                return f"📊 Consulta ejecutada: {step_result.get('result', 'Sin resultado')}"
            elif step_result.get('type') == 'api_call':
                return f"🔌 API llamada: {step_result.get('result', 'Sin resultado')}"
            else:
                return f"✅ Paso completado: {step_result.get('result', 'Sin resultado')}"
        except Exception as e:
            logger.error(f"[GraphRunner] ❌ Error generando preview: {e}")
            return "❌ Error generando vista previa"
    
    def _generate_next_actions(self, step_results: List[Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
        """
        Genera las siguientes acciones sugeridas basadas en los resultados.
        
        Args:
            step_results: Resultados de todos los pasos
            context: Contexto de ejecución
            
        Returns:
            Lista de acciones sugeridas
        """
        actions = []
        
        # Analizar resultados para sugerir acciones
        completed_steps = [r for r in step_results if r['status'] == 'completed']
        failed_steps = [r for r in step_results if r['status'] == 'failed']
        
        if completed_steps:
            actions.append("Ver resultados detallados")
            actions.append("Exportar resultados")
        
        if failed_steps:
            actions.append("Reintentar pasos fallidos")
            actions.append("Ver logs de error")
        
        # Acciones generales
        actions.append("Nueva consulta")
        actions.append("Guardar plan")
        
        return actions[:5]  # Máximo 5 acciones
    
    async def run_graph(
        self,
        explorer: bool,
        chat_id: UUID,
        message: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Ejecuta el grafo apropiado basado en el modo.
        
        Args:
            explorer: True para modo exploración, False para modo guiado
            chat_id: ID del chat
            message: Mensaje del usuario
            context: Contexto del chat
            
        Returns:
            Resultado del grafo ejecutado
        """
        if explorer:
            return await self.run_exploration_graph(chat_id, message, context)
        else:
            return await self.run_guided_graph(chat_id, message, context)
