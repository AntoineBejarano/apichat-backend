# app/utils/response_normalizer.py
"""
🔧 FASE 10: Utilidades para normalización de respuestas y serialización segura
"""

import json
import logging
from typing import Any, Dict, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)


def normalize_assistant_response(response: Any, max_length: int = 1000) -> str:
    """
    🔧 FASE 10: Normalizar assistant_response a string consistente.
    
    Args:
        response: Respuesta del asistente (puede ser string, dict, o cualquier tipo)
        max_length: Longitud máxima permitida para la respuesta
        
    Returns:
        String normalizado y consistente
    """
    try:
        if response is None:
            return "🤖 No se generó respuesta"
        
        # Si ya es string, normalizarlo
        if isinstance(response, str):
            normalized = response.strip()
            if not normalized:
                return "🤖 Respuesta vacía"
            # Truncar si es muy largo
            if len(normalized) > max_length:
                normalized = normalized[:max_length] + "..."
            return normalized
        
        # Si es dict, buscar campos útiles
        if isinstance(response, dict):
            # Priorizar campos específicos
            for field in ["content", "message", "text", "answer", "response"]:
                if field in response and response[field]:
                    content = response[field]
                    if isinstance(content, str) and content.strip():
                        normalized = content.strip()
                        if len(normalized) > max_length:
                            normalized = normalized[:max_length] + "..."
                        return normalized
            
            # Si no hay campos específicos, convertir todo el dict
            try:
                json_str = json.dumps(response, ensure_ascii=False, default=str)
                if len(json_str) > max_length:
                    json_str = json_str[:max_length] + "..."
                return json_str
            except Exception as e:
                logger.warning(f"[ResponseNormalizer] Error serializando dict: {e}")
                return str(response)[:max_length]
        
        # Si es lista, mostrar elementos principales
        if isinstance(response, list):
            if not response:
                return "📋 Lista vacía"
            # Mostrar solo los primeros elementos
            limited = response[:3]
            result = f"📋 Lista con {len(response)} elementos: {limited}"
            if len(response) > 3:
                result += f" ... y {len(response) - 3} más"
            if len(result) > max_length:
                result = result[:max_length] + "..."
            return result
        
        # Para otros tipos, convertir a string
        result = str(response)
        if len(result) > max_length:
            result = result[:max_length] + "..."
        return result
        
    except Exception as e:
        logger.error(f"[ResponseNormalizer] Error normalizando respuesta: {e}")
        return f"🤖 Error procesando respuesta: {str(e)[:100]}"


def safe_serialize_result(result: Any, max_length: int = 500) -> str:
    """
    🔧 FASE 10: Serialización segura de resultados para logging.
    
    Args:
        result: Resultado a serializar
        max_length: Longitud máxima del resultado serializado
        
    Returns:
        String serializado de forma segura
    """
    try:
        if result is None:
            return "null"
        
        # Si ya es string, truncar si es necesario
        if isinstance(result, str):
            if len(result) <= max_length:
                return result
            return result[:max_length] + "..."
        
        # Intentar serializar a JSON
        try:
            json_str = json.dumps(result, ensure_ascii=False, default=str)
            if len(json_str) <= max_length:
                return json_str
            return json_str[:max_length] + "..."
        except (TypeError, ValueError):
            # Si falla JSON, usar str
            str_result = str(result)
            if len(str_result) <= max_length:
                return str_result
            return str_result[:max_length] + "..."
            
    except Exception as e:
        logger.error(f"[ResponseNormalizer] Error en serialización segura: {e}")
        return f"<error_serializing: {str(e)[:50]}>"


def validate_response_structure(response: Dict[str, Any]) -> Dict[str, Any]:
    """
    🔧 FASE 10: Validar y normalizar estructura de respuesta completa.
    
    Args:
        response: Respuesta completa del sistema
        
    Returns:
        Respuesta normalizada y validada
    """
    try:
        normalized = response.copy()
        
        # 🔧 FASE 10: Normalizar assistant_response
        if "assistant_response" in normalized:
            normalized["assistant_response"] = normalize_assistant_response(
                normalized["assistant_response"]
            )
        
        # 🔧 FASE 10: Normalizar otros campos de respuesta
        for field in ["message", "content", "response"]:
            if field in normalized:
                normalized[field] = normalize_assistant_response(
                    normalized[field]
                )
        
        # 🔧 FASE 10: Validar que hay al menos una respuesta
        has_response = any(
            field in normalized and normalized[field] 
            for field in ["assistant_response", "message", "content", "response"]
        )
        
        if not has_response:
            normalized["assistant_response"] = "🤖 No se pudo generar una respuesta válida"
            logger.warning("[ResponseNormalizer] Respuesta sin contenido válido, usando fallback")
        
        # 🔧 FASE 10: Añadir timestamp de normalización
        normalized["_normalized_at"] = datetime.now().isoformat()
        normalized["_normalization_version"] = "fase10"
        
        return normalized
        
    except Exception as e:
        logger.error(f"[ResponseNormalizer] Error validando estructura: {e}")
        return {
            "assistant_response": "🤖 Error interno procesando respuesta",
            "error": str(e),
            "_normalized_at": datetime.now().isoformat(),
            "_normalization_version": "fase10_error"
        }


def truncate_long_content(content: Any, max_length: int = 300) -> str:
    """
    🔧 FASE 10: Truncar contenido largo para logging y debugging.
    
    Args:
        content: Contenido a truncar
        max_length: Longitud máxima permitida
        
    Returns:
        Contenido truncado
    """
    try:
        if content is None:
            return "null"
        
        content_str = str(content)
        if len(content_str) <= max_length:
            return content_str
        
        # Truncar y añadir indicador
        truncated = content_str[:max_length]
        if truncated.endswith("..."):
            return truncated
        return truncated + "..."
        
    except Exception as e:
        logger.error(f"[ResponseNormalizer] Error truncando contenido: {e}")
        return f"<truncation_error: {str(e)[:50]}>"

