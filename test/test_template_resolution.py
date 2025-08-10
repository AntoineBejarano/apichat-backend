import pytest
import sys
import os

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.chat_ws_router import resolve_template_string, resolve_step_templates


def test_resolve_template_string():
    """Test que verifica la resolución de templates en strings"""
    
    # Variables de prueba
    variables = {
        "query_result": "Aquí están los resultados de la consulta",
        "table_name": "usuarios",
        "count": 42
    }
    
    # Test 1: Template simple con {variable}
    template1 = "Resultados obtenidos: {query_result}"
    expected1 = "Resultados obtenidos: Aquí están los resultados de la consulta"
    result1 = resolve_template_string(template1, variables)
    assert result1 == expected1, f"Expected: {expected1}, Got: {result1}"
    
    # Test 2: Template con {{variable}}
    template2 = "Tabla: {{table_name}} con {{count}} registros"
    expected2 = "Tabla: usuarios con 42 registros"
    result2 = resolve_template_string(template2, variables)
    assert result2 == expected2, f"Expected: {expected2}, Got: {result2}"
    
    # Test 3: Template mixto
    template3 = "Consulta en {table_name}: {{count}} resultados"
    expected3 = "Consulta en usuarios: 42 resultados"
    result3 = resolve_template_string(template3, variables)
    assert result3 == expected3, f"Expected: {expected3}, Got: {result3}"
    
    # Test 4: Template sin variables
    template4 = "Mensaje sin variables"
    expected4 = "Mensaje sin variables"
    result4 = resolve_template_string(template4, variables)
    assert result4 == expected4, f"Expected: {expected4}, Got: {result4}"
    
    # Test 5: Template con variable que no existe
    template5 = "Variable inexistente: {no_existe}"
    expected5 = "Variable inexistente: {no_existe}"
    result5 = resolve_template_string(template5, variables)
    assert result5 == expected5, f"Expected: {expected5}, Got: {result5}"
    
    print("✅ Todos los tests de resolve_template_string pasaron")


def test_resolve_step_templates():
    """Test que verifica la resolución de templates en steps"""
    
    # Steps de prueba
    steps = [
        {
            "type": "step",
            "message": "Consultando base de datos",
            "status": "in_progress"
        },
        {
            "type": "step",
            "message": "Resultados obtenidos: {query_result}",
            "status": "pending",
            "depends_on": "query_result",
            "template": "Resultados obtenidos: {query_result}"
        },
        {
            "type": "step",
            "message": "Tabla {{table_name}} procesada",
            "status": "completed"
        }
    ]
    
    # Variables de prueba
    variables = {
        "query_result": "Aquí están los resultados de la consulta",
        "table_name": "usuarios"
    }
    
    # Resolver templates
    resolved_steps = resolve_step_templates(steps, variables)
    
    # Verificar que se resolvieron correctamente
    assert len(resolved_steps) == 3, f"Expected 3 steps, got {len(resolved_steps)}"
    
    # Step 1: No debería cambiar
    assert resolved_steps[0]["message"] == "Consultando base de datos"
    
    # Step 2: Debería resolver el template
    expected_message2 = "Resultados obtenidos: Aquí están los resultados de la consulta"
    assert resolved_steps[1]["message"] == expected_message2, f"Expected: {expected_message2}, Got: {resolved_steps[1]['message']}"
    
    # Step 3: Debería resolver el message
    expected_message3 = "Tabla usuarios procesada"
    assert resolved_steps[2]["message"] == expected_message3, f"Expected: {expected_message3}, Got: {resolved_steps[2]['message']}"
    
    print("✅ Todos los tests de resolve_step_templates pasaron")


def test_edge_cases():
    """Test de casos edge y límite"""
    
    # Test con variables vacías
    result1 = resolve_template_string("Test {var}", {})
    assert result1 == "Test {var}", "Debería mantener el template si no hay variables"
    
    # Test con template vacío
    result2 = resolve_template_string("", {"var": "value"})
    assert result2 == "", "Debería devolver string vacío si el template está vacío"
    
    # Test con variables None
    result3 = resolve_template_string("Test {var}", {"var": None})
    assert result3 == "Test None", "Debería convertir None a string"
    
    # Test con steps vacíos
    result4 = resolve_step_templates([], {"var": "value"})
    assert result4 == [], "Debería devolver lista vacía si no hay steps"
    
    # Test con variables vacías
    result5 = resolve_step_templates([{"message": "Test {var}"}], {})
    assert result5[0]["message"] == "Test {var}", "Debería mantener el template si no hay variables"
    
    print("✅ Todos los tests de edge cases pasaron")


if __name__ == "__main__":
    print("🧪 Ejecutando tests de resolución de templates...")
    
    test_resolve_template_string()
    test_resolve_step_templates()
    test_edge_cases()
    
    print("\n🎉 ¡Todos los tests pasaron exitosamente!")
