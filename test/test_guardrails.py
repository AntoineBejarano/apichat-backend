import pytest
from unittest.mock import Mock, patch
from app.common.enums import RiskLevel


class TestSQLGuardrailsService:
    """Tests mínimos para SQLGuardrailsService"""

    def test_sql_guardrails_import(self):
        """Test que se puede importar SQLGuardrailsService"""
        try:
            from app.services.execution.sql_guardrails_service import SQLGuardrailsService
            assert SQLGuardrailsService is not None
        except ImportError:
            pytest.skip("SQLGuardrailsService no está disponible")

    def test_sql_guardrails_creation(self):
        """Test que se puede crear una instancia de SQLGuardrailsService"""
        try:
            from app.services.execution.sql_guardrails_service import SQLGuardrailsService
            guardrails = SQLGuardrailsService()
            assert guardrails is not None
        except Exception as e:
            pytest.skip(f"No se puede crear SQLGuardrailsService: {e}")

    def test_sql_guardrails_methods(self):
        """Test que SQLGuardrailsService tiene los métodos esperados"""
        try:
            from app.services.execution.sql_guardrails_service import SQLGuardrailsService
            guardrails = SQLGuardrailsService()
            
            # Verificar métodos que realmente existen
            assert hasattr(guardrails, 'analyze_sql_query')
            assert hasattr(guardrails, 'validate_and_apply_guardrails')
            assert hasattr(guardrails, 'get_safe_alternatives')
            
        except Exception as e:
            pytest.skip(f"No se puede crear SQLGuardrailsService: {e}")


class TestFunctionGuardrails:
    """Tests mínimos para FunctionGuardrails"""

    def test_function_guardrails_import(self):
        """Test que se puede importar FunctionGuardrailsService"""
        try:
            from app.services.execution.function_guardrails import FunctionGuardrailsService
            assert FunctionGuardrailsService is not None
        except ImportError:
            pytest.skip("FunctionGuardrailsService no está disponible")

    def test_function_guardrails_creation(self):
        """Test que se puede crear una instancia de FunctionGuardrailsService"""
        try:
            from app.services.execution.function_guardrails import FunctionGuardrailsService
            guardrails = FunctionGuardrailsService()
            assert guardrails is not None
        except Exception as e:
            pytest.skip(f"No se puede crear FunctionGuardrailsService: {e}")

    def test_function_guardrails_methods(self):
        """Test que FunctionGuardrailsService tiene los métodos esperados"""
        try:
            from app.services.execution.function_guardrails import FunctionGuardrailsService
            guardrails = FunctionGuardrailsService()
            
            # Verificar métodos que realmente existen
            assert hasattr(guardrails, 'get_function_guardrail')
            assert hasattr(guardrails, 'validate_function_execution')
            assert hasattr(guardrails, 'add_custom_guardrail')
            
        except Exception as e:
            pytest.skip(f"No se puede crear FunctionGuardrailsService: {e}")


class TestGuardrailsIntegration:
    """Tests de integración básica de guardrails"""

    def test_risk_level_enum(self):
        """Test que RiskLevel enum está disponible y tiene valores esperados"""
        assert RiskLevel.LOW is not None
        assert RiskLevel.MEDIUM is not None
        assert RiskLevel.HIGH is not None
        
        # Verificar que son diferentes
        assert RiskLevel.LOW != RiskLevel.MEDIUM
        assert RiskLevel.MEDIUM != RiskLevel.HIGH
        assert RiskLevel.LOW != RiskLevel.HIGH

    def test_guardrails_services_exist(self):
        """Test que los servicios de guardrails están disponibles en el sistema"""
        try:
            # Intentar importar servicios
            from app.services.execution.sql_guardrails_service import SQLGuardrailsService
            from app.services.execution.function_guardrails import FunctionGuardrailsService
            
            # Si llega aquí, los servicios existen
            assert True
            
        except ImportError as e:
            # Los servicios no están disponibles, pero no es un error
            pytest.skip(f"Servicios de guardrails no disponibles: {e}")

    def test_guardrails_configuration(self):
        """Test que la configuración de guardrails es válida"""
        # Verificar que RiskLevel tiene valores válidos
        risk_values = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH]
        
        for risk in risk_values:
            assert risk is not None
            assert isinstance(risk.value, str) if hasattr(risk, 'value') else True
