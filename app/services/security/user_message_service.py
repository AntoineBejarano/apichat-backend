"""
💬 FASE 7: Servicio de Mensajes Estándar para el Usuario
──────────────────────────────────────────────────────────
Implementa mensajes consistentes y claros para:
- Timeline de ingesta del pipeline
- Estados del chat inteligente
- Errores con códigos y hints accionables
- Mensajes de progreso estandarizados
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class MessageType(Enum):
    """Tipos de mensajes para el usuario"""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"


class PipelineStage(Enum):
    """Etapas del pipeline de ingesta"""
    VALIDATE_DB_ACCESS = "validate_db_access"
    EXTRACT_SCHEMA = "extract_schema_snapshot"
    BUILD_GRAPH = "build_graph"
    GENERATE_CHUNKS = "generate_chunks"
    EMBED_CHUNKS = "embed_chunks"
    VECTOR_UPSERT = "vector_upsert"
    FINALIZE = "finalize_snapshot_active"


class ChatStage(Enum):
    """Etapas del chat inteligente"""
    CONTEXT_RESOLUTION = "context_resolution"
    INTENT_ROUTING = "intent_routing"
    GROUNDING = "grounding"
    PLANNING = "planning"
    SQL_GENERATION = "sql_generation"
    SQL_VALIDATION = "sql_validation"
    SQL_EXECUTION = "sql_execution"
    EXPLANATION = "explanation"


@dataclass
class UserMessage:
    """Mensaje estándar para el usuario"""
    type: MessageType
    title: str
    message: str
    details: Optional[str] = None
    hint: Optional[str] = None
    error_code: Optional[str] = None
    progress_pct: Optional[float] = None
    stage: Optional[str] = None
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el mensaje a diccionario"""
        result = {
            "type": self.type.value,
            "title": self.title,
            "message": self.message
        }
        
        if self.details:
            result["details"] = self.details
        if self.hint:
            result["hint"] = self.hint
        if self.error_code:
            result["error_code"] = self.error_code
        if self.progress_pct is not None:
            result["progress_pct"] = self.progress_pct
        if self.stage:
            result["stage"] = self.stage
        if self.timestamp:
            result["timestamp"] = self.timestamp
            
        return result


