# 🛠️ Guía de Solución de Problemas

> **Guía completa para diagnosticar y resolver problemas comunes en API Chat Backend, organizada por categorías y con soluciones paso a paso.**

## 📋 Tabla de Contenidos

- [🔍 Diagnóstico General](#-diagnóstico-general)
- [🗄️ Problemas de Base de Datos](#️-problemas-de-base-de-datos)
- [🤖 Problemas de LLM](#-problemas-de-llm)
- [🔍 Problemas de Vector Store](#-problemas-de-vector-store)
- [💾 Problemas de Cache](#-problemas-de-cache)
- [🔧 Problemas de Embeddings](#-problemas-de-embeddings)
- [📝 Problemas de Logging](#-problemas-de-logging)
- [🛡️ Problemas de Seguridad](#️-problemas-de-seguridad)
- [🚀 Problemas de Performance](#-problemas-de-performance)
- [🐳 Problemas de Docker](#-problemas-de-docker)
- [📞 Soporte](#-soporte)

## 🔍 Diagnóstico General

### **Health Check Completo**
```bash
# Verificar estado general del sistema
curl http://localhost:8000/health | jq '.'

# Verificar métricas detalladas
curl http://localhost:8000/metrics | jq '.'

# Verificar logs en tiempo real
tail -f logs/app.log | jq '.'
```

### **Verificar Variables de Entorno**
```bash
# Script para verificar configuración
python -c "
import os
required_vars = {
    'LLM_PROVIDER': 'Proveedor de LLM',
    'LLM_API_KEY': 'API Key de LLM',
    'DATABASE_URL': 'URL de base de datos'
}
print('🔍 Verificando variables de entorno...')
for var, desc in required_vars.items():
    value = os.getenv(var)
    if value:
        print(f'✅ {var}: {desc} - CONFIGURADO')
    else:
        print(f'❌ {var}: {desc} - FALTANTE')
"
```

### **Verificar Dependencias**
```bash
# Verificar instalación de Python
python --version

# Verificar dependencias instaladas
pip list | grep -E "(fastapi|sqlalchemy|openai|redis)"

# Verificar puertos en uso
netstat -tulpn | grep :8000
```

## 🗄️ Problemas de Base de Datos

### **Error: "connection refused"**

**Síntomas:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "localhost" (127.0.0.1), port 5432 failed: Connection refused
```

**Soluciones:**

1. **Verificar que PostgreSQL esté ejecutándose**
```bash
# Linux/Mac
sudo systemctl status postgresql
sudo systemctl start postgresql

# Windows
net start postgresql-x64-15
```

2. **Verificar configuración de conexión**
```bash
# Verificar DATABASE_URL en .env
echo $DATABASE_URL

# Test de conexión manual
psql "postgresql://user:pass@localhost:5432/dbname"
```

3. **Verificar firewall**
```bash
# Verificar puerto 5432
sudo ufw status
sudo ufw allow 5432
```

### **Error: "database does not exist"**

**Síntomas:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL: database "apichat_db" does not exist
```

**Soluciones:**

1. **Crear base de datos**
```bash
createdb apichat_db
```

2. **Verificar usuario y permisos**
```bash
# Conectar como superusuario
sudo -u postgres psql

# Crear usuario y base de datos
CREATE USER apichat_user WITH PASSWORD 'password';
CREATE DATABASE apichat_db OWNER apichat_user;
GRANT ALL PRIVILEGES ON DATABASE apichat_db TO apichat_user;
```

### **Error: "permission denied"**

**Síntomas:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) permission denied for table users
```

**Soluciones:**

1. **Verificar permisos de usuario**
```bash
# Conectar a la base de datos
psql "postgresql://user:pass@localhost:5432/dbname"

# Verificar permisos
\du
\dt
```

2. **Otorgar permisos necesarios**
```sql
GRANT USAGE ON SCHEMA public TO apichat_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO apichat_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO apichat_user;
```

### **Error: "pgvector extension not available"**

**Síntomas:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) extension "vector" is not available
```

**Soluciones:**

1. **Instalar extensión pgvector**
```bash
# Conectar como superusuario
sudo -u postgres psql

# Instalar extensión
CREATE EXTENSION IF NOT EXISTS vector;
```

2. **Verificar instalación**
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

## 🤖 Problemas de LLM

### **Error: "The api_key client option must be set"**

**Síntomas:**
```
openai.AuthenticationError: The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable
```

**Soluciones:**

1. **Verificar API Key**
```bash
# Verificar variable de entorno
echo $LLM_API_KEY

# Verificar formato (debe empezar con sk-)
echo $LLM_API_KEY | grep -E "^sk-"
```

2. **Configurar API Key correctamente**
```bash
# En .env
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-actual-api-key-here
```

3. **Verificar límites de uso**
```bash
# Verificar saldo en OpenAI
curl -H "Authorization: Bearer $LLM_API_KEY" \
  https://api.openai.com/v1/dashboard/billing/usage
```

### **Error: "rate limit exceeded"**

**Síntomas:**
```
openai.RateLimitError: Rate limit exceeded for default-gpt-4 in organization org-xxx on requests per min. Limit: 3 / min. Please try again in 20s.
```

**Soluciones:**

1. **Implementar retry con backoff**
```bash
# Aumentar max_retries en .env
LLM_MAX_RETRIES=5
LLM_TIMEOUT=120
```

2. **Usar modelo alternativo**
```bash
# Cambiar a modelo menos demandado
LLM_MODEL=gpt-3.5-turbo
```

3. **Verificar límites de cuenta**
```bash
# Verificar límites en dashboard de OpenAI
# https://platform.openai.com/account/rate-limits
```

### **Error: "model not found"**

**Síntomas:**
```
openai.BadRequestError: The model `gpt-5` does not exist
```

**Soluciones:**

1. **Verificar modelos disponibles**
```bash
# Listar modelos disponibles
curl -H "Authorization: Bearer $LLM_API_KEY" \
  https://api.openai.com/v1/models
```

2. **Usar modelo correcto**
```bash
# En .env
LLM_MODEL=gpt-4  # o gpt-3.5-turbo
```

### **Error: "context length exceeded"**

**Síntomas:**
```
openai.BadRequestError: This model's maximum context length is 4097 tokens. However, your messages resulted in 5000 tokens.
```

**Soluciones:**

1. **Reducir contexto**
```bash
# Ajustar parámetros en configuración
MAX_CONTEXT_LENGTH=3000
```

2. **Implementar truncamiento**
```python
# En el código, truncar mensajes largos
messages = truncate_messages(messages, max_tokens=3000)
```

## 🔍 Problemas de Vector Store

### **Error: "vector dimension mismatch"**

**Síntomas:**
```
ValueError: Vector dimension mismatch. Expected 1536, got 1024
```

**Soluciones:**

1. **Verificar dimensión de embeddings**
```bash
# En .env
VECTOR_DIMENSION=1536  # debe coincidir con el modelo de embeddings
EMBEDDING_MODEL=text-embedding-ada-002  # genera 1536 dimensiones
```

2. **Reindexar embeddings**
```bash
# Limpiar y reindexar
curl -X POST "http://localhost:8000/vector/reindex/1"
```

### **Error: "vector store connection failed"**

**Síntomas:**
```
ConnectionError: Failed to connect to vector store at https://api.pinecone.io
```

**Soluciones:**

1. **Verificar configuración de vector store**
```bash
# Verificar variables
echo $VECTOR_PROVIDER
echo $VECTOR_URL
echo $VECTOR_API_KEY
```

2. **Test de conexión manual**
```bash
# Para Pinecone
curl -H "Api-Key: $VECTOR_API_KEY" \
  https://api.pinecone.io/databases

# Para pgvector
psql "postgresql://user:pass@localhost:5432/vector_db" \
  -c "SELECT * FROM embeddings LIMIT 1;"
```

### **Error: "namespace not found"**

**Síntomas:**
```
ValueError: Namespace 'tenant_1_app_1_db_1_snapshot_1' not found
```

**Soluciones:**

1. **Verificar estrategia de namespace**
```bash
# En .env
VECTOR_NAMESPACE_STRATEGY=tenant_app_db_snapshot
```

2. **Crear namespace manualmente**
```bash
# Para Pinecone
curl -X POST "https://api.pinecone.io/databases" \
  -H "Api-Key: $VECTOR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "namespace_name"}'
```

## 💾 Problemas de Cache

### **Error: "Redis connection failed"**

**Síntomas:**
```
redis.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

**Soluciones:**

1. **Verificar que Redis esté ejecutándose**
```bash
# Linux/Mac
sudo systemctl status redis
sudo systemctl start redis

# Windows
net start redis

# Docker
docker run -d -p 6379:6379 redis:7-alpine
```

2. **Verificar configuración**
```bash
# Verificar CACHE_URL
echo $CACHE_URL

# Test de conexión
redis-cli ping
```

3. **Cambiar a Upstash (serverless)**
```bash
# En .env
CACHE_PROVIDER=upstash
CACHE_URL=https://your-instance.upstash.io
CACHE_API_KEY=your-upstash-api-key
```

### **Error: "cache key not found"**

**Síntomas:**
```
KeyError: Cache key 'schema:1' not found
```

**Soluciones:**

1. **Verificar TTL de cache**
```bash
# Aumentar TTL en configuración
CACHE_TTL=3600  # 1 hora
```

2. **Limpiar cache**
```bash
# Limpiar cache específico
curl -X DELETE "http://localhost:8000/cache/clear/schema:*"
```

3. **Verificar estrategia de cache**
```bash
# Verificar configuración de cache
curl http://localhost:8000/cache/info | jq '.'
```

## 🔧 Problemas de Embeddings

### **Error: "embedding model not found"**

**Síntomas:**
```
openai.BadRequestError: The model `text-embedding-ada-003` does not exist
```

**Soluciones:**

1. **Verificar modelo de embeddings**
```bash
# En .env
EMBEDDING_MODEL=text-embedding-ada-002  # modelo correcto
```

2. **Listar modelos disponibles**
```bash
# Para OpenAI
curl -H "Authorization: Bearer $EMBEDDING_API_KEY" \
  https://api.openai.com/v1/models | jq '.data[] | select(.id | contains("embedding"))'
```

### **Error: "embedding dimension mismatch"**

**Síntomas:**
```
ValueError: Expected embedding dimension 1536, got 1024
```

**Soluciones:**

1. **Verificar configuración de dimensiones**
```bash
# En .env
VECTOR_DIMENSION=1536  # para text-embedding-ada-002
EMBEDDING_MODEL=text-embedding-ada-002
```

2. **Reindexar embeddings**
```bash
# Limpiar embeddings existentes
curl -X POST "http://localhost:8000/vector/reindex/1"
```

## 📝 Problemas de Logging

### **Error: "log file not writable"**

**Síntomas:**
```
PermissionError: [Errno 13] Permission denied: 'logs/app.log'
```

**Soluciones:**

1. **Crear directorio de logs**
```bash
mkdir -p logs
chmod 755 logs
```

2. **Verificar permisos**
```bash
# Verificar permisos del directorio
ls -la logs/

# Cambiar permisos si es necesario
chmod 755 logs/
chown $USER:$USER logs/
```

3. **Usar logging a stdout**
```bash
# En .env
LOG_FILE=""  # vacío para stdout
```

### **Error: "log format not supported"**

**Síntomas:**
```
ValueError: Log format 'xml' not supported
```

**Soluciones:**

1. **Usar formato soportado**
```bash
# En .env
LOG_FORMAT=json  # o text
```

2. **Verificar configuración**
```bash
# Verificar variable
echo $LOG_FORMAT
```

## 🛡️ Problemas de Seguridad

### **Error: "SQL injection detected"**

**Síntomas:**
```
SecurityError: Potential SQL injection detected in query
```

**Soluciones:**

1. **Verificar políticas SQL**
```bash
# En .env
SQL_READ_ONLY=true
SQL_MAX_ROWS=1000
SQL_TIMEOUT_SECONDS=30
```

2. **Revisar consulta generada**
```bash
# Verificar logs para ver la consulta
grep "SQL" logs/app.log | jq '.'
```

### **Error: "schema not allowed"**

**Síntomas:**
```
SecurityError: Schema 'private' not in allowed schemas
```

**Soluciones:**

1. **Configurar schemas permitidos**
```bash
# En .env
SQL_ALLOWED_SCHEMAS=public,sales,hr
```

2. **Verificar permisos de usuario**
```sql
-- Conectar a PostgreSQL
GRANT USAGE ON SCHEMA public TO apichat_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO apichat_user;
```

## 🚀 Problemas de Performance

### **Error: "request timeout"**

**Síntomas:**
```
TimeoutError: Request timed out after 60 seconds
```

**Soluciones:**

1. **Aumentar timeouts**
```bash
# En .env
LLM_TIMEOUT=120
SQL_TIMEOUT_SECONDS=60
VECTOR_TIMEOUT=60
```

2. **Optimizar consultas**
```bash
# Reducir batch size
BATCH_SIZE_EMBEDDINGS=50
VECTOR_BATCH_SIZE=50
```

3. **Implementar caching**
```bash
# Habilitar cache agresivo
CACHE_TTL=7200  # 2 horas
```

### **Error: "memory exceeded"**

**Síntomas:**
```
MemoryError: Unable to allocate memory for large batch
```

**Soluciones:**

1. **Reducir batch sizes**
```bash
# En .env
BATCH_SIZE_EMBEDDINGS=25
VECTOR_BATCH_SIZE=25
CACHE_BATCH_SIZE=50
```

2. **Optimizar procesamiento**
```bash
# Procesar en chunks más pequeños
CHUNK_SIZE=1000
```

## 🐳 Problemas de Docker

### **Error: "container not found"**

**Síntomas:**
```
Error: No such container: apichat-backend
```

**Soluciones:**

1. **Verificar contenedores**
```bash
# Listar contenedores
docker ps -a

# Verificar docker-compose
docker-compose ps
```

2. **Recrear contenedores**
```bash
# Recrear servicios
docker-compose down
docker-compose up -d
```

### **Error: "port already in use"**

**Síntomas:**
```
Error: Port 8000 is already in use
```

**Soluciones:**

1. **Verificar puertos en uso**
```bash
# Verificar qué usa el puerto
netstat -tulpn | grep :8000
lsof -i :8000
```

2. **Cambiar puerto**
```bash
# En docker-compose.yml
ports:
  - "8001:8000"  # cambiar puerto externo
```

### **Error: "volume not found"**

**Síntomas:**
```
Error: No such volume: apichat_postgres_data
```

**Soluciones:**

1. **Crear volumen**
```bash
# Crear volumen manualmente
docker volume create apichat_postgres_data
```

2. **Verificar volúmenes**
```bash
# Listar volúmenes
docker volume ls

# Verificar docker-compose
docker-compose config
```

## 📞 Soporte

### **Recopilar Información de Debug**

```bash
# Script de diagnóstico completo
cat > debug.sh << 'EOF'
#!/bin/bash
echo "=== DIAGNÓSTICO API CHAT BACKEND ==="
echo "Fecha: $(date)"
echo "Sistema: $(uname -a)"
echo "Python: $(python --version)"
echo "Docker: $(docker --version 2>/dev/null || echo 'No instalado')"

echo -e "\n=== VARIABLES DE ENTORNO ==="
env | grep -E "(LLM_|DATABASE_|CACHE_|VECTOR_|EMBEDDING_)" | sort

echo -e "\n=== HEALTH CHECK ==="
curl -s http://localhost:8000/health | jq '.' 2>/dev/null || echo "Health check falló"

echo -e "\n=== MÉTRICAS ==="
curl -s http://localhost:8000/metrics | jq '.' 2>/dev/null || echo "Métricas no disponibles"

echo -e "\n=== LOGS RECIENTES ==="
tail -n 20 logs/app.log 2>/dev/null || echo "Logs no disponibles"

echo -e "\n=== PUERTOS EN USO ==="
netstat -tulpn | grep -E ":(8000|5432|6379)" || echo "Puertos no encontrados"
EOF

chmod +x debug.sh
./debug.sh > debug_report.txt
```

### **Contactar Soporte**

1. **Crear issue en GitHub**
   - Incluir archivo `debug_report.txt`
   - Describir pasos para reproducir el problema
   - Incluir logs relevantes

2. **Información necesaria**
   - Versión de Python
   - Sistema operativo
   - Configuración de variables de entorno
   - Logs de error completos
   - Pasos para reproducir el problema

---

## 📚 Referencias Adicionales

- [README Principal](../README.md)
- [Variables de Entorno](ENVIRONMENT_VARIABLES.md)
- [API Documentation](API.md)
- [GitHub Issues](https://github.com/tu-usuario/apichat-backend/issues)
