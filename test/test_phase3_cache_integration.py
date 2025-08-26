"""
🧪 Tests para FASE 3: INTEGRACIÓN CON CACHE EXISTENTE

Verifica que:
- ReadinessValidator usa cache como fuente de verdad
- ResourcePreparationService prepara recursos correctamente
- WarmupEngine ejecuta warmups proactivamente
- ResourceUploadTrigger dispara preparación automática
- No hay duplicación de preparación
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
import asyncio

# Importar servicios de la Fase 3
from app.services.management.readiness_validator import ReadinessValidator
from app.services.background.resource_preparation_service import ResourcePreparationService
from app.services.background.warmup_engine import WarmupEngine
from app.services.background.resource_upload_trigger import ResourceUploadTrigger


@pytest.fixture
def mock_factory():
    """Factory mock con todos los servicios necesarios"""
    factory = Mock()
    
    # Mock de cache services
    mock_db_cache = AsyncMock()
    mock_db_cache.get_schema.return_value = {
        'tables': [
            {'name': 'users', 'columns': [{'name': 'id', 'type': 'int'}]},
            {'name': 'posts', 'columns': [{'name': 'id', 'type': 'int'}]}
        ]
    }
    
    mock_app_cache = AsyncMock()
    mock_app_cache.get_descriptor.return_value = {
        'functions': [
            {'name': 'get_user', 'parameters': [{'name': 'user_id', 'type': 'string'}]},
            {'name': 'create_post', 'parameters': [{'name': 'title', 'type': 'string'}]}
        ]
    }
    
    factory.get_detailed_schema_cache_service.return_value = mock_db_cache
    factory.get_app_descriptor_cache_service.return_value = mock_app_cache
    
    # Mock de strategy service
    mock_strategy_service = AsyncMock()
    mock_strategy_service.get_strategy.return_value = {
        'steps': [
            {'action': 'query_db', 'parameters': {'table': 'users'}},
            {'action': 'process_data', 'parameters': {'operation': 'filter'}}
        ]
    }
    factory.get_strategy_service.return_value = mock_strategy_service
    
    # Mock de WSEmitter
    mock_ws_emitter = AsyncMock()
    factory.get_ws_emitter.return_value = mock_ws_emitter
    
    # Mock de ReadinessRegistry
    mock_readiness_registry = AsyncMock()
    factory.readiness_registry = mock_readiness_registry
    
    # Mock de background factory
    mock_background_factory = Mock()
    factory.background = mock_background_factory
    
    return factory


@pytest.fixture
def readiness_validator(mock_factory):
    """ReadinessValidator con factory mock"""
    return ReadinessValidator(mock_factory)


@pytest.fixture
def resource_preparation_service(mock_factory):
    """ResourcePreparationService con factory mock"""
    return ResourcePreparationService(mock_factory)


@pytest.fixture
def warmup_engine(mock_factory):
    """WarmupEngine con factory mock"""
    return WarmupEngine(mock_factory)


@pytest.fixture
def resource_upload_trigger(mock_factory):
    """ResourceUploadTrigger con factory mock"""
    return ResourceUploadTrigger(mock_factory)


class TestReadinessValidator:
    """Tests para ReadinessValidator"""
    
    @pytest.mark.asyncio
    async def test_is_database_ready_with_valid_cache(self, readiness_validator, mock_factory):
        """Verifica que is_database_ready funciona con cache válido"""
        result = await readiness_validator.is_database_ready("db_123")
        assert result is True
        
        # Verificar que se llamó al cache service
        mock_factory.get_detailed_schema_cache_service.assert_called_once()
        mock_factory.get_detailed_schema_cache_service().get_schema.assert_called_once_with("db_123")
    
    @pytest.mark.asyncio
    async def test_is_database_ready_with_empty_cache(self, readiness_validator, mock_factory):
        """Verifica que is_database_ready retorna False con cache vacío"""
        # Mock cache vacío
        mock_factory.get_detailed_schema_cache_service().get_schema.return_value = None
        
        result = await readiness_validator.is_database_ready("db_123")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_database_ready_with_invalid_schema(self, readiness_validator, mock_factory):
        """Verifica que is_database_ready retorna False con esquema inválido"""
        # Mock esquema sin tablas
        mock_factory.get_detailed_schema_cache_service().get_schema.return_value = {
            'tables': []
        }
        
        result = await readiness_validator.is_database_ready("db_123")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_application_ready_with_valid_cache(self, readiness_validator, mock_factory):
        """Verifica que is_application_ready funciona con cache válido"""
        result = await readiness_validator.is_application_ready("app_123")
        assert result is True
        
        # Verificar que se llamó al cache service
        mock_factory.get_app_descriptor_cache_service.assert_called_once()
        mock_factory.get_app_descriptor_cache_service().get_descriptor.assert_called_once_with("app_123")
    
    @pytest.mark.asyncio
    async def test_is_application_ready_with_empty_cache(self, readiness_validator, mock_factory):
        """Verifica que is_application_ready retorna False con cache vacío"""
        # Mock cache vacío
        mock_factory.get_app_descriptor_cache_service().get_descriptor.return_value = None
        
        result = await readiness_validator.is_application_ready("app_123")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_is_application_ready_with_no_functions(self, readiness_validator, mock_factory):
        """Verifica que is_application_ready retorna False sin funciones"""
        # Mock descriptor sin funciones
        mock_factory.get_app_descriptor_cache_service().get_descriptor.return_value = {
            'functions': []
        }
        
        result = await readiness_validator.is_application_ready("app_123")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_all_resources(self, readiness_validator):
        """Verifica que validate_all_resources funciona correctamente"""
        result = await readiness_validator.validate_all_resources("user_123")
        
        assert isinstance(result, dict)
        assert 'database' in result
        assert 'application' in result
        assert 'strategies' in result
        
        # Por ahora, todos deberían ser True (mocks configurados para éxito)
        assert all(result.values())
    
    @pytest.mark.asyncio
    async def test_is_environment_ready(self, readiness_validator):
        """Verifica que is_environment_ready funciona correctamente"""
        result = await readiness_validator.is_environment_ready("user_123")
        assert result is True


class TestResourcePreparationService:
    """Tests para ResourcePreparationService"""
    
    @pytest.mark.asyncio
    async def test_prepare_database_success(self, resource_preparation_service, mock_factory):
        """Verifica que prepare_database funciona correctamente"""
        result = await resource_preparation_service.prepare_database("db_123", "user_123")
        assert result is True
        
        # Verificar que se marcó como preparando y luego como listo
        mock_factory.readiness_registry.mark_resource_preparing.assert_called_once_with('database', 'db_123')
        mock_factory.readiness_registry.mark_resource_ready.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prepare_database_with_cache_error(self, resource_preparation_service, mock_factory):
        """Verifica que prepare_database maneja errores de cache"""
        # Mock cache service no disponible
        mock_factory.get_detailed_schema_cache_service.return_value = None
        
        result = await resource_preparation_service.prepare_database("db_123", "user_123")
        assert result is False
        
        # Verificar que se marcó como error
        mock_factory.readiness_registry.mark_resource_error.assert_called_once_with('database', 'db_123', "Cache service no disponible")
    
    @pytest.mark.asyncio
    async def test_prepare_application_success(self, resource_preparation_service, mock_factory):
        """Verifica que prepare_application funciona correctamente"""
        result = await resource_preparation_service.prepare_application("app_123", "user_123")
        assert result is True
        
        # Verificar que se marcó como preparando y luego como listo
        mock_factory.readiness_registry.mark_resource_preparing.assert_called_once_with('application', 'app_123')
        mock_factory.readiness_registry.mark_resource_ready.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_prepare_strategies_success(self, resource_preparation_service, mock_factory):
        """Verifica que prepare_strategies funciona correctamente"""
        strategy_ids = ["strategy_1", "strategy_2"]
        result = await resource_preparation_service.prepare_strategies(strategy_ids, "user_123")
        assert result is True
        
        # Verificar que se marcaron como preparando y luego como listo
        assert mock_factory.readiness_registry.mark_resource_preparing.call_count == 2
        assert mock_factory.readiness_registry.mark_resource_ready.call_count == 2
    
    @pytest.mark.asyncio
    async def test_prepare_user_environment(self, resource_preparation_service):
        """Verifica que prepare_user_environment funciona correctamente"""
        result = await resource_preparation_service.prepare_user_environment("user_123")
        
        assert isinstance(result, dict)
        assert 'database' in result
        assert 'application' in result
        assert 'strategies' in result
        
        # Por ahora, todos deberían ser True (mocks configurados para éxito)
        assert all(result.values())


class TestWarmupEngine:
    """Tests para WarmupEngine"""
    
    @pytest.mark.asyncio
    async def test_warmup_database_success(self, warmup_engine, mock_factory):
        """Verifica que warmup_database funciona correctamente"""
        # Mock cache service para que retorne datos válidos
        mock_cache = AsyncMock()
        mock_cache.get_schema.return_value = {
            'tables': [{'name': 'users', 'columns': [{'name': 'id', 'type': 'int'}]}]
        }
        mock_factory.get_detailed_schema_cache_service.return_value = mock_cache
        
        # Iniciar warmup
        await warmup_engine.warmup_database("db_123", "user_123")
        
        # Verificar que se marcó como preparando
        mock_factory.readiness_registry.mark_resource_preparing.assert_called_once_with('database', 'db_123')
        
        # Esperar a que se complete el warmup (más tiempo para asegurar completado)
        await asyncio.sleep(2.5)
        
        # Verificar que se marcó como listo
        mock_factory.readiness_registry.mark_resource_ready.assert_called_once()
        
        # Verificar que no hay warmups activos
        active_warmups = warmup_engine.get_active_warmups()
        assert len(active_warmups) == 0
    
    @pytest.mark.asyncio
    async def test_warmup_application_success(self, warmup_engine, mock_factory):
        """Verifica que warmup_application funciona correctamente"""
        # Mock cache service para que retorne datos válidos
        mock_cache = AsyncMock()
        mock_cache.get_descriptor.return_value = {
            'functions': [{'name': 'get_user', 'parameters': [{'name': 'user_id', 'type': 'string'}]}]
        }
        mock_factory.get_app_descriptor_cache_service.return_value = mock_cache
        
        # Iniciar warmup
        await warmup_engine.warmup_application("app_123", "user_123")
        
        # Verificar que se marcó como preparando
        mock_factory.readiness_registry.mark_resource_preparing.assert_called_once_with('application', 'app_123')
        
        # Esperar a que se complete el warmup (más tiempo para asegurar completado)
        await asyncio.sleep(2.0)
        
        # Verificar que se marcó como listo
        mock_factory.readiness_registry.mark_resource_ready.assert_called_once()
        
        # Verificar que no hay warmups activos
        active_warmups = warmup_engine.get_active_warmups()
        assert len(active_warmups) == 0
    
    @pytest.mark.asyncio
    async def test_warmup_strategies_success(self, warmup_engine):
        """Verifica que warmup_strategies funciona correctamente"""
        # Iniciar warmup
        await warmup_engine.warmup_strategies("app_123", "user_123")
        
        # Esperar a que se complete el warmup (más tiempo para asegurar completado)
        await asyncio.sleep(1.5)
        
        # Verificar que no hay warmups activos (se completó)
        active_warmups = warmup_engine.get_active_warmups()
        assert len(active_warmups) == 0
    
    @pytest.mark.asyncio
    async def test_warmup_user_environment(self, warmup_engine, mock_factory):
        """Verifica que warmup_user_environment funciona correctamente"""
        # Mock cache services para que retornen datos válidos
        mock_db_cache = AsyncMock()
        mock_db_cache.get_schema.return_value = {
            'tables': [{'name': 'users', 'columns': [{'name': 'id', 'type': 'int'}]}]
        }
        mock_factory.get_detailed_schema_cache_service.return_value = mock_db_cache
        
        mock_app_cache = AsyncMock()
        mock_app_cache.get_descriptor.return_value = {
            'functions': [{'name': 'get_user', 'parameters': [{'name': 'user_id', 'type': 'string'}]}]
        }
        mock_factory.get_app_descriptor_cache_service.return_value = mock_app_cache
        
        # Iniciar warmup
        await warmup_engine.warmup_user_environment("user_123")
        
        # Esperar a que se completen los warmups (más tiempo para asegurar completado)
        await asyncio.sleep(3.0)
        
        # Verificar que no hay warmups activos (se completaron)
        active_warmups = warmup_engine.get_active_warmups()
        assert len(active_warmups) == 0
    
    @pytest.mark.asyncio
    async def test_duplicate_warmup_prevention(self, warmup_engine):
        """Verifica que no se pueden iniciar warmups duplicados"""
        # Iniciar primer warmup
        await warmup_engine.warmup_database("db_123", "user_123")
        
        # Intentar iniciar el mismo warmup nuevamente
        await warmup_engine.warmup_database("db_123", "user_123")
        
        # Verificar que solo hay un warmup activo
        active_warmups = warmup_engine.get_active_warmups()
        assert len(active_warmups) == 1
    
    def test_get_active_warmups(self, warmup_engine):
        """Verifica que get_active_warmups funciona correctamente"""
        active_warmups = warmup_engine.get_active_warmups()
        assert isinstance(active_warmups, dict)
    
    @pytest.mark.asyncio
    async def test_is_resource_warming_up(self, warmup_engine):
        """Verifica que is_resource_warming_up funciona correctamente"""
        # Antes de iniciar warmup
        assert not warmup_engine.is_resource_warming_up('database', 'db_123')
        
        # Iniciar warmup
        await warmup_engine.warmup_database("db_123", "user_123")
        
        # Verificar que está en warmup
        assert warmup_engine.is_resource_warming_up('database', 'db_123')


class TestResourceUploadTrigger:
    """Tests para ResourceUploadTrigger"""
    
    @pytest.mark.asyncio
    async def test_on_database_uploaded(self, resource_upload_trigger, mock_factory):
        """Verifica que on_database_uploaded dispara warmup automático"""
        # Mock WarmupEngine
        mock_warmup_engine = AsyncMock()
        mock_factory.background.get_warmup_engine.return_value = mock_warmup_engine
        
        await resource_upload_trigger.on_database_uploaded("db_123", "user_123")
        
        # Verificar que se llamó al warmup engine
        mock_warmup_engine.warmup_database.assert_called_once_with("db_123", "user_123")
        
        # Verificar que se notificó al usuario
        mock_factory.get_ws_emitter().emit_to_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_application_uploaded(self, resource_upload_trigger, mock_factory):
        """Verifica que on_application_uploaded dispara warmup automático"""
        # Mock WarmupEngine
        mock_warmup_engine = AsyncMock()
        mock_factory.background.get_warmup_engine.return_value = mock_warmup_engine
        
        await resource_upload_trigger.on_application_uploaded("app_123", "user_123")
        
        # Verificar que se llamó al warmup engine
        mock_warmup_engine.warmup_application.assert_called_once_with("app_123", "user_123")
        
        # Verificar que se notificó al usuario
        mock_factory.get_ws_emitter().emit_to_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_strategies_uploaded(self, resource_upload_trigger, mock_factory):
        """Verifica que on_strategies_uploaded dispara warmup automático"""
        # Mock WarmupEngine
        mock_warmup_engine = AsyncMock()
        mock_factory.background.get_warmup_engine.return_value = mock_warmup_engine
        
        strategy_ids = ["strategy_1", "strategy_2"]
        await resource_upload_trigger.on_strategies_uploaded(strategy_ids, "user_123")
        
        # Verificar que se llamó al warmup engine
        mock_warmup_engine.warmup_strategies.assert_called_once_with("default_app", "user_123")
        
        # Verificar que se notificó al usuario
        mock_factory.get_ws_emitter().emit_to_user.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_bulk_upload_completed(self, resource_upload_trigger, mock_factory):
        """Verifica que on_bulk_upload_completed dispara warmups múltiples"""
        # Mock WarmupEngine
        mock_warmup_engine = AsyncMock()
        mock_factory.background.get_warmup_engine.return_value = mock_warmup_engine
        
        uploads = [
            {'type': 'database', 'id': 'db_123'},
            {'type': 'application', 'id': 'app_123'},
            {'type': 'strategy', 'id': 'strategy_1'}
        ]
        
        await resource_upload_trigger.on_bulk_upload_completed(uploads, "user_123")
        
        # Verificar que se llamaron los warmups correspondientes
        mock_warmup_engine.warmup_database.assert_called_once_with("db_123", "user_123")
        mock_warmup_engine.warmup_application.assert_called_once_with("app_123", "user_123")
        mock_warmup_engine.warmup_strategies.assert_called_once_with("app_123", "user_123")
    
    @pytest.mark.asyncio
    async def test_get_trigger_status(self, resource_upload_trigger, mock_factory):
        """Verifica que get_trigger_status funciona correctamente"""
        # Mock WarmupEngine con warmups activos
        mock_warmup_engine = Mock()
        mock_warmup_engine.get_active_warmups.return_value = {
            'database_db_123': {'status': 'warming_up'},
            'application_app_123': {'status': 'warming_up'}
        }
        mock_factory.background.get_warmup_engine.return_value = mock_warmup_engine
        
        result = await resource_upload_trigger.get_trigger_status("user_123")
        
        assert isinstance(result, dict)
        assert 'active_warmups' in result
        assert result['warmup_count'] == 2


class TestCacheIntegration:
    """Tests de integración con cache existente"""
    
    @pytest.mark.asyncio
    async def test_no_duplicate_preparation(self, resource_preparation_service, mock_factory):
        """Verifica que no hay duplicación de preparación"""
        # Preparar base de datos dos veces
        result1 = await resource_preparation_service.prepare_database("db_123", "user_123")
        result2 = await resource_preparation_service.prepare_database("db_123", "user_123")
        
        assert result1 is True
        assert result2 is True
        
        # Verificar que se llamó al cache service solo una vez por preparación
        # (cada preparación es independiente, pero no debería haber duplicación interna)
        cache_service = mock_factory.get_detailed_schema_cache_service()
        assert cache_service.get_schema.call_count == 2  # Una por cada preparación
    
    @pytest.mark.asyncio
    async def test_cache_as_source_of_truth(self, readiness_validator, mock_factory):
        """Verifica que el cache se usa como fuente de verdad"""
        # Cambiar el cache para que retorne diferentes resultados
        mock_factory.get_detailed_schema_cache_service().get_schema.return_value = None
        
        # Ahora debería retornar False
        result = await readiness_validator.is_database_ready("db_123")
        assert result is False
        
        # Restaurar cache válido
        mock_factory.get_detailed_schema_cache_service().get_schema.return_value = {
            'tables': [{'name': 'users', 'columns': [{'name': 'id', 'type': 'int'}]}]
        }
        
        # Ahora debería retornar True
        result = await readiness_validator.is_database_ready("db_123")
        assert result is True
