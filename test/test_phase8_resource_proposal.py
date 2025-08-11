# test/test_phase8_resource_proposal.py
"""
Tests para la Fase 8: Explorer propone combinaciones y salto a Guided.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.services.execution.resource_selector_service import ResourceSelectorService
from app.common.events import ResourceProposalEvent, ResourceProposalResponseEvent
from app.common.enums import WsEventType


class TestResourceSelectorService:
    """Tests para ResourceSelectorService.propose_for_explorer."""
    
    @pytest.fixture
    def resource_selector(self):
        """Fixture para ResourceSelectorService."""
        return ResourceSelectorService()
    
    @pytest.fixture
    def mock_dbs(self):
        """Mock de bases de datos para testing."""
        return [
            {
                'id': 'db1',
                'name': 'Test Database 1',
                'description': 'Base de datos de prueba 1',
                'table_count': 50,
                'size_mb': 100,
                'last_updated': '2024-01-01T00:00:00Z',
                'is_readonly': True,
                'has_comments': True,
                'has_constraints': True,
                'has_indexes': True
            },
            {
                'id': 'db2',
                'name': 'Test Database 2',
                'description': 'Base de datos de prueba 2',
                'table_count': 25,
                'size_mb': 50,
                'last_updated': '2024-01-02T00:00:00Z',
                'is_readonly': False,
                'has_comments': False,
                'has_constraints': True,
                'has_indexes': False
            }
        ]
    
    @pytest.fixture
    def mock_apps(self):
        """Mock de aplicaciones para testing."""
        return [
            {
                'id': 'app1',
                'name': 'Test App 1',
                'description': 'Aplicación de prueba 1',
                'api_count': 30,
                'last_updated': '2024-01-01T00:00:00Z',
                'requires_auth': True,
                'has_rate_limiting': True,
                'has_openapi_spec': True,
                'has_examples': True,
                'has_descriptions': True
            },
            {
                'id': 'app2',
                'name': 'Test App 2',
                'description': 'Aplicación de prueba 2',
                'api_count': 15,
                'last_updated': '2024-01-02T00:00:00Z',
                'requires_auth': False,
                'has_rate_limiting': False,
                'has_openapi_spec': False,
                'has_examples': False,
                'has_descriptions': False
            }
        ]
    
    @pytest.mark.asyncio
    async def test_propose_for_explorer_returns_top_2_combinations(self, resource_selector, mock_dbs, mock_apps):
        """Test que verifica que propose_for_explorer devuelve top-2 combinaciones."""
        prompt = "Buscar usuarios activos en la base de datos"
        
        proposals = await resource_selector.propose_for_explorer(prompt, mock_dbs, mock_apps)
        
        # Debe devolver exactamente 2 propuestas
        assert len(proposals) == 2
        
        # Cada propuesta debe tener la estructura correcta
        for proposal in proposals:
            assert 'database' in proposal
            assert 'application' in proposal
            assert 'combined_score' in proposal
            assert 'selection_reasons' in proposal
            assert 'confidence' in proposal
            
            # Verificar estructura de database
            db = proposal['database']
            assert 'id' in db
            assert 'name' in db
            assert 'score' in db
            assert 'reasons' in db
            assert 'metadata' in db
            
            # Verificar estructura de application
            app = proposal['application']
            assert 'id' in app
            assert 'name' in app
            assert 'score' in app
            assert 'reasons' in app
            assert 'metadata' in app
    
    @pytest.mark.asyncio
    async def test_propose_for_explorer_orders_by_combined_score(self, resource_selector, mock_dbs, mock_apps):
        """Test que verifica que las propuestas están ordenadas por score combinado."""
        prompt = "Analizar datos de ventas"
        
        proposals = await resource_selector.propose_for_explorer(prompt, mock_dbs, mock_apps)
        
        # Las propuestas deben estar ordenadas por score descendente
        assert len(proposals) >= 2
        assert proposals[0]['combined_score'] >= proposals[1]['combined_score']
    
    @pytest.mark.asyncio
    async def test_propose_for_explorer_handles_empty_resources(self, resource_selector):
        """Test que verifica el manejo de recursos vacíos."""
        prompt = "Buscar información"
        
        proposals = await resource_selector.propose_for_explorer(prompt, [], [])
        
        # Debe devolver lista vacía si no hay recursos
        assert proposals == []
    
    @pytest.mark.asyncio
    async def test_propose_for_explorer_handles_partial_resources(self, resource_selector, mock_dbs, mock_apps):
        """Test que verifica el manejo cuando solo hay DBs o solo Apps."""
        prompt = "Consultar datos"
        
        # Solo DBs
        proposals_db_only = await resource_selector.propose_for_explorer(prompt, mock_dbs, [])
        assert proposals_db_only == []
        
        # Solo Apps
        proposals_app_only = await resource_selector.propose_for_explorer(prompt, [], mock_apps)
        assert proposals_app_only == []


class TestResourceProposalEvents:
    """Tests para los eventos de propuesta de recursos."""
    
    def test_resource_proposal_event_structure(self):
        """Test que verifica la estructura del evento ResourceProposalEvent."""
        event = ResourceProposalEvent(
            proposal_id="proposal_123",
            title="¿Usar modo Guided?",
            description="He encontrado recursos útiles",
            options=[
                {
                    "id": "guided_option_1",
                    "label": "Opción 1",
                    "description": "Primera opción",
                    "action": "guided_option_1"
                }
            ],
            user_message="Buscar usuarios activos",
            timeout_seconds=60,
            default_action="explore_only"
        )
        
        assert event.type == WsEventType.RESOURCE_PROPOSAL
        assert event.proposal_id == "proposal_123"
        assert event.title == "¿Usar modo Guided?"
        assert len(event.options) == 1
        assert event.user_message == "Buscar usuarios activos"
        assert event.timeout_seconds == 60
        assert event.default_action == "explore_only"
    
    def test_resource_proposal_response_event_structure(self):
        """Test que verifica la estructura del evento ResourceProposalResponseEvent."""
        event = ResourceProposalResponseEvent(
            proposal_id="proposal_123",
            action="guided_option_1",
            selected_option={
                "database_id": "db1",
                "application_id": "app1"
            },
            user_message="Sí, usar esa opción"
        )
        
        assert event.type == WsEventType.RESOURCE_PROPOSAL_RESPONSE
        assert event.proposal_id == "proposal_123"
        assert event.action == "guided_option_1"
        assert event.selected_option["database_id"] == "db1"
        assert event.selected_option["application_id"] == "app1"
        assert event.user_message == "Sí, usar esa opción"


class TestExplorationGraphIntegration:
    """Tests de integración para ExplorationGraph con propuestas de recursos."""
    
    @pytest.mark.asyncio
    async def test_should_propose_resources_detects_task_intent(self):
        """Test que verifica la detección de intenciones de tarea."""
        from app.services.execution.graphs.exploration_graph import ExplorationGraph
        
        # Mock factory
        mock_factory = Mock()
        graph = ExplorationGraph(mock_factory)
        
        # Mensajes que deberían proponer recursos
        task_messages = [
            "Buscar usuarios activos en la base de datos",
            "Crear un reporte de ventas",
            "Actualizar información del cliente",
            "Generar estadísticas de uso",
            "¿Puedes ayudarme a encontrar datos?"
        ]
        
        for message in task_messages:
            assert graph._should_propose_resources(message) == True, f"Debería proponer para: {message}"
        
        # Mensajes que NO deberían proponer recursos
        exploration_messages = [
            "Qué hay en la base de datos",
            "Explora las tablas disponibles",
            "Muéstrame la estructura",
            "Navega por los datos"
        ]
        
        for message in exploration_messages:
            assert graph._should_propose_resources(message) == False, f"No debería proponer para: {message}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
