# 🧠 APIchat: AI-Powered Automation Platform

Bienvenido a **APIchat**, tu centro de automatización inteligente: combina chat, ejecución de funciones y conexión con bases de datos en un único servicio optimizado para desarrolladores.

---

## 📦 Project Structure

```text
app/
├─ core/
│  ├─ service_factory.py       # Main DI container
├─ models/                     # SQLAlchemy models
├─ schemas/                    # Pydantic schemas
├─ services/
│  ├─ orchestrator_service.py  👑 Main brain of the app
│  ├─ openai_service.py        💬 OpenAI function calling & chat
│  ├─ usage_service.py         📊 Tracks token & usage limits
│  ├─ function_service.py      🔧 CRUD para funciones definidas por usuario
│  ├─ database_service.py      🧬 Conexiones SQL & ejecución segura
│  ├─ executor.py              ⚙️ Ejecuta funciones HTTP o Python
│  ├─ proxy_service.py         🌐 Gestión de proxies
│  ├─ chat_history_service.py  💭 Historial de mensajes
│  ├─ mcp/                     🔌 Conectores externos
├─ routers/
│  ├─ chat.py, usage.py, auth.py, etc.
└─ main.py                     # Entry point
```

---

## 🧠 Cómo Funciona: `OrchestratorService`

`OrchestratorService` es el **cerebro principal** que transforma cualquier mensaje del usuario en acciones inteligentes, validando límites, cargando contexto y ejecutando funciones paso a paso.

### Flujo de trabajo:

1. **✅ Verificación de Límite de Tokens**  
   Se verifica si el usuario ha alcanzado el límite mensual según su plan (`UsageService.check_limit()`). Si es así, el mensaje se detiene.

2. **💬 Registro del Mensaje**  
   El mensaje se guarda con rol `user` en `ChatHistoryService`.

3. **📦 Carga de Contexto**  
   - Prompt del agente  
   - Conexión de base de datos  
   - Proxy, funciones disponibles, etc.

4. **🧠 Planificación con LLM**  
   Se genera un plan estructurado de pasos (`OpenAIService.plan_actions`).  
   Si no hay plan, se responde con `chat_completion()`.

5. **🔁 Ejecución de Pasos**  
   Cada paso se ejecuta: SQL, HTTP, Python, etc., y se registra en el historial.

6. **🧾 Respuesta Final**  
   Se genera una respuesta final con rol `assistant` y se devuelve con los pasos realizados.

```mermaid
graph TD
  A[User Message] --> B[Persist in ChatHistory]
  B --> C[Load Context (Agent, DB, App)]
  C --> D{Plan Actions?}
  D -->|Yes| E[Execute Plan Steps]
  D -->|No| F[ChatCompletion]
  E --> G[Persist Function Calls & DB Results]
  E --> H[Persist Final Assistant Response]
  F --> H
  H --> I[Return Response + Trace]
```

---

## 🚦 Control de Límite por Usuario

### 🔧 Base Técnica

- Cada servicio hereda de `BaseService` y accede a `self.user_id` y `self.db`.
- El `ServiceFactory` centraliza dependencias por usuario y request.

```python
class MyService(BaseService):
    def __init__(self, factory: ServiceFactory):
        super().__init__(factory)
```

---

### 🧮 1. Tokens & Llamadas API

**Servicio:** `UsageService`

- Guarda el uso por usuario (tokens, mensajes).
- Llama a `check_limit("tokens")`, `register_token_use`, etc.

---

### 🛰️ 2. Proxies

**Servicio:** `ProxyService`

- Limita cantidad de proxies por usuario según el plan.

---

### 🗄️ 3. Conexiones SQL

**Servicio:** `DatabaseService`

- Se limita el número de conexiones por usuario.

---

### 🤖 4. Agentes / Apps

**Servicio:** `AppService`

- Limita la cantidad de agentes o apps por usuario.

---

### 🧠 5. Estrategias (Function Strategies)

**Servicio:** `StrategyService`

- Limita cuántas estrategias puede guardar un usuario y cuántos pasos por estrategia.

---

### 📈 6. Panel de Uso

**Servicio:** `UsageService`

Muestra al usuario:

- Tokens usados vs. total mensual.
- Proxies creados.
- Conexiones SQL activas.
- Funciones ejecutadas.

---

## 💳 Ejemplo de Límites por Plan

| Plan      | Tokens/mes | Proxies | DB Connections | Apps | Estrategias |
|-----------|------------|---------|----------------|------|-------------|
| Free      | 10K        | 1       | 1              | 1    | 2           |
| Pro       | 100K       | 5       | 3              | 5    | 10          |
| Business  | 1M         | ∞       | ∞              | ∞    | ∞           |

---

## 🧩 DI & ServiceFactory

```python
ServiceFactory
  ├─ user
  ├─ db
  ├─ get_usage_service()
  ├─ get_database_service()
  ├─ get_openai_service()
  └─ ...
```

- Se pasa una única instancia de `ServiceFactory` a cada servicio por request.
- `BaseService` accede a `factory.db`, `factory.user`, etc.

---
## 📥 Importar y Exportar Estrategias (Formato JSON)

Nuestra plataforma permite importar y exportar estrategias en un formato JSON universal, similar a herramientas como **Make** o **n8n**.

Esto permite:
- Compartir estrategias entre usuarios.
- Clonar automatizaciones.
- Versionar y reutilizar workflows.

---

### 🧠 Estructura del JSON

```json
{
  "name": "Notificar nuevo lead por email",
  "description": "Esta estrategia se activa cuando llega un nuevo lead y envía un correo al club.",
  "trigger": {
    "type": "event",
    "config": {
      "event": "new_lead"
    }
  },
  "steps": [
    {
      "function_id": "send_email",
      "inputs": {
        "to": "{{club.email}}",
        "subject": "Nuevo lead recibido",
        "body": "Hola {{club.name}}, tienes un nuevo lead: {{lead.name}} ({{lead.phone}})"
      }
    },
    {
      "function_id": "log_event",
      "inputs": {
        "message": "Se ha enviado un email al club {{club.name}} por nuevo lead"
      }
    }
  ]
}

---

## 📋 Endpoints Principales

- `POST /chat/{chat_id}/message` → Envia mensaje y ejecuta IA
- `GET /usage` → Ver estado de uso del usuario
- `GET /logs` → Logs de ejecución
- `GET /health` → Healthcheck
- `GET /version` → Info de versión

---

## 🧪 Generar reporte de pruebas contractuales con Schemathesis

Para validar que tu API cumple con su especificación OpenAPI y generar un informe visual de los resultados, puedes usar Schemathesis con el siguiente comando:

### 🔧 Requisitos previos

- Tener la API corriendo localmente (por defecto en `http://127.0.0.1:8000`).
- Haber instalado `schemathesis` con soporte para CLI.
- Tener acceso al archivo de especificación OpenAPI (`/openapi.json`).

### ✅ Comando para ejecutar Schemathesis con reporte

```bash
C:\Users\antub\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.10_qbz5n2kfra8p0\LocalCache\local-packages\Python310\Scripts\schemathesis.exe run http://127.0.0.1:8000/openapi.json --report report.html

---

## 🔐 Futuras Mejoras

- Alertas de límite por email/Slack.
- Cache en Redis para contador de tokens.
- Integración directa con Stripe para upgrade de plan dinámico.

---

## 📜 License

Este proyecto es privado y está pensado para despliegue empresarial y SaaS.