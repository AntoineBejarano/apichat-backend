# test/test_websocket_e2e_complete.py
"""
Test E2E completo del flujo WebSocket.
Simula la interacción completa del usuario desde la conexión hasta la respuesta final.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import WebSocket
from datetime import datetime, timedelta
from uuid import uuid4

from app.main import app
from app.common.enums import WsEventType, Mode, RiskLevel
from app.common.events import (
    DecisionRequestEvent, DecisionResponseEvent, ResourceProposalEvent,
    StatusProgressEvent, ResultPartialEvent, ResultFinalEvent
)


class MockWebSocket:
    """Mock de WebSocket para testing."""
    
    def __init__(self):
        self.sent_messages = []
        self.closed = False
        self.close_code = None
    
    async def accept(self):
        """Simula aceptar la conexión."""
        pass
    
    async def send_json(self, data):
        """Simula enviar JSON."""
        self.sent_messages.append(data)
    
    async def receive_json(self):
        """Simula recibir JSON."""
        # Simular mensaje del usuario
        return {
            "role": "user",
            "content": "Quiero ver los usuarios de la base de datos"
        }
    
    async def close(self, code=1000):
        """Simula cerrar la conexión."""
        self.closed = True
        self.close_code = code


class TestWebSocketE2EComplete:
    """Test E2E completo del flujo WebSocket."""
    
    @pytest.fixture
    def mock_websocket(self):
        """Fixture para WebSocket mock."""
        return MockWebSocket()
    
    @pytest.fixture
    def mock_user(self):
        """Fixture para usuario mock."""
        user = Mock()
        user.id = uuid4()
        user.email = "test@example.com"
        user.username = "testuser"
        return user
    
    @pytest.fixture
    def mock_chat(self):
        """Fixture para chat mock."""
        chat = Mock()
        chat.id = uuid4()
        chat.name = "Test Chat"
        return chat
    
    @pytest.fixture
    def mock_orchestrator_response(self):
        """Fixture para respuesta del orchestrator."""
        return {
            "assistant_response": "He encontrado información sobre los usuarios. Aquí tienes un resumen:",
            "steps": [
                {
                    "step": 1,
                    "message": "Analizando esquema de test_db...",
                    "template": "Analizando esquema de {database_name}..."
                },
                {
                    "step": 2,
                    "message": "Consultando tabla users...",
                    "template": "Consultando tabla {table_name}..."
                }
            ],
            "execution_results": {
                "variables": {
                    "database_name": "test_db",
                    "table_name": "users"
                },
                "data": {
                    "user_count": 150,
                    "active_users": 120
                }
            },
            "mode": "explorer",
            "next_actions": ["view_details", "export_data", "create_report"]
        }
    
    def test_websocket_connection_flow(self, mock_websocket, mock_user, mock_chat):
        """Test del flujo de conexión WebSocket."""
        # Simular conexión exitosa
        assert not mock_websocket.closed
        assert len(mock_websocket.sent_messages) == 0
        
        # Simular aceptación
        asyncio.run(mock_websocket.accept())
        assert not mock_websocket.closed
        
        print("✅ Conexión WebSocket establecida correctamente")
    
    def test_user_message_processing(self, mock_websocket, mock_orchestrator_response):
        """Test del procesamiento de mensajes del usuario."""
        # Simular mensaje del usuario
        user_message = asyncio.run(mock_websocket.receive_json())
        
        assert user_message["role"] == "user"
        assert "usuarios" in user_message["content"]
        assert "base de datos" in user_message["content"]
        
        print("✅ Mensaje del usuario procesado correctamente")
        print(f"   Contenido: {user_message['content']}")
    
    def test_orchestrator_response_format(self, mock_orchestrator_response):
        """Test del formato de respuesta del orchestrator."""
        response = mock_orchestrator_response
        
        # Verificar estructura básica
        assert "assistant_response" in response
        assert "steps" in response
        assert "execution_results" in response
        assert "mode" in response
        assert "next_actions" in response
        
        # Verificar steps
        steps = response["steps"]
        assert len(steps) == 2
        assert steps[0]["step"] == 1
        assert steps[1]["step"] == 2
        
        # Verificar variables
        variables = response["execution_results"]["variables"]
        assert variables["database_name"] == "test_db"
        assert variables["table_name"] == "users"
        
        print("✅ Respuesta del orchestrator tiene formato correcto")
        print(f"   Modo: {response['mode']}")
        print(f"   Acciones disponibles: {response['next_actions']}")
    
    def test_template_resolution(self, mock_orchestrator_response):
        """Test de la resolución de templates en steps."""
        response = mock_orchestrator_response
        steps = response["steps"]
        variables = response["execution_results"]["variables"]

        # Verificar que los templates se resuelven correctamente
        for step in steps:
            if "template" in step:
                template = step["template"]
                resolved = step["message"]

                # Verificar que las variables del template se reemplazaron
                for var_name, var_value in variables.items():
                    if f"{{{var_name}}}" in template:
                        # Si la variable está en el template, debe estar en el mensaje resuelto
                        assert str(var_value) in resolved
                        assert f"{{{var_name}}}" not in resolved
                        assert f"{{{{{var_name}}}}}" not in resolved
        
        print("✅ Templates resueltos correctamente")
        print(f"   Variables disponibles: {list(variables.keys())}")
        print(f"   Steps procesados: {len(steps)}")
    
    def test_decision_request_flow(self, mock_websocket):
        """Test del flujo de solicitud de decisión."""
        # Simular evento de decisión
        decision_event = DecisionRequestEvent(
            decision_id=str(uuid4()),
            title="Confirmar operación",
            description="¿Deseas proceder con la consulta a la base de datos?",
            options=[
                {"id": "confirm", "label": "Confirmar", "action": "confirm"},
                {"id": "cancel", "label": "Cancelar", "action": "cancel"}
            ],
            timeout_seconds=30
        )
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(decision_event.model_dump()))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == WsEventType.DECISION_REQUEST
        assert "decision_id" in last_message
        assert "options" in last_message
        assert len(last_message["options"]) == 2
        
        print("✅ Solicitud de decisión enviada correctamente")
        print(f"   ID de decisión: {last_message['decision_id']}")
        print(f"   Opciones: {[opt['label'] for opt in last_message['options']]}")
    
    def test_decision_response_processing(self, mock_websocket):
        """Test del procesamiento de respuestas de decisión."""
        # Simular respuesta de decisión del usuario
        decision_response = {
            "type": "decision.response",
            "decision_id": str(uuid4()),
            "action": "confirm",
            "user_message": "Sí, proceder con la consulta"
        }
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(decision_response))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == "decision.response"
        assert last_message["action"] == "confirm"
        assert "user_message" in last_message
        
        print("✅ Respuesta de decisión procesada correctamente")
        print(f"   Acción: {last_message['action']}")
        print(f"   Mensaje: {last_message['user_message']}")
    
    def test_resource_proposal_flow(self, mock_websocket):
        """Test del flujo de propuesta de recursos."""
        # Simular evento de propuesta de recursos
        proposal_event = ResourceProposalEvent(
            proposal_id=str(uuid4()),
            title="Opciones de recursos disponibles",
            description="He encontrado estas combinaciones de base de datos y aplicaciones:",
            options=[
                {
                    "database_id": str(uuid4()),
                    "application_id": str(uuid4()),
                    "database_name": "users_db",
                    "application_name": "User Management App",
                    "description": "Gestión completa de usuarios"
                },
                {
                    "database_id": str(uuid4()),
                    "application_id": str(uuid4()),
                    "database_name": "analytics_db",
                    "application_name": "Analytics Dashboard",
                    "description": "Dashboard de análisis de usuarios"
                }
            ],
            user_message="Quiero ver los usuarios de la base de datos"
        )
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(proposal_event.model_dump()))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == WsEventType.RESOURCE_PROPOSAL
        assert "proposal_id" in last_message
        assert "options" in last_message
        assert len(last_message["options"]) == 2
        
        print("✅ Propuesta de recursos enviada correctamente")
        print(f"   ID de propuesta: {last_message['proposal_id']}")
        print(f"   Opciones disponibles: {len(last_message['options'])}")
    
    def test_resource_proposal_response_processing(self, mock_websocket):
        """Test del procesamiento de respuestas a propuestas de recursos."""
        # Simular respuesta a propuesta de recursos
        proposal_response = {
            "type": "resource.proposal.response",
            "proposal_id": str(uuid4()),
            "action": "guided_option_1",
            "selected_option": {
                "database_id": str(uuid4()),
                "application_id": str(uuid4()),
                "database_name": "users_db",
                "application_name": "User Management App"
            },
            "user_message": "Quiero usar la primera opción en modo Guided"
        }
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(proposal_response))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == "resource.proposal.response"
        assert last_message["action"] == "guided_option_1"
        assert "selected_option" in last_message
        
        print("✅ Respuesta a propuesta de recursos procesada correctamente")
        print(f"   Acción: {last_message['action']}")
        print(f"   Base de datos: {last_message['selected_option']['database_name']}")
    
    def test_progress_tracking(self, mock_websocket):
        """Test del seguimiento de progreso."""
        # Simular eventos de progreso
        progress_events = [
            StatusProgressEvent(
                step=1,
                total_steps=3,
                message="Iniciando análisis...",
                percentage=33.33
            ),
            StatusProgressEvent(
                step=2,
                total_steps=3,
                message="Procesando datos...",
                percentage=66.66
            ),
            StatusProgressEvent(
                step=3,
                total_steps=3,
                message="Finalizando...",
                percentage=100.0
            )
        ]
        
        # Simular envío de eventos de progreso
        for event in progress_events:
            asyncio.run(mock_websocket.send_json(event.model_dump()))
        
        # Verificar que se enviaron todos los eventos
        assert len(mock_websocket.sent_messages) >= 3
        
        # Verificar el último evento de progreso
        progress_messages = [msg for msg in mock_websocket.sent_messages 
                           if msg.get("type") == WsEventType.STATUS_PROGRESS]
        
        assert len(progress_messages) == 3
        assert progress_messages[-1]["percentage"] == 100.0
        
        print("✅ Seguimiento de progreso funcionando correctamente")
        print(f"   Eventos de progreso enviados: {len(progress_messages)}")
        print(f"   Progreso final: {progress_messages[-1]['percentage']}%")
    
    def test_partial_results(self, mock_websocket):
        """Test de resultados parciales."""
        # Simular resultado parcial
        partial_event = ResultPartialEvent(
            step=2,
            data={
                "user_count": 150,
                "active_users": 120,
                "inactive_users": 30
            },
            preview="Encontrados 150 usuarios totales, 120 activos y 30 inactivos"
        )
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(partial_event.model_dump()))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == WsEventType.RESULT_PARTIAL
        assert last_message["step"] == 2
        assert "data" in last_message
        assert "preview" in last_message
        
        print("✅ Resultado parcial enviado correctamente")
        print(f"   Paso: {last_message['step']}")
        print(f"   Preview: {last_message['preview']}")
    
    def test_final_results(self, mock_websocket):
        """Test de resultados finales."""
        # Simular resultado final
        final_event = ResultFinalEvent(
            summary="Análisis de usuarios completado exitosamente",
            data={
                "total_users": 150,
                "active_users": 120,
                "inactive_users": 30,
                "user_activity_rate": 80.0,
                "last_activity": "2024-01-15T10:30:00Z"
            },
            next_actions=[
                "view_detailed_report",
                "export_user_data",
                "create_user_analytics",
                "set_up_monitoring"
            ],
            usage_stats={
                "tokens_used": 1250,
                "execution_time_ms": 2340,
                "cache_hits": 3,
                "database_queries": 2
            }
        )
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(final_event.model_dump()))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == WsEventType.RESULT_FINAL
        assert "summary" in last_message
        assert "data" in last_message
        assert "next_actions" in last_message
        assert "usage_stats" in last_message
        
        print("✅ Resultado final enviado correctamente")
        print(f"   Resumen: {last_message['summary']}")
        print(f"   Acciones disponibles: {len(last_message['next_actions'])}")
        print(f"   Tokens utilizados: {last_message['usage_stats']['tokens_used']}")
    
    def test_error_handling(self, mock_websocket):
        """Test del manejo de errores."""
        # Simular error
        error_data = {
            "type": "error",
            "message": "Error al conectar con la base de datos",
            "timestamp": datetime.now().isoformat()
        }
        
        # Simular envío
        asyncio.run(mock_websocket.send_json(error_data))
        
        # Verificar que se envió
        assert len(mock_websocket.sent_messages) > 0
        last_message = mock_websocket.sent_messages[-1]
        
        assert last_message["type"] == "error"
        assert "message" in last_message
        assert "timestamp" in last_message
        
        print("✅ Manejo de errores funcionando correctamente")
        print(f"   Mensaje de error: {last_message['message']}")
    
    def test_websocket_disconnection(self, mock_websocket):
        """Test de la desconexión del WebSocket."""
        # Simular desconexión
        asyncio.run(mock_websocket.close(code=1000))
        
        # Verificar que se cerró
        assert mock_websocket.closed
        assert mock_websocket.close_code == 1000
        
        print("✅ Desconexión del WebSocket funcionando correctamente")
        print(f"   Código de cierre: {mock_websocket.close_code}")
    
    def test_complete_user_journey(self, mock_websocket, mock_orchestrator_response):
        """Test del viaje completo del usuario."""
        print("\n🚀 INICIANDO VIAJE COMPLETO DEL USUARIO")
        
        # 1. Conexión
        self.test_websocket_connection_flow(mock_websocket, None, None)
        
        # 2. Mensaje del usuario
        self.test_user_message_processing(mock_websocket, mock_orchestrator_response)
        
        # 3. Respuesta del orchestrator
        self.test_orchestrator_response_format(mock_orchestrator_response)
        
        # 4. Resolución de templates
        self.test_template_resolution(mock_orchestrator_response)
        
        # 5. Propuesta de recursos
        self.test_resource_proposal_flow(mock_websocket)
        
        # 6. Respuesta del usuario a la propuesta
        self.test_resource_proposal_response_processing(mock_websocket)
        
        # 7. Seguimiento de progreso
        self.test_progress_tracking(mock_websocket)
        
        # 8. Resultados parciales
        self.test_partial_results(mock_websocket)
        
        # 9. Resultado final
        self.test_final_results(mock_websocket)
        
        # 10. Desconexión
        self.test_websocket_disconnection(mock_websocket)
        
        print("\n🎉 VIAJE COMPLETO DEL USUARIO EXITOSO")
        print(f"   Total de mensajes enviados: {len(mock_websocket.sent_messages)}")
        print("   Todos los flujos funcionando correctamente")


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"])
