from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    valid: bool
    message: str
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class SemanticValidator:
    def __init__(self, factory):
        self.factory = factory
    
    async def validate_database_schema(self, db_uuid: str) -> ValidationResult:
        """Valida esquema de base de datos semánticamente"""
        try:
            cache_service = self.factory.get_detailed_schema_cache_service()
            schema = await cache_service.get_schema(db_uuid)
            
            if not schema:
                return ValidationResult(
                    valid=False,
                    errors=["No se pudo obtener el esquema de la base de datos"],
                    message="Esquema de base de datos no disponible"
                )
            
            # Validaciones semánticas
            validation_errors = []
            
            # 1. Verificar que las tablas tienen sentido
            tables = schema.get('tables', [])
            if not tables:
                validation_errors.append("No se detectaron tablas en el esquema")
            
            for table in tables:
                if not table.get('name') or not table.get('columns'):
                    validation_errors.append(f"Tabla {table.get('name', 'unknown')} mal formada")
                
                # Verificar relaciones
                for column in table.get('columns', []):
                    if column.get('foreign_key'):
                        referenced_table = column['foreign_key'].get('table')
                        if referenced_table not in [t['name'] for t in tables]:
                            validation_errors.append(f"Referencia a tabla inexistente: {referenced_table}")
            
            # 2. Verificar que hay al menos una tabla
            if not tables:
                validation_errors.append("No se detectaron tablas en el esquema")
            
            # 3. Verificar que las columnas tienen tipos válidos
            valid_types = ['varchar', 'int', 'timestamp', 'boolean', 'text', 'decimal', 'float', 'date']
            for table in tables:
                for column in table.get('columns', []):
                    if column.get('type') and column['type'].lower() not in valid_types:
                        validation_errors.append(f"Tipo de columna inválido: {column['type']}")
            
            if validation_errors:
                return ValidationResult(
                    valid=False,
                    errors=validation_errors,
                    message="Esquema de base de datos semánticamente inválido"
                )
            
            return ValidationResult(
                valid=True,
                message="Esquema de base de datos válido semánticamente"
            )
            
        except Exception as e:
            logger.error(f"Error validando esquema de base de datos {db_uuid}: {e}")
            return ValidationResult(
                valid=False,
                errors=[str(e)],
                message="Error validando esquema de base de datos"
            )
    
    async def validate_application_functions(self, app_id: str) -> ValidationResult:
        """Valida funciones de aplicación semánticamente"""
        try:
            cache_service = self.factory.get_app_descriptor_cache_service()
            descriptor = await cache_service.get_descriptor(app_id)
            
            if not descriptor:
                return ValidationResult(
                    valid=False,
                    errors=["No se pudo obtener el descriptor de la aplicación"],
                    message="Descriptor de aplicación no disponible"
                )
            
            validation_errors = []
            
            # 1. Verificar que las funciones tienen parámetros válidos
            functions = descriptor.get('functions', [])
            if not functions:
                validation_errors.append("No se detectaron funciones en la aplicación")
            
            for function in functions:
                if not function.get('name'):
                    validation_errors.append("Función sin nombre")
                
                # Verificar tipos de parámetros
                for param in function.get('parameters', []):
                    if not param.get('name') or not param.get('type'):
                        validation_errors.append(f"Parámetro mal formado en función {function.get('name')}")
                
                # Verificar que hay al menos una función
                if not functions:
                    validation_errors.append("No se detectaron funciones en la aplicación")
            
            if validation_errors:
                return ValidationResult(
                    valid=False,
                    errors=validation_errors,
                    message="Aplicación semánticamente inválida"
                )
            
            return ValidationResult(
                valid=True,
                message="Aplicación válida semánticamente"
            )
            
        except Exception as e:
            logger.error(f"Error validando aplicación {app_id}: {e}")
            return ValidationResult(
                valid=False,
                errors=[str(e)],
                message="Error validando aplicación"
            )
    
    async def validate_strategies(self, strategy_id: str) -> ValidationResult:
        """Valida estrategias semánticamente"""
        try:
            strategy_service = self.factory.get_strategy_service()
            strategy = await strategy_service.get_strategy(strategy_id)
            
            if not strategy:
                return ValidationResult(
                    valid=False,
                    errors=["No se pudo obtener la estrategia"],
                    message="Estrategia no disponible"
                )
            
            validation_errors = []
            
            # 1. Verificar que la estrategia tiene un nombre
            if not strategy.get('name'):
                validation_errors.append("Estrategia sin nombre")
            
            # 2. Verificar que tiene pasos definidos
            steps = strategy.get('steps', [])
            if not steps:
                validation_errors.append("Estrategia sin pasos definidos")
            
            # 3. Verificar que cada paso tiene un tipo válido
            valid_step_types = ['query', 'function_call', 'decision', 'loop', 'condition']
            for i, step in enumerate(steps):
                if not step.get('type') or step['type'] not in valid_step_types:
                    validation_errors.append(f"Paso {i+1} tiene tipo inválido: {step.get('type')}")
                
                if not step.get('description'):
                    validation_errors.append(f"Paso {i+1} sin descripción")
            
            if validation_errors:
                return ValidationResult(
                    valid=False,
                    errors=validation_errors,
                    message="Estrategia semánticamente inválida"
                )
            
            return ValidationResult(
                valid=True,
                message="Estrategia válida semánticamente"
            )
            
        except Exception as e:
            logger.error(f"Error validando estrategia {strategy_id}: {e}")
            return ValidationResult(
                valid=False,
                errors=[str(e)],
                message="Error validando estrategia"
            )
