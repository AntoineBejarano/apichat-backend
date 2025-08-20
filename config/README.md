# 🔧 Sistema de Configuración de Sinónimos - Fast Schema Path

## 📋 Descripción

Este directorio contiene la configuración del sistema de sinónimos para el **Fast Schema Path**, que permite respuestas rápidas a preguntas sobre bases de datos sin usar LLM.

## 🗂️ Archivos de Configuración

### 1. `synonyms_config.json` - Configuración Principal
- **Propósito**: Configuración general del sistema
- **Contiene**: Umbrales de confianza, TTL de cache, archivos referenciados
- **Modo de uso**: Configuración del sistema, no modificar manualmente

### 2. `synonyms.json` - Sinónimos Generales
- **Propósito**: Sinónimos para campos y tablas comunes
- **Secciones**:
  - `field_synonyms`: Sinónimos para campos (email, user, name, etc.)
  - `table_synonyms`: Sinónimos para tablas (users, products, orders, etc.)

### 3. `translations.json` - Traducciones por Idioma
- **Propósito**: Traducciones entre español e inglés
- **Secciones**:
  - `es_to_en`: Español → Inglés
  - `en_to_es`: Inglés → Español

### 4. `domain_synonyms.json` - Sinónimos por Dominio
- **Propósito**: Sinónimos específicos por tipo de negocio
- **Dominios disponibles**:
  - `ecommerce`: Comercio electrónico
  - `crm`: Gestión de relaciones con clientes
  - `hr`: Recursos humanos
  - `finance`: Finanzas
  - `inventory`: Inventario

## 🚀 Cómo Añadir Nuevos Sinónimos

### Añadir un Nuevo Campo

```json
// En synonyms.json, sección field_synonyms
"new_field": [
  "nuevo_campo",
  "campo_nuevo", 
  "nuevo_atributo"
]
```

### Añadir una Nueva Traducción

```json
// En translations.json, sección es_to_en
"nuevo_termino": "new_term"

// En translations.json, sección en_to_es  
"new_term": "nuevo_termino"
```

### Añadir un Nuevo Dominio

```json
// En domain_synonyms.json
"new_domain": {
  "table_name": [
    "nombre_tabla",
    "tabla_nombre",
    "entidad_nombre"
  ]
}
```

## 🔄 Recarga de Configuración

El sistema recarga automáticamente las configuraciones cada 5 minutos, o cuando detecta cambios en los archivos.

Para recarga manual:

```python
from app.services.context.synonyms_config_service import SynonymsConfigService

service = SynonymsConfigService()
service.reload_configs()
```

## ✅ Validación de Configuración

Para validar que todos los archivos JSON son correctos:

```bash
python scripts/validate_synonyms_config.py
```

## 📊 Estadísticas del Sistema

Para obtener estadísticas de la configuración cargada:

```python
from app.services.context.synonyms_config_service import SynonymsConfigService

service = SynonymsConfigService()
stats = service.get_config_stats()
print(stats)
```

## 🎯 Ejemplos de Uso

### Ejemplo 1: Usuario pregunta en español
**Pregunta**: "¿Dónde está el campo correo electrónico?"
**Sistema**:
1. Detecta idioma español
2. Traduce "correo electrónico" → "email"
3. Busca "email" en el índice léxico
4. Encuentra coincidencia → Respuesta rápida

### Ejemplo 2: Usuario pregunta sobre dominio específico
**Pregunta**: "¿Dónde están los productos disponibles?"
**Sistema**:
1. Identifica "productos" como término de e-commerce
2. Busca sinónimos: "products", "articulos", "items"
3. Encuentra tabla "products" → Respuesta rápida

## ⚠️ Consideraciones Importantes

1. **No modificar** `synonyms_config.json` manualmente
2. **Mantener** estructura JSON válida
3. **Usar** encoding UTF-8 para caracteres especiales
4. **Validar** cambios con el script de validación
5. **Backup** configuraciones antes de cambios masivos

## 🆘 Solución de Problemas

### Error: "Archivo no encontrado"
- Verificar que el archivo existe en el directorio `config/`
- Verificar permisos de lectura

### Error: "JSON inválido"
- Usar el script de validación: `python scripts/validate_synonyms_config.py`
- Verificar sintaxis JSON con un editor que valide JSON

### Error: "Sinónimos no encontrados"
- Verificar que el término esté en la configuración correcta
- Verificar que no haya errores de tipeo
- Recargar configuración manualmente

## 📈 Métricas de Rendimiento

- **Tiempo de carga**: <100ms
- **Tiempo de búsqueda**: <50ms
- **Cache TTL**: 5 minutos (configurable)
- **Umbral de confianza**: 0.7 (configurable)

## 🔗 Integración con el Sistema

El `SynonymsConfigService` se integra automáticamente con:
- `SchemaExplorerService`: Para búsquedas léxicas
- `LanguageDetectionService`: Para detección de idioma
- `OrchestratorService`: Para el flujo principal

## 📝 Notas de Desarrollo

- **Versión actual**: 1.0.0
- **Última actualización**: 2025-08-20
- **Mantenido por**: Equipo de desarrollo APIchat
- **Compatibilidad**: Python 3.8+
