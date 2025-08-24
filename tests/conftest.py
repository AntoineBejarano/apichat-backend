"""
🧪 CONFIGURACIÓN PRINCIPAL DE PYTEST - SISTEMA EXPLORER/GUIDED

Este archivo contiene la configuración global de pytest, fixtures compartidas,
y setup del entorno de testing para el sistema Explorer/Guided.
"""

import pytest
import asyncio
import os
import sys
from typing import Generator, AsyncGenerator
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
import uuid

# Agregar el directorio raíz al path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuración de pytest
pytest_plugins = [
    "pytest_asyncio",
    "pytest_mock",
    "pytest_cov"
]

# Configuración global
def pytest_configure(config):
    """Configuración global de pytest"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )

# Configuración de asyncio
@pytest.fixture(scope="session")
def event_loop():
    """Crear event loop para tests asíncronos"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# =============================================================================
# 🎭 FIXTURES DE USUARIOS Y SESIONES
# =============================================================================

@pytest.fixture
def mock_user():
    """Usuario mock para testing"""
    return Mock(
        id=uuid.uuid4(),
        username="test_user",
        email="test@example.com",
        is_active=True,
        is_premium=False,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

@pytest.fixture
def mock_premium_user():
    """Usuario premium mock para testing"""
    return Mock(
        id=uuid.uuid4(),
        username="premium_user",
        email="premium@example.com",
        is_active=True,
        is_premium=True,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

@pytest.fixture
def mock_session():
    """Sesión mock para testing"""
    return Mock(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        mode="EXPLORER",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        is_active=True
    )

@pytest.fixture
def mock_exploration_state():
    """Estado de exploración mock"""
    return {
        "current_step": 1,
        "total_steps": 5,
        "context": "database_exploration",
        "progress": 0.2,
        "last_activity": datetime.now()
    }

@pytest.fixture
def mock_guided_state():
    """Estado guiado mock"""
    return {
        "current_plan": "database_analysis",
        "step_index": 0,
        "total_steps": 3,
        "context": "guided_analysis",
        "progress": 0.0
    }

# =============================================================================
# 🔧 FIXTURES DE SERVICIOS
# =============================================================================

@pytest.fixture
def mock_database_service():
    """Servicio de base de datos mock"""
    service = Mock()
    service.get_user_by_id = AsyncMock(return_value=mock_user())
    service.get_session_by_id = AsyncMock(return_value=mock_session())
    service.create_session = AsyncMock(return_value=mock_session())
    service.update_session = AsyncMock(return_value=True)
    return service

@pytest.fixture
def mock_redis_service():
    """Servicio de Redis mock"""
    service = Mock()
    service.get = AsyncMock(return_value=None)
    service.set = AsyncMock(return_value=True)
    service.delete = AsyncMock(return_value=True)
    service.exists = AsyncMock(return_value=False)
    return service

@pytest.fixture
def mock_openai_service():
    """Servicio de OpenAI mock"""
    service = Mock()
    service.generate_response = AsyncMock(return_value="Respuesta mock de OpenAI")
    service.analyze_intent = AsyncMock(return_value="EXPLORER")
    service.rephrase_query = AsyncMock(return_value="Query rephraseada")
    return service

@pytest.fixture
def mock_agent_service():
    """Servicio de agentes mock"""
    service = Mock()
    service.get_agent_by_id = AsyncMock(return_value=Mock(
        id=uuid.uuid4(),
        name="Test Agent",
        mode="EXPLORER",
        is_generic=True
    ))
    service.get_agents_by_mode = AsyncMock(return_value=[])
    return service

# =============================================================================
# 🎯 FIXTURES DE CONTEXTO
# =============================================================================

@pytest.fixture
def mock_request_context():
    """Contexto de request mock"""
    return {
        "user_id": uuid.uuid4(),
        "session_id": uuid.uuid4(),
        "query": "¿Cómo está mi base de datos?",
        "timestamp": datetime.now(),
        "user_agent": "TestBot/1.0"
    }

@pytest.fixture
def mock_resource_context():
    """Contexto de recursos mock"""
    return {
        "database_count": 5,
        "app_count": 12,
        "strategy_count": 8,
        "cache_hit_rate": 0.75,
        "last_sync": datetime.now() - timedelta(hours=1)
    }

@pytest.fixture
def mock_user_profile():
    """Perfil de usuario mock"""
    return {
        "experience_level": "INTERMEDIATE",
        "preferred_mode": "GUIDED",
        "common_queries": ["database_status", "performance_analysis"],
        "learning_patterns": ["step_by_step", "examples_first"],
        "response_style": "DETAILED"
    }

# =============================================================================
# 🧪 FIXTURES DE TESTING
# =============================================================================

@pytest.fixture
def mock_test_data():
    """Datos de test mock"""
    return {
        "databases": [
            {"id": 1, "name": "test_db_1", "type": "postgresql"},
            {"id": 2, "name": "test_db_2", "type": "mysql"}
        ],
        "applications": [
            {"id": 1, "name": "test_app_1", "type": "web"},
            {"id": 2, "name": "test_app_2", "type": "api"}
        ],
        "strategies": [
            {"id": 1, "name": "test_strategy_1", "type": "optimization"},
            {"id": 2, "name": "test_strategy_2", "type": "monitoring"}
        ]
    }

@pytest.fixture
def mock_error_scenarios():
    """Escenarios de error mock"""
    return {
        "database_unavailable": "Database connection failed",
        "redis_unavailable": "Redis connection failed",
        "openai_timeout": "OpenAI API timeout",
        "invalid_data": "Invalid data format",
        "permission_denied": "Access denied"
    }

# =============================================================================
# 🔄 FIXTURES DE CACHE
# =============================================================================

@pytest.fixture
def mock_cache_entry():
    """Entrada de cache mock"""
    return {
        "key": "test_cache_key",
        "value": "test_cache_value",
        "ttl": 3600,
        "created_at": datetime.now(),
        "access_count": 0
    }

@pytest.fixture
def mock_response_cache():
    """Cache de respuestas mock"""
    return {
        "query_hash": "abc123",
        "response": "Respuesta cacheada",
        "mode": "EXPLORER",
        "confidence": 0.95,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(hours=1)
    }

# =============================================================================
# 📊 FIXTURES DE MÉTRICAS
# =============================================================================

@pytest.fixture
def mock_performance_metrics():
    """Métricas de performance mock"""
    return {
        "response_time": 150,  # ms
        "memory_usage": 45.2,  # MB
        "cpu_usage": 12.5,     # %
        "cache_hit_rate": 0.78,
        "error_rate": 0.02
    }

@pytest.fixture
def mock_mode_detection_log():
    """Log de detección de modo mock"""
    return {
        "user_id": uuid.uuid4(),
        "query": "Test query",
        "detected_mode": "EXPLORER",
        "confidence": 0.85,
        "features_used": ["keyword_analysis", "context_analysis"],
        "timestamp": datetime.now(),
        "processing_time": 45  # ms
    }

# =============================================================================
# 🚀 CONFIGURACIÓN DE ENTORNO
# =============================================================================

@pytest.fixture(autouse=True)
def setup_test_environment():
    """Configurar entorno de testing automáticamente"""
    # Configurar variables de entorno para testing
    os.environ["TESTING"] = "true"
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"
    os.environ["OPENAI_API_KEY"] = "test_key"
    
    yield
    
    # Cleanup después de cada test
    os.environ.pop("TESTING", None)

@pytest.fixture(scope="session")
def test_database():
    """Base de datos de testing"""
    # Aquí se configuraría la base de datos de testing
    # Por ahora retornamos un mock
    return Mock(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        execute=AsyncMock(),
        query=AsyncMock()
    )

@pytest.fixture(scope="session")
def test_redis():
    """Redis de testing"""
    # Aquí se configuraría Redis de testing
    # Por ahora retornamos un mock
    return Mock(
        connect=AsyncMock(),
        disconnect=AsyncMock(),
        get=AsyncMock(),
        set=AsyncMock(),
        delete=AsyncMock()
    )

# =============================================================================
# 🎨 UTILIDADES DE TESTING
# =============================================================================

def create_mock_user(**kwargs):
    """Crear usuario mock con parámetros personalizados"""
    default_user = mock_user()
    for key, value in kwargs.items():
        setattr(default_user, key, value)
    return default_user

def create_mock_session(**kwargs):
    """Crear sesión mock con parámetros personalizados"""
    default_session = mock_session()
    for key, value in kwargs.items():
        setattr(default_session, key, value)
    return default_session

def assert_response_structure(response, expected_keys):
    """Verificar estructura de respuesta"""
    assert isinstance(response, dict), "La respuesta debe ser un diccionario"
    for key in expected_keys:
        assert key in response, f"La respuesta debe contener la clave: {key}"

def assert_performance_metrics(metrics, max_response_time=1000, max_memory=100):
    """Verificar métricas de performance"""
    assert metrics["response_time"] <= max_response_time, f"Tiempo de respuesta excede {max_response_time}ms"
    assert metrics["memory_usage"] <= max_memory, f"Uso de memoria excede {max_memory}MB"
    assert metrics["error_rate"] <= 0.05, "Tasa de error debe ser menor al 5%"

# =============================================================================
# 📝 CONFIGURACIÓN DE LOGGING
# =============================================================================

import logging

@pytest.fixture(autouse=True)
def setup_logging():
    """Configurar logging para tests"""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Reducir verbosidad de algunos loggers
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)

# =============================================================================
# 🎯 MARCADORES PERSONALIZADOS
# =============================================================================

def pytest_collection_modifyitems(config, items):
    """Modificar items de colección para agregar marcadores automáticos"""
    for item in items:
        # Marcar tests de integración
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        
        # Marcar tests de performance
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        
        # Marcar tests end-to-end
        if "e2e" in item.nodeid:
            item.add_marker(pytest.mark.e2e)
        
        # Marcar tests lentos
        if any(keyword in item.nodeid.lower() for keyword in ["slow", "benchmark", "load"]):
            item.add_marker(pytest.mark.slow)
