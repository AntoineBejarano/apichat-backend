# 🔧 Fix: Métodos de Servicios Incorrectos

## Problema Identificado

Se detectaron dos errores críticos en el `OrchestratorService` relacionados con llamadas a métodos inexistentes:

### 1. UsageService: Método Incorrecto

**Evidencia:**
```
'UsageService' object has no attribute 'check_usage_limit'
```

**Ubicación:** `app/services/orchestrator_service.py:368`

**Impacto:** 
- Ruido en logs de errores
- Posible salto de límites de uso
- Fallo en la verificación de límites

**Causa:** Se estaba llamando al método `check_usage_limit()` que no existe en `UsageService`.

**Solución:** Cambiar a `check_limit()` que es el método real.

### 2. ServiceFactory: Nombre de Servicio Incorrecto

**Evidencia:**
```
ServiceFactory ... has no attribute 'get_app_service'. Did you mean: 'get_apps_service'?
```

**Ubicación:** `app/services/orchestrator_service.py:932`

**Impacto:**
- No se cargan apps/funciones candidatas
- Flows que requieren apps fallan
- Contexto incompleto para el planner

**Causa:** Se estaba llamando al método `get_app_service()` que no existe en `ServiceFactory`.

**Solución:** Cambiar a `get_apps_service()` que es el método correcto.

## Correcciones Implementadas

### Archivo: `app/services/orchestrator_service.py`

#### Línea 368: Método de verificación de límites
```python
# ANTES (INCORRECTO):
usage_ok = usage_service.check_usage_limit(self.user_id)

# DESPUÉS (CORRECTO):
usage_ok = usage_service.check_limit()
```

#### Línea 932: Método de obtención de servicio de apps
```python
# ANTES (INCORRECTO):
app_service = temp_factory.get_app_service()

# DESPUÉS (CORRECTO):
app_service = temp_factory.get_apps_service()
```

## Verificación

- ✅ Archivo compila sin errores
- ✅ Métodos corregidos apuntan a implementaciones reales
- ✅ Funcionalidad de límites de uso restaurada
- ✅ Carga de aplicaciones restaurada

## Métodos Correctos Verificados

### UsageService
- **Método real:** `check_limit()`
- **Ubicación:** `app/services/usage_service.py:144`
- **Propósito:** Verificar límites de uso del usuario

### ServiceFactory
- **Método real:** `get_apps_service()`
- **Ubicación:** `app/core/service_factory.py:270`
- **Propósito:** Obtener instancia del servicio de aplicaciones

## Impacto de la Corrección

1. **Eliminación de errores:** No más `AttributeError` en logs
2. **Funcionalidad restaurada:** Verificación de límites y carga de apps funcionan correctamente
3. **Contexto completo:** El planner recibe toda la información necesaria
4. **Estabilidad:** Flows que dependen de apps funcionan correctamente

## Prevención Futura

Para evitar errores similares:

1. **Verificar métodos:** Siempre confirmar que los métodos llamados existen en las clases
2. **Usar autocompletado:** Aprovechar el autocompletado del IDE para métodos
3. **Tests unitarios:** Implementar tests que verifiquen la existencia de métodos
4. **Documentación:** Mantener documentación actualizada de las APIs de servicios
