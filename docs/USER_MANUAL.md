# 📚 Manual de Usuario - APIchat

## 🎯 ¿Qué es APIchat?

APIchat es una plataforma conversacional inteligente que te permite interactuar con bases de datos, aplicaciones y herramientas a través de una interfaz de chat natural. Piensa en ello como tener un asistente de IA que puede:

- 🔍 **Explorar** tus recursos disponibles
- 📊 **Consultar** bases de datos
- 🚀 **Ejecutar** funciones de aplicaciones
- 📋 **Crear** planes de acción
- 📈 **Analizar** datos y generar reportes

## 🚀 Primeros Pasos

### 1. Conectarse al Sistema

Para comenzar a usar APIchat, necesitas conectarte a través de WebSocket:

```javascript
// Conectar al WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/{tu_agent_id}');

// Escuchar mensajes
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Mensaje recibido:', data);
};
```

### 2. Enviar tu Primer Mensaje

Una vez conectado, puedes empezar a hablar con el sistema:

```javascript
// Mensaje simple
ws.send(JSON.stringify({
    "role": "user",
    "content": "Hola, ¿qué puedes hacer?"
}));
```

## 🎭 Modos de Operación

APIchat tiene dos modos principales que se adaptan a tus necesidades:

### 🔍 **Modo Explorer** (Por Defecto)

**¿Cuándo usarlo?** Cuando quieres explorar qué recursos tienes disponibles o no estás seguro de qué necesitas.

**Características:**
- Explora automáticamente tus bases de datos y aplicaciones
- Sugiere combinaciones útiles
- Te permite descubrir funcionalidades que no conocías

**Ejemplo de uso:**
```
Usuario: "Quiero ver qué datos tengo sobre usuarios"
APIchat: "He encontrado estas opciones:
1. Base de datos 'users_db' + App 'User Management'
2. Base de datos 'analytics_db' + App 'Dashboard'
¿Cuál prefieres usar?"
```

### 🎯 **Modo Guided** (Dirigido)

**¿Cuándo usarlo?** Cuando ya sabes exactamente qué recursos quieres usar y quieres ejecutar acciones específicas.

**Características:**
- Usa recursos específicos que tú seleccionas
- Ejecuta planes paso a paso
- Te da control total sobre el proceso

**Ejemplo de uso:**
```
Usuario: "Usa la base de datos 'users_db' y la app 'User Management' para crear un reporte de usuarios activos"
APIchat: "Perfecto, voy a crear un reporte usando esos recursos específicos..."
```

## 💬 Tipos de Conversación

### 1. **Consultas Simples**
```
Usuario: "¿Cuántos usuarios tengo?"
APIchat: "Consultando la base de datos... Encontré 150 usuarios totales."
```

### 2. **Análisis Complejos**
```
Usuario: "Analiza el comportamiento de los usuarios y crea un reporte de engagement"
APIchat: "Voy a analizar varios aspectos:
1. Actividad diaria
2. Tiempo de sesión
3. Funciones más utilizadas
4. Patrones de uso..."
```

### 3. **Acciones Automatizadas**
```
Usuario: "Crea un backup de la tabla de usuarios y envíame un email con el resumen"
APIchat: "Ejecutando plan:
1. Creando backup de la tabla users
2. Generando resumen de datos
3. Enviando email con reporte..."
```

## 🔄 Flujo de Interacción

### Paso 1: **Conexión y Saludo**
```
✅ WebSocket conectado
🤖 "¡Hola! Soy tu asistente de APIchat. ¿En qué puedo ayudarte hoy?"
```

### Paso 2: **Entendimiento de la Solicitud**
```
Usuario: "Quiero analizar las ventas del último mes"
🤖 "Entiendo que quieres analizar ventas. Déjame explorar qué recursos tienes disponibles..."
```

### Paso 3: **Propuesta de Recursos** (Modo Explorer)
```
🤖 "He encontrado estas opciones para analizar ventas:
1. Base de datos 'sales_db' + App 'Analytics Suite'
2. Base de datos 'financial_db' + App 'Reporting Tool'
3. Base de datos 'erp_db' + App 'Business Intelligence'

¿Cuál prefieres usar, o quieres que explore más opciones?"
```

### Paso 4: **Confirmación y Ejecución**
```
Usuario: "Usa la primera opción"
🤖 "Perfecto, voy a usar 'sales_db' + 'Analytics Suite' para analizar las ventas..."
```

### Paso 5: **Seguimiento de Progreso**
```
📊 Paso 1/4: Conectando a la base de datos... (25%)
📊 Paso 2/4: Consultando datos de ventas... (50%)
📊 Paso 3/4: Procesando análisis... (75%)
📊 Paso 4/4: Generando reporte... (100%)
```

