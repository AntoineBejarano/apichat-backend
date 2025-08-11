"""
🎯 FASE 11: Tests para el manejo de errores con remediación automática.

Este archivo de test valida la funcionalidad del ErrorHandlerService y su integración
con el sistema de errores comunes.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.common.errors import (
    ErrorRegistry,
    UserFacingError,
    ErrorCategory,
    ErrorSeverity,
    SuggestedAction,
    create_custom_error
)
from app.services.execution.error_handler_service import ErrorHandlerService
from app.common.events import ErrorUserFacingEvent


class TestErrorRegistry:
    """Tests para el registro de errores predefinidos."""
    
    def test_get_error_by_code(self):
        """Test obtener error por código."""
        error = ErrorRegistry.get_error_by_code("LLM_TIMEOUT")
        assert error is not None
        assert error.code == "LLM_TIMEOUT"
        assert error.category == ErrorCategory.LLM_TIMEOUT
        assert error.severity == ErrorSeverity.MEDIUM
        
        # Test con código inexistente
        error = ErrorRegistry.get_error_by_code("NONEXISTENT")
        assert error is None
    
    def test_get_errors_by_category(self):
        """Test obtener errores por categoría."""
        errors = ErrorRegistry.get_errors_by_category(ErrorCategory.DATABASE_ERROR)
        assert len(errors) >= 2  # DATABASE_CONNECTION_ERROR y DATABASE_QUERY_TIMEOUT
        
        for error in errors:
            assert error.category == ErrorCategory.DATABASE_ERROR
    
    def test_get_errors_by_severity(self):
        """Test obtener errores por severidad."""
        errors = ErrorRegistry.get_errors_by_severity(ErrorSeverity.HIGH)
        assert len(errors) >= 2  # INSUFFICIENT_PERMISSIONS y CONFIGURATION_ERROR
        
        for error in errors:
            assert error.severity == ErrorSeverity.HIGH
    
    def test_llm_timeout_error(self):
        """Test error de timeout de LLM."""
        error = ErrorRegistry.LLM_TIMEOUT
        assert error.code == "LLM_TIMEOUT"
        assert error.retry_after == 5
        assert len(error.suggested_actions) == 3
        
        # Verificar acciones sugeridas
        actions = [action.action for action in error.suggested_actions]
        assert "retry" in actions
        assert "simplify_query" in actions
        assert "switch_to_fast_mode" in actions
    
    def test_cache_inconsistent_error(self):
        """Test error de cache inconsistente."""
        error = ErrorRegistry.CACHE_INCONSISTENT
        assert error.code == "CACHE_INCONSISTENT"
        assert error.severity == ErrorSeverity.LOW
        assert error.retry_after is None  # No requiere espera
        
        # Verificar acciones sugeridas
        actions = [action.action for action in error.suggested_actions]
        assert "continue_with_fresh_data" in actions
        assert "check_recent_changes" in actions


class TestErrorHandlerService:
    """Tests para el servicio de manejo de errores."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.mock_ws_emitter = Mock()
        self.mock_ws_emitter.emit_error_user_facing = AsyncMock(return_value=True)
        
        self.error_handler = ErrorHandlerService(self.mock_ws_emitter)
    
    @pytest.mark.asyncio
    async def test_handle_error_with_user_facing_error(self):
        """Test manejar error que ya es UserFacingError."""
        # Crear error predefinido
        original_error = ErrorRegistry.LLM_TIMEOUT
        
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=original_error,
            user_id="test-user-456"
        )
        
        assert result.code == "LLM_TIMEOUT"
        assert result.context is not None
        assert result.context["chat_id"] == "test-chat-123"
        assert result.context["user_id"] == "test-user-456"
        assert result.context["error_count"] == 1
    
    @pytest.mark.asyncio
    async def test_handle_error_with_exception(self):
        """Test manejar excepción y convertirla a UserFacingError."""
        # Crear excepción de timeout
        timeout_exception = Exception("LLM request timed out after 30 seconds")
        
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=timeout_exception,
            user_id="test-user-456"
        )
        
        # Debería detectar que es un timeout de LLM
        assert result.code == "LLM_TIMEOUT"
        assert "tardando más de lo esperado" in result.human_message
        assert result.retry_after == 5
    
    @pytest.mark.asyncio
    async def test_handle_error_with_asyncio_timeout_error(self):
        """Test manejar asyncio.TimeoutError específicamente."""
        import asyncio
        
        # Crear asyncio.TimeoutError
        timeout_exception = asyncio.TimeoutError()
        
        # Test con contexto de operación mínima
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=timeout_exception,
            context={"operation": "minimal_context"},
            user_id="test-user-456"
        )
        
        # Debería detectar que es un timeout de LLM
        assert result.code == "LLM_TIMEOUT"
        assert "tardando más de lo esperado" in result.human_message
        
        # Test con contexto de base de datos
        result_db = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=timeout_exception,
            context={"operation": "database_query", "db_id": "test-db"},
            user_id="test-user-456"
        )
        
        # Debería detectar que es un timeout de base de datos
        assert result_db.code == "DATABASE_QUERY_TIMEOUT"
        assert "consulta a la base de datos" in result_db.human_message
    
    @pytest.mark.asyncio
    async def test_handle_error_with_permission_exception(self):
        """Test manejar excepción de permisos."""
        permission_exception = Exception("Access denied: insufficient permissions")
        
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=permission_exception,
            user_id="test-user-456"
        )
        
        assert result.code == "INSUFFICIENT_PERMISSIONS"
        assert result.severity == ErrorSeverity.HIGH
        assert "permisos suficientes" in result.human_message
    
    @pytest.mark.asyncio
    async def test_handle_error_with_network_exception(self):
        """Test manejar excepción de red."""
        network_exception = Exception("Connection failed: network unreachable")
        
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=network_exception,
            user_id="test-user-456"
        )
        
        assert result.code == "NETWORK_ERROR"
        assert result.severity == ErrorSeverity.MEDIUM
        assert result.retry_after == 15
    
    @pytest.mark.asyncio
    async def test_handle_error_with_generic_exception(self):
        """Test manejar excepción genérica."""
        generic_exception = Exception("Something unexpected happened")
        
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=generic_exception,
            user_id="test-user-456"
        )
        
        assert result.code == "EXECUTION_ERROR"
        assert "Ocurrió un error durante la ejecución" in result.human_message
        assert len(result.suggested_actions) == 3
    
    @pytest.mark.asyncio
    async def test_automatic_remediation_first_error(self):
        """Test que no se aplique remediación en el primer error."""
        # Primer error
        error = ErrorRegistry.LLM_TIMEOUT
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=error,
            user_id="test-user-456"
        )
        
        # Debería mantener las acciones originales
        assert len(result.suggested_actions) == 3
        original_actions = [action.action for action in result.suggested_actions]
        assert "retry" in original_actions
    
    @pytest.mark.asyncio
    async def test_automatic_remediation_multiple_errors(self):
        """Test que se aplique remediación automática en múltiples errores."""
        # Primer error
        await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=ErrorRegistry.LLM_TIMEOUT,
            user_id="test-user-456"
        )
        
        # Segundo error - debería aplicar remediación
        result = await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=ErrorRegistry.DATABASE_QUERY_TIMEOUT,
            user_id="test-user-456"
        )
        
        # Debería incluir acciones de diagnóstico y modo seguro
        actions = [action.action for action in result.suggested_actions]
        assert "diagnose_issue" in actions
        assert "switch_to_safe_mode" in actions
        assert len(result.suggested_actions) <= 3  # Máximo 3 acciones
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_success(self):
        """Test ejecutar acción de reintento exitosamente."""
        result = await self.error_handler.handle_retry_action(
            chat_id="test-chat-123",
            action="retry_operation"
        )
        
        assert result["success"] is True
        assert "reintentada exitosamente" in result["message"]
        assert "retry_count" in result
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_max_retries(self):
        """Test que se alcance el máximo de reintentos."""
        # Ejecutar 4 reintentos (más del máximo de 3)
        for i in range(4):
            result = await self.error_handler.handle_retry_action(
                chat_id="test-chat-123",
                action="retry_operation"
            )
        
        # El último debería fallar por máximo de reintentos
        assert result["success"] is False
        assert "máximo de reintentos" in result["message"]
        assert len(result["suggested_actions"]) == 2
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_switch_to_fast_mode(self):
        """Test cambiar a modo rápido."""
        result = await self.error_handler.handle_retry_action(
            chat_id="test-chat-123",
            action="switch_to_fast_mode"
        )
        
        assert result["success"] is True
        assert result["mode"] == "fast"
        assert "más veloces" in result["message"]
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_use_safe_mode(self):
        """Test cambiar a modo seguro."""
        result = await self.error_handler.handle_retry_action(
            chat_id="test-chat-123",
            action="use_safe_mode"
        )
        
        assert result["success"] is True
        assert result["mode"] == "safe"
        assert "más conservadoras" in result["message"]
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_diagnose_issue(self):
        """Test diagnosticar problema."""
        # Primero crear algunos errores para tener historial
        await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=ErrorRegistry.LLM_TIMEOUT,
            user_id="test-user-456"
        )
        
        await self.error_handler.handle_error(
            chat_id="test-chat-123",
            error=ErrorRegistry.DATABASE_QUERY_TIMEOUT,
            user_id="test-user-456"
        )
        
        # Ahora diagnosticar
        result = await self.error_handler.handle_retry_action(
            chat_id="test-chat-123",
            action="diagnose_issue"
        )
        
        assert result["success"] is True
        assert "Diagnóstico completado" in result["message"]
        assert "patterns" in result
        assert "recommendations" in result
        assert result["patterns"]["total_errors"] == 2
    
    @pytest.mark.asyncio
    async def test_handle_retry_action_unknown_action(self):
        """Test acción de reintento desconocida."""
        result = await self.error_handler.handle_retry_action(
            chat_id="test-chat-123",
            action="unknown_action"
        )
        
        assert result["success"] is False
        assert "no reconocida" in result["message"]
        assert len(result["suggested_actions"]) == 1
        assert result["suggested_actions"][0]["action"] == "show_available_actions"
    
    def test_get_error_statistics_specific_chat(self):
        """Test obtener estadísticas de un chat específico."""
        # Crear algunos errores
        self.error_handler.error_history["test-chat-123"] = [
            {
                "timestamp": datetime.utcnow(),
                "code": "LLM_TIMEOUT",
                "severity": "medium"
            }
        ]
        self.error_handler.retry_counters["test-chat-123"] = 2
        
        stats = self.error_handler.get_error_statistics("test-chat-123")
        
        assert stats["chat_id"] == "test-chat-123"
        assert stats["total_errors"] == 1
        assert stats["retry_count"] == 2
        assert len(stats["recent_errors"]) == 1
    
    def test_get_error_statistics_global(self):
        """Test obtener estadísticas globales."""
        # Crear errores en múltiples chats
        self.error_handler.error_history["chat-1"] = [{"timestamp": datetime.utcnow(), "code": "A", "severity": "low"}]
        self.error_handler.error_history["chat-2"] = [{"timestamp": datetime.utcnow(), "code": "B", "severity": "medium"}]
        
        stats = self.error_handler.get_error_statistics()
        
        assert stats["total_errors"] == 2
        assert stats["total_chats_with_errors"] == 2
        assert stats["average_errors_per_chat"] == 1.0
        assert "chat-1" in stats["chats_by_error_count"]
        assert "chat-2" in stats["chats_by_error_count"]
    
    def test_error_history_limiting(self):
        """Test que se limite el historial de errores por chat."""
        # Crear más de 10 errores usando el método real
        for i in range(15):
            error = create_custom_error(
                code=f"ERROR_{i}",
                category=ErrorCategory.EXECUTION_ERROR,
                severity=ErrorSeverity.LOW,
                human_message=f"Test error {i}",
                suggested_actions=[]
            )
            
            # Usar el método real para registrar el error
            self.error_handler._log_error(error, "test-chat-123", "test-user")

        # Verificar que solo se mantengan los últimos 10
        assert len(self.error_handler.error_history["test-chat-123"]) == 10
        
        # Los últimos errores deberían estar presentes
        last_error = self.error_handler.error_history["test-chat-123"][-1]
        assert last_error["code"] == "ERROR_14"


