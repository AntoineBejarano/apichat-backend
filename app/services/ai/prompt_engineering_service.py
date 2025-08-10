# app/services/prompt_engineering_service.py
"""
PromptEngineeringService - Nivel Unicornio 🦄
─────────────────────────────────────────────
Servicio de prompt engineering avanzado para optimizar la comunicación con el AI.
Combina contexto semántico, embeddings y optimización dinámica de prompts.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from dataclasses import dataclass
from datetime import datetime
import json

logger = logging.getLogger(__name__)


@dataclass
class OptimizedPrompt:
    """Prompt optimizado con contexto semántico"""
    system_prompt: str
    user_prompt: str
    context_schema: Dict[str, Any]
    semantic_hints: List[str]
    confidence_score: float
    optimization_notes: List[str]


@dataclass
class QueryAnalysis:
    """Análisis detallado de una query del usuario"""
    intent: str
    entities: List[str]
    actions: List[str]
    constraints: List[str]
    semantic_focus: str
    complexity_level: str


class PromptEngineeringService:
    """
    Servicio de prompt engineering avanzado para optimizar la comunicación con el AI.
    """
    
    def __init__(self):
        self.prompt_templates = self._load_prompt_templates()
        self.optimization_rules = self._load_optimization_rules()
        self.context_cache = {}
        self.prompt_stats = {
            "total_optimizations": 0,
            "avg_confidence_score": 0.0,
            "successful_queries": 0,
            "failed_queries": 0
        }
        
        logger.info("[PromptEngineeringService] 🦄 Inicializado con templates avanzados")
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Cargar templates de prompts optimizados"""
        return {
            "database_query": """
Eres un experto analista de bases de datos con acceso a un esquema detallado.
Tu tarea es generar consultas SQL precisas y eficientes basándote en la información del esquema.

CONTEXTO DEL ESQUEMA:
{schema_context}

ANÁLISIS SEMÁNTICO:
{semantic_analysis}

REGLAS IMPORTANTES:
1. SIEMPRE verifica que las columnas y tablas existen antes de usarlas
2. Usa los tipos de datos correctos para las comparaciones
3. Considera las relaciones entre tablas para JOINs
4. Optimiza las consultas para rendimiento
5. Maneja casos edge y valores NULL apropiadamente

QUERY DEL USUARIO: {user_query}

Genera una consulta SQL que:
- Sea sintácticamente correcta
- Use solo columnas y tablas que existen
- Sea eficiente y legible
- Incluya comentarios explicativos
""",
            
            "schema_exploration": """
Eres un experto en exploración de esquemas de bases de datos.
Analiza el esquema proporcionado y responde preguntas sobre su estructura.

ESQUEMA DETALLADO:
{schema_context}

ANÁLISIS SEMÁNTICO:
{semantic_analysis}

PREGUNTA: {user_query}

Proporciona una respuesta detallada que incluya:
- Tablas relevantes y sus propósitos
- Columnas importantes y sus tipos
- Relaciones entre tablas
- Ejemplos de uso
""",
            
            "data_analysis": """
Eres un experto analista de datos con acceso a una base de datos.
Tu objetivo es proporcionar insights valiosos basados en los datos disponibles.

CONTEXTO DE DATOS:
{schema_context}

ANÁLISIS SEMÁNTICO:
{semantic_analysis}

SOLICITUD: {user_query}

Genera un análisis que incluya:
- Consultas SQL relevantes
- Interpretación de resultados
- Insights y recomendaciones
- Visualizaciones sugeridas
"""
        }
    
    def _load_optimization_rules(self) -> Dict[str, Any]:
        """Cargar reglas de optimización de prompts"""
        return {
            "intent_detection": {
                "query": ["select", "find", "show", "get", "count", "list"],
                "analysis": ["analyze", "explain", "describe", "understand"],
                "modification": ["insert", "update", "delete", "create", "modify"]
            },
            "complexity_boost": {
                "simple": 1.0,
                "medium": 1.2,
                "complex": 1.5
            },
            "semantic_focus": {
                "location": ["address", "city", "country", "madrid", "barcelona"],
                "name": ["name", "title", "valhalla", "club"],
                "time": ["date", "created", "updated", "timestamp"],
                "quantity": ["count", "number", "amount", "total"]
            }
        }
    
    def optimize_prompt_for_query(
        self, 
        user_query: str, 
        schema_context: Dict[str, Any],
        search_results: List[Any] = None
    ) -> OptimizedPrompt:
        """
        Optimizar prompt para una query específica.
        
        Args:
            user_query: Query del usuario
            schema_context: Contexto del esquema
            search_results: Resultados de búsqueda vectorial
            
        Returns:
            Prompt optimizado con contexto semántico
        """
        start_time = datetime.now()
        
        try:
            # Analizar la query del usuario
            query_analysis = self._analyze_user_query(user_query)
            
            # Determinar el tipo de prompt más apropiado
            prompt_type = self._determine_prompt_type(query_analysis)
            
            # Generar contexto semántico
            semantic_context = self._generate_semantic_context(
                user_query, schema_context, search_results, query_analysis
            )
            
            # Construir prompt optimizado
            system_prompt = self._build_system_prompt(prompt_type, semantic_context)
            user_prompt = self._build_user_prompt(user_query, query_analysis)
            
            # Calcular score de confianza
            confidence_score = self._calculate_confidence_score(query_analysis, semantic_context)
            
            # Generar notas de optimización
            optimization_notes = self._generate_optimization_notes(query_analysis, semantic_context)
            
            optimized_prompt = OptimizedPrompt(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                context_schema=semantic_context,
                semantic_hints=query_analysis.entities,
                confidence_score=confidence_score,
                optimization_notes=optimization_notes
            )
            
            # Actualizar estadísticas
            self._update_stats(confidence_score)
            
            response_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"[PromptEngineeringService] 🎯 Prompt optimizado en {response_time:.2f}s (confianza: {confidence_score:.2f})")
            
            return optimized_prompt
            
        except Exception as e:
            logger.error(f"[PromptEngineeringService] ❌ Error optimizando prompt: {e}")
            # Fallback a prompt básico
            return self._create_fallback_prompt(user_query, schema_context)
    
    def _analyze_user_query(self, query: str) -> QueryAnalysis:
        """Analizar query del usuario para extraer intención y entidades"""
        query_lower = query.lower()
        
        # Detectar intención
        intent = self._detect_intent(query_lower)
        
        # Extraer entidades
        entities = self._extract_entities(query_lower)
        
        # Detectar acciones
        actions = self._detect_actions(query_lower)
        
        # Identificar constraints
        constraints = self._extract_constraints(query_lower)
        
        # Determinar foco semántico
        semantic_focus = self._determine_semantic_focus(query_lower)
        
        # Evaluar complejidad
        complexity_level = self._assess_complexity(query_lower, entities, actions)
        
        return QueryAnalysis(
            intent=intent,
            entities=entities,
            actions=actions,
            constraints=constraints,
            semantic_focus=semantic_focus,
            complexity_level=complexity_level
        )
    
    def _detect_intent(self, query: str) -> str:
        """Detectar la intención principal de la query"""
        if any(term in query for term in ["count", "cuantas", "total"]):
            return "aggregation"
        elif any(term in query for term in ["find", "buscar", "show", "mostrar"]):
            return "query"
        elif any(term in query for term in ["analyze", "analizar", "explain", "explicar"]):
            return "analysis"
        elif any(term in query for term in ["list", "listar", "get", "obtener"]):
            return "retrieval"
        else:
            return "general"
    
    def _extract_entities(self, query: str) -> List[str]:
        """Extraer entidades mencionadas en la query"""
        entities = []
        
        # Entidades de ubicación
        location_entities = ["madrid", "barcelona", "valencia", "address", "city", "country"]
        entities.extend([entity for entity in location_entities if entity in query])
        
        # Entidades de nombre
        name_entities = ["valhalla", "club", "name", "title"]
        entities.extend([entity for entity in name_entities if entity in query])
        
        # Entidades de tabla
        table_entities = ["clubs", "invitations", "users", "members"]
        entities.extend([entity for entity in table_entities if entity in query])
        
        return list(set(entities))
    
    def _detect_actions(self, query: str) -> List[str]:
        """Detectar acciones mencionadas en la query"""
        actions = []
        
        action_patterns = {
            "count": ["count", "cuantas", "total", "sum"],
            "find": ["find", "buscar", "locate", "encontrar"],
            "show": ["show", "mostrar", "display", "list"],
            "analyze": ["analyze", "analizar", "explain", "explicar"]
        }
        
        for action_type, patterns in action_patterns.items():
            if any(pattern in query for pattern in patterns):
                actions.append(action_type)
        
        return actions
    
    def _extract_constraints(self, query: str) -> List[str]:
        """Extraer constraints mencionados en la query"""
        constraints = []
        
        # Constraints de ubicación
        if any(term in query for term in ["madrid", "barcelona"]):
            constraints.append("location_specific")
        
        # Constraints de tiempo
        if any(term in query for term in ["today", "yesterday", "this month"]):
            constraints.append("time_specific")
        
        # Constraints de cantidad
        if any(term in query for term in ["limit", "top", "first"]):
            constraints.append("quantity_limit")
        
        return constraints
    
    def _determine_semantic_focus(self, query: str) -> str:
        """Determinar el foco semántico de la query"""
        if any(term in query for term in ["madrid", "barcelona", "address", "city"]):
            return "location"
        elif any(term in query for term in ["valhalla", "name", "title"]):
            return "name"
        elif any(term in query for term in ["count", "total", "number"]):
            return "quantity"
        elif any(term in query for term in ["date", "created", "updated"]):
            return "time"
        else:
            return "general"
    
    def _assess_complexity(self, query: str, entities: List[str], actions: List[str]) -> str:
        """Evaluar la complejidad de la query"""
        complexity_score = 0
        
        # Factores de complejidad
        complexity_score += len(entities) * 0.5
        complexity_score += len(actions) * 0.3
        complexity_score += len(query.split()) * 0.1
        
        if "join" in query or "relacion" in query:
            complexity_score += 2
        
        if "where" in query or "condicion" in query:
            complexity_score += 1
        
        if complexity_score < 2:
            return "simple"
        elif complexity_score < 4:
            return "medium"
        else:
            return "complex"
    
    def _determine_prompt_type(self, analysis: QueryAnalysis) -> str:
        """Determinar el tipo de prompt más apropiado"""
        if analysis.intent == "aggregation":
            return "database_query"
        elif analysis.intent == "analysis":
            return "data_analysis"
        else:
            return "schema_exploration"
    
    def _generate_semantic_context(
        self, 
        query: str, 
        schema_context: Dict[str, Any],
        search_results: List[Any],
        analysis: QueryAnalysis
    ) -> Dict[str, Any]:
        """Generar contexto semántico optimizado"""
        context = {
            "query_analysis": {
                "intent": analysis.intent,
                "entities": analysis.entities,
                "actions": analysis.actions,
                "semantic_focus": analysis.semantic_focus,
                "complexity": analysis.complexity_level
            },
            "relevant_schema": {},
            "semantic_hints": [],
            "optimization_notes": []
        }
        
        # Filtrar esquema relevante
        if schema_context.get("tables"):
            relevant_tables = {}
            for table_name, table_info in schema_context["tables"].items():
                if self._is_table_relevant(table_name, analysis):
                    relevant_tables[table_name] = table_info
            context["relevant_schema"]["tables"] = relevant_tables
        
        # Agregar hints semánticos
        if analysis.semantic_focus == "location":
            context["semantic_hints"].append("📍 Buscar columnas de ubicación (address, city, country)")
        elif analysis.semantic_focus == "name":
            context["semantic_hints"].append("🏷️ Buscar columnas de nombre (name, title)")
        elif analysis.semantic_focus == "quantity":
            context["semantic_hints"].append("🔢 Usar funciones de agregación (COUNT, SUM)")
        
        # Agregar notas de optimización
        if analysis.complexity_level == "complex":
            context["optimization_notes"].append("⚡ Query compleja detectada - optimizar con índices")
        
        return context
    
    def _is_table_relevant(self, table_name: str, analysis: QueryAnalysis) -> bool:
        """Verificar si una tabla es relevante para el análisis"""
        table_lower = table_name.lower()
        
        # Verificar entidades mencionadas
        for entity in analysis.entities:
            if entity in table_lower:
                return True
        
        # Verificar foco semántico
        if analysis.semantic_focus == "location" and "address" in table_lower:
            return True
        elif analysis.semantic_focus == "name" and "name" in table_lower:
            return True
        
        return True  # Por defecto incluir todas las tablas
    
    def _build_system_prompt(self, prompt_type: str, semantic_context: Dict[str, Any]) -> str:
        """Construir system prompt optimizado"""
        template = self.prompt_templates.get(prompt_type, self.prompt_templates["database_query"])
        
        # Formatear contexto del esquema
        schema_context = self._format_schema_context(semantic_context.get("relevant_schema", {}))
        
        # Formatear análisis semántico
        semantic_analysis = self._format_semantic_analysis(semantic_context.get("query_analysis", {}))
        
        return template.format(
            schema_context=schema_context,
            semantic_analysis=semantic_analysis,
            user_query="{user_query}"  # Placeholder
        )
    
    def _build_user_prompt(self, user_query: str, analysis: QueryAnalysis) -> str:
        """Construir user prompt optimizado"""
        # Agregar contexto adicional basado en el análisis
        enhanced_query = user_query
        
        if analysis.complexity_level == "complex":
            enhanced_query += "\n\nNota: Esta es una consulta compleja. Por favor, optimiza la respuesta para rendimiento."
        
        if analysis.semantic_focus == "location":
            enhanced_query += "\n\nEnfoque: Buscar información de ubicación específica."
        
        return enhanced_query
    
    def _format_schema_context(self, schema: Dict[str, Any]) -> str:
        """Formatear contexto del esquema para el prompt"""
        if not schema.get("tables"):
            return "No hay esquema disponible."
        
        formatted_parts = []
        for table_name, table_info in schema["tables"].items():
            table_part = f"Tabla: {table_name}\n"
            
            if table_info.get("columns"):
                columns = []
                for col_name, col_info in table_info["columns"].items():
                    col_type = col_info.get("type", "unknown")
                    semantic_type = col_info.get("semantic_type", "unknown")
                    columns.append(f"  - {col_name}: {col_type} ({semantic_type})")
                table_part += "\n".join(columns)
            
            formatted_parts.append(table_part)
        
        return "\n\n".join(formatted_parts)
    
    def _format_semantic_analysis(self, analysis: Dict[str, Any]) -> str:
        """Formatear análisis semántico para el prompt"""
        parts = []
        
        if analysis.get("intent"):
            parts.append(f"Intención: {analysis['intent']}")
        
        if analysis.get("entities"):
            parts.append(f"Entidades: {', '.join(analysis['entities'])}")
        
        if analysis.get("semantic_focus"):
            parts.append(f"Foco semántico: {analysis['semantic_focus']}")
        
        if analysis.get("complexity"):
            parts.append(f"Complejidad: {analysis['complexity']}")
        
        return "\n".join(parts) if parts else "Análisis semántico no disponible."
    
    def _calculate_confidence_score(self, analysis: QueryAnalysis, context: Dict[str, Any]) -> float:
        """Calcular score de confianza del prompt optimizado"""
        score = 0.5  # Base score
        
        # Boost por entidades detectadas
        score += len(analysis.entities) * 0.1
        
        # Boost por esquema relevante
        if context.get("relevant_schema", {}).get("tables"):
            score += 0.2
        
        # Boost por análisis semántico claro
        if analysis.semantic_focus != "general":
            score += 0.15
        
        # Penalty por complejidad alta
        if analysis.complexity_level == "complex":
            score -= 0.1
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _generate_optimization_notes(self, analysis: QueryAnalysis, context: Dict[str, Any]) -> List[str]:
        """Generar notas de optimización"""
        notes = []
        
        if analysis.complexity_level == "complex":
            notes.append("⚡ Query compleja - optimización recomendada")
        
        if analysis.semantic_focus == "location":
            notes.append("📍 Foco en ubicación detectado")
        
        if len(analysis.entities) > 3:
            notes.append("🎯 Múltiples entidades detectadas")
        
        if context.get("semantic_hints"):
            notes.append("💡 Hints semánticos aplicados")
        
        return notes
    
    def _create_fallback_prompt(self, user_query: str, schema_context: Dict[str, Any]) -> OptimizedPrompt:
        """Crear prompt de fallback en caso de error"""
        return OptimizedPrompt(
            system_prompt="Eres un asistente de base de datos. Responde de manera clara y precisa.",
            user_prompt=user_query,
            context_schema=schema_context,
            semantic_hints=[],
            confidence_score=0.5,
            optimization_notes=["⚠️ Prompt de fallback usado"]
        )
    
    def _update_stats(self, confidence_score: float) -> None:
        """Actualizar estadísticas de performance"""
        self.prompt_stats["total_optimizations"] += 1
        
        # Actualizar score promedio
        current_avg = self.prompt_stats["avg_confidence_score"]
        total_ops = self.prompt_stats["total_optimizations"]
        
        self.prompt_stats["avg_confidence_score"] = (
            (current_avg * (total_ops - 1) + confidence_score) / total_ops
        )
        
        # Contar queries exitosas/fallidas
        if confidence_score > 0.7:
            self.prompt_stats["successful_queries"] += 1
        else:
            self.prompt_stats["failed_queries"] += 1
    
    def get_prompt_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de prompt engineering"""
        return {
            "total_optimizations": self.prompt_stats["total_optimizations"],
            "avg_confidence_score": self.prompt_stats["avg_confidence_score"],
            "successful_queries": self.prompt_stats["successful_queries"],
            "failed_queries": self.prompt_stats["failed_queries"],
            "success_rate": self.prompt_stats["successful_queries"] / max(self.prompt_stats["total_optimizations"], 1)
        }
