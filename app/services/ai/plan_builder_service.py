"""
PlanBuilderService - Genera planes de ejecución para modo Guided usando LLM.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from uuid import UUID

import openai
from pydantic import BaseModel, Field, validator

from app.common.enums import RiskLevel
from app.core.config import settings
from app.services.ai.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """Modelo para un paso del plan de ejecución."""
    step_id: str = Field(..., description="Identificador único del paso")
    action: str = Field(..., description="Tipo de acción: read, write, analyze, transform")
    description: str = Field(..., description="Descripción clara del paso")
    resource: str = Field(..., description="Recurso a usar: database, application, both")
    sql_query: Optional[str] = Field(None, description="Consulta SQL si aplica")
    function_call: Optional[str] = Field(None, description="Llamada a función si aplica")
    estimated_cost: str = Field(..., description="Costo estimado: low, medium, high")
    risk_level: str = Field(..., description="Nivel de riesgo: low, medium, high")
    timeout_seconds: int = Field(30, description="Timeout en segundos para el paso")
    
    @validator('action')
    def validate_action(cls, v):
        allowed_actions = ['read', 'write', 'analyze', 'transform']
        if v not in allowed_actions:
            raise ValueError(f'action debe ser uno de: {allowed_actions}')
        return v
    
    @validator('resource')
    def validate_resource(cls, v):
        allowed_resources = ['database', 'application', 'both']
        if v not in allowed_resources:
            raise ValueError(f'resource debe ser uno de: {allowed_resources}')
        return v
    
    @validator('estimated_cost', 'risk_level')
    def validate_levels(cls, v):
        allowed_levels = ['low', 'medium', 'high']
        if v not in allowed_levels:
            raise ValueError(f'debe ser uno de: {allowed_levels}')
        return v


class GuidedPlan(BaseModel):
    """Modelo para el plan de ejecución guiado."""
    title: str = Field(..., description="Título descriptivo del plan")
    description: str = Field(..., description="Descripción clara de lo que se va a hacer")
    steps: List[PlanStep] = Field(..., description="Lista de pasos del plan")
    total_estimated_cost: str = Field(..., description="Costo total estimado")
    requires_confirmation: bool = Field(False, description="Si requiere confirmación del usuario")
    fallback_plan: str = Field(..., description="Plan alternativo si algo falla")
    
    @validator('steps')
    def validate_steps(cls, v):
        if len(v) > 2:
            raise ValueError('El plan no puede tener más de 2 pasos')
        if len(v) == 0:
            raise ValueError('El plan debe tener al menos 1 paso')
        return v


class PlanBuilderService:
    """Servicio para generar planes de ejecución guiados usando LLM."""
    
    def __init__(self, factory=None):
        self.settings = settings
        self.factory = factory
        self.openai_service = OpenAIService(factory) if factory else None
        self._load_prompt_template()
    
    def _load_prompt_template(self) -> None:
        """Carga la plantilla de prompt desde el archivo."""
        try:
            prompt_path = Path(__file__).parent / "prompts" / "plan_guided.md"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.prompt_template = f.read()
            logger.info("[PlanBuilder] ✅ Plantilla de prompt cargada")
        except Exception as e:
            logger.error(f"[PlanBuilder] ❌ Error cargando plantilla: {e}")
            # Fallback a plantilla básica
            self.prompt_template = self._get_fallback_template()
    
    def _get_fallback_template(self) -> str:
        """Plantilla de fallback si no se puede cargar el archivo."""
        return """
        Genera un plan de ejecución JSON para la consulta del usuario.
        
        Contexto:
        - Base de Datos: {database_name} ({database_description})
        - Aplicación: {application_name} ({application_description})
        - Consulta: {user_prompt}
        
        Reglas:
        - Máximo 2 pasos
        - Lectura por defecto
        - Seguridad primero
        
        Responde solo con JSON válido siguiendo este formato:
        {{
          "plan": {{
            "title": "Título del plan",
            "description": "Descripción",
            "steps": [
              {{
                "step_id": "step_1",
                "action": "read",
                "description": "Descripción del paso",
                "resource": "database",
                "sql_query": "SELECT...",
                "estimated_cost": "low",
                "risk_level": "low",
                "timeout_seconds": 30
              }}
            ],
            "total_estimated_cost": "low",
            "requires_confirmation": false,
            "fallback_plan": "Plan alternativo"
          }}
        }}
        """
    
    async def build_guided_plan(
        self,
        context: Dict[str, Any],
        database_info: Dict[str, Any],
        application_info: Dict[str, Any],
        user_prompt: str
    ) -> GuidedPlan:
        """
        Construye un plan de ejecución guiado usando LLM.
        
        Args:
            context: Contexto adicional (esquema, funciones, etc.)
            database_info: Información de la base de datos seleccionada
            application_info: Información de la aplicación seleccionada
            user_prompt: Consulta original del usuario
            
        Returns:
            GuidedPlan: Plan estructurado y validado
            
        Raises:
            ValueError: Si el plan generado no es válido
            Exception: Si hay error en la generación
        """
        try:
            logger.info(f"[PlanBuilder] 🚀 Generando plan para: {user_prompt[:100]}...")
            
            # Preparar el prompt con el contexto
            prompt = self._prepare_prompt(
                context, database_info, application_info, user_prompt
            )
            
            # Generar plan con OpenAI
            plan_json = await self._generate_plan_with_llm(prompt)
            
            # Validar y parsear el plan
            plan = self._validate_and_parse_plan(plan_json)
            
            # Aplicar guardrails adicionales
            plan = self._apply_guardrails(plan)
            
            logger.info(f"[PlanBuilder] ✅ Plan generado: {plan.title}")
            return plan
            
        except Exception as e:
            logger.error(f"[PlanBuilder] ❌ Error generando plan: {e}")
            # Retornar plan de fallback
            return self._create_fallback_plan(user_prompt)
    
    def _prepare_prompt(
        self,
        context: Dict[str, Any],
        database_info: Dict[str, Any],
        application_info: Dict[str, Any],
        user_prompt: str
    ) -> str:
        """Prepara el prompt con el contexto específico."""
        # Extraer información relevante
        db_name = database_info.get('resource_name', 'Base de datos')
        db_desc = database_info.get('description', 'Sin descripción')
        app_name = application_info.get('resource_name', 'Aplicación')
        app_desc = application_info.get('description', 'Sin descripción')
        
        # Esquema de BD (limitado para evitar tokens excesivos)
        db_schema = context.get('database_schema', '')
        if len(db_schema) > 1000:
            db_schema = db_schema[:1000] + "... (truncado)"
        
        # Funciones de app
        app_functions = context.get('app_functions', [])
        if isinstance(app_functions, list) and len(app_functions) > 10:
            app_functions = app_functions[:10] + ["... (más funciones disponibles)"]
        
        # Reemplazar placeholders en la plantilla
        prompt = self.prompt_template.format(
            database_name=db_name,
            database_description=db_desc,
            application_name=app_name,
            application_description=app_desc,
            user_prompt=user_prompt,
            database_schema=db_schema,
            app_functions=str(app_functions)
        )
        
        return prompt
    
    async def _generate_plan_with_llm(self, prompt: str) -> str:
        """Genera el plan usando OpenAI."""
        try:
            if not self.openai_service:
                raise ValueError("OpenAIService no disponible")
            
            # Crear un mensaje de chat simple para la llamada
            from app.schemas.chat_schema import ChatMessage
            user_message = ChatMessage(
                role="user",
                content=prompt,
                timestamp=datetime.now()
            )
            
            # Usar el método correcto del OpenAIService
            response = await self.openai_service.chat_completion(
                chat_id=UUID("00000000-0000-0000-0000-000000000000"),  # ID temporal
                system_prompt="Eres un experto en planificación de consultas de base de datos y aplicaciones. Responde SOLO con JSON válido.",
                user_message=user_message
            )
            
            # Extraer el contenido de la respuesta
            content = response.choices[0].message.content.strip()
            
            # Limpiar el contenido (remover markdown si existe)
            if content.startswith('```json'):
                content = content.split('```json')[1]
            if content.endswith('```'):
                content = content[:-3]
            
            content = content.strip()
            logger.info(f"[PlanBuilder] 📝 Respuesta LLM recibida ({len(content)} chars)")
            
            return content
            
        except Exception as e:
            logger.error(f"[PlanBuilder] ❌ Error en LLM: {e}")
            raise Exception(f"Error generando plan con LLM: {e}")
    
    def _validate_and_parse_plan(self, plan_json: str) -> GuidedPlan:
        """Valida y parsea el plan JSON generado."""
        try:
            # Parsear JSON
            plan_data = json.loads(plan_json)
            
            # Extraer la sección del plan
            if 'plan' in plan_data:
                plan_data = plan_data['plan']
            
            # Validar con Pydantic
            plan = GuidedPlan(**plan_data)
            
            logger.info(f"[PlanBuilder] ✅ Plan validado: {len(plan.steps)} pasos")
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"[PlanBuilder] ❌ JSON inválido: {e}")
            raise ValueError(f"Plan JSON inválido: {e}")
        except Exception as e:
            logger.error(f"[PlanBuilder] ❌ Error validando plan: {e}")
            raise ValueError(f"Error validando plan: {e}")
    
    def _apply_guardrails(self, plan: GuidedPlan) -> GuidedPlan:
        """Aplica guardrails adicionales al plan."""
        # Verificar si requiere confirmación basado en el riesgo
        high_risk_steps = [step for step in plan.steps if step.risk_level == 'high']
        write_steps = [step for step in plan.steps if step.action == 'write']
        
        if high_risk_steps or write_steps:
            plan.requires_confirmation = True
            logger.info("[PlanBuilder] ⚠️ Plan marcado para confirmación (riesgo alto o escritura)")
        
        # Aplicar límites de timeout
        for step in plan.steps:
            if step.timeout_seconds > 120:  # Máximo 2 minutos
                step.timeout_seconds = 120
                logger.info(f"[PlanBuilder] ⏰ Timeout ajustado para {step.step_id}")
        
        return plan
    
    def _create_fallback_plan(self, user_prompt: str) -> GuidedPlan:
        """Crea un plan de fallback simple."""
        logger.info("[PlanBuilder] 🆘 Creando plan de fallback")
        
        return GuidedPlan(
            title="Consulta básica de lectura",
            description="Plan de emergencia para consulta simple",
            steps=[
                PlanStep(
                    step_id="step_1",
                    action="read",
                    description="Ejecutar consulta básica de lectura",
                    resource="database",
                    estimated_cost="low",
                    risk_level="low",
                    timeout_seconds=30
                )
            ],
            total_estimated_cost="low",
            requires_confirmation=False,
            fallback_plan="Retornar error con sugerencias de consulta alternativa"
        )
    
    def estimate_token_cost(self, plan: GuidedPlan) -> Dict[str, Any]:
        """Estima el costo en tokens del plan."""
        # Estimación básica basada en la complejidad
        base_tokens = 100
        
        # Tokens por paso
        step_tokens = len(plan.steps) * 50
        
        # Tokens adicionales por complejidad
        complexity_multiplier = 1.0
        if plan.total_estimated_cost == "medium":
            complexity_multiplier = 1.5
        elif plan.total_estimated_cost == "high":
            complexity_multiplier = 2.0
        
        total_tokens = int((base_tokens + step_tokens) * complexity_multiplier)
        
        return {
            "estimated_tokens": total_tokens,
            "complexity": plan.total_estimated_cost,
            "steps_count": len(plan.steps),
            "requires_confirmation": plan.requires_confirmation
        }
