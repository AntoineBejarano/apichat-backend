"""
Response Processor Module
────────────────────────
Maneja la extracción y procesamiento de respuestas del orchestrator.
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ResponseProcessor:
    """
    Procesa y extrae respuestas de los resultados de ejecución del orchestrator.
    """
    
    @staticmethod
    def extract_assistant_response(execution_results: Dict[str, Any]) -> str:
        """
        Extrae la respuesta del asistente de los resultados de ejecución.
        
        Args:
            execution_results: Resultados de la ejecución del plan
            
        Returns:
            Respuesta del asistente como string
        """
        logger.info(f"[ResponseProcessor] 🔍 Procesando execution_results: {execution_results}")
        
        # 🔧 FIX: Si hay steps, generar respuesta basada en steps pero SIN usar message del usuario
        if execution_results.get("steps"):
            steps = execution_results.get("steps", [])
            logger.info(f"[ResponseProcessor] 📋 Encontrados {len(steps)} steps en el plan")
            logger.info(f"[ResponseProcessor] 📋 Contenido de steps: {steps}")
            
            # Buscar en steps por contenido útil, evitando mensajes del usuario
            for i, step in enumerate(steps):
                logger.info(f"[ResponseProcessor] 🔍 Procesando step {i}: {step}")
                if isinstance(step, dict):
                    # Buscar en campos del step que NO sean message (que puede ser del usuario)
                    for step_key in ["content", "result", "output", "data"]:
                        if step_key in step and step[step_key]:
                            step_content = step[step_key]
                            logger.info(f"[ResponseProcessor] 🔍 Encontrado contenido en step[{i}].{step_key}: {step_content}")
                            if isinstance(step_content, str) and len(step_content.strip()) > 10:
                                # Verificar que no sea el mensaje del usuario
                                if not any(user_indicator in step_content.lower() for user_indicator in ["tu pregunta", "responder a", "para responder"]):
                                    logger.info(f"[ResponseProcessor] ✅ Encontrada respuesta en step[{i}]['{step_key}'] (longitud: {len(step_content)} chars)")
                                    return str(step_content)
                                else:
                                    logger.info(f"[ResponseProcessor] ⚠️ Contenido del step parece ser del usuario, saltando")
            
            # Si no hay contenido útil en steps, generar mensaje genérico
            logger.info(f"[ResponseProcessor] 📋 Steps encontrados pero sin contenido útil, generando mensaje genérico")
            return "Consultando base de datos..."
        
        # 🔧 FIX: Buscar en otros campos posibles (excluyendo message que es del usuario)
        for key in ["content", "output", "result", "answer"]:
            if key in execution_results and execution_results[key]:
                response_value = execution_results[key]
                logger.info(f"[ResponseProcessor] 🔍 Encontrado campo '{key}': {response_value}")
                if isinstance(response_value, dict) and 'content' in response_value:
                    actual_response = response_value['content']
                    logger.info(f"[ResponseProcessor] ✅ Encontrada respuesta en '{key}.content' (longitud: {len(str(actual_response))} chars)")
                    return str(actual_response)
                else:
                    response_length = len(str(response_value))
                    logger.info(f"[ResponseProcessor] ✅ Encontrada respuesta en '{key}' (longitud: {response_length} chars)")
                    return str(response_value)
        
        # Si hay error, devolver mensaje de error
        if "error" in execution_results:
            logger.error(f"[ResponseProcessor] ❌ Error encontrado: {execution_results['error']}")
            return f"❌ Error: {execution_results['error']}"
        
        # Si hay execution_error, devolver mensaje de error
        if "execution_error" in execution_results:
            logger.error(f"[ResponseProcessor] ❌ Error de ejecución: {execution_results['execution_error']}")
            return f"❌ Error de ejecución: {execution_results['execution_error']}"
        
        # Si no hay respuesta, devolver mensaje por defecto
        logger.warning("[ResponseProcessor] ⚠️ No se encontró respuesta en los resultados")
        logger.warning(f"[ResponseProcessor] ⚠️ Contenido completo de execution_results: {execution_results}")
        logger.warning("[ResponseProcessor] ⚠️ DEVOLVIENDO MENSAJE POR DEFECTO")
        return "🤖 No se pudo generar una respuesta"
    
    @staticmethod
    def format_results_for_final_answer(results: Dict[str, Any]) -> str:
        """
        Formatea los resultados para la respuesta final.
        
        Args:
            results: Resultados a formatear
            
        Returns:
            Resultados formateados como string
        """
        try:
            if not results:
                return "No se encontraron resultados."
            
            # Si es un string, devolverlo directamente
            if isinstance(results, str):
                return results
            
            # Si es un diccionario, buscar campos útiles
            if isinstance(results, dict):
                # Buscar en campos específicos
                for key in ["content", "result", "output", "answer", "data"]:
                    if key in results and results[key]:
                        return str(results[key])
                
                # Si no hay campos específicos, convertir todo el diccionario
                return str(results)
            
            # Para otros tipos, convertir a string
            return str(results)
            
        except Exception as e:
            logger.error(f"[ResponseProcessor] Error formateando resultados: {e}")
            return f"Error formateando resultados: {str(e)}"
    
    @staticmethod
    def safe_sqlalchemy_to_dict(obj: Any) -> Dict[str, Any]:
        """
        Convierte objetos SQLAlchemy a diccionarios de forma segura.
        Maneja casos donde el objeto puede no tener ciertos atributos.
        
        Args:
            obj: Objeto a convertir
            
        Returns:
            Diccionario con los datos del objeto
        """
        try:
            if hasattr(obj, '__dict__'):
                # Objeto SQLAlchemy - extraer atributos
                result = {}
                for key, value in obj.__dict__.items():
                    # Ignorar atributos internos de SQLAlchemy
                    if not key.startswith('_'):
                        try:
                            # Convertir datetime a ISO string si es posible
                            if hasattr(value, 'isoformat'):
                                result[key] = value.isoformat()
                            else:
                                result[key] = value
                        except Exception:
                            # Si falla la conversión, usar string
                            result[key] = str(value)
                return result
            elif hasattr(obj, 'model_dump'):
                # Objeto Pydantic
                return obj.model_dump()
            elif isinstance(obj, dict):
                # Ya es un diccionario
                return obj
            else:
                # Otro tipo - convertir a string
                return {'value': str(obj)}
        except Exception as e:
            logger.warning(f"[ResponseProcessor] Error convirtiendo objeto a diccionario: {e}")
            return {'error': f'Error converting object: {str(e)}'}
