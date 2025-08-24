"""
🎨 Servicio de Experiencia de Usuario para el Sistema Explorer/Guided

Este servicio mejora la experiencia del usuario proporcionando:
- Mensajes de confirmación amigables
- Indicadores visuales de modo activo
- Sugerencias de uso contextuales
- Transiciones suaves entre modos
"""

import logging
import random
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import json

from app.core.service_factory import ServiceFactory
from app.services.ai.mode_indicator_service import ModeIndicatorService
from app.services.ai.prompt_builder_service import PromptBuilderService

logger = logging.getLogger(__name__)


class UXMessageType(Enum):
    """Tipos de mensajes de UX"""
    MODE_CONFIRMATION = "mode_confirmation"
    MODE_TRANSITION = "mode_transition"
    SUGGESTION = "suggestion"
    HELP = "help"
    WELCOME = "welcome"
    PROGRESS = "progress"
    COMPLETION = "completion"


class UXStyle(Enum):
    """Estilos de UX"""
    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    COMPACT = "compact"
    DETAILED = "detailed"
    PLAYFUL = "playful"


class UserExperienceService:
    """
    🎨 Servicio de Experiencia de Usuario
    
    Mejora la experiencia del usuario con mensajes amigables y guía contextual
    """
    
    def __init__(self, factory: ServiceFactory):
        self.factory = factory
        self.user_id = None  # Se establece al inicializar
        self.user_preferences: Dict[str, Any] = {}
        self.ux_history: List[Dict[str, Any]] = []
        self.message_templates: Dict[str, Dict[str, Any]] = {}
        
        # Configuración de UX
        self.ux_config = {
            "max_suggestions_per_session": 5,
            "suggestion_cooldown_minutes": 10,
            "welcome_message_interval_hours": 24,
            "progress_update_interval_seconds": 30,
            "max_message_length": 200
        }
        
        # Inicializar plantillas de mensajes
        self._initialize_message_templates()
        
        logger.info("[UserExperienceService] 🎨 Servicio inicializado")
    
    def _initialize_message_templates(self):
        """Inicializa plantillas de mensajes de UX"""
        self.message_templates = {
            UXMessageType.MODE_CONFIRMATION: {
                UXStyle.FRIENDLY: {
                    "explorer": [
                        "🔍 Perfecto! Estás en modo Explorer. Te ayudo a descubrir tus recursos.",
                        "🔍 ¡Explorador activado! Vamos a ver qué tienes disponible.",
                        "🔍 Modo Explorer listo. ¿Qué te gustaría explorar primero?"
                    ],
                    "guided": [
                        "🎯 ¡Excelente! Estás en modo Guided. Te guío paso a paso.",
                        "🎯 Modo Guided activado. Vamos a crear un plan juntos.",
                        "🎯 ¡Perfecto! Te ayudo a ejecutar tu plan paso a paso."
                    ],
                    "auto": [
                        "🤖 ¡Inteligencia automática activada! Detecto lo que necesitas.",
                        "🤖 Modo Auto funcionando. Te ayudo de la mejor manera posible.",
                        "🤖 ¡Automático y listo! Adaptándome a tus necesidades."
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "explorer": [
                        "Explorer mode activated. You can now browse and discover your available resources.",
                        "Explorer mode is now active. Browse your resources and discover what's available.",
                        "You are now in Explorer mode. Access your resource catalog and explore options."
                    ],
                    "guided": [
                        "Guided mode activated. I will help you create and execute plans step by step.",
                        "Guided mode is now active. Let's work together to achieve your goals.",
                        "You are now in Guided mode. I'll assist you with planning and execution."
                    ],
                    "auto": [
                        "Auto mode activated. I will intelligently detect and adapt to your needs.",
                        "Auto mode is now active. I'll automatically determine the best approach.",
                        "You are now in Auto mode. I'll intelligently route your requests."
                    ]
                }
            },
            UXMessageType.MODE_TRANSITION: {
                UXStyle.FRIENDLY: {
                    "explorer_to_guided": [
                        "🔄 Cambiando de Explorer a Guided. ¡Ahora te ayudo a ejecutar!",
                        "🔄 Transición: Explorer → Guided. Vamos a crear tu plan.",
                        "🔄 ¡Cambio de modo! De explorar a ejecutar."
                    ],
                    "guided_to_explorer": [
                        "🔄 Cambiando de Guided a Explorer. ¡Vamos a descubrir recursos!",
                        "🔄 Transición: Guided → Explorer. Exploremos juntos.",
                        "🔄 ¡Cambio de modo! De ejecutar a explorar."
                    ],
                    "any_to_auto": [
                        "🔄 Activando modo Auto. ¡Déjame detectar lo que necesitas!",
                        "🔄 Transición a Auto. Inteligencia automática activada.",
                        "🔄 ¡Cambio a Auto! Detectando automáticamente tu intención."
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "explorer_to_guided": [
                        "Transitioning from Explorer to Guided mode. Ready to execute your plan.",
                        "Mode change: Explorer → Guided. Let's proceed with execution.",
                        "Switching to Guided mode for plan execution."
                    ],
                    "guided_to_explorer": [
                        "Transitioning from Guided to Explorer mode. Ready to discover resources.",
                        "Mode change: Guided → Explorer. Let's explore available options.",
                        "Switching to Explorer mode for resource discovery."
                    ],
                    "any_to_auto": [
                        "Activating Auto mode. I'll intelligently detect your needs.",
                        "Transitioning to Auto mode. Automatic detection enabled.",
                        "Switching to Auto mode for intelligent routing."
                    ]
                }
            },
            UXMessageType.SUGGESTION: {
                UXStyle.FRIENDLY: {
                    "general": [
                        "💡 Tip: Puedes decir 'explore' para ver tus recursos o 'plan' para crear acciones.",
                        "💡 Sugerencia: Usa 'help' para obtener ayuda o '?' para opciones.",
                        "💡 Consejo: Di 'auto' para que detecte automáticamente lo que necesitas."
                    ],
                    "explorer": [
                        "💡 En modo Explorer: Di 'show databases' o 'list resources'.",
                        "💡 Explorer tip: Usa 'browse' o 'overview' para ver todo.",
                        "💡 Explorer hint: Di 'what can I do' para opciones disponibles."
                    ],
                    "guided": [
                        "💡 En modo Guided: Di 'create plan for' o 'help me with'.",
                        "💡 Guided tip: Usa 'step by step' o 'walk through'.",
                        "💡 Guided hint: Di 'optimize' o 'analyze' para mejoras."
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "general": [
                        "Tip: Use 'explore' to view resources or 'plan' to create actions.",
                        "Suggestion: Use 'help' for assistance or '?' for options.",
                        "Advice: Say 'auto' for automatic detection of your needs."
                    ],
                    "explorer": [
                        "Explorer tip: Say 'show databases' or 'list resources'.",
                        "Explorer suggestion: Use 'browse' or 'overview' to see everything.",
                        "Explorer hint: Say 'what can I do' for available options."
                    ],
                    "guided": [
                        "Guided tip: Say 'create plan for' or 'help me with'.",
                        "Guided suggestion: Use 'step by step' or 'walk through'.",
                        "Guided hint: Say 'optimize' or 'analyze' for improvements."
                    ]
                }
            },
            UXMessageType.HELP: {
                UXStyle.FRIENDLY: {
                    "general": [
                        "🤝 ¡Hola! Soy tu asistente AI. ¿En qué puedo ayudarte?",
                        "🤝 ¡Hola! Estoy aquí para ayudarte. ¿Qué te gustaría hacer?",
                        "🤝 ¡Hola! Soy tu guía. ¿Cómo puedo asistirte hoy?"
                    ],
                    "explorer": [
                        "🤝 En modo Explorer puedes: ver recursos, explorar opciones, descubrir capacidades.",
                        "🤝 Explorer te permite: navegar por tu catálogo, ver qué hay disponible, explorar opciones.",
                        "🤝 Como Explorer puedes: listar recursos, ver esquemas, explorar conexiones."
                    ],
                    "guided": [
                        "🤝 En modo Guided puedo: crear planes, guiarte paso a paso, ayudarte a ejecutar.",
                        "🤝 Guided te permite: planificar acciones, ejecutar tareas, optimizar procesos.",
                        "🤝 Como Guided puedo: analizar datos, crear estrategias, implementar soluciones."
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "general": [
                        "Hello! I'm your AI assistant. How can I help you today?",
                        "Hello! I'm here to assist you. What would you like to do?",
                        "Hello! I'm your guide. How may I assist you today?"
                    ],
                    "explorer": [
                        "In Explorer mode you can: view resources, explore options, discover capabilities.",
                        "Explorer allows you to: navigate your catalog, see what's available, explore options.",
                        "As Explorer you can: list resources, view schemas, explore connections."
                    ],
                    "guided": [
                        "In Guided mode I can: create plans, guide you step by step, help you execute.",
                        "Guided allows you to: plan actions, execute tasks, optimize processes.",
                        "As Guided I can: analyze data, create strategies, implement solutions."
                    ]
                }
            },
            UXMessageType.WELCOME: {
                UXStyle.FRIENDLY: {
                    "new_user": [
                        "🎉 ¡Bienvenido! Soy tu nuevo asistente AI. ¿Empezamos explorando?",
                        "🎉 ¡Hola! Soy tu guía personal. ¿Qué te gustaría hacer primero?",
                        "🎉 ¡Bienvenido! Estoy aquí para ayudarte. ¿Exploramos juntos?"
                    ],
                    "returning_user": [
                        "👋 ¡Hola de nuevo! ¿Cómo va todo? ¿Continuamos donde lo dejamos?",
                        "👋 ¡Bienvenido de vuelta! ¿Qué te gustaría hacer hoy?",
                        "👋 ¡Hola! Me alegra verte de nuevo. ¿En qué puedo ayudarte?"
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "new_user": [
                        "Welcome! I'm your new AI assistant. Shall we start by exploring?",
                        "Hello! I'm your personal guide. What would you like to do first?",
                        "Welcome! I'm here to help. Shall we explore together?"
                    ],
                    "returning_user": [
                        "Hello again! How are things going? Shall we continue where we left off?",
                        "Welcome back! What would you like to do today?",
                        "Hello! Nice to see you again. How can I assist you?"
                    ]
                }
            },
            UXMessageType.PROGRESS: {
                UXStyle.FRIENDLY: {
                    "started": [
                        "🚀 ¡Empezando! Preparando todo para ti...",
                        "🚀 ¡Vamos! Inicializando el sistema...",
                        "🚀 ¡Listo! Preparando tu experiencia..."
                    ],
                    "in_progress": [
                        "⏳ Trabajando en ello... Un momento por favor.",
                        "⏳ Procesando tu solicitud... Casi listo.",
                        "⏳ En progreso... Preparando la respuesta."
                    ],
                    "almost_done": [
                        "✨ ¡Casi listo! Terminando los últimos detalles...",
                        "✨ ¡Casi ahí! Finalizando el proceso...",
                        "✨ ¡Pronto! Completando la tarea..."
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "started": [
                        "Starting... Preparing everything for you.",
                        "Initializing... Setting up the system.",
                        "Ready... Preparing your experience."
                    ],
                    "in_progress": [
                        "Processing... Please wait a moment.",
                        "Working on your request... Almost ready.",
                        "In progress... Preparing the response."
                    ],
                    "almost_done": [
                        "Almost ready... Finalizing details.",
                        "Almost there... Completing the process.",
                        "Soon... Finishing the task."
                    ]
                }
            },
            UXMessageType.COMPLETION: {
                UXStyle.FRIENDLY: {
                    "success": [
                        "✅ ¡Listo! ¿Hay algo más en lo que pueda ayudarte?",
                        "✅ ¡Completado! ¿Te gustaría hacer algo más?",
                        "✅ ¡Perfecto! ¿Necesitas ayuda con algo más?"
                    ],
                    "partial": [
                        "⚠️ ¡Casi listo! Algunas partes se completaron. ¿Quieres que revise el resto?",
                        "⚠️ ¡Parcialmente completo! ¿Te gustaría que termine lo que falta?",
                        "⚠️ ¡Progreso hecho! ¿Quieres que continúe con el resto?"
                    ]
                },
                UXStyle.PROFESSIONAL: {
                    "success": [
                        "Complete! Is there anything else I can help you with?",
                        "Done! Would you like to do something else?",
                        "Finished! Do you need help with anything else?"
                    ],
                    "partial": [
                        "Partially complete! Some parts were finished. Would you like me to review the rest?",
                        "Partially done! Would you like me to complete what's missing?",
                        "Progress made! Would you like me to continue with the rest?"
                    ]
                }
            }
        }
    
    async def initialize(self, user_id: str):
        """Inicializa el servicio para un usuario específico"""
        self.user_id = user_id
        logger.info(f"[UserExperienceService] Inicializado para usuario: {user_id}")
        
        # Cargar preferencias del usuario
        await self._load_user_preferences()
        
        # Cargar historial de UX
        await self._load_ux_history()
    
    async def _load_user_preferences(self):
        """Carga preferencias del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, preferencias por defecto
            self.user_preferences = {
                "ux_style": UXStyle.FRIENDLY.value,
                "language": "es",  # español por defecto
                "message_length": "medium",
                "show_suggestions": True,
                "show_progress": True,
                "show_welcome": True
            }
            
            logger.debug(f"[UserExperienceService] Preferencias cargadas para usuario: {self.user_id}")
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error cargando preferencias: {e}")
    
    async def _load_ux_history(self):
        """Carga historial de UX del usuario"""
        try:
            # TODO: Implementar carga desde base de datos
            # Por ahora, historial vacío
            self.ux_history = []
            
            logger.debug(f"[UserExperienceService] Historial de UX cargado")
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error cargando historial de UX: {e}")
    
    async def get_mode_confirmation_message(
        self,
        mode: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        🎯 Obtiene mensaje de confirmación de modo
        
        Args:
            mode: Modo confirmado (explorer, guided, auto)
            context: Contexto adicional
            
        Returns:
            Dict con mensaje, estilo y metadatos
        """
        try:
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener plantillas para el modo y estilo
            templates = self.message_templates.get(UXMessageType.MODE_CONFIRMATION, {}).get(style, {})
            
            # Seleccionar mensaje aleatorio
            messages = templates.get(mode, ["Modo activado."])
            selected_message = random.choice(messages)
            
            # Personalizar mensaje con contexto
            personalized_message = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_message,
                "message_type": UXMessageType.MODE_CONFIRMATION.value,
                "style": style.value,
                "mode": mode,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            logger.info(f"[UserExperienceService] Mensaje de confirmación generado para modo: {mode}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de confirmación: {e}")
            return self._get_fallback_message(UXMessageType.MODE_CONFIRMATION, mode)
    
    async def get_mode_transition_message(
        self,
        from_mode: str,
        to_mode: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        🔄 Obtiene mensaje de transición de modo
        
        Args:
            from_mode: Modo anterior
            to_mode: Nuevo modo
            context: Contexto adicional
            
        Returns:
            Dict con mensaje, estilo y metadatos
        """
        try:
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Crear clave de transición
            transition_key = f"{from_mode}_to_{to_mode}"
            
            # Obtener plantillas para la transición y estilo
            templates = self.message_templates.get(UXMessageType.MODE_TRANSITION, {}).get(style, {})
            
            # Buscar mensaje específico o usar genérico
            messages = templates.get(transition_key, templates.get("any_to_auto", ["Cambiando modo..."]))
            selected_message = random.choice(messages)
            
            # Personalizar mensaje con contexto
            personalized_message = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_message,
                "message_type": UXMessageType.MODE_TRANSITION.value,
                "style": style.value,
                "from_mode": from_mode,
                "to_mode": to_mode,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            logger.info(f"[UserExperienceService] Mensaje de transición generado: {from_mode} → {to_mode}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de transición: {e}")
            return self._get_fallback_message(UXMessageType.MODE_TRANSITION, "transition")
    
    async def get_suggestion_message(
        self,
        context: Optional[Dict[str, Any]] = None,
        force: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        💡 Obtiene mensaje de sugerencia contextual
        
        Args:
            context: Contexto actual (modo, recursos, etc.)
            force: Forzar sugerencia incluso si no es el momento apropiado
            
        Returns:
            Dict con sugerencia o None si no es apropiado
        """
        try:
            # Verificar si es apropiado mostrar sugerencias
            if not force and not self._should_show_suggestion():
                return None
            
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener contexto para la sugerencia
            suggestion_context = context or {}
            current_mode = suggestion_context.get("current_mode", "general")
            
            # Obtener plantillas para sugerencias
            templates = self.message_templates.get(UXMessageType.SUGGESTION, {}).get(style, {})
            
            # Seleccionar sugerencia apropiada
            messages = templates.get(current_mode, templates.get("general", ["Tip: Usa 'help' para obtener ayuda."]))
            selected_message = random.choice(messages)
            
            # Personalizar sugerencia
            personalized_suggestion = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_suggestion,
                "message_type": UXMessageType.SUGGESTION.value,
                "style": style.value,
                "context": suggestion_context,
                "timestamp": datetime.now().isoformat(),
                "suggestion_type": current_mode
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            # Actualizar cooldown de sugerencias
            self._update_suggestion_cooldown()
            
            logger.info(f"[UserExperienceService] Sugerencia generada para modo: {current_mode}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando sugerencia: {e}")
            return None
    
    async def get_help_message(
        self,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        🤝 Obtiene mensaje de ayuda contextual
        
        Args:
            context: Contexto actual (modo, recursos, etc.)
            
        Returns:
            Dict con mensaje de ayuda
        """
        try:
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener contexto para la ayuda
            help_context = context or {}
            current_mode = help_context.get("current_mode", "general")
            
            # Obtener plantillas para ayuda
            templates = self.message_templates.get(UXMessageType.HELP, {}).get(style, {})
            
            # Seleccionar mensaje de ayuda apropiado
            messages = templates.get(current_mode, templates.get("general", ["¡Hola! ¿En qué puedo ayudarte?"]))
            selected_message = random.choice(messages)
            
            # Personalizar mensaje de ayuda
            personalized_help = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_help,
                "message_type": UXMessageType.HELP.value,
                "style": style.value,
                "context": help_context,
                "timestamp": datetime.now().isoformat(),
                "help_type": current_mode
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            logger.info(f"[UserExperienceService] Mensaje de ayuda generado para modo: {current_mode}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de ayuda: {e}")
            return self._get_fallback_message(UXMessageType.HELP, "general")
    
    async def get_welcome_message(
        self,
        user_type: str = "returning_user",
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        🎉 Obtiene mensaje de bienvenida
        
        Args:
            user_type: Tipo de usuario (new_user, returning_user)
            context: Contexto adicional
            
        Returns:
            Dict con mensaje de bienvenida o None si no es apropiado
        """
        try:
            # Verificar si es apropiado mostrar mensaje de bienvenida
            if not self._should_show_welcome():
                return None
            
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener plantillas para bienvenida
            templates = self.message_templates.get(UXMessageType.WELCOME, {}).get(style, {})
            
            # Seleccionar mensaje de bienvenida apropiado
            messages = templates.get(user_type, templates.get("returning_user", ["¡Hola!"]))
            selected_message = random.choice(messages)
            
            # Personalizar mensaje de bienvenida
            personalized_welcome = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_welcome,
                "message_type": UXMessageType.WELCOME.value,
                "style": style.value,
                "user_type": user_type,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            # Actualizar cooldown de bienvenida
            self._update_welcome_cooldown()
            
            logger.info(f"[UserExperienceService] Mensaje de bienvenida generado para: {user_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de bienvenida: {e}")
            return None
    
    async def get_progress_message(
        self,
        progress_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ⏳ Obtiene mensaje de progreso
        
        Args:
            progress_type: Tipo de progreso (started, in_progress, almost_done)
            context: Contexto adicional
            
        Returns:
            Dict con mensaje de progreso
        """
        try:
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener plantillas para progreso
            templates = self.message_templates.get(UXMessageType.PROGRESS, {}).get(style, {})
            
            # Seleccionar mensaje de progreso apropiado
            messages = templates.get(progress_type, ["Procesando..."])
            selected_message = random.choice(messages)
            
            # Personalizar mensaje de progreso
            personalized_progress = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_progress,
                "message_type": UXMessageType.PROGRESS.value,
                "style": style.value,
                "progress_type": progress_type,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            logger.info(f"[UserExperienceService] Mensaje de progreso generado: {progress_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de progreso: {e}")
            return self._get_fallback_message(UXMessageType.PROGRESS, progress_type)
    
    async def get_completion_message(
        self,
        completion_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ✅ Obtiene mensaje de completado
        
        Args:
            completion_type: Tipo de completado (success, partial)
            context: Contexto adicional
            
        Returns:
            Dict con mensaje de completado
        """
        try:
            # Determinar estilo del usuario
            style = UXStyle(self.user_preferences.get("ux_style", UXStyle.FRIENDLY.value))
            
            # Obtener plantillas para completado
            templates = self.message_templates.get(UXMessageType.COMPLETION, {}).get(style, {})
            
            # Seleccionar mensaje de completado apropiado
            messages = templates.get(completion_type, ["Completado."])
            selected_message = random.choice(messages)
            
            # Personalizar mensaje de completado
            personalized_completion = await self._personalize_message(selected_message, context)
            
            # Crear respuesta
            result = {
                "message": personalized_completion,
                "message_type": UXMessageType.COMPLETION.value,
                "style": style.value,
                "completion_type": completion_type,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            # Registrar en historial
            await self._record_ux_message(result)
            
            logger.info(f"[UserExperienceService] Mensaje de completado generado: {completion_type}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error generando mensaje de completado: {e}")
            return self._get_fallback_message(UXMessageType.COMPLETION, completion_type)
    
    async def _personalize_message(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """Personaliza un mensaje con contexto específico"""
        try:
            if not context:
                return message
            
            # Reemplazar placeholders con contexto
            personalized_message = message
            
            # Reemplazar {resource_type} si está disponible
            if "{resource_type}" in personalized_message and "resource_type" in context:
                personalized_message = personalized_message.replace(
                    "{resource_type}", 
                    context["resource_type"]
                )
            
            # Reemplazar {user_name} si está disponible
            if "{user_name}" in personalized_message and "user_name" in context:
                personalized_message = personalized_message.replace(
                    "{user_name}", 
                    context["user_name"]
                )
            
            # Reemplazar {mode} si está disponible
            if "{mode}" in personalized_message and "current_mode" in context:
                personalized_message = personalized_message.replace(
                    "{mode}", 
                    context["current_mode"]
                )
            
            # Limitar longitud del mensaje si es necesario
            max_length = self.ux_config["max_message_length"]
            if len(personalized_message) > max_length:
                personalized_message = personalized_message[:max_length-3] + "..."
            
            return personalized_message
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error personalizando mensaje: {e}")
            return message
    
    def _should_show_suggestion(self) -> bool:
        """Determina si es apropiado mostrar una sugerencia"""
        try:
            # Verificar cooldown de sugerencias
            last_suggestion = self._get_last_suggestion_time()
            if last_suggestion:
                cooldown_minutes = self.ux_config["suggestion_cooldown_minutes"]
                if datetime.now() - last_suggestion < timedelta(minutes=cooldown_minutes):
                    return False
            
            # Verificar límite de sugerencias por sesión
            suggestions_this_session = len([
                m for m in self.ux_history[-100:]  # Últimos 100 mensajes
                if m.get("message_type") == UXMessageType.SUGGESTION.value
            ])
            
            if suggestions_this_session >= self.ux_config["max_suggestions_per_session"]:
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error verificando sugerencias: {e}")
            return False
    
    def _should_show_welcome(self) -> bool:
        """Determina si es apropiado mostrar mensaje de bienvenida"""
        try:
            # Verificar cooldown de bienvenida
            last_welcome = self._get_last_welcome_time()
            if last_welcome:
                cooldown_hours = self.ux_config["welcome_message_interval_hours"]
                if datetime.now() - last_welcome < timedelta(hours=cooldown_hours):
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error verificando bienvenida: {e}")
            return False
    
    def _get_last_suggestion_time(self) -> Optional[datetime]:
        """Obtiene la última vez que se mostró una sugerencia"""
        try:
            for message in reversed(self.ux_history):
                if message.get("message_type") == UXMessageType.SUGGESTION.value:
                    return datetime.fromisoformat(message["timestamp"])
            return None
        except Exception:
            return None
    
    def _get_last_welcome_time(self) -> Optional[datetime]:
        """Obtiene la última vez que se mostró un mensaje de bienvenida"""
        try:
            for message in reversed(self.ux_history):
                if message.get("message_type") == UXMessageType.WELCOME.value:
                    return datetime.fromisoformat(message["timestamp"])
            return None
        except Exception:
            return None
    
    def _update_suggestion_cooldown(self):
        """Actualiza el cooldown de sugerencias"""
        try:
            # Registrar timestamp de la última sugerencia
            self.ux_history.append({
                "message_type": UXMessageType.SUGGESTION.value,
                "timestamp": datetime.now().isoformat(),
                "cooldown_update": True
            })
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error actualizando cooldown de sugerencias: {e}")
    
    def _update_welcome_cooldown(self):
        """Actualiza el cooldown de bienvenida"""
        try:
            # Registrar timestamp de la última bienvenida
            self.ux_history.append({
                "message_type": UXMessageType.WELCOME.value,
                "timestamp": datetime.now().isoformat(),
                "cooldown_update": True
            })
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error actualizando cooldown de bienvenida: {e}")
    
    async def _record_ux_message(self, message_data: Dict[str, Any]):
        """Registra un mensaje de UX en el historial"""
        try:
            # Agregar al historial
            self.ux_history.append(message_data)
            
            # Mantener solo los últimos 1000 mensajes
            if len(self.ux_history) > 1000:
                self.ux_history = self.ux_history[-1000:]
            
            # TODO: Persistir en base de datos
            
        except Exception as e:
            logger.warning(f"[UserExperienceService] ⚠️ Error registrando mensaje de UX: {e}")
    
    def _get_fallback_message(self, message_type: UXMessageType, context: str) -> Dict[str, Any]:
        """Obtiene mensaje de fallback cuando falla la generación"""
        fallback_messages = {
            UXMessageType.MODE_CONFIRMATION: "Modo activado.",
            UXMessageType.MODE_TRANSITION: "Cambiando modo...",
            UXMessageType.SUGGESTION: "Tip: Usa 'help' para obtener ayuda.",
            UXMessageType.HELP: "¡Hola! ¿En qué puedo ayudarte?",
            UXMessageType.WELCOME: "¡Bienvenido!",
            UXMessageType.PROGRESS: "Procesando...",
            UXMessageType.COMPLETION: "Completado."
        }
        
        return {
            "message": fallback_messages.get(message_type, "Mensaje no disponible."),
            "message_type": message_type.value,
            "style": "fallback",
            "context": {"fallback": True, "context": context},
            "timestamp": datetime.now().isoformat(),
            "error": True
        }
    
    async def update_user_preferences(self, new_preferences: Dict[str, Any]):
        """Actualiza preferencias del usuario"""
        try:
            self.user_preferences.update(new_preferences)
            
            # TODO: Persistir en base de datos
            logger.info(f"[UserExperienceService] ✅ Preferencias actualizadas: {len(new_preferences)}")
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error actualizando preferencias: {e}")
    
    async def get_ux_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de UX del usuario"""
        try:
            if not self.ux_history:
                return {"total_messages": 0, "types": {}, "style_distribution": {}}
            
            # Contar por tipo
            type_counts = {}
            style_counts = {}
            
            for message in self.ux_history:
                message_type = message.get("message_type", "unknown")
                style = message.get("style", "unknown")
                
                type_counts[message_type] = type_counts.get(message_type, 0) + 1
                style_counts[style] = style_counts.get(style, 0) + 1
            
            return {
                "total_messages": len(self.ux_history),
                "types": type_counts,
                "style_distribution": style_counts,
                "recent_messages": len([m for m in self.ux_history if 
                    datetime.fromisoformat(m["timestamp"]) > datetime.now() - timedelta(hours=1)])
            }
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error obteniendo estadísticas: {e}")
            return {"error": str(e)}
    
    async def cleanup(self):
        """Limpia recursos del servicio"""
        try:
            # Limpiar historial antiguo
            cutoff_time = datetime.now() - timedelta(days=7)
            self.ux_history = [
                m for m in self.ux_history 
                if datetime.fromisoformat(m["timestamp"]) > cutoff_time
            ]
            
            logger.info(f"[UserExperienceService] 🧹 Limpieza completada")
            
        except Exception as e:
            logger.error(f"[UserExperienceService] ❌ Error en limpieza: {e}")


# Factory function para crear el servicio
async def create_user_experience_service(factory: ServiceFactory, user_id: str) -> UserExperienceService:
    """Crea e inicializa el servicio de experiencia de usuario"""
    service = UserExperienceService(factory)
    await service.initialize(user_id)
    return service
