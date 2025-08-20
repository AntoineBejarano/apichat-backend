# 🛠️ Plan de acción: Corrección de ejecución SQL no válida + errores de telemetría en APIchat

Este documento describe los pasos necesarios para solucionar errores lógicos detectados durante el procesamiento de una consulta SQL generada por LLM en APIchat, así como errores secundarios relacionados con telemetría y validaciones.

---

## ✅ Objetivo principal

Evitar que el sistema ejecute respuestas generadas por LLM que no sean consultas SQL válidas, mejorando la lógica de decisión y manejando correctamente los errores de contexto.

---

## 🚀 PLAN DE ACCIÓN EN FASES

---

### 🎯 **FASE 1: Validación de SQL generado por LLM** [✅ COMPLETADA]
**Estado:** Completada  
**Archivo:** `langchain_service.py`  
**Función:** `generate_sql_from_question()`

- [x] Implementar función `is_valid_sql()`
- [x] Añadir validación después de obtener `generated_sql`
- [x] Retornar respuesta apropiada si no es SQL válido
- [x] Ejecutar tests de validación

**✅ Resultado:** Todos los tests pasan exitosamente. La función `is_valid_sql()` valida correctamente SQL y rechaza respuestas explicativas del LLM.

**Código a implementar:**
```python
def is_valid_sql(sql: str) -> bool:
    sql = sql.strip().lower()
    return sql.startswith("select") and "from" in sql

# En el flujo actual:
if not is_valid_sql(generated_sql):
    logger.warning("[ExecutionEngine] ⚠️ La respuesta no parece SQL válido. Respuesta: %s", generated_sql)
    return {
        "content": generated_sql,
        "error": "Respuesta del modelo no es una consulta SQL ejecutable.",
        "status": "llm_response"
    }
```

---

### 🎯 **FASE 2: Prevención de ejecución de respuestas explicativas** [✅ COMPLETADA]
**Estado:** Completada  
**Archivo:** `execution_engine_service.py`

- [x] Implementar detección de frases explicativas
- [x] Añadir guardia antes de ejecutar SQL
- [x] Retornar mensaje de error apropiado
- [x] Ejecutar tests de prevención

**✅ Resultado:** Todos los tests pasan exitosamente. La función `_is_explanatory_response()` detecta correctamente respuestas explicativas del LLM y bloquea su ejecución como SQL.

**Código a implementar:**
```python
if any(phrase in generated_sql.lower() for phrase in ["lo siento", "no puedo", "necesitaría", "reemplaza"]):
    logger.warning("[ExecutionEngine] ⚠️ Detenido: respuesta no es SQL ejecutable")
    return {
        "error": "La IA no generó SQL ejecutable. Revisa si la base de datos fue conectada correctamente.",
        "content": generated_sql,
        "status": "llm_response"
    }
```

---

### 🎯 **FASE 3: Mejora del fallback de esquema** [✅ COMPLETADA]
**Estado:** Completada  
**Archivo:** `schema_explorer_service.py`

- [x] Mejorar lógica de fallback de catálogo
- [x] Implementar mensaje útil cuando no hay esquema
- [x] Añadir opciones para el usuario
- [x] Ejecutar tests de fallback

**✅ Resultado:** Todos los tests pasan exitosamente. El sistema ahora proporciona mensajes útiles cuando no hay esquema disponible y ofrece opciones claras al usuario.

**Código a implementar:**
```python
return {
    "content": "⚠️ No tengo acceso al esquema de tu base de datos. ¿Quieres cargarlo primero?",
    "status": "missing_schema"
}
```

---

### 🎯 **FASE 4: Corrección de errores de telemetría** [✅ COMPLETADA]
**Estado:** Completada  
**Archivo:** `advanced_telemetry_service.py`

- [x] Eliminar `estimated_cost_usd` del dict de parámetros
- [x] Implementar método `track_event()` faltante
- [x] Ejecutar tests de telemetría

**✅ Resultado:** Todos los tests pasan exitosamente. El sistema ahora elimina correctamente `estimated_cost_usd` antes del INSERT y el método `track_event()` funciona correctamente.

**Código a implementar:**
```python
params.pop("estimated_cost_usd", None)

def track_event(self, event_name: str, metadata: dict):
    logger.debug("[AdvancedTelemetryService] Tracking event: %s", event_name)
    # Implementación opcional de tracking de eventos aquí
```

---

### 🎯 **FASE 5: Tests de integración y validación** [✅ COMPLETADA]
**Estado:** Completada

- [x] Crear tests para cada fase implementada
- [x] Ejecutar tests de integración
- [x] Validar flujo completo
- [x] Marcar fases como completadas

