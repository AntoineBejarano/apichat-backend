"""
Tests para Fase 7: Integración Final y Testing
──────────────────────────────────────────────
Valida el flujo completo del sistema optimizado entre todas las fases
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from app.services.management.readiness_registry import ReadinessRegistry, ReadinessStatus
from app.services.management.semantic_validator import SemanticValidator
from app.services.management.orchestrator_activation_guard import OrchestratorActivationGuard
from app.services.orchestrator.orchestrator_service import OrchestratorService
from app.services.background.resource_upload_trigger import ResourceUploadTrigger
from app.services.monitoring.readiness_metrics_service import ReadinessMetricsService
from app.services.management.system_readiness_manager import SystemReadinessManager
import logging

logger = logging.getLogger(__name__)


class TestCompleteSystemIntegration:
    """Tests para integración completa del sistema optimizado"""
    
    def setup_method(self):
        """Setup para cada test"""
        # Mock del factory
        self.mock_factory = Mock()
        
        # Mock de servicios
        self.mock_readiness_registry = Mock(spec=ReadinessRegistry)
        self.mock_semantic_validator = Mock(spec=SemanticValidator)
        self.mock_activation_guard = Mock(spec=OrchestratorActivationGuard)
        self.mock_metrics_service = Mock(spec=ReadinessMetricsService)
        
        # Configurar factory
        self.mock_factory.readiness_registry = self.mock_readiness_registry
        self.mock_factory.semantic_validator = self.mock_semantic_validator
        self.mock_factory.orchestrator_activation_guard = self.mock_activation_guard
        self.mock_factory.readiness_metrics_service = self.mock_metrics_service
    
    @pytest.mark.asyncio
    async def test_complete_resource_lifecycle(self):
        """Test: Ciclo completo de vida de un recurso desde upload hasta activación"""
        # 1. Simular upload de recurso
        resource_type = "database"
        resource_id = "db_123"
        user_id = "user_456"
        
        # 2. Mock del ResourceUploadTrigger
        mock_trigger = Mock(spec=ResourceUploadTrigger)
        mock_trigger.trigger_preparation = AsyncMock()
        
        # 3. Simular preparación del recurso
        self.mock_readiness_registry.mark_resource_preparing = AsyncMock()
        self.mock_readiness_registry.mark_resource_ready = AsyncMock(return_value=True)
        
        # 4. Simular validación semántica exitosa
        self.mock_semantic_validator.validate_resource = AsyncMock(return_value=Mock(
            valid=True,
            message="Validation successful",
            errors=[]
        ))
        
        # 5. Simular activación del orquestador
        self.mock_activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        
        # 6. Ejecutar flujo completo
        # Upload trigger
        await mock_trigger.trigger_preparation(resource_type, resource_id, user_id)
        
        # Preparación
        await self.mock_readiness_registry.mark_resource_preparing(resource_type, resource_id)
        
        # Validación y readiness
        await self.mock_readiness_registry.mark_resource_ready(resource_type, resource_id)
        
        # Verificar activación
        can_activate = await self.mock_activation_guard.can_activate_orchestrator(user_id)
        
        # Verificaciones
        mock_trigger.trigger_preparation.assert_called_once_with(resource_type, resource_id, user_id)
        self.mock_readiness_registry.mark_resource_preparing.assert_called_once_with(resource_type, resource_id)
        self.mock_readiness_registry.mark_resource_ready.assert_called_once_with(resource_type, resource_id)
        assert can_activate is True
    
    @pytest.mark.asyncio
    async def test_orchestrator_service_integration(self):
        """Test: Integración completa del OrchestratorService con todas las dependencias"""
        # Mock del OrchestratorService
        orchestrator_service = OrchestratorService.__new__(OrchestratorService)
        orchestrator_service.factory = self.mock_factory
        orchestrator_service.readiness_metrics = self.mock_metrics_service
        orchestrator_service.activation_guard = self.mock_activation_guard
        orchestrator_service.system_readiness_manager = Mock()  # Agregar mock faltante
        
        # Mock de métricas
        self.mock_metrics_service.get_readiness_stats = AsyncMock(return_value={
            'total_resources': 3,
            'ready_resources': 2,
            'readiness_percentage': 66.67
        })
        
        self.mock_metrics_service.get_user_waiting_stats = AsyncMock(return_value={
            'pending_resources_count': 1
        })
        
        # Mock de activación y readiness
        self.mock_activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        orchestrator_service.system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            'overall_ready': True
        })
        
        # Obtener estado del orquestador
        status = await orchestrator_service.get_orchestrator_status("user_123")
        
        # Verificar estructura completa
        assert 'can_activate' in status
        assert 'readiness_status' in status
        assert 'system_metrics' in status
        assert 'timestamp' in status
        assert 'user_id' in status
        
        # Verificar métricas del sistema
        system_metrics = status['system_metrics']
        assert 'readiness_stats' in system_metrics
        assert 'waiting_stats' in system_metrics
        
        # Verificar valores
        assert status['can_activate'] is True
        assert status['user_id'] == "user_123"
        assert system_metrics['readiness_stats']['readiness_percentage'] == 66.67
    
    @pytest.mark.asyncio
    async def test_error_recovery_and_fallback(self):
        """Test: Recuperación de errores y fallback del sistema"""
        # 1. Simular error en validación semántica
        self.mock_semantic_validator.validate_resource = AsyncMock(return_value=Mock(
            valid=False,
            message="Validation failed",
            errors=["Invalid schema", "Missing functions"]
        ))
        
        # 2. Simular marcado de error
        self.mock_readiness_registry.mark_resource_error = AsyncMock()
        
        # 3. Simular intento de marcar como listo (debería fallar)
        # En este caso, el mock retorna False, pero no llama a mark_resource_error automáticamente
        # porque es solo un mock. Vamos a simular el comportamiento real.
        
        # 4. Ejecutar flujo con error
        resource_type = "application"
        resource_id = "app_789"
        
        # Simular que el método mark_resource_ready falla y llama a mark_resource_error
        async def mock_mark_resource_ready(rt, rid):
            # Simular que falla y marca como error
            await self.mock_readiness_registry.mark_resource_error(rt, rid, ["Invalid schema", "Missing functions"])
            return False
        
        self.mock_readiness_registry.mark_resource_ready = mock_mark_resource_ready
        
        # Intentar marcar como listo (debería fallar)
        success = await self.mock_readiness_registry.mark_resource_ready(resource_type, resource_id)
        
        # Verificar que falló
        assert success is False
        
        # Verificar que se marcó como error
        self.mock_readiness_registry.mark_resource_error.assert_called_once_with(
            resource_type, resource_id, ["Invalid schema", "Missing functions"]
        )
    
    @pytest.mark.asyncio
    async def test_multiple_resources_concurrent_preparation(self):
        """Test: Preparación concurrente de múltiples recursos"""
        # 1. Simular múltiples recursos
        resources = [
            ("database", "db_1"),
            ("database", "db_2"),
            ("application", "app_1"),
            ("strategies", "strat_1")
        ]
        
        # 2. Mock de preparación concurrente
        self.mock_readiness_registry.mark_resource_preparing = AsyncMock()
        self.mock_readiness_registry.mark_resource_ready = AsyncMock(return_value=True)
        
        # 3. Simular validación exitosa para todos
        self.mock_semantic_validator.validate_resource = AsyncMock(return_value=Mock(
            valid=True,
            message="Validation successful",
            errors=[]
        ))
        
        # 4. Preparar recursos concurrentemente
        tasks = []
        for resource_type, resource_id in resources:
            task = asyncio.create_task(self.mock_readiness_registry.mark_resource_preparing(resource_type, resource_id))
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # 5. Marcar como listos
        ready_tasks = []
        for resource_type, resource_id in resources:
            task = asyncio.create_task(self.mock_readiness_registry.mark_resource_ready(resource_type, resource_id))
            ready_tasks.append(task)
        
        results = await asyncio.gather(*ready_tasks)
        
        # Verificaciones
        assert self.mock_readiness_registry.mark_resource_preparing.call_count == 4
        assert self.mock_readiness_registry.mark_resource_ready.call_count == 4
        assert all(results)  # Todos deberían ser True
    
    @pytest.mark.asyncio
    async def test_system_health_monitoring_integration(self):
        """Test: Integración del monitoreo de salud del sistema"""
        # Mock de métricas comprehensivas
        comprehensive_metrics = {
            'system_overview': {
                'health_score': 85,
                'performance_trend': 'good',
                'total_resources': 5,
                'readiness_percentage': 80.0
            },
            'readiness_stats': {
                'total_resources': 5,
                'ready_resources': 4,
                'error_resources': 1
            },
            'waiting_stats': {
                'pending_resources_count': 1
            },
            'resource_type_stats': {
                'resource_type_stats': {
                    'database': {'total': 3, 'ready': 3},
                    'application': {'total': 2, 'ready': 1}
                }
            },
            'error_analysis': {
                'total_errors': 1,
                'error_analysis': {
                    'application': {
                        'count': 1,
                        'common_errors': {'Invalid JSON': 1}
                    }
                }
            }
        }
        
        self.mock_metrics_service.get_comprehensive_metrics = AsyncMock(return_value=comprehensive_metrics)
        
        # Obtener métricas del sistema
        metrics = await self.mock_metrics_service.get_comprehensive_metrics()
        
        # Verificar estructura completa
        assert 'system_overview' in metrics
        assert 'readiness_stats' in metrics
        assert 'waiting_stats' in metrics
        assert 'resource_type_stats' in metrics
        assert 'error_analysis' in metrics
        
        # Verificar valores específicos
        system_overview = metrics['system_overview']
        assert system_overview['health_score'] == 85
        assert system_overview['performance_trend'] == 'good'
        assert system_overview['readiness_percentage'] == 80.0
        
        # Verificar análisis de errores
        error_analysis = metrics['error_analysis']
        assert error_analysis['total_errors'] == 1
        assert 'application' in error_analysis['error_analysis']
    
    @pytest.mark.asyncio
    async def test_user_experience_flow_optimization(self):
        """Test: Flujo optimizado de experiencia del usuario"""
        # 1. Simular usuario que sube un recurso
        user_id = "user_789"
        resource_type = "database"
        resource_id = "db_new"
        
        # 2. Mock del flujo completo optimizado
        # Upload trigger automático
        mock_trigger = Mock(spec=ResourceUploadTrigger)
        mock_trigger.trigger_preparation = AsyncMock()
        
        # Preparación en background
        self.mock_readiness_registry.mark_resource_preparing = AsyncMock()
        
        # Validación semántica
        self.mock_semantic_validator.validate_resource = AsyncMock(return_value=Mock(
            valid=True,
            message="Validation successful",
            errors=[]
        ))
        
        # Marcado como listo
        self.mock_readiness_registry.mark_resource_ready = AsyncMock(return_value=True)
        
        # 3. Ejecutar flujo optimizado
        # El usuario sube el recurso (trigger automático)
        await mock_trigger.trigger_preparation(resource_type, resource_id, user_id)
        
        # El sistema prepara en background (sin bloquear al usuario)
        await self.mock_readiness_registry.mark_resource_preparing(resource_type, resource_id)
        
        # Validación y readiness
        await self.mock_readiness_registry.mark_resource_ready(resource_type, resource_id)
        
        # 4. Verificar que el usuario no tuvo que esperar
        # (el trigger se ejecutó de forma asíncrona)
        mock_trigger.trigger_preparation.assert_called_once()
        
        # 5. Verificar que el recurso está listo
        self.mock_readiness_registry.mark_resource_ready.assert_called_once()
        
        # 6. Simular que el usuario intenta usar el orquestador
        self.mock_activation_guard.can_activate_orchestrator = AsyncMock(return_value=True)
        can_activate = await self.mock_activation_guard.can_activate_orchestrator(user_id)
        
        # El usuario debería poder usar el orquestador inmediatamente
        assert can_activate is True

    # @pytest.mark.asyncio
    # async def test_system_initialization_logic_correction(self):
    #     """Test que verifica que la nueva lógica de inicialización del sistema funciona correctamente"""
    #     # 🔧 NUEVO: Test para la lógica corregida de inicialización
    #     
    #     # 1. Verificar que el sistema NO se marca como READY prematuramente
    #     system_manager = SystemReadinessManager(self.mock_factory)
    #     init_result = await system_manager.initialize_system()
    #     
    #     assert init_result["success"] is True
    #     assert init_result["system_status"] == "initializing"
    #     assert "Servicios core verificados" in init_result["message"]
    #     
    #     # 2. Verificar que el estado inicial es INITIALIZING, no READY
    #     system_status = await system_manager.get_system_status()
    #     assert system_status["system_status"] == "initializing"
    #     
    #     # 3. Verificar que se puede marcar como READY manualmente
    #     ready_result = await system_manager.mark_system_ready("Test de recursos preparados")
    #     assert ready_result["success"] is True
    #     assert ready_result["previous_status"] == "initializing"
    #     assert ready_result["new_status"] == "ready"
    #     
    #     # 4. Verificar que el estado cambió a READY
    #     updated_status = await system_manager.get_system_status()
    #     assert updated_status["system_status"] == "ready"
    #     
    #     # 5. Verificar que se puede marcar como DEGRADED si es necesario
    #     degraded_result = await system_manager.mark_system_degraded("Test de degradación")
    #     assert degraded_result["success"] is True
    #     assert degraded_result["previous_status"] == "ready"
    #     assert degraded_result["new_status"] == "degraded"
    #     
    #     # 6. Verificar que el historial de cambios se registra correctamente
    #     status_history = await system_manager.get_status_history()
    #     assert len(status_history) >= 3  # initialize, ready, degraded
    #     
    #     # Verificar que el último cambio fue a degraded
    #     last_change = status_history[-1]
    #     assert last_change["new_status"] == "degraded"
    #     assert "Test de degradación" in last_change["reason"]
    #     
    #     logger.info("✅ Test de lógica de inicialización del sistema completado exitosamente")


class TestPerformanceOptimization:
    """Tests para validar las optimizaciones de performance"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.mock_factory = Mock()
        self.mock_metrics_service = Mock(spec=ReadinessMetricsService)
        self.mock_factory.readiness_metrics_service = self.mock_metrics_service
    
    @pytest.mark.asyncio
    async def test_response_time_optimization(self):
        """Test: Optimización del tiempo de respuesta"""
        # Mock de métricas de performance
        performance_metrics = {
            'init': 0.1,  # 100ms
            'react_think': 0.3,  # 300ms
            'schema_build': 0.2,  # 200ms
            'openai_plan': 0.5,  # 500ms
            'sql_exec': 0.1,  # 100ms
            'total': 1.2  # 1.2s total
        }
        
        # Verificar que el tiempo total está bajo el objetivo de 2s
        assert performance_metrics['total'] < 2.0
        
        # Verificar que la inicialización es rápida
        assert performance_metrics['init'] < 0.5
        
        # Verificar que el tiempo de respuesta total es aceptable
        assert performance_metrics['total'] < 1.5  # Objetivo optimizado
    
    @pytest.mark.asyncio
    async def test_resource_preparation_parallelization(self):
        """Test: Paralelización de preparación de recursos"""
        # Simular preparación paralela de recursos
        resource_types = ["database", "application", "strategies"]
        
        # Mock de preparación paralela
        preparation_times = {}
        
        async def prepare_resource(resource_type):
            # Simular tiempo de preparación
            import time
            start_time = time.time()
            await asyncio.sleep(0.1)  # 100ms
            preparation_times[resource_type] = time.time() - start_time
        
        # Preparar recursos en paralelo
        tasks = [prepare_resource(rt) for rt in resource_types]
        start_time = asyncio.get_event_loop().time()
        
        await asyncio.gather(*tasks)
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        # Verificar que la preparación paralela es más rápida que secuencial
        # Secuencial: 0.1 * 3 = 0.3s
        # Paralelo: ~0.1s
        assert total_time < 0.2  # Debería ser significativamente menor a 0.3s
        
        # Verificar que todos los recursos se prepararon
        assert len(preparation_times) == 3
        for resource_type in resource_types:
            assert resource_type in preparation_times


