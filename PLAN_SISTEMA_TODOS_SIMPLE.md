# 🎯 PLAN SIMPLE - SISTEMA DE TO-DOS PARA TAREAS LARGAS

## 📋 Resumen Ejecutivo

**Objetivo**: Extender el sistema actual (explorer/no-explorer) para manejar **tareas largas** que requieren múltiples pasos y seguimiento en el tiempo.

**Lo que ya tienes**: 
- ✅ Sistema explorer/no-explorer funcionando
- ✅ **PLANES** cortos (máximo 2 pasos) en `PlanBuilderService` con `GuidedPlan`
- ✅ Redis para cache de planes (`ai_plan_cache`)
- ✅ Estructura de planes con `GuidedPlan` y `PlanStep`
- ✅ Validación: `if len(v) > 2: raise ValueError('El plan no puede tener más de 2 pasos')`

**Lo que necesitas**: Sistema simple para **TO-DOS** (tareas largas >2 pasos) que se ejecuten paso a paso.

---

## 🎯 CONCEPTO CLARO: PLAN vs TO-DO

### **📘 Definición**
- **PLAN**: Representa el objetivo global que el usuario quiere alcanzar. Es un contenedor de pasos.
- **TO-DO**: Representa un paso atómico y ejecutable dentro de ese plan. Cada to-do tiene estado propio (pending, running, done, failed).

### **🔗 Analogía**
- **PLAN** = proyecto/workflow completo
- **TO-DOS** = pasos/acciones concretas de ese workflow
- **Patrón**: Como Airflow o Temporal.io:
  - Workflow/DAG = Plan
  - Task = To-do

### **💡 Ejemplo Concreto**
**Usuario dice**: "Quiero usar mis datos para ver cuántos leads activos tengo este mes y después actualizar mi CRM con esa info."

**Sistema genera**:
- **PLAN**:
  - id: plan_123
  - title: "Actualizar CRM con leads activos"
  - description: "Obtener datos de leads de la base de datos y sincronizarlos con el CRM"
  - status: running

- **TO-DOS**:
  - `query_db_initial`: Ejecutar SQL en la DB del usuario para obtener leads activos del mes (pending)
  - `analyze_data`: Analizar y contar leads, validar formato (pending)
  - `call_crm_api`: Invocar API del CRM con el número de leads activos (pending)

### **⚡ Qué ocurre en ejecución**
1. El Plan pasa a `running`
2. El To-do 1 se ejecuta → si falla, puedes reintentar solo ese paso
3. Cuando To-do 1 termina, pasas al To-do 2, luego al 3
4. Cuando todos los To-dos terminan con éxito, el Plan pasa a `completed`

### **🎯 Beneficios de separar**
- **Control y trazabilidad**: Puedes reintentar un paso sin repetir todo
- **Explainability**: Se puede mostrar al usuario "qué se hizo" paso a paso
- **Automatización futura**: Si detectas que varios planes repiten la misma secuencia de to-dos, puedes recomendar una estrategia/automatización

### **👉 En resumen**
- **PLAN** = El objetivo (ejemplo: "Actualizar CRM con leads activos")
- **TO-DOS** = Los pasos concretos para cumplirlo (ejemplo: "Query DB → Analizar datos → Llamar API")

---

## 💬 CÓMO SE VE PARA EL USUARIO EN EL CHAT

### **1. Propuesta del Plan**
**Sistema**:
```
"He creado un plan con 3 pasos para lograr tu objetivo:
1️⃣ Consultar la base de datos para ver los leads activos este mes
2️⃣ Analizar y contar los resultados
3️⃣ Llamar a la API del CRM con esa información

¿Quieres confirmarlo y que empiece la ejecución?"
```

### **2. Ejecución Paso a Paso**
**Cuando el usuario confirma, el chat va mostrando el estado de los to-dos**:
```
"Ejecutando paso 1: Consultar la DB…"
"✅ Paso 1 completado: 154 leads encontrados"

"Ejecutando paso 2: Analizar resultados…"
"✅ Paso 2 completado: 150 leads válidos tras limpieza de datos"

"Ejecutando paso 3: Llamar al CRM…"
"✅ Paso 3 completado: CRM actualizado con 150 leads activos"
```

### **3. Finalización del Plan**
**Al terminar todos los to-dos**:
**Sistema**:
```
"🎉 El plan Actualizar CRM con leads activos se completó con éxito.
¿Quieres guardarlo en tu histórico para usarlo como referencia en el futuro?"
```

