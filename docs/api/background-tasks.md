# 🔄 Background Tasks API

## 📋 Resumen

La API de Background Tasks permite gestionar tareas en segundo plano de forma asíncrona, con soporte para prioridades, retry logic y monitoring en tiempo real.

## 🎯 Endpoints Disponibles

### POST `/background-tasks/submit`
Envía una nueva tarea al sistema de background processing.

**Request Body:**
```json
{
  "task_type": "data_processing",
  "payload": {
    "data": "test_data",
    "options": {
      "batch_size": 1000,
      "parallel": true
    }
  },
  "priority": "HIGH"
}
```

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "message": "Task submitted successfully"
}
```

### GET `/background-tasks/{task_id}/status`
Obtiene el estado actual de una tarea.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "progress": 45.5,
  "started_at": "2024-01-15T10:30:00Z",
  "estimated_completion": "2024-01-15T10:35:00Z",
  "result": null,
  "error": null
}
```

### DELETE `/background-tasks/{task_id}/cancel`
Cancela una tarea en ejecución.

**Response:**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "CANCELLED",
  "message": "Task cancelled successfully"
}
```

### GET `/background-tasks/stats`
Obtiene estadísticas del sistema de background tasks.

**Response:**
```json
{
  "total_tasks": 150,
  "pending_tasks": 5,
  "running_tasks": 3,
  "completed_tasks": 140,
  "failed_tasks": 2,
  "average_completion_time": 45.2,
  "success_rate": 98.7
}
```

### GET `/background-tasks/task-types`
Obtiene información sobre los tipos de tareas disponibles.

**Response:**
```json
{
  "task_types": [
    {
      "name": "data_processing",
      "description": "Procesamiento de datos en lote",
      "max_duration": 3600,
      "retry_policy": "exponential_backoff",
      "priority_levels": ["LOW", "NORMAL", "HIGH"]
    },
    {
      "name": "report_generation",
      "description": "Generación de reportes",
      "max_duration": 1800,
      "retry_policy": "linear_backoff",
      "priority_levels": ["NORMAL", "HIGH"]
    },
    {
      "name": "cache_update",
      "description": "Actualización de cache",
      "max_duration": 300,
      "retry_policy": "immediate",
      "priority_levels": ["LOW", "NORMAL"]
    }
  ]
}
```

## 🔧 Tipos de Tareas

### Data Processing
Procesamiento de datos en lote con soporte para paralelización.

**Payload Example:**
```json
{
  "data_source": "users_table",
  "filters": {
    "active": true,
    "created_after": "2024-01-01"
  },
  "operations": [
    "clean_data",
    "calculate_metrics",
    "generate_summary"
  ],
  "output_format": "json"
}
```

### Report Generation
Generación de reportes complejos con múltiples fuentes de datos.

**Payload Example:**
```json
{
  "report_type": "sales_summary",
  "date_range": {
    "start": "2024-01-01",
    "end": "2024-01-31"
  },
  "filters": {
    "region": "EU",
    "product_category": "electronics"
  },
  "output_formats": ["pdf", "excel", "json"]
}
```

### Cache Update
Actualización de cache con invalidación inteligente.

**Payload Example:**
```json
{
  "cache_type": "schema_cache",
  "tables": ["users", "orders", "products"],
  "invalidation_strategy": "selective",
  "preload_data": true
}
```

## 🎯 Prioridades

### LOW
- Tareas no críticas
- Procesamiento en tiempo libre
- Cache updates

### NORMAL
- Tareas estándar
- Report generation
- Data processing

### HIGH
- Tareas críticas
- Time-sensitive operations
- User-requested tasks

## 🔄 Estados de Tareas

### PENDING
Tarea en cola esperando ejecución.

### RUNNING
Tarea en ejecución actualmente.

### COMPLETED
Tarea completada exitosamente.

### FAILED
Tarea falló después de todos los reintentos.

### CANCELLED
Tarea cancelada por el usuario.

## 🛠️ Configuración

### Retry Policies

#### Exponential Backoff
```python
retry_delay = base_delay * (2 ** retry_count)
```

#### Linear Backoff
```python
retry_delay = base_delay * retry_count
```

#### Immediate
```python
retry_delay = 0
```

### Timeouts
- **Default timeout**: 3600 segundos (1 hora)
- **Max retries**: 3 intentos
- **Retry delay**: 5-60 segundos

## 📊 Monitoring

### Métricas Disponibles
- **Task completion rate**
- **Average execution time**
- **Error rate**
- **Queue length**
- **Worker utilization**

### Logs
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "level": "INFO",
  "message": "Task started processing",
  "metadata": {
    "task_type": "data_processing",
    "priority": "HIGH",
    "worker_id": "worker-1"
  }
}
```

## 🚀 Ejemplos de Uso

### Python Client
```python
import requests

# Enviar tarea
response = requests.post(
    "http://localhost:8000/background-tasks/submit",
    json={
        "task_type": "data_processing",
        "payload": {"data": "test"},
        "priority": "HIGH"
    }
)
task_id = response.json()["task_id"]

# Monitorear progreso
while True:
    status = requests.get(f"http://localhost:8000/background-tasks/{task_id}/status")
    if status.json()["status"] == "COMPLETED":
        break
    time.sleep(5)
```

### cURL
```bash
# Enviar tarea
curl -X POST http://localhost:8000/background-tasks/submit \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "report_generation",
    "payload": {
      "report_type": "sales_summary",
      "date_range": {
        "start": "2024-01-01",
        "end": "2024-01-31"
      }
    },
    "priority": "NORMAL"
  }'

# Verificar estado
curl http://localhost:8000/background-tasks/{task_id}/status
```

## 🔍 Troubleshooting

### Tareas que Fallan
1. **Verificar logs** para errores específicos
2. **Revisar payload** para datos inválidos
3. **Comprobar timeouts** y límites de recursos
4. **Validar permisos** y acceso a recursos

### Performance Issues
1. **Monitorizar queue length**
2. **Ajustar worker count**
3. **Optimizar task payloads**
4. **Revisar resource limits**

---

## 🎉 Conclusión

La API de Background Tasks proporciona:

- ✅ **Procesamiento asíncrono** robusto
- ✅ **Gestión de prioridades** inteligente
- ✅ **Retry logic** automático
- ✅ **Monitoring** en tiempo real
- ✅ **Escalabilidad** horizontal

**¡Sistema listo para producción!** 🚀
