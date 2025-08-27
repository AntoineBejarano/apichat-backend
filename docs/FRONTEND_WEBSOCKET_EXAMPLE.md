# 🚀 Frontend WebSocket con Preparación Proactiva

## 📋 **Descripción**

Este documento muestra cómo implementar el frontend para usar el nuevo sistema de WebSocket con **preparación proactiva del entorno** usando headers personalizados.

## 🔧 **Cambios Principales**

### **❌ ANTES (Complejo):**
```javascript
// Usuario tenía que enviar metadatos en cada mensaje
ws.send(JSON.stringify({
  "role": "user",
  "content": "Hola, sabes que tablas tiene mi db?",
  "name": "Antoine",
  "explorer": false,
  "db_ids": ["3c2992ec-bd4d-4367-8346-19796cc77be5"],
  "app_ids": []
}));
```

### **✅ DESPUÉS (Simple):**
```javascript
// Usuario solo envía el contenido del mensaje
ws.send(JSON.stringify({
  "content": "Hola, sabes que tablas tiene mi db?"
}));
```

## 🎯 **Implementación del Frontend**

### **1. Configuración del Usuario**

```javascript
// 🔧 OPTIMIZADO: Solo configurar recursos que requieren preparación
const userConfig = {
  role: "user",
  name: "Antoine",
  priorityDBs: ["3c2992ec-bd4d-4367-8346-19796cc77be5"],
  priorityApps: []
  // 🔧 EXPLORER: No va aquí (cambio instantáneo)
  // 🔧 STRATEGIES: No van aquí (se activan cuando se necesitan)
};

// Componente de configuración
function ResourceSelector({ config, onConfigChange }) {
  return (
    <div className="resource-selector">
      <h3>Configurar Recursos Prioritarios</h3>
      
      {/* Selección de Bases de Datos */}
      <div className="db-selector">
        <label>Bases de Datos Prioritarias (máx. 2):</label>
        <select 
          multiple 
          value={config.priorityDBs}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions, option => option.value);
            onConfigChange({ ...config, priorityDBs: selected.slice(0, 2) });
          }}
        >
          <option value="3c2992ec-bd4d-4367-8346-19796cc77be5">Mi Base Principal</option>
          <option value="abc123-def4-5678-9ghi-jklmnopqrst">Base Secundaria</option>
        </select>
      </div>
      
      {/* Selección de Aplicaciones */}
      <div className="app-selector">
        <label>Aplicaciones Prioritarias (máx. 2):</label>
        <select 
          multiple 
          value={config.priorityApps}
          onChange={(e) => {
            const selected = Array.from(e.target.selectedOptions, option => option.value);
            onConfigChange({ ...config, priorityApps: selected.slice(0, 2) });
          }}
        >
          <option value="app1">Aplicación Principal</option>
          <option value="app2">Aplicación Secundaria</option>
        </select>
      </div>
      
             {/* 🔧 STRATEGIES: Eliminados completamente (no se usan) */}
    </div>
  );
}
```

### **2. Conexión WebSocket con Headers**