### **🔑 Diferencias Prácticas que Cursor debe respetar:**

#### **Relación**
- Plan **contiene** muchos to-dos
- Cada to-do **pertenece** a exactamente un plan
- Secuencia ordenada o con dependencias simples

#### **Persistencia**
- **Plan (DB)**: `plans` con metadata → título, descripción, usuario, recursos, fechas
- **To-do (DB)**: `plan_tasks` → título, status, orden, outcome, tiempo, errores

#### **Runtime en Redis**
- `plan:{run_id}:meta` → estado del plan (status global, progreso %)
- `plan:{run_id}:tasks` → lista ordenada de IDs
- `plan:{run_id}:task:{task_id}` → detalle de cada to-do (status, intentos, errores)

#### **UX en Chat**
- **Plan**: Usuario pregunta/confirma → "He creado un plan con 6 pasos"
- **To-do**: Reporta/ejecuta → "Ejecutando tarea 2: Crear tabla users"

#### **🎯 Por qué separar**
- **Histórico**: Comparar planes distintos, medir tareas que se repiten
- **Recomendaciones**: Detectar patrones si varios planes comparten to-dos
- **Ejecución**: Pausas y errores ocurren en to-dos, no en el plan entero
- **Métricas**: Coste por plan (alto nivel), tasa de fallo por to-do (detalle)

---

## 🎯 FASE 1: EXTENDER MODELOS EXISTENTES

### 1.1 Crear Modelos de Plan y To-Do
**Objetivo**: Crear la estructura de datos para planes (contenedores) y to-dos (tareas atómicas).

**Instrucciones**:
- **Tabla `plans`** (contenedor del objetivo global):
  - id, user_id, title, description, status (draft/running/completed)
  - estimated_duration, actual_duration, created_at, updated_at, completed_at
  - metadata (recursos usados, contexto, etc.)
- **Tabla `plan_tasks`** (to-dos atómicos):
  - id, plan_id, title, description, status (pending/in_progress/done/failed)
  - order_index, estimated_effort, actual_effort, outcome, errors
  - created_at, started_at, completed_at
- **Tabla `plan_execution_state`** (seguimiento en Redis):
  - id, plan_id, run_id, redis_key, current_task_index, status
  - created_at, updated_at

### 1.2 Extender Redis para Planes y To-Dos
**Objetivo**: Usar Redis para seguimiento en tiempo real de ejecución de planes.

**Instrucciones**:
- Extender `RedisCacheService` con métodos para planes:
  - `set_plan_execution_state(plan_id, run_id, state)`
  - `get_plan_execution_state(plan_id, run_id)`
  - `update_plan_progress(plan_id, run_id, task_index, status)`
  - `set_task_execution_state(plan_id, run_id, task_id, state)`
  - `get_task_execution_state(plan_id, run_id, task_id)`
- **Estructura en Redis**:
  - `plan:{run_id}:meta` → estado del plan (status global, progreso %)
  - `plan:{run_id}:tasks` → lista ordenada de task IDs
  - `plan:{run_id}:task:{task_id}` → detalle de cada to-do (status, intentos, errores)
- Usar TTL de 24 horas para estados de ejecución

---

## 🎯 FASE 2: SERVICIO DE GENERACIÓN DE TO-DOS

### 2.1 Crear PlanGenerationService
**Objetivo**: Generar planes (contenedores) con to-dos (tareas atómicas) basados en requerimientos del usuario.

**Instrucciones**:
- Crear servicio que extienda la lógica de `PlanBuilderService`
- Método `generate_plan_with_todos(requirement, user_id, context)` que:
  - Analice la complejidad del requerimiento
  - Genere un **PLAN** (contenedor) con título y descripción
  - Genere lista de **TO-DOS** (tareas atómicas) paso a paso
  - Estime esfuerzo para cada to-do
  - Determine si es tarea larga (>2 pasos) o corta
- Integrar con el sistema de recursos del usuario existente
- Usar el mismo sistema de prompts pero adaptado para planes largos

### 2.2 Detectar PLAN vs TO-DO
**Objetivo**: Decidir cuándo usar el sistema actual (PLAN) vs el nuevo sistema (TO-DO).

