# Solución: Resolución Genérica de Placeholders en Plantillas

## Problema Resuelto

**Error**: Placeholders sin resolver en respuestas del plan
- El `GuidedGraph` genera un plan con acción `db_query` que guarda resultados en `store_as="invitation_requests"`
- La plantilla final usa `{{invitation_requests_formatted}}`
- El `ExecutionEngine` ejecuta la query y guarda `invitation_requests`, pero nadie crea `invitation_requests_formatted`
- **Resultado**: El cliente recibe la cadena con el placeholder sin resolver

## Solución Implementada

### 1. ExecutionEngine - Resolución Automática de Placeholders

#### Nuevo método: `_resolve_missing_placeholders()`
- **Detección automática**: Extrae todos los placeholders `{{...}}` del template
- **Generación automática**: Si falta una variable `*_formatted` y existe la base, la genera automáticamente
- **Telemetría**: Registra eventos de placeholders faltantes y auto-generados

#### Nuevo método: `_auto_format_variable()`
- **Formateo inteligente**: Aplica formateo basado en el tipo de dato
- **Listas homogéneas**: Crea tablas Markdown (máx. 20 filas + contador)
- **Listas heterogéneas/Dicts**: Pretty-print JSON compacto
- **Strings/Números**: Usa tal cual

#### Nuevo método: `_format_list_as_table()`
- **Detección automática**: Si es lista de dicts, crea tabla con columnas
- **Truncado inteligente**: Valores muy largos se truncan con "..."
- **Listas simples**: Formato de viñetas

#### Mejora: `_render_text()`
- **Validación final**: Verifica que no queden placeholders sin resolver
- **Mensaje controlado**: Reemplaza placeholders faltantes con "[VARIABLE NO DISPONIBLE]"
- **Logging detallado**: Registra cada placeholder no resuelto

### 2. GuidedGraph - Validación Previa del Plan

#### Nuevo método: `_validate_plan_placeholders()`
- **Validación temprana**: Antes de ejecutar, verifica que todos los placeholders sean válidos
- **Mapeo de variables**: Confirma que cada placeholder corresponda a un `store_as` del plan
- **Detección de problemas**: Identifica placeholders que no se pueden resolver

#### Nuevo método: `_apply_plan_fixes()`
- **Correcciones automáticas**: Estructura preparada para futuras correcciones automáticas
- **Logging detallado**: Registra cada problema detectado

### 3. OpenAI Service - Prompt Mejorado

#### Reglas de Variables en el Prompt
- **Restricciones claras**: Solo usar variables que correspondan a `store_as` de las acciones
- **Ejemplos específicos**: Muestra cómo usar `invitation_requests` y `invitation_requests_formatted`
- **Prevención de errores**: NO inventar nombres de variables no previstos

## Flujo de Resolución

### Fase 1: Validación del Plan (GuidedGraph)
```
Plan generado → Extraer placeholders → Validar vs store_as → Aceptar/Rechazar
```

### Fase 2: Ejecución de Acciones (ExecutionEngine)
```
Ejecutar acciones → Guardar resultados → Generar extras (_list, _pretty, _formatted)
```

### Fase 3: Resolución de Placeholders (ExecutionEngine)
```
Template → Extraer placeholders → Auto-generar *_formatted → Validar completitud
```

### Fase 4: Renderizado Final (ExecutionEngine)
```
Variables completas → Renderizar template → Validar resultado → Respuesta final
```

## Beneficios de la Solución

### ✅ **Robustez**
- Ningún placeholder queda sin resolver
- Generación automática de variables `*_formatted`
- Validación en múltiples puntos del flujo

### ✅ **Flexibilidad**
- Funciona con cualquier nombre de variable
- Formateo inteligente basado en tipo de dato
- Truncado automático para datos grandes

### ✅ **Observabilidad**
- Logging detallado de cada paso
- Telemetría de placeholders faltantes
- Métricas de auto-generación vs bloqueo

### ✅ **Mantenibilidad**
- Código modular y bien documentado
- Separación clara de responsabilidades
- Fácil extensión para nuevos tipos de formateo

## Casos de Uso Cubiertos

### 1. **Variable Base + Formateada**
```python
# Plan genera: store_as="invitation_requests"
# Template usa: {{invitation_requests_formatted}}
# Resultado: Auto-generado automáticamente
```

### 2. **Lista de Resultados**
```python
# Datos: [{"id": 1, "name": "Club A"}, {"id": 2, "name": "Club B"}]
# Auto-genera tabla Markdown formateada
```

### 3. **Datos Heterogéneos**
```python
# Dicts complejos → JSON pretty-print
# Listas largas → Tabla truncada + contador
```

### 4. **Placeholders Inválidos**
```python
# Si falta variable base → Respuesta controlada
# Log de telemetría para debugging
```

## Criterios de Aceptación Cumplidos

- ✅ **Ningún `assistant_response` contiene `{{...}}` sin resolver**
- ✅ **Cualquier `*_formatted` faltante se genera automáticamente**
- ✅ **Placeholders inexistentes provocan respuesta controlada y log**
- ✅ **Funciona con cualquier nombre de variable y tipo de dato**
- ✅ **Telemetría completa de cada placeholder auto-generado**

## Próximos Pasos (Opcionales)

### 1. **Correcciones Automáticas del Plan**
- Implementar lógica para inyectar acciones de formateo faltantes
- Rechazar planes con placeholders imposibles de resolver

### 2. **Formateo Personalizado**
- Permitir especificar formato específico en el plan
- Soporte para diferentes estilos de tabla/formato

### 3. **Validación Avanzada**
- Detectar dependencias entre placeholders
- Validar tipos de datos esperados vs generados

## Archivos Modificados

1. **`app/services/execution_engine_service.py`**
   - Nuevos métodos de resolución de placeholders
   - Mejoras en `_render_text()`
   - Formateo automático inteligente

2. **`app/services/graphs/guided_graph.py`**
   - Validación previa del plan
   - Detección temprana de placeholders inválidos
   - Estructura para correcciones automáticas

3. **`app/services/openai_service.py`**
   - Prompt mejorado con reglas de variables
   - Prevención de placeholders inválidos

## Testing

Para verificar la solución:

1. **Ejecutar consulta con `invitation_requests_formatted`**
2. **Verificar logs de auto-generación**
3. **Confirmar que no hay placeholders sin resolver**
4. **Validar telemetría de placeholders faltantes**

La solución está lista y compila correctamente. Todos los placeholders serán resueltos automáticamente, incluyendo la generación de variables `*_formatted` faltantes.