### Paso 6: **Resultado Final**
```
✅ Análisis completado

📈 **Resumen de Ventas - Último Mes:**
- Total de ventas: $45,230
- Número de transacciones: 156
- Promedio por transacción: $290
- Producto más vendido: Software Premium

🔄 **Próximas acciones disponibles:**
- Ver reporte detallado
- Exportar datos a Excel
- Crear dashboard automático
- Programar análisis mensual
```

## 🎯 Casos de Uso Comunes

### 📊 **Análisis de Datos**
```
Usuario: "Muéstrame las tendencias de ventas de los últimos 6 meses"
APIchat: "Analizando tendencias...
- Enero: $32,450 (línea base)
- Febrero: $38,200 (+18%)
- Marzo: $41,800 (+9%)
- Abril: $39,100 (-6%)
- Mayo: $43,500 (+11%)
- Junio: $45,230 (+4%)

📈 **Tendencia general:** Crecimiento sostenido del 39% en 6 meses"
```

### 🔍 **Búsquedas Específicas**
```
Usuario: "Encuentra todos los usuarios que no han iniciado sesión en más de 30 días"
APIchat: "Buscando usuarios inactivos...
🔍 Consulta ejecutada en tabla 'users'
📋 Resultados encontrados: 23 usuarios

📊 **Resumen:**
- Usuarios inactivos: 23
- Última actividad: Hace 30-45 días
- Categorías: 15 usuarios gratuitos, 8 premium

💡 **Sugerencias:**
- Enviar email de re-engagement
- Ofrecer descuento especial
- Crear campaña de retención"
```

### 🚀 **Automatización**
```
Usuario: "Crea un reporte diario de métricas y envíamelo por email"
APIchat: "Creando automatización...
1. ✅ Configurando consulta automática
2. ✅ Estableciendo horario: 9:00 AM diario
3. ✅ Configurando formato de reporte
4. ✅ Configurando envío por email

🎯 **Automatización configurada:**
- Reporte: Métricas diarias de la aplicación
- Horario: Todos los días a las 9:00 AM
- Destinatario: tu@email.com
- Formato: PDF + Excel adjunto

💡 **Próximos pasos:**
- Revisar primer reporte mañana
- Ajustar métricas si es necesario
- Configurar alertas para valores anómalos"
```

## 🔧 Funcionalidades Avanzadas

### 📋 **Gestión de Decisiones**
A veces APIchat necesita tu confirmación antes de ejecutar acciones importantes:

```
🤖 "⚠️ **Acción que requiere confirmación:**

Voy a ejecutar una consulta que puede tomar varios minutos y afectar el rendimiento de la base de datos.

**Acción:** Análisis completo de transacciones históricas
**Impacto:** Consulta pesada que puede tomar 5-10 minutos
**Recursos:** Base de datos 'transactions_db'

¿Deseas proceder?

[✅ Confirmar] [❌ Cancelar] [⏰ Programar para más tarde]"
```

### 🔄 **Propuestas de Recursos**
Cuando APIchat encuentra múltiples opciones, te las presenta para que elijas:

```
🤖 "🎯 **Opciones de recursos disponibles:**

He encontrado estas combinaciones para tu solicitud de análisis de usuarios:

**Opción 1: Gestión Completa**
- Base de datos: users_db
- Aplicación: User Management App
- Funcionalidades: CRUD completo, análisis, reportes

**Opción 2: Análisis Especializado**
- Base de datos: analytics_db
- Aplicación: Analytics Dashboard
- Funcionalidades: Métricas avanzadas, visualizaciones

**Opción 3: Ver más opciones**
- Explorar otras combinaciones disponibles

¿Cuál prefieres usar?"
```

### 📊 **Resultados Parciales**
Para operaciones largas, APIchat te mantiene informado del progreso:

```
📊 **Progreso: Paso 2/5 - Consultando datos...**

🔄 Procesando consulta de usuarios...
📊 Datos encontrados hasta ahora:
- Usuarios activos: 1,250
- Usuarios inactivos: 89
- Usuarios premium: 456

⏱️ Tiempo estimado restante: 2 minutos
```

## 🚨 Manejo de Errores

### ❌ **Errores del Usuario**
```
❌ **Error detectado:**

No puedo ejecutar la consulta porque:
- La tabla 'ventas_2024' no existe
- El usuario no tiene permisos para acceder a 'financial_db'

💡 **Soluciones sugeridas:**
1. Verificar el nombre exacto de la tabla
2. Contactar al administrador para permisos
3. Usar una tabla alternativa disponible
4. Solicitar creación de la tabla
```