**Instrucciones**:
- **Si el plan generado tiene >2 pasos** → usar sistema de TO-DOS
- **Si tiene ≤2 pasos** → usar sistema actual (PLAN con explorer/no-explorer)
- **Lógica de decisión**:
  ```python
  if estimated_steps > 2:
      return "todo_system"  # Nuevo sistema
  else:
      return "plan_system"  # Sistema actual
  ```
- **Criterios adicionales**:
  - Tiempo estimado total > 30 minutos → TO-DO
  - Requiere confirmación del usuario → TO-DO
  - Operaciones de escritura múltiples → TO-DO
  - Migración o refactoring → TO-DO

---

## 🎯 FASE 3: SISTEMA DE EJECUCIÓN PASO A PASO

### 3.1 Crear TodoExecutionService
**Objetivo**: Ejecutar to-dos paso a paso con seguimiento en Redis.

**Instrucciones**:
- Crear servicio que maneje la ejecución secuencial
- Método `execute_todo_list(todo_list_id, user_id)` que:
  - Cargue la lista de to-dos desde DB
  - Guarde estado inicial en Redis
  - Ejecute cada paso secuencialmente
  - Actualice progreso en Redis en tiempo real
  - Maneje errores y rollback si es necesario
- Integrar con `FunctionExecutor` existente para ejecutar pasos
- Usar el mismo sistema de validación y seguridad

### 3.2 Seguimiento en Tiempo Real
**Objetivo**: Permitir al usuario ver el progreso en tiempo real.

**Instrucciones**:
- Crear endpoint `GET /todos/{todo_list_id}/progress` que lea desde Redis
- Mostrar estado actual: paso actual, progreso %, tiempo estimado restante
- Crear endpoint `POST /todos/{todo_list_id}/pause` y `/resume` para control manual
- Implementar notificaciones cuando se complete un paso importante

---

## 🎯 FASE 4: INTEGRACIÓN CON CHAT EXISTENTE

### 4.1 Extender UnifiedChatService
**Objetivo**: Integrar to-dos en el chat existente.

**Instrucciones**:
- Extender `UnifiedChatService` para detectar cuando generar to-dos
- Si detecta tarea larga → generar lista de to-dos y mostrar al usuario
- Si usuario confirma → iniciar ejecución paso a paso
- Mostrar progreso en el chat: "Ejecutando paso 3 de 7: Creando tabla usuarios..."
- Permitir comandos de chat: "pausar to-do", "mostrar progreso", "cancelar"

### 4.2 Comandos de Chat para To-Dos
**Objetivo**: Comandos específicos para gestionar to-dos desde el chat.

**Instrucciones**:
- `"crear to-do para [requerimiento]"` → generar lista
- `"mostrar mis to-dos"` → listar to-dos del usuario
- `"progreso del to-do [id]"` → mostrar progreso actual
- `"pausar to-do [id]"` → pausar ejecución
- `"reanudar to-do [id]"` → reanudar ejecución
- `"cancelar to-do [id]"` → cancelar y limpiar

---

## 🎯 FASE 5: PERSISTENCIA Y RECOMENDACIONES

### 5.1 Guardar To-Dos Completados en DB
**Objetivo**: Persistir to-dos completados para futuras recomendaciones.

**Instrucciones**:
- Cuando un to-do se complete exitosamente:
  - Guardar en DB con estado "completed"
  - Generar embeddings del to-do para búsqueda semántica
  - Guardar métricas: tiempo real vs estimado, pasos exitosos, errores
- Limpiar estado de Redis después de completar
- Crear tabla `todo_outcomes` para métricas y resultados

### 5.2 Sistema de Recomendaciones Futuro
**Objetivo**: Preparar para recomendaciones de estrategias/automatizaciones.

**Instrucciones**:
- Crear tabla `todo_patterns` para patrones exitosos
- Guardar patrones de to-dos que funcionaron bien
- Preparar estructura para futuras recomendaciones:
  - "Este to-do es similar a uno que completaste antes"
  - "Podrías automatizar estos pasos con una estrategia"
  - "Basado en tu historial, este to-do tomará ~X horas"

---

## 🎯 FLUJO COMPLETO DEL SISTEMA

### **Flujo para PLAN (Sistema Actual)**
```
Usuario: "Mostrar usuarios activos"
↓
Sistema: Detecta tarea simple (≤2 pasos)
↓
Sistema: Usa PLAN con explorer/no-explorer
↓
Sistema: Ejecuta inmediatamente (1-2 pasos)
↓
Sistema: Retorna resultado
↓
Sistema: Guarda en Redis cache (temporal)
```

