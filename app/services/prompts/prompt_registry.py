"""
📝 FASE 8: Prompt Registry - Registro Central de Prompts
──────────────────────────────────────────────────────────
Define todas las claves de prompts del sistema para:
- Pipeline de ingesta
- Chat inteligente
- Orquestación y manejo de errores
- Validación y debugging
"""

from enum import Enum
from typing import Dict, List, Optional


class PromptCategory(Enum):
    """Categorías de prompts del sistema"""
    PIPELINE = "pipeline"
    CHAT = "chat"
    ORCHESTRATION = "orchestration"
    ERROR_HANDLING = "error_handling"
    VALIDATION = "validation"
    DEBUGGING = "debugging"


class PromptKey(Enum):
    """Claves de prompts del sistema para la Fase 8"""
    
    # 🔧 FASE 1: Pipeline de Ingesta
    SCHEMA_EXTRACTION = "schema_extraction"
    SCHEMA_ANALYSIS = "schema_analysis"
    GRAPH_BUILDING = "graph_building"
    CHUNK_GENERATION = "chunk_generation"
    CHUNK_OPTIMIZATION = "chunk_optimization"
    EMBEDDING_GENERATION = "embedding_generation"
    VECTOR_INDEXING = "vector_indexing"
    PIPELINE_ORCHESTRATION = "pipeline_orchestration"
    
    # 💬 FASE 5: Chat Inteligente
    INTENT_CLASSIFICATION = "intent_classification"
    CONTEXT_RESOLUTION = "context_resolution"
    GROUNDING_QUERY = "grounding_query"
    QUERY_PLANNING = "query_planning"
    SQL_GENERATION = "sql_generation"
    SQL_EXPLANATION = "sql_explanation"
    RESULT_INTERPRETATION = "result_interpretation"
    CHAT_ORCHESTRATION = "chat_orchestration"
    
    # 🛡️ FASE 7: Seguridad y Validación
    SQL_VALIDATION = "sql_validation"
    SECURITY_CHECK = "security_check"
    POLICY_ENFORCEMENT = "policy_enforcement"
    ERROR_EXPLANATION = "error_explanation"
    
    # 🔄 FASE 4: Vector Store
    VECTOR_SEARCH = "vector_search"
    SIMILARITY_QUERY = "similarity_query"
    VECTOR_OPTIMIZATION = "vector_optimization"
    
    # 📊 FASE 2: GraphRack
    GRAPH_ANALYSIS = "graph_analysis"
    RELATIONSHIP_DETECTION = "relationship_detection"
    PATH_FINDING = "path_finding"
    
    # 🚨 Manejo de Errores
    ERROR_RECOVERY = "error_recovery"
    RETRY_STRATEGY = "retry_strategy"
    FALLBACK_HANDLING = "fallback_handling"
    
    # 🔍 Debugging y Logging
    DEBUG_ANALYSIS = "debug_analysis"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    SYSTEM_HEALTH = "system_health"


