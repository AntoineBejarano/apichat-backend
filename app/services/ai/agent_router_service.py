"""
🧠 Agent Router Service: Enrutamiento inteligente de agentes por modo

Sistema que detecta automáticamente el modo del usuario y enruta al agente apropiado,
con fallback a agentes genéricos del sistema.
"""

import logging
from typing import Dict, Any, Optional, List
from uuid import UUID
from enum import Enum
import time

from app.models.agent_model import Agent
from app.services.management.agent_service import AgentService

logger = logging.getLogger(__name__)


class AgentMode(Enum):
    """Modos de agente disponibles"""
    EXPLORER = "explorer"
    GUIDED = "guided"
    AUTO = "auto"
    CUSTOM = "custom"


class AgentRouterService:
    """
    🧠 Servicio de enrutamiento inteligente de agentes
    
    Funcionalidades:
    - Detección automática de modo basado en contexto
    - Enrutamiento a agentes específicos del usuario
    - Fallback a agentes genéricos del sistema
    - Cache de decisiones de enrutamiento
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.user_id = factory.user.id
        self.agent_service = factory.get_agent_service()
        
        # Cache de agentes genéricos del sistema
        self._generic_agents_cache = {}
        self._user_agents_cache = {}
        
        logger.info(f"[AgentRouterService] 🚀 Inicializado para usuario {self.user_id}")
    
    async def route_to_agent(
        self, 
        mode: str, 
        context: Dict[str, Any],
        user_preference: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        🎯 Enruta al agente apropiado basado en el modo y contexto
        
        Args:
            mode: Modo detectado (explorer, guided, auto, custom)
            context: Contexto del usuario (recursos, historial, etc.)
            user_preference: Preferencia específica del usuario (opcional)
            
        Returns:
            Información del agente seleccionado y metadata de enrutamiento
        """
        try:
            start_time = time.time()
            logger.info(f"[AgentRouterService] 🎯 Enrutando modo: {mode}")
            
            # 1. Intentar usar agente específico del usuario si hay preferencia
            if user_preference:
                user_agent = await self._get_user_specific_agent(user_preference)
                if user_agent:
                    result = self._build_routing_result(
                        agent=user_agent,
                        routing_method="user_preference",
                        mode=mode,
                        context=context,
                        execution_time=time.time() - start_time
                    )
                    # Log de selección por preferencia del usuario
                    await self._log_agent_selection(user_agent, mode, "user_preference", context)
                    return result
            
            # 2. Buscar agente del usuario que coincida con el modo
            user_agent = await self._get_user_agent_by_mode(mode)
            if user_agent:
                result = self._build_routing_result(
                    agent=user_agent,
                    routing_method="user_mode_match",
                    mode=mode,
                    context=context,
                    execution_time=time.time() - start_time
                )
                # Log de selección por coincidencia de modo
                await self._log_agent_selection(user_agent, mode, "user_mode_match", context)
                return result
            
            # 3. Fallback a agente genérico del sistema
            generic_agent = await self._get_generic_agent_by_mode(mode)
            if generic_agent:
                result = self._build_routing_result(
                    agent=generic_agent,
                    routing_method="generic_fallback",
                    mode=mode,
                    context=context,
                    execution_time=time.time() - start_time
                )
                # Log de selección por fallback genérico
                await self._log_agent_selection(generic_agent, mode, "generic_fallback", context)
                return result
            
            # 4. Fallback final al agente Auto Mode
            auto_agent = await self._get_generic_agent_by_mode("auto")
            if auto_agent:
                result = self._build_routing_result(
                    agent=auto_agent,
                    routing_method="auto_fallback",
                    mode="auto",
                    context=context,
                    execution_time=time.time() - start_time
                )
                # Log de selección por fallback auto
                await self._log_agent_selection(auto_agent, "auto", "auto_fallback", context)
                return result
            
            # 5. Error: No se encontró ningún agente
            logger.error(f"[AgentRouterService] ❌ No se encontró agente para modo: {mode}")
            return self._build_error_result(
                mode=mode,
                error="No se encontró agente apropiado",
                context=context
            )
            
        except Exception as e:
            logger.exception(f"[AgentRouterService] ❌ Error en enrutamiento: {e}")
            return self._build_error_result(
                mode=mode,
                error=f"Error en enrutamiento: {str(e)}",
                context=context
            )
    
    async def _get_user_specific_agent(self, agent_name: str) -> Optional[Agent]:
        """Obtiene un agente específico del usuario por nombre"""
        try:
            # Buscar en cache primero
            cache_key = f"user_agent_{self.user_id}_{agent_name}"
            if cache_key in self._user_agents_cache:
                return self._user_agents_cache[cache_key]
            
            # Buscar en base de datos
            agent = await self.agent_service.get_agent_by_name_and_user(
                name=agent_name,
                user_id=self.user_id
            )
            
            if agent:
                # Cachear resultado
                self._user_agents_cache[cache_key] = agent
                logger.info(f"[AgentRouterService] ✅ Agente específico encontrado: {agent_name}")
            
            return agent
            
        except Exception as e:
            logger.warning(f"[AgentRouterService] ⚠️ Error obteniendo agente específico: {e}")
            return None
    
    async def _get_user_agent_by_mode(self, mode: str) -> Optional[Agent]:
        """Obtiene un agente del usuario que coincida con el modo"""
        try:
            # Buscar en cache primero
            cache_key = f"user_mode_{self.user_id}_{mode}"
            if cache_key in self._user_agents_cache:
                return self._user_agents_cache[cache_key]
            
            # Buscar en base de datos
            agents = await self.agent_service.get_agents_by_user_and_mode(
                user_id=self.user_id,
                mode=mode
            )
            
            if agents:
                # Seleccionar el primer agente disponible
                agent = agents[0]
                # Cachear resultado
                self._user_agents_cache[cache_key] = agent
                logger.info(f"[AgentRouterService] ✅ Agente de usuario encontrado para modo: {mode}")
                return agent
            
            return None
            
        except Exception as e:
            logger.warning(f"[AgentRouterService] ⚠️ Error obteniendo agente de usuario: {e}")
            return None
    
    async def _get_generic_agent_by_mode(self, mode: str) -> Optional[Agent]:
        """Obtiene un agente genérico del sistema por modo"""
        try:
            # Buscar en cache primero
            cache_key = f"generic_mode_{mode}"
            if cache_key in self._generic_agents_cache:
                return self._generic_agents_cache[cache_key]
            
            # Buscar agente genérico del sistema
            system_user_id = UUID("11111111-1111-1111-1111-111111111111")
            agents = await self.agent_service.get_agents_by_user_and_mode(
                user_id=system_user_id,
                mode=mode,
                is_generic=True
            )
            
            if agents:
                # Seleccionar el primer agente genérico disponible
                agent = agents[0]
                # Cachear resultado
                self._generic_agents_cache[cache_key] = agent
                logger.info(f"[AgentRouterService] ✅ Agente genérico encontrado para modo: {mode}")
                return agent
            
            return None
            
        except Exception as e:
            logger.warning(f"[AgentRouterService] ⚠️ Error obteniendo agente genérico: {e}")
            return None
    
    def _build_routing_result(
        self, 
        agent: Agent, 
        routing_method: str, 
        mode: str, 
        context: Dict[str, Any],
        execution_time: float
    ) -> Dict[str, Any]:
        """Construye el resultado del enrutamiento"""
        return {
            "success": True,
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "system_prompt": agent.system_prompt,
                "mode": agent.mode,
                "is_generic": agent.is_generic,
                "language": agent.language,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "memory_enabled": agent.memory_enabled
            },
            "routing_metadata": {
                "method": routing_method,
                "mode_requested": mode,
                "mode_actual": agent.mode,
                "execution_time_ms": round(execution_time * 1000, 2),
                "cache_hit": routing_method in ["user_mode_match", "generic_fallback"],
                "fallback_used": routing_method in ["generic_fallback", "auto_fallback"]
            },
            "context": context
        }
    
    def _build_error_result(
        self, 
        mode: str, 
        error: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construye resultado de error"""
        return {
            "success": False,
            "error": error,
            "routing_metadata": {
                "method": "error",
                "mode_requested": mode,
                "mode_actual": None,
                "execution_time_ms": 0,
                "cache_hit": False,
                "fallback_used": False
            },
            "context": context
        }
    
    async def get_available_modes(self) -> List[str]:
        """Obtiene los modos disponibles para el usuario"""
        try:
            modes = set()
            
            # Modos de agentes del usuario
            user_agents = await self.agent_service.get_agents_by_user(self.user_id)
            for agent in user_agents:
                if agent.mode:
                    modes.add(agent.mode)
            
            # Modos de agentes genéricos
            system_user_id = UUID("11111111-1111-1111-1111-111111111111")
            generic_agents = await self.agent_service.get_agents_by_user_and_generic(
                user_id=system_user_id,
                is_generic=True
            )
            for agent in generic_agents:
                if agent.mode:
                    modes.add(agent.mode)
            
            return list(modes)
            
        except Exception as e:
            logger.error(f"[AgentRouterService] ❌ Error obteniendo modos disponibles: {e}")
            return ["auto"]  # Fallback al modo automático
    
    async def clear_cache(self):
        """Limpia el cache de agentes"""
        self._generic_agents_cache.clear()
        self._user_agents_cache.clear()
        logger.info("[AgentRouterService] 🧹 Cache limpiado")
    
    async def get_routing_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de enrutamiento"""
        return {
            "cache_size": {
                "generic_agents": len(self._generic_agents_cache),
                "user_agents": len(self._user_agents_cache)
            },
            "available_modes": await self.get_available_modes(),
            "user_id": str(self.user_id)
        }
    
    async def _log_agent_selection(
        self,
        agent: Agent,
        mode: str,
        selection_reason: str,
        context: Dict[str, Any]
    ):
        """Registra la selección de agente usando el logger"""
        try:
            # Obtener el logger de modo de forma lazy
            if not hasattr(self, '_mode_logger'):
                try:
                    self._mode_logger = self.factory.get_mode_detection_logger()
                except Exception as e:
                    logger.warning(f"[AgentRouterService] ⚠️ No se pudo obtener el logger: {e}")
                    return
            
            if self._mode_logger:
                # Obtener agentes disponibles para contexto
                available_agents = await self._get_available_agents_for_context(mode)
                
                await self._mode_logger.log_agent_selection(
                    user_id=self.user_id,
                    selected_agent=str(agent.id),
                    agent_mode=agent.mode,
                    selection_reason=selection_reason,
                    available_agents=[str(a.id) for a in available_agents],
                    context=context
                )
        except Exception as e:
            logger.warning(f"[AgentRouterService] ⚠️ Error registrando selección de agente: {e}")
    
    async def _get_available_agents_for_context(self, mode: str) -> List[Agent]:
        """Obtiene agentes disponibles para el contexto dado"""
        try:
            agents = []
            
            # Agentes del usuario
            user_agents = await self.agent_service.get_agents_by_user_and_mode(
                user_id=self.user_id,
                mode=mode
            )
            agents.extend(user_agents)
            
            # Agentes genéricos del sistema
            system_user_id = UUID("11111111-1111-1111-1111-111111111111")
            generic_agents = await self.agent_service.get_agents_by_user_and_generic(
                user_id=system_user_id,
                is_generic=True
            )
            agents.extend(generic_agents)
            
            return agents
            
        except Exception as e:
            logger.warning(f"[AgentRouterService] ⚠️ Error obteniendo agentes disponibles: {e}")
            return []


# Función helper para dependency injection
def get_agent_router_service(factory) -> AgentRouterService:
    """Obtiene una instancia del Agent Router Service"""
    return AgentRouterService(factory)
