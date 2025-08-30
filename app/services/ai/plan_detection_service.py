"""
PlanDetectionService - Servicio para detectar si una consulta requiere un plan corto o largo.
Extiende la lógica existente del sistema para diferenciar entre planes simples y complejos.
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from uuid import UUID
from enum import Enum

from app.services.ai.plan_generation_service import PlanComplexity
from app.services.ai.plan_builder_service import PlanBuilderService

logger = logging.getLogger(__name__)


class PlanType(str, Enum):
    """Tipos de plan disponibles."""
    SIMPLE = "simple"        # 1-2 pasos, usar PlanBuilderService existente
    COMPLEX = "complex"      # 3+ pasos, usar PlanGenerationService nuevo


class PlanDetectionResult:
    """Resultado de la detección de tipo de plan."""
    
    def __init__(
        self,
        plan_type: PlanType,
        complexity: PlanComplexity,
        confidence: float,
        reasoning: str,
        should_use_existing: bool,
        estimated_steps: int
    ):
        self.plan_type = plan_type
        self.complexity = complexity
        self.confidence = confidence
        self.reasoning = reasoning
        self.should_use_existing = should_use_existing
        self.estimated_steps = estimated_steps


class PlanDetectionService:
    """Servicio para detectar el tipo de plan necesario basado en la consulta del usuario."""
    
    def __init__(self, factory=None):
        self.factory = factory
        self.plan_builder_service = PlanBuilderService(factory) if factory else None
    
    def detect_plan_type(
        self,
        user_prompt: str,
        context: Dict[str, Any],
        user_id: UUID,
        database_info: Optional[Dict[str, Any]] = None,
        application_info: Optional[Dict[str, Any]] = None,
        api_info: Optional[Dict[str, Any]] = None
    ) -> PlanDetectionResult:
        """
        Detecta si la consulta requiere un plan simple o complejo.
        
        Args:
            user_prompt: Consulta del usuario
            context: Contexto adicional
            user_id: ID del usuario
            database_info: Información de bases de datos
            application_info: Información de aplicaciones
            api_info: Información de APIs
            
        Returns:
            PlanDetectionResult: Resultado de la detección
        """
        try:
            logger.info(f"[PlanDetection] 🔍 Analizando consulta: {user_prompt[:100]}...")
            
            # 1. Análisis de complejidad básico
            complexity_analysis = self._analyze_complexity(user_prompt, context)
            
            # 2. Análisis de recursos necesarios
            resource_analysis = self._analyze_resources_needed(
                user_prompt, database_info, application_info, api_info
            )
            
            # 3. Análisis de patrones de consulta
            pattern_analysis = self._analyze_query_patterns(user_prompt)
            
            # 4. Análisis de contexto del usuario
            context_analysis = self._analyze_user_context(context, user_id)
            
            # 5. Decisión final
            result = self._make_detection_decision(
                complexity_analysis,
                resource_analysis,
                pattern_analysis,
                context_analysis,
                user_prompt
            )
            
            logger.info(f"[PlanDetection] ✅ Decisión: {result.plan_type.value} (confianza: {result.confidence:.2f})")
            return result
            
        except Exception as e:
            logger.error(f"[PlanDetection] ❌ Error en detección: {e}")
            # Fallback a plan simple
            return PlanDetectionResult(
                plan_type=PlanType.SIMPLE,
                complexity=PlanComplexity.SIMPLE,
                confidence=0.5,
                reasoning="Error en detección, usando plan simple por defecto",
                should_use_existing=True,
                estimated_steps=1
            )
    
    def _analyze_complexity(self, user_prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analiza la complejidad de la consulta."""
        prompt_lower = user_prompt.lower()
        
        # Palabras clave que indican complejidad alta
        high_complexity_keywords = [
            "migrar", "migración", "refactorizar", "refactorización", "reestructurar",
            "implementar", "desarrollar", "crear sistema", "arquitectura", "microservicios",
            "pipeline", "workflow", "proceso completo", "múltiples pasos", "secuencia",
            "automatizar", "orquestar", "coordinación", "integración compleja"
        ]
        
        # Palabras clave que indican complejidad media
        medium_complexity_keywords = [
            "analizar", "procesar", "transformar", "actualizar", "sincronizar",
            "integrar", "conectar", "configurar", "optimizar", "mejorar",
            "consolidar", "agregar", "modificar", "ajustar", "calibrar"
        ]
        
        # Palabras clave que indican complejidad simple
        simple_keywords = [
            "mostrar", "listar", "consultar", "buscar", "encontrar",
            "contar", "sumar", "promedio", "máximo", "mínimo",
            "ver", "revisar", "comprobar", "validar"
        ]
        
        # Contar ocurrencias
        high_count = sum(1 for keyword in high_complexity_keywords if keyword in prompt_lower)
        medium_count = sum(1 for keyword in medium_complexity_keywords if keyword in prompt_lower)
        simple_count = sum(1 for keyword in simple_keywords if keyword in prompt_lower)
        
        # Análisis de longitud y estructura
        word_count = len(user_prompt.split())
        has_multiple_sentences = user_prompt.count('.') > 1
        has_conditional_logic = any(word in prompt_lower for word in ['si', 'cuando', 'mientras', 'después'])
        
        # Determinar complejidad
        if high_count >= 2 or (high_count >= 1 and word_count > 50):
            complexity_score = 0.9
            complexity_level = "high"
        elif medium_count >= 2 or (medium_count >= 1 and word_count > 30):
            complexity_score = 0.7
            complexity_level = "medium"
        elif simple_count >= 1 and word_count < 20:
            complexity_score = 0.3
            complexity_level = "simple"
        else:
            complexity_score = 0.5
            complexity_level = "medium"
        
        return {
            "score": complexity_score,
            "level": complexity_level,
            "high_keywords": high_count,
            "medium_keywords": medium_count,
            "simple_keywords": simple_count,
            "word_count": word_count,
            "has_multiple_sentences": has_multiple_sentences,
            "has_conditional_logic": has_conditional_logic
        }
    
    def _analyze_resources_needed(
        self,
        user_prompt: str,
        database_info: Optional[Dict[str, Any]],
        application_info: Optional[Dict[str, Any]],
        api_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analiza qué recursos necesita la consulta."""
        prompt_lower = user_prompt.lower()
        
        # Detectar tipos de recursos
        needs_database = any(word in prompt_lower for word in [
            "tabla", "tablas", "base de datos", "database", "sql", "consulta", "query",
            "registros", "datos", "información", "select", "insert", "update", "delete"
        ])
        
        needs_application = any(word in prompt_lower for word in [
            "aplicación", "app", "función", "function", "ejecutar", "procesar",
            "algoritmo", "lógica", "cálculo", "transformación"
        ])
        
        needs_api = any(word in prompt_lower for word in [
            "api", "endpoint", "servicio", "service", "llamar", "invocar",
            "conectar", "integrar", "sincronizar", "webhook"
        ])
        
        # Contar recursos disponibles
        db_count = len(database_info) if database_info else 0
        app_count = len(application_info) if application_info else 0
        api_count = len(api_info) if api_info else 0
        
        # Determinar complejidad basada en recursos
        resource_complexity = 0.3  # Base simple
        
        if needs_database and needs_application:
            resource_complexity = 0.8
        elif needs_database and needs_api:
            resource_complexity = 0.7
        elif needs_application and needs_api:
            resource_complexity = 0.7
        elif needs_database or needs_application or needs_api:
            resource_complexity = 0.5
        
        # Penalizar si faltan recursos
        if needs_database and db_count == 0:
            resource_complexity += 0.2
        if needs_application and app_count == 0:
            resource_complexity += 0.2
        if needs_api and api_count == 0:
            resource_complexity += 0.2
        
        return {
            "needs_database": needs_database,
            "needs_application": needs_application,
            "needs_api": needs_api,
            "available_databases": db_count,
            "available_applications": app_count,
            "available_apis": api_count,
            "complexity_score": min(resource_complexity, 1.0),
            "resource_gap": (needs_database and db_count == 0) or (needs_application and app_count == 0) or (needs_api and api_count == 0)
        }
    
    def _analyze_query_patterns(self, user_prompt: str) -> Dict[str, Any]:
        """Analiza patrones específicos en la consulta."""
        prompt_lower = user_prompt.lower()
        
        # Patrones que indican múltiples pasos
        multi_step_patterns = [
            "primero", "después", "luego", "finalmente", "paso", "etapa",
            "1.", "2.", "3.", "primero", "segundo", "tercero",
            "y después", "y luego", "y finalmente"
        ]
        
        # Patrones que indican operaciones secuenciales
        sequential_patterns = [
            "migrar", "transferir", "copiar", "mover", "sincronizar",
            "backup", "respaldo", "restaurar", "rollback"
        ]
        
        # Patrones que indican validación
        validation_patterns = [
            "verificar", "validar", "comprobar", "revisar", "confirmar",
            "asegurar", "garantizar", "chequear"
        ]
        
        # Contar patrones
        multi_step_count = sum(1 for pattern in multi_step_patterns if pattern in prompt_lower)
        sequential_count = sum(1 for pattern in sequential_patterns if pattern in prompt_lower)
        validation_count = sum(1 for pattern in validation_patterns if pattern in prompt_lower)
        
        # Determinar si es un patrón complejo
        is_complex_pattern = (
            multi_step_count >= 2 or
            sequential_count >= 1 or
            validation_count >= 2 or
            (multi_step_count >= 1 and validation_count >= 1)
        )
        
        return {
            "multi_step_count": multi_step_count,
            "sequential_count": sequential_count,
            "validation_count": validation_count,
            "is_complex_pattern": is_complex_pattern,
            "pattern_complexity_score": 0.8 if is_complex_pattern else 0.3
        }
    
    def _analyze_user_context(self, context: Dict[str, Any], user_id: UUID) -> Dict[str, Any]:
        """Analiza el contexto del usuario para influir en la decisión."""
        # Por ahora, análisis básico del contexto
        # En el futuro se puede expandir con historial de planes, preferencias, etc.
        
        context_complexity = 0.5  # Base neutral
        
        # Si hay muchas funciones disponibles, puede indicar complejidad
        if 'functions' in context and len(context['functions']) > 5:
            context_complexity += 0.2
        
        # Si hay múltiples bases de datos, puede indicar complejidad
        if 'databases' in context and len(context['databases']) > 2:
            context_complexity += 0.1
        
        return {
            "complexity_score": min(context_complexity, 1.0),
            "has_many_functions": 'functions' in context and len(context['functions']) > 5,
            "has_multiple_databases": 'databases' in context and len(context['databases']) > 2
        }
    
    def _make_detection_decision(
        self,
        complexity_analysis: Dict[str, Any],
        resource_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
        context_analysis: Dict[str, Any],
        user_prompt: str
    ) -> PlanDetectionResult:
        """Toma la decisión final sobre el tipo de plan."""
        
        # Calcular score combinado
        complexity_score = complexity_analysis["score"]
        resource_score = resource_analysis["complexity_score"]
        pattern_score = pattern_analysis["pattern_complexity_score"]
        context_score = context_analysis["complexity_score"]
        
        # Peso de cada factor
        weights = {
            "complexity": 0.4,
            "resources": 0.3,
            "patterns": 0.2,
            "context": 0.1
        }
        
        combined_score = (
            complexity_score * weights["complexity"] +
            resource_score * weights["resources"] +
            pattern_score * weights["patterns"] +
            context_score * weights["context"]
        )
        
        # Determinar tipo de plan
        if combined_score >= 0.7:
            plan_type = PlanType.COMPLEX
            complexity = PlanComplexity.COMPLEX
            estimated_steps = max(5, int(combined_score * 10))
            should_use_existing = False
        elif combined_score >= 0.5:
            plan_type = PlanType.COMPLEX
            complexity = PlanComplexity.MODERATE
            estimated_steps = max(3, int(combined_score * 6))
            should_use_existing = False
        else:
            plan_type = PlanType.SIMPLE
            complexity = PlanComplexity.SIMPLE
            estimated_steps = max(1, int(combined_score * 3))
            should_use_existing = True
        
        # Generar reasoning
        reasoning_parts = []
        if complexity_analysis["level"] == "high":
            reasoning_parts.append("alta complejidad detectada")
        if resource_analysis["resource_gap"]:
            reasoning_parts.append("recursos limitados")
        if pattern_analysis["is_complex_pattern"]:
            reasoning_parts.append("patrones complejos identificados")
        if context_analysis["has_many_functions"]:
            reasoning_parts.append("muchas funciones disponibles")
        
        reasoning = f"Score combinado: {combined_score:.2f}. " + ", ".join(reasoning_parts) if reasoning_parts else "Análisis estándar"
        
        return PlanDetectionResult(
            plan_type=plan_type,
            complexity=complexity,
            confidence=min(combined_score + 0.2, 1.0),  # Ajustar confianza
            reasoning=reasoning,
            should_use_existing=should_use_existing,
            estimated_steps=estimated_steps
        )
    
    def should_use_existing_plan_builder(
        self,
        user_prompt: str,
        context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        Método de compatibilidad con el sistema existente.
        Determina si usar el PlanBuilderService existente.
        
        Returns:
            Tuple[bool, str]: (usar_existente, razon)
        """
        try:
            # Análisis rápido para compatibilidad
            prompt_lower = user_prompt.lower()
            
            # Palabras clave que definitivamente requieren plan complejo
            complex_keywords = [
                "migrar", "migración", "refactorizar", "implementar", "desarrollar",
                "crear sistema", "arquitectura", "pipeline", "workflow", "automatizar"
            ]
            
            has_complex_keywords = any(keyword in prompt_lower for keyword in complex_keywords)
            
            # Si tiene palabras clave complejas, usar nuevo sistema
            if has_complex_keywords:
                return False, "Palabras clave de complejidad alta detectadas"
            
            # Si es muy largo, usar nuevo sistema
            if len(user_prompt.split()) > 30:
                return False, "Consulta muy larga, requiere plan detallado"
            
            # Si tiene múltiples oraciones, usar nuevo sistema
            if user_prompt.count('.') > 2:
                return False, "Múltiples objetivos detectados"
            
            # Por defecto, usar sistema existente
            return True, "Consulta simple, usar sistema existente"
            
        except Exception as e:
            logger.error(f"[PlanDetection] ❌ Error en compatibilidad: {e}")
            return True, "Error en análisis, usar sistema existente por defecto"
