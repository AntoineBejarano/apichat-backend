# 🚀 Sistema de Triggering Automático de APIs

## 📋 Resumen

El sistema de triggering automático de APIs permite ejecutar funciones de API automáticamente basándose en queries en lenguaje natural, utilizando búsqueda vectorial y configuración personalizada por usuario.

## 🏗️ Arquitectura

### Componentes Principales

1. **ExtensibleEmbeddingService**: Sistema de embeddings extensible para múltiples tipos de recursos
2. **UnifiedVectorSearchService**: Búsqueda vectorial unificada entre DB y APIs
3. **APITriggeringService**: Servicio principal de triggering automático
4. **UnifiedChatService**: Chat que integra DB y APIs con detección automática de intención
5. **APITriggeringConfigService**: Gestión de configuración por usuario

### Flujo de Funcionamiento

```
Usuario → "Crear usuario con email test@example.com" 
    ↓
UnifiedChatService detecta intención de API
    ↓
APITriggeringService busca funciones relevantes
    ↓
ExtensibleEmbeddingService encuentra POST /users
    ↓
Extrae parámetros: email="test@example.com"
    ↓
Verifica permisos del usuario
    ↓
Ejecuta función automáticamente
    ↓
Retorna resultado al usuario
```

## 🔧 Configuración

### Variables de Entorno

```bash
# Configuración de triggering
API_TRIGGERING_ENABLED=True
API_TRIGGERING_CONFIDENCE_THRESHOLD=0.7
API_TRIGGERING_MAX_FUNCTIONS=3
API_TRIGGERING_TIMEOUT=30

# Vector Store (ya configurado)
VECTOR_PROVIDER=pgvector
EMBEDDING_PROVIDER=openai
```

### Configuración por Usuario

Cada usuario puede configurar su propio comportamiento de triggering:

```json
{
  "enabled": true,
  "confidence_threshold": 0.7,
  "max_auto_executions": 5,
  "timeout_seconds": 30,
  "allowed_endpoints": ["POST /users", "GET /products"],
  "blocked_endpoints": ["DELETE /users"],
  "auto_confirm": false,
  "require_explicit_consent": true
}
```

## 📡 Endpoints Disponibles

### 1. Configuración de Triggering

#### Crear configuración
```http
POST /api-triggering-configs/
{
  "app_id": "uuid",
  "enabled": true,
  "confidence_threshold": 0.7,
  "max_auto_executions": 5,
  "allowed_endpoints": ["POST /users"],
  "blocked_endpoints": ["DELETE /users"]
}
```

#### Obtener configuración por app
```http
GET /api-triggering-configs/app/{app_id}
```

#### Actualizar configuración
```http
PUT /api-triggering-configs/{config_id}
{
  "confidence_threshold": 0.8,
  "auto_confirm": true
}
```

### 2. Triggering Automático

#### Ejecutar función por query
```http
POST /api-triggering/trigger?query=crear usuario con email test@example.com&app_id=uuid&auto_execute=true
```

#### Probar query sin ejecutar
```http
POST /api-triggering/test-query?query=obtener todos los usuarios&app_id=uuid
```

#### Obtener sugerencias
```http
GET /api-triggering/suggestions?query=crear&app_id=uuid
```

### 3. Chat Unificado

#### Enviar mensaje al chat unificado
```http
POST /unified-chat/send
{
  "content": "Crear un usuario y luego consultar todos los usuarios",
  "chat_id": "uuid",
  "app_id": "uuid",
  "db_id": "uuid",
  "auto_execute_apis": false
}
```

#### Confirmar ejecución de API
```http
POST /unified-chat/confirm-api-execution
{
  "function_id": "uuid",
  "function_name": "create_user",
  "endpoint": "POST /users",
  "method": "POST",
  "parameters": {"email": "test@example.com"},
  "confidence": 0.9,
  "requires_confirmation": true,
  "estimated_execution_time": 5
}
```

#### Obtener sugerencias de chat
```http
GET /unified-chat/suggestions?partial_message=crear&app_id=uuid&db_id=uuid
```

## 🎯 Casos de Uso

### 1. Triggering Automático Simple

```bash
# Usuario dice:
"Crear un usuario con email juan@example.com y nombre Juan"

# Sistema:
1. Detecta intención de API
2. Busca función POST /users
3. Extrae parámetros: email="juan@example.com", name="Juan"
4. Ejecuta automáticamente
5. Responde: "✅ Usuario creado exitosamente"
```

### 2. Triggering con Confirmación

```bash
# Usuario dice:
"Eliminar el usuario con ID 123"

# Sistema:
1. Detecta intención de API (DELETE)
2. Encuentra función DELETE /users/{id}
3. Requiere confirmación (operación destructiva)
4. Muestra plan: "¿Eliminar usuario ID 123?"
5. Usuario confirma
6. Ejecuta función
```

