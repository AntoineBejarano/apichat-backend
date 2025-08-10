# Solución para Problema de Concurrencia de SQLAlchemy

## Problema Identificado

El error de SQLAlchemy estaba ocurriendo debido a **acceso concurrente a la misma sesión de base de datos** en el `OrchestratorService`. Específicamente:

### Causa Raíz
- En `_load_context_parallel`, se ejecutaban múltiples tareas en paralelo usando `asyncio.gather()`
- Todas las tareas compartían la misma instancia de `self.db` (la sesión de SQLAlchemy)
- Cuando una tarea ejecutaba `_load_database_schemas_async` (que llama a `_ensure_warm_schemas`), otra tarea podía estar intentando usar la misma sesión
- El conflicto específico estaba en que `_ensure_warm_schemas` se ejecutaba en un executor separado pero seguía usando la misma sesión `self.db`

## Solución Implementada

### 1. Sesiones Separadas para Cada Tarea Asíncrona

Cada método asíncrono ahora crea su propia sesión de base de datos:

```python
async def _store_user_message_async(self, chat_id: UUID, message: ChatMessage):
    """Guardar mensaje del usuario con sesión separada para evitar conflictos de concurrencia"""
    try:
        # 🔧 FIX: Crear sesión separada para evitar conflictos
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Crear una nueva instancia del servicio con la sesión separada
            from app.core.service_factory import ServiceFactory
            temp_factory = ServiceFactory(db=db, request=self.factory.request)
            history_service = temp_factory.get_chat_history_service()
            
            # ... lógica del servicio ...
            
        finally:
            db.close()  # 🔧 IMPORTANTE: Cerrar la sesión
    except Exception as e:
        logger.exception(f"[OrchestratorService] Failed to store user message: {e}")
        return False
```

### 2. Métodos Refactorizados

Los siguientes métodos han sido refactorizados para usar sesiones separadas:

- `_store_user_message_async()` - Guardar mensajes del usuario
- `_save_assistant_message_async()` - Guardar mensajes del asistente  
- `_load_history_async()` - Cargar historial del chat
- `_check_usage_limit_async()` - Verificar límites de uso
- `_load_apps_async()` - Cargar aplicaciones
- `_load_functions_async()` - Cargar funciones disponibles
- `_load_mcp_tools_async()` - Cargar herramientas MCP
- `_load_agent_prompt_async()` - Cargar prompt del agente
- `_load_database_schemas_async()` - Ya tenía sesión separada

### 3. Patrón de Implementación

Cada método sigue este patrón:

1. **Crear sesión separada**: `db = SessionLocal()`
2. **Crear factory temporal**: `temp_factory = ServiceFactory(db=db, request=self.factory.request)`
3. **Obtener servicio**: `service = temp_factory.get_service()`
4. **Ejecutar lógica**: Usar el servicio para operaciones de BD
5. **Cerrar sesión**: `db.close()` en bloque `finally`

### 4. Manejo de Errores

- Cada método tiene manejo de excepciones robusto
- Las sesiones se cierran siempre en el bloque `finally`
- Los errores se registran con `logger.exception()`
- Se retornan valores por defecto seguros en caso de error

## Beneficios de la Solución

### ✅ Eliminación de Conflictos de Concurrencia
- Cada tarea asíncrona tiene su propia sesión de BD
- No hay más acceso concurrente a la misma sesión
- Las operaciones pueden ejecutarse en paralelo sin conflictos

### ✅ Mejor Rendimiento
- Las tareas se ejecutan verdaderamente en paralelo
- No hay bloqueos por espera de sesiones compartidas
- Mejor utilización de recursos del sistema

### ✅ Mayor Robustez
- Manejo de errores mejorado
- Sesiones se cierran correctamente
- Fallbacks seguros en caso de error

### ✅ Mantenibilidad
- Código más claro y predecible
- Patrón consistente en todos los métodos
- Fácil debugging y testing

## Consideraciones de Implementación

### Importaciones
```python
from app.core.database import SessionLocal
from app.core.service_factory import ServiceFactory
```

### Manejo de Sesiones
- **Siempre** usar `try/finally` para cerrar sesiones
- Crear factory temporal con la nueva sesión
- No reutilizar sesiones entre tareas

### Logging
- Usar `logger.exception()` para errores
- Incluir contexto útil en los logs
- Registrar operaciones exitosas para debugging

## Testing de la Solución

Para verificar que la solución funciona:

1. **Ejecutar múltiples requests simultáneos**
2. **Verificar logs** - no debe haber errores de SQLAlchemy
3. **Monitorear rendimiento** - las tareas deben ejecutarse en paralelo
4. **Verificar integridad de datos** - los mensajes deben guardarse correctamente

## Monitoreo y Mantenimiento

### Logs a Observar
- `[OrchestratorService] User message stored with separate session`
- `[OrchestratorService] History loaded with separate session`
- `[OrchestratorService] Usage limit checked with separate session`

### Métricas de Rendimiento
- Tiempo de ejecución de `_load_context_parallel`
- Número de sesiones de BD creadas/cerradas
- Tasa de éxito de operaciones de BD

### Mantenimiento Futuro
- Al agregar nuevos métodos asíncronos, seguir el mismo patrón
- Revisar periódicamente el manejo de sesiones
- Considerar implementar pool de conexiones si es necesario

---

**Nota**: Esta solución mantiene la compatibilidad con el código existente mientras resuelve el problema de concurrencia de manera elegante y eficiente.
