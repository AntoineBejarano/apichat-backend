# FutureFaces — Estrategias (Workflows tipo n8n)
> Diseño y plan de implementación para **estrategias**: flujos orquestados (cron/evento/manual), con **apps integradas** (p. ej., Gmail), subida por endpoint y ejecución segura, idempotente y observable.

## Objetivos
- Subir, versionar y ejecutar **estrategias** (DAGs) en formato JSON/YAML.
- Soportar **triggers** (cron / webhook / manual / programático).
- Integrar **apps** (Gmail, Notion, n8n-compat “like”) mediante un **registry** de conectores.
- Cumplir con multi-tenant, scopes, guardrails y observabilidad definidos en el plan general.

---

## Modelo de datos (SQLAlchemy)
- **Strategy**: id, org_id, name, slug, description, version, is_active, created_at, updated_at.
- **StrategyRevision**: id, strategy_id, version, spec (JSON), checksum, created_by, changelog.
- **Trigger**: id, strategy_id, type (`cron|webhook|manual|programmatic`), config (JSON), is_active.
- **Node**: id, strategy_revision_id, key, app_id, action, config (JSON), timeout_s, retry_policy, risk.
- **Edge**: id, strategy_revision_id, from_key, to_key, condition (expresión).
- **Credential**: id, org_id, app, scopes, encrypted_secret, created_by.
- **Run**: id, strategy_revision_id, org_id, trigger_type, run_key (idempotency), started_at, finished_at, status, usage (tokens/cost), error_code.
- **RunEvent**: id, run_id, node_key, event_type, payload (JSON), ts.
- Índices recomendados: (org_id, created_at), (strategy_id, version), (run_key), (run.status).

---

## Fase S1 — Esquema y validación de Estrategias
**Objetivo**: Aceptar estrategias con contrato estable.
**Cambios**:
- Esquema Pydantic v2: `StrategySpec` con `nodes[]`, `edges[]`, `metadata`, `permissions`.
- Validaciones: DAG acíclico, keys únicas, credenciales y scopes requeridos, timeouts válidos.
- Soporta **JSON** y **YAML** (autodetección por `Content-Type` o extensión).
**Archivos**: `app/strategies/spec.py`, `app/strategies/validators.py`.
**Prompt Cursor**: “Crea StrategySpec y validadores (DAG, scopes, timeouts).”
**Hecho cuando**: subir una spec inválida devuelve `error.user_facing` con causas.

---

## Fase S2 — Endpoint de subida y versionado
**Objetivo**: “Subirla y listo” con control de versiones.
**Cambios**:
- `POST /v1/strategies/upload` → crea/actualiza `Strategy` + `StrategyRevision`.
- Detección de cambios por `checksum`; `version = semver+1` si cambia.
- Opciones: `activate=true`, `changelog`, `dry_run=true` (solo validar).
**Archivos**: `app/routers/strategies_router.py`, `app/services/strategies_service.py`.
**Hecho cuando**: recibir un YAML válido crea versión y opcionalmente la activa.

---

## Fase S3 — Registry de Apps (Conectores)
**Objetivo**: Acciones reutilizables con permisos.
**Cambios**:
- `AppRegistry` con metadatos: `app_id`, `actions`, `required_scopes`, `schema config/input/output`.
- Ejemplo **Gmail**: `send_email`, `search_threads`, `reply`. Scopes: `gmail.send`, `gmail.read`.
- Enforce scopes: el **StrategyRunner** valida credenciales y permisos por nodo.
**Archivos**: `app/apps/registry.py`, `app/apps/gmail.py` (+ clients).
**Hecho cuando**: el runner rechaza un nodo si faltan scopes/credenciales.

---

## Fase S4 — Scheduler (cron) y triggers
**Objetivo**: Disparar estrategias por tiempo o eventos.
**Cambios**:
- Scheduler basado en APScheduler o croniter + Redis (persistente, multi-worker).
- Tipos: `cron` (expresión estándar), `webhook` (POST firmado), `manual`, `programmatic` (SDK).
- Guards: ventanas de mantenimiento, **rate limiting** por estrategia.
**Archivos**: `app/scheduler/scheduler_service.py`, `app/routers/webhooks_router.py`.
**Hecho cuando**: una spec con trigger cron se ejecuta a la hora programada.

---

## Fase S5 — StrategyRunner (DAG, async, idempotente)
**Objetivo**: Ejecutar flujos de forma segura y trazable.
**Cambios**:
- Ejecución **DAG** en orden topológico, paralelismo por “niveles” con límites por org/estrategia.
- **Idempotencia** por `run_key` (trigger + timestamp discretizado o key externa).
- **Timeouts** y **retry/backoff** por nodo; **DLQ** (dead-letter) opcional.
- **Outbox** para eventos, `RunEvent` detallado, `status.progress`/`result.partial` por nodo.
- **OpenTelemetry**: span por nodo, atributos de coste/tokens.
**Archivos**: `app/strategies/runner.py`, `app/strategies/execution_context.py`.
**Hecho cuando**: el mismo trigger no duplica ejecuciones con igual `run_key`.