### 3. Chat Mixto (DB + API)

```bash
# Usuario dice:
"Mostrar todos los usuarios de la base de datos y crear uno nuevo via API"

# Sistema:
1. Detecta intención mixta
2. Ejecuta consulta SQL: SELECT * FROM users
3. Busca función POST /users
4. Ejecuta ambas operaciones
5. Responde con datos de DB + resultado de API
```

### 4. Búsqueda Inteligente

```bash
# Usuario dice:
"API para procesar pagos"

# Sistema:
1. Busca en embeddings de APIs
2. Encuentra endpoints relacionados con pagos
3. Sugiere: POST /payments, GET /payment-methods
4. Muestra documentación y ejemplos
```

## 🔍 Sistema de Embeddings Extensible

### Tipos de Recursos Soportados

```python
class ResourceType(Enum):
    API_ENDPOINT = "api_endpoint"
    API_PARAMETER = "api_parameter"
    API_RESPONSE = "api_response"
    STRATEGY_RULE = "strategy_rule"        # Futuro
    STRATEGY_CONDITION = "strategy_condition"  # Futuro
    STRATEGY_ACTION = "strategy_action"    # Futuro
    FUNCTION_CODE = "function_code"        # Futuro
    FUNCTION_DOCS = "function_docs"        # Futuro
    DATABASE_TABLE = "database_table"
    DATABASE_COLUMN = "database_column"
    DATABASE_RELATIONSHIP = "database_relationship"
```

### Extensibilidad para Futuras Funcionalidades

El sistema está diseñado para crecer fácilmente:

1. **Estrategias**: Reglas de negocio embebibles
2. **Funciones**: Código y documentación embebibles
3. **Integraciones**: APIs externas embebibles
4. **Templates**: Plantillas de código embebibles

## 🛡️ Seguridad y Control

### Control de Acceso

- **Whitelist**: Solo endpoints permitidos
- **Blacklist**: Endpoints bloqueados
- **Confianza**: Umbral mínimo de confianza
- **Límites**: Máximo de ejecuciones automáticas

### Auditoría

- Logs de todas las ejecuciones
- Métricas de uso por usuario
- Análisis de patrones de uso
- Alertas de seguridad

## 📊 Analytics y Monitoreo

### Métricas Disponibles

```json
{
  "triggering_analytics": {
    "total_requests": 150,
    "successful_executions": 142,
    "failed_executions": 8,
    "average_confidence": 0.85,
    "most_triggered_functions": ["POST /users", "GET /products"],
    "execution_times": {
      "average": 2.3,
      "min": 0.8,
      "max": 5.2
    }
  },
  "search_analytics": {
    "total_searches": 300,
    "cache_hit_rate": 0.75,
    "most_searched_types": ["api", "database"],
    "average_response_time": 0.5
  }
}
```

## 🚀 Próximos Pasos

### Fase 1: Optimización
- [ ] Mejora de extracción de parámetros con LLM
- [ ] Cache inteligente de embeddings
- [ ] Optimización de búsqueda vectorial

### Fase 2: Extensibilidad
- [ ] Soporte para estrategias
- [ ] Embeddings de funciones de código
- [ ] Integración con más tipos de APIs

### Fase 3: Inteligencia Avanzada
- [ ] Aprendizaje de patrones de usuario
- [ ] Sugerencias proactivas
- [ ] Análisis predictivo de intenciones

## 🔧 Troubleshooting

### Problemas Comunes

1. **No se encuentran funciones relevantes**
   - Verificar que las APIs estén correctamente embebidas
   - Ajustar el umbral de confianza
   - Revisar la configuración de whitelist/blacklist

2. **Extracción incorrecta de parámetros**
   - Mejorar la query con más contexto
   - Usar nombres de parámetros más específicos
   - Verificar la documentación de la API

3. **Ejecución fallida**
   - Revisar logs de error
   - Verificar permisos de la API
   - Comprobar conectividad y autenticación

### Logs Importantes

```bash
# Búsqueda vectorial
[UnifiedVectorSearchService] 🔍 Búsqueda unificada: 'crear usuario' para user_id=123

# Detección de intención
[UnifiedChatService] 🎯 Intención detectada: api_call (confianza: 0.89)

# Ejecución de función
[APITriggeringService] ✅ Función ejecutada: create_user
```

## 📚 Referencias

- [Plan de Refactorización](plan_refactor_apichat.md)
- [Documentación de Vector Store](docs/phases/phase2-vector.md)
- [API Reference](docs/api/)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
