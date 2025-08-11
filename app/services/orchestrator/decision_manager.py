# app/services/orchestrator/decision_manager.py
"""
DecisionManager: Maneja confirmaciones de decisión con timeout y default seguro.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DecisionManager:
    """
    Maneja confirmaciones de decisión del usuario con timeout y default seguro.
    """
    
    def __init__(self):
        self.pending_decisions: Dict[str, asyncio.Event] = {}
        self.decision_results: Dict[str, Dict[str, Any]] = {}
        self.decision_timeouts: Dict[str, asyncio.Task] = {}
    
    async def request_decision(
        self,
        title: str,
        description: str,
        options: list,
        timeout_seconds: int = 30,
        default_action: str = "cancel"
    ) -> str:
        """
        Solicita una decisión del usuario y espera la respuesta.
        
        Args:
            title: Título de la decisión
            description: Descripción detallada
            options: Lista de opciones disponibles
            timeout_seconds: Tiempo de espera en segundos
            default_action: Acción por defecto si expira el timeout
            
        Returns:
            Acción seleccionada por el usuario o default_action
        """
        decision_id = str(uuid.uuid4())
        
        # Crear evento para esperar la respuesta
        decision_event = asyncio.Event()
        self.pending_decisions[decision_id] = decision_event
        
        # Configurar timeout
        timeout_task = asyncio.create_task(
            self._handle_timeout(decision_id, default_action)
        )
        self.decision_timeouts[decision_id] = timeout_task
        
        logger.info(f"[DecisionManager] 🔄 Esperando decisión {decision_id}: {title}")
        
        try:
            # Esperar la decisión o timeout
            await asyncio.wait_for(decision_event.wait(), timeout=timeout_seconds)
            
            # Obtener resultado
            result = self.decision_results.get(decision_id, {})
            action = result.get('action', default_action)
            
            logger.info(f"[DecisionManager] ✅ Decisión {decision_id} recibida: {action}")
            return action
            
        except asyncio.TimeoutError:
            logger.warning(f"[DecisionManager] ⏰ Timeout en decisión {decision_id}, usando default: {default_action}")
            return default_action
            
        finally:
            # Limpiar recursos
            self._cleanup_decision(decision_id)
    
    def submit_decision_response(
        self,
        decision_id: str,
        action: str,
        user_message: Optional[str] = None,
        selected_options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Procesa la respuesta de decisión del usuario.
        
        Args:
            decision_id: ID de la decisión
            action: Acción seleccionada
            user_message: Mensaje adicional del usuario
            selected_options: Opciones seleccionadas
            
        Returns:
            True si se procesó correctamente, False si la decisión no existe
        """
        if decision_id not in self.pending_decisions:
            logger.warning(f"[DecisionManager] ⚠️ Decisión {decision_id} no encontrada")
            return False
        
        # Guardar resultado
        self.decision_results[decision_id] = {
            'action': action,
            'user_message': user_message,
            'selected_options': selected_options,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Señalar que la decisión está lista
        decision_event = self.pending_decisions[decision_id]
        decision_event.set()
        
        logger.info(f"[DecisionManager] 📝 Respuesta recibida para decisión {decision_id}: {action}")
        return True
    
    async def _handle_timeout(self, decision_id: str, default_action: str):
        """Maneja el timeout de una decisión."""
        await asyncio.sleep(30)  # Esperar 30 segundos
        
        if decision_id in self.pending_decisions:
            logger.info(f"[DecisionManager] ⏰ Aplicando timeout para decisión {decision_id}")
            
            # Aplicar acción por defecto
            self.decision_results[decision_id] = {
                'action': default_action,
                'reason': 'timeout',
                'timestamp': datetime.utcnow().isoformat()
            }
            
            # Señalar que la decisión está lista
            decision_event = self.pending_decisions[decision_id]
            decision_event.set()
    
    def _cleanup_decision(self, decision_id: str):
        """Limpia los recursos de una decisión."""
        # Cancelar timeout si existe
        if decision_id in self.decision_timeouts:
            timeout_task = self.decision_timeouts[decision_id]
            if not timeout_task.done():
                timeout_task.cancel()
            del self.decision_timeouts[decision_id]
        
        # Limpiar eventos y resultados
        if decision_id in self.pending_decisions:
            del self.pending_decisions[decision_id]
        
        if decision_id in self.decision_results:
            del self.decision_results[decision_id]
        
        logger.debug(f"[DecisionManager] 🧹 Limpieza completada para decisión {decision_id}")
    
    def get_pending_decisions_count(self) -> int:
        """Retorna el número de decisiones pendientes."""
        return len(self.pending_decisions)
    
    def is_decision_pending(self, decision_id: str) -> bool:
        """Verifica si una decisión está pendiente."""
        return decision_id in self.pending_decisions
