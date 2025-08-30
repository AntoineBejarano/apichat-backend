# 🚀 PLAN WORKFLOW ENGINE ENTERPRISE - Motor de Workflows tipo n8n para APIchat

## 📋 Resumen Ejecutivo

**Objetivo**: Implementar un motor de workflows enterprise-grade que permita crear, ejecutar y gestionar workflows complejos con triggers inteligentes, nodos universales y orquestación avanzada, integrado perfectamente con el sistema actual de APIchat.

**Filosofía**: Construir sobre lo existente, no reemplazar. Cada workflow se ejecuta como un Plan, cada nodo como un To-do, manteniendo la compatibilidad total con el sistema actual.

---

## 🧰 **AJUSTES CLAVE PARA ENTERPRISE-GRADE (TOP 12)**

### **1. 🔗 Consistencia de Modelos**
- **workflow_runs.plan_id** → referencia a `plans` (no `user_plans`)
- **workflow_run_id** en `plans` para trazabilidad 1:1
- **workflow_node_id** en `plan_tasks` para mapeo directo

### **2. ⚡ Runtime Único (Redis) y Estados**
- **Contrato de claves**: `wf:{run_id}:meta`, `wf:{run_id}:node:{node_id}`
- **Log append-only** con progreso %
- **Reanudación**: `resume_token` + idempotencia por nodo

### **3. 🔄 Idempotencia & Dedupe**
- **Clave estándar** por nodo (hash de inputs normalizados)
- **Idempotency-Key** para llamadas HTTP externas
- **Deduplicación** automática de ejecuciones

### **4. 🔁 Retries / Timeouts / Circuit Breaker**
- **Política por nodo**: reintentos, backoff con jitter, timeout
- **Circuit breaker** por credencial+endpoint
- **Degradación gradual** en fallos

### **5. 📝 Tipado & Validación**
- **JSON Schema** por tipo de nodo (input/output)
- **Structured outputs** con validación estricta para IA
- **Validación en tiempo real** durante ejecución

### **6. 🧮 Motor de Expresiones y Plantillas**
- **Sintaxis única**: `{{ }}` + funciones mínimas
- **Funciones**: jsonPath, hash, now, math, string
- **Variables**: run, nodo, secrets, env

### **7. 🔐 Credentials**
- **workflow_credentials** con scopes, rotación, expiración
- **Masking en logs** automático
- **Enlace credencial ↔ nodo** por `credentialsRef`

### **8. 🔀 Control de Flujo Mínimo**
- **MVP**: Iterator (ForEach), Switch/If, Transform, Delay/Wait
- **Parallel** → Fase 2
- **Control de flujo declarativo**

### **9. 📊 Observabilidad**
- **Correlación**: request_id/run_id
- **Métricas por nodo**: latencia, retries, errores, coste AI
- **Estados en tiempo real** para chat

### **10. 🚦 Políticas/Cuotas/Backpressure**
- **Límites** por usuario/tenant y credencial
- **Cola con prioridades** y degradación ligera
- **Rate limiting** inteligente

### **11. ⚠️ Errores & Compensación**
- **onError** por workflow y nodo (stop/continue/route)
- **Saga/compensation** declarativa (Fase 2)
- **Recovery automático**

### **12. 📥 Import de APIs**
- **Ingesta OpenAPI/Postman** para autogenerar nodos HTTP
- **Tipado automático** de headers/body/paginación
- **Validación de esquemas** importados

---

## 🎯 **FASE 1: Fundación - Triggers y Nodos Básicos**

### **1.1 Objetivos**
- Implementar triggers básicos (webhook, cron, manual)
- Crear nodos universales básicos (HTTP, DB, AI)
- Integración con sistema de planes existente
- **Resolver lagunas críticas de seguridad y validación**

### **1.2 Nuevos Modelos de Base de Datos**

```sql
-- ===== WORKFLOW SCHEMA VERSIONS =====
CREATE TABLE workflow_schema_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version VARCHAR(20) NOT NULL UNIQUE,
    schema_definition JSONB NOT NULL, -- JSON Schema para validar workflow_spec
    is_active BOOLEAN DEFAULT false,
    migration_script TEXT, -- Script para migrar de versión anterior
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== WORKFLOWS =====
CREATE TABLE workflow_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0.0', -- Referencia a workflow_schema_versions
    workflow_spec JSONB NOT NULL, -- Definición completa del workflow
    is_active BOOLEAN DEFAULT true,
    is_template BOOLEAN DEFAULT false,
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    retention_days INTEGER DEFAULT 90, -- Política de retención
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_workflow_schema_version 
        FOREIGN KEY (schema_version) REFERENCES workflow_schema_versions(version)
);

-- ===== TRIGGERS =====
CREATE TABLE workflow_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    trigger_type VARCHAR(20) NOT NULL, -- webhook, cron, manual, event, db_watch
    trigger_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    trigger_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== WORKFLOW RUNS =====
CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id UUID REFERENCES plans(id) ON DELETE SET NULL, -- AJUSTE: referencia a plans (no user_plans)
    trigger_type VARCHAR(20) NOT NULL,
    trigger_data JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, paused
    current_node_id VARCHAR(100),
    execution_state JSONB DEFAULT '{}',
    variables JSONB DEFAULT '{}', -- Variables del workflow con valores por defecto
    cost_tracking JSONB DEFAULT '{}', -- Tracking de costes AI por run
    resume_token VARCHAR(255), -- Para reanudación de ejecuciones
    request_id VARCHAR(255), -- Para correlación de logs
    progress_percentage INTEGER DEFAULT 0, -- Progreso del workflow
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE -- Para política de retención
);

-- ===== NODE EXECUTIONS =====
CREATE TABLE workflow_node_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(100) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending, running, completed, failed, skipped
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    masked_logs TEXT, -- Logs con PII enmascarado
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    is_idempotent BOOLEAN DEFAULT false,
    idempotency_key VARCHAR(255), -- Clave única para deduplicación
    transaction_id VARCHAR(255), -- Para rollback de transacciones DB
    credentials_ref VARCHAR(255), -- Referencia a credencial (no datos en claro)
    circuit_breaker_state VARCHAR(20) DEFAULT 'closed', -- closed, open, half_open
    error_message TEXT,
    execution_time_ms INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== CREDENTIALS =====
CREATE TABLE workflow_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    credential_type VARCHAR(50) NOT NULL, -- api_key, oauth2, basic_auth, custom
    encrypted_data JSONB NOT NULL, -- Datos encriptados
    scopes JSONB DEFAULT '[]',
    expires_at TIMESTAMP WITH TIME ZONE,
    rotation_schedule VARCHAR(50), -- daily, weekly, monthly, manual
    last_rotated_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== NODE TYPE SCHEMAS =====
CREATE TABLE workflow_node_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type VARCHAR(50) NOT NULL UNIQUE,
    input_schema JSONB NOT NULL, -- JSON Schema para validar inputs
    output_schema JSONB NOT NULL, -- JSON Schema para validar outputs
    version VARCHAR(20) DEFAULT '1.0.0',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== EXPRESSION FUNCTIONS =====
CREATE TABLE workflow_expression_functions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    function_name VARCHAR(100) NOT NULL UNIQUE,
    function_type VARCHAR(50) NOT NULL, -- jsonPath, hash, now, math, string
    implementation TEXT NOT NULL, -- Código Python/JavaScript
    parameters_schema JSONB NOT NULL, -- Schema de parámetros
    return_type VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== RBAC PERMISSIONS =====
CREATE TABLE workflow_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL, -- workflow, credential, template
    resource_id UUID NOT NULL,
    permission VARCHAR(50) NOT NULL, -- read, write, execute, admin
    granted_by UUID REFERENCES users(id),
    granted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id, resource_type, resource_id, permission)
);

-- ===== COST LIMITS =====
CREATE TABLE workflow_cost_limits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    limit_type VARCHAR(50) NOT NULL, -- daily_ai_cost, monthly_ai_cost, per_run_cost
    limit_value DECIMAL(10,4) NOT NULL,
    current_usage DECIMAL(10,4) DEFAULT 0,
    reset_period VARCHAR(20) NOT NULL, -- daily, monthly
    last_reset_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, limit_type)
);
```

