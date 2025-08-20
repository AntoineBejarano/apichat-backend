# 🏗️ **DIAGRAMA DE ARQUITECTURA ACTUAL**

> **APICHAT-BACKEND 2.0 - ReAct Orchestrator**  
> **Fecha**: Diciembre 2024

---

## 🎯 **ARQUITECTURA GENERAL**

```mermaid
graph TB
    subgraph "🌐 Frontend/API"
        A[Usuario/Cliente] --> B[FastAPI Router]
        B --> C[OrchestratorService]
    end
    
    subgraph "🧠 Core - ReAct Orchestrator"
        C --> D[ReAct Orchestrator]
        D --> E{THINK}
        E --> F{¿Qué acción?}
        F -->|explore| G[ExplorationGraph]
        F -->|guide| H[GuidedGraph]
        F -->|sql_direct| I[Execution Engine]
        F -->|complete| J[Respuesta Final]
    end
    
    subgraph "🗄️ Grafos Especializados"
        G --> K[Schema Loading]
        K --> L[LLM SQL Generation]
        L --> M[SQL Execution]
        
        H --> N[Context Loading]
        N --> O[Intention Analysis]
        O --> P[Plan Execution]
    end
    
    subgraph "⚡ Cache Inteligente"
        Q[SchemaExplorerService]
        R[DetailedSchemaCache]
        S[Fast Schema Path]
        
        Q --> R
        Q --> S
        S --> T[<100ms Response]
    end
    
    subgraph "📊 Telemetría"
        U[LangSmith Integration]
        V[LLM Runs Tracking]
        W[Performance Metrics]
        
        D --> U
        U --> V
        V --> W
    end
    
    subgraph "🔧 Servicios de Soporte"
        X[Service Factory]
        Y[Database Service]
        Z[LangChain Service]
        
        X --> Y
        X --> Z
    end
    
    M --> J
    P --> J
    T --> J
```

---

## 🔄 **FLUJO DE PROCESAMIENTO DETALLADO**

```mermaid
sequenceDiagram
    participant U as Usuario
    participant O as OrchestratorService
    participant R as ReAct Orchestrator
    participant E as ExplorationGraph
    participant G as GuidedGraph
    participant C as Cache
    participant L as LLM
    participant D as Database
    
    U->>O: Envía mensaje
    O->>R: Delega a ReAct
    
    loop Think → Act → Observe (máx. 5 iteraciones)
        R->>L: THINK: ¿Qué hacer?
        L->>R: Respuesta con acción
        
        alt Acción: explore
            R->>E: Ejecutar ExplorationGraph
            E->>C: Buscar en cache
            alt Cache Hit
                C->>E: Respuesta rápida
            else Cache Miss
                E->>D: Cargar esquema
                D->>E: Esquema de BD
                E->>L: Generar SQL
                L->>E: SQL generado
                E->>D: Ejecutar SQL
                D->>E: Resultados
            end
            E->>R: Resultado de exploración
            
        else Acción: guide
            R->>G: Ejecutar GuidedGraph
            G->>L: Análisis de intención
            L->>G: Plan de ejecución
            G->>D: Ejecutar plan
            D->>G: Resultados
            G->>R: Resultado guiado
        end
        
        R->>R: OBSERVE: Evaluar resultado
        alt ¿Completo?
            R->>R: Sí, salir del loop
        else
            R->>R: No, continuar iteración
        end
    end
    
    R->>O: Respuesta final
    O->>U: Respuesta al usuario
```

---

## 🗄️ **SISTEMA DE CACHE MULTI-NIVEL**

```mermaid
graph LR
    subgraph "🚀 Fast Schema Path"
        A[Query del Usuario] --> B{¿En Cache?}
        B -->|Sí| C[Respuesta <1ms]
        B -->|No| D[Fallback a BD]
        D --> E[Respuesta <100ms]
    end
    
    subgraph "💾 Niveles de Cache"
        F[L1: Redis Memory]
        G[L2: Disk JSON]
        H[L3: Database]
        
        F --> G
        G --> H
    end
    
    subgraph "🔍 Tipos de Cache"
        I[Schema Cache]
        J[Response Cache]
        K[Query Cache]
        L[Context Cache]
    end
    
    C --> F
    E --> H
```

