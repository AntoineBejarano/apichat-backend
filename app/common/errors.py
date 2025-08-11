"""
🎯 FASE 11: Errores comunes con remediación automática.

Este módulo define códigos de error estándar, mensajes humanos amigables
y acciones sugeridas para que el usuario siempre sepa qué hacer a continuación.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ErrorSeverity(str, Enum):
    """Niveles de severidad de error."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Categorías de error para agrupación."""
    LLM_TIMEOUT = "llm_timeout"
    CACHE_INCONSISTENT = "cache_inconsistent"
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    DATABASE_ERROR = "database_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    EXECUTION_ERROR = "execution_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RATE_LIMIT = "rate_limit"
    CONFIGURATION_ERROR = "configuration_error"


class SuggestedAction(BaseModel):
    """Acción sugerida para remediar un error."""
    label: str = Field(..., description="Texto visible para el usuario")
    action: str = Field(..., description="Identificador de la acción")
    description: Optional[str] = Field(None, description="Descripción opcional de la acción")
    requires_confirmation: bool = Field(False, description="Si requiere confirmación del usuario")
    priority: int = Field(1, description="Prioridad de la acción (1=alta, 3=baja)")


class UserFacingError(BaseModel):
    """Error amigable para el usuario con acciones de remediación."""
    code: str = Field(..., description="Código único del error")
    category: ErrorCategory = Field(..., description="Categoría del error")
    severity: ErrorSeverity = Field(..., description="Nivel de severidad")
    human_message: str = Field(..., description="Mensaje comprensible para el usuario")
    technical_details: Optional[str] = Field(None, description="Detalles técnicos opcionales")
    suggested_actions: List[SuggestedAction] = Field(..., description="Acciones sugeridas")
    retry_after: Optional[int] = Field(None, description="Segundos antes de reintentar")
    context: Optional[Dict[str, Any]] = Field(None, description="Contexto adicional del error")


