"""
PremiumPromptService - Personalización premium de prompts por usuario
"""

import json
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from app.core.service_factory import ServiceFactory
from app.models.user_model import User
from app.models.agent_model import Agent


class PremiumFeature(Enum):
    """Características premium disponibles"""
    CUSTOM_BASE_PROMPTS = "custom_base_prompts"
    CUSTOMIZABLE_AGENTS = "customizable_agents"
    PERSONALIZED_STYLES = "personalized_styles"
    ADVANCED_ANALYSIS = "advanced_analysis"
    PREDICTIVE_INSIGHTS = "predictive_insights"
    LEARNING_OPTIMIZATION = "learning_optimization"


class ResponseStyle(Enum):
    """Estilos de respuesta premium"""
    TECHNICAL_DETAILED = "technical_detailed"
    BUSINESS_FOCUSED = "business_focused"
    VISUAL_RICH = "visual_rich"
    INTERACTIVE = "interactive"
    STORYTELLING = "storytelling"
    DATA_DRIVEN = "data_driven"


@dataclass
class CustomPrompt:
    """Prompt personalizado del usuario"""
    id: str
    name: str
    content: str
    mode: str
    language: str
    created_at: datetime
    updated_at: datetime
    usage_count: int = 0
    is_active: bool = True


@dataclass
class UserStylePreference:
    """Preferencias de estilo del usuario"""
    response_style: ResponseStyle
    detail_level: str  # "minimal", "standard", "detailed", "comprehensive"
    include_examples: bool = True
    include_visuals: bool = False
    include_metrics: bool = True
    tone: str = "professional"  # "casual", "professional", "friendly", "formal"


