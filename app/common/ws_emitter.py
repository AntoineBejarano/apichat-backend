# app/common/ws_emitter.py
"""
Servicio base para emitir eventos WebSocket de forma consistente.
"""
import json
import logging
from typing import Any, Dict, Optional, Union
from fastapi import WebSocket
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from .events import (
    BaseWsEvent, StatusTypingEvent, StatusProgressEvent, DecisionRequestEvent,
    DecisionResponseEvent, ResourceProposalEvent, ResourceProposalResponseEvent,
    ResultPartialEvent, ResultFinalEvent, NoticeInfoEvent, ErrorUserFacingEvent,
    TelemetrySnapshotEvent
)
from .enums import Mode

logger = logging.getLogger(__name__)


class WebSocketEmitter:
    """
    Emisor de eventos WebSocket con métodos helper para cada tipo de evento.
    """
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.session_id: Optional[str] = None
    
    async def emit(self, event: BaseWsEvent) -> bool:
        """
        Emite un evento WebSocket.
        
        Args:
            event: Evento a emitir
            
        Returns:
            True si se emitió correctamente, False en caso contrario
        """
        try:
            if self.session_id:
                event.session_id = self.session_id
            
            # Convertir datetime a string antes de serializar
            event_data = event.model_dump()
            event_data = self._convert_datetime_to_iso(event_data)
            
            await self.websocket.send_json(event_data)
            logger.debug(f"✅ Evento WS emitido: {event.type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error emitiendo evento WS {event.type}: {str(e)}")
            return False
    
    def _convert_datetime_to_iso(self, data: Any) -> Any:
        """
        Convierte recursivamente todos los objetos datetime a string ISO.
        """
        if isinstance(data, dict):
            return {key: self._convert_datetime_to_iso(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._convert_datetime_to_iso(item) for item in data]
        elif hasattr(data, 'isoformat'):  # datetime objects
            return data.isoformat()
        else:
            return data
    
    async def emit_status_typing(self, is_typing: bool = True) -> bool:
        """Emite evento de estado de escritura."""
        event = StatusTypingEvent(is_typing=is_typing)
        return await self.emit(event)
    
    async def emit_status_progress(
        self, 
        step: int, 
        total_steps: int, 
        message: str, 
        percentage: Optional[float] = None
    ) -> bool:
        """Emite evento de progreso."""
        event = StatusProgressEvent(
            step=step,
            total_steps=total_steps,
            message=message,
            percentage=percentage
        )
        return await self.emit(event)
    
    async def emit_decision_request(
        self,
        decision_id: str,
        title: str,
        description: str,
        options: list,
        timeout_seconds: int = 30,
        default_action: str = "cancel"
    ) -> bool:
        """Emite solicitud de decisión."""
        event = DecisionRequestEvent(
            decision_id=decision_id,
            title=title,
            description=description,
            options=options,
            timeout_seconds=timeout_seconds,
            default_action=default_action
        )
        return await self.emit(event)
    
    async def emit_decision_response(
        self,
        decision_id: str,
        action: str,
        user_message: Optional[str] = None,
        selected_options: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emite respuesta de decisión."""
        event = DecisionResponseEvent(
            decision_id=decision_id,
            action=action,
            user_message=user_message,
            selected_options=selected_options
        )
        return await self.emit(event)
    
    async def emit_resource_proposal(
        self,
        proposal_id: str,
        title: str,
        description: str,
        options: list,
        user_message: str,
        timeout_seconds: int = 60,
        default_action: str = "explore_only"
    ) -> bool:
        """Emite propuesta de recursos para modo Explorer."""
        event = ResourceProposalEvent(
            proposal_id=proposal_id,
            title=title,
            description=description,
            options=options,
            user_message=user_message,
            timeout_seconds=timeout_seconds,
            default_action=default_action
        )
        return await self.emit(event)
    
    async def emit_resource_proposal_response(
        self,
        proposal_id: str,
        action: str,
        selected_option: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ) -> bool:
        """Emite respuesta a propuesta de recursos."""
        event = ResourceProposalResponseEvent(
            proposal_id=proposal_id,
            action=action,
            selected_option=selected_option,
            user_message=user_message
        )
        return await self.emit(event)
    
    async def emit_result_partial(
        self,
        step: int,
        data: Dict[str, Any],
        preview: Optional[str] = None
    ) -> bool:
        """Emite resultado parcial."""
        event = ResultPartialEvent(
            step=step,
            data=data,
            preview=preview
        )
        return await self.emit(event)
    
    async def emit_result_final(
        self,
        summary: str,
        data: Dict[str, Any],
        next_actions: list,
        usage_stats: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Emite resultado final."""
        event = ResultFinalEvent(
            summary=summary,
            data=data,
            next_actions=next_actions,
            usage_stats=usage_stats
        )
        return await self.emit(event)
    
    async def emit_notice_info(
        self,
        message: str,
        level: str = "info",
        actions: Optional[list] = None
    ) -> bool:
        """Emite notificación informativa."""
        event = NoticeInfoEvent(
            message=message,
            level=level,
            actions=actions
        )
        return await self.emit(event)
    
    async def emit_error_user_facing(
        self,
        code: str,
        human_message: str,
        suggested_actions: list,
        technical_details: Optional[str] = None
    ) -> bool:
        """Emite error para el usuario."""
        event = ErrorUserFacingEvent(
            code=code,
            human_message=human_message,
            suggested_actions=suggested_actions,
            technical_details=technical_details
        )
        return await self.emit(event)
    
    async def emit_telemetry_snapshot(
        self,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        cache_hit_ratio: float,
        steps_executed: int,
        confirmations_required: int,
        mode: Mode
    ) -> bool:
        """Emite snapshot de telemetría."""
        event = TelemetrySnapshotEvent(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cache_hit_ratio=cache_hit_ratio,
            steps_executed=steps_executed,
            confirmations_required=confirmations_required,
            mode=mode
        )
        return await self.emit(event)


class WSEmitter:
    """
    Emisor de eventos WebSocket para usuarios específicos.
    Esta clase se usa cuando no se tiene acceso directo al WebSocket del usuario.
    """
    
    def __init__(self):
        # TODO: Implementar lógica para obtener WebSocket del usuario
        # Por ahora, solo logueamos el evento
        pass
    
    def emit_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """
        Emite un evento a un usuario específico.
        
        Args:
            user_id: ID del usuario
            event_type: Tipo de evento
            data: Datos del evento
            
        Returns:
            True si se emitió correctamente, False en caso contrario
        """
        try:
            # TODO: Implementar lógica real de emisión
            # Por ahora, solo logueamos el evento
            logger.info(f"[WSEmitter] 📡 Evento {event_type} emitido a usuario {user_id}: {data}")
            return True
            
        except Exception as e:
            logger.error(f"[WSEmitter] ❌ Error emitiendo evento {event_type} a usuario {user_id}: {str(e)}")
            return False
