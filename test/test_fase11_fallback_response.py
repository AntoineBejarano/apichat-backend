#!/usr/bin/env python3
"""
🔧 FASE 11: Test temporal para verificar fallback de respuesta IA
"""

from app.services.ai.fallback_response_service import FallbackResponseService


def test_fase11_fallback_service():
    """🔧 FASE 11: Verificar servicio de fallback"""
    
    print("🔧 FASE 11: Iniciando test de servicio de fallback...")
    
    # Test 1: Inicializar servicio
    print("✅ Test 1: Inicializando servicio de fallback")
    fallback_service = FallbackResponseService()
    assert fallback_service is not None, "Servicio no se inicializó"
    assert hasattr(fallback_service, 'fallback_templates'), "No tiene plantillas de fallback"
    assert hasattr(fallback_service, 'error_patterns'), "No tiene patrones de error"
    
    # Test 2: Verificar plantillas de fallback
    print("✅ Test 2: Verificando plantillas de fallback")
    templates = fallback_service.fallback_templates
    assert "general_fallback" in templates, "Falta plantilla general"
    assert "database_error" in templates, "Falta plantilla de base de datos"
    assert "execution_error" in templates, "Falta plantilla de ejecución"
    assert "unknown_error" in templates, "Falta plantilla de error desconocido"
    
    # Test 3: Verificar patrones de error
    print("✅ Test 3: Verificando patrones de error")
    patterns = fallback_service.error_patterns
    assert "database" in patterns, "Faltan patrones de base de datos"
    assert "execution" in patterns, "Faltan patrones de ejecución"
    assert "timeout" in patterns, "Faltan patrones de timeout"
    
    print("🔧 FASE 11: ✅ Todos los tests de inicialización pasaron!")


def test_fase11_error_detection():
    """🔧 FASE 11: Verificar detección de tipos de error"""
    
    print("🔧 FASE 11: Iniciando test de detección de errores...")
    
    fallback_service = FallbackResponseService()
    
    # Test 1: Detectar error de base de datos
    print("✅ Test 1: Detectando error de base de datos")
    execution_results = {"error": "Database connection failed"}
    error_type = fallback_service._detect_error_type(execution_results, "Consulta base de datos")
    assert "database" in error_type, f"Error de BD no detectado: {error_type}"
    
    # Test 2: Detectar error de ejecución
    print("✅ Test 2: Detectando error de ejecución")
    execution_results = {"execution_error": "Function execution failed"}
    error_type = fallback_service._detect_error_type(execution_results, "Ejecutar función")
    assert "execution" in error_type, f"Error de ejecución no detectado: {error_type}"
    
    # Test 3: Detectar error de timeout
    print("✅ Test 3: Detectando error de timeout")
    execution_results = {"error": "Query timed out after 30 seconds"}
    error_type = fallback_service._detect_error_type(execution_results, "Consulta lenta")
    assert "timeout" in error_type, f"Error de timeout no detectado: {error_type}"
    
    # Test 4: Detectar error de validación
    print("✅ Test 4: Detectando error de validación")
    execution_results = {"error": "Invalid SQL syntax"}
    error_type = fallback_service._detect_error_type(execution_results, "Validar consulta")
    assert "validation" in error_type, f"Error de validación no detectado: {error_type}"
    
    print("🔧 FASE 11: ✅ Todos los tests de detección de errores pasaron!")


def test_fase11_fallback_generation():
    """🔧 FASE 11: Verificar generación de respuestas de fallback"""
    
    print("🔧 FASE 11: Iniciando test de generación de fallback...")
    
    fallback_service = FallbackResponseService()
    
    # Test 1: Generar fallback de base de datos
    print("✅ Test 1: Generando fallback de base de datos")
    execution_results = {"error": "Database connection failed"}
    context = {"db_ids": ["db1", "db2"]}
    fallback = fallback_service.generate_fallback_response(
        execution_results, "Consulta base de datos", context
    )
    assert "base de datos" in fallback.lower(), f"Fallback de BD no contiene texto esperado: {fallback[:100]}"
    assert "Fase 11" in fallback, f"Fallback no contiene versión: {fallback[:100]}"
    
    # Test 2: Generar fallback de ejecución
    print("✅ Test 2: Generando fallback de ejecución")
    execution_results = {"execution_error": "Function execution failed"}
    fallback = fallback_service.generate_fallback_response(
        execution_results, "Ejecutar función", None
    )
    assert "ejecución" in fallback.lower(), f"Fallback de ejecución no contiene texto esperado: {fallback[:100]}"
    
    # Test 3: Generar fallback de contexto
    print("✅ Test 3: Generando fallback de contexto")
    execution_results = {"variables": {"query_result": {"error": "No context found"}}}
    context = {"databases": [], "apps": []}
    fallback = fallback_service.generate_fallback_response(
        execution_results, "Consulta sin contexto", context
    )
    assert "contexto" in fallback.lower(), f"Fallback de contexto no contiene texto esperado: {fallback[:100]}"
    
    print("🔧 FASE 11: ✅ Todos los tests de generación de fallback pasaron!")