### **1.3 Nuevos Servicios**

```python
# app/services/workflow/workflow_schema_service.py
class WorkflowSchemaService:
    """Gestión de esquemas y validación de workflows"""
    
    async def validate_workflow_spec(self, spec: Dict[str, Any], schema_version: str) -> ValidationResult
    async def migrate_workflow_spec(self, spec: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]
    async def get_schema_definition(self, version: str) -> Dict[str, Any]
    async def create_schema_version(self, version: str, schema: Dict[str, Any]) -> WorkflowSchemaVersion

# app/services/workflow/workflow_definition_service.py
class WorkflowDefinitionService:
    """Gestión de definiciones de workflows"""
    
    async def create_workflow(self, data: WorkflowCreate) -> WorkflowDefinition
    async def get_user_workflows(self, user_id: UUID) -> List[WorkflowDefinition]
    async def update_workflow(self, workflow_id: UUID, data: WorkflowUpdate) -> WorkflowDefinition
    async def delete_workflow(self, workflow_id: UUID) -> bool
    async def validate_workflow_spec(self, spec: Dict[str, Any]) -> ValidationResult

# app/services/workflow/workflow_trigger_service.py
class WorkflowTriggerService:
    """Gestión de triggers de workflows"""
    
    async def create_trigger(self, workflow_id: UUID, data: TriggerCreate) -> WorkflowTrigger
    async def activate_trigger(self, trigger_id: UUID) -> bool
    async def deactivate_trigger(self, trigger_id: UUID) -> bool
    async def handle_webhook(self, trigger_id: UUID, payload: Dict[str, Any]) -> WorkflowRun
    async def handle_cron_trigger(self, trigger_id: UUID) -> WorkflowRun

# app/services/workflow/workflow_execution_service.py
class WorkflowExecutionService:
    """Ejecución de workflows usando LangGraph"""
    
    async def start_workflow_execution(self, workflow_id: UUID, trigger_data: Dict[str, Any]) -> WorkflowRun
    async def pause_workflow_execution(self, run_id: UUID) -> bool
    async def resume_workflow_execution(self, run_id: UUID, resume_token: str) -> bool  # AJUSTE: resume_token
    async def cancel_workflow_execution(self, run_id: UUID) -> bool
    async def get_execution_status(self, run_id: UUID) -> WorkflowRunStatus
    async def rollback_failed_execution(self, run_id: UUID) -> bool

# app/services/workflow/workflow_runtime_service.py  # NUEVO
class WorkflowRuntimeService:
    """Gestión del runtime Redis y estados"""
    
    async def store_workflow_state(self, run_id: UUID, state: Dict[str, Any]) -> bool
    async def get_workflow_state(self, run_id: UUID) -> Dict[str, Any]
    async def update_progress(self, run_id: UUID, percentage: int) -> bool
    async def append_log(self, run_id: UUID, log_entry: str) -> bool
    async def get_workflow_logs(self, run_id: UUID) -> List[str]

# app/services/workflow/expression_engine_service.py  # NUEVO
class ExpressionEngineService:
    """Motor de expresiones y plantillas"""
    
    async def evaluate_expression(self, expression: str, context: Dict[str, Any]) -> Any
    async def validate_expression(self, expression: str) -> ValidationResult
    async def extract_variables(self, expression: str) -> List[str]
    async def register_function(self, function_name: str, implementation: str) -> bool

# app/services/workflow/idempotency_service.py  # NUEVO
class IdempotencyService:
    """Gestión de idempotencia y deduplicación"""
    
    async def generate_idempotency_key(self, node_id: str, inputs: Dict[str, Any]) -> str
    async def check_idempotency(self, idempotency_key: str) -> Optional[WorkflowNodeExecution]
    async def mark_as_processed(self, idempotency_key: str, execution_id: UUID) -> bool
    async def cleanup_expired_keys(self) -> int

# app/services/workflow/circuit_breaker_service.py  # NUEVO
class CircuitBreakerService:
    """Gestión de circuit breakers"""
    
    async def check_circuit_breaker(self, credential_id: str, endpoint: str) -> bool
    async def record_success(self, credential_id: str, endpoint: str) -> bool
    async def record_failure(self, credential_id: str, endpoint: str) -> bool
    async def get_breaker_state(self, credential_id: str, endpoint: str) -> str

# app/services/workflow/security_service.py
class WorkflowSecurityService:
    """Gestión de seguridad y RBAC"""
    
    async def check_permission(self, user_id: UUID, resource_type: str, resource_id: UUID, permission: str) -> bool
    async def grant_permission(self, user_id: UUID, resource_type: str, resource_id: UUID, permission: str) -> bool
    async def revoke_permission(self, user_id: UUID, resource_type: str, resource_id: UUID, permission: str) -> bool
    async def mask_pii_in_logs(self, logs: str) -> str
    async def audit_action(self, user_id: UUID, action: str, resource_type: str, resource_id: UUID) -> bool

# app/services/workflow/cost_control_service.py
class WorkflowCostControlService:
    """Control de costes AI y límites"""
    
    async def check_cost_limit(self, user_id: UUID, estimated_cost: float) -> bool
    async def track_ai_cost(self, run_id: UUID, tokens: int, cost: float, provider: str) -> bool
    async def get_daily_usage(self, user_id: UUID) -> Dict[str, Any]
    async def reset_daily_limits(self, user_id: UUID) -> bool
    async def get_cost_alerts(self, user_id: UUID) -> List[CostAlert]

# app/services/workflow/api_import_service.py  # NUEVO
class APIImportService:
    """Import de APIs OpenAPI/Postman"""
    
    async def import_openapi_spec(self, spec_url: str, user_id: UUID) -> List[WorkflowNodeSchema]
    async def import_postman_collection(self, collection_data: Dict[str, Any], user_id: UUID) -> List[WorkflowNodeSchema]
    async def generate_http_nodes(self, api_spec: Dict[str, Any]) -> List[Dict[str, Any]]
    async def validate_imported_schema(self, schema: Dict[str, Any]) -> ValidationResult
```