class TestCustomErrorCreation:
    """Tests para la creación de errores personalizados."""
    
    def test_create_custom_error(self):
        """Test crear error personalizado."""
        custom_error = create_custom_error(
            code="CUSTOM_ERROR",
            category=ErrorCategory.EXECUTION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            human_message="Este es un error personalizado",
            suggested_actions=[
                {
                    "label": "Acción personalizada",
                    "action": "custom_action",
                    "description": "Descripción de la acción",
                    "priority": 1
                }
            ],
            technical_details="Detalles técnicos del error",
            retry_after=30,
            context={"custom_field": "custom_value"}
        )
        
        assert custom_error.code == "CUSTOM_ERROR"
        assert custom_error.category == ErrorCategory.EXECUTION_ERROR
        assert custom_error.severity == ErrorSeverity.MEDIUM
        assert custom_error.human_message == "Este es un error personalizado"
        assert len(custom_error.suggested_actions) == 1
        assert custom_error.suggested_actions[0].action == "custom_action"
        assert custom_error.technical_details == "Detalles técnicos del error"
        assert custom_error.retry_after == 30
        assert custom_error.context["custom_field"] == "custom_value"
    
    def test_get_prioritized_actions(self):
        """Test obtener acciones sugeridas por prioridad."""
        from app.common.errors import get_prioritized_actions
        
        # Crear error con acciones de diferentes prioridades
        custom_error = create_custom_error(
            code="TEST_ERROR",
            category=ErrorCategory.EXECUTION_ERROR,
            severity=ErrorSeverity.MEDIUM,
            human_message="Test error",
            suggested_actions=[
                {
                    "label": "Alta prioridad",
                    "action": "high_priority",
                    "priority": 1
                },
                {
                    "label": "Baja prioridad",
                    "action": "low_priority",
                    "priority": 3
                },
                {
                    "label": "Media prioridad",
                    "action": "medium_priority",
                    "priority": 2
                }
            ]
        )
        
        # Obtener acciones prioritarias
        prioritized = get_prioritized_actions(custom_error, max_actions=2)
        
        assert len(prioritized) == 2
        assert prioritized[0].priority == 1  # Alta prioridad
        assert prioritized[1].priority == 2  # Media prioridad


