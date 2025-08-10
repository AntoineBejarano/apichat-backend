"""
PlanStrategyManager - Módulo para manejo de planes y estrategias
────────────────────────────────────────────────────────────────
Responsabilidades:
- Generación de planes
- Validación de planes
- Ejecución de estrategias
- Manejo de resultados de ejecución
"""

import logging
from typing import Dict, List, Optional, Any
from uuid import UUID
from sqlalchemy.orm import Session

from app.schemas.plan_schema import PlanModel
from app.utils.performance_monitor import monitor_performance, performance_context
from app.utils.profiler import profile_function, profile_context

logger = logging.getLogger(__name__)


class PlanStrategyManager:
    """Maneja todas las operaciones relacionadas con planes y estrategias"""
    
    def __init__(self, factory):
        self.factory = factory
        self.db = factory.db
        self.strategy_service = factory.get_strategy_service()
        self.executed_strategy_service = factory.get_executed_strategy_service()
    
    def should_force_plan(
        self, 
        db_ids: Optional[List[UUID]], 
        user_message: str, 
        execution_results: Dict[str, Any]
    ) -> bool:
        """Determina si se debe forzar la generación de un plan"""
        try:
            # Si hay bases de datos específicas, forzar plan
            if db_ids and len(db_ids) > 0:
                return True
            
            # Si el mensaje contiene palabras clave que sugieren consulta de BD
            db_keywords = [
                'query', 'select', 'find', 'search', 'get', 'show', 'list',
                'consulta', 'buscar', 'encontrar', 'mostrar', 'listar',
                'tabla', 'database', 'base de datos', 'registros', 'datos'
            ]
            
            user_message_lower = user_message.lower()
            if any(keyword in user_message_lower for keyword in db_keywords):
                return True
            
            # Si hay resultados de ejecución que sugieren necesidad de plan
            if execution_results and 'needs_plan' in execution_results:
                return execution_results['needs_plan']
            
            return False
            
        except Exception as e:
            logger.error(f"Error determinando si forzar plan: {e}")
            return False
    
    def generate_minimal_plan_for_db_intention(
        self, 
        user_message: str, 
        db_ids: List[UUID]
    ) -> Dict[str, Any]:
        """Genera un plan mínimo para intenciones de base de datos"""
        try:
            plan = {
                'type': 'database_query',
                'description': f'Consulta a {len(db_ids)} base(s) de datos',
                'steps': [
                    {
                        'step': 1,
                        'action': 'analyze_query',
                        'description': 'Analizar la consulta del usuario',
                        'target': 'user_message',
                        'parameters': {'message': user_message}
                    },
                    {
                        'step': 2,
                        'action': 'explore_schemas',
                        'description': 'Explorar esquemas de las bases de datos',
                        'target': 'database_schemas',
                        'parameters': {'db_ids': [str(db_id) for db_id in db_ids]}
                    },
                    {
                        'step': 3,
                        'action': 'generate_sql',
                        'description': 'Generar consulta SQL apropiada',
                        'target': 'sql_query',
                        'parameters': {}
                    },
                    {
                        'step': 4,
                        'action': 'execute_query',
                        'description': 'Ejecutar la consulta',
                        'target': 'query_results',
                        'parameters': {}
                    },
                    {
                        'step': 5,
                        'action': 'format_response',
                        'description': 'Formatear la respuesta',
                        'target': 'final_response',
                        'parameters': {}
                    }
                ],
                'estimated_tokens': 500,
                'priority': 'high'
            }
            
            return plan
            
        except Exception as e:
            logger.error(f"Error generando plan mínimo para BD: {e}")
            return {}
    
    async def execute_strategy(
        self, 
        strategy_id: UUID, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ejecuta una estrategia específica"""
        try:
            # Obtener la estrategia
            strategy = await self.strategy_service.get_strategy(strategy_id)
            if not strategy:
                return {
                    'success': False,
                    'error': 'Strategy not found',
                    'results': {}
                }
            
            # Ejecutar la estrategia
            execution_result = await self._run_strategy_execution(strategy, context)
            
            # Guardar resultado de ejecución
            if execution_result['success']:
                await self._save_execution_result(strategy_id, context, execution_result)
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error ejecutando estrategia {strategy_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': {}
            }
    
    async def _run_strategy_execution(
        self, 
        strategy, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ejecuta la lógica de una estrategia"""
        try:
            # Aquí implementarías la lógica de ejecución de estrategias
            # Por ahora retornamos un resultado simulado
            
            execution_result = {
                'success': True,
                'strategy_id': str(strategy.id),
                'strategy_name': strategy.name,
                'execution_time': 0.5,
                'results': {
                    'message': 'Strategy executed successfully',
                    'context_used': list(context.keys()),
                    'timestamp': '2024-01-01T00:00:00Z'
                }
            }
            
            return execution_result
            
        except Exception as e:
            logger.error(f"Error ejecutando lógica de estrategia: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': {}
            }
    
    async def _save_execution_result(
        self, 
        strategy_id: UUID, 
        context: Dict[str, Any], 
        result: Dict[str, Any]
    ) -> None:
        """Guarda el resultado de una ejecución de estrategia"""
        try:
            # Aquí implementarías la lógica para guardar el resultado
            # usando el servicio de estrategias ejecutadas
            pass
            
        except Exception as e:
            logger.error(f"Error guardando resultado de ejecución: {e}")
    
    def validate_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Valida que un plan sea válido y ejecutable"""
        try:
            validation_errors = []
            
            # Verificar estructura básica
            required_fields = ['type', 'description', 'steps']
            for field in required_fields:
                if field not in plan:
                    validation_errors.append(f"Missing required field: {field}")
            
            # Verificar pasos
            if 'steps' in plan:
                steps = plan['steps']
                if not isinstance(steps, list) or len(steps) == 0:
                    validation_errors.append("Plan must have at least one step")
                else:
                    for i, step in enumerate(steps):
                        step_errors = self._validate_plan_step(step, i + 1)
                        validation_errors.extend(step_errors)
            
            # Verificar tipo
            if 'type' in plan:
                valid_types = ['database_query', 'api_call', 'mcp_tool', 'custom_function']
                if plan['type'] not in valid_types:
                    validation_errors.append(f"Invalid plan type: {plan['type']}")
            
            if validation_errors:
                return {
                    'valid': False,
                    'errors': validation_errors
                }
            
            return {
                'valid': True,
                'errors': []
            }
            
        except Exception as e:
            logger.error(f"Error validando plan: {e}")
            return {
                'valid': False,
                'errors': [f'Validation error: {str(e)}']
            }
    
    def _validate_plan_step(self, step: Dict[str, Any], step_number: int) -> List[str]:
        """Valida un paso individual de un plan"""
        errors = []
        
        # Verificar campos requeridos del paso
        required_step_fields = ['step', 'action', 'description']
        for field in required_step_fields:
            if field not in step:
                errors.append(f"Step {step_number}: Missing required field: {field}")
        
        # Verificar que el número de paso sea correcto
        if 'step' in step and step['step'] != step_number:
            errors.append(f"Step {step_number}: Step number mismatch: expected {step_number}, got {step['step']}")
        
        # Verificar que la acción sea válida
        if 'action' in step:
            valid_actions = [
                'analyze_query', 'explore_schemas', 'generate_sql', 'execute_query',
                'format_response', 'call_api', 'use_mcp_tool', 'call_function'
            ]
            if step['action'] not in valid_actions:
                errors.append(f"Step {step_number}: Invalid action: {step['action']}")
        
        return errors
    
    def optimize_plan_for_tokens(self, plan: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """Optimiza un plan para cumplir con límites de tokens"""
        try:
            if not plan or 'steps' not in plan:
                return plan
            
            # Calcular tokens estimados del plan actual
            current_tokens = plan.get('estimated_tokens', 0)
            
            # Si ya estamos dentro del límite, retornar tal como está
            if current_tokens <= max_tokens:
                return plan
            
            # Si no, optimizar reduciendo pasos
            optimized_plan = plan.copy()
            steps = plan['steps']
            
            # Mantener solo los pasos esenciales
            essential_steps = [1, 2, 4, 5]  # analyze, explore, execute, format
            optimized_steps = []
            
            for step in steps:
                if step.get('step') in essential_steps:
                    optimized_steps.append(step)
            
            optimized_plan['steps'] = optimized_steps
            optimized_plan['estimated_tokens'] = max_tokens
            
            return optimized_plan
            
        except Exception as e:
            logger.error(f"Error optimizando plan para tokens: {e}")
            return plan
    
    def format_plan_for_context(self, plan: Dict[str, Any]) -> str:
        """Formatea un plan para incluir en el contexto"""
        try:
            if not plan or 'steps' not in plan:
                return ""
            
            formatted_lines = [
                f"Plan: {plan.get('description', 'No description')}",
                f"Tipo: {plan.get('type', 'Unknown')}",
                f"Pasos:"
            ]
            
            for step in plan['steps']:
                step_desc = f"  {step.get('step', '?')}. {step.get('description', 'No description')}"
                formatted_lines.append(step_desc)
            
            return "\n".join(formatted_lines)
            
        except Exception as e:
            logger.error(f"Error formateando plan para contexto: {e}")
            return ""
