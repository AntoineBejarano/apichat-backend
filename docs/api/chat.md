# 💬 Chat API

La API de chat de APIchat permite enviar mensajes a la IA y recibir respuestas inteligentes. Soporta tanto HTTP como WebSocket para diferentes casos de uso.

## 🚀 Endpoints Principales

### **1. Enviar Mensaje (HTTP)**
```http
POST /chat/send
Content-Type: application/json
```

**Parámetros:**
- `message` (obligatorio): Objeto ChatMessage
- `chat_id` (opcional): ID del chat (se crea uno nuevo si no se proporciona)
- `agent_id` (opcional): ID del agente
- `db_ids` (opcional): Lista de IDs de bases de datos para contexto
- `app_ids` (opcional): Lista de IDs de aplicaciones para contexto
- `explorer` (opcional): Modo explorador (default: false)

**Ejemplo de Request:**
```json
{
  "role": "user",
  "content": "Cuenta cuántos usuarios activos tengo",
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": "550e8400-e29b-41d4-a716-446655440001",
  "db_ids": ["550e8400-e29b-41d4-a716-446655440002"],
  "app_ids": ["550e8400-e29b-41d4-a716-446655440003"],
  "explorer": false
}
```

**Ejemplo de Response:**
```json
{
  "success": true,
  "chat_id": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_response": "He encontrado 150 usuarios activos en tu base de datos.",
  "execution_results": {
    "total_users": 150,
    "active_users": 120
  },
  "steps": [
    {
      "type": "db_query",
      "sql": "SELECT COUNT(*) as total FROM users WHERE active = true",
      "result": 150
    }
  ]
}
```

### **2. Enviar Mensaje a Chat Específico**
```http
POST /chat/{chat_id}/message
Content-Type: application/json
```

**Parámetros:**
- `chat_id` (obligatorio): ID del chat en la URL
- `message` (obligatorio): Objeto ChatMessage
- `agent_id` (opcional): ID del agente
- `db_ids` (opcional): Lista de IDs de bases de datos
- `app_ids` (opcional): Lista de IDs de aplicaciones
- `explorer` (opcional): Modo explorador

**Ejemplo:**
```bash
curl -X POST http://localhost:8000/chat/550e8400-e29b-41d4-a716-446655440000/message \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Analiza los usuarios más activos",
    "db_ids": ["550e8400-e29b-41d4-a716-446655440002"]
  }'
```

### **3. WebSocket (Recomendado)**
```http
WS /ws/{agent_id}
```

**Conexión:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/550e8400-e29b-41d4-a716-446655440001');
```

**Enviar mensaje:**
```json
{
  "role": "user",
  "content": "Cuenta cuántos usuarios activos tengo",
  "db_ids": ["550e8400-e29b-41d4-a716-446655440002"],
  "app_ids": ["550e8400-e29b-41d4-a716-446655440003"],
  "explorer": false
}
```

**Recibir respuesta:**
```json
{
  "type": "steps",
  "steps": [
    {
      "type": "db_query",
      "sql": "SELECT COUNT(*) as total FROM users WHERE active = true",
      "result": 150
    }
  ]
}
```

```json
{
  "type": "response",
  "message": "He encontrado 150 usuarios activos en tu base de datos."
}
```

## 📋 Gestión de Chats

### **Crear Chat**
```http
POST /chat/
Content-Type: application/json
```

```json
{
  "name": "Mi Chat Personal"
}
```

### **Listar Chats**
```http
GET /chat/
```

### **Obtener Chat Específico**
```http
GET /chat/{chat_id}
```

### **Eliminar Chat**
```http
DELETE /chat/{chat_id}
```

## 🔧 Parámetros del ChatMessage

```typescript
interface ChatMessage {
  role: string;           // "user", "assistant", "system"
  content: string;        // Contenido del mensaje
  name?: string;          // Nombre del emisor (opcional)
  timestamp?: Date;       // Timestamp (opcional)
  explorer?: boolean;     // Modo explorador (opcional)
  db_ids?: UUID[];       // IDs de bases de datos (opcional)
  app_ids?: UUID[];      // IDs de aplicaciones (opcional)
}
```

## 🎯 Casos de Uso

### **1. Chat Simple**
```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Hola, ¿cómo estás?"
  }'
```

### **2. Chat con Base de Datos**
```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Cuenta cuántos usuarios tengo",
    "db_ids": ["550e8400-e29b-41d4-a716-446655440002"]
  }'
```

### **3. Chat con Agente Específico**
```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Analiza los datos de ventas",
    "agent_id": "550e8400-e29b-41d4-a716-446655440001",
    "db_ids": ["550e8400-e29b-41d4-a716-446655440002"]
  }'
```

### **4. Modo Explorador**
```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Explora mi base de datos",
    "explorer": true
  }'
```

## ⚡ Optimizaciones

### **HTTP vs WebSocket**

| Característica | HTTP | WebSocket |
|----------------|------|-----------|
| **Tiempo Real** | ❌ | ✅ |
| **Pasos Intermedios** | ❌ | ✅ |
| **Conexión Persistente** | ❌ | ✅ |
| **Simplicidad** | ✅ | ❌ |
| **Performance** | ⚠️ | ✅ |

### **Recomendaciones**

- **Usar HTTP** para: Integraciones simples, testing, scripts
- **Usar WebSocket** para: Chat en tiempo real, UI interactiva, pasos intermedios

## 🔍 Debugging

### **Logs de Performance**
```bash
# Ver logs de performance
grep "⏱️" logs/app.log

# Ver logs del chat
grep "chat" logs/app.log
```

### **Métricas en Tiempo Real**
```bash
# Obtener métricas del chat
curl http://localhost:8000/performance/metrics
```

## 🚨 Códigos de Error

| Código | Descripción |
|--------|-------------|
| `400` | Parámetros inválidos |
| `401` | No autenticado |
| `404` | Chat no encontrado |
| `429` | Límite de tokens alcanzado |
| `500` | Error interno del servidor |

## 📚 Ejemplos Completos

### **JavaScript (WebSocket)**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/550e8400-e29b-41d4-a716-446655440001');

ws.onopen = () => {
  console.log('Conectado al chat');
  
  ws.send(JSON.stringify({
    role: 'user',
    content: 'Cuenta mis usuarios',
    db_ids: ['550e8400-e29b-41d4-a716-446655440002']
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  if (data.type === 'steps') {
    console.log('Pasos ejecutados:', data.steps);
  } else if (data.type === 'response') {
    console.log('Respuesta:', data.message);
  }
};
```

### **Python (HTTP)**
```python
import requests

response = requests.post(
    'http://localhost:8000/chat/send',
    json={
        'role': 'user',
        'content': 'Cuenta mis usuarios',
        'db_ids': ['550e8400-e29b-41d4-a716-446655440002']
    }
)

result = response.json()
print(f"Respuesta: {result['assistant_response']}")
print(f"Resultados: {result['execution_results']}")
``` 