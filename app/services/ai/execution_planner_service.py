"""
🔧 FASE 2: Servicio de Planificación de Ejecución Avanzado
────────────────────────────────────────────────────────────
Implementa detección automática de intención de consulta y uso de embeddings
para localizar tablas relevantes de forma inteligente.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import re
from enum import Enum

from app.services.ai.language_detection_service import LanguageDetectionService
from app.core.config import settings

logger = logging.getLogger(__name__)

class QueryIntent(Enum):
    """Tipos de intención de consulta detectados"""
    SCHEMA_EXPLORATION = "schema_exploration"      # Explorar estructura de BD
    DATA_QUERY = "data_query"                      # Consultar datos específicos
    AGGREGATION = "aggregation"                    # Agregaciones (COUNT, SUM, etc.)
    RELATIONSHIP_ANALYSIS = "relationship_analysis" # Análisis de relaciones
    PERFORMANCE_ANALYSIS = "performance_analysis"   # Análisis de performance
    UNKNOWN = "unknown"                            # Intención no clara

class ExecutionPlannerService:
    """Servicio para planificar la ejecución de consultas de forma inteligente"""
    
    def __init__(self, factory=None):
        self.factory = factory
        self.language_service = LanguageDetectionService()
        
        # Patrones para detectar intenciones
        self.intent_patterns = {
            QueryIntent.SCHEMA_EXPLORATION: [
                r'\b(mostrar|listar|ver|explorar|estructura|schema|esquema|tablas?|tables?)\b',
                r'\b(qué|what|cuáles|which)\s+(tablas?|tables?|columnas?|columns?)\b',
                r'\b(disponibles?|available|existen|exist)\b',
                r'\b(descripción|description|definición|definition)\b'
            ],
            QueryIntent.DATA_QUERY: [
                r'\b(seleccionar|select|obtener|get|buscar|find|filtrar|filter)\b',
                r'\b(datos?|data|información|information|registros?|records?)\b',
                r'\b(desde|from|en|in)\b',
                r'\b(condición|condition|criteria|criterio)\b'
            ],
            QueryIntent.AGGREGATION: [
                r'\b(contar|count|sumar|sum|promedio|average|mean|media)\b',
                r'\b(máximo|maximum|max|mínimo|minimum|min)\b',
                r'\b(total|total|agrupar|group|resumen|summary)\b',
                r'\b(cuántos?|how many|cuánto|how much)\b'
            ],
            QueryIntent.RELATIONSHIP_ANALYSIS: [
                r'\b(relación|relationship|conexión|connection|join|unir)\b',
                r'\b(entre|between|con|with|a través|through)\b',
                r'\b(foreign key|clave foránea|referencia|reference)\b',
                r'\b(dependencia|dependency|jerarquía|hierarchy)\b'
            ],
            QueryIntent.PERFORMANCE_ANALYSIS: [
                r'\b(performance|rendimiento|velocidad|speed|tiempo|time)\b',
                r'\b(lento|slow|rápido|fast|optimizar|optimize)\b',
                r'\b(índice|index|query plan|plan de consulta)\b',
                r'\b(bottleneck|cuello de botella|estadísticas|statistics)\b'
            ]
        }
        
        # Palabras clave de contexto para determinar recursos relevantes
        self.context_keywords = {
            'user': ['usuario', 'user', 'cliente', 'customer', 'empleado', 'employee'],
            'order': ['pedido', 'order', 'compra', 'purchase', 'venta', 'sale'],
            'product': ['producto', 'product', 'item', 'artículo', 'servicio', 'service'],
            'financial': ['financiero', 'financial', 'pago', 'payment', 'factura', 'invoice'],
            'logistics': ['logística', 'logistics', 'envío', 'shipping', 'almacén', 'warehouse'],
            'analytics': ['análisis', 'analytics', 'reporte', 'report', 'métrica', 'metric']
        }
    
    def analyze_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analiza la intención de una consulta usando patrones y NLP
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Dict con análisis de intención y metadata
        """
        # Mejorar consulta con detección de idioma
        enhanced_query_info = self.language_service.enhance_query_for_schema_search(query)
        enhanced_query = enhanced_query_info['enhanced_query']
        
        # Detectar intención usando patrones
        detected_intent = self._detect_intent_from_patterns(enhanced_query)
        
        # Extraer contexto y recursos relevantes
        context_info = self._extract_context_and_resources(enhanced_query)
        
        # Determinar si se necesita SQL
        needs_sql = self._determine_sql_necessity(detected_intent, context_info)
        
        # Generar plan de ejecución
        execution_plan = self._generate_execution_plan(detected_intent, context_info, needs_sql)
        
        analysis_result = {
            'original_query': query,
            'enhanced_query': enhanced_query,
            'detected_language': enhanced_query_info['detected_language'],
            'intent': detected_intent.value,
            'intent_confidence': self._calculate_intent_confidence(enhanced_query, detected_intent),
            'context': context_info,
            'needs_sql': needs_sql,
            'execution_plan': execution_plan,
            'suggested_approach': self._suggest_approach(detected_intent, needs_sql),
            'estimated_complexity': self._estimate_complexity(detected_intent, context_info)
        }
        
        logger.info(f"[ExecutionPlannerService] 🔧 FASE 2: Intención detectada: {detected_intent.value} (confianza: {analysis_result['intent_confidence']:.2f})")
        return analysis_result
    
    def _detect_intent_from_patterns(self, query: str) -> QueryIntent:
        """Detecta intención usando patrones regex"""
        query_lower = query.lower()
        
        # Contar coincidencias para cada tipo de intención
        intent_scores = {}
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, query_lower, re.IGNORECASE))
                score += matches
            intent_scores[intent] = score
        
        # Encontrar intención con mayor score
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            if best_intent[1] > 0:
                return best_intent[0]
        
        return QueryIntent.UNKNOWN
    
    def _extract_context_and_resources(self, query: str) -> Dict[str, Any]:
        """Extrae contexto y recursos relevantes de la consulta"""
        query_lower = query.lower()
        context_info = {
            'business_domains': [],
            'entities': [],
            'operations': [],
            'filters': [],
            'time_periods': []
        }
        
        # Detectar dominios de negocio
        for domain, keywords in self.context_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                context_info['business_domains'].append(domain)
        
        # Detectar entidades (tablas potenciales)
        entity_patterns = [
            r'\b(users?|usuarios?|clientes?|customers?)\b',
            r'\b(orders?|pedidos?|compras?|purchases?)\b',
            r'\b(products?|productos?|items?|artículos?)\b',
            r'\b(payments?|pagos?|facturas?|invoices?)\b',
            r'\b(shipments?|envíos?|logistics?|logística)\b'
        ]
        
        for pattern in entity_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            context_info['entities'].extend(matches)
        
        # Detectar operaciones
        operation_patterns = [
            r'\b(crear|create|insertar|insert)\b',
            r'\b(leer|read|obtener|get)\b',
            r'\b(actualizar|update|modificar|modify)\b',
            r'\b(eliminar|delete|borrar|remove)\b'
        ]
        
        for pattern in operation_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            context_info['operations'].extend(matches)
        
        # Detectar filtros de tiempo
        time_patterns = [
            r'\b(hoy|today|ayer|yesterday|mañana|tomorrow)\b',
            r'\b(esta semana|this week|última semana|last week)\b',
            r'\b(este mes|this month|último mes|last month)\b',
            r'\b(este año|this year|último año|last year)\b'
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, query_lower, re.IGNORECASE)
            context_info['time_periods'].extend(matches)
        
        return context_info
    
    def _determine_sql_necessity(self, intent: QueryIntent, context: Dict[str, Any]) -> bool:
        """Determina si la consulta requiere generación de SQL"""
        # Consultas de exploración de esquema no necesitan SQL complejo
        if intent == QueryIntent.SCHEMA_EXPLORATION:
            return False
        
        # Consultas de datos siempre necesitan SQL
        if intent in [QueryIntent.DATA_QUERY, QueryIntent.AGGREGATION]:
            return True
        
        # Análisis de relaciones puede necesitar SQL complejo
        if intent == QueryIntent.RELATIONSHIP_ANALYSIS:
            return len(context.get('entities', [])) > 1
        
        # Análisis de performance puede necesitar SQL específico
        if intent == QueryIntent.PERFORMANCE_ANALYSIS:
            return True
        
        return False
    
    def _generate_execution_plan(self, intent: QueryIntent, context: Dict[str, Any], needs_sql: bool) -> Dict[str, Any]:
        """Genera un plan de ejecución basado en la intención y contexto"""
        plan = {
            'steps': [],
            'estimated_duration': 0,
            'resource_requirements': [],
            'fallback_strategies': []
        }
        
        if intent == QueryIntent.SCHEMA_EXPLORATION:
            plan['steps'] = [
                '1. Búsqueda rápida en information_schema',
                '2. Filtrado por esquemas relevantes',
                '3. Presentación estructurada de resultados'
            ]
            plan['estimated_duration'] = 0.5
            plan['resource_requirements'] = ['schema_cache', 'fast_path']
            
        elif intent == QueryIntent.DATA_QUERY:
            plan['steps'] = [
                '1. Análisis de intención y contexto',
                '2. Generación de SQL optimizado',
                '3. Validación de seguridad',
                '4. Ejecución y formateo de resultados'
            ]
            plan['estimated_duration'] = 2.0
            plan['resource_requirements'] = ['sql_generator', 'executor', 'formatter']
            
        elif intent == QueryIntent.AGGREGATION:
            plan['steps'] = [
                '1. Detección de función de agregación',
                '2. Identificación de tabla objetivo',
                '3. Generación de SQL con GROUP BY',
                '4. Ejecución y presentación de métricas'
            ]
            plan['estimated_duration'] = 1.5
            plan['resource_requirements'] = ['aggregation_analyzer', 'sql_generator']
            
        # Estrategias de fallback
        plan['fallback_strategies'] = [
            'Búsqueda difusa en esquema',
            'Consulta genérica de information_schema',
            'Sugerencias de consultas similares'
        ]
        
        return plan
    
    def _calculate_intent_confidence(self, query: str, intent: QueryIntent) -> float:
        """Calcula la confianza en la detección de intención"""
        if intent == QueryIntent.UNKNOWN:
            return 0.0
        
        patterns = self.intent_patterns.get(intent, [])
        total_matches = 0
        
        for pattern in patterns:
            matches = len(re.findall(pattern, query.lower(), re.IGNORECASE))
            total_matches += matches
        
        # Normalizar confianza (0-1)
        max_possible_matches = len(patterns) * 2  # Asumiendo máximo 2 matches por patrón
        confidence = min(total_matches / max_possible_matches, 1.0)
        
        return confidence
    
    def _suggest_approach(self, intent: QueryIntent, needs_sql: bool) -> str:
        """Sugiere el enfoque de ejecución más apropiado"""
        if intent == QueryIntent.SCHEMA_EXPLORATION:
            return "fast_schema_path"
        elif needs_sql:
            return "guided_sql_generation"
        else:
            return "natural_language_response"
    
    def _estimate_complexity(self, intent: QueryIntent, context: Dict[str, Any]) -> str:
        """Estima la complejidad de la consulta"""
        if intent == QueryIntent.SCHEMA_EXPLORATION:
            return "low"
        elif intent == QueryIntent.DATA_QUERY and len(context.get('entities', [])) <= 1:
            return "medium"
        elif intent in [QueryIntent.AGGREGATION, QueryIntent.RELATIONSHIP_ANALYSIS]:
            return "high"
        else:
            return "medium"
    
    def get_optimization_suggestions(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Genera sugerencias de optimización basadas en el análisis"""
        suggestions = []
        
        if analysis_result['intent'] == QueryIntent.SCHEMA_EXPLORATION.value:
            suggestions.extend([
                "Usar búsqueda rápida en information_schema",
                "Aplicar filtros por esquema de usuario",
                "Cachear resultados de esquema frecuentes"
            ])
        
        if analysis_result['needs_sql']:
            suggestions.extend([
                "Generar SQL con LIMIT automático",
                "Aplicar validaciones de seguridad",
                "Usar índices apropiados para la consulta"
            ])
        
        if analysis_result['estimated_complexity'] == 'high':
            suggestions.extend([
                "Considerar ejecución asíncrona",
                "Implementar timeout de ejecución",
                "Proporcionar progreso en tiempo real"
            ])
        
        return suggestions
