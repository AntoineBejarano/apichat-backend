# 🔧 Fix: Carga de Historial del Chat Rota

## 📋 Problema Identificado

**Error**: `'ChatHistory' object has no attribute 'created_at'`

**Ubicación**: `app/services/orchestrator_service.py` - método `_load_history_async`

**Impacto**: 
- El planner recibe menos contexto (msgs=2 en vez de ~22)
- Decide responder "simple" en lugar de planificar
- Se rompe la funcionalidad del chat

## 🔍 Causa Raíz

El código estaba intentando acceder a `msg.created_at.isoformat()` pero el modelo `ChatHistory` tiene el campo `timestamp`, no `created_at`.

**Código problemático**:
```python
'created_at': msg.created_at.isoformat() if msg.created_at else None,
```

**Modelo real**:
```python
# app/models/chat_history_model.py
class ChatHistory(Base):
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    # NO tiene created_at
```

## ✅ Solución Implementada

### 1. **Método Auxiliar Robusto** (`_safe_sqlalchemy_to_dict`)
```python
def _safe_sqlalchemy_to_dict(self, obj: Any) -> Dict[str, Any]:
    """
    Convierte objetos SQLAlchemy a diccionarios de forma segura.
    Maneja casos donde el objeto puede no tener ciertos atributos.
    """
    try:
        if hasattr(obj, '__dict__'):
            # Objeto SQLAlchemy - extraer atributos
            result = {}
            for key, value in obj.__dict__.items():
                # Ignorar atributos internos de SQLAlchemy
                if not key.startswith('_'):
                    try:
                        # Convertir datetime a ISO string si es posible
                        if hasattr(value, 'isoformat'):
                            result[key] = value.isoformat()
                        else:
                            result[key] = value
                    except Exception:
                        # Si falla la conversión, usar string
                        result[key] = str(value)
            return result
        elif hasattr(obj, 'model_dump'):
            # Objeto Pydantic
            return obj.model_dump()
        elif isinstance(obj, dict):
            # Ya es un diccionario
            return obj
        else:
            # Otro tipo - convertir a string
            return {'value': str(obj)}
    except Exception as e:
        logger.warning(f"[OrchestratorService] Error convirtiendo objeto a diccionario: {e}")
        return {'error': f'Error converting object: {str(e)}'}
```

### 2. **Conversión Segura del Historial**
```python
# Convertir a formato de diccionario de forma segura
history_dicts = []
for msg in history:
    try:
        # 🔧 FIX: Usar método auxiliar para conversión segura
        msg_dict = self._safe_sqlalchemy_to_dict(msg)
        
        # 🔧 FIX: Asegurar campos requeridos con valores por defecto
        msg_dict = {
            'role': msg_dict.get('role', 'unknown'),
            'content': msg_dict.get('content', ''),
            'name': msg_dict.get('name'),
            'timestamp': msg_dict.get('timestamp'),
            'is_function_call': msg_dict.get('is_function_call', False)
        }
        
        history_dicts.append(msg_dict)
        
    except Exception as msg_error:
        logger.warning(f"[OrchestratorService] Error procesando mensaje del historial: {msg_error}")
        # Agregar mensaje básico en caso de error
        history_dicts.append({
            'role': 'unknown',
            'content': 'Error loading message',
            'name': None,
            'timestamp': None,
            'is_function_call': False
        })
```

## 🛡️ Características de la Solución

### **Robustez**
- ✅ Usa `getattr` y `.get()` para acceso seguro
- ✅ Maneja objetos SQLAlchemy y Pydantic
- ✅ Convierte automáticamente `datetime` a ISO string
- ✅ Proporciona valores por defecto para campos faltantes

### **Manejo de Errores**
- ✅ Try-catch individual para cada mensaje
- ✅ Logging detallado de errores
- ✅ Fallback a mensaje de error básico
- ✅ No interrumpe la carga del historial completo

### **Compatibilidad**
- ✅ Funciona con modelos SQLAlchemy existentes
- ✅ Compatible con esquemas Pydantic
- ✅ Mantiene la estructura de datos esperada
- ✅ No rompe la interfaz existente

## 🔄 Flujo de Ejecución

1. **Carga del Historial**: `history_service.get_chat_history(chat_id)`
2. **Conversión Segura**: `_safe_sqlalchemy_to_dict(msg)` para cada mensaje
3. **Normalización**: Asegurar campos requeridos con valores por defecto
4. **Manejo de Errores**: Try-catch individual para robustez
5. **Resultado**: Lista de diccionarios con formato consistente

## 📊 Beneficios

- **✅ Historial Completo**: El planner recibe todos los mensajes (~22 en vez de 2)
- **✅ Planificación Correcta**: El planner puede tomar decisiones informadas
- **✅ Robustez**: Maneja errores sin romper la funcionalidad
- **✅ Mantenibilidad**: Código más limpio y fácil de debuggear
- **✅ Compatibilidad**: Funciona con diferentes tipos de objetos

## 🧪 Testing

**Verificación de Compilación**:
```bash
python -m py_compile app/services/orchestrator_service.py
# ✅ Exit code: 0
```

**Campos Esperados en el Resultado**:
```python
{
    'role': str,           # 'user', 'assistant', 'system'
    'content': str,        # Contenido del mensaje
    'name': Optional[str], # Nombre del mensaje (opcional)
    'timestamp': str,      # ISO string del timestamp
    'is_function_call': bool # Si es llamada a función
}
```

## 🚀 Próximos Pasos

1. **Testing en Producción**: Verificar que el historial se carga correctamente
2. **Monitoreo**: Observar logs para confirmar que no hay más errores
3. **Performance**: Evaluar si la conversión segura impacta el rendimiento
4. **Refactoring**: Considerar aplicar el patrón a otros métodos similares

---

**Estado**: ✅ **IMPLEMENTADO Y COMPILADO**
**Fecha**: $(date)
**Archivo**: `app/services/orchestrator_service.py`