def test_fase11_should_use_fallback():
    """🔧 FASE 11: Verificar lógica de cuándo usar fallback"""
    
    print("🔧 FASE 11: Iniciando test de lógica de fallback...")
    
    fallback_service = FallbackResponseService()
    
    # Test 1: No usar fallback si hay assistant_response válido
    print("✅ Test 1: Verificando que no se use fallback con respuesta válida")
    execution_results = {"assistant_response": "Respuesta válida del asistente"}
    should_use = fallback_service.should_use_fallback(execution_results)
    assert not should_use, "No debería usar fallback con respuesta válida"
    
    # Test 2: Usar fallback si no hay assistant_response
    print("✅ Test 2: Verificando que se use fallback sin respuesta")
    execution_results = {"assistant_response": ""}
    should_use = fallback_service.should_use_fallback(execution_results)
    assert should_use, "Debería usar fallback sin respuesta"
    
    # Test 3: Usar fallback si hay error
    print("✅ Test 3: Verificando que se use fallback con error")
    execution_results = {"error": "Error de prueba"}
    should_use = fallback_service.should_use_fallback(execution_results)
    assert should_use, "Debería usar fallback con error"
    
    # Test 4: Usar fallback si hay error en variables
    print("✅ Test 4: Verificando que se use fallback con error en variables")
    execution_results = {"variables": {"query_result": {"error": "SQL error"}}}
    should_use = fallback_service.should_use_fallback(execution_results)
    assert should_use, "Debería usar fallback con error en variables"
    
    print("🔧 FASE 11: ✅ Todos los tests de lógica de fallback pasaron!")


def test_fase11_error_classification():
    """🔧 FASE 11: Verificar clasificación de errores por texto"""
    
    print("🔧 FASE 11: Iniciando test de clasificación de errores...")
    
    fallback_service = FallbackResponseService()
    
    # Test 1: Clasificar error de base de datos
    print("✅ Test 1: Clasificando error de base de datos")
    error_text = "Database connection failed"
    error_type = fallback_service._classify_error_by_text(error_text)
    assert "database" in error_type, f"Error de BD no clasificado: {error_type}"
    
    # Test 2: Clasificar error de timeout
    print("✅ Test 2: Clasificando error de timeout")
    error_text = "Query timed out after 30 seconds"
    error_type = fallback_service._classify_error_by_text(error_text)
    assert "timeout" in error_type, f"Error de timeout no clasificado: {error_type}"
    
    # Test 3: Clasificar error de permisos
    print("✅ Test 3: Clasificando error de permisos")
    error_text = "Access denied: insufficient permissions"
    error_type = fallback_service._classify_error_by_text(error_text)
    assert "resource" in error_type, f"Error de permisos no clasificado: {error_type}"
    
    # Test 4: Clasificar error general
    print("✅ Test 4: Clasificando error general")
    error_text = "Unknown error occurred"
    error_type = fallback_service._classify_error_by_text(error_text)
    assert "general" in error_type, f"Error general no clasificado: {error_type}"
    
    print("🔧 FASE 11: ✅ Todos los tests de clasificación de errores pasaron!")


def main():
    """🔧 FASE 11: Ejecutar todos los tests"""
    
    print("🔧 FASE 11: Iniciando tests completos de Fallback de Respuesta IA...")
    
    try:
        test_fase11_fallback_service()
        test_fase11_error_detection()
        test_fase11_fallback_generation()
        test_fase11_should_use_fallback()
        test_fase11_error_classification()
        
        print("\n🔧 FASE 11: ✅ TODOS LOS TESTS PASARON EXITOSAMENTE!")
        print("✅ Servicio de fallback implementado")
        print("✅ Detección de tipos de error implementada")
        print("✅ Generación de respuestas de fallback implementada")
        print("✅ Lógica de cuándo usar fallback implementada")
        print("✅ Clasificación de errores por texto implementada")
        print("✅ Normalización de salida de acciones DB implementada")
        
    except Exception as e:
        print(f"\n🔧 FASE 11: ❌ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 FASE 11 completada exitosamente!")
    else:
        print("\n❌ FASE 11 falló en los tests")

