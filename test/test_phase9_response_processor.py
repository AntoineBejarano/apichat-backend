"""
Test para Fase 9: ResponseProcessor - Plantillas UX
────────────────────────────────────────────────────
Verifica que los formateadores de respuestas estén funcionando correctamente
con micro-copy estándar para modo Explorer y Guided.
"""

import pytest
from typing import Dict, List, Any
from app.services.orchestrator.response_processor import ResponseProcessor


class TestResponseProcessorFormatters:
    """Test de los formateadores de ResponseProcessor."""
    
    def test_format_explorer_report_basic(self):
        """Test del formateador básico para modo Explorer."""
        processor = ResponseProcessor()
        
        findings = [
            {"content": "Se encontraron 3 tablas relacionadas con usuarios"},
            {"content": "La tabla 'users' tiene 150 registros"},
            {"content": "Hay 2 aplicaciones que pueden acceder a estos datos"}
        ]
        citations = ["database_schema", "app_registry"]
        usage = {"tokens_used": 120, "execution_time": 1.5}
        next_actions = [
            "Explorar la estructura de la tabla users",
            "Ver qué aplicaciones tienen acceso",
            "Consultar datos específicos de usuarios"
        ]
        
        result = processor.format_explorer_report(findings, citations, usage, next_actions)
        
        # Verificar estructura básica
        assert "🔍 **Reporte de Exploración**" in result
        assert "**Hallazgos principales:**" in result
        assert "**Fuentes:**" in result
        assert "**Uso:**" in result
        assert "**Siguientes acciones:**" in result
        
        # Verificar contenido
        assert "Se encontraron 3 tablas relacionadas con usuarios" in result
        assert "database_schema" in result
        assert "120" in result
        assert "1.50s" in result
        assert "Explorar la estructura de la tabla users" in result
        
        # Verificar que no haya demasiados bullets en total (debe ser razonable)
        total_bullets = result.count("•")
        assert total_bullets <= 12, f"Demasiados bullets en total: {total_bullets}"
        
        # Verificar que cada sección tenga el contenido esperado
        assert "Se encontraron 3 tablas relacionadas con usuarios" in result
        assert "La tabla 'users' tiene 150 registros" in result
        assert "Hay 2 aplicaciones que pueden acceder a estos datos" in result
    
    def test_format_explorer_report_empty_data(self):
        """Test del formateador con datos vacíos."""
        processor = ResponseProcessor()
        
        result = processor.format_explorer_report([], [], {}, [])
        
        # Debe generar solo la cabecera
        assert "🔍 **Reporte de Exploración**" in result
        assert "**Hallazgos principales:**" not in result
        assert "**Fuentes:**" not in result
        assert "**Uso:**" not in result
        assert "**Siguientes acciones:**" not in result
    
    def test_format_explorer_report_partial_data(self):
        """Test del formateador con datos parciales."""
        processor = ResponseProcessor()
        
        findings = [{"content": "Solo un hallazgo"}]
        next_actions = ["Una acción"]
        
        result = processor.format_explorer_report(findings, [], {}, next_actions)
        
        # Debe incluir solo los datos disponibles
        assert "**Hallazgos principales:**" in result
        assert "**Siguientes acciones:**" in result
        assert "**Fuentes:**" not in result
        assert "**Uso:**" not in result
    
    def test_format_guided_execution_basic(self):
        """Test del formateador básico para modo Guided."""
        processor = ResponseProcessor()
        
        plan = {
            "title": "Consulta de usuarios activos",
            "description": "Obtener usuarios que han estado activos en los últimos 30 días"
        }
        outcomes = [
            {"status": "completed", "description": "Consulta SQL ejecutada exitosamente"},
            {"status": "completed", "description": "Datos procesados y formateados"},
            {"status": "failed", "description": "Error en validación de permisos"}
        ]
        audit_id = "audit_123"
        usage = {
            "tokens_used": 200,
            "execution_time": 2.5,
            "estimated_cost": "$0.004"
        }
        next_actions = [
            "Revisar permisos de acceso",
            "Reintentar la consulta",
            "Contactar al administrador"
        ]
        
        result = processor.format_guided_execution(plan, outcomes, audit_id, usage, next_actions)
        
        # Verificar estructura básica
        assert "🎯 **Ejecución Guiada Completada**" in result
        assert "**Plan:**" in result
        assert "**Resultados:**" in result
        assert "**ID de Auditoría:**" in result
        assert "**Uso:**" in result
        assert "**Siguientes acciones:**" in result
        
        # Verificar contenido específico
        assert "Consulta de usuarios activos" in result
        assert "✅ 2 pasos completados exitosamente" in result
        assert "❌ 1 paso falló" in result
        assert "audit_123" in result
        assert "200" in result
        assert "2.50s" in result
        assert "$0.004" in result
        assert "Revisar permisos de acceso" in result
    
    def test_format_guided_execution_no_plan(self):
        """Test del formateador sin plan."""
        processor = ResponseProcessor()
        
        outcomes = [{"status": "completed", "description": "Operación completada"}]
        usage = {"tokens_used": 50}
        
        result = processor.format_guided_execution({}, outcomes, "", usage, [])
        
        # Debe manejar plan vacío
        assert "🎯 **Ejecución Guiada Completada**" in result
        assert "**Plan:** Sin título" in result
        assert "✅ 1 paso completado exitosamente" in result
    
    def test_format_guided_execution_all_failed(self):
        """Test del formateador con todos los pasos fallidos."""
        processor = ResponseProcessor()
        
        outcomes = [
            {"status": "failed", "description": "Error de conexión"},
            {"status": "failed", "description": "Timeout en consulta"}
        ]
        
        result = processor.format_guided_execution({}, outcomes, "", {}, [])
        
        assert "❌ 2 pasos fallaron" in result
        assert "✅ 0 pasos completados exitosamente" in result
    
    def test_micro_copy_consistency(self):
        """Test de que el micro-copy sea consistente entre modos."""
        processor = ResponseProcessor()
        
        # Datos de prueba
        findings = [{"content": "Test finding"}]
        next_actions = ["Test action"]
        usage = {"tokens_used": 100}
        
        # Formatear en ambos modos
        explorer_result = processor.format_explorer_report(findings, [], usage, next_actions)
        guided_result = processor.format_guided_execution({}, [], "test", usage, next_actions)
        
        # Verificar que ambos usen la misma estructura de micro-copy
        assert "**Siguientes acciones:**" in explorer_result
        assert "**Siguientes acciones:**" in guided_result
        assert "• Test action" in explorer_result
        assert "• Test action" in guided_result
        
        # Verificar emojis consistentes
        assert "🔍" in explorer_result
        assert "🎯" in guided_result
    
    def test_error_handling(self):
        """Test de manejo de errores en formateadores."""
        processor = ResponseProcessor()
        
        # Test con datos que podrían causar errores
        malformed_findings = [{"invalid_key": None}, {"content": "Valid content"}]
        
        # Debe manejar errores graciosamente
        result = processor.format_explorer_report(malformed_findings, [], {}, [])
        assert "🔍 **Reporte de Exploración**" in result
        assert "Valid content" in result  # Debe incluir contenido válido
    
    def test_usage_formatting(self):
        """Test de formateo de estadísticas de uso."""
        processor = ResponseProcessor()
        
        usage = {
            "tokens_used": 150,
            "execution_time": 1.75,
            "estimated_cost": "$0.003"
        }
        
        result = processor.format_guided_execution({}, [], "test", usage, [])
        
        # Verificar formateo de números
        assert "150" in result
        assert "1.75s" in result
        assert "$0.003" in result
    
    def test_next_actions_limit(self):
        """Test de que las acciones sugeridas estén limitadas a 3."""
        processor = ResponseProcessor()
        
        many_actions = [f"Acción {i}" for i in range(10)]
        
        result = processor.format_explorer_report([], [], {}, many_actions)
        
        # Contar bullets de acciones
        action_bullets = result.count("• Acción")
        assert action_bullets <= 3  # Máximo 3 acciones
    
    def test_findings_limit(self):
        """Test de que los hallazgos estén limitados a 3."""
        processor = ResponseProcessor()
        
        many_findings = [{"content": f"Hallazgo {i}"} for i in range(10)]
        
        result = processor.format_explorer_report(many_findings, [], {}, [])
        
        # Contar bullets de hallazgos
        finding_bullets = result.count("• Hallazgo")
        assert finding_bullets <= 3  # Máximo 3 hallazgos