### **1.4 Endpoints Frontend**

```python
# app/routers/workflow_router.py

# ===== SCHEMA VALIDATION =====
@router.post("/schemas/validate", response_model=ValidationResultOut)
async def validate_workflow_schema(data: SchemaValidationRequest, factory: ServiceFactory = Depends(get_factory))

@router.get("/schemas/versions", response_model=List[SchemaVersionOut])
async def get_schema_versions(factory: ServiceFactory = Depends(get_factory))

@router.post("/schemas/migrate", response_model=WorkflowSpecOut)
async def migrate_workflow_schema(data: SchemaMigrationRequest, factory: ServiceFactory = Depends(get_factory))

# ===== WORKFLOW DEFINITIONS =====
@router.post("/workflows", response_model=WorkflowDefinitionOut)
async def create_workflow(data: WorkflowCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows", response_model=List[WorkflowDefinitionOut])
async def get_user_workflows(factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinitionOut)
async def get_workflow(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.put("/workflows/{workflow_id}", response_model=WorkflowDefinitionOut)
async def update_workflow(workflow_id: UUID, data: WorkflowUpdate, factory: ServiceFactory = Depends(get_factory))

@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

# ===== TRIGGERS =====
@router.post("/workflows/{workflow_id}/triggers", response_model=WorkflowTriggerOut)
async def create_trigger(workflow_id: UUID, data: TriggerCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}/triggers", response_model=List[WorkflowTriggerOut])
async def get_workflow_triggers(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/triggers/{trigger_id}/activate")
async def activate_trigger(trigger_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/triggers/{trigger_id}/deactivate")
async def deactivate_trigger(trigger_id: UUID, factory: ServiceFactory = Depends(get_factory))

# ===== EXECUTION =====
@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowRunOut)
async def execute_workflow(workflow_id: UUID, data: WorkflowExecutionRequest, factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}/runs", response_model=List[WorkflowRunOut])
async def get_workflow_runs(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.get("/runs/{run_id}", response_model=WorkflowRunOut)
async def get_workflow_run(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/runs/{run_id}/pause")
async def pause_workflow_run(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/runs/{run_id}/resume")
async def resume_workflow_run(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/runs/{run_id}/cancel")
async def cancel_workflow_run(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

# ===== WEBHOOKS =====
@router.post("/webhooks/{trigger_id}")
async def webhook_endpoint(trigger_id: UUID, payload: Dict[str, Any], request: Request)

# ===== CREDENTIALS =====
@router.post("/credentials", response_model=WorkflowCredentialOut)
async def create_credential(data: CredentialCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/credentials", response_model=List[WorkflowCredentialOut])
async def get_user_credentials(factory: ServiceFactory = Depends(get_factory))

@router.put("/credentials/{credential_id}", response_model=WorkflowCredentialOut)
async def update_credential(credential_id: UUID, data: CredentialUpdate, factory: ServiceFactory = Depends(get_factory))

@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: UUID, factory: ServiceFactory = Depends(get_factory))

# ===== SECURITY & RBAC =====
@router.post("/permissions/grant")
async def grant_permission(data: PermissionGrantRequest, factory: ServiceFactory = Depends(get_factory))

@router.post("/permissions/revoke")
async def revoke_permission(data: PermissionRevokeRequest, factory: ServiceFactory = Depends(get_factory))

@router.get("/permissions/check")
async def check_permission(resource_type: str, resource_id: UUID, permission: str, factory: ServiceFactory = Depends(get_factory))

# ===== COST CONTROL =====
@router.get("/costs/limits", response_model=List[CostLimitOut])
async def get_cost_limits(factory: ServiceFactory = Depends(get_factory))

@router.post("/costs/limits", response_model=CostLimitOut)
async def create_cost_limit(data: CostLimitCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/costs/usage", response_model=CostUsageOut)
async def get_cost_usage(time_range: str = "24h", factory: ServiceFactory = Depends(get_factory))

@router.post("/costs/check")
async def check_cost_limit(estimated_cost: float, factory: ServiceFactory = Depends(get_factory))

# ===== RUNTIME & EXPRESSIONS =====
@router.get("/runs/{run_id}/state", response_model=WorkflowStateOut)
async def get_workflow_state(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.get("/runs/{run_id}/logs", response_model=List[str])
async def get_workflow_logs(run_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/expressions/validate", response_model=ValidationResultOut)
async def validate_expression(data: ExpressionValidationRequest, factory: ServiceFactory = Depends(get_factory))

@router.post("/expressions/evaluate", response_model=ExpressionResultOut)
async def evaluate_expression(data: ExpressionEvaluationRequest, factory: ServiceFactory = Depends(get_factory))

# ===== API IMPORT =====
@router.post("/apis/import/openapi", response_model=List[WorkflowNodeSchemaOut])
async def import_openapi_spec(data: OpenAPIImportRequest, factory: ServiceFactory = Depends(get_factory))

@router.post("/apis/import/postman", response_model=List[WorkflowNodeSchemaOut])
async def import_postman_collection(data: PostmanImportRequest, factory: ServiceFactory = Depends(get_factory))
```

### **1.5 Integración con Sistema Actual**

```python
# Modificación del PlanExecutionService existente
class PlanExecutionService:
    async def start_plan_execution(self, plan_id: UUID, user_id: UUID, **kwargs):
        # Verificar si es un workflow
        if plan_id in self.workflow_plans:
            return await self._execute_workflow_plan(plan_id, user_id, **kwargs)
        else:
            # Ejecución normal de plan
            return await self._execute_regular_plan(plan_id, user_id, **kwargs)
    
    async def _execute_workflow_plan(self, plan_id: UUID, user_id: UUID, **kwargs):
        """Ejecuta un plan que viene de un workflow"""
        workflow_run = await self.workflow_service.get_run_by_plan_id(plan_id)
        return await self.workflow_service.execute_workflow(workflow_run.workflow_id, **kwargs)

# Modificaciones necesarias en modelos existentes
class Plan(Base):  # AJUSTE: Referencia a plans (no user_plans)
    # ... campos existentes ...
    workflow_run_id = Column(UUID(as_uuid=True), ForeignKey("workflow_runs.id"), nullable=True)
    workflow_run = relationship("WorkflowRun", back_populates="plan")

class PlanTask(Base):
    # ... campos existentes ...
    workflow_node_id = Column(String(100), nullable=True)
    is_workflow_node = Column(Boolean, default=False)
```

