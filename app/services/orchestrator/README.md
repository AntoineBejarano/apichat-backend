# Estructura de Servicios Refactorizada

## Visión General

Esta refactorización divide el `orchestrator_service.py` monolítico (2000+ líneas) en módulos especializados y organizados por responsabilidad.

## Estructura de Carpetas

```
app/services/
├── orchestrator_service.py        # ← MANTENER aquí por ahora (coordinador principal)
├── orchestrator/                  # ← NUEVA: Lógica de orquestación
├── context/                       # ← NUEVA: Gestión de contexto
├── execution/                     # ← NUEVA: Ejecución de planes y funciones
├── data/                          # ← NUEVA: Persistencia y caché
├── ai/                            # ← NUEVA: Servicios de IA
├── integration/                   # ← NUEVA: APIs externas y MCP
└── management/                    # ← NUEVA: Gestión de usuarios y recursos
```

## Plan de Refactorización

### Fase 1: ✅ Reorganización de Servicios Existentes
- [x] Crear estructura de carpetas
- [x] Crear archivos __init__.py
- [x] Mover servicios existentes a carpetas apropiadas
- [x] Organizar servicios por responsabilidad
- [x] Crear __init__.py principal

### Fase 2: Refactorización del Orchestrator
- [ ] Extraer módulos del orchestrator_service.py
- [ ] Implementar interfaces entre módulos
- [ ] Validar funcionalidad

### Fase 3: Optimización y Testing
- [ ] Refinar interfaces
- [ ] Agregar tests unitarios
- [ ] Documentar APIs

## Servicios Organizados

### **context/** - Gestión de Contexto
- `DetailedSchemaCacheService` - Caché de esquemas detallados
- `AppDescriptorCacheService` - Caché de descriptores de apps
- `VectorSearchService` - Búsqueda vectorial
- `IntentClassifierService` - Clasificación de intenciones
- `SchemaExplorerService` - Exploración de esquemas
- `DetailedSchemaCache` - Caché de esquemas

### **execution/** - Ejecución y Planes
- `ExecutionEngineService` - Motor de ejecución principal
- `FunctionExecutorService` - Ejecutor de funciones
- `SQLExecutorService` - Ejecutor de SQL
- `StrategyService` - Gestión de estrategias
- `FunctionService` - Gestión de funciones
- `SQLGuardrailsService` - Protecciones SQL
- `QueryValidationService` - Validación de consultas
- `graphs/` - Grafos de ejecución

### **data/** - Persistencia y Caché
- `CacheService` - Servicio de caché general
- `ChatHistoryService` - Historial de chat
- `ChatService` - Gestión de chats
- `SessionService` - Gestión de sesiones
- `UsageService` - Uso y métricas
- `DatabaseService` - Servicio de base de datos

### **ai/** - Servicios de IA
- `OpenAIService` - Integración con OpenAI
- `LangChainService` - Servicios de LangChain
- `DescriptionSelectorService` - Selector de descripciones
- `PromptEngineeringService` - Ingeniería de prompts

### **integration/** - APIs Externas
- `IntegrationService` - Servicio de integración general
- `MCPIntegrationService` - Integración MCP
- `OpenAPIService` - Servicios OpenAPI
- `ProxyService` - Servicio de proxy
- `mcp/` - Conectores MCP

### **management/** - Gestión de Recursos
- `UserService` - Gestión de usuarios
- `RoleService` - Gestión de roles
- `PermissionService` - Gestión de permisos
- `AppService` - Gestión de aplicaciones
- `AgentService` - Gestión de agentes
- `PerformanceMonitoringService` - Monitoreo de rendimiento
- `TelemetryService` - Telemetría
- `BillingService` - Facturación
- `SchedulerService` - Programación de tareas

## Beneficios de la Nueva Estructura

1. **Mantenibilidad**: Código más fácil de entender y modificar
2. **Testabilidad**: Módulos independientes más fáciles de testear
3. **Reutilización**: Servicios pueden ser usados por otros módulos
4. **Escalabilidad**: Preparado para microservicios
5. **Debugging**: Problemas más fáciles de aislar y resolver

## Próximos Pasos

1. ✅ **COMPLETADO**: Reorganización de servicios existentes
2. Actualizar imports en todo el proyecto (Fase 1.5)
3. Comenzar extracción de módulos del orchestrator (Fase 2)