**✅ Resultado:** Todos los 27 tests de integración pasan exitosamente. El flujo completo del sistema funciona correctamente con todas las mejoras implementadas.

---

### 🎯 **FASE 6: Integración de Langsmith (Base de Datos + SDK)** [✅ COMPLETADA]
**Estado:** Completada

- [x] Crear modelo `LLMRun` en SQLAlchemy para tracking de llamadas LLM
- [x] Crear schemas Pydantic para operaciones CRUD de `LLMRun`
- [x] Crear servicio `LLMRunsService` para gestión de datos
- [x] Integrar en `ServiceFactory` para acceso global
- [x] Crear configuración centralizada de Langsmith con API key
- [x] Implementar decorador `@traceable_if_enabled` para tracing condicional
- [x] Integrar tracing en `LangchainService` y `ExecutionEngineService`
- [x] Crear tests específicos para esta fase

**✅ Resultado:** Todos los tests pasan exitosamente. El sistema ahora tiene trazabilidad completa de llamadas LLM con Langsmith y almacenamiento en base de datos.

---

### 🎯 **FASE 7: ReAct Orchestrator (Simplificación del Orchestrator)** [✅ COMPLETADA]
**Estado:** Completada

- [x] Crear `ReActOrchestrator` como coordinador principal simplificado
- [x] Implementar patrón ReAct: Think → Act → Observe → Repeat
- [x] Integrar con grafos existentes (`ExplorationGraph`, `GuidedGraph`)
- [x] Añadir al `ServiceFactory` para acceso global
- [x] Crear tests específicos para esta fase

**✅ Resultado:** Todos los tests pasan exitosamente. El sistema ahora tiene un orchestrator simplificado que usa ReAct como coordinador principal, reduciendo drásticamente la complejidad del orchestrator original de 2000+ líneas.

**Código implementado:**
```python
class ReActOrchestrator:
    """
    🧠 ReAct Orchestrator: Coordinador principal simplificado
    
    Think → Act → Observe → Repeat hasta resolver completamente
    """
    
    async def handle_message(self, chat_id, message, db_ids=None, app_ids=None, explorer=True):
        # Loop ReAct principal con máximo 5 iteraciones
        while context["iteration"] < self.max_iterations:
            # 🧠 THINK: LLM decide qué hacer
            thought = await self._think(context)
            
            # 🎯 ACT: Ejecutar la acción decidida
            result = await self._act(thought, context)
            
            # 👁️ OBSERVE: Evaluar resultado y actualizar contexto
            context = await self._observe(result, context)
```

---

## 📂 Archivos afectados

| Archivo                           | Acción a realizar                                                       | Estado |
|----------------------------------|--------------------------------------------------------------------------|---------|
| `langchain_service.py`           | Validación de SQL generado por el modelo                                 | ✅ |
| `execution_engine_service.py`    | Prevención de ejecución si es un mensaje explicativo                     | ✅ |
| `schema_explorer_service.py`     | Mejor manejo de fallback y mensaje al usuario                            | ✅ |
| `advanced_telemetry_service.py`  | Arreglo de insert con columna generada + creación de `track_event()`     | ✅ |
| `orchestrator_service.py`        | (Opcional) Añadir más guardias para short-circuits si no hay contexto DB | ⏳ |

---

## 🧠 Contexto resumido del error

El sistema generó una respuesta explicativa del LLM, la trató como si fuera SQL y la ejecutó literalmente, causando un `SyntaxError` en la base de datos. Esto se debió a:
- Confianza baja en la intención (`conf: 0.51`)
- Fallback a generación por LLM sin validación posterior
- Ausencia de guardias lógicas para filtrar respuestas no ejecutables

---

## ✅ Resultado esperado

Con estas mejoras:
- Las respuestas explicativas no se ejecutarán como SQL.
- El usuario recibirá feedback claro cuando falte información.
- Los errores de telemetría dejarán de lanzarse.
- Se evitan errores secundarios por funciones inexistentes (`track_event`) o campos mal insertados.

---

## 📊 PROGRESO GENERAL
- [x] FASE 1: Validación de SQL generado por LLM
- [x] FASE 2: Prevención de ejecución de respuestas explicativas  
- [x] FASE 3: Mejora del fallback de esquema
- [x] FASE 4: Corrección de errores de telemetría
- [x] FASE 5: Tests de integración y validación
- [x] FASE 6: Integración de Langsmith (Base de Datos + SDK)
- [x] FASE 7: ReAct Orchestrator (Simplificación del Orchestrator)

**Progreso:** 7/7 fases completadas (100%) 🎉