### **1.6 Especificaciones Técnicas Críticas**

#### **JSON Schema para Workflow Spec (v1.0.0) - AJUSTADO**
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["version", "nodes", "connections"],
  "properties": {
    "version": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+$"},
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "type", "config"],
        "properties": {
          "id": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
          "type": {"type": "string", "enum": ["http", "database", "ai", "transform", "conditional", "iterator", "switch", "delay"]},
          "config": {"type": "object"},
          "credentialsRef": {"type": "string"}, // AJUSTE: Referencia a credencial
          "retry_policy": {
            "type": "object",
            "properties": {
              "max_retries": {"type": "integer", "minimum": 0, "maximum": 10},
              "backoff_multiplier": {"type": "number", "minimum": 1.0},
              "jitter": {"type": "boolean", "default": true}, // AJUSTE: Jitter para backoff
              "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 3600}, // AJUSTE: Timeout
              "is_idempotent": {"type": "boolean"}
            }
          },
          "pagination": {
            "type": "object",
            "properties": {
              "strategy": {"type": "string", "enum": ["offset", "cursor", "nextLink"]},
              "page_size": {"type": "integer", "minimum": 1, "maximum": 1000}
            }
          },
          "onError": { // AJUSTE: Manejo de errores
            "type": "object",
            "properties": {
              "action": {"type": "string", "enum": ["stop", "continue", "route"]},
              "route_to": {"type": "string"},
              "retry": {"type": "boolean"}
            }
          }
        }
      }
    },
    "connections": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["from", "to"],
        "properties": {
          "from": {"type": "string"},
          "to": {"type": "string"},
          "condition": {"type": "string"} // AJUSTE: Expresiones con {{ }}
        }
      }
    },
    "variables": {
      "type": "object",
      "patternProperties": {
        "^[a-zA-Z_][a-zA-Z0-9_]*$": {
          "type": "object",
          "required": ["default_value"],
          "properties": {
            "default_value": {},
            "description": {"type": "string"},
            "required": {"type": "boolean"},
            "source": {"type": "string", "enum": ["run", "node", "secrets", "env"]} // AJUSTE: Fuente de variable
          }
        }
      }
    }
  }
}
```

#### **Contrato de Claves Redis**
```python
# Contrato estándar para claves Redis
REDIS_KEYS = {
    "workflow_meta": "wf:{run_id}:meta",
    "workflow_node": "wf:{run_id}:node:{node_id}",
    "workflow_log": "wf:{run_id}:log",  # Append-only
    "workflow_progress": "wf:{run_id}:progress",
    "workflow_variables": "wf:{run_id}:vars",
    "idempotency": "idem:{hash_key}",
    "circuit_breaker": "cb:{credential_id}:{endpoint}",
    "rate_limit": "rl:{user_id}:{resource}"
}
```

#### **Motor de Expresiones**
```python
# Sintaxis de expresiones: {{ function(args) }}
EXPRESSION_FUNCTIONS = {
    "jsonPath": "{{ jsonPath(data, '$.field') }}",
    "hash": "{{ hash('sha256', data) }}",
    "now": "{{ now('iso') }}",
    "math": "{{ math('add', a, b) }}",
    "string": "{{ string('format', 'Hello {name}', name=user.name) }}"
}
```

#### **Políticas de Seguridad**
```python
# Configuración de enmascaramiento PII
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})",
    "ssn": r"\b\d{3}-?\d{2}-?\d{4}\b",
    "credit_card": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"
}

# Políticas de retención
RETENTION_POLICIES = {
    "workflow_runs": 90,  # días
    "node_executions": 30,
    "audit_logs": 365,
    "cost_tracking": 730
}
```

---

## 🎯 **FASE 2: Nodos Avanzados y Control de Flujo**

### **2.1 Objetivos**
- Implementar nodos de control de flujo (Switch, If, ForEach, Parallel)
- Nodos de transformación de datos
- Sistema de variables y plantillas

### **2.2 Nuevos Tipos de Nodos**

```python
# app/services/workflow/nodes/
class SwitchNode(WorkflowNode):
    """Nodo de control de flujo condicional"""
    
class ForEachNode(WorkflowNode):
    """Nodo para iterar sobre arrays"""
    
class ParallelNode(WorkflowNode):
    """Nodo para ejecución paralela"""
    
class TransformNode(WorkflowNode):
    """Nodo para transformación de datos"""
    
class DelayNode(WorkflowNode):
    """Nodo para delays y esperas"""
```

### **2.3 Sistema de Variables y Plantillas**

```python
# app/services/workflow/template_engine.py
class WorkflowTemplateEngine:
    """Motor de plantillas para workflows"""
    
    def render_template(self, template: str, variables: Dict[str, Any]) -> str
    def extract_variables(self, template: str) -> List[str]
    def validate_template(self, template: str) -> ValidationResult
```

### **2.4 Endpoints Adicionales**

```python
# ===== TEMPLATE ENGINE =====
@router.post("/templates/validate")
async def validate_template(data: TemplateValidationRequest, factory: ServiceFactory = Depends(get_factory))

@router.post("/templates/render")
async def render_template(data: TemplateRenderRequest, factory: ServiceFactory = Depends(get_factory))

# ===== NODE TYPES =====
@router.get("/node-types", response_model=List[NodeTypeOut])
async def get_available_node_types(factory: ServiceFactory = Depends(get_factory))

@router.get("/node-types/{node_type}/schema", response_model=NodeTypeSchemaOut)
async def get_node_type_schema(node_type: str, factory: ServiceFactory = Depends(get_factory))
```

---

## 🎯 **FASE 3: Triggers Avanzados y Event Bus**

### **3.1 Objetivos**
- Implementar triggers de base de datos (DB-watch)
- Sistema de eventos interno
- Triggers de API events

### **3.2 Nuevos Modelos**

```sql
-- ===== EVENT DEFINITIONS =====
CREATE TABLE workflow_event_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- db_change, api_call, user_action
    event_schema JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== DB WATCH TRIGGERS =====
CREATE TABLE workflow_db_watch_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_id UUID NOT NULL REFERENCES workflow_triggers(id) ON DELETE CASCADE,
    db_id UUID NOT NULL REFERENCES databases(id) ON DELETE CASCADE,
    table_name VARCHAR(255) NOT NULL,
    operation_type VARCHAR(20) NOT NULL, -- INSERT, UPDATE, DELETE
    filter_conditions JSONB DEFAULT '{}',
    polling_interval_seconds INTEGER DEFAULT 30,
    last_polled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **3.3 Servicios de Eventos**

