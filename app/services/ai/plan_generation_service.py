"""
PlanGenerationService - Genera planes largos con múltiples to-dos usando LLM.
Extiende el sistema actual de PlanBuilderService para manejar tareas complejas.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID, uuid4
from enum import Enum

import openai
from pydantic import BaseModel, Field, validator

from app.common.enums import RiskLevel
from app.core.config import settings
from app.services.ai.openai_service import OpenAIService

logger = logging.getLogger(__name__)


class PlanComplexity(str, Enum):
    """Niveles de complejidad de un plan."""
    SIMPLE = "simple"      # 1-2 pasos (usar PlanBuilderService existente)
    MODERATE = "moderate"  # 3-5 pasos (nuevo sistema)
    COMPLEX = "complex"    # 6+ pasos (nuevo sistema)


class PlanTask(BaseModel):
    """Modelo para una tarea atómica dentro de un plan."""
    task_id: str = Field(..., description="Identificador único de la tarea")
    title: str = Field(..., description="Título descriptivo de la tarea")
    description: str = Field(..., description="Descripción detallada de la tarea")
    action_type: str = Field(..., description="Tipo de acción: read, write, analyze, transform, api_call, sql_execution")
    resource_type: str = Field(..., description="Tipo de recurso: database, application, api, both")
    
    # Detalles específicos
    sql_query: Optional[str] = Field(None, description="Consulta SQL si aplica")
    function_call: Optional[str] = Field(None, description="Llamada a función si aplica")
    api_endpoint: Optional[str] = Field(None, description="Endpoint de API si aplica")
    
    # Metadatos
    estimated_effort: int = Field(5, description="Esfuerzo estimado en minutos")
    risk_level: str = Field("low", description="Nivel de riesgo: low, medium, high")
    timeout_seconds: int = Field(60, description="Timeout en segundos")
    dependencies: List[str] = Field(default_factory=list, description="IDs de tareas de las que depende")
    
    @validator('action_type')
    def validate_action_type(cls, v):
        allowed_actions = ['read', 'write', 'analyze', 'transform', 'api_call', 'sql_execution']
        if v not in allowed_actions:
            raise ValueError(f'action_type debe ser uno de: {allowed_actions}')
        return v
    
    @validator('resource_type')
    def validate_resource_type(cls, v):
        allowed_resources = ['database', 'application', 'api', 'both']
        if v not in allowed_resources:
            raise ValueError(f'resource_type debe ser uno de: {allowed_resources}')
        return v
    
    @validator('risk_level')
    def validate_risk_level(cls, v):
        allowed_levels = ['low', 'medium', 'high']
        if v not in allowed_levels:
            raise ValueError(f'risk_level debe ser uno de: {allowed_levels}')
        return v


class GeneratedPlan(BaseModel):
    """Modelo para un plan generado con múltiples to-dos."""
    plan_id: str = Field(default_factory=lambda: str(uuid4()), description="ID único del plan")
    title: str = Field(..., description="Título del plan")
    description: str = Field(..., description="Descripción del objetivo global")
    complexity: PlanComplexity = Field(..., description="Nivel de complejidad del plan")
    
    # Tareas del plan
    tasks: List[PlanTask] = Field(..., description="Lista de tareas atómicas")
    
    # Metadatos
    total_estimated_effort: int = Field(..., description="Esfuerzo total estimado en minutos")
    requires_confirmation: bool = Field(True, description="Si requiere confirmación del usuario")
    fallback_plan: Optional[str] = Field(None, description="Plan alternativo si falla")
    
    # Contexto
    user_resources: Dict[str, Any] = Field(default_factory=dict, description="Recursos disponibles del usuario")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @validator('tasks')
    def validate_tasks(cls, v):
        if len(v) == 0:
            raise ValueError('El plan debe tener al menos 1 tarea')
        if len(v) > 20:
            raise ValueError('El plan no puede tener más de 20 tareas')
        return v


class PlanGenerationService:
    """Servicio para generar planes largos con múltiples to-dos usando LLM."""
    
    def __init__(self, factory=None):
        self.settings = settings
        self.factory = factory
        self.openai_service = OpenAIService(factory) if factory else None
        self._load_prompt_templates()
    
    def _load_prompt_templates(self) -> None:
        """Carga las plantillas de prompt desde archivos."""
        try:
            # Plantilla para planes largos
            prompt_path = Path(__file__).parent / "prompts" / "plan_generation.md"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                self.plan_generation_template = f.read()
            logger.info("[PlanGeneration] ✅ Plantilla de generación cargada")
        except Exception as e:
            logger.error(f"[PlanGeneration] ❌ Error cargando plantilla: {e}")
            self.plan_generation_template = self._get_fallback_template()
    
    def _get_fallback_template(self) -> str:
        """Plantilla de fallback para generación de planes."""
        return """
        Genera un plan detallado con múltiples tareas para lograr el objetivo del usuario.
        
        Contexto:
        - Usuario: {user_id}
        - Objetivo: {user_prompt}
        - Recursos disponibles: {user_resources}
        - Base de datos: {database_info}
        - Aplicaciones: {application_info}
        - APIs disponibles: {api_info}
        
        Reglas:
        - Genera entre 3-10 tareas atómicas
        - Cada tarea debe ser ejecutable independientemente
        - Incluye dependencias entre tareas
        - Estima esfuerzo realista (1-30 minutos por tarea)
        - Prioriza seguridad y validación
        
        Responde solo con JSON válido siguiendo este formato:
        {{
          "plan": {{
            "title": "Título descriptivo del plan",
            "description": "Descripción del objetivo global",
            "complexity": "moderate",
            "tasks": [
              {{
                "task_id": "task_1",
                "title": "Título de la tarea",
                "description": "Descripción detallada",
                "action_type": "read",
                "resource_type": "database",
                "sql_query": "SELECT...",
                "estimated_effort": 5,
                "risk_level": "low",
                "timeout_seconds": 60,
                "dependencies": []
              }}
            ],
            "total_estimated_effort": 30,
            "requires_confirmation": true,
            "fallback_plan": "Plan alternativo simplificado"
          }}
        }}
        """
    
    async def generate_plan(
        self,
        user_prompt: str,
        user_id: UUID,
        context: Dict[str, Any],
        database_info: Optional[Dict[str, Any]] = None,
        application_info: Optional[Dict[str, Any]] = None,
        api_info: Optional[Dict[str, Any]] = None
    ) -> GeneratedPlan:
        """
        Genera un plan detallado con múltiples to-dos.
        
        Args:
            user_prompt: Objetivo o consulta del usuario
            user_id: ID del usuario
            context: Contexto adicional
            database_info: Información de bases de datos disponibles
            application_info: Información de aplicaciones disponibles
            api_info: Información de APIs disponibles
            
        Returns:
            GeneratedPlan: Plan estructurado con múltiples tareas
            
        Raises:
            ValueError: Si el plan generado no es válido
            Exception: Si hay error en la generación
        """
        try:
            logger.info(f"[PlanGeneration] 🚀 Generando plan para: {user_prompt[:100]}...")
            
            # Determinar complejidad del plan
            complexity = self._analyze_plan_complexity(user_prompt, context)
            
            # Preparar recursos del usuario
            user_resources = self._prepare_user_resources(
                database_info, application_info, api_info, context
            )
            
            # Preparar el prompt
            prompt = self._prepare_generation_prompt(
                user_prompt, user_id, user_resources, complexity
            )
            
            # Generar plan con LLM
            plan_json = await self._generate_plan_with_llm(prompt)
            
            # Validar y parsear el plan
            plan = self._validate_and_parse_plan(plan_json, complexity)
            
            # Aplicar guardrails y optimizaciones
            plan = self._apply_plan_guardrails(plan)
            
            logger.info(f"[PlanGeneration] ✅ Plan generado: {plan.title} ({len(plan.tasks)} tareas)")
            return plan
            
        except Exception as e:
            logger.error(f"[PlanGeneration] ❌ Error generando plan: {e}")
            # Retornar plan de fallback
            return self._create_fallback_plan(user_prompt, complexity)
    
    def _analyze_plan_complexity(
        self, 
        user_prompt: str, 
        context: Dict[str, Any]
    ) -> PlanComplexity:
        """Analiza la complejidad del plan basado en el prompt y contexto."""
        prompt_lower = user_prompt.lower()
        
        # Palabras clave que indican complejidad
        complex_keywords = [
            "migrar", "migración", "refactorizar", "refactorización", "reestructurar",
            "implementar", "desarrollar", "crear sistema", "arquitectura", "microservicios",
            "pipeline", "workflow", "proceso completo", "múltiples pasos", "secuencia"
        ]
        
        moderate_keywords = [
            "analizar", "procesar", "transformar", "actualizar", "sincronizar",
            "integrar", "conectar", "configurar", "optimizar", "mejorar"
        ]
        
        # Contar palabras clave
        complex_count = sum(1 for keyword in complex_keywords if keyword in prompt_lower)
        moderate_count = sum(1 for keyword in moderate_keywords if keyword in prompt_lower)
        
        # Determinar complejidad
        if complex_count >= 2 or len(user_prompt) > 200:
            return PlanComplexity.COMPLEX
        elif moderate_count >= 1 or complex_count >= 1:
            return PlanComplexity.MODERATE
        else:
            return PlanComplexity.SIMPLE
    
    def _prepare_user_resources(
        self,
        database_info: Optional[Dict[str, Any]],
        application_info: Optional[Dict[str, Any]],
        api_info: Optional[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepara la información de recursos disponibles del usuario."""
        resources = {
            "databases": database_info or {},
            "applications": application_info or {},
            "apis": api_info or {},
            "context": context
        }
        
        # Agregar información de funciones disponibles si existe
        if 'functions' in context:
            resources['functions'] = context['functions']
        
        return resources
    
    def _prepare_generation_prompt(
        self,
        user_prompt: str,
        user_id: UUID,
        user_resources: Dict[str, Any],
        complexity: PlanComplexity
    ) -> str:
        """Prepara el prompt para la generación del plan."""
        return self.plan_generation_template.format(
            user_id=str(user_id),
            user_prompt=user_prompt,
            user_resources=json.dumps(user_resources, indent=2),
            database_info=json.dumps(user_resources.get('databases', {}), indent=2),
            application_info=json.dumps(user_resources.get('applications', {}), indent=2),
            api_info=json.dumps(user_resources.get('apis', {}), indent=2),
            complexity=complexity.value
        )
    
    async def _generate_plan_with_llm(self, prompt: str) -> str:
        """Genera el plan usando el servicio de LLM."""
        if not self.openai_service:
            raise Exception("OpenAI service no disponible")
        
        try:
            response = await self.openai_service.generate_completion(
                prompt=prompt,
                max_tokens=2000,
                temperature=0.3,  # Menor temperatura para planes más consistentes
                model="gpt-4-1106-preview"
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"[PlanGeneration] ❌ Error en LLM: {e}")
            raise
    
    def _validate_and_parse_plan(
        self, 
        plan_json: str, 
        expected_complexity: PlanComplexity
    ) -> GeneratedPlan:
        """Valida y parsea el plan generado por el LLM."""
        try:
            # Parsear JSON
            plan_data = json.loads(plan_json)
            
            if 'plan' not in plan_data:
                raise ValueError("Formato de respuesta inválido: falta 'plan'")
            
            plan_info = plan_data['plan']
            
            # Validar estructura básica
            required_fields = ['title', 'description', 'tasks']
            for field in required_fields:
                if field not in plan_info:
                    raise ValueError(f"Campo requerido faltante: {field}")
            
            # Parsear tareas
            tasks = []
            for task_data in plan_info['tasks']:
                task = PlanTask(**task_data)
                tasks.append(task)
            
            # Crear plan
            plan = GeneratedPlan(
                title=plan_info['title'],
                description=plan_info['description'],
                complexity=PlanComplexity(plan_info.get('complexity', expected_complexity.value)),
                tasks=tasks,
                total_estimated_effort=plan_info.get('total_estimated_effort', sum(t.estimated_effort for t in tasks)),
                requires_confirmation=plan_info.get('requires_confirmation', True),
                fallback_plan=plan_info.get('fallback_plan'),
                user_resources={}
            )
            
            return plan
            
        except json.JSONDecodeError as e:
            logger.error(f"[PlanGeneration] ❌ Error parseando JSON: {e}")
            raise ValueError(f"JSON inválido: {e}")
        except Exception as e:
            logger.error(f"[PlanGeneration] ❌ Error validando plan: {e}")
            raise
    
    def _apply_plan_guardrails(self, plan: GeneratedPlan) -> GeneratedPlan:
        """Aplica guardrails de seguridad y optimización al plan."""
        # 1. Limitar número máximo de tareas
        if len(plan.tasks) > 15:
            plan.tasks = plan.tasks[:15]
            logger.warning("[PlanGeneration] ⚠️ Plan truncado a 15 tareas máximo")
        
        # 2. Validar dependencias
        task_ids = {task.task_id for task in plan.tasks}
        for task in plan.tasks:
            valid_deps = [dep for dep in task.dependencies if dep in task_ids]
            if len(valid_deps) != len(task.dependencies):
                logger.warning(f"[PlanGeneration] ⚠️ Dependencias inválidas en tarea {task.task_id}")
            task.dependencies = valid_deps
        
        # 3. Ajustar esfuerzo total
        plan.total_estimated_effort = sum(task.estimated_effort for task in plan.tasks)
        
        # 4. Validar timeouts
        for task in plan.tasks:
            if task.timeout_seconds > 300:  # 5 minutos máximo
                task.timeout_seconds = 300
                logger.warning(f"[PlanGeneration] ⚠️ Timeout ajustado para tarea {task.task_id}")
        
        return plan
    
    def _create_fallback_plan(
        self, 
        user_prompt: str, 
        complexity: PlanComplexity
    ) -> GeneratedPlan:
        """Crea un plan de fallback simple."""
        fallback_task = PlanTask(
            task_id="fallback_task_1",
            title="Ejecutar consulta básica",
            description=f"Ejecutar la consulta: {user_prompt}",
            action_type="read",
            resource_type="database",
            estimated_effort=5,
            risk_level="low"
        )
        
        return GeneratedPlan(
            title="Plan de Fallback",
            description=f"Plan simplificado para: {user_prompt}",
            complexity=PlanComplexity.SIMPLE,
            tasks=[fallback_task],
            total_estimated_effort=5,
            requires_confirmation=True,
            fallback_plan="Ejecución directa sin plan"
        )
    
    def should_use_plan_generation(
        self, 
        user_prompt: str, 
        context: Dict[str, Any]
    ) -> Tuple[bool, PlanComplexity]:
        """
        Determina si se debe usar el nuevo sistema de generación de planes.
        
        Returns:
            Tuple[bool, PlanComplexity]: (debe_usar_generacion, complejidad)
        """
        complexity = self._analyze_plan_complexity(user_prompt, context)
        
        # Usar nuevo sistema solo para planes moderados o complejos
        should_use = complexity in [PlanComplexity.MODERATE, PlanComplexity.COMPLEX]
        
        logger.info(f"[PlanGeneration] 🔍 Análisis: complejidad={complexity.value}, usar_generacion={should_use}")
        
        return should_use, complexity