---

## Fase S6 — Guardrails y seguridad avanzada
**Objetivo**: Riesgo controlado por nodo y estrategia.
**Cambios**:
- `risk` en nodos (`low|med|high`) → confirmación previa si se lanza manual.
- **Prompt Firewall** en nodos LLM; redacción/mascarado de PII.
- **Scopes de función** ya definidos en AppRegistry; enforcement centralizado.
**Archivos**: `app/security/guardrails_strategy.py`.
**Hecho cuando**: nodos de riesgo medio/alto requieren confirmación.

---

## Fase S7 — Secrets y credenciales
**Objetivo**: Manejo de secretos seguro.
**Cambios**:
- Almacenamiento cifrado (AES-GCM) + rotación; inyección just-in-time al nodo.
- **Connection test** por app (p. ej., Gmail `me/profile`).
- **Per-org** y **per-user** (opcional) con herencia controlada.
**Archivos**: `app/security/credentials_service.py`.
**Hecho cuando**: credenciales inválidas bloquean activación del trigger.

---

## Fase S8 — Observabilidad, métricas y costes
**Objetivo**: Operación proactiva.
**Cambios**:
- Métricas `/metrics` por estrategia: runs, latencia, éxito, coste/tokens, fallos por nodo.
- **Telemetry snapshot** en `Run` + enlaces a trazas OTel.
- Alertas (Prometheus) por tasa de fallos y timeouts.
**Archivos**: `app/observability/metrics_strategies.py`.
**Hecho cuando**: dashboards muestran salud por estrategia y por org.

---

## Fase S9 — SDKs y Webhooks de salida
**Objetivo**: Integrabilidad.
**Cambios**:
- SDK mínimo (TS/Python): lanzar estrategias, pasar `input`, consultar estado.
- Webhooks de salida: `on_run_started`, `on_node_completed`, `on_run_finished` (firma HMAC).
**Archivos**: `sdk/js`, `sdk/python`, `app/routers/outgoing_webhooks.py`.
**Hecho cuando**: un cliente externo lanza una estrategia y recibe callbacks.

---

## Fase S10 — QA, sandbox y “dry-run”
**Objetivo**: Confiar antes de activar.
**Cambios**:
- **Dry-run**: simula nodos (sin efectos) y valida datos.
- **Sandbox de apps**: mocks para Gmail/Notion con resultados deterministas.
- Evals mínimos: asserts de shape/contratos por nodo.
**Archivos**: `app/strategies/dryrun.py`, `tests/test_strategies_e2e.py`.
**Hecho cuando**: se puede probar una estrategia compleja sin enviar emails reales.

---

## Fase S11 — Marketplace interno (opcional)
**Objetivo**: Reutilización y aceleración.
**Cambios**:
- Catálogo de **plantillas** (estrategias compartibles) con permisos.
- Instalación por org → crea Strategy + credenciales requeridas (wizard).
**Archivos**: `app/strategies/templates/`, `app/routers/marketplace_router.py`.
**Hecho cuando**: una plantilla “Gmail resumen diario” se instala y corre.

---

## Ejemplo mínimo de Strategy (YAML)
```yaml
metadata:
  name: gmail_daily_summary
  description: Envía un resumen diario a mi email
permissions:
  credentials:
    - app: gmail
      scopes: ["gmail.send", "gmail.read"]
triggers:
  - type: cron
    config:
      expression: "0 8 * * *"  # todos los días 08:00
spec:
  nodes:
    - key: fetch_threads
      app: gmail
      action: search_threads
      config:
        query: "newer_than:1d -category:social -category:promotions"
      timeout_s: 30
      retry_policy: {max: 2, backoff: "exp"}
    - key: summarize
      app: llm
      action: summarize_text
      config:
        input_from: fetch_threads
      timeout_s: 60
      risk: low
    - key: send_email
      app: gmail
      action: send_email
      config:
        to: "me@example.com"
        subject: "Resumen diario"
        body_from: summarize
  edges:
    - from: fetch_threads
      to: summarize
    - from: summarize
      to: send_email
```

---

## Criterios generales de aceptación
- Subida de estrategias en JSON/YAML con validaciones exhaustivas.
- Triggers funcionando (cron/webhook/manual) con idempotencia por `run_key`.
- Apps con scopes/credenciales verificadas y enforcement en runtime.
- Observabilidad: métricas y trazas por run y por nodo.
- Tests e2e que cubren éxito, timeout, retry, y dry-run.