```python
# app/services/workflow/event_service.py
class WorkflowEventService:
    """Gestión de eventos del sistema"""
    
    async def emit_event(self, event_type: str, data: Dict[str, Any], user_id: UUID)
    async def subscribe_to_event(self, event_type: str, workflow_id: UUID)
    async def handle_db_change(self, db_id: UUID, table: str, operation: str, data: Dict[str, Any])

# app/services/workflow/db_watch_service.py
class DatabaseWatchService:
    """Monitoreo de cambios en bases de datos"""
    
    async def start_watching_table(self, db_id: UUID, table: str, trigger_id: UUID)
    async def stop_watching_table(self, trigger_id: UUID)
    async def poll_database_changes(self, db_id: UUID, table: str, last_polled: datetime)
```

---

## 🎯 **FASE 4: Idempotencia, Retries y Circuit Breaker**

### **4.1 Objetivos**
- Sistema de idempotencia robusto
- Retries con backoff exponencial
- Circuit breaker para APIs

### **4.2 Nuevos Modelos**

```sql
-- ===== IDEMPOTENCY =====
CREATE TABLE workflow_idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(idempotency_key)
);

-- ===== CIRCUIT BREAKERS =====
CREATE TABLE workflow_circuit_breakers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL, -- api_endpoint, database, external_service
    resource_id VARCHAR(255) NOT NULL,
    failure_count INTEGER DEFAULT 0,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    state VARCHAR(20) DEFAULT 'closed', -- closed, open, half_open
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, resource_type, resource_id)
);
```

### **4.3 Servicios de Resiliencia**

```python
# app/services/workflow/idempotency_service.py
class IdempotencyService:
    """Gestión de idempotencia"""
    
    async def generate_idempotency_key(self, workflow_id: UUID, trigger_data: Dict[str, Any]) -> str
    async def check_idempotency(self, idempotency_key: str) -> Optional[WorkflowRun]
    async def mark_as_processed(self, idempotency_key: str, run_id: UUID)

# app/services/workflow/circuit_breaker_service.py
class CircuitBreakerService:
    """Gestión de circuit breakers"""
    
    async def check_circuit_breaker(self, resource_type: str, resource_id: str, user_id: UUID) -> bool
    async def record_success(self, resource_type: str, resource_id: str, user_id: UUID)
    async def record_failure(self, resource_type: str, resource_id: str, user_id: UUID)
```

---

## 🎯 **FASE 5: Observabilidad y Monitoreo**

### **5.1 Objetivos**
- Métricas detalladas de workflows
- Logs estructurados
- Alertas y notificaciones

### **5.2 Nuevos Modelos**

```sql
-- ===== WORKFLOW METRICS =====
CREATE TABLE workflow_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(100),
    metric_type VARCHAR(50) NOT NULL, -- execution_time, memory_usage, api_calls, cost
    metric_value DECIMAL(15,4) NOT NULL,
    metric_unit VARCHAR(20),
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== WORKFLOW ALERTS =====
CREATE TABLE workflow_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL, -- failure_rate, execution_time, cost_threshold
    alert_config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **5.3 Servicios de Observabilidad**

```python
# app/services/workflow/metrics_service.py
class WorkflowMetricsService:
    """Recolección y análisis de métricas"""
    
    async def record_metric(self, run_id: UUID, metric_type: str, value: float, unit: str = None)
    async def get_workflow_metrics(self, workflow_id: UUID, time_range: str) -> Dict[str, Any]
    async def get_user_metrics_summary(self, user_id: UUID) -> Dict[str, Any]

# app/services/workflow/alerting_service.py
class WorkflowAlertingService:
    """Sistema de alertas"""
    
    async def create_alert(self, user_id: UUID, alert_config: AlertConfig) -> WorkflowAlert
    async def check_alerts(self, run_id: UUID)
    async def send_alert_notification(self, alert_id: UUID, message: str)
```

### **5.4 Endpoints de Observabilidad**

```python
# ===== METRICS =====
@router.get("/workflows/{workflow_id}/metrics", response_model=WorkflowMetricsOut)
async def get_workflow_metrics(workflow_id: UUID, time_range: str = "24h", factory: ServiceFactory = Depends(get_factory))

@router.get("/metrics/summary", response_model=UserMetricsSummaryOut)
async def get_user_metrics_summary(factory: ServiceFactory = Depends(get_factory))

# ===== ALERTS =====
@router.post("/alerts", response_model=WorkflowAlertOut)
async def create_alert(data: AlertCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/alerts", response_model=List[WorkflowAlertOut])
async def get_user_alerts(factory: ServiceFactory = Depends(get_factory))

@router.put("/alerts/{alert_id}", response_model=WorkflowAlertOut)
async def update_alert(alert_id: UUID, data: AlertUpdate, factory: ServiceFactory = Depends(get_factory))
```

---

## 🎯 **FASE 6: Testing, Sandbox y Versionado**

### **6.1 Objetivos**
- Sistema de testing de workflows
- Sandbox para desarrollo
- Versionado y despliegue

### **6.2 Nuevos Modelos**

```sql
-- ===== WORKFLOW VERSIONS =====
CREATE TABLE workflow_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    workflow_spec JSONB NOT NULL,
    changelog TEXT,
    is_published BOOLEAN DEFAULT false,
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(workflow_id, version)
);

-- ===== WORKFLOW TESTS =====
CREATE TABLE workflow_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id UUID NOT NULL REFERENCES workflow_definitions(id) ON DELETE CASCADE,
    test_name VARCHAR(255) NOT NULL,
    test_data JSONB NOT NULL,
    expected_result JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== TEST RUNS =====