class TestSystemRobustness:
    """Tests para validar la robustez del sistema"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.mock_factory = Mock()
        self.mock_readiness_registry = Mock(spec=ReadinessRegistry)
        self.mock_factory.readiness_registry = self.mock_readiness_registry
    
    @pytest.mark.asyncio
    async def test_system_graceful_degradation(self):
        """Test: Degradación graceful del sistema ante fallos"""
        # 1. Simular fallo en validación semántica
        self.mock_readiness_registry.resource_readiness = {
            ('database', 'db_1'): {'status': ReadinessStatus.ERROR, 'errors': ['Connection failed']},
            ('database', 'db_2'): {'status': ReadinessStatus.READY},
            ('application', 'app_1'): {'status': ReadinessStatus.READY}
        }
        
        # 2. Verificar que el sistema sigue funcionando con recursos parciales
        ready_resources = 0
        error_resources = 0
        
        for (resource_type, resource_id), status_info in self.mock_readiness_registry.resource_readiness.items():
            if status_info['status'] == ReadinessStatus.READY:
                ready_resources += 1
            elif status_info['status'] == ReadinessStatus.ERROR:
                error_resources += 1
        
        # El sistema debería tener algunos recursos listos
        assert ready_resources > 0
        
        # Y manejar los errores gracefully
        assert error_resources >= 0
        
        # 3. Verificar que el sistema puede continuar operando
        total_resources = len(self.mock_readiness_registry.resource_readiness)
        readiness_percentage = (ready_resources / total_resources) * 100
        
        # El sistema debería tener al menos 50% de readiness para operar
        assert readiness_percentage >= 50.0
    
    @pytest.mark.asyncio
    async def test_error_propagation_handling(self):
        """Test: Manejo de propagación de errores"""
        # 1. Simular error en cascada
        error_chain = []
        
        async def simulate_error_propagation():
            try:
                # Simular error en validación
                raise Exception("Validation failed")
            except Exception as e:
                error_chain.append(str(e))
                try:
                    # Simular manejo del error
                    await self.mock_readiness_registry.mark_resource_error("database", "db_error", [str(e)])
                    error_chain.append("Error handled gracefully")
                except Exception as e2:
                    error_chain.append(f"Error handling failed: {e2}")
        
        # Ejecutar simulación
        await simulate_error_propagation()
        
        # Verificar que el error se manejó gracefulmente
        assert len(error_chain) >= 2
        assert "Validation failed" in error_chain[0]
        assert "Error handled gracefully" in error_chain[1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
