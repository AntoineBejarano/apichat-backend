"""
PromptBuilderService - Construcción dinámica de prompts del sistema
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
from app.models.database_model import DatabaseConnection
from app.models.app_model import App
from app.models.strategy_model import Strategy


class PromptStyle(Enum):
    """Estilos de prompt disponibles"""
    TECHNICAL = "technical"
    FRIENDLY = "friendly"
    CONCISE = "concise"
    DETAILED = "detailed"
    SPANISH = "spanish"
    ENGLISH = "english"


class UserLevel(Enum):
    """Niveles técnicos de usuario"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


@dataclass
class UserProfile:
    """Perfil de usuario para personalización de prompts"""
    language: str = "es"
    technical_level: UserLevel = UserLevel.INTERMEDIATE
    preferred_style: PromptStyle = PromptStyle.FRIENDLY
    is_premium: bool = False
    custom_prompts: Dict[str, str] = None
    last_interaction: Optional[datetime] = None


@dataclass
class ResourceContext:
    """Contexto de recursos disponibles"""
    databases: List[Dict[str, Any]] = None
    apps: List[Dict[str, Any]] = None
    strategies: List[Dict[str, Any]] = None
    active_resources: List[str] = None
    resource_relationships: Dict[str, List[str]] = None


class PromptBuilderService:
    """
    Servicio para construir prompts del sistema dinámicos y personalizados
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.logger = logging.getLogger(__name__)
        self.cache = {}
        self.cache_ttl = 300  # 5 minutos
        
        # Prompts base por modo
        self.base_prompts = {
            "explorer": {
                "es": "Eres un asistente experto en exploración de recursos. Tu objetivo es ayudar al usuario a descubrir y entender los recursos disponibles de manera clara y organizada.",
                "en": "You are an expert resource exploration assistant. Your goal is to help the user discover and understand available resources in a clear and organized manner."
            },
            "guided": {
                "es": "Eres un asistente experto en ejecución guiada. Tu objetivo es crear planes detallados y ejecutar acciones específicas con los recursos seleccionados.",
                "en": "You are an expert guided execution assistant. Your goal is to create detailed plans and execute specific actions with selected resources."
            },
            "auto": {
                "es": "Eres un asistente inteligente que detecta automáticamente la intención del usuario. Adaptas tu respuesta según el contexto y las necesidades detectadas.",
                "en": "You are an intelligent assistant that automatically detects user intent. You adapt your response based on context and detected needs."
            }
        }
        
        # Estilos de respuesta por nivel técnico
        self.style_templates = {
            UserLevel.BEGINNER: {
                "es": "Explica de manera simple y paso a paso. Usa analogías y ejemplos prácticos.",
                "en": "Explain in simple, step-by-step terms. Use analogies and practical examples."
            },
            UserLevel.INTERMEDIATE: {
                "es": "Proporciona explicaciones técnicas pero accesibles. Incluye detalles relevantes sin sobrecargar.",
                "en": "Provide technical but accessible explanations. Include relevant details without overwhelming."
            },
            UserLevel.EXPERT: {
                "es": "Usa terminología técnica avanzada. Proporciona análisis profundos y optimizaciones.",
                "en": "Use advanced technical terminology. Provide deep analysis and optimizations."
            }
        }
        
        # Prompts premium personalizables
        self.premium_prompts = {
            "es": {
                "explorer": "Eres un asistente premium de exploración con acceso a análisis avanzados y recomendaciones personalizadas.",
                "guided": "Eres un asistente premium de ejecución con capacidades de optimización automática y análisis predictivo.",
                "auto": "Eres un asistente premium inteligente con capacidades de aprendizaje automático y personalización avanzada."
            },
            "en": {
                "explorer": "You are a premium exploration assistant with access to advanced analysis and personalized recommendations.",
                "guided": "You are a premium execution assistant with automatic optimization and predictive analysis capabilities.",
                "auto": "You are a premium intelligent assistant with machine learning and advanced personalization capabilities."
            }
        }
    
    async def initialize(self, user_id: str):
        """Inicializar el servicio para un usuario específico"""
        try:
            self.user_id = user_id
            self.user_profile = await self._load_user_profile()
            self.logger.info(f"PromptBuilderService inicializado para usuario {user_id}")
        except Exception as e:
            self.logger.error(f"Error inicializando PromptBuilderService: {e}")
            raise
    
    async def build_final_prompt(
        self, 
        agent_mode: str, 
        user_context: Optional[Dict] = None, 
        resource_context: Optional[Dict] = None
    ) -> str:
        """
        Construir el prompt final personalizado
        """
        try:
            # 1. Prompt base del agente
            base_prompt = self._get_agent_base_prompt(agent_mode)
            
            # 2. Contexto del usuario
            user_profile_context = self._build_user_profile_context(user_context)
            
            # 3. Contexto del recurso
            resource_context_text = self._build_resource_context(resource_context)
            
            # 4. Prompt final personalizado
            final_prompt = f"{base_prompt}\n\n{user_profile_context}\n\n{resource_context_text}"
            
            # 5. Cache del prompt generado
            cache_key = f"{self.user_id}:{agent_mode}:{hash(final_prompt)}"
            self.cache[cache_key] = {
                "prompt": final_prompt,
                "timestamp": datetime.now(),
                "context": {
                    "agent_mode": agent_mode,
                    "user_context": user_context,
                    "resource_context": resource_context
                }
            }
            
            self.logger.info(f"Prompt construido para modo {agent_mode} - Longitud: {len(final_prompt)}")
            return final_prompt
            
        except Exception as e:
            self.logger.error(f"Error construyendo prompt: {e}")
            return self._get_fallback_prompt(agent_mode)
    
    def _get_agent_base_prompt(self, agent_mode: str) -> str:
        """Obtener el prompt base del agente según el modo"""
        language = self.user_profile.language
        base_prompt = self.base_prompts.get(agent_mode, {}).get(language, self.base_prompts["auto"][language])
        
        # Aplicar personalización premium si está disponible
        if self.user_profile.is_premium:
            premium_prompt = self.premium_prompts.get(language, {}).get(agent_mode, "")
            if premium_prompt:
                base_prompt = f"{base_prompt}\n\n{premium_prompt}"
        
        return base_prompt
    
    def _build_user_profile_context(self, user_context: Optional[Dict] = None) -> str:
        """Construir contexto del perfil de usuario"""
        context_parts = []
        
        # Idioma y nivel técnico
        language = self.user_profile.language
        level = self.user_profile.technical_level
        
        if language == "es":
            context_parts.append(f"Idioma: Español")
            context_parts.append(f"Nivel técnico: {self._get_level_description_es(level)}")
            context_parts.append(f"Estilo preferido: {self._get_style_description_es(self.user_profile.preferred_style)}")
        else:
            context_parts.append(f"Language: English")
            context_parts.append(f"Technical level: {self._get_level_description_en(level)}")
            context_parts.append(f"Preferred style: {self._get_style_description_en(self.user_profile.preferred_style)}")
        
        # Instrucciones de estilo
        style_instructions = self.style_templates[level].get(language, "")
        if style_instructions:
            context_parts.append(f"Instrucciones de estilo: {style_instructions}")
        
        # Contexto adicional del usuario si se proporciona
        if user_context:
            if "current_task" in user_context:
                context_parts.append(f"Tarea actual: {user_context['current_task']}")
            if "previous_context" in user_context:
                context_parts.append(f"Contexto previo: {user_context['previous_context']}")
        
        return "\n".join(context_parts)
    
    def _build_resource_context(self, resource_context: Optional[Dict] = None) -> str:
        """Construir contexto de recursos disponibles"""
        if not resource_context:
            return "No hay contexto de recursos específico disponible."
        
        context_parts = []
        language = self.user_profile.language
        
        if language == "es":
            context_parts.append("Recursos disponibles:")
        else:
            context_parts.append("Available resources:")
        
        # Bases de datos
        if resource_context.get("databases"):
            db_count = len(resource_context["databases"])
            if language == "es":
                context_parts.append(f"- Bases de datos: {db_count} disponibles")
            else:
                context_parts.append(f"- Databases: {db_count} available")
        
        # Aplicaciones
        if resource_context.get("apps"):
            app_count = len(resource_context["apps"])
            if language == "es":
                context_parts.append(f"- Aplicaciones: {app_count} disponibles")
            else:
                context_parts.append(f"- Applications: {app_count} available")
        
        # Estrategias
        if resource_context.get("strategies"):
            strategy_count = len(resource_context["strategies"])
            if language == "es":
                context_parts.append(f"- Estrategias: {strategy_count} disponibles")
            else:
                context_parts.append(f"- Strategies: {strategy_count} available")
        
        # Recursos activos
        if resource_context.get("active_resources"):
            active = resource_context["active_resources"]
            if language == "es":
                context_parts.append(f"- Recursos activos: {', '.join(active)}")
            else:
                context_parts.append(f"- Active resources: {', '.join(active)}")
        
        return "\n".join(context_parts)
    
    def _get_fallback_prompt(self, agent_mode: str) -> str:
        """Obtener prompt de fallback en caso de error"""
        language = self.user_profile.language
        
        if language == "es":
            return f"Eres un asistente AI. Modo: {agent_mode}. Responde de manera clara y útil."
        else:
            return f"You are an AI assistant. Mode: {agent_mode}. Respond clearly and helpfully."
    
    def _get_level_description_es(self, level: UserLevel) -> str:
        """Obtener descripción del nivel en español"""
        descriptions = {
            UserLevel.BEGINNER: "Principiante - Explicaciones simples y paso a paso",
            UserLevel.INTERMEDIATE: "Intermedio - Explicaciones técnicas pero accesibles",
            UserLevel.EXPERT: "Experto - Terminología avanzada y análisis profundo"
        }
        return descriptions.get(level, "Intermedio")
    
    def _get_level_description_en(self, level: UserLevel) -> str:
        """Obtener descripción del nivel en inglés"""
        descriptions = {
            UserLevel.BEGINNER: "Beginner - Simple, step-by-step explanations",
            UserLevel.INTERMEDIATE: "Intermediate - Technical but accessible explanations",
            UserLevel.EXPERT: "Expert - Advanced terminology and deep analysis"
        }
        return descriptions.get(level, "Intermediate")
    
    def _get_style_description_es(self, style: PromptStyle) -> str:
        """Obtener descripción del estilo en español"""
        descriptions = {
            PromptStyle.TECHNICAL: "Técnico - Respuestas precisas y detalladas",
            PromptStyle.FRIENDLY: "Amigable - Respuestas cercanas y comprensibles",
            PromptStyle.CONCISE: "Conciso - Respuestas breves y directas",
            PromptStyle.DETAILED: "Detallado - Respuestas completas y exhaustivas",
            PromptStyle.SPANISH: "Español - Respuestas en español",
            PromptStyle.ENGLISH: "Inglés - Respuestas en inglés"
        }
        return descriptions.get(style, "Amigable")
    
    def _get_style_description_en(self, style: PromptStyle) -> str:
        """Obtener descripción del estilo en inglés"""
        descriptions = {
            PromptStyle.TECHNICAL: "Technical - Precise and detailed responses",
            PromptStyle.FRIENDLY: "Friendly - Approachable and understandable responses",
            PromptStyle.CONCISE: "Concise - Brief and direct responses",
            PromptStyle.DETAILED: "Detailed - Complete and exhaustive responses",
            PromptStyle.SPANISH: "Spanish - Responses in Spanish",
            PromptStyle.ENGLISH: "English - Responses in English"
        }
        return descriptions.get(style, "Friendly")
    
    async def _load_user_profile(self) -> UserProfile:
        """Cargar perfil del usuario desde la base de datos"""
        try:
            # Obtener usuario desde la base de datos
            db = self.factory.get_database_service()
            user = await db.get_user_by_id(self.user_id)
            
            if not user:
                # Perfil por defecto si no existe
                return UserProfile()
            
            # Crear perfil basado en datos del usuario
            profile = UserProfile(
                language=getattr(user, 'language', 'es'),
                technical_level=self._parse_technical_level(getattr(user, 'technical_level', 'intermediate')),
                preferred_style=self._parse_prompt_style(getattr(user, 'preferred_style', 'friendly')),
                is_premium=getattr(user, 'is_premium', False),
                custom_prompts=getattr(user, 'custom_prompts', {}),
                last_interaction=getattr(user, 'last_interaction', None)
            )
            
            return profile
            
        except Exception as e:
            self.logger.error(f"Error cargando perfil de usuario: {e}")
            return UserProfile()
    
    def _parse_technical_level(self, level_str: str) -> UserLevel:
        """Parsear nivel técnico desde string"""
        try:
            return UserLevel(level_str.lower())
        except ValueError:
            return UserLevel.INTERMEDIATE
    
    def _parse_prompt_style(self, style_str: str) -> PromptStyle:
        """Parsear estilo de prompt desde string"""
        try:
            return PromptStyle(style_str.lower())
        except ValueError:
            return PromptStyle.FRIENDLY
    
    async def update_user_preferences(
        self, 
        language: Optional[str] = None,
        technical_level: Optional[UserLevel] = None,
        preferred_style: Optional[PromptStyle] = None,
        custom_prompts: Optional[Dict[str, str]] = None
    ):
        """Actualizar preferencias del usuario"""
        try:
            if language:
                self.user_profile.language = language
            if technical_level:
                self.user_profile.technical_level = technical_level
            if preferred_style:
                self.user_profile.preferred_style = preferred_style
            if custom_prompts:
                self.user_profile.custom_prompts = custom_prompts
            
            # Limpiar cache
            self._clear_user_cache()
            
            self.logger.info(f"Preferencias actualizadas para usuario {self.user_id}")
            
        except Exception as e:
            self.logger.error(f"Error actualizando preferencias: {e}")
    
    def _clear_user_cache(self):
        """Limpiar cache del usuario"""
        keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{self.user_id}:")]
        for key in keys_to_remove:
            del self.cache[key]
    
    async def get_prompt_statistics(self) -> Dict[str, Any]:
        """Obtener estadísticas de prompts generados"""
        try:
            user_prompts = [v for k, v in self.cache.items() if k.startswith(f"{self.user_id}:")]
            
            stats = {
                "total_prompts": len(user_prompts),
                "modes_used": {},
                "average_length": 0,
                "cache_hit_ratio": 0,
                "last_generated": None
            }
            
            if user_prompts:
                # Contar modos usados
                for prompt_data in user_prompts:
                    mode = prompt_data["context"]["agent_mode"]
                    stats["modes_used"][mode] = stats["modes_used"].get(mode, 0) + 1
                
                # Longitud promedio
                total_length = sum(len(p["prompt"]) for p in user_prompts)
                stats["average_length"] = total_length / len(user_prompts)
                
                # Último generado
                latest = max(user_prompts, key=lambda x: x["timestamp"])
                stats["last_generated"] = latest["timestamp"].isoformat()
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas: {e}")
            return {}
    
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
    
    async def force_refresh_profile(self):
        """Forzar refresco del perfil del usuario"""
        try:
            self.user_profile = await self._load_user_profile()
            self._clear_user_cache()
            self.logger.info(f"Perfil refrescado para usuario {self.user_id}")
        except Exception as e:
            self.logger.error(f"Error refrescando perfil: {e}")