class PremiumPromptService:
    """
    Servicio para personalización premium de prompts por usuario
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        self.cache_ttl = 600  # 10 minutos
        
        # Estilos de respuesta premium por característica
        self.premium_response_styles = {
            PremiumFeature.CUSTOM_BASE_PROMPTS: {
                "es": "Respuestas con prompts base personalizados según tus preferencias específicas",
                "en": "Responses with custom base prompts according to your specific preferences"
            },
            PremiumFeature.CUSTOMIZABLE_AGENTS: {
                "es": "Agentes AI personalizados que se adaptan a tu estilo de trabajo",
                "en": "Customized AI agents that adapt to your work style"
            },
            PremiumFeature.PERSONALIZED_STYLES: {
                "es": "Estilos de respuesta personalizados según tu perfil y preferencias",
                "en": "Personalized response styles according to your profile and preferences"
            },
            PremiumFeature.ADVANCED_ANALYSIS: {
                "es": "Análisis avanzados con insights profundos y recomendaciones estratégicas",
                "en": "Advanced analysis with deep insights and strategic recommendations"
            },
            PremiumFeature.PREDICTIVE_INSIGHTS: {
                "es": "Insights predictivos basados en patrones históricos y tendencias",
                "en": "Predictive insights based on historical patterns and trends"
            },
            PremiumFeature.LEARNING_OPTIMIZATION: {
                "es": "Optimización automática del aprendizaje basada en tu comportamiento",
                "en": "Automatic learning optimization based on your behavior"
            }
        }
        
        # Plantillas de prompts premium por modo
        self.premium_mode_templates = {
            "explorer": {
                "es": {
                    "basic": "Eres un asistente premium de exploración con acceso a análisis avanzados.",
                    "advanced": "Eres un consultor senior de exploración con capacidades de análisis predictivo y recomendaciones estratégicas.",
                    "expert": "Eres un estratega de exploración premium con análisis de impacto de negocio y optimizaciones automáticas."
                },
                "en": {
                    "basic": "You are a premium exploration assistant with access to advanced analysis.",
                    "advanced": "You are a senior exploration consultant with predictive analysis and strategic recommendation capabilities.",
                    "expert": "You are a premium exploration strategist with business impact analysis and automatic optimizations."
                }
            },
            "guided": {
                "es": {
                    "basic": "Eres un asistente premium de ejecución con capacidades de optimización automática.",
                    "advanced": "Eres un mentor senior de ejecución con análisis predictivo y planificación estratégica.",
                    "expert": "Eres un estratega de ejecución premium con optimización automática y análisis de ROI."
                },
                "en": {
                    "basic": "You are a premium execution assistant with automatic optimization capabilities.",
                    "advanced": "You are a senior execution mentor with predictive analysis and strategic planning.",
                    "expert": "You are a premium execution strategist with automatic optimization and ROI analysis."
                }
            },
            "auto": {
                "es": {
                    "basic": "Eres un asistente premium inteligente con capacidades de aprendizaje automático.",
                    "advanced": "Eres un consultor premium inteligente con análisis predictivo y personalización avanzada.",
                    "expert": "Eres un estratega premium inteligente con optimización automática y insights predictivos."
                },
                "en": {
                    "basic": "You are a premium intelligent assistant with machine learning capabilities.",
                    "advanced": "You are a premium intelligent consultant with predictive analysis and advanced personalization.",
                    "expert": "You are a premium intelligent strategist with automatic optimization and predictive insights."
                }
            }
        }
    
    async def initialize(self, user_id: str):
        """Inicializar el servicio para un usuario específico"""
        try:
            self.user_id = user_id
            self.user_premium_features = await self._load_user_premium_features()
            self.custom_prompts = await self._load_custom_prompts()
            self.style_preferences = await self._load_style_preferences()
            self.logger.info(f"PremiumPromptService inicializado para usuario {user_id}")
        except Exception as e:
            self.logger.error(f"Error inicializando PremiumPromptService: {e}")
            raise
    
    async def get_premium_prompt(
        self, 
        mode: str, 
        base_prompt: str,
        user_context: Optional[Dict] = None
    ) -> str:
        """
        Obtener prompt premium personalizado para el usuario
        """
        try:
            if not self.user_premium_features:
                return base_prompt
            
            # 1. Aplicar características premium disponibles
            enhanced_prompt = await self._apply_premium_features(base_prompt, mode, user_context)
            
            # 2. Aplicar prompts personalizados si existen
            if self.custom_prompts:
                enhanced_prompt = await self._apply_custom_prompts(enhanced_prompt, mode)
            
            # 3. Aplicar preferencias de estilo
            if self.style_preferences:
                enhanced_prompt = await self._apply_style_preferences(enhanced_prompt)
            
            # 4. Cache del prompt premium
            cache_key = f"{self.user_id}:premium:{mode}:{hash(enhanced_prompt)}"
            self.cache[cache_key] = {
                "prompt": enhanced_prompt,
                "timestamp": datetime.now(),
                "features_applied": list(self.user_premium_features.keys()),
                "mode": mode
            }
            
            self.logger.info(f"Prompt premium generado para modo {mode} - Características: {len(self.user_premium_features)}")
            return enhanced_prompt
            
        except Exception as e:
            self.logger.error(f"Error generando prompt premium: {e}")
            return base_prompt
    
    async def _apply_premium_features(
        self, 
        base_prompt: str, 
        mode: str, 
        user_context: Optional[Dict]
    ) -> str:
        """Aplicar características premium al prompt base"""
        enhanced_prompt = base_prompt
        
        # Obtener nivel premium del usuario
        premium_level = self._get_premium_level()
        language = user_context.get("language", "es") if user_context else "es"
        
        # Aplicar plantilla premium según el modo
        if mode in self.premium_mode_templates:
            mode_templates = self.premium_mode_templates[mode]
            if language in mode_templates:
                level_templates = mode_templates[language]
                if premium_level in level_templates:
                    enhanced_prompt = f"{enhanced_prompt}\n\n{level_templates[premium_level]}"
        
        # Agregar descripción de características premium
        premium_features_text = []
        for feature in self.user_premium_features:
            if feature in self.premium_response_styles:
                feature_desc = self.premium_response_styles[feature].get(language, "")
                if feature_desc:
                    premium_features_text.append(f"• {feature_desc}")
        
        if premium_features_text:
            if language == "es":
                enhanced_prompt += "\n\nCaracterísticas premium activas:\n" + "\n".join(premium_features_text)
            else:
                enhanced_prompt += "\n\nActive premium features:\n" + "\n".join(premium_features_text)
        
        return enhanced_prompt
    
    async def _apply_custom_prompts(self, enhanced_prompt: str, mode: str) -> str:
        """Aplicar prompts personalizados del usuario"""
        if not self.custom_prompts:
            return enhanced_prompt
        
        # Buscar prompts personalizados para el modo
        mode_prompts = [p for p in self.custom_prompts if p.mode == mode and p.is_active]
        
        if not mode_prompts:
            return enhanced_prompt
        
        # Usar el prompt más reciente o más usado
        best_prompt = max(mode_prompts, key=lambda x: (x.usage_count, x.updated_at))
        
        # Agregar prompt personalizado
        enhanced_prompt += f"\n\nPrompt personalizado:\n{best_prompt.content}"
        
        # Incrementar contador de uso
        await self._increment_prompt_usage(best_prompt.id)
        
        return enhanced_prompt
    
    async def _apply_style_preferences(self, enhanced_prompt: str) -> str:
        """Aplicar preferencias de estilo del usuario"""
        if not self.style_preferences:
            return enhanced_prompt
        
        style = self.style_preferences
        style_instructions = []
        
        # Instrucciones de estilo
        if style.include_examples:
            style_instructions.append("Incluye ejemplos prácticos y casos de uso")
        
        if style.include_visuals:
            style_instructions.append("Sugiere visualizaciones y diagramas cuando sea apropiado")
        
        if style.include_metrics:
            style_instructions.append("Incluye métricas y KPIs relevantes")
        
        # Nivel de detalle
        detail_instructions = {
            "minimal": "Proporciona respuestas concisas y directas",
            "standard": "Proporciona respuestas equilibradas con información esencial",
            "detailed": "Proporciona respuestas detalladas con contexto completo",
            "comprehensive": "Proporciona respuestas exhaustivas con análisis profundo"
        }
        
        if style.detail_level in detail_instructions:
            style_instructions.append(detail_instructions[style.detail_level])
        
        # Tono
        tone_instructions = {
            "casual": "Usa un tono cercano y conversacional",
            "professional": "Mantén un tono profesional y técnico",
            "friendly": "Usa un tono amigable y accesible",
            "formal": "Mantén un tono formal y estructurado"
        }
        
        if style.tone in tone_instructions:
            style_instructions.append(tone_instructions[style.tone])
        
        if style_instructions:
            enhanced_prompt += f"\n\nInstrucciones de estilo:\n" + "\n".join([f"• {inst}" for inst in style_instructions])
        
        return enhanced_prompt
    
    def _get_premium_level(self) -> str:
        """Determinar el nivel premium del usuario"""
        feature_count = len(self.user_premium_features)
        
        if feature_count >= 5:
            return "expert"
        elif feature_count >= 3:
            return "advanced"
        else:
            return "basic"
    
    async def create_custom_prompt(
        self,
        name: str,
        content: str,
        mode: str,
        language: str = "es"
    ) -> Optional[CustomPrompt]:
        """Crear un nuevo prompt personalizado"""
        try:
            # Verificar que el usuario tenga permisos premium
            if not self.user_premium_features:
                self.logger.warning(f"Usuario {self.user_id} no tiene características premium")
                return None
            
            # Crear prompt personalizado
            custom_prompt = CustomPrompt(
                id=f"custom_{datetime.now().timestamp()}",
                name=name,
                content=content,
                mode=mode,
                language=language,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                usage_count=0,
                is_active=True
            )
            
            # Guardar en la base de datos
            await self._save_custom_prompt(custom_prompt)
            
            # Actualizar cache local
            self.custom_prompts.append(custom_prompt)
            
            self.logger.info(f"Prompt personalizado creado: {name} para modo {mode}")
            return custom_prompt
            
        except Exception as e:
            self.logger.error(f"Error creando prompt personalizado: {e}")
            return None
    
    async def update_custom_prompt(
        self,
        prompt_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """Actualizar un prompt personalizado existente"""
        try:
            # Buscar prompt en cache local
            prompt = next((p for p in self.custom_prompts if p.id == prompt_id), None)
            if not prompt:
                return False
            
            # Actualizar campos
            if name is not None:
                prompt.name = name
            if content is not None:
                prompt.content = content
            if is_active is not None:
                prompt.is_active = is_active
            
            prompt.updated_at = datetime.now()
            
            # Guardar en la base de datos
            await self._update_custom_prompt(prompt)
            
            self.logger.info(f"Prompt personalizado actualizado: {prompt_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error actualizando prompt personalizado: {e}")
            return False
    
    async def delete_custom_prompt(self, prompt_id: str) -> bool:
        """Eliminar un prompt personalizado"""
        try:
            # Buscar prompt en cache local
            prompt = next((p for p in self.custom_prompts if p.id == prompt_id), None)
            if not prompt:
                return False
            
            # Eliminar de la base de datos
            await self._delete_custom_prompt(prompt_id)
            
            # Remover de cache local
            self.custom_prompts = [p for p in self.custom_prompts if p.id != prompt_id]
            
            self.logger.info(f"Prompt personalizado eliminado: {prompt_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error eliminando prompt personalizado: {e}")
            return False
    
    async def update_style_preferences(
        self,
        response_style: Optional[ResponseStyle] = None,
        detail_level: Optional[str] = None,
        include_examples: Optional[bool] = None,
        include_visuals: Optional[bool] = None,
        include_metrics: Optional[bool] = None,
        tone: Optional[str] = None
    ) -> bool:
        """Actualizar preferencias de estilo del usuario"""
        try:
            if not self.style_preferences:
                self.style_preferences = UserStylePreference(
                    response_style=ResponseStyle.TECHNICAL_DETAILED,
                    detail_level="standard"
                )
            
            # Actualizar campos
            if response_style is not None:
                self.style_preferences.response_style = response_style
            if detail_level is not None:
                self.style_preferences.detail_level = detail_level
            if include_examples is not None:
                self.style_preferences.include_examples = include_examples
            if include_visuals is not None:
                self.style_preferences.include_visuals = include_visuals
            if include_metrics is not None:
                self.style_preferences.include_metrics = include_metrics
            if tone is not None:
                self.style_preferences.tone = tone
            
            # Guardar en la base de datos
            await self._save_style_preferences(self.style_preferences)
            
            # Limpiar cache
            self._clear_user_cache()
            
            self.logger.info(f"Preferencias de estilo actualizadas para usuario {self.user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error actualizando preferencias de estilo: {e}")
            return False
    
    async def get_premium_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas premium del usuario"""
        try:
            stats = {
                "premium_features": list(self.user_premium_features.keys()) if self.user_premium_features else [],
                "custom_prompts_count": len(self.custom_prompts) if self.custom_prompts else 0,
                "style_preferences": self.style_preferences.__dict__ if self.style_preferences else None,
                "prompts_generated": len([k for k in self.cache.keys() if k.startswith(f"{self.user_id}:premium:")]),
                "last_premium_usage": None
            }
            
            # Obtener último uso premium
            premium_keys = [k for k in self.cache.keys() if k.startswith(f"{self.user_id}:premium:")]
            if premium_keys:
                latest_key = max(premium_keys, key=lambda x: self.cache[x]["timestamp"])
                stats["last_premium_usage"] = self.cache[latest_key]["timestamp"].isoformat()
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas premium: {e}")
            return {}
    
    async def _load_user_premium_features(self) -> List[PremiumFeature]:
        """Cargar características premium del usuario desde la base de datos"""
        try:
            # Obtener usuario desde la base de datos
            db = self.factory.get_database_service()
            user = await db.get_user_by_id(self.user_id)
            
            if not user or not getattr(user, 'is_premium', False):
                return []
            
            # Obtener características premium del usuario
            # Por ahora, asumimos que usuarios premium tienen todas las características
            # En el futuro, esto podría venir de una tabla de suscripciones
            return list(PremiumFeature)
            
        except Exception as e:
            self.logger.error(f"Error cargando características premium: {e}")
            return []
    
    async def _load_custom_prompts(self) -> List[CustomPrompt]:
        """Cargar prompts personalizados del usuario desde la base de datos"""
        try:
            # Por ahora, retornamos lista vacía
            # En el futuro, esto vendría de una tabla de prompts personalizados
            return []
            
        except Exception as e:
            self.logger.error(f"Error cargando prompts personalizados: {e}")
            return []
    
    async def _load_style_preferences(self) -> Optional[UserStylePreference]:
        """Cargar preferencias de estilo del usuario desde la base de datos"""
        try:
            # Por ahora, retornamos None
            # En el futuro, esto vendría de una tabla de preferencias de estilo
            return None
            
        except Exception as e:
            self.logger.error(f"Error cargando preferencias de estilo: {e}")
            return None
    
    async def _save_custom_prompt(self, prompt: CustomPrompt):
        """Guardar prompt personalizado en la base de datos"""
        # Implementar cuando se cree la tabla de prompts personalizados
        pass
    
    async def _update_custom_prompt(self, prompt: CustomPrompt):
        """Actualizar prompt personalizado en la base de datos"""
        # Implementar cuando se cree la tabla de prompts personalizados
        pass
    
    async def _delete_custom_prompt(self, prompt_id: str):
        """Eliminar prompt personalizado de la base de datos"""
        # Implementar cuando se cree la tabla de prompts personalizados
        pass
    
    async def _save_style_preferences(self, preferences: UserStylePreference):
        """Guardar preferencias de estilo en la base de datos"""
        # Implementar cuando se cree la tabla de preferencias de estilo
        pass
    
    async def _increment_prompt_usage(self, prompt_id: str):
        """Incrementar contador de uso de un prompt personalizado"""
        # Implementar cuando se cree la tabla de prompts personalizados
        pass
    
    def _clear_user_cache(self):
        """Limpiar cache del usuario"""
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{self.user_id}:")]
        for key in keys_to_remove:
            del self.cache[key]
    
    async def cleanup(self):
        """Limpiar recursos del servicio"""
        try:
            # Limpiar cache expirado
            current_time = datetime.now()
            expired_keys = []
            
            for key, value in self.cache.items():
                if current_time - value["timestamp"] > timedelta(seconds=self.cache_ttl):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
            
            self.logger.info(f"Cleanup completado - {len(expired_keys)} entradas expiradas removidas")
            
        except Exception as e:
            self.logger.error(f"Error en cleanup: {e}")