class UserMessageService:
    """
    💬 Servicio de mensajes estándar para la Fase 7
    
    Implementa:
    - Mensajes consistentes para el pipeline de ingesta
    - Timeline estándar para el chat inteligente
    - Errores con códigos y hints accionables
    - Mensajes de progreso estandarizados
    """
    
    def __init__(self):
        # Mensajes estándar para el pipeline de ingesta
        self.pipeline_messages = {
            PipelineStage.VALIDATE_DB_ACCESS: {
                "title": "🔌 Verificando conexión",
                "message": "Verificando acceso a la base de datos (solo lectura)",
                "success": "✅ Conexión verificada correctamente",
                "error": "❌ Error de conexión a la base de datos"
            },
            PipelineStage.EXTRACT_SCHEMA: {
                "title": "🧩 Extrayendo esquema",
                "message": "Analizando estructura de tablas, columnas y relaciones",
                "success": "✅ Esquema extraído: {table_count} tablas, {relation_count} relaciones",
                "error": "❌ Error extrayendo el esquema de la base de datos"
            },
            PipelineStage.BUILD_GRAPH: {
                "title": "🕸️ Construyendo grafo",
                "message": "Creando grafo de relaciones entre tablas",
                "success": "✅ Grafo construido con {node_count} nodos y {edge_count} aristas",
                "error": "❌ Error construyendo el grafo de relaciones"
            },
            PipelineStage.GENERATE_CHUNKS: {
                "title": "📝 Generando chunks",
                "message": "Creando fragmentos de texto para embeddings",
                "success": "✅ {chunk_count} chunks generados para embeddings",
                "error": "❌ Error generando chunks de texto"
            },
            PipelineStage.EMBED_CHUNKS: {
                "title": "🧠 Generando embeddings",
                "message": "Procesando chunks con modelo de embeddings",
                "success": "✅ Embeddings generados: {processed}/{total} chunks",
                "error": "❌ Error generando embeddings"
            },
            PipelineStage.VECTOR_UPSERT: {
                "title": "📇 Indexando vectorialmente",
                "message": "Almacenando embeddings en el índice vectorial",
                "success": "✅ Índice vectorial listo con {vector_count} vectores",
                "error": "❌ Error almacenando en el índice vectorial"
            },
            PipelineStage.FINALIZE: {
                "title": "🎯 Finalizando snapshot",
                "message": "Activando el nuevo snapshot del esquema",
                "success": "✅ Snapshot activado y listo para consultas",
                "error": "❌ Error activando el snapshot"
            }
        }
        
        # Mensajes estándar para el chat inteligente
        self.chat_messages = {
            ChatStage.CONTEXT_RESOLUTION: {
                "title": "🔍 Resolviendo contexto",
                "message": "Identificando el esquema activo para tu consulta",
                "success": "✅ Contexto resuelto: esquema {snapshot_id}",
                "error": "❌ Error resolviendo el contexto de la consulta"
            },
            ChatStage.INTENT_ROUTING: {
                "title": "🧭 Clasificando intención",
                "message": "Analizando si tu consulta es específica o general",
                "success": "✅ Intención clasificada como {intent_type}",
                "error": "❌ Error clasificando la intención de la consulta"
            },
            ChatStage.GROUNDING: {
                "title": "🔎 Grounding con esquema",
                "message": "Conectando tu consulta con la estructura de la base de datos",
                "success": "✅ Grounding completado con {hit_count} elementos relevantes",
                "error": "❌ Error realizando grounding de la consulta"
            },
            ChatStage.PLANNING: {
                "title": "📋 Planificando consulta",
                "message": "Creando plan de ejecución usando el grafo de relaciones",
                "success": "✅ Plan creado: {table_count} tablas, {join_count} joins",
                "error": "❌ Error planificando la consulta"
            },
            ChatStage.SQL_GENERATION: {
                "title": "⚡ Generando SQL",
                "message": "Creando consulta SQL estricta y segura",
                "success": "✅ SQL generado: {sql_preview}",
                "error": "❌ Error generando la consulta SQL"
            },
            ChatStage.SQL_VALIDATION: {
                "title": "✅ Validando SQL",
                "message": "Verificando que la consulta cumple las políticas de seguridad",
                "success": "✅ SQL validado y asegurado",
                "error": "❌ Error validando la consulta SQL"
            },
            ChatStage.SQL_EXECUTION: {
                "title": "⏱️ Ejecutando consulta",
                "message": "Ejecutando consulta con límites de seguridad",
                "success": "✅ Consulta ejecutada: {row_count} filas en {duration_ms}ms",
                "error": "❌ Error ejecutando la consulta"
            },
            ChatStage.EXPLANATION: {
                "title": "💡 Generando explicación",
                "message": "Creando explicación clara de los resultados",
                "success": "✅ Explicación generada",
                "error": "❌ Error generando la explicación"
            }
        }
        
        # Mensajes de error estándar
        self.error_messages = {
            "SQL_VALIDATION_ERROR": {
                "title": "🚫 Consulta SQL no permitida",
                "message": "Tu consulta no cumple con las políticas de seguridad",
                "hint": "Solo se permiten consultas SELECT. Revisa la sintaxis y asegúrate de no usar operaciones peligrosas."
            },
            "SCHEMA_NOT_ALLOWED": {
                "title": "🚫 Schema no permitido",
                "message": "Estás intentando acceder a un schema no autorizado",
                "hint": "Solo puedes acceder a schemas públicos y de tu aplicación. Verifica los nombres de las tablas."
            },
            "FORBIDDEN_PATTERN_DETECTED": {
                "title": "🚫 Operación no permitida",
                "message": "Se detectó una operación SQL potencialmente peligrosa",
                "hint": "No se permiten operaciones como DROP, DELETE, UPDATE, INSERT, CREATE, ALTER, TRUNCATE, UNION, etc."
            },
            "OPERATION_NOT_ALLOWED": {
                "title": "🚫 Operación no permitida",
                "message": "El tipo de operación solicitada no está permitido",
                "hint": "Solo se permiten consultas SELECT. Si necesitas modificar datos, contacta al administrador."
            },
            "VALIDATION_ERROR": {
                "title": "❌ Error de validación",
                "message": "Los datos proporcionados no son válidos",
                "hint": "Revisa que todos los campos requeridos estén completos y en el formato correcto."
            },
            "SERVICE_UNAVAILABLE": {
                "title": "🔌 Servicio no disponible",
                "message": "El servicio solicitado no está disponible en este momento",
                "hint": "Intenta nuevamente en unos minutos. Si el problema persiste, contacta al soporte."
            },
            "TIMEOUT_ERROR": {
                "title": "⏰ Tiempo de espera agotado",
                "message": "La operación tardó más tiempo del permitido",
                "hint": "Intenta con una consulta más específica o reduce el alcance de los datos solicitados."
            }
        }
    
    def get_pipeline_message(self, stage, status: str = "message", 
                           **kwargs) -> UserMessage:
        """
        📝 Obtiene mensaje estándar para una etapa del pipeline
        
        Args:
            stage: Etapa del pipeline
            status: Estado del mensaje (message, success, error)
            **kwargs: Variables para formatear el mensaje
            
        Returns:
            Mensaje estándar para el usuario
        """
        stage_messages = self.pipeline_messages.get(stage, {})
        message_key = status if status in stage_messages else "message"
        
        title = stage_messages.get(message_key, stage_messages.get("message", ""))
        message = stage_messages.get(message_key, stage_messages.get("message", ""))
        
        # Formatear mensaje con variables
        try:
            message = message.format(**kwargs)
        except KeyError:
            pass  # Si faltan variables, usar el mensaje tal como está
        
        return UserMessage(
            type=MessageType.PROGRESS if status == "message" else 
                  MessageType.SUCCESS if status == "success" else MessageType.ERROR,
            title=title,
            message=message,
            stage=stage.value,
            progress_pct=kwargs.get("progress_pct")
        )
    
    def get_chat_message(self, stage, status: str = "message",
                        **kwargs) -> UserMessage:
        """
        💬 Obtiene mensaje estándar para una etapa del chat
        
        Args:
            stage: Etapa del chat
            status: Estado del mensaje (message, success, error)
            **kwargs: Variables para formatear el mensaje
            
        Returns:
            Mensaje estándar para el usuario
        """
        stage_messages = self.chat_messages.get(stage, {})
        message_key = status if status in stage_messages else "message"
        
        title = stage_messages.get(message_key, stage_messages.get("message", ""))
        message = stage_messages.get(message_key, stage_messages.get("message", ""))
        
        # Formatear mensaje con variables
        try:
            message = message.format(**kwargs)
        except KeyError:
            pass
        
        return UserMessage(
            type=MessageType.PROGRESS if status == "message" else 
                  MessageType.SUCCESS if status == "success" else MessageType.ERROR,
            title=title,
            message=message,
            stage=stage.value
        )
    
    def get_error_message(self, error_code: str, details: str = None,
                         hint: str = None) -> UserMessage:
        """
        ❌ Obtiene mensaje estándar para un error
        
        Args:
            error_code: Código del error
            details: Detalles adicionales del error
            hint: Sugerencia personalizada
            
        Returns:
            Mensaje de error estándar para el usuario
        """
        error_info = self.error_messages.get(error_code, {
            "title": "❌ Error del sistema",
            "message": "Ha ocurrido un error inesperado",
            "hint": "Contacta al soporte técnico si el problema persiste."
        })
        
        return UserMessage(
            type=MessageType.ERROR,
            title=error_info["title"],
            message=error_info["message"],
            details=details,
            hint=hint or error_info.get("hint"),
            error_code=error_code
        )
    
    def get_progress_timeline(self, current_stage, 
                            completed_stages = None,
                            **kwargs) -> List[UserMessage]:
        """
        📊 Genera timeline de progreso del pipeline
        
        Args:
            current_stage: Etapa actual
            completed_stages: Listas de etapas completadas
            **kwargs: Variables para formatear mensajes
            
        Returns:
            Lista de mensajes formando el timeline
        """
        completed_stages = completed_stages or []
        timeline = []
        
        # Añadir etapas completadas
        for stage in completed_stages:
            message = self.get_pipeline_message(stage, "success", **kwargs)
            message.progress_pct = 100
            timeline.append(message)
        
        # Añadir etapa actual
        if current_stage:
            message = self.get_pipeline_message(current_stage, "message", **kwargs)
            message.progress_pct = kwargs.get("progress_pct", 0)
            timeline.append(message)
        
        # Añadir etapas pendientes
        all_stages = list(PipelineStage)
        for stage in all_stages:
            if stage not in completed_stages and stage != current_stage:
                message = self.get_pipeline_message(stage, "message", **kwargs)
                message.progress_pct = 0
                message.message = "⏳ Pendiente"
                timeline.append(message)
        
        return timeline
    
    def get_chat_timeline(self, current_stage,
                         completed_stages = None,
                         **kwargs) -> List[UserMessage]:
        """
        💬 Genera timeline del chat inteligente
        
        Args:
            current_stage: Etapa actual del chat
            completed_stages: Lista de etapas completadas
            **kwargs: Variables para formatear mensajes
            
        Returns:
            Lista de mensajes formando el timeline del chat
        """
        completed_stages = completed_stages or []
        timeline = []
        
        # Añadir etapas completadas
        for stage in completed_stages:
            message = self.get_chat_message(stage, "success", **kwargs)
            timeline.append(message)
        
        # Añadir etapa actual
        if current_stage:
            message = self.get_chat_message(current_stage, "message", **kwargs)
            timeline.append(message)
        
        return timeline
    
    def get_success_summary(self, operation_type: str, **kwargs) -> UserMessage:
        """
        ✅ Genera mensaje de resumen exitoso
        
        Args:
            operation_type: Tipo de operación (pipeline, chat, etc.)
            **kwargs: Variables para formatear el mensaje
            
        Returns:
            Mensaje de resumen exitoso
        """
        if operation_type == "pipeline":
            title = "🎉 Pipeline completado exitosamente"
            message = "El esquema ha sido procesado y está listo para consultas"
        elif operation_type == "chat":
            title = "💬 Consulta procesada exitosamente"
            message = "Tu consulta ha sido ejecutada y los resultados están listos"
        else:
            title = "✅ Operación completada"
            message = "La operación se ha completado exitosamente"
        
        return UserMessage(
            type=MessageType.SUCCESS,
            title=title,
            message=message,
            details=kwargs.get("details"),
            hint=kwargs.get("hint")
        )
    
    def get_retry_message(self, stage: str, error_details: str = None) -> UserMessage:
        """
        🔄 Genera mensaje para reintentos
        
        Args:
            stage: Etapa que falló
            error_details: Detalles del error
            
        Returns:
            Mensaje de reintento para el usuario
        """
        return UserMessage(
            type=MessageType.WARNING,
            title="🔄 Reintentando operación",
            message=f"Reintentando la etapa '{stage}' que falló anteriormente",
            details=error_details,
            hint="Si el problema persiste después de varios intentos, contacta al soporte."
        )
