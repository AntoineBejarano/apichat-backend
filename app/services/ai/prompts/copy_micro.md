# Micro-Copy Estándar para Respuestas UX
> Plantillas de texto consistentes para respuestas del sistema en modo Explorer y Guided.

## 🎯 Objetivos
- **Consistencia**: Mismo tono y estructura en todas las respuestas
- **Claridad**: Mensajes fáciles de entender y procesar
- **Accionabilidad**: Siempre sugerir próximos pasos claros
- **Brevedad**: Máximo 3 bullets por sección

---

## 🔍 Modo Explorer - Plantillas

### Cabecera
```
🔍 **Reporte de Exploración**
```

### Hallazgos principales
```
**Hallazgos principales:**
• [Descripción del hallazgo 1]
• [Descripción del hallazgo 2] 
• [Descripción del hallazgo 3]
```

### Fuentes
```
**Fuentes:**
• [Nombre de la fuente 1]
• [Nombre de la fuente 2]
```

### Uso
```
**Uso:**
• Tokens: [número]
• Tiempo: [X.XX]s
```

### Siguientes acciones
```
**Siguientes acciones:**
• [Acción sugerida 1]
• [Acción sugerida 2]
• [Acción sugerida 3]
```

---

## 🎯 Modo Guided - Plantillas

### Cabecera
```
🎯 **Ejecución Guiada Completada**
```

### Plan
```
**Plan:** [Título del plan]
[Descripción del plan si está disponible]
```

### Resultados
```
**Resultados:**
• ✅ [X] pasos completados exitosamente
• ❌ [X] pasos fallaron
• [Descripción del paso 1]
• [Descripción del paso 2]
```

### Auditoría
```
**ID de Auditoría:** [audit_id]
```

### Uso
```
**Uso:**
• Tokens: [número]
• Tiempo total: [X.XX]s
• Costo estimado: [costo]
```

### Siguientes acciones
```
**Siguientes acciones:**
• [Acción sugerida 1]
• [Acción sugerida 2]
• [Acción sugerida 3]
```

---

## 📝 Reglas de Micro-Copy

### Estructura
1. **Cabecera clara** con emoji y título
2. **Máximo 3 bullets** por sección
3. **Secciones separadas** con líneas en blanco
4. **Acciones al final** para orientar al usuario

### Tono
- **Amigable pero profesional**
- **Directo y claro**
- **Siempre constructivo**
- **Evitar jerga técnica innecesaria**

### Formato
- **Markdown básico** para estructura
- **Emojis** para identificación visual rápida
- **Bullets** para listas
- **Negritas** para títulos de sección

---

## 🔧 Casos de Uso

### Sin resultados
```
🔍 **Reporte de Exploración**

**Hallazgos principales:**
• No se encontraron resultados para tu consulta

**Siguientes acciones:**
• Reformula tu pregunta con términos más específicos
• Verifica que los recursos estén disponibles
• Contacta al administrador del sistema
```

### Con errores
```
🎯 **Ejecución Guiada Completada**

**Resultados:**
• ❌ 1 paso falló
• [Descripción del error]

**Siguientes acciones:**
• Revisa los parámetros de entrada
• Verifica permisos de acceso
• Intenta con una consulta más simple
```

### Éxito completo
```
🎯 **Ejecución Guiada Completada**

**Resultados:**
• ✅ 2 pasos completados exitosamente
• Consulta ejecutada correctamente
• Datos procesados y formateados

**Uso:**
• Tokens: 150
• Tiempo total: 2.34s

**Siguientes acciones:**
• Exporta los resultados
• Guarda la consulta para uso futuro
• Comparte con tu equipo
```