CREATE TABLE workflow_test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_id UUID NOT NULL REFERENCES workflow_tests(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    test_status VARCHAR(20) NOT NULL, -- passed, failed, error
    actual_result JSONB,
    error_message TEXT,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **6.3 Servicios de Testing**

```python
# app/services/workflow/testing_service.py
class WorkflowTestingService:
    """Testing de workflows"""
    
    async def create_test(self, workflow_id: UUID, test_data: TestCreate) -> WorkflowTest
    async def run_test(self, test_id: UUID) -> TestRunResult
    async def run_all_tests(self, workflow_id: UUID) -> List[TestRunResult]
    async def validate_workflow_spec(self, spec: Dict[str, Any]) -> ValidationResult

# app/services/workflow/versioning_service.py
class WorkflowVersioningService:
    """Versionado de workflows"""
    
    async def create_version(self, workflow_id: UUID, version: str, spec: Dict[str, Any]) -> WorkflowVersion
    async def publish_version(self, version_id: UUID) -> bool
    async def rollback_to_version(self, workflow_id: UUID, version: str) -> bool
    async def get_version_diff(self, version1_id: UUID, version2_id: UUID) -> Dict[str, Any]
```

### **6.4 Endpoints de Testing y Versionado**

```python
# ===== TESTING =====
@router.post("/workflows/{workflow_id}/tests", response_model=WorkflowTestOut)
async def create_test(workflow_id: UUID, data: TestCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}/tests", response_model=List[WorkflowTestOut])
async def get_workflow_tests(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/tests/{test_id}/run", response_model=TestRunResultOut)
async def run_test(test_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/workflows/{workflow_id}/tests/run-all", response_model=List[TestRunResultOut])
async def run_all_tests(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

# ===== VERSIONING =====
@router.post("/workflows/{workflow_id}/versions", response_model=WorkflowVersionOut)
async def create_version(workflow_id: UUID, data: VersionCreate, factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}/versions", response_model=List[WorkflowVersionOut])
async def get_workflow_versions(workflow_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/versions/{version_id}/publish")
async def publish_version(version_id: UUID, factory: ServiceFactory = Depends(get_factory))

@router.post("/workflows/{workflow_id}/rollback")
async def rollback_workflow(workflow_id: UUID, data: RollbackRequest, factory: ServiceFactory = Depends(get_factory))
```

---

## 🎯 **FASE 7: Plantillas, Reutilización y Catálogo**

### **7.1 Objetivos**
- Sistema de plantillas de workflows
- Catálogo de nodos reutilizables
- Librería de patrones comunes

### **7.2 Nuevos Modelos**

```sql
-- ===== WORKFLOW TEMPLATES =====
CREATE TABLE workflow_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    template_spec JSONB NOT NULL,
    is_public BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(id),
    usage_count INTEGER DEFAULT 0,
    rating DECIMAL(3,2) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== NODE LIBRARY =====
CREATE TABLE workflow_node_library (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    description TEXT,
    node_spec JSONB NOT NULL,
    is_public BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(id),
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== WORKFLOW PATTERNS =====
CREATE TABLE workflow_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_name VARCHAR(255) NOT NULL,
    pattern_type VARCHAR(100) NOT NULL, -- lead_processing, data_sync, notification
    description TEXT,
    pattern_spec JSONB NOT NULL,
    use_cases JSONB DEFAULT '[]',
    is_public BOOLEAN DEFAULT false,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **7.3 Servicios de Catálogo**

```python
# app/services/workflow/template_service.py
class WorkflowTemplateService:
    """Gestión de plantillas de workflows"""
    
    async def create_template(self, data: TemplateCreate) -> WorkflowTemplate
    async def get_public_templates(self, category: str = None) -> List[WorkflowTemplate]
    async def get_user_templates(self, user_id: UUID) -> List[WorkflowTemplate]
    async def use_template(self, template_id: UUID, user_id: UUID) -> WorkflowDefinition

# app/services/workflow/pattern_service.py
class WorkflowPatternService:
    """Gestión de patrones de workflows"""
    
    async def create_pattern(self, data: PatternCreate) -> WorkflowPattern
    async def get_patterns_by_type(self, pattern_type: str) -> List[WorkflowPattern]
    async def suggest_patterns(self, user_context: Dict[str, Any]) -> List[WorkflowPattern]
```

### **7.4 Endpoints de Catálogo**

```python
# ===== TEMPLATES =====
@router.get("/templates", response_model=List[WorkflowTemplateOut])
async def get_public_templates(category: str = None, factory: ServiceFactory = Depends(get_factory))

@router.post("/templates", response_model=WorkflowTemplateOut)
async def create_template(data: TemplateCreate, factory: ServiceFactory = Depends(get_factory))

@router.post("/templates/{template_id}/use", response_model=WorkflowDefinitionOut)
async def use_template(template_id: UUID, data: TemplateUseRequest, factory: ServiceFactory = Depends(get_factory))

# ===== PATTERNS =====
@router.get("/patterns", response_model=List[WorkflowPatternOut])
async def get_patterns(pattern_type: str = None, factory: ServiceFactory = Depends(get_factory))

@router.post("/patterns", response_model=WorkflowPatternOut)
async def create_pattern(data: PatternCreate, factory: ServiceFactory = Depends(get_factory))

@router.post("/patterns/suggest", response_model=List[WorkflowPatternOut])
async def suggest_patterns(data: PatternSuggestionRequest, factory: ServiceFactory = Depends(get_factory))
```

---

## 🎯 **FASE 8: Gobernanza, Costes y Compliance**

### **8.1 Objetivos**
- Control de costes por workflow
- Políticas de uso y cuotas
- Compliance y auditoría

### **8.2 Nuevos Modelos**

```sql
-- ===== COST TRACKING =====
CREATE TABLE workflow_cost_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    node_id VARCHAR(100),
    cost_type VARCHAR(50) NOT NULL, -- api_call, ai_tokens, compute_time
    provider VARCHAR(100),
    cost_amount DECIMAL(10,4) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== USAGE QUOTAS =====
CREATE TABLE workflow_usage_quotas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    quota_type VARCHAR(50) NOT NULL, -- daily_runs, monthly_cost, api_calls
    quota_limit DECIMAL(15,4) NOT NULL,
    current_usage DECIMAL(15,4) DEFAULT 0,
    reset_period VARCHAR(20) NOT NULL, -- daily, weekly, monthly
    last_reset_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ===== AUDIT LOG =====
CREATE TABLE workflow_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflow_definitions(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50) NOT NULL,
    resource_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### **8.3 Servicios de Gobernanza**

```python
# app/services/workflow/cost_service.py
class WorkflowCostService:
    """Gestión de costes de workflows"""
    
    async def track_cost(self, run_id: UUID, cost_type: str, amount: float, provider: str = None)
    async def get_user_costs(self, user_id: UUID, time_range: str) -> Dict[str, Any]
    async def get_workflow_costs(self, workflow_id: UUID, time_range: str) -> Dict[str, Any]
    async def check_cost_quota(self, user_id: UUID, estimated_cost: float) -> bool

# app/services/workflow/quota_service.py
class WorkflowQuotaService:
    """Gestión de cuotas de uso"""
    
    async def check_quota(self, user_id: UUID, quota_type: str, requested_amount: float) -> bool
    async def consume_quota(self, user_id: UUID, quota_type: str, amount: float) -> bool
    async def reset_quotas(self, user_id: UUID) -> bool
    async def get_quota_usage(self, user_id: UUID) -> Dict[str, Any]
```

### **8.4 Endpoints de Gobernanza**

```python
# ===== COST TRACKING =====
@router.get("/costs/summary", response_model=CostSummaryOut)
async def get_cost_summary(time_range: str = "30d", factory: ServiceFactory = Depends(get_factory))

@router.get("/workflows/{workflow_id}/costs", response_model=WorkflowCostsOut)
async def get_workflow_costs(workflow_id: UUID, time_range: str = "30d", factory: ServiceFactory = Depends(get_factory))

# ===== QUOTAS =====
@router.get("/quotas", response_model=List[QuotaUsageOut])
async def get_quota_usage(factory: ServiceFactory = Depends(get_factory))

@router.post("/quotas/check")
async def check_quota(data: QuotaCheckRequest, factory: ServiceFactory = Depends(get_factory))

# ===== AUDIT =====
@router.get("/audit", response_model=List[AuditLogOut])
async def get_audit_log(time_range: str = "7d", factory: ServiceFactory = Depends(get_factory))
```

---

## 🔧 **Integración con Sistema Actual**

### **Modificaciones Necesarias**

1. **UserPlan Model** - Agregar campo `workflow_run_id` opcional
2. **PlanTask Model** - Agregar campo `workflow_node_id` opcional
3. **PlanExecutionService** - Detectar si es workflow y delegar
4. **ServiceFactory** - Agregar getters para servicios de workflow
5. **Main.py** - Registrar nuevos routers

### **Compatibilidad**

- ✅ **Planes existentes** siguen funcionando igual
- ✅ **Workflows** se ejecutan como planes especiales
- ✅ **Chat** puede crear workflows dinámicamente
- ✅ **Recomendaciones** incluyen workflows exitosos

---

## 📊 **Resumen de Endpoints por Fase**

| Fase | Endpoints | Funcionalidad |
|------|-----------|---------------|
| 1 | **35 endpoints** | Workflows básicos, triggers, ejecución, **seguridad, costes, validación, runtime, expresiones, API import** |
| 2 | 8 endpoints | Nodos avanzados, plantillas |
| 3 | 6 endpoints | Triggers avanzados, eventos |
| 4 | 4 endpoints | Idempotencia, circuit breakers |
| 5 | 8 endpoints | Métricas, alertas, observabilidad |
| 6 | 12 endpoints | Testing, versionado, sandbox |
| 7 | 10 endpoints | Plantillas, patrones, catálogo |
| 8 | 6 endpoints | Costes, cuotas, auditoría |

**Total: 89 endpoints** para un sistema completo de workflows enterprise con **seguridad enterprise-grade**.

---

## 🚀 **Cronograma Estimado**

- **Fase 1**: **8-10 semanas** (Fundación + **Seguridad Enterprise + Top 12 Ajustes**)
- **Fase 2**: 3-4 semanas (Nodos avanzados)
- **Fase 3**: 3-4 semanas (Triggers avanzados)
- **Fase 4**: 2-3 semanas (Resiliencia)
- **Fase 5**: 3-4 semanas (Observabilidad)
- **Fase 6**: 4-5 semanas (Testing y versionado)
- **Fase 7**: 3-4 semanas (Catálogo)
- **Fase 8**: 2-3 semanas (Gobernanza)

**Total estimado: 28-37 semanas** (7-9.5 meses) para un sistema completo con **seguridad enterprise-grade**.

---

## 🎯 **Conclusión**

Este plan transforma APIchat en una plataforma de workflows **enterprise-grade con seguridad de nivel bancario**, manteniendo total compatibilidad con el sistema actual. 

### **🔒 Características de Seguridad Enterprise:**
- ✅ **Validación estricta** con JSON Schema versionado
- ✅ **Ejecución determinista** con manejo de variables faltantes
- ✅ **Transacciones seguras** con rollback automático
- ✅ **Enmascaramiento PII** en logs y métricas
- ✅ **RBAC granular** por workflow/credencial
- ✅ **Control de costes AI** con límites diarios
- ✅ **Políticas de retención** automáticas
- ✅ **Auditoría completa** de accesos y cambios
- ✅ **Runtime Redis** con contrato de claves estándar
- ✅ **Idempotencia robusta** con deduplicación automática
- ✅ **Circuit breakers** por credencial+endpoint
- ✅ **Motor de expresiones** con sintaxis `{{ }}`
- ✅ **Import automático** de APIs OpenAPI/Postman
- ✅ **Control de flujo** declarativo (Iterator, Switch, Transform)

### **🚀 Valor Incremental:**
Cada fase aporta valor incremental, permitiendo empezar con funcionalidad básica y evolucionar hacia un sistema completo tipo **n8n + Temporal.io + Airflow** pero adaptado específicamente para el ecosistema APIchat.

### **⚡ Ready for Production:**
Con las lagunas críticas resueltas desde Fase 1, el sistema está preparado para entornos de producción enterprise desde el primer release.

---

## 🔍 **VACÍOS CRÍTICOS ADICIONALES IDENTIFICADOS**

### **🚨 ANTES DE BUILD - CHECKLIST CRÍTICO**

#### **1. 🏗️ Scheduler & Workers**
- **Cola de trabajos**: Redis Streams/Sidekiq/Celery separados del API
- **Concurrencia**: Por workflow, usuario/tenant y credencial (rate limit)
- **Política de preempción**: Pausa/cancel y reintentos a nivel cola
- **Workers dedicados**: Separación clara API vs Workers

#### **2. ⚖️ Árbitro de Estados**
- **Fuente de verdad**: Redis = runtime, Postgres = persist/commit (checkpoints)
- **FSM por nodo**: pending→running→completed/failed/skipped con eventos válidos
- **Estados imposibles**: Validación de transiciones de estado

#### **3. 💾 Transacciones en DB Node**
- **Boundaries**: BEGIN/COMMIT por nodo, opción "transactional batch"
- **Idempotencia**: UPSERT con claves naturales y migración segura
- **Rollback**: Transacciones atómicas por nodo

#### **4. 🛡️ Sandbox del Motor de Expresiones**
- **Whitelisting**: Funciones permitidas, timeouts y límites de profundidad/CPU
- **Protección**: jsonPath/eval de payloads maliciosos
- **Aislamiento**: Sin I/O, sin reloj libre, timeout duro

#### **5. 🔐 Gestión de Secretos**
- **KMS**: Envelope encryption + rotación y scopes por credencial
- **Break-glass**: Access logs por lectura de secreto
- **Rotación**: Automática + prueba de conectividad post-rotación

#### **6. 📋 Política de Serialización/Compatibilidad**
- **Compatibilidad**: Hacia atrás del workflow_spec por schema_version
- **Migrador**: Dry-run y reporte (qué cambia y por qué)
- **Semver real**: Negación de cambios breaking

#### **7. 🚦 Rate Limiting Multicapa**
- **Por endpoint/credencial**: Límites granulares
- **Por workflow**: Y global
- **Fallback**: "Degradar a modo diferido" si se excede

#### **8. 💬 UX de Errores y Control en Chat**
- **Frases estándar**: stop/continue/route; mostrar causa y siguiente acción
- **Botones**: Pausar, Reintentar nodo, Saltar, Cancelar
- **Human-in-the-loop**: Nodo Approval con expiración y fallback

#### **9. 🧪 Testing Determinista**
- **Golden tests**: Por workflow con mocks de APIs
- **Record/replay**: De respuestas HTTP
- **Contract tests**: Para nodos importados de OpenAPI

#### **10. 🗂️ Cierre/Retención**
- **Política automática**: Por retention_days + jobs de purga
- **Export**: Run bundle (inputs/outputs/log) bajo solicitud
- **Clasificación PII**: Por campo y masking configurable

#### **11. 🔒 Seguridad de Webhooks & APIs**
- **Verificación de firma**: Por proveedor y anti-replay (timestamp + nonce)
- **Rate limit**: Específico para webhooks y payload size limits
- **CSRF**: Para endpoints de control (pause/resume/cancel)

#### **12. 🏢 Aislamiento Multi-tenant**
- **Namespacing**: Estricto en Redis/DB por tenant
- **RBAC**: Por workflow y credencial (owner, editor, runner)
- **Etiquetado**: tenant_id en logs/metrics para filtrado

#### **13. 📁 Gestión de Ficheros/Grandes Payloads**
- **Offload**: A objeto (S3/GCS) para outputs > N MB
- **Links temporales**: Y hashing de integridad
- **Sanitización**: De archivos (tipo y AV opcional)

#### **14. 📊 Observabilidad Avanzada**
- **Tracing distribuido**: OpenTelemetry con spans por nodo
- **SLOs**: Definidos (p95, error budget) y alertas en métricas clave
- **Correlación**: request_id↔run_id en todos los logs

#### **15. 🔄 Plan de Fallos y Colas**
- **DLQ**: Por cola y re-ingesta manual/automática
- **Poison message**: Detection (cap de reintentos por run)
- **Health checks**: + watchdog para workers

#### **16. 🚀 Compatibilidad & Despliegue Seguro**
- **Canary/feature flags**: Por tipo de nodo y por tenant
- **Blue/green**: Rolling de workers + migraciones con "preflight"
- **Backward-compatible**: workflow_spec (semver real)

#### **17. ⏰ Cron & Zona Horaria**
- **Cron con TZ**: Por workflow y manejo DST
- **Ventanas de mantenimiento**: Saltables (no dispare crons en ese período)

#### **18. 🗄️ Nodos DB Seguros**
- **Bind params**: Siempre; catálogo de tablas permitido (allow-list)
- **Modo read-only**: Seleccionable
- **Upserts idempotentes**: Con claves naturales/únicas documentadas

#### **19. 💰 Cost & Presupuesto Preventivo**
- **Estimación previa**: De coste (tokens/calls) y "ask-to-proceed" si supera umbral
- **Cuotas**: Por credencial además de por usuario/tenant
- **KPIs**: Por workflow (leads creados/actualizados) además de técnicas

#### **20. 📚 Catálogo & DX**
- **Esquema oficial**: Por tipo de nodo (docs + ejemplos)
- **Snippets/plantillas**: Curadas (lead ingest, upsert CRM, notificar)
- **CLI**: O endpoint lint/validate de workflow offline

---

## 🔄 **PROCESO DE REVISIÓN Y REFACTORIZACIÓN**

### **📋 Checklist de Revisión por Fase**

#### **Antes de cada Release:**
1. ✅ **Revisar vacíos críticos** de la lista anterior
2. ✅ **Verificar completitud** de funcionalidades planificadas
3. ✅ **Evaluar complejidad** vs tiempo estimado
4. ✅ **Identificar dependencias** entre componentes
5. ✅ **Planificar refactorización** si es necesario

#### **Criterios para Refactorización:**
- **Complejidad excesiva**: >2 semanas de retraso en estimación
- **Dependencias circulares**: Entre servicios o modelos
- **Performance crítica**: Límites de escalabilidad identificados
- **Seguridad**: Vulnerabilidades o gaps de seguridad
- **Mantenibilidad**: Código difícil de mantener o extender

#### **Proceso de Refactorización:**
1. **Pausar desarrollo** de la fase actual
2. **Analizar impacto** de la refactorización
3. **Rediseñar arquitectura** problemática
4. **Implementar cambios** de forma incremental
5. **Actualizar estimaciones** y cronograma
6. **Reanudar desarrollo** con arquitectura mejorada

### **🚨 Señales de Alerta para Refactorización**

#### **Técnicas:**
- **Complejidad ciclomática** >15 en servicios
- **Acoplamiento alto** entre módulos
- **Duplicación de código** >30%
- **Tiempo de build** >10 minutos
- **Cobertura de tests** <80%

#### **De Negocio:**
- **Retraso acumulado** >25% del cronograma
- **Cambios de requisitos** frecuentes
- **Feedback negativo** en demos
- **Problemas de performance** en pruebas

### **📊 Métricas de Seguimiento**

#### **Por Fase:**
- **Completitud**: % de funcionalidades implementadas
- **Calidad**: Cobertura de tests, linting, security scans
- **Performance**: Tiempo de respuesta, throughput
- **Tiempo**: Estimado vs real por tarea

#### **Por Release:**
- **Estabilidad**: Bugs en producción
- **Adopción**: Uso de nuevas funcionalidades
- **Satisfacción**: Feedback de usuarios
- **Escalabilidad**: Límites identificados

---

## 🎯 **CONCLUSIÓN ACTUALIZADA**

Este plan transforma APIchat en una plataforma de workflows **enterprise-grade con seguridad de nivel bancario**, manteniendo total compatibilidad con el sistema actual.

### **🔒 Características de Seguridad Enterprise:**
- ✅ **Validación estricta** con JSON Schema versionado
- ✅ **Ejecución determinista** con manejo de variables faltantes
- ✅ **Transacciones seguras** con rollback automático
- ✅ **Enmascaramiento PII** en logs y métricas
- ✅ **RBAC granular** por workflow/credencial
- ✅ **Control de costes AI** con límites diarios
- ✅ **Políticas de retención** automáticas
- ✅ **Auditoría completa** de accesos y cambios
- ✅ **Runtime Redis** con contrato de claves estándar
- ✅ **Idempotencia robusta** con deduplicación automática
- ✅ **Circuit breakers** por credencial+endpoint
- ✅ **Motor de expresiones** con sintaxis `{{ }}`
- ✅ **Import automático** de APIs OpenAPI/Postman
- ✅ **Control de flujo** declarativo (Iterator, Switch, Transform)
- ✅ **Proceso de revisión** y refactorización integrado

### **🚀 Valor Incremental:**
Cada fase aporta valor incremental, permitiendo empezar con funcionalidad básica y evolucionar hacia un sistema completo tipo **n8n + Temporal.io + Airflow** pero adaptado específicamente para el ecosistema APIchat.

### **⚡ Ready for Production:**
Con las lagunas críticas resueltas desde Fase 1 y el proceso de revisión integrado, el sistema está preparado para entornos de producción enterprise desde el primer release, con capacidad de adaptación y mejora continua.
