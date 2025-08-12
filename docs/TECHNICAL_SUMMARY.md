# 🔧 Resumen Técnico - APIchat

## 🏗️ Arquitectura del Sistema

### **Visión General**
APIchat es una plataforma conversacional que implementa un patrón de arquitectura basado en eventos, con un sistema de orquestación inteligente que coordina múltiples servicios especializados.

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   WebSocket     │    │   Orchestrator   │    │   GraphRunner   │
│   Interface     │◄──►│     Service      │◄──►│   (Execution)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Event        │    │   Context        │    │   Services      │
│   Emitter      │    │   Manager        │    │   (DB, API,     │
└─────────────────┘    └──────────────────┘    │   MCP, etc.)    │
                                               └─────────────────┘
```

## 🧠 Componentes Principales

### 1. **OrchestratorService** - Cerebro del Sistema
- **Responsabilidad**: Coordinación central de todos los flujos
- **Funcionalidades**:
  - Gestión de modos (Explorer vs Guided)
  - Control de presupuesto de tokens
  - Coordinación de servicios especializados
  - Manejo de contexto y memoria

```python
class OrchestratorService:
    def __init__(self, factory: ServiceFactory):
        self.token_budget = TokenBudgetManager()
        self.context_loader = ContextLoader(factory)
        self.graph_runner = GraphRunner(factory)
        self.decision_manager = DecisionManager()
        self.ws_emitter = factory.get_ws_emitter()
```

### 2. **GraphRunner** - Motor de Ejecución
- **Responsabilidad**: Ejecución de planes y grafos de acción
- **Tipos de Grafos**:
  - `ExplorationGraph`: Descubrimiento de recursos
  - `GuidedGraph`: Ejecución dirigida de acciones

```python
class GraphRunner:
    async def execute_exploration_graph(self, user_message: str) -> Dict[str, Any]:
        # Explora recursos disponibles
        # Propone combinaciones DB + App
        # Retorna opciones para el usuario
    
    async def execute_guided_graph(self, plan: PlanModel) -> Dict[str, Any]:
        # Ejecuta plan específico paso a paso
        # Maneja errores y reintentos
        # Emite eventos de progreso
```

### 3. **WebSocket Event System** - Comunicación en Tiempo Real
- **Eventos Clave**:
  - `status.typing`: Indicador de escritura
  - `status.progress`: Seguimiento de progreso
  - `decision.request`: Solicitudes de confirmación
  - `result.partial`: Resultados intermedios
  - `result.final`: Resultados completos

```python
class WebSocketEmitter:
    async def emit_status_progress(self, step: int, total: int, message: str):
        event = StatusProgressEvent(step=step, total_steps=total, message=message)
        await self.emit(event)
    
    async def emit_decision_request(self, decision_id: str, options: List[Dict]):
        event = DecisionRequestEvent(decision_id=decision_id, options=options)
        await self.emit(event)
```

## 🔄 Flujos de Trabajo

### **Flujo Explorer (Descubrimiento)**
```
1. Usuario envía mensaje vago
2. Orchestrator detecta modo Explorer
3. ContextLoader analiza recursos disponibles
4. ResourceSelector propone combinaciones
5. Usuario elige opción
6. Sistema cambia a modo Guided
7. Ejecuta plan con recursos seleccionados
```

### **Flujo Guided (Ejecución)**
```
1. Usuario especifica recursos y acción
2. Orchestrator valida recursos
3. PlanBuilder crea plan de ejecución
4. GraphRunner ejecuta paso a paso
5. Eventos WebSocket informan progreso
6. Resultado final con próximas acciones
```

## 🛡️ Sistema de Seguridad y Guardrails

### **SQL Guardrails**
- **Validación de consultas**: Análisis de riesgo antes de ejecutar
- **Límites de filas**: Prevención de consultas masivas
- **Alternativas seguras**: Sugerencias cuando se detectan riesgos

```python
class SQLGuardrailsService:
    def analyze_sql_query(self, sql: str) -> RiskAssessment:
        # Analiza nivel de riesgo
        # Detecta operaciones peligrosas
        # Sugiere alternativas seguras
    
    def validate_and_apply_guardrails(self, sql: str) -> SafeSQLQuery:
        # Aplica límites automáticos
        # Modifica consultas riesgosas
        # Retorna versión segura