class TestResponseProcessorIntegration:
    """Test de integración de ResponseProcessor."""
    
    def test_response_processor_initialization(self):
        """Test de que ResponseProcessor se inicialice correctamente."""
        processor = ResponseProcessor()
        assert processor is not None
        assert hasattr(processor, 'format_explorer_report')
        assert hasattr(processor, 'format_guided_execution')
    
    def test_formatters_produce_strings(self):
        """Test de que los formateadores produzcan strings."""
        processor = ResponseProcessor()
        
        explorer_result = processor.format_explorer_report([], [], {}, [])
        guided_result = processor.format_guided_execution({}, [], "", {}, [])
        
        assert isinstance(explorer_result, str)
        assert isinstance(guided_result, str)
        assert len(explorer_result) > 0
        assert len(guided_result) > 0
    
    def test_formatters_handle_edge_cases(self):
        """Test de casos edge en los formateadores."""
        processor = ResponseProcessor()
        
        # Casos edge
        edge_cases = [
            (None, [], {}, []),  # None en findings
            ([], None, {}, []),  # None en citations
            ([], [], None, []),  # None en usage
            ([], [], {}, None),  # None en next_actions
        ]
        
        for case in edge_cases:
            try:
                result = processor.format_explorer_report(*case)
                assert isinstance(result, str)
            except Exception as e:
                # Si falla, debe ser un error manejado
                assert "Error formateando" in str(result)


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"])