class PromptRegistry:
    """
    📝 Registro central de prompts para la Fase 8
    
    Proporciona:
    - Mapeo de claves a categorías
    - Metadatos de prompts
    - Validación de claves
    - Agrupación por funcionalidad
    """
    
    def __init__(self):
        # Mapeo de prompts a categorías
        self._prompt_categories = {
            # Pipeline de ingesta
            PromptKey.SCHEMA_EXTRACTION: PromptCategory.PIPELINE,
            PromptKey.SCHEMA_ANALYSIS: PromptCategory.PIPELINE,
            PromptKey.GRAPH_BUILDING: PromptCategory.PIPELINE,
            PromptKey.CHUNK_GENERATION: PromptCategory.PIPELINE,
            PromptKey.CHUNK_OPTIMIZATION: PromptCategory.PIPELINE,
            PromptKey.EMBEDDING_GENERATION: PromptCategory.PIPELINE,
            PromptKey.VECTOR_INDEXING: PromptCategory.PIPELINE,
            PromptKey.PIPELINE_ORCHESTRATION: PromptCategory.PIPELINE,
            
            # Chat inteligente
            PromptKey.INTENT_CLASSIFICATION: PromptCategory.CHAT,
            PromptKey.CONTEXT_RESOLUTION: PromptCategory.CHAT,
            PromptKey.GROUNDING_QUERY: PromptCategory.CHAT,
            PromptKey.QUERY_PLANNING: PromptCategory.CHAT,
            PromptKey.SQL_GENERATION: PromptCategory.CHAT,
            PromptKey.SQL_EXPLANATION: PromptCategory.CHAT,
            PromptKey.RESULT_INTERPRETATION: PromptCategory.CHAT,
            PromptKey.CHAT_ORCHESTRATION: PromptCategory.CHAT,
            
            # Orquestación
            PromptKey.SQL_VALIDATION: PromptCategory.ORCHESTRATION,
            PromptKey.SECURITY_CHECK: PromptCategory.ORCHESTRATION,
            PromptKey.POLICY_ENFORCEMENT: PromptCategory.ORCHESTRATION,
            PromptKey.ERROR_EXPLANATION: PromptCategory.ORCHESTRATION,
            
            # Vector Store
            PromptKey.VECTOR_SEARCH: PromptCategory.VALIDATION,
            PromptKey.SIMILARITY_QUERY: PromptCategory.VALIDATION,
            PromptKey.VECTOR_OPTIMIZATION: PromptCategory.VALIDATION,
            
            # GraphRack
            PromptKey.GRAPH_ANALYSIS: PromptCategory.VALIDATION,
            PromptKey.RELATIONSHIP_DETECTION: PromptCategory.VALIDATION,
            PromptKey.PATH_FINDING: PromptCategory.VALIDATION,
            
            # Manejo de errores
            PromptKey.ERROR_RECOVERY: PromptCategory.ERROR_HANDLING,
            PromptKey.RETRY_STRATEGY: PromptCategory.ERROR_HANDLING,
            PromptKey.FALLBACK_HANDLING: PromptCategory.ERROR_HANDLING,
            
            # Debugging
            PromptKey.DEBUG_ANALYSIS: PromptCategory.DEBUGGING,
            PromptKey.PERFORMANCE_ANALYSIS: PromptCategory.DEBUGGING,
            PromptKey.SYSTEM_HEALTH: PromptCategory.DEBUGGING,
        }
        
        # Metadatos de prompts
        self._prompt_metadata = {
            PromptKey.SCHEMA_EXTRACTION: {
                "description": "Extrae y analiza el esquema de una base de datos",
                "required_vars": ["db_name", "connection_info"],
                "optional_vars": ["business_context", "extraction_level"],
                "default_version": "v1",
                "max_tokens": 2000
            },
            PromptKey.SQL_GENERATION: {
                "description": "Genera consultas SQL seguras basadas en consultas naturales",
                "required_vars": ["user_query", "schema_info"],
                "optional_vars": ["security_rules", "query_limits", "preferred_style"],
                "default_version": "v2",
                "max_tokens": 1500
            },
            PromptKey.INTENT_CLASSIFICATION: {
                "description": "Clasifica la intención de una consulta del usuario",
                "required_vars": ["user_query"],
                "optional_vars": ["context", "user_history"],
                "default_version": "v1",
                "max_tokens": 800
            }
        }
    
    def get_category(self, prompt_key: PromptKey) -> PromptCategory:
        """Obtiene la categoría de un prompt"""
        return self._prompt_categories.get(prompt_key, PromptCategory.VALIDATION)
    
    def get_metadata(self, prompt_key: PromptKey) -> Optional[Dict]:
        """Obtiene los metadatos de un prompt"""
        return self._prompt_metadata.get(prompt_key)
    
    def get_prompts_by_category(self, category: PromptCategory) -> List[PromptKey]:
        """Obtiene todos los prompts de una categoría"""
        return [key for key, cat in self._prompt_categories.items() if cat == category]
    
    def get_all_prompts(self) -> List[PromptKey]:
        """Obtiene todas las claves de prompts disponibles"""
        return list(PromptKey)
    
    def validate_prompt_key(self, prompt_key: str) -> bool:
        """Valida si una clave de prompt existe"""
        try:
            PromptKey(prompt_key)
            return True
        except ValueError:
            return False
    
    def get_prompt_info(self, prompt_key: PromptKey) -> Dict:
        """Obtiene información completa de un prompt"""
        metadata = self.get_metadata(prompt_key)
        category = self.get_category(prompt_key)
        
        return {
            "key": prompt_key.value,
            "category": category.value,
            "metadata": metadata or {},
            "description": metadata.get("description", "Sin descripción disponible") if metadata else "Sin descripción disponible"
        }
    
    def get_registry_summary(self) -> Dict:
        """Obtiene un resumen del registro de prompts"""
        categories_count = {}
        for category in PromptCategory:
            categories_count[category.value] = len(self.get_prompts_by_category(category))
        
        return {
            "total_prompts": len(PromptKey),
            "categories": categories_count,
            "available_prompts": [key.value for key in PromptKey],
            "registry_version": "1.0.0"
        }


# Instancia global del registro
prompt_registry = PromptRegistry()