```javascript
// Función para conectar WebSocket con headers personalizados
function connectWebSocket(userConfig) {
  // 🔧 OPTIMIZADO: Solo headers para recursos que requieren preparación
  const customHeaders = {
    'X-User-Role': userConfig.role,
    'X-User-Name': userConfig.name,
    'X-User-Priority-DBs': userConfig.priorityDBs.join(','),
    'X-User-Priority-Apps': userConfig.priorityApps.join(',')
    // 🔧 EXPLORER: No va en headers (cambio instantáneo)
    // 🔧 STRATEGIES: No van en headers (se activan cuando se necesitan)
  };
  
  // Conectar WebSocket
  const ws = new WebSocket('ws://localhost:8000/ws/chat', {
    headers: customHeaders
  });
  
  return ws;
}

// Hook personalizado para WebSocket
function useWebSocket(userConfig) {
  const [ws, setWs] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [environmentStatus, setEnvironmentStatus] = useState('connecting');
  
  useEffect(() => {
    if (!userConfig) return;
    
    const websocket = connectWebSocket(userConfig);
    
    websocket.onopen = () => {
      setIsConnected(true);
      setEnvironmentStatus('connecting');
      console.log('🚀 WebSocket conectado');
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Manejar diferentes tipos de mensajes
      switch (data.type) {
        case 'environment.preparing_proactively':
          setEnvironmentStatus('preparing');
          console.log('🚀 Preparando entorno proactivamente:', data.message);
          break;
          
        case 'environment.ready_proactive':
          setEnvironmentStatus('ready');
          console.log('✅ Entorno listo proactivamente:', data.message);
          break;
          
        case 'environment.preparing':
          setEnvironmentStatus('preparing');
          console.log('⏳ Entorno en preparación:', data.message);
          break;
          
        case 'environment.ready':
          setEnvironmentStatus('ready');
          console.log('✅ Entorno listo:', data.message);
          break;
          
        case 'environment.preparation_failed':
          setEnvironmentStatus('error');
          console.error('❌ Error preparando entorno:', data.message);
          break;
          
        case 'system.status':
          console.log('🔍 Estado del sistema:', data.message);
          break;
          
        default:
          console.log('📨 Mensaje recibido:', data);
      }
    };
    
    websocket.onerror = (error) => {
      console.error('❌ Error en WebSocket:', error);
      setEnvironmentStatus('error');
    };
    
    websocket.onclose = () => {
      setIsConnected(false);
      setEnvironmentStatus('disconnected');
      console.log('🔌 WebSocket desconectado');
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, [userConfig]);
  
  return { ws, isConnected, environmentStatus };
}
```

### **3. Componente de Chat Simplificado**

```javascript
// Componente principal del chat
function ChatInterface({ userConfig }) {
  const { ws, isConnected, environmentStatus } = useWebSocket(userConfig);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  
  // Enviar mensaje (ahora solo contenido)
  const sendMessage = () => {
    if (!inputMessage.trim() || !ws || environmentStatus !== 'ready') return;
    
    // 🔧 NUEVO: Solo enviar el contenido del mensaje
    const messageData = {
      content: inputMessage.trim()
    };
    
    ws.send(JSON.stringify(messageData));
    
    // Agregar mensaje del usuario
    setMessages(prev => [...prev, {
      role: 'user',
      content: inputMessage.trim(),
      timestamp: new Date()
    }]);
    
    setInputMessage('');
  };
  
  return (
    <div className="chat-interface">
      {/* Estado del entorno */}
      <div className={`environment-status ${environmentStatus}`}>
        {environmentStatus === 'connecting' && '🔌 Conectando...'}
        {environmentStatus === 'preparing' && '🚀 Preparando entorno...'}
        {environmentStatus === 'ready' && '✅ Entorno listo'}
        {environmentStatus === 'error' && '❌ Error en entorno'}
        {environmentStatus === 'disconnected' && '🔌 Desconectado'}
      </div>
      
      {/* Mensajes */}
      <div className="messages">
        {messages.map((msg, index) => (
          <div key={index} className={`message ${msg.role}`}>
            <div className="content">{msg.content}</div>
            <div className="timestamp">{msg.timestamp.toLocaleTimeString()}</div>
          </div>
        ))}
      </div>
      
      {/* Input del mensaje */}
      <div className="message-input">
        <input
          type="text"
          value={inputMessage}
          onChange={(e) => setInputMessage(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
          placeholder="Escribe tu mensaje..."
          disabled={!isConnected || environmentStatus !== 'ready'}
        />
        <button 
          onClick={sendMessage}
          disabled={!isConnected || environmentStatus !== 'ready' || !inputMessage.trim()}
        >
          Enviar
        </button>
      </div>
    </div>
  );
}
```

### **4. Componente Principal de la Aplicación**

```javascript
function App() {
     const [userConfig, setUserConfig] = useState({
     role: "user",
     name: "Antoine",
     priorityDBs: ["3c2992ec-bd4d-4367-8346-19796cc77be5"],
     priorityApps: []
     // 🔧 EXPLORER: No va aquí (cambio instantáneo)
     // 🔧 STRATEGIES: Eliminados completamente (no se usan)
   });
  
  return (
    <div className="app">
      <header>
        <h1>🚀 Chat con Preparación Proactiva</h1>
      </header>
      
      <main>
        {/* Selector de recursos */}
        <ResourceSelector 
          config={userConfig} 
          onConfigChange={setUserConfig} 
        />
        
        {/* Interfaz del chat */}
        <ChatInterface userConfig={userConfig} />
      </main>
    </div>
  );
}
```

