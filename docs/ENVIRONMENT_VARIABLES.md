# 📊 Guía Completa de Variables de Entorno

> **Documentación detallada de todas las variables de entorno disponibles en API Chat Backend, incluyendo ejemplos, valores por defecto y casos de uso.**

## 📋 Tabla de Contenidos

- [🔑 Autenticación y APIs](#-autenticación-y-apis)
- [🗄️ Base de Datos](#️-base-de-datos)
- [🔍 Vector Store](#-vector-store)
- [💾 Cache](#-cache)
- [🔧 Embeddings](#-embeddings)
- [📝 Logging](#-logging)
- [🛡️ Seguridad](#️-seguridad)
- [⚙️ Configuración General](#️-configuración-general)
- [🔧 Ejemplos de Configuración](#-ejemplos-de-configuración)

## 🔑 Autenticación y APIs

### **LLM Provider**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `LLM_PROVIDER` | Proveedor de LLM | `openai` | ✅ | `anthropic` |
| `LLM_API_KEY` | API Key del proveedor | - | ✅ | `sk-...` |
| `LLM_URL` | URL base (self-hosted) | - | ❌ | `https://api.openai.com/v1` |
| `LLM_TIMEOUT` | Timeout en segundos | `60` | ❌ | `120` |
| `LLM_MAX_RETRIES` | Máximo reintentos | `3` | ❌ | `5` |
| `LLM_BATCH_SIZE` | Tamaño de batch | `1` | ❌ | `10` |

#### **Proveedores Soportados**

**OpenAI**
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
LLM_URL=https://api.openai.com/v1  # opcional
```

**Anthropic (Claude)**
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-anthropic-key
```

**Google (Gemini)**
```bash
LLM_PROVIDER=google
LLM_API_KEY=your-google-api-key
```

**Cohere**
```bash
LLM_PROVIDER=cohere
LLM_API_KEY=your-cohere-api-key
```

## 🗄️ Base de Datos

### **Conexión Principal**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `DATABASE_URL` | URL de conexión PostgreSQL | - | ✅ | `postgresql://user:pass@localhost:5432/db` |
| `DATABASE_POOL_SIZE` | Tamaño del pool | `20` | ❌ | `50` |
| `DATABASE_MAX_OVERFLOW` | Máximo overflow | `30` | ❌ | `40` |
| `DATABASE_ECHO` | Log SQL queries | `false` | ❌ | `true` |

#### **Ejemplos de Conexión**

**Local PostgreSQL**
```bash
DATABASE_URL=postgresql://usuario:contraseña@localhost:5432/apichat_db
```

**PostgreSQL en la Nube**
```bash
DATABASE_URL=postgresql://user:pass@db.example.com:5432/production_db?sslmode=require
```

**Con Parámetros Adicionales**
```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/db?connect_timeout=10&application_name=apichat
```

## 🔍 Vector Store

### **Configuración Vectorial**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `VECTOR_PROVIDER` | Proveedor vectorial | `pgvector` | ❌ | `pinecone` |
| `VECTOR_URL` | URL del vector store | `DATABASE_URL` | ❌ | `https://api.pinecone.io` |
| `VECTOR_API_KEY` | API Key del vector store | - | ❌ | `your-pinecone-key` |
| `VECTOR_NAMESPACE_STRATEGY` | Estrategia de namespaces | `tenant_app_db_snapshot` | ❌ | `simple` |
| `VECTOR_DIMENSION` | Dimensión de embeddings | `1536` | ❌ | `1024` |
| `VECTOR_TIMEOUT` | Timeout en segundos | `30` | ❌ | `60` |
| `VECTOR_MAX_RETRIES` | Máximo reintentos | `3` | ❌ | `5` |
| `VECTOR_BATCH_SIZE` | Tamaño de batch | `100` | ❌ | `200` |

#### **Proveedores Soportados**

**pgvector (PostgreSQL)**
```bash
VECTOR_PROVIDER=pgvector
VECTOR_URL=postgresql://user:pass@localhost:5432/vector_db
# No requiere API key
```

**Pinecone**
```bash
VECTOR_PROVIDER=pinecone
VECTOR_URL=https://api.pinecone.io
VECTOR_API_KEY=your-pinecone-api-key
```

**Weaviate**
```bash
VECTOR_PROVIDER=weaviate
VECTOR_URL=http://localhost:8080
VECTOR_API_KEY=your-weaviate-api-key
```

**Qdrant**
```bash
VECTOR_PROVIDER=qdrant
VECTOR_URL=http://localhost:6333
VECTOR_API_KEY=your-qdrant-api-key
```

## 💾 Cache

### **Configuración de Cache**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `CACHE_PROVIDER` | Proveedor de cache | `redis` | ❌ | `upstash` |
| `CACHE_URL` | URL del cache | `redis://localhost:6379/0` | ❌ | `https://upstash.io` |
| `CACHE_API_KEY` | API Key del cache | - | ❌ | `your-upstash-key` |
| `CACHE_TIMEOUT` | Timeout en segundos | `10` | ❌ | `20` |
| `CACHE_MAX_RETRIES` | Máximo reintentos | `3` | ❌ | `5` |
| `CACHE_BATCH_SIZE` | Tamaño de batch | `100` | ❌ | `200` |

#### **Proveedores Soportados**

**Redis Local**
```bash
CACHE_PROVIDER=redis
CACHE_URL=redis://localhost:6379/0
```

**Redis en la Nube**
```bash
CACHE_PROVIDER=redis
CACHE_URL=redis://user:pass@redis.example.com:6379/0
```

**Upstash (Serverless Redis)**
```bash
CACHE_PROVIDER=upstash
CACHE_URL=https://your-instance.upstash.io
CACHE_API_KEY=your-upstash-api-key
```

## 🔧 Embeddings

### **Configuración de Embeddings**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `EMBEDDING_PROVIDER` | Proveedor de embeddings | `openai` | ❌ | `cohere` |
| `EMBEDDING_MODEL` | Modelo de embeddings | `text-embedding-ada-002` | ❌ | `embed-english-v3.0` |
| `EMBEDDING_API_KEY` | API Key del proveedor | `LLM_API_KEY` | ❌ | `sk-...` |
| `EMBEDDING_URL` | URL base (self-hosted) | - | ❌ | `https://api.openai.com/v1` |
| `EMBEDDING_TIMEOUT` | Timeout en segundos | `30` | ❌ | `60` |
| `EMBEDDING_MAX_RETRIES` | Máximo reintentos | `3` | ❌ | `5` |
| `BATCH_SIZE_EMBEDDINGS` | Tamaño de batch | `100` | ❌ | `200` |

#### **Proveedores Soportados**

**OpenAI**
```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_API_KEY=sk-your-openai-key
```

**Cohere**
```bash
EMBEDDING_PROVIDER=cohere
EMBEDDING_MODEL=embed-english-v3.0
EMBEDDING_API_KEY=your-cohere-api-key
```

**HuggingFace**
```bash
EMBEDDING_PROVIDER=huggingface
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_API_KEY=your-huggingface-token
```

## 📝 Logging

### **Configuración de Logs**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `LOG_LEVEL` | Nivel de logging | `INFO` | ❌ | `DEBUG` |
| `LOG_FORMAT` | Formato de logs | `json` | ❌ | `text` |
| `LOG_FILE` | Archivo de logs | - | ❌ | `logs/app.log` |
| `LOG_MAX_SIZE` | Tamaño máximo por archivo | `10MB` | ❌ | `50MB` |
| `LOG_BACKUP_COUNT` | Número de backups | `5` | ❌ | `10` |

#### **Niveles de Log Disponibles**
- `DEBUG`: Información detallada para debugging
- `INFO`: Información general del sistema
- `WARNING`: Advertencias que no impiden funcionamiento
- `ERROR`: Errores que afectan funcionalidad
- `CRITICAL`: Errores críticos del sistema

#### **Formatos Disponibles**
- `json`: Logs estructurados en JSON (recomendado)
- `text`: Logs en formato texto plano

## 🛡️ Seguridad

### **Políticas SQL**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `SQL_MAX_ROWS` | Máximo filas por consulta | `1000` | ❌ | `500` |
| `SQL_TIMEOUT_SECONDS` | Timeout para consultas | `30` | ❌ | `60` |
| `SQL_ALLOWED_SCHEMAS` | Schemas permitidos | `public` | ❌ | `public,sales,hr` |
| `SQL_READ_ONLY` | Solo consultas SELECT | `true` | ❌ | `false` |
| `SQL_BLACKLIST_KEYWORDS` | Palabras prohibidas | - | ❌ | `DROP,TRUNCATE,DELETE` |

### **Autenticación y Autorización**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `AUTH_ENABLED` | Habilitar autenticación | `false` | ❌ | `true` |
| `AUTH_SECRET_KEY` | Clave secreta para JWT | - | ❌ | `your-secret-key` |
| `AUTH_ALGORITHM` | Algoritmo JWT | `HS256` | ❌ | `RS256` |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Expiración token | `30` | ❌ | `60` |

## ⚙️ Configuración General

### **Servidor y Performance**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `HOST` | Host del servidor | `0.0.0.0` | ❌ | `127.0.0.1` |
| `PORT` | Puerto del servidor | `8000` | ❌ | `8080` |
| `WORKERS` | Número de workers | `1` | ❌ | `4` |
| `RELOAD` | Auto-reload en desarrollo | `true` | ❌ | `false` |
| `CORS_ORIGINS` | Orígenes CORS permitidos | `*` | ❌ | `http://localhost:3000` |

### **Métricas y Monitoreo**

| Variable | Descripción | Default | Requerido | Ejemplo |
|----------|-------------|---------|-----------|---------|
| `METRICS_ENABLED` | Habilitar métricas | `true` | ❌ | `false` |
| `METRICS_PORT` | Puerto para métricas | `9090` | ❌ | `8080` |
| `HEALTH_CHECK_INTERVAL` | Intervalo health check | `30` | ❌ | `60` |

## 🔧 Ejemplos de Configuración

### **Configuración Mínima**
```bash
# .env
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
DATABASE_URL=postgresql://user:pass@localhost:5432/apichat_db
```

### **Configuración de Desarrollo**
```bash
# .env
# LLM
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-openai-key
LLM_TIMEOUT=60

# Database
DATABASE_URL=postgresql://dev:dev@localhost:5432/apichat_dev
DATABASE_POOL_SIZE=10

# Cache
CACHE_PROVIDER=redis
CACHE_URL=redis://localhost:6379/0

# Vector Store
VECTOR_PROVIDER=pgvector
VECTOR_URL=postgresql://dev:dev@localhost:5432/vector_dev

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-ada-002

# Logging
LOG_LEVEL=DEBUG
LOG_FORMAT=json

# Security
SQL_MAX_ROWS=1000
SQL_TIMEOUT_SECONDS=30
SQL_READ_ONLY=true
```

### **Configuración de Producción**
```bash
# .env
# LLM
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-anthropic-key
LLM_TIMEOUT=120
LLM_MAX_RETRIES=5

# Database
DATABASE_URL=postgresql://prod:prod@db.example.com:5432/apichat_prod?sslmode=require
DATABASE_POOL_SIZE=50
DATABASE_MAX_OVERFLOW=30

# Cache
CACHE_PROVIDER=upstash
CACHE_URL=https://your-instance.upstash.io
CACHE_API_KEY=your-upstash-api-key
CACHE_TIMEOUT=20

# Vector Store
VECTOR_PROVIDER=pinecone
VECTOR_URL=https://api.pinecone.io
VECTOR_API_KEY=your-pinecone-api-key
VECTOR_DIMENSION=1536

# Embeddings
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_API_KEY=sk-your-openai-key
BATCH_SIZE_EMBEDDINGS=200

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=logs/app.log

# Security
SQL_MAX_ROWS=500
SQL_TIMEOUT_SECONDS=60
SQL_ALLOWED_SCHEMAS=public,sales,hr
SQL_READ_ONLY=true

# Server
HOST=0.0.0.0
PORT=8000
WORKERS=4
CORS_ORIGINS=https://app.example.com

# Metrics
METRICS_ENABLED=true
METRICS_PORT=9090
```

### **Configuración con Docker**
```bash
# docker-compose.yml
version: '3.8'
services:
  app:
    image: apichat-backend:latest
    environment:
      - LLM_PROVIDER=openai
      - LLM_API_KEY=${LLM_API_KEY}
      - DATABASE_URL=postgresql://user:pass@db:5432/apichat
      - CACHE_PROVIDER=redis
      - CACHE_URL=redis://redis:6379/0
      - VECTOR_PROVIDER=pgvector
      - VECTOR_URL=postgresql://user:pass@db:5432/vector
    ports:
      - "8000:8000"
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=apichat
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## 🔍 Validación de Configuración

### **Verificar Configuración**
```bash
# Verificar variables requeridas
python -c "
import os
required_vars = ['LLM_PROVIDER', 'LLM_API_KEY', 'DATABASE_URL']
missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print(f'❌ Variables faltantes: {missing}')
else:
    print('✅ Todas las variables requeridas están configuradas')
"
```

### **Test de Conexiones**
```bash
# Test de health check
curl http://localhost:8000/health | jq '.'

# Test de métricas
curl http://localhost:8000/metrics | jq '.'
```

---

## 📚 Referencias Adicionales

- [README Principal](../README.md)
- [Guía de Instalación](INSTALLATION.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [API Documentation](API.md)
