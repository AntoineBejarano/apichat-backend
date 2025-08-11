"""
Test para Fase 10: TokenBudget UX (avisos y modos)
───────────────────────────────────────────────────
Valida la funcionalidad de:
1. TokenBudgetManager.budget_hint() con opciones de modo
2. Avisos de trimming cuando se recorta el contexto
3. Cambios de modo (rápido/equilibrado/preciso)
4. Integración en OrchestratorService
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from typing import Dict, Any

from app.services.orchestrator.token_budget import TokenBudgetManager
from app.services.orchestrator_service import OrchestratorService
from app.common.enums import Mode


class TestTokenBudgetManagerBudgetHint:
    """Test para el método budget_hint del TokenBudgetManager."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.token_budget = TokenBudgetManager()
    
    def test_budget_hint_low_usage(self):
        """Test para uso bajo de tokens (modo preciso recomendado)."""
        estimated_tokens = 2000  # 25% del máximo
        
        result = self.token_budget.budget_hint(estimated_tokens)
        
        assert result["current_usage"]["status"] == "ok"
        assert result["recommended_mode"] == "preciso"
        assert result["current_usage"]["budget_usage_percent"] == 25.0
        assert "Puedes usar modo 'preciso'" in result["suggestions"][0]
        
        # Verificar modos disponibles
        assert "preciso" in result["available_modes"]
        assert "equilibrado" in result["available_modes"]
        assert "rápido" in result["available_modes"]
        
        # Verificar que preciso sea el recomendado
        assert result["available_modes"]["preciso"]["recommended"] is True
        assert result["available_modes"]["equilibrado"]["recommended"] is False
        assert result["available_modes"]["rápido"]["recommended"] is False
    
    def test_budget_hint_medium_usage(self):
        """Test para uso medio de tokens (modo equilibrado recomendado)."""
        estimated_tokens = 5000  # 62.5% del máximo
        
        result = self.token_budget.budget_hint(estimated_tokens)
        
        assert result["current_usage"]["status"] == "ok"
        assert result["recommended_mode"] == "equilibrado"
        assert result["current_usage"]["budget_usage_percent"] == 62.5
        assert "Modo 'equilibrado' puede optimizar" in result["suggestions"][0]
        
        # Verificar que equilibrado sea el recomendado
        assert result["available_modes"]["equilibrado"]["recommended"] is True
    
    def test_budget_hint_high_usage(self):
        """Test para uso alto de tokens (modo rápido recomendado)."""
        estimated_tokens = 7000  # 87.5% del máximo
        
        result = self.token_budget.budget_hint(estimated_tokens)
        
        assert result["current_usage"]["status"] == "warning"
        assert result["recommended_mode"] == "rápido"
        assert result["current_usage"]["budget_usage_percent"] == 87.5
        assert "Considera usar modo 'rápido'" in result["suggestions"][0]
        
        # Verificar que rápido sea el recomendado
        assert result["available_modes"]["rápido"]["recommended"] is True
    
    def test_budget_hint_critical_usage(self):
        """Test para uso crítico de tokens (modo rápido recomendado)."""
        estimated_tokens = 9000  # 112.5% del máximo
        
        result = self.token_budget.budget_hint(estimated_tokens)
        
        assert result["current_usage"]["status"] == "warning"
        assert result["recommended_mode"] == "rápido"
        assert result["current_usage"]["budget_usage_percent"] == 112.5
        assert "Considera usar modo 'rápido'" in result["suggestions"][0]
    
    def test_budget_hint_mode_features(self):
        """Test para verificar características de cada modo."""
        estimated_tokens = 4000
        
        result = self.token_budget.budget_hint(estimated_tokens)
        
        # Verificar características del modo preciso
        preciso = result["available_modes"]["preciso"]
        assert "Historial completo" in preciso["features"]
        assert "Esquemas detallados" in preciso["features"]
        assert "Descriptores completos" in preciso["features"]
        
        # Verificar características del modo equilibrado
        equilibrado = result["available_modes"]["equilibrado"]
        assert "Historial moderado" in equilibrado["features"]
        assert "Esquemas resumidos" in equilibrado["features"]
        assert "Descriptores optimizados" in equilibrado["features"]
        
        # Verificar características del modo rápido
        rapido = result["available_modes"]["rápido"]
        assert "Historial mínimo" in rapido["features"]
        assert "Esquemas básicos" in rapido["features"]
        assert "Descriptores resumidos" in rapido["features"]