class ErrorRegistry:
    """Registro centralizado de errores con remediación automática."""
    
    # Errores de LLM y timeout
    LLM_TIMEOUT = UserFacingError(
        code="LLM_TIMEOUT",
        category=ErrorCategory.LLM_TIMEOUT,
        severity=ErrorSeverity.MEDIUM,
        human_message="La respuesta está tardando más de lo esperado. Esto puede deberse a alta demanda o complejidad de la consulta.",
        suggested_actions=[
            SuggestedAction(
                label="Reintentar",
                action="retry",
                description="Intentar la operación nuevamente",
                priority=1
            ),
            SuggestedAction(
                label="Simplificar consulta",
                action="simplify_query",
                description="Reformular la pregunta de manera más simple",
                priority=2
            ),
            SuggestedAction(
                label="Cambiar a modo rápido",
                action="switch_to_fast_mode",
                description="Usar configuración optimizada para velocidad",
                priority=2
            )
        ],
        retry_after=5
    )
    
    LLM_RATE_LIMIT = UserFacingError(
        code="LLM_RATE_LIMIT",
        category=ErrorCategory.RATE_LIMIT,
        severity=ErrorSeverity.MEDIUM,
        human_message="Has alcanzado el límite de consultas por minuto. Por favor, espera un momento antes de continuar.",
        suggested_actions=[
            SuggestedAction(
                label="Esperar y reintentar",
                action="wait_and_retry",
                description="Esperar 1 minuto y volver a intentar",
                priority=1
            ),
            SuggestedAction(
                label="Verificar uso",
                action="check_usage",
                description="Revisar el consumo actual de tokens y consultas",
                priority=2
            )
        ],
        retry_after=60
    )
    
    # Errores de cache
    CACHE_INCONSISTENT = UserFacingError(
        code="CACHE_INCONSISTENT",
        category=ErrorCategory.CACHE_INCONSISTENT,
        severity=ErrorSeverity.LOW,
        human_message="La información en caché puede estar desactualizada. Se está refrescando automáticamente.",
        suggested_actions=[
            SuggestedAction(
                label="Continuar con datos actualizados",
                action="continue_with_fresh_data",
                description="Proceder con la información más reciente",
                priority=1
            ),
            SuggestedAction(
                label="Verificar cambios recientes",
                action="check_recent_changes",
                description="Revisar qué ha cambiado desde la última actualización",
                priority=2
            )
        ]
    )
    
    CACHE_MISS = UserFacingError(
        code="CACHE_MISS",
        category=ErrorCategory.CACHE_INCONSISTENT,
        severity=ErrorSeverity.LOW,
        human_message="No se encontró información en caché. Se está cargando desde la fuente original.",
        suggested_actions=[
            SuggestedAction(
                label="Esperar carga",
                action="wait_for_load",
                description="Esperar a que se complete la carga de datos",
                priority=1
            ),
            SuggestedAction(
                label="Ver progreso",
                action="show_progress",
                description="Ver el estado actual de la carga",
                priority=2
            )
        ]
    )
    
    # Errores de permisos
    INSUFFICIENT_PERMISSIONS = UserFacingError(
        code="INSUFFICIENT_PERMISSIONS",
        category=ErrorCategory.INSUFFICIENT_PERMISSIONS,
        severity=ErrorSeverity.HIGH,
        human_message="No tienes permisos suficientes para realizar esta operación.",
        suggested_actions=[
            SuggestedAction(
                label="Solicitar permisos",
                action="request_permissions",
                description="Contactar al administrador para solicitar acceso",
                priority=1
            ),
            SuggestedAction(
                label="Ver permisos actuales",
                action="check_current_permissions",
                description="Revisar qué operaciones puedes realizar",
                priority=2
            ),
            SuggestedAction(
                label="Usar modo de solo lectura",
                action="switch_to_readonly",
                description="Cambiar a modo que solo permite consultas",
                priority=2
            )
        ]
    )
    
    # Errores de base de datos
    DATABASE_CONNECTION_ERROR = UserFacingError(
        code="DATABASE_CONNECTION_ERROR",
        category=ErrorCategory.DATABASE_ERROR,
        severity=ErrorSeverity.HIGH,
        human_message="No se pudo conectar con la base de datos. Verificando la conexión...",
        suggested_actions=[
            SuggestedAction(
                label="Reintentar conexión",
                action="retry_connection",
                description="Intentar conectar nuevamente",
                priority=1
            ),
            SuggestedAction(
                label="Verificar estado del servicio",
                action="check_service_status",
                description="Revisar si hay problemas conocidos",
                priority=2
            ),
            SuggestedAction(
                label="Contactar soporte",
                action="contact_support",
                description="Reportar el problema al equipo técnico",
                priority=3
            )
        ],
        retry_after=10
    )
    
    DATABASE_QUERY_TIMEOUT = UserFacingError(
        code="DATABASE_QUERY_TIMEOUT",
        category=ErrorCategory.DATABASE_ERROR,
        severity=ErrorSeverity.MEDIUM,
        human_message="La consulta a la base de datos está tardando más de lo esperado.",
        suggested_actions=[
            SuggestedAction(
                label="Cancelar y simplificar",
                action="cancel_and_simplify",
                description="Cancelar la consulta actual y reformular",
                priority=1
            ),
            SuggestedAction(
                label="Usar modo optimizado",
                action="use_optimized_mode",
                description="Cambiar a configuración de consultas rápidas",
                priority=2
            ),
            SuggestedAction(
                label="Reintentar con timeout mayor",
                action="retry_with_longer_timeout",
                description="Intentar con un límite de tiempo más alto",
                priority=2
            )
        ]
    )
    
    # Errores de validación
    VALIDATION_ERROR = UserFacingError(
        code="VALIDATION_ERROR",
        category=ErrorCategory.VALIDATION_ERROR,
        severity=ErrorSeverity.LOW,
        human_message="La información proporcionada no cumple con el formato esperado.",
        suggested_actions=[
            SuggestedAction(
                label="Revisar formato",
                action="review_format",
                description="Verificar que la entrada cumpla con los requisitos",
                priority=1
            ),
            SuggestedAction(
                label="Ver ejemplos",
                action="show_examples",
                description="Mostrar ejemplos de formato válido",
                priority=2
            ),
            SuggestedAction(
                label="Usar asistente",
                action="use_assistant",
                description="Activar el modo asistido para guiarte",
                priority=2
            )
        ]
    )
    
    # Errores de recursos no encontrados
    RESOURCE_NOT_FOUND = UserFacingError(
        code="RESOURCE_NOT_FOUND",
        category=ErrorCategory.RESOURCE_NOT_FOUND,
        severity=ErrorSeverity.MEDIUM,
        human_message="No se encontró el recurso solicitado. Puede haber sido eliminado o movido.",
        suggested_actions=[
            SuggestedAction(
                label="Buscar alternativas",
                action="search_alternatives",
                description="Buscar recursos similares disponibles",
                priority=1
            ),
            SuggestedAction(
                label="Verificar nombre",
                action="verify_name",
                description="Confirmar el nombre exacto del recurso",
                priority=2
            ),
            SuggestedAction(
                label="Explorar recursos disponibles",
                action="explore_available",
                description="Ver qué recursos están actualmente disponibles",
                priority=2
            )
        ]
    )
    
    # Errores de ejecución
    EXECUTION_ERROR = UserFacingError(
        code="EXECUTION_ERROR",
        category=ErrorCategory.EXECUTION_ERROR,
        severity=ErrorSeverity.MEDIUM,
        human_message="Ocurrió un error durante la ejecución de la operación.",
        suggested_actions=[
            SuggestedAction(
                label="Reintentar operación",
                action="retry_operation",
                description="Intentar ejecutar nuevamente",
                priority=1
            ),
            SuggestedAction(
                label="Verificar configuración",
                action="check_configuration",
                description="Revisar la configuración actual",
                priority=2
            ),
            SuggestedAction(
                label="Usar modo seguro",
                action="use_safe_mode",
                description="Cambiar a configuración más conservadora",
                priority=2
            )
        ]
    )
    
    # Errores de red
    NETWORK_ERROR = UserFacingError(
        code="NETWORK_ERROR",
        category=ErrorCategory.NETWORK_ERROR,
        severity=ErrorSeverity.MEDIUM,
        human_message="Problema de conectividad detectado. Verificando la conexión...",
        suggested_actions=[
            SuggestedAction(
                label="Verificar conexión",
                action="check_connection",
                description="Verificar el estado de la conexión a internet",
                priority=1
            ),
            SuggestedAction(
                label="Reintentar",
                action="retry",
                description="Intentar la operación nuevamente",
                priority=1
            ),
            SuggestedAction(
                label="Usar modo offline",
                action="use_offline_mode",
                description="Cambiar a modo que funciona sin conexión",
                priority=2
            )
        ],
        retry_after=15
    )
    
    # Errores de configuración
    CONFIGURATION_ERROR = UserFacingError(
        code="CONFIGURATION_ERROR",
        category=ErrorCategory.CONFIGURATION_ERROR,
        severity=ErrorSeverity.HIGH,
        human_message="Error en la configuración del sistema. Se requiere intervención del administrador.",
        suggested_actions=[
            SuggestedAction(
                label="Contactar administrador",
                action="contact_admin",
                description="Notificar al administrador del sistema",
                priority=1
            ),
            SuggestedAction(
                label="Verificar configuración",
                action="check_config",
                description="Revisar la configuración actual del sistema",
                priority=2
            ),
            SuggestedAction(
                label="Usar configuración por defecto",
                action="use_default_config",
                description="Aplicar configuración estándar del sistema",
                priority=2
            )
        ]
    )
    
    @classmethod
    def get_error_by_code(cls, code: str) -> Optional[UserFacingError]:
        """Obtiene un error predefinido por su código."""
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, UserFacingError) and attr.code == code:
                return attr
        return None
    
    @classmethod
    def get_errors_by_category(cls, category: ErrorCategory) -> List[UserFacingError]:
        """Obtiene todos los errores de una categoría específica."""
        errors = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, UserFacingError) and attr.category == category:
                errors.append(attr)
        return errors
    
    @classmethod
    def get_errors_by_severity(cls, severity: ErrorSeverity) -> List[UserFacingError]:
        """Obtiene todos los errores de una severidad específica."""
        errors = []
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, UserFacingError) and attr.severity == severity:
                errors.append(attr)
        return errors


