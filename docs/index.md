# 🧠 APIchat Documentation

Bienvenido a la documentación oficial de **APIchat**, la plataforma de automatización inteligente que combina chat conversacional, ejecución de funciones y conexión con bases de datos.

## 🚀 ¿Qué es APIchat?

APIchat es una plataforma SaaS que permite a los desarrolladores crear automatizaciones inteligentes usando lenguaje natural. Combina:

- **🤖 IA Conversacional**: Chat con memoria de contexto
- **🔧 Function Calling**: Ejecución automática de funciones HTTP, SQL y Python
- **🗄️ Multi-DB**: Soporte para PostgreSQL, MySQL, SQLite, Oracle, SQL Server
- **📊 Métricas Avanzadas**: Tracking de uso y performance en tiempo real
- **⚡ Optimizaciones**: Cache inteligente, paralelización y profiling detallado

## 🎯 Casos de Uso

### **Automatización de Negocios**
```python
# Ejemplo: Automatizar reportes de ventas
"Genera un reporte de ventas del mes actual y envíalo por email"
```

### **Integración de APIs**
```python
# Ejemplo: Conectar múltiples servicios
"Cuando llegue un nuevo lead, guárdalo en la BD y envíalo a Slack"
```

### **Análisis de Datos**
```python
# Ejemplo: Consultas complejas
"Analiza los usuarios más activos y crea un gráfico de engagement"
```

## 🏗️ Arquitectura

```mermaid
graph TD
    A[User Input] --> B[OrchestratorService]
    B --> C[OpenAI Service]
    C --> D[Plan Generation]
    D --> E[Execution Engine]
    E --> F[Database Service]
    E --> G[Function Service]
    E --> H[Proxy Service]
    F --> I[Results]
    G --> I
    H --> I
    I --> J[Response]
```

## 📈 Performance

Nuestras optimizaciones garantizan:

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| **Tiempo Total** | 4-6s | 1.5-2.5s | **60-70%** |
| **Consultas BD** | ~200ms | ~50ms | **75%** |
| **Llamadas OpenAI** | 3-5s | 1-2s | **60%** |

## 🔧 Quick Start

### **1. Instalación**
```bash
git clone https://github.com/tu-usuario/apichat-backend.git
cd apichat-backend
pip install -r requirements.txt
```

### **2. Configuración**
```bash
# .env
DATABASE_URL=postgresql://user:pass@localhost:5432/apichat
OPENAI_API_KEY=sk-...
```

### **3. Ejecutar**
```bash
uvicorn app.main:app --reload
```

### **4. Probar**
```bash
curl -X POST http://localhost:8000/chat/send \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola, ¿cómo estás?"}'
```

## 📚 Documentación

### **Para Desarrolladores**
- [🏗️ Arquitectura](architecture/overview.md) - Entender la estructura del sistema
- [🔧 Instalación](installation.md) - Configurar el entorno de desarrollo
- [📊 Performance](development/performance.md) - Optimizaciones y profiling
- [🧪 Testing](development/testing.md) - Escribir y ejecutar tests

### **Para Usuarios**
- [🚀 Quick Start](quickstart.md) - Empezar en 5 minutos
- [🔌 APIs](api/chat.md) - Referencia completa de endpoints
- [📖 Guías](guides/functions.md) - Tutoriales paso a paso
- [📈 Métricas](api/performance.md) - Monitoreo y analytics

### **Para DevOps**
- [🚀 Deployment](development/deployment.md) - Despliegue en producción
- [📊 Monitoring](development/performance.md) - Métricas y alertas
- [🔧 Configuration](configuration.md) - Variables de entorno

## 🤝 Contribuir

¿Quieres contribuir al proyecto?

1. **Fork** el repositorio
2. **Crea** una rama para tu feature
3. **Desarrolla** con tests y documentación
4. **Envía** un Pull Request

Ver [Contributing Guidelines](CONTRIBUTING.md) para más detalles.

## 🆘 Soporte

- **📧 Email**: support@apichat.es
- **💬 Discord**: [Comunidad APIchat](https://discord.gg/apichat)
- **🐛 Issues**: [GitHub Issues](https://github.com/tu-usuario/apichat-backend/issues)
- **📖 Docs**: Esta documentación

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver [LICENSE](../LICENSE) para más detalles.

---

**¡Gracias por usar APIchat! 🚀** 