class TestErrorHandlerIntegration:
    """Tests de integración del ErrorHandlerService."""
    
    @pytest.mark.asyncio
    async def test_error_handler_with_ws_emitter_failure(self):
        """Test que el ErrorHandlerService maneje fallos del WebSocketEmitter."""
        # Crear mock que falla
        mock_ws_emitter = Mock()
        mock_ws_emitter.emit_error_user_facing = AsyncMock(side_effect=Exception("WS failure"))
        
        error_handler = ErrorHandlerService(mock_ws_emitter)
        
        # Debería manejar el fallo del WebSocketEmitter
        result = await error_handler.handle_error(
            chat_id="test-chat-123",
            error=ErrorRegistry.LLM_TIMEOUT,
            user_id="test-user-456"
        )
        
        # Debería retornar el error procesado a pesar del fallo del WS
        assert result.code == "LLM_TIMEOUT"
        assert result.human_message is not None
    
    @pytest.mark.asyncio
    async def test_error_handler_fallback_on_critical_failure(self):
        """Test que el ErrorHandlerService use fallback en fallos críticos."""
        # Crear mock que falla en el manejo de errores
        mock_ws_emitter = Mock()
        mock_ws_emitter.emit_error_user_facing = AsyncMock(return_value=True)
        
        error_handler = ErrorHandlerService(mock_ws_emitter)
        
        # Simular fallo crítico en el manejo de errores
        with patch.object(error_handler, '_categorize_exception', side_effect=Exception("Critical failure")):
            result = await error_handler.handle_error(
                chat_id="test-chat-123",
                error=Exception("Test error"),
                user_id="test-user-456"
            )
        
        # Debería usar el error de fallback
        assert result.code == "ERROR_HANDLER_FAILURE"
        assert result.severity == ErrorSeverity.HIGH
        assert "error inesperado" in result.human_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