```

### **Function Guardrails**
- **Evaluación de riesgo**: Análisis de funciones antes de ejecutar
- **Confirmación requerida**: Solicita aprobación para operaciones críticas
- **Categorización**: Clasifica funciones por nivel de riesgo

```python
class FunctionGuardrailsService:
    def add_function_guardrail(self, function_id: int, risk_level: FunctionRiskLevel):
        # Configura guardrails para función específica
    
    def validate_function_execution(self, function_id: int, params: Dict) -> ValidationResult:
        # Valida parámetros y contexto
        # Determina si requiere confirmación
        # Retorna resultado de validación
```

## ⚡ Optimizaciones y Rendimiento

### **Token Budget Management**
- **Control inteligente**: Presupuesto por llamada y sesión
- **Trimming automático**: Recorta contexto cuando es necesario
- **Optimización de esquemas**: Reduce caracteres de schema automáticamente

```python
class TokenBudgetManager:
    MAX_INPUT_TOKENS = 8000
    MAX_OUTPUT_TOKENS = 2048
    MAX_HISTORY_TURNS = 6
    
    def optimize_context(self, context: Dict[str, Any]) -> OptimizedContext:
        # Recorta historial si es necesario
        # Optimiza esquemas de base de datos
        # Mantiene información crítica
```

### **Fast Schema Path**
- **Búsqueda rápida**: Lookup de esquemas sin LLM
- **Cache inteligente**: Almacenamiento de esquemas frecuentes
- **Fallback a LLM**: Cuando la búsqueda rápida falla

```python
class SchemaExplorerService:
    def fast_lookup(self, query: str, db_ids: List[str]) -> Tuple[Optional[Dict], float, str]:
        # Búsqueda trigram para coincidencias rápidas
        # Retorna esquema y confianza
        # Fallback a búsqueda LLM si es necesario
```

## 🔧 Hardening y Robustez (Fase 15)

### **Sistema de Reintentos**
- **Backoff exponencial**: Reintentos inteligentes con delays crecientes
- **Timeouts configurables**: Límites de tiempo para diferentes operaciones
- **Manejo de fallos transitorios**: Recuperación automática de errores

```python
class RetryService:
    def retry_with_backoff(self, func: Callable, max_retries: int = 3) -> Any:
        # Implementa backoff exponencial
        # Maneja diferentes tipos de excepciones
        # Retorna resultado o última excepción
```

### **Sistema de Undo/Rollback**
- **Operaciones reversibles**: Registro de operaciones que pueden deshacerse
- **Rollback automático**: Deshacer cambios en caso de error
- **Limpieza automática**: Eliminación de operaciones expiradas

```python
class UndoService:
    def register_operation(self, operation: UndoableOperation) -> str:
        # Registra operación para posible rollback
    
    def execute_undo(self, operation_id: str) -> UndoResult:
        # Ejecuta rollback de operación específica
        # Valida que la operación sea reversible
        # Retorna resultado del rollback
```

## 📊 Monitoreo y Telemetría

### **Performance Monitoring**
- **Métricas en tiempo real**: Latencia, throughput, uso de recursos
- **Profiling automático**: Análisis de rendimiento de funciones
- **Alertas inteligentes**: Notificaciones cuando se detectan problemas

```python
@monitor_performance
async def handle_user_message(self, message: str) -> Dict[str, Any]:
    # Decorador automático para monitoreo
    # Métricas de latencia y recursos
    # Alertas si excede umbrales