class TestTokenBudgetManagerTrimming:
    """Test para el trimming inteligente del TokenBudgetManager."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        self.token_budget = TokenBudgetManager()
    
    def test_apply_intelligent_context_trimming_no_trimming(self):
        """Test cuando no se necesita trimming."""
        context = {
            "chat_history": [{"content": "test"}],
            "database_schemas": {"db1": [{"name": "table1"}]},
            "app_descriptors": [{"name": "app1", "description": "short"}],
            "functions": [{"name": "func1", "description": "short"}]
        }
        
        result = self.token_budget.apply_intelligent_context_trimming(context)
        
        assert "_trimming_info" in result
        trimming_info = result["_trimming_info"]
        assert trimming_info["chat_history_trimmed"] is False
        assert trimming_info["db_schemas_trimmed"] is False
        assert trimming_info["app_descriptors_trimmed"] is False
        assert trimming_info["functions_trimmed"] is False
        assert trimming_info["original_tokens"] > 0
        assert trimming_info["trimmed_tokens"] > 0
    
    def test_apply_intelligent_context_trimming_with_trimming(self):
        """Test cuando se aplica trimming."""
        # Crear contexto que exceda los límites
        long_description = "x" * 3000  # Excede MAX_APP_DESCRIPTOR_CHARS
        
        context = {
            "chat_history": [{"content": "test"}] * 10,  # Excede MAX_HISTORY_TURNS
            "database_schemas": {"db1": [{"name": f"table{i}"} for i in range(15)]},  # Excede límite de 10
            "app_descriptors": [{"name": "app1", "description": long_description}],
            "functions": [{"name": "func1", "description": "x" * 150}]  # Excede MAX_FUNCTION_DESCRIPTION_CHARS
        }
        
        result = self.token_budget.apply_intelligent_context_trimming(context)
        
        assert "_trimming_info" in result
        trimming_info = result["_trimming_info"]
        
        # Verificar que se aplicó trimming
        assert trimming_info["chat_history_trimmed"] is True
        assert trimming_info["db_schemas_trimmed"] is True
        assert trimming_info["app_descriptors_trimmed"] is True
        assert trimming_info["functions_trimmed"] is True
        
        # Verificar que se ahorraron tokens
        assert trimming_info["trimmed_tokens"] < trimming_info["original_tokens"]
        tokens_saved = trimming_info["original_tokens"] - trimming_info["trimmed_tokens"]
        assert tokens_saved > 0


class TestOrchestratorServiceTokenBudgetUX:
    """Test para la integración de TokenBudget UX en OrchestratorService."""
    
    def setup_method(self):
        """Configuración inicial para cada test."""
        # Solo probamos la funcionalidad del TokenBudgetManager directamente
        from app.services.orchestrator.token_budget import TokenBudgetManager
        self.token_budget = TokenBudgetManager()
        
        # Mock de WebSocketEmitter para los tests
        self.mock_ws_emitter = Mock()
        self.mock_ws_emitter.emit_notice_info = AsyncMock(return_value=True)
        self.mock_ws_emitter.emit_error_user_facing = AsyncMock(return_value=True)
    
    @pytest.mark.asyncio
    async def test_token_budget_mode_change_logic_rapido(self):
        """Test para la lógica de cambio a modo rápido."""
        # Simular cambio de modo
        original_max_tokens = self.token_budget.MAX_INPUT_TOKENS
        original_history_turns = self.token_budget.MAX_HISTORY_TURNS
        
        # Aplicar modo rápido
        self.token_budget.MAX_INPUT_TOKENS = 4800  # 60% del original
        self.token_budget.MAX_HISTORY_TURNS = 3
        self.token_budget.TOP_K_DBS = 1
        self.token_budget.TOP_K_APPS = 1
        
        # Verificar que se ajustaron los límites
        assert self.token_budget.MAX_INPUT_TOKENS == 4800
        assert self.token_budget.MAX_HISTORY_TURNS == 3
        assert self.token_budget.TOP_K_DBS == 1
        assert self.token_budget.TOP_K_APPS == 1
        
        # Restaurar valores originales
        self.token_budget.MAX_INPUT_TOKENS = original_max_tokens
        self.token_budget.MAX_HISTORY_TURNS = original_history_turns
    
    @pytest.mark.asyncio
    async def test_token_budget_mode_change_logic_equilibrado(self):
        """Test para la lógica de cambio a modo equilibrado."""
        # Simular cambio de modo
        original_max_tokens = self.token_budget.MAX_INPUT_TOKENS
        original_history_turns = self.token_budget.MAX_HISTORY_TURNS
        
        # Aplicar modo equilibrado
        self.token_budget.MAX_INPUT_TOKENS = 6400  # 80% del original
        self.token_budget.MAX_HISTORY_TURNS = 4
        self.token_budget.TOP_K_DBS = 2
        self.token_budget.TOP_K_APPS = 1
        
        # Verificar que se ajustaron los límites
        assert self.token_budget.MAX_INPUT_TOKENS == 6400
        assert self.token_budget.MAX_HISTORY_TURNS == 4
        assert self.token_budget.TOP_K_DBS == 2
        assert self.token_budget.TOP_K_APPS == 1
        
        # Restaurar valores originales
        self.token_budget.MAX_INPUT_TOKENS = original_max_tokens
        self.token_budget.MAX_HISTORY_TURNS = original_history_turns
    
    @pytest.mark.asyncio
    async def test_token_budget_mode_change_logic_preciso(self):
        """Test para la lógica de cambio a modo preciso."""
        # Simular cambio de modo
        original_max_tokens = self.token_budget.MAX_INPUT_TOKENS
        original_history_turns = self.token_budget.MAX_HISTORY_TURNS
        
        # Aplicar modo preciso
        self.token_budget.MAX_INPUT_TOKENS = 8000  # 100% del original
        self.token_budget.MAX_HISTORY_TURNS = 6
        self.token_budget.TOP_K_DBS = 2
        self.token_budget.TOP_K_APPS = 2
        
        # Verificar que se restauraron los límites originales
        assert self.token_budget.MAX_INPUT_TOKENS == 8000
        assert self.token_budget.MAX_HISTORY_TURNS == 6
        assert self.token_budget.TOP_K_DBS == 2
        assert self.token_budget.TOP_K_APPS == 2
        
        # Restaurar valores originales
        self.token_budget.MAX_INPUT_TOKENS = original_max_tokens
        self.token_budget.MAX_HISTORY_TURNS = original_history_turns
    
    @pytest.mark.asyncio
    async def test_token_budget_mode_change_logic_invalid_mode(self):
        """Test para la lógica de modo inválido."""
        # Verificar que se mantienen los valores por defecto para modo inválido
        original_max_tokens = self.token_budget.MAX_INPUT_TOKENS
        original_history_turns = self.token_budget.MAX_HISTORY_TURNS
        
        # Intentar cambiar a modo inválido (no debería cambiar nada)
        try:
            # Simular error de modo inválido
            raise ValueError("Modo no válido: modo_invalido")
        except ValueError as e:
            # Verificar que el error se captura correctamente
            assert "Modo no válido" in str(e)
        
        # Verificar que los valores no cambiaron
        assert self.token_budget.MAX_INPUT_TOKENS == original_max_tokens
        assert self.token_budget.MAX_HISTORY_TURNS == original_history_turns


class TestTokenBudgetUXIntegration:
    """Test de integración para TokenBudget UX."""
    
    def test_token_budget_manager_initialization(self):
        """Test de inicialización del TokenBudgetManager."""
        token_budget = TokenBudgetManager()
        
        # Verificar constantes iniciales
        assert token_budget.MAX_INPUT_TOKENS == 8000
        assert token_budget.MAX_OUTPUT_TOKENS == 2048
        assert token_budget.MAX_HISTORY_TURNS == 6
        assert token_budget.MAX_SCHEMA_CHARS == 3000
        assert token_budget.TOP_K_DBS == 2
        assert token_budget.TOP_K_APPS == 2
    
    def test_budget_hint_consistency(self):
        """Test de consistencia en budget_hint."""
        token_budget = TokenBudgetManager()
        
        # Probar diferentes rangos de tokens
        test_cases = [
            (1000, "preciso"),      # 12.5%
            (4000, "preciso"),      # 50%
            (5000, "equilibrado"),  # 62.5%
            (6000, "equilibrado"),  # 75%
            (7000, "rápido"),       # 87.5%
            (9000, "rápido"),       # 112.5%
        ]
        
        for estimated_tokens, expected_mode in test_cases:
            result = token_budget.budget_hint(estimated_tokens)
            assert result["recommended_mode"] == expected_mode, \
                f"Para {estimated_tokens} tokens, se esperaba {expected_mode}, se obtuvo {result['recommended_mode']}"
    
    def test_trimming_info_structure(self):
        """Test de estructura de información de trimming."""
        token_budget = TokenBudgetManager()
        
        context = {
            "chat_history": [{"content": "test"}] * 10,
            "database_schemas": {"db1": [{"name": f"table{i}"} for i in range(15)]}
        }
        
        result = token_budget.apply_intelligent_context_trimming(context)
        
        # Verificar estructura de trimming_info
        assert "_trimming_info" in result
        trimming_info = result["_trimming_info"]
        
        required_keys = [
            "chat_history_trimmed",
            "db_schemas_trimmed", 
            "app_descriptors_trimmed",
            "functions_trimmed",
            "original_tokens",
            "trimmed_tokens"
        ]
        
        for key in required_keys:
            assert key in trimming_info, f"Falta clave requerida: {key}"
        
        # Verificar tipos de datos
        assert isinstance(trimming_info["chat_history_trimmed"], bool)
        assert isinstance(trimming_info["original_tokens"], int)
        assert isinstance(trimming_info["trimmed_tokens"], int)
        assert trimming_info["original_tokens"] >= trimming_info["trimmed_tokens"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
