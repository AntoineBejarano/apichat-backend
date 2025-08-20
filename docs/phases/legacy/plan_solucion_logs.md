# Plan por fases para solucionar errores y optimizar logs en APIchat

## Fase 1 — Inyección de ServiceFactory en SchemaExplorerService
**Problema:** `'SchemaExplorerService' object has no attribute 'factory'`.  
**Cambios:**
- `app/services/context/schema_explorer_service.py`
  - `__init__(self, factory)` y `self.factory = factory`.
  - Reemplazar cualquier acceso a servicios caché vía `self.factory`.
- Donde se instancia: pasar `factory`.

**Prueba rápida:**
- Lanza el flujo con tu misma pregunta (“Hola, sabes…”).  
- Debe desaparecer el error de `factory` y verse el índice mínimo creado **sin warnings**.

## Fase 2 — Fallback del grafo guiado (o stub)
**Problema:** `'StrategyService' object has no attribute run_guided_graph'`.  
**Cambios:**
- `app/services/orchestrator/graph_runner.py`
  - Si `GUIDED_GRAPH_ENABLED=false` o no existe el método → **fallback** a plan mínimo.
- (Opcional) `app/services/strategy_service.py`: stub vacío de `run_guided_graph`.

**Prueba rápida:**  
- Ver `GraphRunner` log “Guided mode unavailable -> fallback”, y que el flujo siga.

## Fase 3 — Telemetría: `completed_at > started_at`
**Problema:** validación Pydantic falla.  
**Cambios:**
- `app/services/management/advanced_telemetry_service.py`
  - Generar `started_at = now(UTC)` y al cerrar step: `completed_at = max(now, started_at + 1µs)`.

**Prueba rápida:**  
- Debe desaparecer `Value error, completed_at debe ser posterior…`.

## Fase 4 — Planner: enriquecer `db_query` con `database_id`
**Problema:** “🛡️ Acción sin sql o database_id…”.  
**Cambios:**
- `app/services/orchestrator_service.py`
  - Tras generar plan, completar cada `db_query` con `database_id` (usa el principal del contexto).
- (Si tienes el SQL ya generado) pasa `sql` también.

**Prueba rápida:**  
- Ver que ya no aparece el warning de guardrails, y que el `ExecutionEngine` recibe `database_id`.

## Fase 5 — Estandarizar interfaz Langchain/DB y evitar `await` a `str`
**Problema:** `object str can't be used in 'await' expression`.  
**Cambios:**
- `app/services/ai/langchain_service.py`
  - Define `async def ask_db(...) -> dict` y **siempre** devuelve `{rows, sql, summary}`.
- `app/services/execution/execution_engine_service.py`
  - Cuando ejecutes `ask_db`, **await** garantizado (ya es async).  
  - Si en algún punto recibes algo no awaitable: elimina `await` y normaliza.

**Prueba rápida:**  
- Ejecutar la misma consulta; debe desaparecer el error y `query_result` ser un **dict**.

## Fase 6 — Guardrails NL→SQL (si no hay `sql`)
**Problema:** seguridad de consulta.  
**Cambios:**
- `ExecutionEngine._run_db_query`:
  - Si `action.sql` no existe → `sql = await langchain.generate_sql(question, db_id)`.
  - Validar con guardrails (prohibir DDL/DML, exigir `LIMIT`, lista blanca).

**Prueba rápida:**  
- Enviar pregunta ambigua; validar que se añade `LIMIT` y no ejecuta DDL.

## Fase 7 — ChatHistory: método correcto para guardar
**Problema:** `'ChatHistoryService' object has no attribute create_chat_history'`.  
**Cambios:**
- O bien **implementa** `create_chat_history(...)` en `app/services/data/chat_history_service.py`,
- O cambia en `orchestrator_service` a usar el método real (`save_message` / `create_message`).

**Prueba rápida:**  
- Tras la respuesta, verifica que el mensaje del asistente queda persistido.

## Fase 8 — Fast Schema Path: confianza y caché detallado
**Problema:** confianza 0.10 → cae a LLM.  
**Cambios:**
- Con la `factory` arreglada (F1), conecta `DetailedSchemaCache` correctamente.
- Ajusta umbral con env `CONF_FAST=0.6` temporalmente mientras calibras.
- Mejora índice con nombres de tabla/columna + sinónimos.

**Prueba rápida:**  
- Misma pregunta: debería subir la confianza y/o devolver respuesta más precisa.

## Fase 9 — Logs duplicados
**Sí, está duplicado.**  
Ves:
```
[SchemaCacheService] ✅ Cache L2 hit (BD) - 41 tablas
apichat - [SchemaCacheService] ✅ Cache L2 hit (BD) - 41 tablas
```
Ocurre porque el logger del módulo **propaga** al root y además tienes otro logger (p.ej. `apichat`) que también emite.

**Arreglo:**
- En cada logger con handler propio:
  ```python
  logger = logging.getLogger("apichat")
  logger.propagate = False
  ```
- No añadir handlers dos veces:
  ```python
  if not logger.handlers:
      logger.addHandler(logging.StreamHandler())
  ```
- Config global: un único `StreamHandler`, sin `basicConfig()` repetidos.
- En FastAPI con Uvicorn:
  ```python
  uvicorn.run(app, log_config=your_dict_config, log_level="info")
  ```

**Prueba rápida:**
- Reinicia y busca la línea “Cache L2 hit”. Debe aparecer **una sola** vez.

## Fase 10 — Hardening y DX
**Acciones:**
- Normalizar `assistant_response`.
- Serialización segura en steps (`json.dumps(result)[:N]`).
- Timers: no logar si no existe.
- Añadir tests para guided fallback, guardrails, chat history, telemetría y logs.

## Fase 11 – Añadir fallback de respuesta IA cuando `assistant_response` está vacío

**Objetivo:**  
Evitar que un error interno (por ejemplo, en `db_query`) aparezca como si fuera la respuesta de la IA y garantizar que siempre haya un mensaje claro para el usuario.

**Acciones:**

1. **Normalizar la salida de las acciones DB**  
   Asegúrate de que todas las funciones que ejecutan acciones sobre la base de datos devuelvan un diccionario con una estructura clara:
   ```python
   return {"ok": True, "rows": rows, "sql": sql, "summary": summary}
   # En caso de error:
   return {"ok": False, "error": str(e)}
