from typing import Dict, Any, Optional
from enum import Enum
import re
import logging
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Tipos de intención que puede tener un mensaje del usuario"""
    DB_READ = "db_read"           # Consultas SELECT, análisis, reportes
    DB_WRITE = "db_write"         # INSERT, UPDATE, DELETE, DDL
    APP_CALL = "app_call"         # Llamadas a APIs/funciones de aplicaciones
    CHAT = "chat"                 # Conversación general, saludo, preguntas conceptuales
    UNKNOWN = "unknown"           # No se puede determinar


class IntentClassifierService(BaseService):
    """
    Servicio para clasificar la intención de un mensaje del usuario.
    Determina si requiere acceso a base de datos, apps, o es conversación general.
    """
    
    def __init__(self, factory):
        super().__init__(factory)
        
        # Patrones para clasificación de intenciones
        self._db_read_patterns = [
            r'\b(select|query|busca|encuentra|muestra|lista|ver|obtén|dame|cuántos|cuántas)\b',
            r'\b(tabla|tablas|base\s+de\s+datos|bd|db|registro|registros)\b',
            r'\b(count|sum|avg|max|min|group\s+by|order\s+by|where)\b',
            r'\b(reporte|informe|estadística|análisis|dashboard)\b',
            r'\b(usuarios|productos|ventas|pedidos|clientes|facturas)\b'
        ]
        
        self._db_write_patterns = [
            r'\b(insert|create|update|delete|modify|cambiar|actualizar|insertar|crear|eliminar|borrar)\b',
            r'\b(añadir|agregar|modificar|editar|guardar|almacenar)\b',
            r'\b(nuevo|nueva|elimina|borra|actualiza|modifica)\b'
        ]
        
        self._app_call_patterns = [
            r'\b(api|endpoint|función|servicio|llamar|ejecutar|invocar)\b',
            r'\b(webhook|http|rest|post|get|put|delete)\b',
            r'\b(integración|conectar|sincronizar|enviar|recibir)\b'
        ]
        
        self._chat_patterns = [
            r'\b(hola|hi|hello|saludo|buenos\s+días|buenas\s+tardes|buenas\s+noches)\b',
            r'\b(qué\s+tal|cómo\s+estás|ayuda|help|explicar|explícame)\b',
            r'\b(gracias|thank\s+you|perfecto|genial|excelente|ok)\b',
            r'\b(qué\s+es|cómo\s+funciona|para\s+qué\s+sirve|conceptual)\b'
        ]

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Clasifica la intención de un texto del usuario.
        
        Args:
            text: Mensaje del usuario
            
        Returns:
            Dict con:
            - intent: IntentType
            - confidence: float (0.0-1.0)
            - reasoning: str (explicación de la clasificación)
            - requires_resources: bool (si necesita DB/Apps)
        """
        if not text or not isinstance(text, str):
            return {
                "intent": IntentType.UNKNOWN,
                "confidence": 0.0,
                "reasoning": "Texto vacío o inválido",
                "requires_resources": False
            }
        
        text_lower = text.lower()
        scores = {}
        
        # Calcular scores para cada tipo de intención
        scores[IntentType.DB_READ] = self._calculate_pattern_score(text_lower, self._db_read_patterns)
        scores[IntentType.DB_WRITE] = self._calculate_pattern_score(text_lower, self._db_write_patterns)
        scores[IntentType.APP_CALL] = self._calculate_pattern_score(text_lower, self._app_call_patterns)
        scores[IntentType.CHAT] = self._calculate_pattern_score(text_lower, self._chat_patterns)
        
        # Determinar la intención con mayor score
        best_intent = max(scores.keys(), key=lambda k: scores[k])
        max_score = scores[best_intent]
        
        # Si no hay un score significativo, es UNKNOWN
        if max_score < 0.3:
            best_intent = IntentType.UNKNOWN
            confidence = 0.0
        else:
            confidence = min(max_score, 1.0)
        
        # Determinar si requiere recursos
        requires_resources = best_intent in [IntentType.DB_READ, IntentType.DB_WRITE, IntentType.APP_CALL]
        
        # Generar reasoning
        reasoning = self._generate_reasoning(best_intent, max_score, text_lower)
        
        logger.info(f"[IntentClassifier] 🎯 Texto: '{text[:50]}...' -> {best_intent.value} (conf: {confidence:.2f})")
        
        return {
            "intent": best_intent,
            "confidence": confidence,
            "reasoning": reasoning,
            "requires_resources": requires_resources
        }
    
    def _calculate_pattern_score(self, text: str, patterns: list) -> float:
        """Calcula el score de coincidencia con patrones regex"""
        matches = 0
        total_patterns = len(patterns)
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                matches += 1
        
        # Score base por coincidencias
        base_score = matches / total_patterns if total_patterns > 0 else 0.0
        
        # Bonus por múltiples coincidencias en el mismo patrón
        word_count = len(text.split())
        density_bonus = min(matches / max(word_count, 1), 0.3)
        
        return min(base_score + density_bonus, 1.0)
    
    def _generate_reasoning(self, intent: IntentType, score: float, text: str) -> str:
        """Genera explicación de por qué se clasificó con esa intención"""
        if intent == IntentType.DB_READ:
            return f"Detectadas palabras clave de consulta/lectura de datos (score: {score:.2f})"
        elif intent == IntentType.DB_WRITE:
            return f"Detectadas palabras clave de modificación de datos (score: {score:.2f})"
        elif intent == IntentType.APP_CALL:
            return f"Detectadas palabras clave de llamada a servicios/APIs (score: {score:.2f})"
        elif intent == IntentType.CHAT:
            return f"Detectadas palabras clave de conversación general (score: {score:.2f})"
        else:
            return f"No se detectaron patrones claros de intención (score: {score:.2f})"
    
    def is_resource_dependent(self, intent: IntentType) -> bool:
        """Determina si una intención requiere recursos específicos (DB/Apps)"""
        return intent in [IntentType.DB_READ, IntentType.DB_WRITE, IntentType.APP_CALL]
    
    def get_clarification_message(self, intent: IntentType) -> str:
        """Genera mensaje de aclaración cuando se requieren recursos específicos"""
        if intent == IntentType.DB_READ:
            return "Para realizar esta consulta, necesito saber con qué base de datos deseas trabajar. ¿Podrías especificar cuál?"
        elif intent == IntentType.DB_WRITE:
            return "Para realizar esta operación de escritura, necesito saber en qué base de datos quieres hacer los cambios. ¿Cuál prefieres?"
        elif intent == IntentType.APP_CALL:
            return "Para ejecutar esta acción, necesito saber qué aplicación o servicio quieres usar. ¿Podrías especificar cuál?"
        else:
            return "¿Con qué base de datos o aplicación deseas trabajar?"
