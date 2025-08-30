from typing import Dict, Any, List, Optional, TypedDict
from app.schemas.chat_schema import ChatMessage
from app.schemas.plan_schema import UserPlanOut
from app.models.app_model import App
from app.models.function_model import Function


class ExplorationState(TypedDict, total=False):
    """Estado compartido del grafo de exploración"""
    
    # Identificación y contexto
    chat_id: str
    message: ChatMessage
    history: List[Dict[str, Any]]

    # Recursos inferidos
    db_ids: List[str]
    db_conns: List[Dict[str, Any]]  # Información de conexiones serializable
    db_dialect: Optional[str]
    apps: List[App]
    functions: List[Function]
    proxy_id: Optional[str]
    
    # Campos para modo explore mejorado
    compact_schemas: Dict[str, str]  # {db_id: compact_schema}
    cache_status: Optional[Dict[str, str]]  # Para debugging

    # 🧠 SMART AI SYSTEM - Nuevos campos
    normalized_query: Optional[str]  # Consulta normalizada por SmartRephraseService
    rephrase_confidence: Optional[float]  # Confianza del rephrase (0.0 - 1.0)
    rephrase_metadata: Optional[Dict[str, Any]]  # Metadatos del rephrase
    
    intent_type: Optional[str]  # Tipo de intención clasificada (db_query, api_function, etc.)
    intent_confidence: Optional[float]  # Confianza de la clasificación (0.0 - 1.0)
    routing_path: Optional[List[str]]  # Ruta de enrutamiento sugerida
    intent_metadata: Optional[Dict[str, Any]]  # Metadatos de la clasificación
    
    smart_ai_result: Optional[Dict[str, Any]]  # Resultado completo del Smart AI
    smart_ai_processing_steps: Optional[List[Dict[str, Any]]]  # Pasos del procesamiento
    smart_ai_recommendations: Optional[List[Dict[str, Any]]]  # Recomendaciones del sistema
    smart_ai_cache_info: Optional[Dict[str, Any]]  # Información del cache

    # Salidas posibles
    plan: UserPlanOut
    assistant_response: str
    error: str
    
    # Métricas de rendimiento (dict serializable)
    performance_metrics: Optional[Dict[str, Any]]
