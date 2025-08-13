# app/services/ai/fallback_response_service.py
"""
🔧 FASE 11: Servicio de fallback de respuesta IA cuando assistant_response está vacío
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class FallbackResponseService:
    """
    🔧 FASE 11: Servicio para generar respuestas de fallback cuando assistant_response está vacío.
    Evita que errores internos aparezcan como respuestas de la IA.
    """
    
    def __init__(self):
        self.fallback_templates = self._load_fallback_templates()
        self.error_patterns = self._load_error_patterns()
    
    def _load_fallback_templates(self) -> Dict[str, str]:
        """🔧 FASE 11: Cargar plantillas de fallback para diferentes situaciones"""
        return {
            "general_fallback": "🤖 No pude generar una respuesta completa para tu consulta. ¿Podrías reformular tu pregunta o ser más específico?",
            "database_error": "🗄️ Tuve un problema accediendo a la base de datos. ¿Podrías verificar que la conexión esté activa y volver a intentar?",
            "execution_error": "⚙️ Ocurrió un error durante la ejecución de tu consulta. El equipo técnico ha sido notificado.",
            "timeout_error": "⏰ La consulta tardó más de lo esperado. ¿Podrías intentar con una pregunta más específica?",
            "validation_error": "✅ Tu consulta no pudo ser validada correctamente. ¿Podrías reformularla de otra manera?",
            "context_error": "📚 No pude obtener suficiente contexto para responder tu pregunta. ¿Podrías proporcionar más detalles?",
            "resource_error": "🔍 No encontré los recursos necesarios para responder tu consulta. ¿Podrías verificar que estén disponibles?",
            "unknown_error": "❓ Ocurrió un error inesperado. Por favor, intenta nuevamente o contacta soporte si el problema persiste."
        }
    
    def _load_error_patterns(self) -> Dict[str, List[str]]:
        """🔧 FASE 11: Cargar patrones para detectar tipos de errores"""
        return {
            "database": [
                "connection", "database", "sql", "query", "table", "column", "schema",
                "conexión", "base de datos", "consulta", "tabla", "columna", "esquema"
            ],
            "execution": [
                "execution", "runtime", "execution_error", "runtime_error", "function",
                "ejecución", "tiempo de ejecución", "función", "error de ejecución"
            ],
            "timeout": [
                "timeout", "timed out", "time out", "expired", "deadline",
                "tiempo agotado", "expiró", "límite de tiempo"
            ],
            "validation": [
                "validation", "invalid", "malformed", "syntax", "format",
                "validación", "inválido", "mal formado", "sintaxis", "formato"
            ],
            "context": [
                "context", "missing", "not found", "empty", "null", "undefined",
                "contexto", "faltante", "no encontrado", "vacío", "nulo", "indefinido"
            ],
            "resource": [
                "resource", "file", "memory", "disk", "network", "permission",
                "recurso", "archivo", "memoria", "disco", "red", "permiso"
            ]
        }
    
    def generate_fallback_response(
        self, 
        execution_results: Dict[str, Any], 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        🔧 FASE 11: Generar respuesta de fallback basada en el contexto y errores.
        
        Args:
            execution_results: Resultados de la ejecución que pueden contener errores
            user_message: Mensaje original del usuario
            context: Contexto adicional de la ejecución
            
        Returns:
            Respuesta de fallback apropiada
        """
        try:
            logger.info(f"[FallbackResponseService] 🔧 FASE 11: Generando respuesta de fallback")
            
            # 🔧 FASE 11: Detectar tipo de error
            error_type = self._detect_error_type(execution_results, user_message)
            logger.info(f"[FallbackResponseService] 🔧 FASE 11: Tipo de error detectado: {error_type}")
            
            # 🔧 FASE 11: Generar respuesta específica para el tipo de error
            fallback_response = self._generate_specific_fallback(error_type, execution_results, user_message, context)
            
            # 🔧 FASE 11: Añadir metadatos de fallback
            fallback_response = self._add_fallback_metadata(fallback_response, error_type, execution_results)
            
            logger.info(f"[FallbackResponseService] 🔧 FASE 11: Respuesta de fallback generada: {fallback_response[:100]}...")
            return fallback_response
            
        except Exception as e:
            logger.error(f"[FallbackResponseService] ❌ Error generando fallback: {e}")
            return self.fallback_templates["unknown_error"]
    
    def _detect_error_type(self, execution_results: Dict[str, Any], user_message: str) -> str:
        """🔧 FASE 11: Detectar el tipo de error basado en los resultados y mensaje"""
        try:
            # 🔧 FASE 11: PRIORIDAD 1: Buscar errores explícitos en execution_results
            if "error" in execution_results:
                error_text = str(execution_results["error"]).lower()
                classified_error = self._classify_error_by_text(error_text)
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Error explícito detectado: '{error_text}' -> {classified_error}")
                return classified_error
            
            if "execution_error" in execution_results:
                error_text = str(execution_results["execution_error"]).lower()
                classified_error = self._classify_error_by_text(error_text)
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Error de ejecución detectado: '{error_text}' -> {classified_error}")
                return classified_error
            
            # 🔧 FASE 11: PRIORIDAD 2: Buscar en variables si existen
            if "variables" in execution_results:
                variables = execution_results["variables"]
                for var_name, var_value in variables.items():
                    if "error" in str(var_value).lower():
                        error_text = str(var_value).lower()
                        classified_error = self._classify_error_by_text(error_text)
                        logger.info(f"[FallbackResponseService] 🔧 FASE 11: Error en variables detectado: '{error_text}' -> {classified_error}")
                        return classified_error
            
            # 🔧 FASE 11: PRIORIDAD 3: Analizar el mensaje del usuario para contexto (solo si no hay errores explícitos)
            user_lower = user_message.lower()
            if any(word in user_lower for word in self.error_patterns["database"]):
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Patrón de BD detectado en mensaje: '{user_message}'")
                return "database_error"
            elif any(word in user_lower for word in self.error_patterns["validation"]):
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Patrón de validación detectado en mensaje: '{user_message}'")
                return "validation_error"
            elif any(word in user_lower for word in self.error_patterns["context"]):
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Patrón de contexto detectado en mensaje: '{user_message}'")
                return "context_error"
            
            # Por defecto, error general
            logger.info(f"[FallbackResponseService] 🔧 FASE 11: No se detectó patrón específico, usando fallback general")
            return "general_fallback"
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error detectando tipo de error: {e}")
            return "unknown_error"
    
    def _classify_error_by_text(self, error_text: str) -> str:
        """🔧 FASE 11: Clasificar error basado en el texto del error"""
        error_lower = error_text.lower()
        
        # 🔧 FASE 11: PRIORIDAD 1: Clasificaciones específicas (más específicas primero)
        if "timeout" in error_lower or "timed out" in error_lower:
            return "timeout_error"
        elif "invalid" in error_lower or "syntax" in error_lower or "malformed" in error_lower:
            return "validation_error"
        elif "permission" in error_lower or "access denied" in error_lower:
            return "resource_error"
        elif "connection" in error_lower or "network" in error_lower:
            return "database_error"
        
        # 🔧 FASE 11: PRIORIDAD 2: Clasificar por patrones generales (palabras completas)
        for error_type, patterns in self.error_patterns.items():
            if any(pattern in error_lower.split() for pattern in patterns):
                return f"{error_type}_error"
        
        return "general_fallback"
    
    def _generate_specific_fallback(
        self, 
        error_type: str, 
        execution_results: Dict[str, Any], 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """🔧 FASE 11: Generar fallback específico para el tipo de error"""
        try:
            # 🔧 FASE 11: Obtener plantilla base
            template = self.fallback_templates.get(error_type, self.fallback_templates["unknown_error"])
            
            # 🔧 FASE 11: Personalizar basado en el contexto
            if error_type == "database_error":
                return self._customize_database_fallback(template, execution_results, context)
            elif error_type == "execution_error":
                return self._customize_execution_fallback(template, execution_results, context)
            elif error_type == "context_error":
                return self._customize_context_fallback(template, execution_results, user_message, context)
            elif error_type == "validation_error":
                return self._customize_validation_fallback(template, execution_results, user_message)
            else:
                return self._customize_general_fallback(template, execution_results, user_message)
                
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error generando fallback específico: {e}")
            return self.fallback_templates["unknown_error"]
    
    def _customize_database_fallback(
        self, 
        template: str, 
        execution_results: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """🔧 FASE 11: Personalizar fallback de base de datos"""
        try:
            # Buscar información específica de la base de datos
            db_info = ""
            if context and "db_ids" in context:
                db_count = len(context["db_ids"])
                db_info = f"\n\n📊 **Contexto**: Estabas consultando {db_count} base(s) de datos."
            
            # Buscar errores específicos de SQL
            sql_error = ""
            if "variables" in execution_results:
                variables = execution_results["variables"]
                if "query_result" in variables and "error" in str(variables["query_result"]):
                    sql_error = f"\n\n🔍 **Detalle técnico**: {str(variables['query_result']['error'])[:100]}..."
            
            return f"{template}{db_info}{sql_error}"
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error personalizando fallback de BD: {e}")
            return template
    
    def _customize_execution_fallback(
        self, 
        template: str, 
        execution_results: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """🔧 FASE 11: Personalizar fallback de ejecución"""
        try:
            # Buscar detalles del error de ejecución
            error_details = ""
            if "error" in execution_results:
                error_msg = str(execution_results["error"])
                if len(error_msg) > 50:
                    error_msg = error_msg[:50] + "..."
                error_details = f"\n\n🔍 **Error detectado**: {error_msg}"
            
            # Añadir información de contexto si está disponible
            context_info = ""
            if context and "function_name" in context:
                context_info = f"\n\n⚙️ **Función**: {context['function_name']}"
            
            return f"{template}{error_details}{context_info}"
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error personalizando fallback de ejecución: {e}")
            return template
    
    def _customize_context_fallback(
        self, 
        template: str, 
        execution_results: Dict[str, Any], 
        user_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """🔧 FASE 11: Personalizar fallback de contexto"""
        try:
            # Analizar qué contexto falta
            missing_context = []
            
            if context:
                if not context.get("databases"):
                    missing_context.append("bases de datos")
                if not context.get("apps"):
                    missing_context.append("aplicaciones")
                if not context.get("functions"):
                    missing_context.append("funciones disponibles")
            
            if missing_context:
                context_info = f"\n\n📚 **Contexto faltante**: {', '.join(missing_context)}"
                return f"{template}{context_info}"
            
            return template
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error personalizando fallback de contexto: {e}")
            return template
    
    def _customize_validation_fallback(
        self, 
        template: str, 
        execution_results: Dict[str, Any], 
        user_message: str
    ) -> str:
        """🔧 FASE 11: Personalizar fallback de validación"""
        try:
            # Sugerir alternativas basadas en el mensaje del usuario
            suggestions = []
            
            if "base de datos" in user_message.lower() or "database" in user_message.lower():
                suggestions.append("• Especificar el nombre de la tabla o columna")
                suggestions.append("• Usar términos más específicos")
                suggestions.append("• Verificar la ortografía de los nombres")
            
            if suggestions:
                suggestions_text = "\n\n💡 **Sugerencias**:\n" + "\n".join(suggestions)
                return f"{template}{suggestions_text}"
            
            return template
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error personalizando fallback de validación: {e}")
            return template
    
    def _customize_general_fallback(
        self, 
        template: str, 
        execution_results: Dict[str, Any], 
        user_message: str
    ) -> str:
        """🔧 FASE 11: Personalizar fallback general"""
        try:
            # Añadir contexto del mensaje del usuario
            user_context = f"\n\n💬 **Tu consulta**: {user_message[:100]}..."
            
            # Añadir información de pasos si existe
            steps_info = ""
            if "steps" in execution_results:
                steps = execution_results["steps"]
                if steps:
                    steps_info = f"\n\n📋 **Pasos ejecutados**: {len(steps)} paso(s) completado(s)"
            
            return f"{template}{user_context}{steps_info}"
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error personalizando fallback general: {e}")
            return template
    
    def _add_fallback_metadata(
        self, 
        response: str, 
        error_type: str, 
        execution_results: Dict[str, Any]
    ) -> str:
        """🔧 FASE 11: Añadir metadatos de fallback a la respuesta"""
        try:
            metadata = f"\n\n---\n🔧 **Información técnica**: Esta es una respuesta de fallback generada automáticamente debido a un error de tipo '{error_type}'. El equipo técnico ha sido notificado."
            
            # Añadir timestamp
            timestamp = datetime.now().isoformat()
            metadata += f"\n⏰ **Generado**: {timestamp}"
            
            # Añadir versión del fallback
            metadata += f"\n📦 **Versión**: Fase 11 - Fallback automático"
            
            return f"{response}{metadata}"
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error añadiendo metadatos: {e}")
            return response
    
    def should_use_fallback(self, execution_results: Dict[str, Any]) -> bool:
        """
        🔧 FASE 11: Determinar si se debe usar fallback.
        
        Args:
            execution_results: Resultados de la ejecución
            
        Returns:
            True si se debe usar fallback, False en caso contrario
        """
        try:
            # 🔧 FASE 11: Verificar si hay assistant_response válido
            if "assistant_response" in execution_results:
                response = execution_results["assistant_response"]
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Verificando assistant_response: '{response}' (tipo: {type(response)})")
                if response and str(response).strip():
                    logger.info(f"[FallbackResponseService] 🔧 FASE 11: Respuesta válida encontrada, NO usar fallback")
                    return False  # Hay respuesta válida, no usar fallback
                else:
                    logger.info(f"[FallbackResponseService] 🔧 FASE 11: Respuesta vacía o nula, SÍ usar fallback")
                    return True  # Respuesta vacía o nula, SÍ usar fallback
            
            # 🔧 FASE 11: Verificar si hay errores
            if "error" in execution_results or "execution_error" in execution_results:
                logger.info(f"[FallbackResponseService] 🔧 FASE 11: Error encontrado, SÍ usar fallback")
                return True
            
            # 🔧 FASE 11: Verificar si hay variables con errores
            if "variables" in execution_results:
                variables = execution_results["variables"]
                for var_name, var_value in variables.items():
                    if "error" in str(var_value).lower():
                        logger.info(f"[FallbackResponseService] 🔧 FASE 11: Error en variables, SÍ usar fallback")
                        return True
            
            # 🔧 FASE 11: Verificar si hay pasos fallidos
            if "steps" in execution_results:
                steps = execution_results["steps"]
                for step in steps:
                    if step.get("status") == "error":
                        logger.info(f"[FallbackResponseService] 🔧 FASE 11: Paso fallido, SÍ usar fallback")
                        return True
            
            logger.info(f"[FallbackResponseService] 🔧 FASE 11: No se encontraron errores, NO usar fallback")
            return False
            
        except Exception as e:
            logger.warning(f"[FallbackResponseService] Error verificando si usar fallback: {e}")
            return True  # Por defecto, usar fallback si hay error
