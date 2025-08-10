"""
AgentManager - Manejo de agentes y prompts
───────────────────────────────────────────
Responsable de:
- Carga de prompts de agentes
- Manejo de configuraciones de agentes
- Optimización de prompts para tokens
- Gestión de tipos de agentes
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID

from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context

logger = logging.getLogger(__name__)


class AgentManager:
    """Maneja todas las operaciones relacionadas con agentes y prompts"""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        
        # Configuración de límites
        self.max_agent_prompt_chars = 3000
        self.max_agent_name_chars = 100
        
    @monitor_performance("load_agent_prompt")
    @profile_function("load_agent_prompt")
    async def load_agent_prompt_async(self, agent_id: UUID) -> str:
        """Carga el prompt de un agente de forma asíncrona"""
        try:
            with performance_context("load_agent_prompt"):
                # Obtener agente desde el servicio
                agent_service = self.factory.get_service("agent")
                
                # Cargar agente
                agent = await agent_service.get_agent(agent_id)
                if not agent:
                    logger.warning(f"Agente {agent_id} no encontrado")
                    return self._get_default_agent_prompt()
                
                # Obtener prompt del agente
                prompt = agent.get("prompt", "")
                if not prompt:
                    logger.warning(f"Agente {agent_id} no tiene prompt configurado")
                    return self._get_default_agent_prompt()
                
                # Optimizar prompt para tokens
                optimized_prompt = self._optimize_agent_prompt(prompt)
                
                return optimized_prompt
                
        except Exception as e:
            logger.error(f"Error cargando prompt del agente {agent_id}: {e}")
            return self._get_default_agent_prompt()
    
    def _get_default_agent_prompt(self) -> str:
        """Retorna un prompt por defecto para agentes"""
        return """Eres un asistente inteligente que ayuda a los usuarios a interactuar con bases de datos y aplicaciones. 
        Tu objetivo es proporcionar respuestas claras y útiles basadas en el contexto disponible."""
    
    def _optimize_agent_prompt(self, prompt: str) -> str:
        """Optimiza el prompt del agente para reducir tokens"""
        try:
            if len(prompt) <= self.max_agent_prompt_chars:
                return prompt
            
            # Truncar prompt y agregar indicador
            optimized_prompt = prompt[:self.max_agent_prompt_chars] + "..."
            
            # Agregar nota sobre optimización
            optimized_prompt += "\n\n[Nota: Este prompt ha sido optimizado para reducir el uso de tokens]"
            
            logger.info(f"Prompt del agente optimizado: {len(prompt)} -> {len(optimized_prompt)} caracteres")
            
            return optimized_prompt
            
        except Exception as e:
            logger.error(f"Error optimizando prompt del agente: {e}")
            return prompt
    
    def load_agent_prompt(self, agent_id: Optional[UUID]) -> str:
        """Carga el prompt del agente (versión síncrona)"""
        try:
            if not agent_id:
                return self._get_default_agent_prompt()
            
            # Crear nueva sesión
            db = SessionLocal()
            
            try:
                # Obtener agente desde la base de datos
                agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
                
                if not agent:
                    logger.warning(f"Agente {agent_id} no encontrado en versión síncrona")
                    return self._get_default_agent_prompt()
                
                # Obtener prompt
                prompt = agent.prompt or ""
                if not prompt:
                    logger.warning(f"Agente {agent_id} no tiene prompt configurado en versión síncrona")
                    return self._get_default_agent_prompt()
                
                # Optimizar prompt
                optimized_prompt = self._optimize_agent_prompt(prompt)
                
                return optimized_prompt
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error cargando prompt del agente {agent_id} en versión síncrona: {e}")
            return self._get_default_agent_prompt()
    
    def get_agent_type(self, agent_id: Optional[UUID]) -> str:
        """Obtiene el tipo de un agente"""
        try:
            if not agent_id:
                return "default"
            
            # Crear nueva sesión
            db = SessionLocal()
            
            try:
                # Obtener agente desde la base de datos
                agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
                
                if not agent:
                    return "default"
                
                return agent.type or "default"
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error obteniendo tipo del agente {agent_id}: {e}")
            return "default"
    
    def get_agent_config(self, agent_id: Optional[UUID]) -> Dict[str, Any]:
        """Obtiene la configuración de un agente"""
        try:
            if not agent_id:
                return {}
            
            # Crear nueva sesión
            db = SessionLocal()
            
            try:
                # Obtener agente desde la base de datos
                agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
                
                if not agent:
                    return {}
                
                # Convertir configuración
                config = agent.config or {}
                if isinstance(config, str):
                    try:
                        import json
                        config = json.loads(config)
                    except:
                        config = {}
                
                return config
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error obteniendo configuración del agente {agent_id}: {e}")
            return {}
    
    def validate_agent_permissions(self, agent_id: Optional[UUID], user_id: UUID) -> bool:
        """Valida si el usuario tiene permisos para usar el agente"""
        try:
            if not agent_id:
                return True  # Agente por defecto siempre disponible
            
            # Crear nueva sesión
            db = SessionLocal()
            
            try:
                # Verificar permisos del usuario para el agente
                permission = db.query(PermissionModel).filter(
                    PermissionModel.user_id == user_id,
                    PermissionModel.resource_type == "agent",
                    PermissionModel.resource_id == agent_id
                ).first()
                
                if permission:
                    return True
                
                # Verificar si el agente es público
                agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
                if agent and agent.is_public:
                    return True
                
                return False
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error validando permisos del agente {agent_id} para usuario {user_id}: {e}")
            return False
    
    def get_agent_metadata(self, agent_id: Optional[UUID]) -> Dict[str, Any]:
        """Obtiene metadatos de un agente"""
        try:
            if not agent_id:
                return {
                    "name": "Agente por defecto",
                    "type": "default",
                    "version": "1.0",
                    "description": "Agente estándar del sistema"
                }
            
            # Crear nueva sesión
            db = SessionLocal()
            
            try:
                # Obtener agente desde la base de datos
                agent = db.query(AgentModel).filter(AgentModel.id == agent_id).first()
                
                if not agent:
                    return {}
                
                # Extraer metadatos
                metadata = {
                    "name": agent.name or "Agente sin nombre",
                    "type": agent.type or "unknown",
                    "version": getattr(agent, 'version', '1.0'),
                    "description": agent.description or "",
                    "created_at": agent.created_at.isoformat() if agent.created_at else None,
                    "updated_at": agent.updated_at.isoformat() if agent.updated_at else None
                }
                
                return metadata
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error obteniendo metadatos del agente {agent_id}: {e}")
            return {}
    
    def estimate_tokens_for_agent_prompt(self, prompt: str) -> int:
        """Estima el número de tokens para el prompt del agente"""
        try:
            # Estimación aproximada: 1 token ≈ 4 caracteres
            estimated_tokens = len(prompt) // 4
            
            return estimated_tokens
            
        except Exception as e:
            logger.error(f"Error estimando tokens para prompt del agente: {e}")
            return 0
    
    def should_optimize_agent_prompt(self, prompt: str) -> bool:
        """Determina si el prompt del agente debe ser optimizado"""
        try:
            estimated_tokens = self.estimate_tokens_for_agent_prompt(prompt)
            return estimated_tokens > 1000  # Límite de 1000 tokens
            
        except Exception as e:
            logger.error(f"Error determinando si optimizar prompt del agente: {e}")
            return False
    
    def create_agent_context(self, agent_id: Optional[UUID], user_id: UUID) -> Dict[str, Any]:
        """Crea el contexto completo para un agente"""
        try:
            context = {
                "agent": {},
                "user": {
                    "id": str(user_id)
                },
                "permissions": {}
            }
            
            if agent_id:
                # Obtener información del agente
                context["agent"] = {
                    "id": str(agent_id),
                    "type": self.get_agent_type(agent_id),
                    "config": self.get_agent_config(agent_id),
                    "metadata": self.get_agent_metadata(agent_id)
                }
                
                # Verificar permisos
                has_permissions = self.validate_agent_permissions(agent_id, user_id)
                context["permissions"]["can_use_agent"] = has_permissions
                
                if has_permissions:
                    # Cargar prompt del agente
                    prompt = self.load_agent_prompt(agent_id)
                    context["agent"]["prompt"] = prompt
                    context["agent"]["prompt_tokens"] = self.estimate_tokens_for_agent_prompt(prompt)
                else:
                    # Usar agente por defecto si no hay permisos
                    context["agent"]["type"] = "default"
                    context["agent"]["prompt"] = self._get_default_agent_prompt()
                    context["agent"]["prompt_tokens"] = self.estimate_tokens_for_agent_prompt(context["agent"]["prompt"])
            else:
                # Agente por defecto
                context["agent"] = {
                    "type": "default",
                    "prompt": self._get_default_agent_prompt(),
                    "prompt_tokens": self.estimate_tokens_for_agent_prompt(self._get_default_agent_prompt())
                }
                context["permissions"]["can_use_agent"] = True
            
            return context
            
        except Exception as e:
            logger.error(f"Error creando contexto del agente {agent_id}: {e}")
            return {
                "agent": {
                    "type": "default",
                    "prompt": self._get_default_agent_prompt(),
                    "prompt_tokens": 0
                },
                "user": {"id": str(user_id)},
                "permissions": {"can_use_agent": True}
            }
