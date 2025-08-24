"""
🎨 Mode Indicator Service: Indicadores visuales de modo activo

Este servicio proporciona indicadores visuales del modo activo,
tips de uso contextuales y transiciones visuales entre modos.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.mode_transition_service import ModeTransitionService

logger = logging.getLogger(__name__)


class IndicatorType(Enum):
    """Tipos de indicadores visuales"""
    MODE_BADGE = "mode_badge"           # Badge del modo activo
    STATUS_INDICATOR = "status_indicator" # Indicador de estado
    PROGRESS_BAR = "progress_bar"        # Barra de progreso
    TIP_BOX = "tip_box"                  # Caja de tips
    TRANSITION_ANIMATION = "transition_animation" # Animación de transición


class VisualStyle(Enum):
    """Estilos visuales disponibles"""
    MODERN = "modern"           # Estilo moderno y minimalista
    CLASSIC = "classic"         # Estilo clásico y tradicional
    COLORFUL = "colorful"       # Estilo colorido y vibrante
    DARK = "dark"               # Estilo oscuro
    LIGHT = "light"             # Estilo claro


class ModeIndicatorService:
    """
    🎨 Servicio de indicadores visuales de modo activo
    
    Funcionalidades:
    - Indicadores visuales del modo activo
    - Tips de uso contextuales
    - Transiciones visuales entre modos
    - Personalización de estilos
    - Métricas de uso de indicadores
    """
    
    def __init__(self, factory):
        """
        Inicializa el servicio de indicadores de modo
        
        Args:
            factory: ServiceFactory para obtener servicios
        """
        self.factory = factory
        self.mode_detection_service = None
        self.mode_transition_service = None
        
        # Configuración de indicadores por modo
        self._setup_mode_indicators()
        
        # Configuración de estilos visuales
        self._setup_visual_styles()
        
        # Métricas de uso de indicadores
        self.indicator_usage_metrics = {}
        
        logger.info("[ModeIndicatorService] 🚀 Inicializado para indicadores visuales de modo")
    
    def _setup_mode_indicators(self):
        """Configura los indicadores por modo"""
        self.mode_indicators = {
            "explorer": {
                "name": "Explorer Mode",
                "description": "Modo de exploración de recursos",
                "icon": "🔍",
                "color": "#4CAF50",
                "badge_style": "success",
                "tips": [
                    "Usa consultas generales para explorar recursos",
                    "Pregunta sobre la estructura de tus datos",
                    "Descubre nuevas funcionalidades disponibles"
                ],
                "key_features": [
                    "Exploración automática",
                    "Sugerencias de recursos",
                    "Análisis de estructura"
                ]
            },
            "guided": {
                "name": "Guided Mode",
                "description": "Modo guiado paso a paso",
                "icon": "🎯",
                "color": "#2196F3",
                "badge_style": "info",
                "tips": [
                    "Selecciona recursos específicos para trabajar",
                    "Sigue las instrucciones paso a paso",
                    "Confirma cada acción antes de proceder"
                ],
                "key_features": [
                    "Planificación estructurada",
                    "Confirmación de acciones",
                    "Ejecución controlada"
                ]
            },
            "auto": {
                "name": "Auto Mode",
                "description": "Modo automático inteligente",
                "icon": "🤖",
                "color": "#9C27B0",
                "badge_style": "warning",
                "tips": [
                    "El sistema detecta automáticamente tu intención",
                    "Puedes cambiar de modo en cualquier momento",
                    "Confirma las acciones automáticas si es necesario"
                ],
                "key_features": [
                    "Detección automática",
                    "Adaptación inteligente",
                    "Fallback automático"
                ]
            }
        }
    
    def _setup_visual_styles(self):
        """Configura los estilos visuales"""
        self.visual_styles = {
            VisualStyle.MODERN: {
                "badge_radius": "20px",
                "shadow": "0 4px 12px rgba(0,0,0,0.15)",
                "transition": "all 0.3s ease",
                "font_family": "'Segoe UI', system-ui, sans-serif"
            },
            VisualStyle.CLASSIC: {
                "badge_radius": "4px",
                "shadow": "0 2px 4px rgba(0,0,0,0.1)",
                "transition": "all 0.2s ease",
                "font_family": "Georgia, serif"
            },
            VisualStyle.COLORFUL: {
                "badge_radius": "25px",
                "shadow": "0 6px 20px rgba(0,0,0,0.2)",
                "transition": "all 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)",
                "font_family": "'Comic Sans MS', cursive, sans-serif"
            },
            VisualStyle.DARK: {
                "badge_radius": "16px",
                "shadow": "0 4px 16px rgba(0,0,0,0.3)",
                "transition": "all 0.3s ease",
                "font_family": "'Roboto', sans-serif"
            },
            VisualStyle.LIGHT: {
                "badge_radius": "18px",
                "shadow": "0 2px 8px rgba(0,0,0,0.08)",
                "transition": "all 0.25s ease",
                "font_family": "'Open Sans', sans-serif"
            }
        }
    
    async def _get_services(self):
        """Obtiene servicios necesarios de forma lazy"""
        try:
            if not self.mode_detection_service:
                self.mode_detection_service = self.factory.get_mode_detection_service()
            
            if not self.mode_transition_service:
                self.mode_transition_service = self.factory.get_mode_transition_service()
                
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error obteniendo servicios: {e}")
    
    async def get_mode_indicator(
        self,
        user_id: UUID,
        active_mode: str,
        style: VisualStyle = VisualStyle.MODERN,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Obtiene el indicador visual del modo activo
        
        Args:
            user_id: ID del usuario
            active_mode: Modo activo
            style: Estilo visual a aplicar
            context: Contexto adicional
            
        Returns:
            Indicador visual del modo
        """
        try:
            await self._get_services()
            
            # Obtener configuración del modo
            mode_config = self.mode_indicators.get(active_mode, self.mode_indicators["auto"])
            
            # Obtener estilo visual
            visual_config = self.visual_styles.get(style, self.visual_styles[VisualStyle.MODERN])
            
            # Construir indicador
            indicator = {
                "mode": active_mode,
                "name": mode_config["name"],
                "description": mode_config["description"],
                "icon": mode_config["icon"],
                "color": mode_config["color"],
                "badge_style": mode_config["badge_style"],
                "visual_style": style.value,
                "css_properties": visual_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Agregar tips contextuales
            indicator["tips"] = await self._get_contextual_tips(
                user_id, active_mode, context
            )
            
            # Agregar características clave
            indicator["key_features"] = mode_config["key_features"]
            
            # Agregar estado de transición si aplica
            if context and context.get("transition_in_progress"):
                indicator["transition_status"] = {
                    "from_mode": context.get("previous_mode"),
                    "to_mode": active_mode,
                    "progress": context.get("transition_progress", 0),
                    "estimated_time": context.get("estimated_transition_time", 0)
                }
            
            # Actualizar métricas
            await self._update_indicator_metrics(user_id, active_mode, style)
            
            logger.info(
                f"[ModeIndicatorService] 🎨 Indicador generado para usuario {user_id} "
                f"(modo: {active_mode}, estilo: {style.value})"
            )
            
            return indicator
            
        except Exception as e:
            logger.error(f"[ModeIndicatorService] ❌ Error generando indicador: {e}")
            return self._get_fallback_indicator(active_mode)
    
    async def get_contextual_tips(
        self,
        user_id: UUID,
        active_mode: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene tips contextuales para el modo activo
        
        Args:
            user_id: ID del usuario
            active_mode: Modo activo
            context: Contexto de la sesión
            
        Returns:
            Lista de tips contextuales
        """
        try:
            tips = []
            
            # Tips base del modo
            mode_config = self.mode_indicators.get(active_mode, {})
            base_tips = mode_config.get("tips", [])
            
            for tip in base_tips:
                tips.append({
                    "text": tip,
                    "type": "general",
                    "priority": "medium",
                    "icon": "💡"
                })
            
            # Tips contextuales basados en el contexto
            if context:
                contextual_tips = await self._generate_contextual_tips(context, active_mode)
                tips.extend(contextual_tips)
            
            # Tips de rendimiento si aplica
            performance_tips = await self._get_performance_tips(user_id, active_mode)
            tips.extend(performance_tips)
            
            # Ordenar por prioridad
            priority_order = {"high": 3, "medium": 2, "low": 1}
            tips.sort(key=lambda x: priority_order.get(x.get("priority", "medium"), 1), reverse=True)
            
            return tips[:5]  # Máximo 5 tips
            
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error obteniendo tips: {e}")
            return []
    
    async def _generate_contextual_tips(
        self,
        context: Dict[str, Any],
        active_mode: str
    ) -> List[Dict[str, Any]]:
        """Genera tips contextuales basados en el contexto"""
        try:
            tips = []
            
            # Tip basado en recursos disponibles
            resource_count = context.get("resource_count", 0)
            if resource_count == 0:
                tips.append({
                    "text": "No hay recursos disponibles. Considera agregar bases de datos o aplicaciones.",
                    "type": "resource",
                    "priority": "high",
                    "icon": "⚠️"
                })
            elif resource_count < 3:
                tips.append({
                    "text": "Pocos recursos disponibles. Agregar más recursos mejorará la experiencia.",
                    "type": "resource",
                    "priority": "medium",
                    "icon": "💡"
                })
            
            # Tip basado en modo de transición
            if context.get("transition_in_progress"):
                tips.append({
                    "text": "Transición de modo en progreso. Espera a que se complete.",
                    "type": "transition",
                    "priority": "high",
                    "icon": "🔄"
                })
            
            # Tip basado en complejidad de consulta
            query_complexity = context.get("query_complexity", 5)
            if query_complexity > 8 and active_mode == "explorer":
                tips.append({
                    "text": "Consulta compleja detectada. Considera cambiar a modo Guided para mejor control.",
                    "type": "complexity",
                    "priority": "medium",
                    "icon": "🎯"
                })
            elif query_complexity < 3 and active_mode == "guided":
                tips.append({
                    "text": "Consulta simple detectada. El modo Explorer podría ser más eficiente.",
                    "type": "complexity",
                    "priority": "low",
                    "icon": "🔍"
                })
            
            # Tip basado en historial de uso
            session_duration = context.get("session_duration_minutes", 0)
            if session_duration > 30:
                tips.append({
                    "text": "Sesión larga detectada. Considera hacer una pausa o revisar el progreso.",
                    "type": "session",
                    "priority": "medium",
                    "icon": "⏰"
                })
            
            return tips
            
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error generando tips contextuales: {e}")
            return []
    
    async def _get_performance_tips(
        self,
        user_id: UUID,
        active_mode: str
    ) -> List[Dict[str, Any]]:
        """Obtiene tips de rendimiento para el modo activo"""
        try:
            tips = []
            
            # Aquí se implementaría lógica para obtener métricas de rendimiento
            # Por ahora retornamos tips genéricos
            
            if active_mode == "explorer":
                tips.append({
                    "text": "El modo Explorer es más eficiente para consultas generales y exploración.",
                    "type": "performance",
                    "priority": "low",
                    "icon": "⚡"
                })
            elif active_mode == "guided":
                tips.append({
                    "text": "El modo Guided optimiza el tiempo para tareas específicas y complejas.",
                    "type": "performance",
                    "priority": "low",
                    "icon": "⚡"
                })
            elif active_mode == "auto":
                tips.append({
                    "text": "El modo Auto se adapta automáticamente para máxima eficiencia.",
                    "type": "performance",
                    "priority": "low",
                    "icon": "⚡"
                })
            
            return tips
            
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error obteniendo tips de rendimiento: {e}")
            return []
    
    async def get_transition_indicator(
        self,
        user_id: UUID,
        from_mode: str,
        to_mode: str,
        progress: float = 0.0,
        style: VisualStyle = VisualStyle.MODERN
    ) -> Dict[str, Any]:
        """
        Obtiene indicador de transición entre modos
        
        Args:
            user_id: ID del usuario
            from_mode: Modo anterior
            to_mode: Modo nuevo
            progress: Progreso de la transición (0.0 - 1.0)
            style: Estilo visual
            
        Returns:
            Indicador de transición
        """
        try:
            # Obtener configuraciones de ambos modos
            from_config = self.mode_indicators.get(from_mode, {})
            to_config = self.mode_indicators.get(to_mode, {})
            
            # Obtener estilo visual
            visual_config = self.visual_styles.get(style, self.visual_styles[VisualStyle.MODERN])
            
            # Construir indicador de transición
            transition_indicator = {
                "type": "transition",
                "from_mode": {
                    "name": from_config.get("name", from_mode.title()),
                    "icon": from_config.get("icon", "❓"),
                    "color": from_config.get("color", "#666666")
                },
                "to_mode": {
                    "name": to_config.get("name", to_mode.title()),
                    "icon": to_config.get("icon", "❓"),
                    "color": to_config.get("color", "#666666")
                },
                "progress": progress,
                "status": self._get_transition_status(progress),
                "visual_style": style.value,
                "css_properties": visual_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Agregar animación de transición
            transition_indicator["animation"] = {
                "type": "slide",
                "duration": "0.5s",
                "easing": "ease-in-out"
            }
            
            # Agregar mensaje de transición
            if progress < 0.5:
                transition_indicator["message"] = f"Cambiando de {from_mode} a {to_mode}..."
            else:
                transition_indicator["message"] = f"Completando transición a {to_mode}..."
            
            logger.info(
                f"[ModeIndicatorService] 🔄 Indicador de transición generado para usuario {user_id}: "
                f"{from_mode} -> {to_mode} ({progress:.1%})"
            )
            
            return transition_indicator
            
        except Exception as e:
            logger.error(f"[ModeIndicatorService] ❌ Error generando indicador de transición: {e}")
            return self._get_fallback_transition_indicator(from_mode, to_mode)
    
    def _get_transition_status(self, progress: float) -> str:
        """Obtiene el estado de la transición basado en el progreso"""
        if progress < 0.25:
            return "initiating"
        elif progress < 0.5:
            return "in_progress"
        elif progress < 0.75:
            return "almost_complete"
        elif progress < 1.0:
            return "finalizing"
        else:
            return "completed"
    
    async def get_mode_comparison(
        self,
        user_id: UUID,
        modes: List[str] = None,
        style: VisualStyle = VisualStyle.MODERN
    ) -> Dict[str, Any]:
        """
        Obtiene comparación visual entre modos
        
        Args:
            user_id: ID del usuario
            modes: Lista de modos a comparar (si no se especifica, se comparan todos)
            style: Estilo visual
            
        Returns:
            Comparación visual entre modos
        """
        try:
            if modes is None:
                modes = list(self.mode_indicators.keys())
            
            # Obtener estilo visual
            visual_config = self.visual_styles.get(style, self.visual_styles[VisualStyle.MODERN])
            
            # Construir comparación
            comparison = {
                "type": "mode_comparison",
                "modes": [],
                "visual_style": style.value,
                "css_properties": visual_config,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            for mode in modes:
                if mode in self.mode_indicators:
                    mode_config = self.mode_indicators[mode]
                    
                    mode_info = {
                        "mode": mode,
                        "name": mode_config["name"],
                        "description": mode_config["description"],
                        "icon": mode_config["icon"],
                        "color": mode_config["color"],
                        "badge_style": mode_config["badge_style"],
                        "key_features": mode_config["key_features"],
                        "tips": mode_config["tips"][:2]  # Solo 2 tips para comparación
                    }
                    
                    comparison["modes"].append(mode_info)
            
            # Agregar recomendación
            comparison["recommendation"] = await self._get_mode_recommendation(user_id, modes)
            
            logger.info(
                f"[ModeIndicatorService] 📊 Comparación de modos generada para usuario {user_id}: "
                f"{len(modes)} modos comparados"
            )
            
            return comparison
            
        except Exception as e:
            logger.error(f"[ModeIndicatorService] ❌ Error generando comparación: {e}")
            return {"error": str(e)}
    
    async def _get_mode_recommendation(
        self,
        user_id: UUID,
        modes: List[str]
    ) -> Dict[str, Any]:
        """Obtiene recomendación de modo basada en el usuario"""
        try:
            # Aquí se implementaría lógica para recomendar el mejor modo
            # Por ahora retornamos una recomendación genérica
            
            if "explorer" in modes:
                recommended_mode = "explorer"
                reason = "Ideal para exploración general y descubrimiento de recursos"
            elif "guided" in modes:
                recommended_mode = "guided"
                reason = "Perfecto para tareas específicas y control paso a paso"
            else:
                recommended_mode = "auto"
                reason = "Se adapta automáticamente a tus necesidades"
            
            return {
                "recommended_mode": recommended_mode,
                "reason": reason,
                "confidence": 0.8
            }
            
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error obteniendo recomendación: {e}")
            return {
                "recommended_mode": "auto",
                "reason": "Modo automático recomendado",
                "confidence": 0.5
            }
    
    async def _update_indicator_metrics(
        self,
        user_id: UUID,
        active_mode: str,
        style: VisualStyle
    ):
        """Actualiza métricas de uso de indicadores"""
        try:
            user_id_str = str(user_id)
            
            if user_id_str not in self.indicator_usage_metrics:
                self.indicator_usage_metrics[user_id_str] = {}
            
            # Actualizar métricas por modo
            if active_mode not in self.indicator_usage_metrics[user_id_str]:
                self.indicator_usage_metrics[user_id_str][active_mode] = {
                    "usage_count": 0,
                    "last_used": 0,
                    "style_preferences": {},
                    "tips_viewed": 0
                }
            
            # Actualizar métricas
            mode_metrics = self.indicator_usage_metrics[user_id_str][active_mode]
            mode_metrics["usage_count"] += 1
            mode_metrics["last_used"] = datetime.utcnow().timestamp()
            
            # Actualizar preferencias de estilo
            style_str = style.value
            if style_str not in mode_metrics["style_preferences"]:
                mode_metrics["style_preferences"][style_str] = 0
            mode_metrics["style_preferences"][style_str] += 1
            
        except Exception as e:
            logger.warning(f"[ModeIndicatorService] ⚠️ Error actualizando métricas: {e}")
    
    def _get_fallback_indicator(self, active_mode: str) -> Dict[str, Any]:
        """Obtiene indicador de fallback"""
        return {
            "mode": active_mode,
            "name": f"{active_mode.title()} Mode",
            "description": f"Modo {active_mode} activo",
            "icon": "❓",
            "color": "#666666",
            "badge_style": "secondary",
            "visual_style": "modern",
            "css_properties": self.visual_styles[VisualStyle.MODERN],
            "timestamp": datetime.utcnow().isoformat(),
            "tips": [],
            "key_features": []
        }
    
    def _get_fallback_transition_indicator(
        self,
        from_mode: str,
        to_mode: str
    ) -> Dict[str, Any]:
        """Obtiene indicador de transición de fallback"""
        return {
            "type": "transition",
            "from_mode": {
                "name": from_mode.title(),
                "icon": "❓",
                "color": "#666666"
            },
            "to_mode": {
                "name": to_mode.title(),
                "icon": "❓",
                "color": "#666666"
            },
            "progress": 0.0,
            "status": "initiating",
            "visual_style": "modern",
            "css_properties": self.visual_styles[VisualStyle.MODERN],
            "timestamp": datetime.utcnow().isoformat(),
            "animation": {
                "type": "fade",
                "duration": "0.3s",
                "easing": "ease"
            },
            "message": f"Transición de {from_mode} a {to_mode}"
        }
    
    async def get_indicator_analytics(
        self,
        user_id: UUID,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Obtiene análisis de uso de indicadores para un usuario
        
        Args:
            user_id: ID del usuario
            days: Días hacia atrás para el análisis
            
        Returns:
            Análisis de uso de indicadores
        """
        try:
            user_id_str = str(user_id)
            
            if user_id_str not in self.indicator_usage_metrics:
                return {
                    "user_id": str(user_id),
                    "message": "No hay datos de uso de indicadores disponibles"
                }
            
            # Obtener métricas del usuario
            user_metrics = self.indicator_usage_metrics[user_id_str]
            
            # Calcular estadísticas generales
            total_modes = len(user_metrics)
            total_usage = sum(metrics["usage_count"] for metrics in user_metrics.values())
            
            # Análisis por modo
            mode_analysis = {}
            for mode, metrics in user_metrics.items():
                mode_analysis[mode] = {
                    "usage_count": metrics["usage_count"],
                    "last_used": metrics["last_used"],
                    "preferred_style": max(
                        metrics["style_preferences"].items(),
                        key=lambda x: x[1]
                    )[0] if metrics["style_preferences"] else "modern"
                }
            
            # Análisis de preferencias de estilo
            style_preferences = {}
            for mode_metrics in user_metrics.values():
                for style, count in mode_metrics["style_preferences"].items():
                    if style not in style_preferences:
                        style_preferences[style] = 0
                    style_preferences[style] += count
            
            return {
                "user_id": str(user_id),
                "analysis_period_days": days,
                "summary": {
                    "total_modes": total_modes,
                    "total_usage": total_usage,
                    "most_used_mode": max(
                        user_metrics.items(),
                        key=lambda x: x[1]["usage_count"]
                    )[0] if user_metrics else None
                },
                "mode_analysis": mode_analysis,
                "style_preferences": style_preferences
            }
            
        except Exception as e:
            logger.error(f"[ModeIndicatorService] ❌ Error obteniendo análisis: {e}")
            return {"error": str(e)}
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtiene información del servicio"""
        return {
            "service_name": "ModeIndicatorService",
            "description": "Servicio de indicadores visuales de modo activo",
            "features": [
                "Indicadores visuales del modo activo",
                "Tips de uso contextuales",
                "Transiciones visuales entre modos",
                "Personalización de estilos",
                "Métricas de uso de indicadores"
            ],
            "supported_modes": list(self.mode_indicators.keys()),
            "supported_styles": [style.value for style in VisualStyle],
            "indicator_types": [indicator.value for indicator in IndicatorType],
            "status": "active"
        }