## 🎯 **Flujo de Usuario**

### **1. Configuración Inicial**
- Usuario abre la aplicación
- Ve selector de recursos prioritarios
- Selecciona DBs y Apps que quiere usar (requieren preparación)
- Configuración se guarda en estado local

### **2. Conexión WebSocket**
- Frontend conecta con headers personalizados
- Sistema recibe conexión + recursos prioritarios
- Sistema inicia preparación proactiva en background

### **3. Preparación del Entorno**
- Usuario ve: "🚀 Preparando tu entorno en background (1 DB(s))..."
- Sistema prepara recursos en background
- Usuario puede leer/esperar mientras se prepara

### **4. Entorno Listo**
- Sistema notifica: "✅ Tu entorno está listo para usar"
- Usuario puede empezar a escribir mensajes
- **SIN esperas adicionales**

### **5. Envío de Mensajes**
- Usuario escribe: "Hola, sabes que tablas tiene mi db?"
- Frontend envía: `{ "content": "Hola, sabes que tablas tiene mi db?" }`
- Sistema responde inmediatamente (entorno ya preparado)

## 🚀 **Beneficios de la Nueva Implementación**

### **✅ Para el Usuario:**
- **Configuración una vez**: No repite recursos en cada mensaje
- **Sin esperas**: Entorno se prepara mientras lee/piensa
- **Mensajes simples**: Solo escribe su pregunta
- **Feedback claro**: Ve progreso de preparación

### **✅ Para el Sistema:**
- **Preparación proactiva**: Solo DBs y Apps (requieren preparación)
- **Eficiencia**: No desperdicia recursos en cambios instantáneos
- **UX superior**: Respuesta inmediata sin preparación

### **✅ Para el Desarrollador:**
- **Código más limpio**: Mensajes solo contienen contenido
- **Headers estándar**: Fácil de implementar y debuggear
- **Separación clara**: Metadatos en headers, contenido en mensaje

## 🔧 **Headers del WebSocket (OPTIMIZADOS)**

```
X-User-Role: user
X-User-Name: Antoine
X-User-Priority-DBs: 3c2992ec-bd4d-4367-8346-19796cc77be5
X-User-Priority-Apps: 
```

**🔧 NOTA:** `explorer` y `strategies` NO van en headers porque:
- **Explorer**: Cambio instantáneo, no requiere preparación
- **Strategies**: Se activan cuando se necesitan, no se preparan proactivamente

## 📱 **Ejemplo de Uso Completo**

```javascript
// 1. 🔧 OPTIMIZADO: Solo configurar recursos que requieren preparación
const config = {
  priorityDBs: ["3c2992ec-bd4d-4367-8346-19796cc77be5"],
  priorityApps: ["app1"]
  // 🔧 EXPLORER: No va aquí (cambio instantáneo)
  // 🔧 STRATEGIES: No van aquí (se activan cuando se necesitan)
};

// 2. Conectar WebSocket con headers optimizados
const ws = new WebSocket('ws://localhost:8000/ws/chat', {
  headers: {
    'X-User-Priority-DBs': config.priorityDBs.join(','),
    'X-User-Priority-Apps': config.priorityApps.join(',')
  }
});

// 3. Sistema prepara entorno automáticamente
// Usuario ve: "🚀 Preparando tu entorno en background (1 DB(s), 1 App(s))..."

// 4. Entorno listo
// Usuario ve: "✅ Tu entorno está listo para usar"

// 5. Usuario envía mensaje simple
ws.send(JSON.stringify({
  content: "Hola, sabes que tablas tiene mi db?"
}));

// 6. Sistema responde inmediatamente
// (entorno ya preparado proactivamente)
```

**¡La nueva implementación es mucho más simple, eficiente y proporciona una UX superior!** 🎉
