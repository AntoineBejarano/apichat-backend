"""
Sistema de guardrails para funciones.
Añade niveles de riesgo y validaciones de seguridad.
"""

from typing import Dict, List, Optional, Any, Set
from enum import Enum
from pydantic import BaseModel, Field, validator

from app.utils.logger import get_logger

logger = get_logger(__name__)


class FunctionRiskLevel(str, Enum):
    """Niveles de riesgo para funciones."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FunctionCategory(str, Enum):
    """Categorías de funciones."""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    SYSTEM = "system"
    EXTERNAL = "external"
    ADMIN = "admin"


class FunctionPermission(str, Enum):
    """Permisos requeridos para funciones."""
    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class FunctionGuardrail(BaseModel):
    """Configuración de guardrail para una función."""
    function_name: str
    risk_level: FunctionRiskLevel
    category: FunctionCategory
    required_permission: FunctionPermission
    max_execution_time: int = Field(default=30, description="Tiempo máximo en segundos")
    requires_confirmation: bool = False
    allowed_roles: List[str] = Field(default_factory=list)
    blocked_roles: List[str] = Field(default_factory=list)
    rate_limit_per_minute: int = Field(default=100, description="Límite de ejecuciones por minuto")
    input_validation_rules: Dict[str, Any] = Field(default_factory=dict)
    output_validation_rules: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('requires_confirmation')
    def set_confirmation_requirement(cls, v, values):
        """Establece confirmación automática para funciones de alto riesgo."""
        if 'risk_level' in values:
            return values['risk_level'] in [FunctionRiskLevel.HIGH, FunctionRiskLevel.CRITICAL]
        return v


class FunctionGuardrailsService:
    """Servicio para gestionar guardrails de funciones."""
    
    def __init__(self):
        # Configuración por defecto de guardrails
        self.default_guardrails = self._initialize_default_guardrails()
        
        # Cache de guardrails por función
        self._guardrails_cache: Dict[str, FunctionGuardrail] = {}
        
        # Historial de ejecuciones para rate limiting
        self._execution_history: Dict[str, List[float]] = {}
        
        logger.info("🛡️ FunctionGuardrailsService inicializado")
    
    def _initialize_default_guardrails(self) -> Dict[str, FunctionGuardrail]:
        """Inicializa guardrails por defecto para funciones comunes."""
        return {
            # Funciones de lectura - bajo riesgo
            "get_user_profile": FunctionGuardrail(
                function_name="get_user_profile",
                risk_level=FunctionRiskLevel.LOW,
                category=FunctionCategory.READ,
                required_permission=FunctionPermission.READ,
                max_execution_time=5
            ),
            
            "list_users": FunctionGuardrail(
                function_name="list_users",
                risk_level=FunctionRiskLevel.LOW,
                category=FunctionCategory.READ,
                required_permission=FunctionPermission.READ,
                max_execution_time=10,
                rate_limit_per_minute=50
            ),
            
            # Funciones de escritura - riesgo medio
            "update_user_profile": FunctionGuardrail(
                function_name="update_user_profile",
                risk_level=FunctionRiskLevel.MEDIUM,
                category=FunctionCategory.WRITE,
                required_permission=FunctionPermission.WRITE,
                max_execution_time=15,
                requires_confirmation=True,
                rate_limit_per_minute=20
            ),
            
            "create_user": FunctionGuardrail(
                function_name="create_user",
                risk_level=FunctionRiskLevel.MEDIUM,
                category=FunctionCategory.WRITE,
                required_permission=FunctionPermission.ADMIN,
                max_execution_time=20,
                requires_confirmation=True,
                rate_limit_per_minute=10
            ),
            
            # Funciones de eliminación - alto riesgo
            "delete_user": FunctionGuardrail(
                function_name="delete_user",
                risk_level=FunctionRiskLevel.HIGH,
                category=FunctionCategory.DELETE,
                required_permission=FunctionPermission.ADMIN,
                max_execution_time=30,
                requires_confirmation=True,
                rate_limit_per_minute=5,
                allowed_roles=["admin", "super_admin"]
            ),
            
            "purge_data": FunctionGuardrail(
                function_name="purge_data",
                risk_level=FunctionRiskLevel.CRITICAL,
                category=FunctionCategory.SYSTEM,
                required_permission=FunctionPermission.OWNER,
                max_execution_time=60,
                requires_confirmation=True,
                rate_limit_per_minute=1,
                allowed_roles=["super_admin", "owner"]
            ),
            
            # Funciones del sistema - riesgo variable
            "restart_service": FunctionGuardrail(
                function_name="restart_service",
                risk_level=FunctionRiskLevel.HIGH,
                category=FunctionCategory.SYSTEM,
                required_permission=FunctionPermission.ADMIN,
                max_execution_time=120,
                requires_confirmation=True,
                rate_limit_per_minute=2,
                allowed_roles=["admin", "super_admin"]
            ),
            
            # Funciones externas - riesgo medio
            "send_email": FunctionGuardrail(
                function_name="send_email",
                risk_level=FunctionRiskLevel.MEDIUM,
                category=FunctionCategory.EXTERNAL,
                required_permission=FunctionPermission.WRITE,
                max_execution_time=30,
                rate_limit_per_minute=30
            ),
            
            "call_external_api": FunctionGuardrail(
                function_name="call_external_api",
                risk_level=FunctionRiskLevel.MEDIUM,
                category=FunctionCategory.EXTERNAL,
                required_permission=FunctionPermission.WRITE,
                max_execution_time=60,
                rate_limit_per_minute=20
            )
        }
    
    def get_function_guardrail(self, function_name: str) -> Optional[FunctionGuardrail]:
        """Obtiene el guardrail para una función específica."""
        # Verificar cache primero
        if function_name in self._guardrails_cache:
            return self._guardrails_cache[function_name]
        
        # Buscar en configuración por defecto
        if function_name in self.default_guardrails:
            guardrail = self.default_guardrails[function_name]
            self._guardrails_cache[function_name] = guardrail
            return guardrail
        
        # Crear guardrail por defecto basado en el nombre
        default_guardrail = self._create_default_guardrail(function_name)
        self._guardrails_cache[function_name] = default_guardrail
        return default_guardrail
    
    def _create_default_guardrail(self, function_name: str) -> FunctionGuardrail:
        """Crea un guardrail por defecto basado en el nombre de la función."""
        # Inferir categoría y riesgo basado en el nombre
        name_lower = function_name.lower()
        
        if any(word in name_lower for word in ["get", "list", "find", "search", "read"]):
            category = FunctionCategory.READ
            risk_level = FunctionRiskLevel.LOW
            permission = FunctionPermission.READ
        elif any(word in name_lower for word in ["create", "add", "insert", "save"]):
            category = FunctionCategory.WRITE
            risk_level = FunctionRiskLevel.MEDIUM
            permission = FunctionPermission.WRITE
        elif any(word in name_lower for word in ["update", "modify", "change", "edit"]):
            category = FunctionCategory.WRITE
            risk_level = FunctionRiskLevel.MEDIUM
            permission = FunctionPermission.WRITE
        elif any(word in name_lower for word in ["delete", "remove", "purge", "drop"]):
            category = FunctionCategory.DELETE
            risk_level = FunctionRiskLevel.HIGH
            permission = FunctionPermission.ADMIN
        elif any(word in name_lower for word in ["restart", "stop", "start", "kill"]):
            category = FunctionCategory.SYSTEM
            risk_level = FunctionRiskLevel.HIGH
            permission = FunctionPermission.ADMIN
        else:
            category = FunctionCategory.WRITE
            risk_level = FunctionRiskLevel.MEDIUM
            permission = FunctionPermission.WRITE
        
        return FunctionGuardrail(
            function_name=function_name,
            risk_level=risk_level,
            category=category,
            required_permission=permission,
            requires_confirmation=risk_level in [FunctionRiskLevel.HIGH, FunctionRiskLevel.CRITICAL]
        )
    
    def validate_function_execution(
        self,
        function_name: str,
        user_roles: List[str],
        user_permissions: List[str],
        input_data: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, Optional[str], FunctionGuardrail]:
        """
        Valida si una función puede ser ejecutada.
        
        Args:
            function_name: Nombre de la función
            user_roles: Roles del usuario
            user_permissions: Permisos del usuario
            input_data: Datos de entrada para validación adicional
            
        Returns:
            Tuple con (permitido, mensaje_error, guardrail)
        """
        guardrail = self.get_function_guardrail(function_name)
        
        # 1. Verificar permisos básicos
        if not self._check_permissions(guardrail, user_permissions):
            return False, f"Permisos insuficientes para ejecutar {function_name}", guardrail
        
        # 2. Verificar roles permitidos/bloqueados
        if not self._check_roles(guardrail, user_roles):
            return False, f"Rol no permitido para ejecutar {function_name}", guardrail
        
        # 3. Verificar rate limiting
        if not self._check_rate_limit(function_name):
            return False, f"Rate limit excedido para {function_name}", guardrail
        
        # 4. Validar datos de entrada si hay reglas
        if input_data and guardrail.input_validation_rules:
            validation_result = self._validate_input_data(input_data, guardrail.input_validation_rules)
            if not validation_result[0]:
                return False, f"Validación de entrada falló: {validation_result[1]}", guardrail
        
        # 5. Verificar si requiere confirmación
        if guardrail.requires_confirmation:
            logger.info(f"⚠️ Función {function_name} requiere confirmación del usuario")
        
        return True, None, guardrail
    
    def _check_permissions(self, guardrail: FunctionGuardrail, user_permissions: List[str]) -> bool:
        """Verifica si el usuario tiene los permisos necesarios."""
        if guardrail.required_permission == FunctionPermission.NONE:
            return True
        
        required_permission = guardrail.required_permission.value
        
        # Mapeo de jerarquía de permisos
        permission_hierarchy = {
            FunctionPermission.READ.value: ["read", "write", "admin", "owner"],
            FunctionPermission.WRITE.value: ["write", "admin", "owner"],
            FunctionPermission.ADMIN.value: ["admin", "owner"],
            FunctionPermission.OWNER.value: ["owner"]
        }
        
        allowed_permissions = permission_hierarchy.get(required_permission, [])
        return any(perm in user_permissions for perm in allowed_permissions)
    
    def _check_roles(self, guardrail: FunctionGuardrail, user_roles: List[str]) -> bool:
        """Verifica si el usuario tiene roles permitidos."""
        # Si hay roles bloqueados, verificar que el usuario no los tenga
        if guardrail.blocked_roles:
            if any(role in user_roles for role in guardrail.blocked_roles):
                return False
        
        # Si hay roles permitidos específicos, verificar que el usuario los tenga
        if guardrail.allowed_roles:
            return any(role in user_roles for role in guardrail.allowed_roles)
        
        # Si no hay restricciones de roles, permitir
        return True
    
    def _check_rate_limit(self, function_name: str) -> bool:
        """Verifica el rate limiting de la función."""
        guardrail = self.get_function_guardrail(function_name)
        current_time = self._get_current_time()
        
        # Limpiar historial antiguo (más de 1 minuto)
        if function_name in self._execution_history:
            self._execution_history[function_name] = [
                t for t in self._execution_history[function_name]
                if current_time - t < 60
            ]
        else:
            self._execution_history[function_name] = []
        
        # Verificar si se excede el límite
        if len(self._execution_history[function_name]) >= guardrail.rate_limit_per_minute:
            return False
        
        # Registrar ejecución
        self._execution_history[function_name].append(current_time)
        return True
    
    def _validate_input_data(self, input_data: Dict[str, Any], rules: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Valida datos de entrada según las reglas definidas."""
        # Implementación básica de validación
        # En una implementación real, esto podría usar Pydantic o similar
        
        for field, rule in rules.items():
            if field not in input_data:
                if rule.get("required", False):
                    return False, f"Campo requerido '{field}' no encontrado"
                continue
            
            value = input_data[field]
            
            # Validar tipo
            expected_type = rule.get("type")
            if expected_type and not isinstance(value, expected_type):
                return False, f"Campo '{field}' debe ser de tipo {expected_type}"
            
            # Validar longitud para strings
            if isinstance(value, str) and "max_length" in rule:
                if len(value) > rule["max_length"]:
                    return False, f"Campo '{field}' excede longitud máxima de {rule['max_length']}"
            
            # Validar rango para números
            if isinstance(value, (int, float)):
                if "min_value" in rule and value < rule["min_value"]:
                    return False, f"Campo '{field}' debe ser mayor o igual a {rule['min_value']}"
                if "max_value" in rule and value > rule["max_value"]:
                    return False, f"Campo '{field}' debe ser menor o igual a {rule['max_value']}"
        
        return True, None
    
    def _get_current_time(self) -> float:
        """Obtiene el tiempo actual para rate limiting."""
        import time
        return time.time()
    
    def get_functions_by_risk_level(self, risk_level: FunctionRiskLevel) -> List[str]:
        """Obtiene todas las funciones de un nivel de riesgo específico."""
        functions = []
        for guardrail in self.default_guardrails.values():
            if guardrail.risk_level == risk_level:
                functions.append(guardrail.function_name)
        return functions
    
    def get_functions_requiring_confirmation(self) -> List[str]:
        """Obtiene todas las funciones que requieren confirmación."""
        functions = []
        for guardrail in self.default_guardrails.values():
            if guardrail.requires_confirmation:
                functions.append(guardrail.function_name)
        return functions
    
    def add_custom_guardrail(self, guardrail: FunctionGuardrail) -> None:
        """Añade un guardrail personalizado."""
        self.default_guardrails[guardrail.function_name] = guardrail
        self._guardrails_cache[guardrail.function_name] = guardrail
        logger.info(f"🛡️ Guardrail personalizado añadido para {guardrail.function_name}")
    
    def remove_guardrail(self, function_name: str) -> bool:
        """Elimina un guardrail personalizado."""
        if function_name in self.default_guardrails:
            del self.default_guardrails[function_name]
            if function_name in self._guardrails_cache:
                del self._guardrails_cache[function_name]
            logger.info(f"🛡️ Guardrail eliminado para {function_name}")
            return True
        return False
