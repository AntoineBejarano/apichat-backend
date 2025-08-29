# 🚀 API Chat Backend - Sistema Inteligente de Chat con Base de Datos

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Sistema de chat inteligente que permite conversar con bases de datos usando lenguaje natural, con capacidades avanzadas de RAG (Retrieval-Augmented Generation) y análisis semántico.**

## 📋 Tabla de Contenidos

- [🎯 Características Principales](#-características-principales)
- [🏗️ Arquitectura del Sistema](#️-arquitectura-del-sistema)
- [🚀 Inicio Rápido](#-inicio-rápido)
- [⚙️ Configuración](#️-configuración)
- [📊 Variables de Entorno](#-variables-de-entorno)
- [🔧 Instalación](#-instalación)
- [📖 Uso](#-uso)
- [🔍 API Endpoints](#-api-endpoints)
- [🔄 Flujo de Datos](#-flujo-de-datos)
- [🛠️ Troubleshooting](#️-troubleshooting)
- [📈 Monitoreo y Métricas](#-monitoreo-y-métricas)
- [🤝 Contribución](#-contribución)
- [📄 Licencia](#-licencia)

## 🎯 Características Principales

### **🧠 Inteligencia Artificial**
- **Chat Inteligente**: Conversación natural con bases de datos
- **RAG Avanzado**: Retrieval-Augmented Generation con embeddings semánticos
- **Análisis de Intención**: Router inteligente para clasificar consultas
- **Planificación**: Generación de planes de ejecución estructurados
- **SQL Generation**: Generación automática de consultas SQL

### **🔧 Sistema Provider-Agnóstico**
- **Múltiples LLMs**: OpenAI, Anthropic (Claude), Google (Gemini), Cohere
- **Vector Stores**: pgvector, Pinecone, Weaviate, Qdrant
- **Cache Flexible**: Redis, Upstash (serverless)
- **Configuración por ENV**: Cambio de proveedores sin modificar código

### **🛡️ Seguridad y Robustez**
- **Políticas SQL Estrictas**: Solo SELECT, límites de filas y timeout
- **Validación de Consultas**: Verificación de seguridad antes de ejecución
- **Logs Estructurados**: Trazabilidad completa con JSON
- **Manejo de Errores**: Mensajes claros y códigos de error estandarizados

### **📊 Pipeline de Datos**
- **Ingesta de Schemas**: Procesamiento automático de estructuras de BD
- **Generación de Grafos**: Relaciones semánticas entre entidades
- **Chunking Inteligente**: Fragmentación semántica de documentos
- **Indexación Vectorial**: Embeddings para búsqueda semántica

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   Load Balancer  │
│   (React/Vue)   │◄──►│   (FastAPI)      │◄──►│   (Nginx/Traefik)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CORE SERVICES LAYER                          │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  Chat Service   │  Schema Service  │  Vector Service │  Cache    │
│  (Intelligent)  │  (Pipeline)     │  (RAG)          │  (Redis)  │
└─────────────────┴─────────────────┴─────────────────┴───────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ADAPTERS LAYER                               │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  LLM Adapter    │  Vector Adapter │  Cache Adapter  │  Embedding│
│  (Provider-     │  (pgvector/     │  (Redis/        │  (OpenAI/ │
│   agnóstico)    │   Pinecone)     │   Upstash)      │   Cohere) │
└─────────────────┴─────────────────┴─────────────────┴───────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL PROVIDERS                           │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  OpenAI API     │  Anthropic API  │  Google AI      │  Cohere   │
│  (GPT-4/3.5)    │  (Claude)       │  (Gemini)       │  (Command)│
└─────────────────┴─────────────────┴─────────────────┴───────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                               │
├─────────────────┬─────────────────┬─────────────────┬───────────┤
│  PostgreSQL     │  Vector Store   │  Cache Store    │  Logs     │
│  (Main Data)    │  (Embeddings)   │  (Session)      │  (JSON)   │
└─────────────────┴─────────────────┴─────────────────┴───────────┘
```

## 🚀 Inicio Rápido

### **Prerrequisitos**
- Python 3.9+
- PostgreSQL 13+
- Redis (opcional, para cache)
- Docker (opcional)

### **1. Clonar el Repositorio**
```bash
git clone https://github.com/tu-usuario/apichat-backend.git
cd apichat-backend
```

### **2. Configurar Variables de Entorno**
```bash
cp .env.example .env
# Editar .env con tus configuraciones
```

### **3. Instalar Dependencias**
```bash
pip install -r requirements.txt
```

### **4. Configurar Base de Datos**
```bash
# Crear base de datos PostgreSQL
createdb apichat_db

# Ejecutar migraciones
python -m alembic upgrade head
```

### **5. Iniciar el Servidor**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### **6. Verificar Instalación**
```bash
curl http://localhost:8000/health
```

## ⚙️ Configuración

### **Configuración Mínima**
```bash
# LLM Provider (requerido)
LLM_PROVIDER=openai
LLM_API_KEY=tu-api-key-openai

# Database (requerido)
DATABASE_URL=postgresql://user:pass@localhost:5432/apichat_db

# Cache (opcional, usa Redis por defecto)
CACHE_PROVIDER=redis
CACHE_URL=redis://localhost:6379/0
```

### **Configuración Avanzada**
```bash
# Vector Store
VECTOR_PROVIDER=pgvector
VECTOR_URL=postgresql://user:pass@localhost:5432/vector_db

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-ada-002

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## 📊 Variables de Entorno

### **🔑 Autenticación y APIs**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `LLM_PROVIDER` | Proveedor de LLM (openai/anthropic/google/cohere) | `openai` | ✅ |
| `LLM_API_KEY` | API Key del proveedor LLM | - | ✅ |
| `LLM_URL` | URL base del proveedor (para self-hosted) | - | ❌ |
| `LLM_TIMEOUT` | Timeout en segundos para requests LLM | `60` | ❌ |
| `LLM_MAX_RETRIES` | Máximo número de reintentos | `3` | ❌ |

### **🗄️ Base de Datos**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `DATABASE_URL` | URL de conexión PostgreSQL | - | ✅ |
| `DATABASE_POOL_SIZE` | Tamaño del pool de conexiones | `20` | ❌ |
| `DATABASE_MAX_OVERFLOW` | Máximo overflow del pool | `30` | ❌ |

### **🔍 Vector Store**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `VECTOR_PROVIDER` | Proveedor vectorial (pgvector/pinecone/weaviate/qdrant) | `pgvector` | ❌ |
| `VECTOR_URL` | URL del vector store | `DATABASE_URL` | ❌ |
| `VECTOR_API_KEY` | API Key del vector store | - | ❌ |
| `VECTOR_NAMESPACE_STRATEGY` | Estrategia de namespaces | `tenant_app_db_snapshot` | ❌ |
| `VECTOR_DIMENSION` | Dimensión de embeddings | `1536` | ❌ |

### **💾 Cache**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `CACHE_PROVIDER` | Proveedor de cache (redis/upstash) | `redis` | ❌ |
| `CACHE_URL` | URL del cache | `redis://localhost:6379/0` | ❌ |
| `CACHE_API_KEY` | API Key del cache (Upstash) | - | ❌ |
| `CACHE_TIMEOUT` | Timeout en segundos | `10` | ❌ |
| `CACHE_MAX_RETRIES` | Máximo número de reintentos | `3` | ❌ |

### **🔧 Embeddings**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `EMBEDDING_PROVIDER` | Proveedor de embeddings (openai/cohere/huggingface) | `openai` | ❌ |
| `EMBEDDING_MODEL` | Modelo de embeddings | `text-embedding-ada-002` | ❌ |
| `EMBEDDING_API_KEY` | API Key del proveedor | `LLM_API_KEY` | ❌ |
| `BATCH_SIZE_EMBEDDINGS` | Tamaño de batch para embeddings | `100` | ❌ |

### **📝 Logging**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `LOG_LEVEL` | Nivel de logging (DEBUG/INFO/WARNING/ERROR) | `INFO` | ❌ |
| `LOG_FORMAT` | Formato de logs (json/text) | `json` | ❌ |
| `LOG_FILE` | Archivo de logs (opcional) | - | ❌ |

### **🛡️ Seguridad**
| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|-----------|
| `SQL_MAX_ROWS` | Máximo número de filas por consulta | `1000` | ❌ |
| `SQL_TIMEOUT_SECONDS` | Timeout para consultas SQL | `30` | ❌ |
| `SQL_ALLOWED_SCHEMAS` | Schemas permitidos (comma-separated) | `public` | ❌ |
| `SQL_READ_ONLY` | Solo consultas SELECT | `true` | ❌ |

## 🔧 Instalación

### **Instalación con Docker (Recomendado)**

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/apichat-backend.git
cd apichat-backend

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# 3. Iniciar con Docker Compose
docker-compose up -d

# 4. Verificar instalación
curl http://localhost:8000/health
```

### **Instalación Manual**

```bash
# 1. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar base de datos
createdb apichat_db
python -m alembic upgrade head

# 4. Iniciar servidor
uvicorn app.main:app --reload
```

## 📖 Uso

### **1. Configurar Base de Datos**
```bash
# Agregar conexión de base de datos
curl -X POST "http://localhost:8000/databases" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mi_base_datos",
    "host": "localhost",
    "port": 5432,
    "database": "mi_db",
    "username": "usuario",
    "password": "contraseña"
  }'
```

### **2. Procesar Schema**
```bash
# Iniciar procesamiento del schema
curl -X POST "http://localhost:8000/schema/process/1" \
  -H "Content-Type: application/json"
```

### **3. Chat Inteligente**
```bash
# Hacer pregunta en lenguaje natural
curl -X POST "http://localhost:8000/chat/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Cuántos usuarios tenemos registrados?",
    "database_id": 1
  }'
```

## 🔍 API Endpoints

### **🏥 Health Check**
```http
GET /health
```
**Respuesta:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "llm": "healthy",
    "vector_store": "healthy"
  }
}
```

### **🗄️ Databases**
```http
GET /databases                    # Listar bases de datos
POST /databases                   # Crear conexión
GET /databases/{id}              # Obtener detalles
PUT /databases/{id}              # Actualizar conexión
DELETE /databases/{id}           # Eliminar conexión
```

### **📊 Schema**
```http
GET /schema/status/{db_id}        # Estado del schema
POST /schema/process/{db_id}     # Procesar schema
GET /schema/graph/{db_id}        # Obtener grafo de relaciones
POST /schema/retry/{db_id}       # Reintentar procesamiento
```

### **💬 Chat**
```http
POST /chat/ask                   # Pregunta inteligente
GET /chat/history/{session_id}   # Historial de chat
POST /chat/clear/{session_id}    # Limpiar historial
```

### **🔍 Vector Search**
```http
POST /vector/search              # Búsqueda semántica
GET /vector/status              # Estado del vector store
POST /vector/reindex/{db_id}    # Reindexar embeddings
```

## 🔄 Flujo de Datos

### **1. Ingesta de Schema**
```
Base de Datos → Schema Service → Pipeline de Estados → Grafo de Relaciones
     ↓              ↓                    ↓                    ↓
  Conexión    Extracción de    Procesamiento por    Generación de
  PostgreSQL   Metadatos       Stages (0-100%)      Nodos y Aristas
```

### **2. Procesamiento de Chunks**
```
Documentos → Chunking Service → Embeddings → Vector Store
     ↓              ↓              ↓            ↓
  Metadata    Fragmentación    OpenAI API   pgvector/
  Semántica   Inteligente      Cohere       Pinecone
```

### **3. Chat Inteligente**
```
Usuario → Intent Router → Grounding → Planificación → SQL Generation → Validación → Ejecución
   ↓           ↓            ↓           ↓              ↓              ↓           ↓
Pregunta   Clasificación   Contexto   Plan de      Consulta SQL   Verificación  Resultado
Natural    de Intención   Semántico   Acciones     Generada       de Seguridad  Formateado
```

## 🛠️ Troubleshooting

### **Problemas Comunes**

#### **1. Error de Conexión a Base de Datos**
```bash
# Error: "connection refused"
# Solución:
- Verificar que PostgreSQL esté ejecutándose
- Verificar DATABASE_URL en .env
- Verificar credenciales de usuario
```

#### **2. Error de API Key de LLM**
```bash
# Error: "The api_key client option must be set"
# Solución:
- Verificar LLM_API_KEY en .env
- Verificar que la API key sea válida
- Verificar límites de uso de la API
```

#### **3. Error de Vector Store**
```bash
# Error: "vector extension not available"
# Solución:
- Instalar extensión pgvector: CREATE EXTENSION vector;
- Verificar VECTOR_PROVIDER en .env
- Verificar conexión al vector store
```

#### **4. Error de Cache**
```bash
# Error: "Redis connection failed"
# Solución:
- Verificar que Redis esté ejecutándose
- Verificar CACHE_URL en .env
- Cambiar a CACHE_PROVIDER=upstash si no tienes Redis local
```

### **Logs y Debugging**

#### **Verificar Logs**
```bash
# Logs en formato JSON
tail -f logs/app.log | jq '.'

# Logs de errores específicos
grep "ERROR" logs/app.log | jq '.'
```

#### **Health Check Detallado**
```bash
# Verificar estado de todos los servicios
curl http://localhost:8000/health | jq '.'
```

#### **Métricas de Performance**
```bash
# Ver métricas de adapters
curl http://localhost:8000/metrics | jq '.'
```

## 📈 Monitoreo y Métricas

### **Métricas Disponibles**
- **Requests por minuto**
- **Latencia promedio**
- **Tasa de éxito/error**
- **Uso de tokens LLM**
- **Tiempo de respuesta vector search**
- **Estado de health checks**

### **Alertas Recomendadas**
- Latencia > 5 segundos
- Tasa de error > 5%
- Health check fallido
- Uso de API keys > 80%

### **Dashboards Sugeridos**
- Grafana para métricas en tiempo real
- Prometheus para recolección de métricas
- ELK Stack para análisis de logs

## 🤝 Contribución

### **1. Fork del Repositorio**
```bash
git clone https://github.com/tu-usuario/apichat-backend.git
cd apichat-backend
```

### **2. Crear Rama de Feature**
```bash
git checkout -b feature/nueva-funcionalidad
```

### **3. Desarrollar y Testear**
```bash
# Instalar dependencias de desarrollo
pip install -r requirements-dev.txt

# Ejecutar tests
python -m pytest tests/

# Ejecutar linting
flake8 app/
black app/
```

### **4. Crear Pull Request**
- Describir cambios realizados
- Incluir tests si aplica
- Verificar que todos los tests pasen
- Actualizar documentación si es necesario

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.

---

## 🆘 Soporte

- **Documentación**: [docs/](docs/)
- **Guía de Variables de Entorno**: [docs/ENVIRONMENT_VARIABLES.md](docs/ENVIRONMENT_VARIABLES.md)
- **Guía de Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Issues**: [GitHub Issues](https://github.com/tu-usuario/apichat-backend/issues)
- **Discusiones**: [GitHub Discussions](https://github.com/tu-usuario/apichat-backend/discussions)
- **Email**: soporte@apichat.com

---

**¿Te gustó el proyecto? ¡Dale una ⭐ en GitHub!**
