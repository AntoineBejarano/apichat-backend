"""
🔧 FASE 7: Test del ReAct Orchestrator
──────────────────────────────────────
Verifica que el ReAct Orchestrator simplificado funciona correctamente.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from app.services.react_orchestrator import ReActOrchestrator


class TestPhase7ReActOrchestrator:
    """Test de la FASE 7: ReAct Orchestrator"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        factory = Mock()
        factory.user = Mock()
        factory.user.id = uuid4()
        return factory
    
    @pytest.fixture
    def mock_langchain_service(self):
        """LangchainService mock"""
        service = Mock()
        service.llm = Mock()
        service.llm.ainvoke = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_exploration_graph(self):
        """ExplorationGraph mock"""
        graph = Mock()
        graph.run = AsyncMock(return_value={"content": "Exploración completada"})
        return graph
    
    @pytest.fixture
    def mock_guided_graph(self):
        """GuidedGraph mock"""
        graph = Mock()
        graph.run = AsyncMock(return_value={"content": "Guía completada"})
        return graph
    
    @pytest.fixture
    def react_orchestrator(self, mock_factory, mock_langchain_service, mock_exploration_graph, mock_guided_graph):
        """Instancia de ReActOrchestrator para testing"""
        orchestrator = ReActOrchestrator(mock_factory)
        
        # Mock de los servicios
        orchestrator.langchain_service = mock_langchain_service
        orchestrator.exploration_graph = mock_exploration_graph
        orchestrator.guided_graph = mock_guided_graph
        
        # Mock del chat history service
        mock_chat_history_service = Mock()
        mock_chat_history_service.create_chat_history = AsyncMock()
        mock_factory.get_chat_history_service.return_value = mock_chat_history_service
        
        # Mock del execution engine service
        mock_execution_service = Mock()
        mock_execution_service._run_db_query = AsyncMock(return_value={"content": "SQL ejecutado"})
        mock_factory.get_execution_engine_service.return_value = mock_execution_service
        
        return orchestrator
    
    def test_react_orchestrator_initialization(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que el ReAct Orchestrator se inicializa correctamente"""
        assert react_orchestrator is not None
        assert hasattr(react_orchestrator, 'handle_message')
        assert hasattr(react_orchestrator, '_think')
        assert hasattr(react_orchestrator, '_act')
        assert hasattr(react_orchestrator, '_observe')
        
        # Verificar configuración ReAct
        assert react_orchestrator.max_iterations == 5
        assert "THINK" in react_orchestrator.thinking_prompt
        assert "ACT" in react_orchestrator.thinking_prompt
        assert "OBSERVE" in react_orchestrator.thinking_prompt
        
        print("✅ ReActOrchestrator se inicializa correctamente")
    
    def test_react_orchestrator_methods_exist(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que todos los métodos necesarios existen"""
        required_methods = [
            'handle_message',
            '_think',
            '_act', 
            '_observe',
            '_execute_exploration_graph',
            '_execute_guided_graph',
            '_execute_sql_direct',
            '_is_satisfactory_result',
            '_is_complete',
            '_build_final_response',
            '_save_reasoning_step'
        ]
        
        for method_name in required_methods:
            assert hasattr(react_orchestrator, method_name), f"Método {method_name} no encontrado"
            method = getattr(react_orchestrator, method_name)
            assert callable(method), f"Método {method_name} no es callable"
        
        print("✅ Todos los métodos requeridos existen en ReActOrchestrator")
    
    @pytest.mark.asyncio
    async def test_think_method_parses_json_correctly(self, react_orchestrator, mock_langchain_service):
        """🔧 FASE 7: Test que verifica que el método _think parsea JSON correctamente"""
        # Mock de respuesta del LLM
        mock_response = Mock()
        mock_response.content = '{"action": "explore", "reasoning": "Necesito explorar la BD", "sql": null, "context_needed": "Ninguno"}'
        mock_langchain_service.llm.ainvoke.return_value = mock_response
        
        context = {
            "message": "¿Cuántos usuarios tengo?",
            "db_ids": ["db1", "db2"],
            "app_ids": [],
            "explorer": True,
            "iteration": 1,
            "history": [],
            "results": []
        }
        
        thought = await react_orchestrator._think(context)
        
        assert thought is not None
        assert thought["action"] == "explore"
        assert thought["reasoning"] == "Necesito explorar la BD"
        assert thought["sql"] is None
        assert thought["context_needed"] == "Ninguno"
        
        print("✅ Método _think parsea JSON correctamente")
    
    @pytest.mark.asyncio
    async def test_act_method_executes_exploration_graph(self, react_orchestrator, mock_exploration_graph):
        """🔧 FASE 7: Test que verifica que el método _act ejecuta ExplorationGraph"""
        thought = {
            "action": "explore",
            "reasoning": "Necesito explorar la BD",
            "sql": None,
            "context_needed": "Ninguno"
        }
        
        context = {
            "chat_id": "chat1",
            "message": "¿Cuántos usuarios tengo?",
            "db_ids": ["db1"],
            "app_ids": []
        }
        
        result = await react_orchestrator._act(thought, context)
        
        assert result is not None
        assert result["content"] == "Exploración completada"
        mock_exploration_graph.run.assert_called_once()
        
        print("✅ Método _act ejecuta ExplorationGraph correctamente")
    
    @pytest.mark.asyncio
    async def test_act_method_executes_guided_graph(self, react_orchestrator, mock_guided_graph):
        """🔧 FASE 7: Test que verifica que el método _act ejecuta GuidedGraph"""
        thought = {
            "action": "guide",
            "reasoning": "Necesito guía específica",
            "sql": None,
            "context_needed": "Ninguno"
        }
        
        context = {
            "chat_id": "chat1",
            "message": "¿Cuántos usuarios tengo?",
            "db_ids": ["db1"],
            "app_ids": []
        }
        
        result = await react_orchestrator._act(thought, context)
        
        assert result is not None
        assert result["content"] == "Guía completada"
        mock_guided_graph.run.assert_called_once()
        
        print("✅ Método _act ejecuta GuidedGraph correctamente")
    
    @pytest.mark.asyncio
    async def test_observe_method_updates_context(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que el método _observe actualiza el contexto"""
        context = {
            "iteration": 1,
            "history": [],
            "results": []
        }
        
        result = {"content": "Resultado exitoso"}
        
        updated_context = await react_orchestrator._observe(result, context)
        
        assert len(updated_context["results"]) == 1
        assert len(updated_context["history"]) == 1
        assert updated_context["results"][0] == result
        assert updated_context["history"][0]["action"] == "executed"
        
        print("✅ Método _observe actualiza el contexto correctamente")
    
    def test_is_satisfactory_result_method(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que el método _is_satisfactory_result funciona"""
        # Resultado satisfactorio
        good_result = {"content": "Contenido útil"}
        assert react_orchestrator._is_satisfactory_result(good_result) is True
        
        # Resultado con error
        bad_result = {"error": "Algo salió mal"}
        assert react_orchestrator._is_satisfactory_result(bad_result) is False
        
        # Resultado vacío
        empty_result = {}
        assert react_orchestrator._is_satisfactory_result(empty_result) is False
        
        print("✅ Método _is_satisfactory_result funciona correctamente")
    
    def test_is_complete_method(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que el método _is_complete funciona"""
        # Contexto incompleto
        incomplete_context = {
            "iteration": 1,
            "satisfactory": False,
            "results": []
        }
        assert react_orchestrator._is_complete(incomplete_context) is False
        
        # Contexto completo por satisfacción
        satisfied_context = {
            "iteration": 1,
            "satisfactory": True,
            "results": ["resultado"]
        }
        assert react_orchestrator._is_complete(satisfied_context) is True
        
        # Contexto completo por iteraciones máximas
        max_iterations_context = {
            "iteration": 5,
            "satisfactory": False,
            "results": []
        }
        assert react_orchestrator._is_complete(max_iterations_context) is True
        
        print("✅ Método _is_complete funciona correctamente")
    
    def test_build_final_response_method(self, react_orchestrator):
        """🔧 FASE 7: Test que verifica que el método _build_final_response funciona"""
        context = {
            "iteration": 2,
            "db_ids": ["db1"],
            "app_ids": [],
            "explorer": True,
            "history": [{"action": "executed", "result": "test"}],
            "results": [{"content": "Respuesta final"}]
        }
        
        response_time = 1500
        
        final_response = react_orchestrator._build_final_response(context, response_time)
        
        assert final_response["content"] == "Respuesta final"
        assert final_response["source"] == "react_orchestrator"
        assert final_response["iterations"] == 2
        assert final_response["response_time_ms"] == 1500
        assert final_response["method"] == "react_hybrid"
        assert "react_history" in final_response
        
        print("✅ Método _build_final_response funciona correctamente")


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