```

### **Advanced Telemetry**
- **KPIs del usuario**: Métricas de uso y satisfacción
- **Análisis de patrones**: Comportamiento típico de usuarios
- **Optimizaciones automáticas**: Sugerencias basadas en métricas

```python
class AdvancedTelemetryService:
    def track_user_interaction(self, interaction: UserInteraction):
        # Registra interacción del usuario
        # Calcula métricas de satisfacción
        # Identifica patrones de uso
    
    def generate_insights(self) -> List[Insight]:
        # Analiza métricas acumuladas
        # Genera insights y recomendaciones
        # Sugiere optimizaciones
```

## 🔌 Integración y Extensibilidad

### **MCP (Model Context Protocol)**
- **Conectores flexibles**: HTTP, WebSocket, stdio
- **Herramientas dinámicas**: Carga de herramientas en tiempo de ejecución
- **Autenticación configurable**: Tokens, headers, credenciales

```python
class MCPIntegrationService:
    def register_tool(self, tool: MCPTool):
        # Registra nueva herramienta MCP
        # Configura autenticación y endpoints
        # Hace disponible para el usuario
    
    async def execute_tool(self, tool_name: str, params: Dict) -> ToolResult:
        # Ejecuta herramienta MCP específica
        # Maneja errores y timeouts
        # Retorna resultado estructurado
```

### **Service Factory Pattern**
- **Inyección de dependencias**: Creación automática de servicios
- **Configuración dinámica**: Adaptación según contexto (HTTP vs WebSocket)
- **Lazy loading**: Carga de servicios solo cuando se necesitan

```python
class ServiceFactory:
    def __init__(self, db: Session, request: Union[Request, WebSocket, None]):
        self.db = db
        self.request = request
        self._services = {}
    
    def get_orchestrator_service(self) -> OrchestratorService:
        # Crea o reutiliza instancia del orchestrator
        # Configura según tipo de request
        # Inyecta dependencias necesarias
```

## 🧪 Testing y Calidad

### **Test E2E Completo**
- **Simulación de flujos**: Tests que cubren todo el viaje del usuario
- **Mocks inteligentes**: Simulación de servicios externos
- **Validación de eventos**: Verificación de eventos WebSocket

```python
class TestWebSocketE2EComplete:
    def test_complete_user_journey(self):
        # 1. Conexión WebSocket
        # 2. Procesamiento de mensaje
        # 3. Respuesta del orchestrator
        # 4. Resolución de templates
        # 5. Propuestas de recursos
        # 6. Confirmaciones y ejecución
        # 7. Seguimiento de progreso
        # 8. Resultados finales
```

### **Cobertura de Tests**
- **Unit tests**: Componentes individuales
- **Integration tests**: Interacción entre servicios
- **E2E tests**: Flujos completos del usuario

## 🚀 Roadmap y Futuro

### **Próximas Fases**
- **Fase 16**: Machine Learning y Personalización
- **Fase 17**: Integración con más proveedores
- **Fase 18**: Analytics avanzado y predicciones
- **Fase 19**: Colaboración y equipos
- **Fase 20**: API pública y marketplace

### **Mejoras Técnicas Planificadas**
- **GraphQL**: API más flexible y eficiente
- **WebAssembly**: Ejecución de código en el navegador
- **Edge Computing**: Procesamiento distribuido
- **Real-time Collaboration**: Colaboración en tiempo real

## 📚 Recursos Adicionales

### **Documentación**
- [Manual de Usuario](./USER_MANUAL.md)
- [API Reference](./api/README.md)
- [Deployment Guide](./deployment/README.md)

### **Código Fuente**
- [Orchestrator Service](../app/services/orchestrator_service.py)
- [WebSocket Router](../app/routers/chat_ws_router.py)
- [Event Models](../app/common/events.py)

### **Tests**
- [E2E Tests](../test/test_websocket_e2e_complete.py)
- [Unit Tests](../test/)
- [Integration Tests](../test/)

---

**APIchat** representa la evolución de las interfaces conversacionales, combinando la simplicidad del chat natural con la potencia de sistemas empresariales complejos. La arquitectura modular y basada en eventos permite escalabilidad, mantenibilidad y extensibilidad, mientras que el sistema de guardrails y hardening garantiza seguridad y robustez en producción.
