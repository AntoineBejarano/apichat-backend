"""
SchemaValidator - Validador de Esquemas y Contextos
─────────────────────────────────────────────────────
Valida esquemas de base de datos y contextos antes de la ejecución.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Validador de esquemas y contextos para asegurar que la ejecución sea segura.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def validate_compact_schemas(self, compact_schemas: Dict, db_ids: List) -> bool:
        """
        Valida que hay compact_schemas válidos para las DBs solicitadas.
        
        Args:
            compact_schemas: Diccionario de esquemas compactos
            db_ids: Lista de IDs de bases de datos
            
        Returns:
            True si todos los esquemas son válidos, False en caso contrario
        """
        if not compact_schemas or not db_ids:
            return False
        
        for db_id in db_ids:
            # Convertir a str si es UUID para comparación
            db_key = str(db_id) if hasattr(db_id, 'hex') else db_id
            
            # Buscar tanto con UUID como con str
            schema_found = False
            for key in [db_id, db_key, str(db_id)]:
                if key in compact_schemas and compact_schemas[key] and compact_schemas[key].strip():
                    schema_found = True
                    break
            
            if not schema_found:
                self.logger.warning(f"[SchemaValidator] ⚠️ No hay compact_schema válido para DB {db_id}")
                return False
        
        self.logger.info(f"[SchemaValidator] ✅ Compact schemas válidos para {len(db_ids)} DBs")
        return True
    
    def validate_context_for_iteration(self, context_tasks: Dict[str, Any], db_ids: List[UUID], iteration: int) -> bool:
        """
        Valida que el contexto sea válido para la iteración actual.
        
        Args:
            context_tasks: Tareas de contexto cargadas
            db_ids: IDs de bases de datos
            iteration: Número de iteración actual
            
        Returns:
            True si el contexto es válido, False en caso contrario
        """
        if not db_ids:
            return True
        
        compact_schemas = context_tasks.get("compact_schemas", {})
        if not compact_schemas:
            self.logger.warning(f"[SchemaValidator] ⚠️ No hay compact_schemas en iteración {iteration}")
            return False
        
        for db_id in db_ids:
            db_key = str(db_id) if hasattr(db_id, 'hex') else db_id
            
            # Buscar tanto con UUID como con str
            schema_found = False
            for key in [db_id, db_key, str(db_id)]:
                if key in compact_schemas and compact_schemas[key] and compact_schemas[key].strip():
                    schema_found = True
                    break
            
            if not schema_found:
                self.logger.warning(f"[SchemaValidator] ⚠️ No hay compact_schema válido para DB {db_id} en iteración {iteration}")
                return False
        
        self.logger.info(f"[SchemaValidator] ✅ Compact schemas válidos para {len(db_ids)} DBs en iteración {iteration}")
        return True
    
    def validate_database_connection(self, db_ids: List[UUID], context: Dict[str, Any]) -> bool:
        """
        Valida que las conexiones a las bases de datos sean válidas.
        
        Args:
            db_ids: IDs de bases de datos
            context: Contexto cargado
            
        Returns:
            True si las conexiones son válidas, False en caso contrario
        """
        if not db_ids:
            return True
        
        database_schemas = context.get("database_schemas", {})
        if not database_schemas:
            self.logger.warning("[SchemaValidator] ⚠️ No hay database_schemas en el contexto")
            return False
        
        for db_id in db_ids:
            if db_id not in database_schemas:
                self.logger.warning(f"[SchemaValidator] ⚠️ No hay schema para DB {db_id}")
                return False
            
            schema = database_schemas[db_id]
            if not schema or not isinstance(schema, list):
                self.logger.warning(f"[SchemaValidator] ⚠️ Schema inválido para DB {db_id}")
                return False
        
        self.logger.info(f"[SchemaValidator] ✅ Conexiones válidas para {len(db_ids)} DBs")
        return True
    
    def validate_app_integrations(self, app_ids: List[UUID], context: Dict[str, Any]) -> bool:
        """
        Valida que las integraciones de aplicaciones sean válidas.
        
        Args:
            app_ids: IDs de aplicaciones
            context: Contexto cargado
            
        Returns:
            True si las integraciones son válidas, False en caso contrario
        """
        if not app_ids:
            return True
        
        apps = context.get("apps", [])
        if not apps:
            self.logger.warning("[SchemaValidator] ⚠️ No hay apps en el contexto")
            return False
        
        # Verificar que todas las apps solicitadas estén disponibles
        available_app_ids = {str(app.get("id")) for app in apps if app.get("id")}
        requested_app_ids = {str(app_id) for app_id in app_ids}
        
        missing_apps = requested_app_ids - available_app_ids
        if missing_apps:
            self.logger.warning(f"[SchemaValidator] ⚠️ Apps no disponibles: {missing_apps}")
            return False
        
        self.logger.info(f"[SchemaValidator] ✅ Integraciones válidas para {len(app_ids)} apps")
        return True
    
    def validate_context_completeness(self, context: Dict[str, Any], required_keys: List[str]) -> bool:
        """
        Valida que el contexto contenga todas las claves requeridas.
        
        Args:
            context: Contexto a validar
            required_keys: Claves que deben estar presentes
            
        Returns:
            True si el contexto es completo, False en caso contrario
        """
        missing_keys = []
        for key in required_keys:
            if key not in context or context[key] is None:
                missing_keys.append(key)
        
        if missing_keys:
            self.logger.warning(f"[SchemaValidator] ⚠️ Claves faltantes en contexto: {missing_keys}")
            return False
        
        self.logger.info(f"[SchemaValidator] ✅ Contexto completo con {len(required_keys)} claves requeridas")
        return True
    
    def create_validation_error_response(self, error_type: str, details: str = "") -> Dict[str, Any]:
        """
        Crea una respuesta de error de validación estandarizada.
        
        Args:
            error_type: Tipo de error
            details: Detalles adicionales del error
            
        Returns:
            Dict con información del error
        """
        error_messages = {
            "missing_valid_schemas": "❌ Error: No se pudo obtener información de las bases de datos solicitadas. Por favor, verifica la conexión.",
            "missing_valid_schemas_iteration": "❌ Error: No se pudo obtener información de las bases de datos en esta iteración.",
            "invalid_database_connection": "❌ Error: Conexión a la base de datos no válida.",
            "invalid_app_integration": "❌ Error: Integración de aplicación no válida.",
            "incomplete_context": "❌ Error: Contexto incompleto para la ejecución.",
        }
        
        error_message = error_messages.get(error_type, f"❌ Error de validación: {error_type}")
        if details:
            error_message += f" {details}"
        
        return {
            "assistant_response": error_message,
            "error": error_type,
            "validation_failed": True
        }