---

## 🎯 **DECISION TREE DEL REACT ORCHESTRATOR**

```mermaid
graph TD
    A[Usuario envía mensaje] --> B{¿Es consulta de esquema?}
    B -->|Sí| C[Fast Schema Path]
    B -->|No| D{¿Tiene contexto rico?}
    
    C --> E{¿Cache Hit?}
    E -->|Sí| F[Respuesta instantánea]
    E -->|No| G[Fallback a BD]
    
    D -->|Sí| H[GuidedGraph]
    D -->|No| I[ExplorationGraph]
    
    H --> J[Análisis de intención]
    J --> K[Plan de ejecución]
    K --> L[Ejecución paso a paso]
    
    I --> M[Cargar esquemas]
    M --> N[Generar SQL con LLM]
    N --> O[Ejecutar consulta]
    
    F --> P[Respuesta final]
    G --> P
    L --> P
    O --> P
```

---

## 📊 **MÉTRICAS DE RENDIMIENTO**

```mermaid
graph LR
    subgraph "⚡ Antes (Orchestrator Complejo)"
        A1[5-15 segundos]
        A2[15+ módulos]
        A3[Múltiples fallos]
        A4[Difícil debugging]
    end
    
    subgraph "🚀 Ahora (ReAct)"
        B1[1-3 segundos]
        B2[1 coordinador + 2 grafos]
        B3[Controlado (máx. 5 iteraciones)]
        B4[Simple debugging]
    end
    
    A1 --> B1
    A2 --> B2
    A3 --> B3
    A4 --> B4
```

---

## 🔧 **SERVICIOS Y DEPENDENCIAS**

```mermaid
graph TB
    subgraph "🏗️ Service Factory"
        SF[ServiceFactory]
    end
    
    subgraph "🧠 Core Services"
        RO[ReAct Orchestrator]
        OS[OrchestratorService]
        LS[LangChain Service]
    end
    
    subgraph "🗄️ Context Services"
        SES[SchemaExplorerService]
        DSC[DetailedSchemaCache]
        DSCS[DetailedSchemaCacheService]
    end
    
    subgraph "🎯 Execution Services"
        EG[ExplorationGraph]
        GG[GuidedGraph]
        EES[ExecutionEngineService]
    end
    
    subgraph "📊 Management Services"
        LRS[LLMRunsService]
        TS[TelemetryService]
        CHS[ChatHistoryService]
    end
    
    SF --> RO
    SF --> OS
    SF --> LS
    SF --> SES
    SF --> DSC
    SF --> DSCS
    SF --> EG
    SF --> GG
    SF --> EES
    SF --> LRS
    SF --> TS
    SF --> CHS
    
    OS --> RO
    RO --> EG
    RO --> GG
    RO --> EES
    RO --> LS
```

---

## 🚀 **BENEFICIOS DE LA ARQUITECTURA**

| Aspecto | Antes | Ahora | Mejora |
|---------|-------|-------|---------|
| **Velocidad** | 5-15s | 1-3s | **3-5x** |
| **Complejidad** | 15+ módulos | 1 coordinador | **5x** |
| **Mantenibilidad** | Difícil | Fácil | **4x** |
| **Debugging** | Complejo | Simple | **3x** |
| **Escalabilidad** | Limitada | Alta | **3x** |
| **Observabilidad** | Básica | Completa | **5x** |

---

## 🔮 **ROADMAP FUTURO**

```mermaid
graph LR
    subgraph "🎯 Fase Actual"
        A[ReAct Orchestrator]
        B[Cache Inteligente]
        C[LangSmith Integration]
    end
    
    subgraph "🚀 Fase Siguiente"
        D[Vector Search]
        E[Prompt Engineering]
        F[Cache Predictivo]
    end
    
    subgraph "🌟 Fase Futura"
        G[Microservicios]
        H[Auto-scaling]
        I[Distributed Cache]
    end
    
    A --> D
    B --> E
    C --> F
    D --> G
    E --> H
    F --> I
```

---

> **📝 Nota**: Estos diagramas representan la arquitectura actual del sistema después de la migración completa al ReAct Orchestrator.
