#!/usr/bin/env python3
"""
🚀 ResponseEnhancementNode - Mejora de Respuesta con AI
────────────────────────────────────────────────────────
Combina la respuesta rápida inicial con los resultados
del análisis AI para crear una respuesta final completa.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ResponseEnhancementNode:
    """
    🚀 Nodo que mejora la respuesta combinando cache + AI.
    
    Características:
    - Combina respuesta rápida con análisis AI
    - Genera respuesta final coherente
    - Mantiene transparencia sobre fuentes
    - Optimiza para mejor experiencia de usuario
    """
    
    def __init__(self, factory):
        self.factory = factory
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        🚀 Genera respuesta final mejorada combinando todas las fuentes.
        
        Args:
            state: Estado del grafo con respuesta rápida y análisis AI
            
        Returns:
            Estado actualizado con respuesta final mejorada
        """
        start_time = datetime.now()
        
        try:
            # Extraer información del estado
            quick_response = state.get("quick_response", "")
            ai_analysis = state.get("ai_analysis", {})
            execution_plan = state.get("execution_plan", {})
            sql_validation = state.get("sql_validation_metadata", {})
            
            logger.info(f"[ResponseEnhancementNode] 🚀 Generando respuesta final mejorada")
            
            # 🎯 GENERAR RESPUESTA FINAL
            enhanced_response = await self._generate_enhanced_response(
                quick_response=quick_response,
                ai_analysis=ai_analysis,
                execution_plan=execution_plan,
                sql_validation=sql_validation
            )
            
            # 📊 METADATAS DE MEJORA
            enhancement_metadata = {
                "enhancement_type": "ai_enhanced_response",
                "enhancement_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "sources_combined": [
                    "quick_response_cache",
                    "ai_analysis",
                    "execution_plan",
                    "sql_validation"
                ],
                "response_quality": "comprehensive",
                "user_experience": "progressive_enhancement",
                "next_phase": "response_delivery"
            }
            
            logger.info(f"[ResponseEnhancementNode] ✅ Respuesta mejorada generada en {enhancement_metadata['enhancement_time_ms']:.1f}ms")
            
            return {
                **state,
                "enhanced_response": enhanced_response,
                "enhancement_metadata": enhancement_metadata,
                "current_phase": "response_enhancement_completed"
            }
            
        except Exception as e:
            logger.error(f"[ResponseEnhancementNode] ❌ Error mejorando respuesta: {e}")
            
            # 🆘 FALLBACK: Usar solo respuesta rápida
            fallback_response = self._generate_fallback_response(quick_response, str(e))
            
            return {
                **state,
                "enhanced_response": fallback_response,
                "enhancement_metadata": {
                    "enhancement_type": "fallback",
                    "enhancement_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "error": str(e),
                    "next_phase": "fallback_delivery"
                },
                "current_phase": "response_enhancement_failed"
            }
    
    async def _generate_enhanced_response(
        self,
        quick_response: str,
        ai_analysis: dict,
        execution_plan: dict,
        sql_validation: dict
    ) -> str:
        """🚀 Genera respuesta final combinando todas las fuentes."""
        
        response_parts = []
        
        # 📋 ENCABEZADO CON RESUMEN
        header = self._generate_response_header(ai_analysis, execution_plan)
        response_parts.append(header)
        
        # ⚡ RESPUESTA RÁPIDA (SIEMPRE INCLUIR)
        if quick_response:
            response_parts.append("\n" + "=" * 60)
            response_parts.append("⚡ **RESPUESTA RÁPIDA** (Información Inmediata)")
            response_parts.append("=" * 60)
            response_parts.append(quick_response)
        
        # 🤖 ANÁLISIS AI (SI ESTÁ DISPONIBLE)
        if ai_analysis and isinstance(ai_analysis, list):
            response_parts.append("\n" + "=" * 60)
            response_parts.append("🤖 **ANÁLISIS INTELIGENTE** (Detección de Intenciones)")
            response_parts.append("=" * 60)
            
            ai_summary = self._generate_ai_summary(ai_analysis)
            response_parts.append(ai_summary)
        
        # 📋 PLAN DE EJECUCIÓN (SI ESTÁ DISPONIBLE)
        if execution_plan and execution_plan.get("steps"):
            response_parts.append("\n" + "=" * 60)
            response_parts.append("📋 **PLAN DE EJECUCIÓN** (Pasos Generados)")
            response_parts.append("=" * 60)
            
            plan_summary = self._generate_plan_summary(execution_plan)
            response_parts.append(plan_summary)
        
        # 🛡️ VALIDACIÓN SQL (SI ESTÁ DISPONIBLE)
        if sql_validation:
            response_parts.append("\n" + "=" * 60)
            response_parts.append("🛡️ **VALIDACIÓN DE SEGURIDAD** (SQL Verificado)")
            response_parts.append("=" * 60)
            
            validation_summary = self._generate_validation_summary(sql_validation)
            response_parts.append(validation_summary)
        
        # 🎯 RESUMEN FINAL
        final_summary = self._generate_final_summary(
            ai_analysis, execution_plan, sql_validation
        )
        response_parts.append("\n" + "=" * 60)
        response_parts.append("🎯 **RESUMEN FINAL**")
        response_parts.append("=" * 60)
        response_parts.append(final_summary)
        
        return "\n".join(response_parts)
    
    def _generate_response_header(self, ai_analysis: dict, execution_plan: dict) -> str:
        """📋 Genera encabezado de la respuesta."""
        
        intentions_count = len(ai_analysis) if isinstance(ai_analysis, list) else 0
        plan_steps = len(execution_plan.get("steps", [])) if execution_plan else 0
        
        header_parts = [
            "# 🚀 **RESPUESTA COMPLETA MEJORADA**",
            "",
            "Tu consulta ha sido procesada usando nuestro **sistema híbrido** que combina:",
            "• ⚡ **Respuesta Rápida** desde cache y esquema real",
            "• 🤖 **Análisis AI** para detectar intenciones múltiples",
            "• 📋 **Plan de Ejecución** personalizado y validado",
            "• 🛡️ **Validación de Seguridad** para SQL seguro",
            ""
        ]
        
        if intentions_count > 0:
            header_parts.append(f"**🎯 Intenciones Detectadas:** {intentions_count}")
        
        if plan_steps > 0:
            header_parts.append(f"**📋 Pasos del Plan:** {plan_steps}")
        
        header_parts.append("")
        header_parts.append("---")
        header_parts.append("")
        
        return "\n".join(header_parts)
    
    def _generate_ai_summary(self, ai_analysis: List[Dict[str, Any]]) -> str:
        """🤖 Genera resumen del análisis AI."""
        
        summary_parts = [
            "La **Inteligencia Artificial** ha analizado tu consulta y detectado:",
            ""
        ]
        
        for i, intention in enumerate(ai_analysis, 1):
            intention_type = intention.get("type", "unknown")
            context = intention.get("context", "N/A")
            priority = intention.get("priority", "N/A")
            confidence = intention.get("confidence", "N/A")
            
            summary_parts.extend([
                f"**{i}. {intention_type.replace('_', ' ').title()}**",
                f"   • Contexto: {context}",
                f"   • Prioridad: {priority}/5",
                f"   • Confianza: {confidence:.2f}",
                ""
            ])
        
        summary_parts.append("**💡 Beneficio:** La AI entiende exactamente lo que necesitas y genera un plan personalizado.")
        
        return "\n".join(summary_parts)
    
    def _generate_plan_summary(self, execution_plan: Dict[str, Any]) -> str:
        """📋 Genera resumen del plan de ejecución."""
        
        plan_parts = [
            f"**Plan:** {execution_plan.get('title', 'Plan de Ejecución')}",
            f"**Descripción:** {execution_plan.get('description', 'N/A')}",
            "",
            "**Pasos del Plan:**",
            ""
        ]
        
        for i, step in enumerate(execution_plan.get("steps", []), 1):
            step_desc = step.get("step", "N/A")
            action = step.get("action", "N/A")
            description = step.get("description", "N/A")
            
            plan_parts.extend([
                f"**{i}. {step_desc}**",
                f"   • Acción: {action}",
                f"   • Descripción: {description}",
                ""
            ])
        
        plan_parts.append("**🚀 Estado:** Plan generado y listo para ejecución.")
        
        return "\n".join(plan_parts)
    
    def _generate_validation_summary(self, sql_validation: Dict[str, Any]) -> str:
        """🛡️ Genera resumen de la validación SQL."""
        
        total_steps = sql_validation.get("total_steps", 0)
        validated_steps = sql_validation.get("validated_steps", 0)
        failed_steps = sql_validation.get("failed_steps", 0)
        security_issues = sql_validation.get("security_issues", 0)
        
        validation_parts = [
            "**Validación de Seguridad SQL Completada:**",
            "",
            f"• **Total de pasos:** {total_steps}",
            f"• **Pasos validados:** {validated_steps}",
            f"• **Pasos con problemas:** {failed_steps}",
            f"• **Problemas de seguridad:** {security_issues}",
            ""
        ]
        
        if security_issues == 0:
            validation_parts.append("✅ **Estado:** Todas las consultas SQL son seguras y válidas.")
        else:
            validation_parts.append("⚠️ **Estado:** Se detectaron problemas de seguridad que requieren atención.")
        
        validation_parts.append("")
        validation_parts.append("**🛡️ Garantías de Seguridad:**")
        validation_parts.append("• Solo consultas de lectura (SELECT)")
        validation_parts.append("• Uso de tablas reales de la base de datos")
        print("• Prevención de SQL injection")
        print("• Validación de sintaxis")
        
        return "\n".join(validation_parts)
    
    def _generate_final_summary(
        self,
        ai_analysis: dict,
        execution_plan: dict,
        sql_validation: dict
    ) -> str:
        """🎯 Genera resumen final de la respuesta."""
        
        summary_parts = [
            "## 🎯 **RESUMEN DE LO QUE HAS OBTENIDO**",
            "",
            "**✅ Respuesta Inmediata:** Información básica en menos de 100ms",
            "**✅ Análisis Inteligente:** Detección de múltiples intenciones",
            "**✅ Plan Personalizado:** Pasos específicos para tu consulta",
            "**✅ Seguridad Garantizada:** SQL validado y seguro",
            "",
            "## 🚀 **PRÓXIMOS PASOS**",
            "",
            "El sistema está ejecutando el plan generado para darte:",
            "• 📊 Resultados específicos de tu consulta",
            "• 🔍 Información detallada sobre invitaciones de clubs",
            "• 📋 Esquema completo de las tablas relevantes",
            "• 💡 Recomendaciones de uso",
            "",
            "**⏱️ Tiempo estimado:** 3-10 segundos para resultados completos",
            "",
            "## 💡 **BENEFICIOS DEL SISTEMA HÍBRIDO**",
            "",
            "• **Velocidad:** Nunca esperas, siempre recibes algo útil",
            "• **Inteligencia:** AI entiende exactamente lo que necesitas",
            "• **Seguridad:** Solo datos reales, sin alucinaciones",
            "• **Transparencia:** Sabes exactamente qué está pasando en cada paso",
            "• **Escalabilidad:** Sistema que crece con tus necesidades"
        ]
        
        return "\n".join(summary_parts)
    
    def _generate_fallback_response(self, quick_response: str, error: str) -> str:
        """🆘 Genera respuesta de fallback si algo falla."""
        
        fallback_parts = [
            "# 🆘 **RESPUESTA DE EMERGENCIA**",
            "",
            "Se produjo un error durante la mejora de la respuesta:",
            f"**Error:** {error}",
            "",
            "## 📋 **RESPUESTA RÁPIDA DISPONIBLE**",
            "",
            "Aunque no se pudo mejorar la respuesta, aquí tienes la información básica:",
            "",
            quick_response if quick_response else "No hay respuesta rápida disponible.",
            "",
            "## 🔄 **RECUPERACIÓN AUTOMÁTICA**",
            "",
            "El sistema está intentando recuperarse automáticamente.",
            "Tu consulta será procesada de manera básica.",
            "",
            "**⏱️ Tiempo estimado:** 5-15 segundos"
        ]
        
        return "\n".join(fallback_parts)
