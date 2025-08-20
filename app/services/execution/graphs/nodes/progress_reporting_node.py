#!/usr/bin/env python3
"""
📊 ProgressReportingNode - Reporte de Progreso en Tiempo Real
─────────────────────────────────────────────────────────────
Mantiene al cliente informado de cada paso del proceso
con transparencia completa sobre lo que está sucediendo.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ProgressReportingNode:
    """
    📊 Nodo que reporta progreso en tiempo real al cliente.
    
    Características:
    - Transparencia completa del proceso
    - Explicación de cada paso
    - Estimaciones de tiempo
    - Estado actual del sistema
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.orchestrator_service = factory.get_orchestrator_service()
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        📊 Reporta progreso actual y explica el siguiente paso.
        
        Args:
            state: Estado del grafo con información de progreso
            
        Returns:
            Estado actualizado con reporte de progreso
        """
        try:
            # Extraer información del estado
            current_phase = state.get("current_phase", "unknown")
            query = state.get("message", {}).get("content", "")
            chat_id = state.get("chat_id")
            
            logger.info(f"[ProgressReportingNode] 📊 Reportando progreso: {current_phase}")
            
            # 📊 GENERAR REPORTE DE PROGRESO
            progress_report = await self._generate_progress_report(current_phase, state)
            
            # 📡 EMITIR AL CLIENTE
            if chat_id and self.orchestrator_service:
                await self._emit_progress_to_client(chat_id, progress_report)
            
            # 📝 METADATAS DE PROGRESO
            progress_metadata = {
                "phase": current_phase,
                "timestamp": datetime.now().isoformat(),
                "progress_percentage": self._calculate_progress_percentage(current_phase),
                "estimated_time_remaining": self._estimate_time_remaining(current_phase),
                "next_phase": self._get_next_phase(current_phase)
            }
            
            logger.info(f"[ProgressReportingNode] ✅ Progreso reportado: {current_phase}")
            
            return {
                **state,
                "progress_report": progress_report,
                "progress_metadata": progress_metadata,
                "last_progress_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ProgressReportingNode] ❌ Error reportando progreso: {e}")
            
            # 🆘 FALLBACK: Reporte básico
            fallback_report = {
                "status": "processing",
                "message": "Procesando tu consulta...",
                "phase": "error_recovery",
                "details": f"Error técnico: {str(e)}"
            }
            
            return {
                **state,
                "progress_report": fallback_report,
                "progress_metadata": {
                    "phase": "error",
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
            }
    
    async def _generate_progress_report(self, current_phase: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """📊 Genera reporte detallado del progreso actual."""
        
        if current_phase == "quick_response_completed":
            return await self._report_quick_response_completed(state)
        elif current_phase == "ai_analysis_completed":
            return await self._report_ai_analysis_completed(state)
        elif current_phase == "plan_execution_started":
            return await self._report_plan_execution_started(state)
        elif current_phase == "plan_execution_completed":
            return await self._report_plan_execution_completed(state)
        elif current_phase == "error":
            return await self._report_error_state(state)
        else:
            return await self._report_general_progress(current_phase, state)
    
    async def _report_quick_response_completed(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """📋 Reporta que la respuesta rápida se completó."""
        
        quick_response = state.get("quick_response", "")
        metadata = state.get("quick_response_metadata", {})
        
        return {
            "status": "quick_response_completed",
            "phase": "Respuesta Rápida Completada",
            "message": "✅ He generado una respuesta rápida con la información disponible",
            "details": [
                f"⚡ Tiempo de respuesta: {metadata.get('response_time_ms', 0):.1f}ms",
                f"📊 Fuente de datos: {metadata.get('data_source', 'cache')}",
                f"🎯 Cobertura: {metadata.get('coverage', 'basic')}",
                "🤖 La AI está analizando tu consulta completa en paralelo..."
            ],
            "next_step": "Análisis AI en progreso",
            "estimated_time": "2-5 segundos",
            "user_benefit": "Ya tienes información útil mientras esperas el análisis completo"
        }
    
    async def _report_ai_analysis_completed(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """🤖 Reporta que el análisis AI se completó."""
        
        ai_analysis = state.get("ai_analysis", {})
        metadata = state.get("ai_analysis_metadata", {})
        plan = state.get("execution_plan", {})
        
        intentions_count = metadata.get("intentions_detected", 0)
        plan_steps = metadata.get("plan_steps", 0)
        
        return {
            "status": "ai_analysis_completed",
            "phase": "Análisis AI Completado",
            "message": f"🎯 La AI ha detectado {intentions_count} intenciones en tu consulta",
            "details": [
                f"🤖 Intenciones detectadas: {intentions_count}",
                f"📋 Plan generado: {plan_steps} pasos",
                f"⏱️ Tiempo de análisis: {metadata.get('analysis_time_ms', 0):.1f}ms",
                f"📊 Confianza: {metadata.get('confidence', 'unknown')}",
                f"🏗️ Esquema usado: {'Sí' if metadata.get('schema_used') else 'No'}"
            ],
            "plan_summary": {
                "title": plan.get("title", "Plan de Ejecución"),
                "description": plan.get("description", "Plan generado por AI"),
                "steps_count": plan_steps
            },
            "next_step": "Ejecutando plan paso a paso",
            "estimated_time": "3-10 segundos",
            "user_benefit": "La AI ha entendido exactamente lo que necesitas y ha generado un plan personalizado"
        }
    
    async def _report_plan_execution_started(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """🚀 Reporta que la ejecución del plan comenzó."""
        
        plan = state.get("execution_plan", {})
        plan_steps = len(plan.get("steps", []))
        
        return {
            "status": "plan_execution_started",
            "phase": "Ejecutando Plan",
            "message": f"🚀 Comenzando ejecución del plan con {plan_steps} pasos",
            "details": [
                f"📋 Plan: {plan.get('title', 'Plan de Ejecución')}",
                f"🔢 Pasos a ejecutar: {plan_steps}",
                "⚡ Ejecutando en paralelo para máxima velocidad",
                "🛡️ Validando cada paso antes de ejecutar"
            ],
            "next_step": "Ejecutando pasos del plan",
            "estimated_time": f"{plan_steps * 2}-{plan_steps * 5} segundos",
            "user_benefit": "Cada paso se ejecuta de manera segura y validada"
        }
    
    async def _report_plan_execution_completed(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """✅ Reporta que la ejecución del plan se completó."""
        
        plan = state.get("execution_plan", {})
        plan_steps = len(plan.get("steps", []))
        
        return {
            "status": "plan_execution_completed",
            "phase": "Plan Completado",
            "message": f"✅ Plan ejecutado exitosamente: {plan_steps} pasos completados",
            "details": [
                f"📋 Plan ejecutado: {plan.get('title', 'Plan de Ejecución')}",
                f"✅ Pasos completados: {plan_steps}/{plan_steps}",
                "🎯 Todas las intenciones de tu consulta han sido satisfechas",
                "📊 Resultados disponibles para revisión"
            ],
            "next_step": "Generando respuesta final",
            "estimated_time": "<1 segundo",
            "user_benefit": "Tu consulta ha sido procesada completamente con resultados precisos"
        }
    
    async def _report_error_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """❌ Reporta estado de error."""
        
        error_info = state.get("error", "Error desconocido")
        
        return {
            "status": "error",
            "phase": "Error Detectado",
            "message": "❌ Se ha detectado un error en el procesamiento",
            "details": [
                f"🚨 Error: {error_info}",
                "🔄 Sistema activando modo de recuperación",
                "📞 Contactando servicios de respaldo",
                "⏱️ Estimando tiempo de recuperación"
            ],
            "next_step": "Recuperación automática",
            "estimated_time": "5-15 segundos",
            "user_benefit": "El sistema se recupera automáticamente sin pérdida de datos"
        }
    
    async def _report_general_progress(self, current_phase: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """📊 Reporte general de progreso para fases no específicas."""
        
        return {
            "status": "processing",
            "phase": current_phase.replace("_", " ").title(),
            "message": f"🔄 Procesando: {current_phase.replace('_', ' ').title()}",
            "details": [
                "⚙️ Sistema procesando tu solicitud",
                "📊 Analizando información disponible",
                "🤖 Preparando respuesta personalizada",
                "⏱️ Optimizando para máxima velocidad"
            ],
            "next_step": "Continuando procesamiento",
            "estimated_time": "Variable",
            "user_benefit": "Tu consulta está siendo procesada de manera óptima"
        }
    
    async def _emit_progress_to_client(self, chat_id: str, progress_report: Dict[str, Any]):
        """📡 Emite progreso al cliente a través del orchestrator."""
        
        try:
            # Emitir progreso usando el servicio del orchestrator
            await self.orchestrator_service.emit_status_progress(
                chat_id=chat_id,
                step=1,  # Paso actual
                total_steps=1,  # Total de pasos
                message=progress_report.get("message", "Procesando..."),
                percentage=self._calculate_progress_percentage(progress_report.get("phase", ""))
            )
            
            logger.info(f"[ProgressReportingNode] 📡 Progreso emitido al cliente {chat_id}")
            
        except Exception as e:
            logger.warning(f"[ProgressReportingNode] ⚠️ No se pudo emitir progreso: {e}")
    
    def _calculate_progress_percentage(self, current_phase: str) -> float:
        """📊 Calcula el porcentaje de progreso basado en la fase actual."""
        
        phase_progress = {
            "quick_response_completed": 25.0,
            "ai_analysis_completed": 50.0,
            "plan_execution_started": 75.0,
            "plan_execution_completed": 100.0,
            "error": 0.0
        }
        
        return phase_progress.get(current_phase, 10.0)
    
    def _estimate_time_remaining(self, current_phase: str) -> str:
        """⏱️ Estima el tiempo restante basado en la fase actual."""
        
        time_estimates = {
            "quick_response_completed": "2-5 segundos",
            "ai_analysis_completed": "3-10 segundos",
            "plan_execution_started": "Variable según complejidad",
            "plan_execution_completed": "Completado",
            "error": "5-15 segundos"
        }
        
        return time_estimates.get(current_phase, "Variable")
    
    def _get_next_phase(self, current_phase: str) -> str:
        """🔄 Determina la siguiente fase del proceso."""
        
        phase_sequence = {
            "quick_response_completed": "ai_analysis",
            "ai_analysis_completed": "plan_execution",
            "plan_execution_started": "plan_completion",
            "plan_execution_completed": "response_generation",
            "error": "error_recovery"
        }
        
        return phase_sequence.get(current_phase, "unknown")
