import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from app.services.orchestrator_service import OrchestratorService
from app.core.service_factory import ServiceFactory


class TestOrchestratorResponse:
    """Test para verificar que el query_result llega correctamente al usuario"""
    
    @pytest.fixture
    def mock_factory(self):
        """Mock del ServiceFactory"""
        factory = Mock(spec=ServiceFactory)
        
        # Mock de la base de datos
        mock_db = Mock()
        factory.db = mock_db
        
        # Mock del usuario
        mock_user = Mock()
        mock_user.id = "test-user-123"
        factory.user = mock_user
        
        # Mock del ExecutionEngineService
        mock_execution_engine = Mock()
        mock_execution_engine.execute_plan.return_value = {
            "variables": {
                "query_result": {
                    "result": [
                        {"id": 1, "name": "Club A", "status": "active"},
                        {"id": 2, "name": "Club B", "status": "pending"},
                        {"id": 3, "name": "Club C", "status": "active"},
                        {"id": 4, "name": "Club D", "status": "rejected"},
                        {"id": 5, "name": "Club E", "status": "active"}
                    ],
                    "count": 5,
                    "query_time": "0.023s"
                }
            },
            "executed_strategy_id": "test-strategy-123"
        }
        factory.get_execution_engine_service.return_value = mock_execution_engine
        
        # Mock del ChatHistoryService
        mock_chat_service = Mock()
        mock_chat_service.save_assistant_message_async = AsyncMock()
        factory.get_chat_history_service.return_value = mock_chat_service
        
        # Mock del OpenAIService
        mock_openai = Mock()
        mock_openai.generate_plan.return_value = {
            "actions": [
                {
                    "type": "db_query",
                    "sql": "SELECT * FROM clubs WHERE status = 'active'",
                    "database_id": "test-db-123"
                }
            ],
            "steps": [
                {
                    "type": "step",
                    "message": "Consultando base de datos para obtener la información solicitada",
                    "status": "in_progress"
                },
                {
                    "type": "step", 
                    "message": "Resultados obtenidos: {query_result}",
                    "status": "pending",
                    "depends_on": "query_result",
                    "template": "Resultados obtenidos: {query_result}"
                }
            ]
        }
        factory.get_openai_service.return_value = mock_openai
        
        return factory
    
    @pytest.fixture
    def orchestrator(self, mock_factory):
        """Instancia del OrchestratorService con mocks"""
        return OrchestratorService(mock_factory)
    
    @pytest.mark.asyncio
    async def test_query_result_reaches_user(self, orchestrator, mock_factory):
        """
        Test principal: verificar que el query_result llega correctamente al usuario
        """
        # Simular mensaje del usuario
        user_message = "¿Qué clubs activos tienes?"
        chat_id = "test-chat-123"
        user_id = "test-user-123"
        
        # Ejecutar el flujo completo
        result = await orchestrator.handle_user_message(
            user_message=user_message,
            chat_id=chat_id,
            user_id=user_id
        )
        
        # 🔍 DEBUG: Imprimir el resultado completo
        print(f"\n🔍 RESULTADO COMPLETO:")
        print(f"Tipo: {result.get('type')}")
        print(f"Message: {result.get('message')}")
        print(f"Steps count: {len(result.get('steps', []))}")
        print(f"Execution results keys: {list(result.get('execution_results', {}).keys())}")
        
        # Verificar que la respuesta es tipo "step"
        assert result["type"] == "step", f"La respuesta debería ser tipo 'step', pero es: {result['type']}"
        
        # Verificar que hay steps
        assert "steps" in result, "La respuesta debería contener steps"
        assert len(result["steps"]) > 0, "Debería haber al menos un step"
        
        # Verificar que el message contiene información útil (no solo "Consultando...")
        message = result["message"]
        print(f"\n🔍 MESSAGE FIELD: '{message}'")
        
        # El message debería contener información del query_result, no solo "Consultando..."
        assert "Consultando base de datos" not in message, f"El message no debería ser solo 'Consultando...', es: {message}"
        
        # Verificar que el message contiene información de los resultados
        assert "Resultados obtenidos" in message, f"El message debería contener 'Resultados obtenidos', es: {message}"
        assert "Club A" in message, f"El message debería contener información de los clubs, es: {message}"
        
        # Verificar que solo se muestran los primeros 3 valores
        assert "Club D" not in message, "El message no debería contener el 4to club (Club D)"
        assert "Club E" not in message, "El message no debería contener el 5to club (Club E)"
        assert "... y 2 más" in message, "El message debería indicar que hay más resultados"
        
        # Verificar que execution_results contiene las variables
        execution_results = result.get("execution_results", {})
        assert "variables" in execution_results, "execution_results debería contener variables"
        assert "query_result" in execution_results["variables"], "variables debería contener query_result"
        
        print(f"\n✅ TEST EXITOSO: El query_result llega correctamente al usuario")
        print(f"✅ Message formateado: {message}")
    
    @pytest.mark.asyncio
    async def test_extract_assistant_response_with_query_result(self, orchestrator):
        """
        Test específico para _extract_assistant_response con query_result
        """
        # Simular execution_results con query_result
        execution_results = {
            "variables": {
                "query_result": {
                    "result": [
                        {"id": 1, "name": "Club A"},
                        {"id": 2, "name": "Club B"},
                        {"id": 3, "name": "Club C"},
                        {"id": 4, "name": "Club D"}
                    ]
                }
            }
        }
        
        # Llamar directamente a _extract_assistant_response
        result = orchestrator._extract_assistant_response(execution_results)
        
        print(f"\n🔍 RESULTADO DE _extract_assistant_response:")
        print(f"Resultado: {result}")
        print(f"Tipo: {type(result)}")
        print(f"Longitud: {len(str(result))}")
        
        # Verificar que el resultado está formateado correctamente
        assert "Resultados obtenidos" in result, "El resultado debería contener 'Resultados obtenidos'"
        assert "Club A" in result, "El resultado debería contener Club A"
        assert "Club B" in result, "El resultado debería contener Club B"
        assert "Club C" in result, "El resultado debería contener Club C"
        assert "Club D" not in result, "El resultado NO debería contener Club D (solo primeros 3)"
        assert "... y 1 más" in result, "Debería indicar que hay más resultados"
        
        print(f"\n✅ TEST EXITOSO: _extract_assistant_response formatea correctamente el query_result")
    
    @pytest.mark.asyncio
    async def test_minimal_plan_generation(self, orchestrator):
        """
        Test para verificar que el plan mínimo se genera correctamente
        """
        user_message = "¿Cuántos usuarios activos hay?"
        
        # Generar plan mínimo
        plan = orchestrator._generate_minimal_plan_for_db_intention(user_message, ["test-db-123"])
        
        print(f"\n🔍 PLAN MÍNIMO GENERADO:")
        print(f"Actions: {plan.get('actions')}")
        print(f"Steps: {plan.get('steps')}")
        
        # Verificar que el plan tiene la estructura correcta
        assert "actions" in plan, "El plan debería tener actions"
        assert "steps" in plan, "El plan debería tener steps"
        assert len(plan["actions"]) > 0, "Debería haber al menos una acción"
        assert len(plan["steps"]) > 0, "Debería haber al menos un step"
        
        # Verificar que el primer step no contiene el mensaje del usuario
        first_step = plan["steps"][0]
        assert "Consultando base de datos para obtener la información solicitada" in first_step["message"], "El primer step debería tener un mensaje genérico"
        assert user_message not in first_step["message"], "El primer step NO debería contener el mensaje del usuario"
        
        # Verificar que el segundo step tiene el template correcto
        if len(plan["steps"]) > 1:
            second_step = plan["steps"][1]
            assert "{query_result}" in second_step["template"], "El segundo step debería tener template con {query_result}"
            assert "Resultados obtenidos" in second_step["template"], "El template debería contener 'Resultados obtenidos'"
        
        print(f"\n✅ TEST EXITOSO: El plan mínimo se genera correctamente")


if __name__ == "__main__":
    # Ejecutar los tests
    pytest.main([__file__, "-v", "-s"])
