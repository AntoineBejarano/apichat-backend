"""
ResponseFormatter - Formateador de Respuestas
─────────────────────────────────────────────
Formatea y procesa respuestas del asistente y resultados de ejecución.
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Formateador de respuestas para el asistente y resultados de ejecución.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def format_step_response(
        self, 
        assistant_response: str, 
        steps: List[Any], 
        execution_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Formatea una respuesta tipo "step" para el websocket.
        
        Args:
            assistant_response: Respuesta del asistente
            steps: Lista de pasos de ejecución
            execution_results: Resultados de la ejecución
            
        Returns:
            Dict con respuesta formateada tipo "step"
        """
        final_response = {
            "type": "step",
            "message": assistant_response,
            "steps": steps,
            "execution_results": execution_results,
            "formatted": True,
            "timestamp": datetime.now().isoformat()
        }
        
        self.logger.info(f"[ResponseFormatter] 🎯 Respuesta tipo 'step' formateada")
        self.logger.info(f"[ResponseFormatter] 🎯 MESSAGE field: '{final_response['message']}' (tipo: {type(final_response['message'])})")
        self.logger.info(f"[ResponseFormatter] 🎯 STEPS count: {len(final_response['steps'])}")
        self.logger.info(f"[ResponseFormatter] 🎯 EXECUTION_RESULTS keys: {list(final_response['execution_results'].keys())}")
        
        return final_response
    
    def format_normal_response(
        self, 
        assistant_response: str, 
        execution_results: Dict[str, Any], 
        steps: List[Any]
    ) -> Dict[str, Any]:
        """
        Formatea una respuesta normal (sin steps).
        
        Args:
            assistant_response: Respuesta del asistente
            execution_results: Resultados de la ejecución
            steps: Lista de pasos (puede estar vacía)
            
        Returns:
            Dict con respuesta formateada normal
        """
        final_response = {
            "assistant_response": assistant_response,
            "execution_results": execution_results,
            "steps": steps,
        }
        
        self.logger.info(f"[ResponseFormatter] 🎯 Respuesta normal formateada: {final_response}")
        return final_response
    
    def format_response_by_type(
        self, 
        assistant_response: str, 
        execution_results: Dict[str, Any], 
        steps: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Formatea la respuesta basándose en si hay steps o no.
        
        Args:
            assistant_response: Respuesta del asistente
            execution_results: Resultados de la ejecución
            steps: Lista de pasos (opcional)
            
        Returns:
            Dict con respuesta formateada según el tipo
        """
        if steps and len(steps) > 0:
            return self.format_step_response(assistant_response, steps, execution_results)
        else:
            return self.format_normal_response(assistant_response, execution_results, steps or [])
    
    def extract_assistant_response(self, execution_results: Dict[str, Any]) -> str:
        """
        Extrae la respuesta del asistente de los resultados de ejecución.
        
        Args:
            execution_results: Resultados de la ejecución
            
        Returns:
            String con la respuesta del asistente
        """
        # 🔧 FIX: Buscar en variables primero (nuevo campo)
        if execution_results.get("variables"):
            variables = execution_results.get("variables", {})
            for var_name, var_value in variables.items():
                if isinstance(var_value, str) and len(var_value.strip()) > 10:
                    # Verificar que no sea el mensaje del usuario
                    if not any(user_indicator in var_value.lower() for user_indicator in ["tu pregunta", "responder a", "para responder"]):
                        logger.info(f"[ResponseFormatter] ✅ Encontrada respuesta en variables['{var_name}'] (longitud: {len(var_value)} chars)")
                        return str(var_value)
                    else:
                        logger.debug(f"[ResponseFormatter] ⚠️ Variable '{var_name}' parece ser del usuario, saltando")
        
        # 🔧 FIX: Si hay steps, generar respuesta basada en steps pero SIN usar message del usuario
        if execution_results.get("steps"):
            steps = execution_results.get("steps", [])
            logger.info(f"[ResponseFormatter] 📋 Encontrados {len(steps)} steps en el plan")
            logger.info(f"[ResponseFormatter] 📋 Contenido de steps: {steps}")
            
            # Buscar en steps por contenido útil, evitando mensajes del usuario
            for i, step in enumerate(steps):
                logger.info(f"[ResponseFormatter] 🔍 Procesando step {i}: {step}")
                if isinstance(step, dict):
                    # Buscar en campos del step que NO sean message (que puede ser del usuario)
                    for step_key in ["content", "result", "output", "data"]:
                        if step_key in step and step[step_key]:
                            step_content = step[step_key]
                            logger.info(f"[ResponseFormatter] 🔍 Encontrado contenido en step[{i}].{step_key}: {step_content}")
                            if isinstance(step_content, str) and len(step_content.strip()) > 10:
                                # Verificar que no sea el mensaje del usuario
                                if not any(user_indicator in step_content.lower() for user_indicator in ["tu pregunta", "responder a", "para responder"]):
                                    logger.info(f"[ResponseFormatter] ✅ Encontrada respuesta en step[{i}]['{step_key}'] (longitud: {len(step_content)} chars)")
                                    return str(step_content)
                                else:
                                    logger.info(f"[ResponseFormatter] ⚠️ Contenido del step parece ser del usuario, saltando")
            
            # Si no hay contenido útil en steps, generar mensaje genérico
            logger.info(f"[ResponseFormatter] 📋 Steps encontrados pero sin contenido útil, generando mensaje genérico")
            return "Consultando base de datos..."
        else:
            logger.info(f"[ResponseFormatter] 🔍 NO hay steps en execution_results")
        
        # 🔧 FIX: Buscar en otros campos posibles (excluyendo message que es del usuario)
        for key in ["content", "output", "result", "answer"]:
            if key in execution_results and execution_results[key]:
                response_value = execution_results[key]
                logger.info(f"[ResponseFormatter] 🔍 Encontrado campo '{key}': {response_value}")
                if isinstance(response_value, dict) and 'content' in response_value:
                    actual_response = response_value['content']
                    logger.info(f"[ResponseFormatter] ✅ Encontrada respuesta en '{key}.content' (longitud: {len(str(actual_response))} chars)")
                    return str(actual_response)
                else:
                    response_length = len(str(response_value))
                    logger.info(f"[ResponseFormatter] ✅ Encontrada respuesta en '{key}' (longitud: {response_length} chars)")
                    return str(response_value)
        
        # Si hay error, devolver mensaje de error
        if "error" in execution_results:
            logger.error(f"[ResponseFormatter] ❌ Error encontrado: {execution_results['error']}")
            return f"❌ Error: {execution_results['error']}"
        
        # Si hay execution_error, devolver mensaje de error
        if "execution_error" in execution_results:
            logger.error(f"[ResponseFormatter] ❌ Error de ejecución: {execution_results['execution_error']}")
            return f"❌ Error de ejecución: {execution_results['execution_error']}"
        
        # Si no hay respuesta, devolver mensaje por defecto
        logger.warning("[ResponseFormatter] ⚠️ No se encontró respuesta en los resultados")
        logger.warning(f"[ResponseFormatter] ⚠️ Contenido completo de execution_results: {execution_results}")
        logger.warning("[ResponseFormatter] ⚠️ DEVOLVIENDO MENSAJE POR DEFECTO")
        return "🤖 No se pudo generar una respuesta"
    
    def format_results_for_final_answer(self, results: Dict[str, Any]) -> str:
        """
        Formatea los resultados para la respuesta final.
        
        Args:
            results: Resultados a formatear
            
        Returns:
            String formateado con los resultados
        """
        if not results:
            return "No se encontró información específica en la base de datos."
        
        lines = []
        for key, value in results.items():
            if isinstance(value, (dict, list)):
                # Para estructuras complejas, mostrar resumen
                if isinstance(value, list):
                    lines.append(f"- {key}: {len(value)} elementos encontrados")
                else:
                    lines.append(f"- {key}: {len(value)} campos disponibles")
            else:
                # Para valores simples, mostrar directamente
                lines.append(f"- {key}: {value}")
        
        return "\n".join(lines)
    
    def calculate_content_length(self, data: Dict[str, Any]) -> int:
        """
        Calcula la longitud del contenido de forma segura.
        
        Args:
            data: Datos a medir
            
        Returns:
            Longitud del contenido en caracteres
        """
        try:
            if isinstance(data, dict):
                # Para diccionarios, sumar longitudes de valores string
                total_length = 0
                for key, value in data.items():
                    if isinstance(value, str):
                        total_length += len(value)
                    elif isinstance(value, (dict, list)):
                        total_length += self.calculate_content_length(value)
                return total_length
            elif isinstance(data, list):
                # Para listas, sumar longitudes de elementos
                return sum(self.calculate_content_length(item) for item in data)
            elif isinstance(data, str):
                # Para strings, devolver longitud directa
                return len(data)
            else:
                # Para otros tipos, convertir a string y medir
                return len(str(data))
        except Exception as e:
            logger.warning(f"[ResponseFormatter] Error calculando longitud de contenido: {e}")
            return 0
