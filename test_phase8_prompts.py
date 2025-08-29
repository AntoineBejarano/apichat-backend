"""
🧪 Tests para FASE 8 - Sistema de Prompts Configurable
─────────────────────────────────────────────────────────
Verifica:
- PromptRegistry: Registro central de prompts
- PromptTemplateService: Renderizado y gestión de prompts
- Configuración desde archivo YAML
- Integración con el sistema
"""

import sys
import os
import time
import tempfile
import yaml

# Añadir el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_prompt_registry():
    """🧪 Test del PromptRegistry"""
    print("📝 Probando PromptRegistry...")
    
    try:
        from app.services.prompts.prompt_registry import (
            PromptKey, PromptCategory, PromptRegistry, prompt_registry
        )
        
        # Test 1: Enums básicos
        print("  📋 Test 1: Enums básicos")
        assert PromptKey.SCHEMA_EXTRACTION.value == "schema_extraction", f"Valor incorrecto: {PromptKey.SCHEMA_EXTRACTION.value}"
        assert PromptCategory.PIPELINE.value == "pipeline", f"Valor incorrecto: {PromptCategory.PIPELINE.value}"
        print("    ✅ Enums funcionando correctamente")
        
        # Test 2: Instancia global
        print("  📋 Test 2: Instancia global")
        assert prompt_registry is not None, "Instancia global no creada"
        assert isinstance(prompt_registry, PromptRegistry), "Tipo incorrecto de instancia"
        print("    ✅ Instancia global creada correctamente")
        
        # Test 3: Categorías de prompts
        print("  📋 Test 3: Categorías de prompts")
        category = prompt_registry.get_category(PromptKey.SCHEMA_EXTRACTION)
        assert category == PromptCategory.PIPELINE, f"Categoría incorrecta: {category}"
        
        category = prompt_registry.get_category(PromptKey.SQL_GENERATION)
        assert category == PromptCategory.CHAT, f"Categoría incorrecta: {category}"
        print("    ✅ Categorías asignadas correctamente")
        
        # Test 4: Metadatos de prompts
        print("  📋 Test 4: Metadatos de prompts")
        metadata = prompt_registry.get_metadata(PromptKey.SCHEMA_EXTRACTION)
        assert metadata is not None, "Metadatos no encontrados"
        assert "description" in metadata, "Descripción no encontrada en metadatos"
        print("    ✅ Metadatos funcionando correctamente")
        
        # Test 5: Prompts por categoría
        print("  📋 Test 5: Prompts por categoría")
        pipeline_prompts = prompt_registry.get_prompts_by_category(PromptCategory.PIPELINE)
        assert len(pipeline_prompts) > 0, "No hay prompts de pipeline"
        assert PromptKey.SCHEMA_EXTRACTION in pipeline_prompts, "SCHEMA_EXTRACTION no está en pipeline"
        print("    ✅ Prompts agrupados por categoría correctamente")
        
        # Test 6: Validación de claves
        print("  📋 Test 6: Validación de claves")
        assert prompt_registry.validate_prompt_key("schema_extraction"), "Clave válida rechazada"
        assert not prompt_registry.validate_prompt_key("invalid_key"), "Clave inválida aceptada"
        print("    ✅ Validación de claves funcionando")
        
        # Test 7: Información de prompts
        print("  📋 Test 7: Información de prompts")
        info = prompt_registry.get_prompt_info(PromptKey.SQL_GENERATION)
        assert info["key"] == "sql_generation", f"Clave incorrecta: {info['key']}"
        assert info["category"] == "chat", f"Categoría incorrecta: {info['category']}"
        print("    ✅ Información de prompts generada correctamente")
        
        # Test 8: Resumen del registro
        print("  📋 Test 8: Resumen del registro")
        summary = prompt_registry.get_registry_summary()
        assert summary["total_prompts"] > 0, "No hay prompts en el registro"
        assert "categories" in summary, "Categorías no encontradas en resumen"
        print("    ✅ Resumen del registro generado correctamente")
        
        print("  🎉 PromptRegistry: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"    ❌ Error en PromptRegistry: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_template_service():
    """🧪 Test del PromptTemplateService"""
    print("📝 Probando PromptTemplateService...")
    
    try:
        from app.services.prompts.prompt_template_service import (
            PromptTemplateService, PromptContext
        )
        
        # Test 1: Inicialización del servicio
        print("  📋 Test 1: Inicialización del servicio")
        service = PromptTemplateService()
        assert service is not None, "Servicio no inicializado"
        print("    ✅ Servicio inicializado correctamente")
        
        # Test 2: Prompts por defecto
        print("  📋 Test 2: Prompts por defecto")
        summary = service.get_service_summary()
        assert summary["default_prompts"] > 0, "No hay prompts por defecto"
        print("    ✅ Prompts por defecto cargados")
        
        # Test 3: Renderizado básico
        print("  📋 Test 3: Renderizado básico")
        context = PromptContext(
            prompt_key="schema_extraction",
            variables={
                "db_name": "test_db",
                "connection_info": "postgresql://test",
                "extraction_level": "detailed",
                "business_context": "testing"
            }
        )
        
        prompt = service.get_prompt("schema_extraction", context)
        assert "test_db" in prompt, "Variable db_name no renderizada"
        assert "postgresql://test" in prompt, "Variable connection_info no renderizada"
        print("    ✅ Renderizado básico funcionando")
        
        # Test 4: Variables faltantes
        print("  📋 Test 4: Variables faltantes")
        incomplete_context = PromptContext(
            prompt_key="schema_extraction",
            variables={"db_name": "test_db"}  # Faltan variables
        )
        
        prompt = service.get_prompt("schema_extraction", incomplete_context)
        assert "test_db" in prompt, "Variable db_name no renderizada"
        # Verificar que las variables faltantes estén marcadas
        assert "connection_info_NO_DISPONIBLE" in prompt or "business_context_NO_DISPONIBLE" in prompt, "Variable faltante no marcada"
        print("    ✅ Manejo de variables faltantes funcionando")
        
        # Test 5: Actualización de prompts
        print("  📋 Test 5: Actualización de prompts")
        new_template = "Nuevo template para {db_name} con {custom_var}"
        success = service.update_prompt("test_prompt", new_template, "v2")
        assert success, "Actualización de prompt falló"
        print("    ✅ Actualización de prompts funcionando")
        
        # Test 6: Validación de templates
        print("  📋 Test 6: Validación de templates")
        # Template válido
        valid_template = "Template válido con {variable}"
        assert service._validate_prompt_template(valid_template), "Template válido rechazado"
        
        # Template inválido (variable con caracteres peligrosos)
        invalid_template = "Template inválido con {variable!@#}"
        assert not service._validate_prompt_template(invalid_template), "Template inválido aceptado"
        print("    ✅ Validación de templates funcionando")
        
        # Test 7: Versiones de prompts
        print("  📋 Test 7: Versiones de prompts")
        versions = service.get_prompt_versions("schema_extraction")
        assert "default" in versions, "Versión default no encontrada"
        print("    ✅ Versiones de prompts funcionando")
        
        # Test 8: Información de prompts
        print("  📋 Test 8: Información de prompts")
        info = service.get_prompt_info("sql_generation")
        assert "key" in info, "Clave no encontrada en info"
        assert info["key"] == "sql_generation", "Clave incorrecta en info"
        print("    ✅ Información de prompts funcionando")
        
        # Test 9: Limpieza de caché
        print("  📋 Test 9: Limpieza de caché")
        service.clear_cache()
        summary_after = service.get_service_summary()
        assert summary_after["cache_size"] == 0, "Caché no se limpió"
        print("    ✅ Limpieza de caché funcionando")
        
        print("  🎉 PromptTemplateService: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"    ❌ Error en PromptTemplateService: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_configuration():
    """🧪 Test de la configuración de prompts desde YAML"""
    print("📝 Probando configuración de prompts...")
    
    try:
        # Test 1: Archivo de configuración existe
        print("  📋 Test 1: Archivo de configuración")
        config_path = "./config/prompts.yaml"
        assert os.path.exists(config_path), f"Archivo de configuración no encontrado: {config_path}"
        print("    ✅ Archivo de configuración encontrado")
        
        # Test 2: YAML válido
        print("  📋 Test 2: YAML válido")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        assert "prompts" in config, "Sección 'prompts' no encontrada"
        assert "global" in config, "Sección 'global' no encontrada"
        print("    ✅ YAML válido y parseable")
        
        # Test 3: Prompts configurados
        print("  📋 Test 3: Prompts configurados")
        prompts = config["prompts"]
        expected_prompts = ["schema_extraction", "sql_generation", "intent_classification"]
        
        for expected in expected_prompts:
            assert expected in prompts, f"Prompt '{expected}' no encontrado en configuración"
        print("    ✅ Prompts esperados configurados")
        
        # Test 4: Versiones de prompts
        print("  📋 Test 4: Versiones de prompts")
        schema_extraction = prompts["schema_extraction"]
        assert "versions" in schema_extraction, "Versiones no encontradas en schema_extraction"
        assert "v2" in schema_extraction["versions"], "Versión v2 no encontrada"
        print("    ✅ Versiones de prompts configuradas")
        
        # Test 5: Configuración global
        print("  📋 Test 5: Configuración global")
        global_config = config["global"]
        assert "environment" in global_config, "Environment no configurado"
        assert "default_version" in global_config, "Default version no configurado"
        print("    ✅ Configuración global válida")
        
        print("  🎉 Configuración de prompts: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"    ❌ Error en configuración de prompts: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_integration():
    """🧪 Test de integración del sistema de prompts"""
    print("🔗 Probando integración del sistema...")
    
    try:
        from app.services.prompts import PromptTemplateService, PromptContext, PromptKey
        
        # Test 1: Servicio completo
        print("  📋 Test 1: Servicio completo")
        service = PromptTemplateService()
        
        # Test 2: Prompt de pipeline (Fase 1)
        print("  📋 Test 2: Prompt de pipeline")
        pipeline_context = PromptContext(
            prompt_key="schema_extraction",
            variables={
                "db_name": "ecommerce_db",
                "connection_info": "postgresql://user:pass@host:5432/ecommerce",
                "extraction_level": "comprehensive",
                "business_context": "Plataforma de comercio electrónico"
            }
        )
        
        pipeline_prompt = service.get_prompt("schema_extraction", pipeline_context)
        assert "ecommerce_db" in pipeline_prompt, "Prompt de pipeline no renderizado correctamente"
        print("    ✅ Prompt de pipeline funcionando")
        
        # Test 3: Prompt de chat (Fase 5)
        print("  📋 Test 3: Prompt de chat")
        chat_context = PromptContext(
            prompt_key="sql_generation",
            variables={
                "user_query": "¿Cuántos usuarios activos tenemos?",
                "schema_info": "Tabla users con campos: id, name, email, active, created_at",
                "max_rows": 1000,  # Variables planas que coinciden con el template
                "timeout_seconds": 30,
                "allowed_schemas": "public",
                "preferred_style": "clear_and_concise"
            }
        )
        
        chat_prompt = service.get_prompt("sql_generation", chat_context)
        assert "¿Cuántos usuarios activos tenemos?" in chat_prompt, "Prompt de chat no renderizado"
        print("    ✅ Prompt de chat funcionando")
        
        # Test 4: Prompt de seguridad (Fase 7)
        print("  📋 Test 4: Prompt de seguridad")
        security_context = PromptContext(
            prompt_key="sql_validation",
            variables={
                "sql_query": "SELECT * FROM users WHERE active = true",
                "allowed_operations": "SELECT",
                "allowed_schemas": "public",
                "row_limits_max": 1000,  # Variables planas
                "timeout_limits_max": 30,
                "forbidden_patterns": "DROP, DELETE, UPDATE"
            }
        )
        
        security_prompt = service.get_prompt("sql_validation", security_context)
        assert "SELECT * FROM users WHERE active = true" in security_prompt, "Prompt de seguridad no renderizado"
        print("    ✅ Prompt de seguridad funcionando")
        
        # Test 5: Métricas del servicio
        print("  📋 Test 5: Métricas del servicio")
        summary = service.get_service_summary()
        assert summary["service_name"] == "PromptTemplateService", "Nombre del servicio incorrecto"
        assert summary["prompts_configured"] >= 0, "Número de prompts configurados incorrecto"
        print("    ✅ Métricas del servicio funcionando")
        
        print("  🎉 Integración: TODOS LOS TESTS PASARON")
        return True
        
    except Exception as e:
        print(f"    ❌ Error en integración: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """🏃 Función principal de tests"""
    print("🧪 INICIANDO TESTS DE FASE 8 - SISTEMA DE PROMPTS CONFIGURABLE")
    print("=" * 80)
    
    tests = [
        ("PromptRegistry", test_prompt_registry),
        ("PromptTemplateService", test_prompt_template_service),
        ("Configuración de Prompts", test_prompt_configuration),
        ("Integración", test_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Ejecutando {test_name}...")
        if test_func():
            passed += 1
            print(f"✅ {test_name}: PASÓ")
        else:
            print(f"❌ {test_name}: FALLÓ")
    
    print("\n" + "=" * 80)
    print(f"📊 RESUMEN DE TESTS: {passed}/{total} PASARON")
    
    if passed == total:
        print("🎉 ¡TODOS LOS TESTS DE LA FASE 8 PASARON EXITOSAMENTE!")
        print("📝 Sistema de Prompts Configurable implementado correctamente")
        return True
    else:
        print("💥 ALGUNOS TESTS FALLARON")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