### **Flujo para PLAN con TO-DOS (Nuevo Sistema)**
```
Usuario: "Migrar base de datos a microservicios"
↓
Sistema: Detecta tarea compleja (>2 pasos)
↓
Sistema: Genera PLAN (contenedor) + lista de TO-DOS (8 tareas atómicas)
↓
Sistema: Muestra PLAN al usuario: "He creado un plan con 8 pasos"
↓
Usuario: Confirma ejecución
↓
Sistema: Guarda PLAN en DB + estado en Redis
↓
Sistema: Ejecuta TO-DO 1: "Crear backup", actualiza progreso en Redis
↓
Sistema: Ejecuta TO-DO 2: "Instalar PostgreSQL", actualiza progreso en Redis
↓
... (continúa ejecutando cada TO-DO paso a paso)
↓
Sistema: Completa PLAN, marca como "completed" en DB, limpia Redis
```

---

## 🎯 CASOS DE USO PRINCIPALES

### 1. **Migración de Base de Datos**
```
Usuario: "Migrar mi base de datos de MySQL a PostgreSQL"
Sistema: 
- Genera PLAN: "Migración MySQL → PostgreSQL"
- Genera 8 TO-DOS: "1. Backup de datos, 2. Instalar PostgreSQL, 3. Crear esquema..."
- Muestra: "He creado un plan con 8 pasos"
- Usuario confirma
- Ejecuta cada TO-DO paso a paso con progreso visible
```

### 2. **Refactoring Complejo**
```
Usuario: "Refactorizar mi aplicación a microservicios"
Sistema:
- Genera PLAN: "Refactoring a Microservicios"
- Genera 12 TO-DOS atómicos
- Muestra estimación de tiempo del PLAN
- Usuario puede pausar/reanudar TO-DOS individuales
- Progreso visible en tiempo real por TO-DO
```

### 3. **Setup de Proyecto Completo**
```
Usuario: "Configurar proyecto completo con CI/CD, monitoreo y deployment"
Sistema:
- Genera PLAN: "Setup Completo de Proyecto"
- Genera 15 TO-DOS agrupados por categoría
- Permite ejecutar TO-DOS por lotes
- Guarda patrones de TO-DOS para futuras recomendaciones
```

---

## 🎯 CRONOGRAMA SIMPLE

### **Semana 1: Modelos y Redis**
- [ ] Crear tablas de to-dos
- [ ] Extender RedisCacheService
- [ ] Tests básicos

### **Semana 2: Generación de To-Dos**
- [ ] Crear TodoGenerationService
- [ ] Integrar con sistema de recursos del usuario
- [ ] Tests de generación

### **Semana 3: Ejecución Paso a Paso**
- [ ] Crear TodoExecutionService
- [ ] Implementar seguimiento en Redis
- [ ] Tests de ejecución

### **Semana 4: Integración con Chat**
- [ ] Extender UnifiedChatService
- [ ] Implementar comandos de chat
- [ ] Tests de integración

### **Semana 5: Persistencia y Recomendaciones**
- [ ] Guardar to-dos completados
- [ ] Preparar sistema de recomendaciones
- [ ] Tests completos

---

## 🎯 BENEFICIOS DEL ENFOQUE SIMPLE

### **Para el Usuario:**
- ✅ Ve progreso en tiempo real
- ✅ Puede pausar/reanudar tareas largas
- ✅ Confirma antes de ejecutar
- ✅ Historial de tareas completadas

### **Para el Sistema:**
- ✅ Reutiliza infraestructura existente
- ✅ Extiende funcionalidad sin romper nada
- ✅ Preparado para recomendaciones futuras
- ✅ Escalable y mantenible

### **Para el Desarrollo:**
- ✅ Basado en lo que ya funciona
- ✅ Incremental y seguro
- ✅ Fácil de testear
- ✅ Documentado y claro

---

## 🚀 PRÓXIMOS PASOS INMEDIATOS

1. **Aprobar este plan simple** (mucho más realista)
2. **Comenzar con Fase 1** - modelos y Redis
3. **Reutilizar** todo lo que ya tienes funcionando
4. **Iterar** paso a paso sin romper nada existente

¿Te parece mucho más realista este enfoque? ¿Empezamos con la Fase 1?
