"""
📝 FASE 8: Prompt Template Service - Gestión de Prompts Configurables
────────────────────────────────────────────────────────────────────────
Implementa:
- Renderizado de prompts con variables
- Gestión de versiones de prompts
- Caché y optimización de prompts
- Validación de prompts
"""

import re
import logging
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from pathlib import Path
import yaml
import json

from .prompt_registry import PromptKey, PromptRegistry, prompt_registry

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """Template de un prompt con metadatos"""
    key: str
    version: str
    template: str
    variables: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: float
    updated_at: float


@dataclass
class PromptContext:
    """Contexto para renderizar un prompt"""
    prompt_key: str
    variables: Dict[str, Any]
    version: Optional[str] = None
    environment: str = "production"
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None


class PromptTemplateService:
    """
    📝 Servicio de templates de prompts para la Fase 8
    
    Implementa:
    - Renderizado de prompts con variables
    - Gestión de versiones
    - Caché inteligente
    - Validación de prompts
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "./config/prompts.yaml"
        self.prompt_registry = prompt_registry
        
        # Caché de prompts
        self._prompt_cache: Dict[str, PromptTemplate] = {}
        self._cache_ttl = 300  # 5 minutos
        self._last_cache_cleanup = time.time()
        
        # Configuración de prompts
        self._prompt_configs: Dict[str, Dict] = {}
        self._default_prompts: Dict[str, str] = {}
        
        # Cargar configuración
        self._load_configuration()
        
        logger.info(f"[PromptTemplateService] Inicializado con {len(self._prompt_configs)} configuraciones")
    
    def _load_configuration(self):
        """Carga la configuración de prompts desde archivo"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self._prompt_configs = config.get('prompts', {})
                    self._default_prompts = config.get('defaults', {})
                    logger.info(f"[PromptTemplateService] Configuración cargada desde {self.config_path}")
            else:
                logger.warning(f"[PromptTemplateService] Archivo de configuración no encontrado: {self.config_path}")
                self._load_default_prompts()
        except Exception as e:
            logger.error(f"[PromptTemplateService] Error cargando configuración: {e}")
            self._load_default_prompts()
    
    def _load_default_prompts(self):
        """Carga prompts por defecto hardcodeados"""
        self._default_prompts = {
            "schema_extraction": """
Analiza el esquema de la base de datos {db_name} y extrae la siguiente información:

**ESTRUCTURA DE TABLAS:**
- Nombre de cada tabla
- Columnas y sus tipos de datos
- Claves primarias y foráneas
- Índices y constraints

**RELACIONES:**
- Dependencias entre tablas
- Cardinalidad de relaciones
- Integridad referencial

**CONTEXTO:**
Base de datos: {connection_info}
Nivel de detalle: {extraction_level}
Contexto de negocio: {business_context}

Genera un análisis estructurado y detallado del esquema.
""",
            "sql_generation": """
Genera una consulta SQL SELECT segura y eficiente para la siguiente consulta:

**CONSULTA DEL USUARIO:**
{user_query}

**ESQUEMA DISPONIBLE:**
{schema_info}

**REGLAS DE SEGURIDAD:**
- Solo operaciones SELECT permitidas
- Límite máximo: {max_rows} filas
- Timeout: {timeout_seconds} segundos
- Schemas permitidos: {allowed_schemas}

**ESTILO PREFERIDO:**
{preferred_style}

Genera SQL válido, seguro y optimizado.
""",
            "intent_classification": """
Clasifica la intención de la siguiente consulta del usuario:

**CONSULTA:**
{user_query}

**CONTEXTO DISPONIBLE:**
- Esquema de base de datos
- Historial de consultas del usuario
- Contexto de la sesión

**CATEGORÍAS POSIBLES:**
1. **STRUCTURED**: Consulta específica sobre datos estructurados
2. **DIFFUSE**: Consulta general o conversacional
3. **ANALYTICAL**: Consulta analítica o de reportes
4. **EXPLORATORY**: Exploración del esquema o datos

**RESPUESTA:**
Proporciona la categoría más apropiada y justifica tu elección.
"""
        }
        
        logger.info(f"[PromptTemplateService] Cargados {len(self._default_prompts)} prompts por defecto")
    
    def get_prompt(self, prompt_key: str, context: PromptContext) -> str:
        """
        📝 Obtiene un prompt renderizado
        
        Args:
            prompt_key: Clave del prompt
            context: Contexto para renderizar
            
        Returns:
            Prompt renderizado con variables
        """
        start_time = time.time()
        
        try:
            # Validar clave del prompt
            if not self.prompt_registry.validate_prompt_key(prompt_key):
                raise ValueError(f"Clave de prompt inválida: {prompt_key}")
            
            # Obtener template
            template = self._get_prompt_template(prompt_key, context.version)
            
            # Renderizar prompt
            rendered_prompt = self._render_template_robust(template, context.variables)
            
            # Logging de métricas
            render_time = (time.time() - start_time) * 1000
            logger.info(f"[PromptTemplateService] Prompt '{prompt_key}' renderizado en {render_time:.2f}ms")
            
            return rendered_prompt
            
        except Exception as e:
            logger.error(f"[PromptTemplateService] Error renderizando prompt '{prompt_key}': {e}")
            # Fallback a prompt por defecto
            return self._get_fallback_prompt(prompt_key, context)
    
    def _get_prompt_template(self, prompt_key: str, version: Optional[str] = None) -> str:
        """Obtiene el template de un prompt"""
        cache_key = f"{prompt_key}:{version or 'default'}"
        
        # Verificar caché
        if cache_key in self._prompt_cache:
            cached = self._prompt_cache[cache_key]
            if time.time() - cached.updated_at < self._cache_ttl:
                return cached.template
        
        # Obtener desde configuración
        template = self._load_template_from_config(prompt_key, version)
        
        # Actualizar caché
        self._prompt_cache[cache_key] = PromptTemplate(
            key=prompt_key,
            version=version or "default",
            template=template,
            variables={},
            metadata={},
            created_at=time.time(),
            updated_at=time.time()
        )
        
        return template
    
    def _load_template_from_config(self, prompt_key: str, version: Optional[str] = None) -> str:
        """Carga template desde configuración"""
        # Intentar desde archivo de configuración
        if prompt_key in self._prompt_configs:
            prompt_config = self._prompt_configs[prompt_key]
            
            if version and version in prompt_config.get("versions", {}):
                return prompt_config["versions"][version]
            elif "default" in prompt_config:
                return prompt_config["default"]
        
        # Fallback a prompts por defecto
        if prompt_key in self._default_prompts:
            return self._default_prompts[prompt_key]
        
        # Prompt genérico si no se encuentra
        return f"Prompt no configurado para: {prompt_key}"
    
    def _render_template(self, template: str, variables: Dict[str, Any]) -> str:
        """Renderiza un template con variables"""
        try:
            # Renderizado simple con str.format
            return template.format(**variables)
        except KeyError as e:
            # Variable faltante, reemplazar con placeholder
            missing_var = str(e).strip("'")
            logger.warning(f"[PromptTemplateService] Variable faltante en template: {missing_var}")
            # Reemplazar todas las ocurrencias de la variable faltante
            template = template.replace(f"{{{missing_var}}}", f"[{missing_var}_NO_DISPONIBLE]")
            # Intentar renderizar de nuevo con las variables restantes
            try:
                return template.format(**variables)
            except KeyError as e2:
                # Otra variable faltante, continuar reemplazando
                missing_var2 = str(e2).strip("'")
                logger.warning(f"[PromptTemplateService] Variable faltante adicional: {missing_var2}")
                template = template.replace(f"{{{missing_var2}}}", f"[{missing_var2}_NO_DISPONIBLE]")
                # Intentar una vez más
                try:
                    return template.format(**variables)
                except:
                    return template
            except Exception:
                return template
        except Exception as e:
            logger.error(f"[PromptTemplateService] Error renderizando template: {e}")
            return template
    
    def _render_template_robust(self, template: str, variables: Dict[str, Any]) -> str:
        """Renderizado robusto que maneja múltiples variables faltantes"""
        try:
            # Intentar renderizado directo primero
            return template.format(**variables)
        except KeyError:
            # Hay variables faltantes, reemplazarlas todas
            import re
            variable_pattern = r'\{([^}]+)\}'
            variables_in_template = re.findall(variable_pattern, template)
            
            # Crear una copia del template para modificarla
            modified_template = template
            
            # Reemplazar todas las variables faltantes
            for var_name in variables_in_template:
                if var_name not in variables:
                    placeholder = f"[{var_name}_NO_DISPONIBLE]"
                    modified_template = modified_template.replace(f"{{{var_name}}}", placeholder)
                    logger.warning(f"[PromptTemplateService] Variable faltante reemplazada: {var_name}")
            
            # Ahora intentar renderizar con las variables disponibles
            try:
                return modified_template.format(**variables)
            except Exception as e:
                logger.error(f"[PromptTemplateService] Error en renderizado final: {e}")
                return modified_template
        except Exception as e:
            logger.error(f"[PromptTemplateService] Error en renderizado robusto: {e}")
            return template
    
    def _get_fallback_prompt(self, prompt_key: str, context: PromptContext) -> str:
        """Obtiene un prompt de fallback"""
        fallback_templates = {
            "schema_extraction": "Analiza el esquema de la base de datos {db_name}.",
            "sql_generation": "Genera SQL para: {user_query}",
            "intent_classification": "Clasifica la intención de: {user_query}"
        }
        
        fallback = fallback_templates.get(prompt_key, f"Prompt de fallback para: {prompt_key}")
        
        try:
            return fallback.format(**context.variables)
        except:
            return fallback
    
    def update_prompt(self, prompt_key: str, template: str, version: str = "default") -> bool:
        """
        🔄 Actualiza un prompt en tiempo real
        
        Args:
            prompt_key: Clave del prompt
            template: Nuevo template
            version: Versión del prompt
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Validar prompt
            if not self._validate_prompt_template(template):
                raise ValueError("Template de prompt inválido")
            
            # Actualizar caché
            cache_key = f"{prompt_key}:{version}"
            self._prompt_cache[cache_key] = PromptTemplate(
                key=prompt_key,
                version=version,
                template=template,
                variables={},
                metadata={},
                created_at=time.time(),
                updated_at=time.time()
            )
            
            logger.info(f"[PromptTemplateService] Prompt '{prompt_key}' v{version} actualizado")
            return True
            
        except Exception as e:
            logger.error(f"[PromptTemplateService] Error actualizando prompt '{prompt_key}': {e}")
            return False
    
    def _validate_prompt_template(self, template: str) -> bool:
        """Valida un template de prompt"""
        if not template or len(template.strip()) == 0:
            return False
        
        # Verificar variables válidas (formato {variable})
        variable_pattern = r'\{([^}]+)\}'
        variables = re.findall(variable_pattern, template)
        
        # Validar que las variables no contengan caracteres peligrosos
        for var in variables:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
                return False
        
        return True
    
    def get_prompt_versions(self, prompt_key: str) -> List[str]:
        """Obtiene las versiones disponibles de un prompt"""
        versions = ["default"]
        
        if prompt_key in self._prompt_configs:
            prompt_config = self._prompt_configs[prompt_key]
            if "versions" in prompt_config:
                versions.extend(list(prompt_config["versions"].keys()))
        
        return versions
    
    def get_prompt_info(self, prompt_key: str) -> Dict[str, Any]:
        """Obtiene información detallada de un prompt"""
        try:
            key_enum = PromptKey(prompt_key)
            return self.prompt_registry.get_prompt_info(key_enum)
        except ValueError:
            return {"error": f"Prompt key inválida: {prompt_key}"}
    
    def clear_cache(self):
        """Limpia el caché de prompts"""
        self._prompt_cache.clear()
        self._last_cache_cleanup = time.time()
        logger.info("[PromptTemplateService] Caché limpiado")
    
    def get_service_summary(self) -> Dict[str, Any]:
        """Obtiene un resumen del servicio"""
        return {
            "service_name": "PromptTemplateService",
            "prompts_configured": len(self._prompt_configs),
            "default_prompts": len(self._default_prompts),
            "cache_size": len(self._prompt_cache),
            "cache_ttl_seconds": self._cache_ttl,
            "registry_summary": self.prompt_registry.get_registry_summary(),
            "service_version": "1.0.0"
        }
