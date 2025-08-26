"""
🔧 System Preparation Manager: Coordina la preparación del ServiceFactory por fases

Este servicio maneja la inicialización progresiva del ServiceFactory,
asegurando que cada fase se complete antes de continuar con la siguiente.
"""

from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemPreparationManager:
    """
    🔧 System Preparation Manager
    
    Coordina la preparación progresiva del ServiceFactory por fases:
    - Fase 1: Core Services (DB, Auth, Config)
    - Fase 2: AI Services (Agents, Mode Detection)
    - Fase 3: Execution Services (Chat, Functions)
    - Fase 4: Orchestrator Services (Cache, Data, Management)
    """
    
    def __init__(self, factory):
        """
        Inicializa el System Preparation Manager
        
        Args:
            factory: Instancia de ServiceFactory a preparar
        """
        self.factory = factory
        self.phase_manager = None
        self.preparation_start_time = None
        self.preparation_end_time = None
        
        logger.info(f"[SystemPreparationManager] ✅ Inicializado para factory")
    
    async def prepare_for_chat(self) -> Dict[str, Any]:
        """
        Prepara factory para uso en chat (Fases 1-3)
        
        Returns:
            Dict con el resultado de la preparación
        """
        try:
            self.preparation_start_time = datetime.now()
            logger.info(f"[SystemPreparationManager] 🚀 Iniciando preparación para chat")
            
            # Preparar fases 1-3
            await self.factory.prepare_phase_1_core()
            await self.factory.prepare_phase_2_ai()
            await self.factory.prepare_phase_3_execution()
            
            # Obtener estado de fases
            self.phase_manager = self.factory.phase_manager
            phase_status = await self.phase_manager.get_phase_status()
            
            self.preparation_end_time = datetime.now()
            preparation_duration = (self.preparation_end_time - self.preparation_start_time).total_seconds()
            
            logger.info(f"[SystemPreparationManager] ✅ Factory preparado para chat en {preparation_duration:.2f}s")
            
            return {
                'success': True,
                'phase_status': phase_status,
                'ready_for_chat': True,
                'preparation_duration': preparation_duration,
                'completed_phases': ['phase_1_core', 'phase_2_ai', 'phase_3_execution']
            }
            
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error preparando para chat: {e}")
            return {
                'success': False,
                'error': str(e),
                'ready_for_chat': False,
                'preparation_duration': None
            }
    
    async def prepare_for_orchestrator(self) -> Dict[str, Any]:
        """
        Prepara factory para orquestador (todas las fases)
        
        Returns:
            Dict con el resultado de la preparación
        """
        try:
            self.preparation_start_time = datetime.now()
            logger.info(f"[SystemPreparationManager] 🚀 Iniciando preparación para orquestador")
            
            # Preparar para chat primero (fases 1-3)
            chat_result = await self.prepare_for_chat()
            if not chat_result['success']:
                return chat_result
            
            # Preparar fase adicional para orquestador
            await self.factory.prepare_phase_4_orchestrator()
            
            # Obtener estado final
            phase_status = await self.phase_manager.get_phase_status()
            
            self.preparation_end_time = datetime.now()
            preparation_duration = (self.preparation_end_time - self.preparation_start_time).total_seconds()
            
            logger.info(f"[SystemPreparationManager] ✅ Factory preparado para orquestador en {preparation_duration:.2f}s")
            
            return {
                'success': True,
                'ready_for_orchestrator': True,
                'ready_for_chat': True,
                'phase_status': phase_status,
                'preparation_duration': preparation_duration,
                'completed_phases': ['phase_1_core', 'phase_2_ai', 'phase_3_execution', 'phase_4_orchestrator']
            }
            
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error preparando para orquestador: {e}")
            return {
                'success': False,
                'error': str(e),
                'ready_for_chat': False,
                'ready_for_orchestrator': False,
                'preparation_duration': None
            }
    
    async def get_preparation_status(self) -> Dict[str, Any]:
        """
        Obtiene estado actual de preparación
        
        Returns:
            Dict con el estado de preparación
        """
        if not self.phase_manager:
            return {
                'status': 'not_started',
                'message': 'No se ha iniciado la preparación'
            }
        
        try:
            phase_status = await self.phase_manager.get_phase_status()
            completed_phases = list(self.phase_manager.completed_phases)
            
            # Determinar estado general
            if len(completed_phases) == 0:
                status = 'not_started'
                message = 'No se ha completado ninguna fase'
            elif len(completed_phases) < 4:
                status = 'in_progress'
                message = f'Fase {len(completed_phases)} de 4 completada'
            else:
                status = 'completed'
                message = 'Todas las fases completadas'
            
            return {
                'status': status,
                'message': message,
                'phase_status': phase_status,
                'completed_phases': completed_phases,
                'total_phases': 4,
                'preparation_start_time': self.preparation_start_time.isoformat() if self.preparation_start_time else None,
                'preparation_end_time': self.preparation_end_time.isoformat() if self.preparation_end_time else None
            }
            
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error obteniendo estado: {e}")
            return {
                'status': 'error',
                'message': f'Error obteniendo estado: {str(e)}',
                'error': str(e)
            }
    
    async def is_ready_for_chat(self) -> bool:
        """
        Verifica si el factory está listo para chat
        
        Returns:
            True si está listo, False en caso contrario
        """
        try:
            status = await self.get_preparation_status()
            return status['status'] in ['in_progress', 'completed'] and len(status['completed_phases']) >= 3
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error verificando readiness para chat: {e}")
            return False
    
    async def is_ready_for_orchestrator(self) -> bool:
        """
        Verifica si el factory está listo para orquestador
        
        Returns:
            True si está listo, False en caso contrario
        """
        try:
            status = await self.get_preparation_status()
            return status['status'] == 'completed' and len(status['completed_phases']) == 4
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error verificando readiness para orquestador: {e}")
            return False
    
    async def reset_preparation(self) -> bool:
        """
        Resetea el estado de preparación
        
        Returns:
            True si se reseteó correctamente
        """
        try:
            logger.info(f"[SystemPreparationManager] 🔄 Reseteando preparación")
            
            # Resetear flags del factory
            self.factory._phase_1_core_ready = False
            self.factory._phase_2_ai_ready = False
            self.factory._phase_3_execution_ready = False
            self.factory._phase_4_orchestrator_ready = False
            
            # Resetear phase manager
            if self.phase_manager:
                self.phase_manager.completed_phases.clear()
                self.phase_manager.phase_status.clear()
            
            # Resetear timestamps
            self.preparation_start_time = None
            self.preparation_end_time = None
            
            logger.info(f"[SystemPreparationManager] ✅ Preparación reseteada")
            return True
            
        except Exception as e:
            logger.error(f"[SystemPreparationManager] ❌ Error reseteando preparación: {e}")
            return False