### 🔧 **Errores del Sistema**
```
🔧 **Error del sistema:**

Se produjo un error temporal al conectar con la base de datos:
- Error: Timeout de conexión
- Causa: Alta carga del servidor

🔄 **Acción automática:** Reintentando en 5 segundos...
✅ **Resuelto:** Conexión restablecida

💡 **Prevención:** El sistema reintentará automáticamente en caso de fallos temporales
```

## ⚙️ Configuración y Personalización

### 🔐 **Preferencias de Usuario**
```
🤖 "Configurando tus preferencias:

📧 **Notificaciones:**
- Reportes por email: ✅ Activado
- Alertas críticas: ✅ Activado
- Resúmenes semanales: ❌ Desactivado

⏰ **Horarios preferidos:**
- Zona horaria: UTC-5 (América del Este)
- Horario de trabajo: 9:00 AM - 6:00 PM
- Reportes automáticos: 8:00 AM

🎨 **Interfaz:**
- Tema: Claro
- Idioma: Español
- Formato de fecha: DD/MM/YYYY"
```

### 📊 **Límites y Cuotas**
```
📊 **Estado de tu cuenta:**

🟢 **Tokens disponibles:** 45,000 / 50,000
📅 **Renovación:** En 15 días
💾 **Almacenamiento:** 2.3 GB / 5 GB
🔄 **Consultas diarias:** 156 / 200

💡 **Optimizaciones:**
- Usar consultas específicas para ahorrar tokens
- Limpiar historial de chat antiguo
- Usar cache para consultas repetitivas
```

## 🎓 Consejos y Mejores Prácticas

### 💡 **Para Consultas Eficientes**
1. **Sé específico:** "Usuarios activos en los últimos 7 días" vs "Usuarios"
2. **Usa contexto:** "Compara con el mes anterior"
3. **Define el formato:** "En formato tabla" o "Como gráfico"

### 🔍 **Para Exploración Efectiva**
1. **Empieza amplio:** "¿Qué datos tengo sobre ventas?"
2. **Refina gradualmente:** "Ahora solo del último trimestre"
3. **Pregunta por opciones:** "¿Qué más puedo hacer con estos datos?"

### 🚀 **Para Automatización**
1. **Define el objetivo:** "Quiero un reporte semanal automático"
2. **Especifica el formato:** "En PDF y enviado por email"
3. **Establece horarios:** "Todos los lunes a las 9:00 AM"

## 📞 Soporte y Ayuda

### 🆘 **Cuándo Pedir Ayuda**
- No entiendes la respuesta del sistema
- Una funcionalidad no funciona como esperabas
- Necesitas configurar algo específico
- Quieres reportar un bug o sugerir mejoras

### 📚 **Recursos de Ayuda**
- **Documentación técnica:** `/docs/api`
- **Ejemplos de uso:** `/examples`
- **FAQ:** `/help/faq`
- **Soporte directo:** `support@apichat.com`

### 💬 **Comandos de Ayuda**
```
Usuario: "Ayuda"
APIchat: "Aquí tienes los comandos disponibles:

📚 **Comandos básicos:**
- 'ayuda' - Mostrar esta ayuda
- 'modo explorer' - Cambiar a modo exploración
- 'modo guided' - Cambiar a modo dirigido
- 'recursos' - Ver recursos disponibles
- 'historial' - Ver conversaciones anteriores
- 'configurar' - Ajustar preferencias

🎯 **Comandos de datos:**
- 'consultar [tabla]' - Consultar datos específicos
- 'analizar [dato]' - Análisis automático
- 'reporte [tipo]' - Generar reporte
- 'exportar [formato]' - Exportar datos

🔧 **Comandos del sistema:**
- 'estado' - Ver estado del sistema
- 'limpiar' - Limpiar historial
- 'reiniciar' - Reiniciar sesión"
```

## 🎉 ¡Felicidades!

Ahora conoces las funcionalidades principales de APIchat. El sistema está diseñado para ser intuitivo y aprender de tus preferencias con el tiempo.

**Recuerda:**
- 🗣️ **Habla naturalmente** - No necesitas comandos técnicos
- 🔍 **Explora primero** - Usa el modo Explorer para descubrir opciones
- 🎯 **Sé específico** - Cuanto más claro seas, mejor será la respuesta
- 💡 **Pregunta por opciones** - Siempre hay múltiples formas de hacer las cosas
- 🚀 **Automatiza** - Configura reportes y análisis recurrentes

¡Disfruta explorando el poder de APIchat! 🚀