# Función helper para crear errores personalizados
def create_custom_error(
    code: str,
    category: ErrorCategory,
    severity: ErrorSeverity,
    human_message: str,
    suggested_actions: List[Dict[str, Any]],
    technical_details: Optional[str] = None,
    retry_after: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> UserFacingError:
    """
    Crea un error personalizado con acciones sugeridas.
    
    Args:
        code: Código único del error
        category: Categoría del error
        severity: Nivel de severidad
        human_message: Mensaje comprensible para el usuario
        suggested_actions: Lista de acciones sugeridas como dicts
        technical_details: Detalles técnicos opcionales
        retry_after: Segundos antes de reintentar
        context: Contexto adicional del error
        
    Returns:
        UserFacingError personalizado
    """
    actions = [
        SuggestedAction(**action) if isinstance(action, dict) else action
        for action in suggested_actions
    ]
    
    return UserFacingError(
        code=code,
        category=category,
        severity=severity,
        human_message=human_message,
        suggested_actions=actions,
        technical_details=technical_details,
        retry_after=retry_after,
        context=context
    )


# Función helper para obtener acciones sugeridas por prioridad
def get_prioritized_actions(error: UserFacingError, max_actions: int = 3) -> List[SuggestedAction]:
    """
    Obtiene las acciones sugeridas ordenadas por prioridad.
    
    Args:
        error: Error del usuario
        max_actions: Máximo número de acciones a retornar
        
    Returns:
        Lista de acciones ordenadas por prioridad
    """
    sorted_actions = sorted(error.suggested_actions, key=lambda x: x.priority)
    return sorted_actions[:max_actions]
