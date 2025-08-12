"""
Servicio de undo/rollback para la Fase 15 - Hardening.
Maneja la capacidad de deshacer operaciones cuando están disponibles.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.models.executed_strategy_model import ExecutedStrategy
from app.models.function_call_log_model import FunctionCallLog

logger = logging.getLogger(__name__)


class UndoOperation:
    """Representa una operación que puede ser deshecha."""
    
    def __init__(
        self,
        operation_id: str,
        operation_type: str,
        description: str,
        undo_function: Callable,
        undo_args: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation_id = operation_id
        self.operation_type = operation_type
        self.description = description
        self.undo_function = undo_function
        self.undo_args = undo_args
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)
        self.executed = False
    
    def execute_undo(self) -> Dict[str, Any]:
        """Ejecuta la operación de undo."""
        try:
            logger.info(f"🔄 Ejecutando undo para operación {self.operation_id}: {self.description}")
            result = self.undo_function(**self.undo_args)
            self.executed = True
            logger.info(f"✅ Undo ejecutado exitosamente para {self.operation_id}")
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"❌ Error al ejecutar undo para {self.operation_id}: {e}")
            return {"success": False, "error": str(e)}


class UndoService:
    """Servicio para gestionar operaciones de undo/rollback."""
    
    def __init__(self):
        self.undo_operations: Dict[str, UndoOperation] = {}
        self.undo_history: List[UndoOperation] = []
    
    def register_undo_operation(
        self,
        operation_type: str,
        description: str,
        undo_function: Callable,
        undo_args: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Registra una operación que puede ser deshecha.
        
        Args:
            operation_type: Tipo de operación (db_query, api_function, etc.)
            description: Descripción de la operación
            undo_function: Función que ejecuta el undo
            undo_args: Argumentos para la función de undo
            metadata: Metadatos adicionales
            
        Returns:
            ID único de la operación
        """
        operation_id = str(uuid4())
        
        undo_op = UndoOperation(
            operation_id=operation_id,
            operation_type=operation_type,
            description=description,
            undo_function=undo_function,
            undo_args=undo_args,
            metadata=metadata
        )
        
        self.undo_operations[operation_id] = undo_op
        logger.info(f"📝 Registrada operación de undo: {operation_id} - {description}")
        
        return operation_id
    
    def can_undo(self, operation_id: str) -> bool:
        """Verifica si una operación puede ser deshecha."""
        return operation_id in self.undo_operations and not self.undo_operations[operation_id].executed
    
    def get_undo_operations(self, operation_type: Optional[str] = None) -> List[UndoOperation]:
        """Obtiene todas las operaciones de undo disponibles."""
        if operation_type:
            return [op for op in self.undo_operations.values() if op.operation_type == operation_type]
        return list(self.undo_operations.values())
    
    def execute_undo(self, operation_id: str) -> Dict[str, Any]:
        """
        Ejecuta el undo de una operación específica.
        
        Args:
            operation_id: ID de la operación a deshacer
            
        Returns:
            Resultado de la operación de undo
        """
        if operation_id not in self.undo_operations:
            return {"success": False, "error": f"Operación {operation_id} no encontrada"}
        
        undo_op = self.undo_operations[operation_id]
        
        if undo_op.executed:
            return {"success": False, "error": f"Operación {operation_id} ya fue deshecha"}
        
        result = undo_op.execute_undo()
        
        # Mover a historial
        self.undo_history.append(undo_op)
        del self.undo_operations[operation_id]
        
        return result
    
    def execute_undo_all(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Ejecuta undo de todas las operaciones disponibles.
        
        Args:
            operation_type: Tipo de operación específico (opcional)
            
        Returns:
            Resumen de todas las operaciones de undo
        """
        operations = self.get_undo_operations(operation_type)
        
        if not operations:
            return {"success": True, "message": "No hay operaciones para deshacer", "count": 0}
        
        results = []
        success_count = 0
        
        for operation in operations:
            result = self.execute_undo(operation.operation_id)
            results.append({
                "operation_id": operation.operation_id,
                "description": operation.description,
                "result": result
            })
            
            if result.get("success"):
                success_count += 1
        
        return {
            "success": True,
            "total_operations": len(operations),
            "successful_undos": success_count,
            "failed_undos": len(operations) - success_count,
            "results": results
        }
    
    def get_undo_suggestions(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera sugerencias de undo basadas en el contexto actual.
        
        Args:
            context: Contexto de la ejecución actual
            
        Returns:
            Lista de sugerencias de undo
        """
        suggestions = []
        
        # Sugerir undo para operaciones de base de datos
        db_operations = [op for op in self.undo_operations.values() if op.operation_type == "db_query"]
        if db_operations:
            suggestions.append({
                "type": "db_operations",
                "description": f"Deshacer {len(db_operations)} operaciones de base de datos",
                "operations": [op.operation_id for op in db_operations],
                "priority": "high" if any("delete" in op.description.lower() or "update" in op.description.lower() for op in db_operations) else "medium"
            })
        
        # Sugerir undo para funciones de API
        api_operations = [op for op in self.undo_operations.values() if op.operation_type == "api_function"]
        if api_operations:
            suggestions.append({
                "type": "api_operations",
                "description": f"Deshacer {len(api_operations)} llamadas a funciones",
                "operations": [op.operation_id for op in api_operations],
                "priority": "medium"
            })
        
        # Ordenar por prioridad
        priority_order = {"high": 0, "medium": 1, "low": 2}
        suggestions.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        return suggestions
    
    def cleanup_expired_operations(self, max_age_hours: int = 24) -> int:
        """
        Limpia operaciones de undo expiradas.
        
        Args:
            max_age_hours: Edad máxima en horas para mantener operaciones
            
        Returns:
            Número de operaciones limpiadas
        """
        from datetime import timedelta
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        expired_operations = [
            op_id for op_id, op in self.undo_operations.items()
            if op.timestamp < cutoff_time
        ]
        
        for op_id in expired_operations:
            del self.undo_operations[op_id]
        
        if expired_operations:
            logger.info(f"🧹 Limpiadas {len(expired_operations)} operaciones de undo expiradas")
        
        return len(expired_operations)
    
    def export_undo_state(self) -> Dict[str, Any]:
        """Exporta el estado actual del servicio de undo."""
        return {
            "active_operations": len(self.undo_operations),
            "history_count": len(self.undo_history),
            "operation_types": list(set(op.operation_type for op in self.undo_operations.values())),
            "last_cleanup": getattr(self, '_last_cleanup', None)
        }


# Instancia global del servicio
undo_service = UndoService()


# Funciones de undo predefinidas para operaciones comunes
def create_db_undo_operation(
    table_name: str,
    operation: str,
    original_data: Dict[str, Any],
    where_conditions: Dict[str, Any]
) -> Callable:
    """
    Crea una función de undo para operaciones de base de datos.
    
    Args:
        table_name: Nombre de la tabla
        operation: Tipo de operación (INSERT, UPDATE, DELETE)
        original_data: Datos originales antes de la operación
        where_conditions: Condiciones WHERE para identificar registros
        
    Returns:
        Función de undo
    """
    def undo_db_operation(**kwargs) -> Dict[str, Any]:
        # Esta es una implementación simplificada
        # En una implementación real, se ejecutaría SQL real
        logger.info(f"🔄 Undo DB: {operation} en tabla {table_name}")
        
        if operation == "INSERT":
            # Para INSERT, hacer DELETE
            return {"action": "DELETE", "table": table_name, "conditions": where_conditions}
        elif operation == "DELETE":
            # Para DELETE, hacer INSERT
            return {"action": "INSERT", "table": table_name, "data": original_data}
        elif operation == "UPDATE":
            # Para UPDATE, restaurar valores originales
            return {"action": "UPDATE", "table": table_name, "data": original_data, "conditions": where_conditions}
        else:
            raise ValueError(f"Operación de base de datos no soportada: {operation}")
    
    return undo_db_operation


def create_api_function_undo_operation(
    function_name: str,
    original_state: Dict[str, Any],
    undo_endpoint: Optional[str] = None
) -> Callable:
    """
    Crea una función de undo para llamadas a funciones de API.
    
    Args:
        function_name: Nombre de la función
        original_state: Estado original antes de la llamada
        undo_endpoint: Endpoint específico para undo (opcional)
        
    Returns:
        Función de undo
    """
    def undo_api_function(**kwargs) -> Dict[str, Any]:
        logger.info(f"🔄 Undo API: {function_name}")
        
        if undo_endpoint:
            # Llamar endpoint específico de undo
            return {"action": "call_undo_endpoint", "endpoint": undo_endpoint, "data": original_state}
        else:
            # Restaurar estado original
            return {"action": "restore_state", "function": function_name, "state": original_state}
    
    return undo_api_function
