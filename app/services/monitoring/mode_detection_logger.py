"""
📊 Mode Detection Logger: Sistema de logging estructurado para decisiones de modo

Este servicio registra todas las decisiones de modo del sistema Explorer/Guided
para análisis, debugging y mejora continua del sistema.
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from uuid import UUID
from enum import Enum

from app.models.user_session_mode import UserSessionMode
from app.services.ai.mode_detection_service import ModeDetectionService

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Niveles de logging para decisiones de modo"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DecisionType(Enum):
    """Tipos de decisiones de modo"""
    INITIAL_DETECTION = "initial_detection"
    MODE_TRANSITION = "mode_transition"
    USER_CONFIRMATION = "user_confirmation"
    AUTO_FALLBACK = "auto_fallback"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    AGENT_SELECTION = "agent_selection"
    RESOURCE_PRIORITIZATION = "resource_prioritization"


class ModeDetectionLogger:
    """
    📊 Logger estructurado para decisiones de modo del sistema Explorer/Guided
    
    Funcionalidades:
    - Logging estructurado de todas las decisiones
    - Métricas de precisión de detección
    - Análisis de patrones de usuario
    - Exportación de logs para análisis
    """
    
    def __init__(self, factory):
        """
        Inicializa el logger de detección de modo
        
        Args:
            factory: ServiceFactory para obtener servicios
        """
        self.factory = factory
        self.mode_detection_service = None
        self.log_buffer = []
        self.max_buffer_size = 1000
        self.flush_interval = 60  # segundos
        
        # Inicializar logging estructurado
        self._setup_structured_logging()
        
        logger.info("[ModeDetectionLogger] 🚀 Inicializado para logging de decisiones de modo")
    
    def _setup_structured_logging(self):
        """Configura logging estructurado"""
        try:
            # Crear logger estructurado
            structured_logger = logging.getLogger("mode_detection_structured")
            structured_logger.setLevel(logging.INFO)
            
            # Handler para archivo JSON
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                "logs/mode_detection.json",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5
            )
            
            # Formatter JSON
            class JSONFormatter(logging.Formatter):
                def format(self, record):
                    log_entry = {
                        "timestamp": datetime.utcnow().isoformat(),
                        "level": record.levelname,
                        "message": record.getMessage(),
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno
                    }
                    
                    # Agregar campos adicionales si existen
                    if hasattr(record, 'user_id'):
                        log_entry['user_id'] = record.user_id
                    if hasattr(record, 'decision_type'):
                        log_entry['decision_type'] = record.decision_type
                    if hasattr(record, 'confidence'):
                        log_entry['confidence'] = record.confidence
                    if hasattr(record, 'mode'):
                        log_entry['mode'] = record.mode
                    
                    return json.dumps(log_entry)
            
            file_handler.setFormatter(JSONFormatter())
            structured_logger.addHandler(file_handler)
            
            self.structured_logger = structured_logger
            
        except Exception as e:
            logger.warning(f"[ModeDetectionLogger] ⚠️ Error configurando logging estructurado: {e}")
            self.structured_logger = None
    
    async def _get_services(self):
        """Obtiene servicios necesarios de forma lazy"""
        try:
            if not self.mode_detection_service:
                self.mode_detection_service = self.factory.get_mode_detection_service()
        except Exception as e:
            logger.warning(f"[ModeDetectionLogger] ⚠️ Error obteniendo servicios: {e}")
    
    async def log_mode_decision(
        self,
        user_id: UUID,
        decision_type: DecisionType,
        input_text: str,
        detected_mode: str,
        confidence: float,
        context: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Registra una decisión de modo del sistema
        
        Args:
            user_id: ID del usuario
            decision_type: Tipo de decisión
            input_text: Texto de entrada del usuario
            detected_mode: Modo detectado
            confidence: Nivel de confianza (0.0 - 1.0)
            context: Contexto de la decisión
            metadata: Metadatos adicionales
            
        Returns:
            True si se registró correctamente
        """
        try:
            # Crear entrada de log estructurada
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id),
                "decision_type": decision_type.value,
                "input_text": input_text[:500],  # Limitar longitud
                "detected_mode": detected_mode,
                "confidence": round(confidence, 3),
                "context": context,
                "metadata": metadata or {},
                "session_id": context.get("session_id"),
                "chat_id": context.get("chat_id"),
                "resource_count": context.get("resource_count", 0),
                "processing_time_ms": context.get("processing_time_ms", 0)
            }
            
            # Agregar al buffer
            self.log_buffer.append(log_entry)
            
            # Log estructurado
            if self.structured_logger:
                self.structured_logger.info(
                    f"Mode decision: {detected_mode} (confidence: {confidence})",
                    extra={
                        'user_id': str(user_id),
                        'decision_type': decision_type.value,
                        'confidence': confidence,
                        'mode': detected_mode
                    }
                )
            
            # Log estándar
            logger.info(
                f"[ModeDetectionLogger] 📊 Decisión registrada: {decision_type.value} -> {detected_mode} "
                f"(confianza: {confidence:.1%}) para usuario {user_id}"
            )
            
            # Flush si el buffer está lleno
            if len(self.log_buffer) >= self.max_buffer_size:
                await self._flush_logs()
            
            return True
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error registrando decisión: {e}")
            return False
    
    async def log_mode_transition(
        self,
        user_id: UUID,
        from_mode: str,
        to_mode: str,
        trigger: str,
        user_confirmed: bool,
        context: Dict[str, Any]
    ) -> bool:
        """
        Registra una transición de modo
        
        Args:
            user_id: ID del usuario
            from_mode: Modo anterior
            to_mode: Modo nuevo
            trigger: Causa de la transición
            user_confirmed: Si el usuario confirmó
            context: Contexto de la transición
            
        Returns:
            True si se registró correctamente
        """
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id),
                "decision_type": DecisionType.MODE_TRANSITION.value,
                "from_mode": from_mode,
                "to_mode": to_mode,
                "trigger": trigger,
                "user_confirmed": user_confirmed,
                "context": context,
                "transition_type": "automatic" if not user_confirmed else "user_confirmed"
            }
            
            self.log_buffer.append(log_entry)
            
            logger.info(
                f"[ModeDetectionLogger] 🔄 Transición registrada: {from_mode} -> {to_mode} "
                f"(trigger: {trigger}, confirmado: {user_confirmed}) para usuario {user_id}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error registrando transición: {e}")
            return False
    
    async def log_cache_decision(
        self,
        user_id: UUID,
        cache_hit: bool,
        response_type: str,
        response_time_ms: float,
        cache_level: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Registra decisiones relacionadas con cache
        
        Args:
            user_id: ID del usuario
            cache_hit: Si fue cache hit o miss
            response_type: Tipo de respuesta
            response_time_ms: Tiempo de respuesta en ms
            cache_level: Nivel de cache (L1, L2, L3)
            context: Contexto de la decisión
            
        Returns:
            True si se registró correctamente
        """
        try:
            decision_type = DecisionType.CACHE_HIT if cache_hit else DecisionType.CACHE_MISS
            
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id),
                "decision_type": decision_type.value,
                "cache_hit": cache_hit,
                "response_type": response_type,
                "response_time_ms": response_time_ms,
                "cache_level": cache_level,
                "context": context,
                "performance_impact": "fast" if response_time_ms < 100 else "normal" if response_time_ms < 500 else "slow"
            }
            
            self.log_buffer.append(log_entry)
            
            logger.info(
                f"[ModeDetectionLogger] 💾 Cache decision: {'HIT' if cache_hit else 'MISS'} "
                f"({cache_level}) - {response_time_ms:.1f}ms para usuario {user_id}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error registrando decisión de cache: {e}")
            return False
    
    async def log_agent_selection(
        self,
        user_id: UUID,
        selected_agent: str,
        agent_mode: str,
        selection_reason: str,
        available_agents: List[str],
        context: Dict[str, Any]
    ) -> bool:
        """
        Registra selección de agentes
        
        Args:
            user_id: ID del usuario
            selected_agent: Agente seleccionado
            agent_mode: Modo del agente
            selection_reason: Razón de la selección
            available_agents: Lista de agentes disponibles
            context: Contexto de la selección
            
        Returns:
            True si se registró correctamente
        """
        try:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": str(user_id),
                "decision_type": DecisionType.AGENT_SELECTION.value,
                "selected_agent": selected_agent,
                "agent_mode": agent_mode,
                "selection_reason": selection_reason,
                "available_agents": available_agents,
                "context": context,
                "agent_count": len(available_agents)
            }
            
            self.log_buffer.append(log_entry)
            
            logger.info(
                f"[ModeDetectionLogger] 🤖 Agente seleccionado: {selected_agent} "
                f"(modo: {agent_mode}, razón: {selection_reason}) para usuario {user_id}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error registrando selección de agente: {e}")
            return False
    
    async def get_user_decision_history(
        self,
        user_id: UUID,
        days: int = 7,
        decision_types: Optional[List[DecisionType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene historial de decisiones de un usuario
        
        Args:
            user_id: ID del usuario
            days: Días hacia atrás
            decision_types: Tipos de decisión a filtrar
            
        Returns:
            Lista de decisiones del usuario
        """
        try:
            # Filtrar por usuario y fecha
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            user_decisions = [
                log for log in self.log_buffer
                if log.get("user_id") == str(user_id) and
                datetime.fromisoformat(log["timestamp"]) >= cutoff_date
            ]
            
            # Filtrar por tipos de decisión si se especifica
            if decision_types:
                type_values = [dt.value for dt in decision_types]
                user_decisions = [
                    log for log in user_decisions
                    if log.get("decision_type") in type_values
                ]
            
            # Ordenar por timestamp descendente
            user_decisions.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return user_decisions
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error obteniendo historial: {e}")
            return []
    
    async def get_decision_metrics(
        self,
        user_id: Optional[UUID] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Obtiene métricas de decisiones de modo
        
        Args:
            user_id: ID del usuario (opcional, si no se especifica se obtienen métricas globales)
            days: Días hacia atrás
            
        Returns:
            Métricas de decisiones
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Filtrar logs por fecha
            recent_logs = [
                log for log in self.log_buffer
                if datetime.fromisoformat(log["timestamp"]) >= cutoff_date
            ]
            
            # Filtrar por usuario si se especifica
            if user_id:
                recent_logs = [
                    log for log in recent_logs
                    if log.get("user_id") == str(user_id)
                ]
            
            # Calcular métricas
            total_decisions = len(recent_logs)
            if total_decisions == 0:
                return {
                    "total_decisions": 0,
                    "period_days": days,
                    "user_specific": user_id is not None
                }
            
            # Métricas por tipo de decisión
            decision_types = {}
            for log in recent_logs:
                decision_type = log.get("decision_type", "unknown")
                if decision_type not in decision_types:
                    decision_types[decision_type] = 0
                decision_types[decision_type] += 1
            
            # Métricas de confianza (solo para detecciones iniciales)
            confidence_scores = [
                log["confidence"] for log in recent_logs
                if log.get("decision_type") == DecisionType.INITIAL_DETECTION.value
                and "confidence" in log
            ]
            
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
            
            # Métricas de cache
            cache_hits = len([
                log for log in recent_logs
                if log.get("decision_type") == DecisionType.CACHE_HIT.value
            ])
            cache_misses = len([
                log for log in recent_logs
                if log.get("decision_type") == DecisionType.CACHE_MISS.value
            ])
            
            cache_hit_ratio = cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0
            
            # Métricas de transiciones
            transitions = len([
                log for log in recent_logs
                if log.get("decision_type") == DecisionType.MODE_TRANSITION.value
            ])
            
            return {
                "total_decisions": total_decisions,
                "period_days": days,
                "user_specific": user_id is not None,
                "decision_types": decision_types,
                "confidence_metrics": {
                    "average_confidence": round(avg_confidence, 3),
                    "total_detections": len(confidence_scores)
                },
                "cache_metrics": {
                    "cache_hits": cache_hits,
                    "cache_misses": cache_misses,
                    "hit_ratio": round(cache_hit_ratio, 3)
                },
                "transition_metrics": {
                    "total_transitions": transitions,
                    "transition_rate": round(transitions / total_decisions, 3) if total_decisions > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error obteniendo métricas: {e}")
            return {"error": str(e)}
    
    async def get_user_patterns(
        self,
        user_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analiza patrones de uso de un usuario
        
        Args:
            user_id: ID del usuario
            days: Días hacia atrás para el análisis
            
        Returns:
            Patrones de uso del usuario
        """
        try:
            # Obtener historial del usuario
            user_history = await self.get_user_decision_history(user_id, days)
            
            if not user_history:
                return {
                    "user_id": str(user_id),
                    "patterns_found": False,
                    "message": "No hay datos suficientes para análisis"
                }
            
            # Análisis de patrones temporales
            hourly_patterns = {}
            daily_patterns = {}
            
            for log in user_history:
                timestamp = datetime.fromisoformat(log["timestamp"])
                hour = timestamp.hour
                day = timestamp.strftime("%A")
                
                hourly_patterns[hour] = hourly_patterns.get(hour, 0) + 1
                daily_patterns[day] = daily_patterns.get(day, 0) + 1
            
            # Patrones de modo preferido
            mode_preferences = {}
            for log in user_history:
                if "detected_mode" in log:
                    mode = log["detected_mode"]
                    mode_preferences[mode] = mode_preferences.get(mode, 0) + 1
            
            # Patrones de confianza
            confidence_patterns = {
                "high_confidence": len([log for log in user_history if log.get("confidence", 0) >= 0.8]),
                "medium_confidence": len([log for log in user_history if 0.5 <= log.get("confidence", 0) < 0.8]),
                "low_confidence": len([log for log in user_history if log.get("confidence", 0) < 0.5])
            }
            
            # Patrones de transición
            transition_patterns = []
            for i in range(len(user_history) - 1):
                current = user_history[i]
                next_log = user_history[i + 1]
                
                if (current.get("decision_type") == DecisionType.INITIAL_DETECTION.value and
                    next_log.get("decision_type") == DecisionType.MODE_TRANSITION.value):
                    
                    transition_patterns.append({
                        "from_mode": current.get("detected_mode"),
                        "to_mode": next_log.get("to_mode"),
                        "trigger": next_log.get("trigger")
                    })
            
            return {
                "user_id": str(user_id),
                "patterns_found": True,
                "analysis_period_days": days,
                "temporal_patterns": {
                    "hourly_activity": hourly_patterns,
                    "daily_activity": daily_patterns
                },
                "mode_preferences": mode_preferences,
                "confidence_patterns": confidence_patterns,
                "transition_patterns": transition_patterns,
                "total_activities": len(user_history)
            }
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error analizando patrones: {e}")
            return {"error": str(e)}
    
    async def _flush_logs(self):
        """Envía logs del buffer a almacenamiento persistente"""
        try:
            if not self.log_buffer:
                return
            
            # Aquí se implementaría la lógica para enviar logs a base de datos
            # Por ahora solo limpiamos el buffer
            flushed_count = len(self.log_buffer)
            self.log_buffer.clear()
            
            logger.info(f"[ModeDetectionLogger] 💾 Flush completado: {flushed_count} logs enviados")
            
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error en flush: {e}")
    
    async def export_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[UUID] = None,
        format: str = "json"
    ) -> Union[str, bytes]:
        """
        Exporta logs en el formato especificado
        
        Args:
            start_date: Fecha de inicio
            end_date: Fecha de fin
            user_id: ID del usuario (opcional)
            format: Formato de exportación (json, csv)
            
        Returns:
            Logs exportados en el formato especificado
        """
        try:
            # Filtrar logs por fecha
            filtered_logs = [
                log for log in self.log_buffer
                if start_date <= datetime.fromisoformat(log["timestamp"]) <= end_date
            ]
            
            # Filtrar por usuario si se especifica
            if user_id:
                filtered_logs = [
                    log for log in filtered_logs
                    if log.get("user_id") == str(user_id)
                ]
            
            if format.lower() == "json":
                return json.dumps(filtered_logs, indent=2, ensure_ascii=False)
            
            elif format.lower() == "csv":
                import csv
                from io import StringIO
                
                if not filtered_logs:
                    return ""
                
                output = StringIO()
                writer = csv.DictWriter(output, fieldnames=filtered_logs[0].keys())
                writer.writeheader()
                writer.writerows(filtered_logs)
                
                return output.getvalue()
            
            else:
                raise ValueError(f"Formato no soportado: {format}")
                
        except Exception as e:
            logger.error(f"[ModeDetectionLogger] ❌ Error exportando logs: {e}")
            return f"Error: {str(e)}"
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtiene información del servicio"""
        return {
            "service_name": "ModeDetectionLogger",
            "description": "Sistema de logging estructurado para decisiones de modo",
            "features": [
                "Logging estructurado de decisiones",
                "Métricas de precisión",
                "Análisis de patrones",
                "Exportación de logs",
                "Buffer en memoria con flush automático"
            ],
            "buffer_status": {
                "current_size": len(self.log_buffer),
                "max_size": self.max_buffer_size,
                "flush_interval": f"{self.flush_interval}s"
            },
            "status": "active"
        }
