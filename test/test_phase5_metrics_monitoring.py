"""
Tests para Fase 5: Métricas y Monitoring
────────────────────────────────────────
Valida la funcionalidad de métricas mejoradas y ReadinessMetricsService
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from app.services.execution.graphs.utils.performance_metrics import PerformanceMetrics
from app.services.monitoring.readiness_metrics_service import ReadinessMetricsService
from app.services.management.readiness_registry import ReadinessStatus


class TestEnhancedPerformanceMetrics:
    """Tests para PerformanceMetrics mejorado con métricas de readiness"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.metrics = PerformanceMetrics()
    
    def test_record_phase_time(self):
        """Test: Registrar tiempo de fase de inicialización"""
        # Registrar tiempo de fase
        self.metrics.record_phase_time("phase_1_core", 0.5)
        self.metrics.record_phase_time("phase_2_ai", 1.2)
        self.metrics.record_phase_time("phase_1_core", 0.6)
        
        # Verificar que se registraron correctamente
        assert "phase_1_core" in self.metrics.phase_timings
        assert "phase_2_ai" in self.metrics.phase_timings
        assert len(self.metrics.phase_timings["phase_1_core"]) == 2
        assert len(self.metrics.phase_timings["phase_2_ai"]) == 1
        assert self.metrics.phase_timings["phase_1_core"] == [0.5, 0.6]
        assert self.metrics.phase_timings["phase_2_ai"] == [1.2]
    
    def test_record_resource_readiness(self):
        """Test: Registrar tiempo de preparación de recurso"""
        # Registrar preparación de recursos
        self.metrics.record_resource_readiness("database", "db_123", 2.5)
        self.metrics.record_resource_readiness("application", "app_456", 1.8)
        self.metrics.record_resource_readiness("database", "db_123", 2.1)
        
        # Verificar que se registraron correctamente
        key_db = "database_db_123"
        key_app = "application_app_456"
        
        assert key_db in self.metrics.resource_readiness_times
        assert key_app in self.metrics.resource_readiness_times
        assert self.metrics.resource_readiness_times[key_db] == [2.5, 2.1]
        assert self.metrics.resource_readiness_times[key_app] == [1.8]
        
        # Verificar historial de preparación
        assert key_db in self.metrics.resource_preparation_history
        assert len(self.metrics.resource_preparation_history[key_db]) == 2
        assert self.metrics.resource_preparation_history[key_db][0]['duration'] == 2.5
        assert self.metrics.resource_preparation_history[key_db][1]['duration'] == 2.1
    
    def test_track_user_waiting(self):
        """Test: Trackear usuarios esperando"""
        # Trackear usuarios esperando
        self.metrics.track_user_waiting("user_1", "database")
        self.metrics.track_user_waiting("user_2", "application")
        
        # Verificar que se registraron correctamente
        assert "user_1" in self.metrics.users_waiting
        assert "user_2" in self.metrics.users_waiting
        assert self.metrics.users_waiting["user_1"]["waiting_for"] == "database"
        assert self.metrics.users_waiting["user_2"]["waiting_for"] == "application"
        assert self.metrics.users_waiting["user_1"]["status"] == "waiting"
        assert self.metrics.users_waiting["user_2"]["status"] == "waiting"
    
    def test_mark_user_no_longer_waiting(self):
        """Test: Marcar usuario como no esperando"""
        # Trackear usuario esperando
        self.metrics.track_user_waiting("user_1", "database")
        
        # Simular que ya no está esperando
        self.metrics.mark_user_no_longer_waiting("user_1")
        
        # Verificar que se marcó como completado
        assert self.metrics.users_waiting["user_1"]["status"] == "completed"
        assert "completed_at" in self.metrics.users_waiting["user_1"]
    
    def test_get_phase_stats(self):
        """Test: Obtener estadísticas de una fase"""
        # Registrar tiempos de fase
        self.metrics.record_phase_time("phase_1_core", 0.5)
        self.metrics.record_phase_time("phase_1_core", 0.6)
        self.metrics.record_phase_time("phase_1_core", 0.4)
        
        # Obtener estadísticas
        stats = self.metrics.get_phase_stats("phase_1_core")
        
        # Verificar estadísticas
        assert stats["count"] == 3
        assert stats["average"] == pytest.approx(0.5, rel=1e-2)
        assert stats["min"] == 0.4
        assert stats["max"] == 0.6
        assert stats["last_execution"] == 0.4
    
    def test_get_resource_performance_stats(self):
        """Test: Obtener estadísticas de performance de un recurso"""
        # Registrar preparación de recursos
        self.metrics.record_resource_readiness("database", "db_123", 2.5)
        self.metrics.record_resource_readiness("database", "db_123", 2.1)
        self.metrics.record_resource_readiness("database", "db_123", 2.8)
        
        # Obtener estadísticas
        stats = self.metrics.get_resource_performance_stats("database", "db_123")
        
        # Verificar estadísticas
        assert stats["count"] == 3
        assert stats["average"] == pytest.approx(2.47, rel=1e-2)
        assert stats["min"] == 2.1
        assert stats["max"] == 2.8
        assert stats["last_preparation"] is not None
    
    def test_get_users_waiting_stats(self):
        """Test: Obtener estadísticas de usuarios esperando"""
        # Trackear usuarios esperando
        self.metrics.track_user_waiting("user_1", "database")
        self.metrics.track_user_waiting("user_2", "application")
        
        # Marcar uno como completado
        self.metrics.mark_user_no_longer_waiting("user_1")
        
        # Obtener estadísticas
        stats = self.metrics.get_users_waiting_stats()
        
        # Verificar estadísticas
        assert stats["currently_waiting"] == 1
        assert stats["total_completed"] == 1
        # El tiempo de espera puede ser 0 si se ejecuta muy rápido, pero debe ser >= 0
        assert stats["average_wait_time"] >= 0
    
    def test_get_users_waiting_stats_with_real_timing(self):
        """Test: Obtener estadísticas con timing real"""
        # Trackear usuario esperando
        self.metrics.track_user_waiting("user_3", "database")
        
        # Simular un tiempo de espera real
        import time
        time.sleep(0.1)  # Esperar 100ms
        
        # Marcar como completado
        self.metrics.mark_user_no_longer_waiting("user_3")
        
        # Obtener estadísticas
        stats = self.metrics.get_users_waiting_stats()
        
        # Verificar que el tiempo de espera es mayor que 0
        assert stats["currently_waiting"] == 0
        assert stats["total_completed"] == 1  # Solo user_3 de este test
        assert stats["average_wait_time"] > 0  # Ahora debe ser > 0
    
    def test_get_metrics_includes_new_metrics(self):
        """Test: get_metrics incluye las nuevas métricas"""
        # Registrar algunas métricas
        self.metrics.record_phase_time("phase_1_core", 0.5)
        self.metrics.record_resource_readiness("database", "db_123", 2.5)
        self.metrics.track_user_waiting("user_1", "database")
        
        # Obtener métricas
        metrics = self.metrics.get_metrics()
        
        # Verificar que incluye las nuevas métricas
        assert "phases" in metrics
        assert "resources" in metrics
        assert "users_waiting" in metrics
        assert "phase_1_core" in metrics["phases"]
        assert "database_db_123" in metrics["resources"]
    
    def test_log_breakdown_includes_phases_and_resources(self):
        """Test: log_breakdown incluye breakdown de fases y recursos"""
        # Registrar métricas
        self.metrics.record_phase_time("phase_1_core", 0.5)
        self.metrics.record_resource_readiness("database", "db_123", 2.5)
        
        # Verificar que no hay error al llamar log_breakdown
        # (esto es principalmente para verificar que no hay excepciones)
        try:
            self.metrics.log_breakdown()
            assert True  # Si llegamos aquí, no hubo excepción
        except Exception as e:
            pytest.fail(f"log_breakdown lanzó excepción: {e}")
    
    def test_get_performance_summary_includes_readiness_metrics(self):
        """Test: get_performance_summary incluye métricas de readiness"""
        # Registrar métricas
        self.metrics.record_phase_time("phase_1_core", 0.5)
        self.metrics.record_resource_readiness("database", "db_123", 2.5)
        self.metrics.track_user_waiting("user_1", "database")
        
        # Obtener resumen
        summary = self.metrics.get_performance_summary()
        
        # Verificar que incluye métricas de readiness
        assert "readiness_metrics" in summary
        readiness_metrics = summary["readiness_metrics"]
        assert readiness_metrics["total_phases_tracked"] == 1
        assert readiness_metrics["total_resources_tracked"] == 1
        assert readiness_metrics["users_currently_waiting"] == 1
        assert readiness_metrics["total_users_completed"] == 0


class TestReadinessMetricsService:
    """Tests para ReadinessMetricsService"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.mock_factory = Mock()
        self.mock_readiness_registry = Mock()
        self.mock_factory.readiness_registry = self.mock_readiness_registry
        
        self.metrics_service = ReadinessMetricsService(self.mock_factory)
    
    @pytest.mark.asyncio
    async def test_get_readiness_stats(self):
        """Test: Obtener estadísticas de readiness del sistema"""
        # Mock del ReadinessRegistry
        self.mock_readiness_registry.resource_readiness = {
            ('database', 'db_1'): {'status': ReadinessStatus.READY, 'timestamp': '2024-01-01T00:00:00Z'},
            ('database', 'db_2'): {'status': ReadinessStatus.PENDING, 'timestamp': '2024-01-01T00:00:00Z'},
            ('application', 'app_1'): {'status': ReadinessStatus.ERROR, 'timestamp': '2024-01-01T00:00:00Z'},
            ('application', 'app_2'): {'status': ReadinessStatus.PREPARING, 'timestamp': '2024-01-01T00:00:00Z'},
            ('strategies', 'strat_1'): {'status': ReadinessStatus.VALIDATING, 'timestamp': '2024-01-01T00:00:00Z'}
        }
        
        # Obtener estadísticas
        stats = await self.metrics_service.get_readiness_stats()
        
        # Verificar estadísticas
        assert stats['total_resources'] == 5
        assert stats['ready_resources'] == 1
        assert stats['pending_resources'] == 1
        assert stats['error_resources'] == 1
        assert stats['preparing_resources'] == 1
        assert stats['validating_resources'] == 1
        assert stats['readiness_percentage'] == 20.0  # 1/5 * 100
        assert 'timestamp' in stats
    
    @pytest.mark.asyncio
    async def test_get_user_waiting_stats(self):
        """Test: Obtener estadísticas de usuarios esperando"""
        # Mock del método get_pending_resources
        self.mock_readiness_registry.get_pending_resources = AsyncMock(return_value=[
            {'type': 'database', 'id': 'db_1'},
            {'type': 'database', 'id': 'db_2'},
            {'type': 'application', 'id': 'app_1'}
        ])
        
        # Obtener estadísticas
        stats = await self.metrics_service.get_user_waiting_stats()
        
        # Verificar estadísticas
        assert stats['pending_resources_count'] == 3
        assert stats['resource_types_waiting']['database'] == 2
        assert stats['resource_types_waiting']['application'] == 1
        assert stats['estimated_completion_time'] == 9  # 3 * 3 segundos
        assert 'timestamp' in stats
    
    @pytest.mark.asyncio
    async def test_get_resource_type_stats(self):
        """Test: Obtener estadísticas por tipo de recurso"""
        # Mock del ReadinessRegistry
        self.mock_readiness_registry.resource_readiness = {
            ('database', 'db_1'): {'status': ReadinessStatus.READY},
            ('database', 'db_2'): {'status': ReadinessStatus.READY},
            ('database', 'db_3'): {'status': ReadinessStatus.ERROR},
            ('application', 'app_1'): {'status': ReadinessStatus.READY},
            ('application', 'app_2'): {'status': ReadinessStatus.PENDING}
        }
        
        # Obtener estadísticas
        stats = await self.metrics_service.get_resource_type_stats()
        
        # Verificar estadísticas
        resource_type_stats = stats['resource_type_stats']
        
        # Database stats
        assert resource_type_stats['database']['total'] == 3
        assert resource_type_stats['database']['ready'] == 2
        assert resource_type_stats['database']['error'] == 1
        assert resource_type_stats['database']['ready_percentage'] == pytest.approx(66.67, rel=1e-2)
        assert resource_type_stats['database']['error_percentage'] == pytest.approx(33.33, rel=1e-2)
        
        # Application stats
        assert resource_type_stats['application']['total'] == 2
        assert resource_type_stats['application']['ready'] == 1
        assert resource_type_stats['application']['pending'] == 1
        assert resource_type_stats['application']['ready_percentage'] == 50.0
    
    @pytest.mark.asyncio
    async def test_get_error_analysis(self):
        """Test: Obtener análisis de errores para debugging"""
        # Mock del ReadinessRegistry con errores
        self.mock_readiness_registry.resource_readiness = {
            ('database', 'db_1'): {
                'status': ReadinessStatus.ERROR,
                'errors': ['Connection failed', 'Timeout'],
                'timestamp': '2024-01-01T00:00:00Z'
            },
            ('database', 'db_2'): {
                'status': ReadinessStatus.ERROR,
                'errors': ['Connection failed'],
                'timestamp': '2024-01-01T00:00:00Z'
            },
            ('application', 'app_1'): {
                'status': ReadinessStatus.ERROR,
                'errors': ['Invalid JSON'],
                'timestamp': '2024-01-01T00:00:00Z'
            }
        }
        
        # Obtener análisis de errores
        error_analysis = await self.metrics_service.get_error_analysis()
        
        # Verificar análisis
        assert error_analysis['total_errors'] == 3
        
        # Database errors
        db_errors = error_analysis['error_analysis']['database']
        assert db_errors['count'] == 2
        assert db_errors['common_errors']['Connection failed'] == 2
        assert db_errors['common_errors']['Timeout'] == 1
        
        # Application errors
        app_errors = error_analysis['error_analysis']['application']
        assert app_errors['count'] == 1
        assert app_errors['common_errors']['Invalid JSON'] == 1
    
    @pytest.mark.asyncio
    async def test_get_comprehensive_metrics(self):
        """Test: Obtener métricas comprehensivas del sistema"""
        # Mock de todos los métodos
        self.metrics_service.get_readiness_stats = AsyncMock(return_value={
            'total_resources': 5,
            'ready_resources': 3,
            'readiness_percentage': 60.0
        })
        
        self.metrics_service.get_user_waiting_stats = AsyncMock(return_value={
            'pending_resources_count': 2
        })
        
        self.metrics_service.get_resource_type_stats = AsyncMock(return_value={
            'resource_type_stats': {'database': {'total': 3, 'ready': 2}}
        })
        
        self.metrics_service.get_error_analysis = AsyncMock(return_value={
            'total_errors': 1
        })
        
        # Obtener métricas comprehensivas
        comprehensive = await self.metrics_service.get_comprehensive_metrics()
        
        # Verificar estructura
        assert 'system_overview' in comprehensive
        assert 'readiness_stats' in comprehensive
        assert 'waiting_stats' in comprehensive
        assert 'resource_type_stats' in comprehensive
        assert 'error_analysis' in comprehensive
        
        # Verificar métricas calculadas
        system_overview = comprehensive['system_overview']
        assert system_overview['health_score'] > 0
        assert system_overview['performance_trend'] in ['excellent', 'good', 'fair', 'poor', 'critical']
        assert system_overview['total_resources'] == 5
        assert system_overview['readiness_percentage'] == 60.0
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test: Manejo de errores en el servicio"""
        # Mock que lanza excepción
        self.mock_readiness_registry.resource_readiness = {}
        self.mock_readiness_registry.get_pending_resources = AsyncMock(side_effect=Exception("Test error"))
        
        # Obtener estadísticas (debería manejar el error)
        stats = await self.metrics_service.get_user_waiting_stats()
        
        # Verificar que se maneja el error
        assert 'error' in stats
        assert stats['error'] == "Test error"
        assert 'timestamp' in stats
    
    def test_calculate_health_score(self):
        """Test: Cálculo de score de salud del sistema"""
        # Caso: sin recursos
        readiness_stats = {'total_resources': 0}
        health_score = self.metrics_service._calculate_health_score(readiness_stats)
        assert health_score == 100
        
        # Caso: todos los recursos listos
        readiness_stats = {'total_resources': 5, 'ready_resources': 5, 'error_resources': 0}
        health_score = self.metrics_service._calculate_health_score(readiness_stats)
        assert health_score == 100
        
        # Caso: algunos recursos con errores
        readiness_stats = {'total_resources': 5, 'ready_resources': 3, 'error_resources': 2}
        health_score = self.metrics_service._calculate_health_score(readiness_stats)
        assert health_score == 52  # (3/5 * 100) - (2/5 * 20) = 60 - 8 = 52
    
    def test_calculate_performance_trend(self):
        """Test: Cálculo de tendencia de performance"""
        # Casos de prueba
        assert self.metrics_service._calculate_performance_trend({'readiness_percentage': 95}) == "excellent"
        assert self.metrics_service._calculate_performance_trend({'readiness_percentage': 80}) == "good"
        assert self.metrics_service._calculate_performance_trend({'readiness_percentage': 60}) == "fair"
        assert self.metrics_service._calculate_performance_trend({'readiness_percentage': 30}) == "poor"
        assert self.metrics_service._calculate_performance_trend({'readiness_percentage': 10}) == "critical"


class TestOrchestratorServiceIntegration:
    """Tests para integración de métricas en OrchestratorService"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.mock_factory = Mock()
        self.mock_readiness_metrics = Mock()
        self.mock_system_readiness_manager = Mock()
        
        # Mock del OrchestratorService
        from app.services.orchestrator.orchestrator_service import OrchestratorService
        self.orchestrator_service = OrchestratorService.__new__(OrchestratorService)
        self.orchestrator_service.factory = self.mock_factory
        self.orchestrator_service.readiness_metrics = self.mock_readiness_metrics
        self.orchestrator_service.system_readiness_manager = self.mock_system_readiness_manager
    
    @pytest.mark.asyncio
    async def test_get_orchestrator_status_includes_metrics(self):
        """Test: get_orchestrator_status incluye métricas del sistema"""
        # Mock de los métodos
        self.mock_readiness_metrics.get_readiness_stats = AsyncMock(return_value={
            'total_resources': 5,
            'ready_resources': 3,
            'readiness_percentage': 60.0
        })
        
        self.mock_readiness_metrics.get_user_waiting_stats = AsyncMock(return_value={
            'pending_resources_count': 2
        })
        
        self.mock_system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            'overall_ready': False
        })
        
        # Mock del activation_guard
        self.orchestrator_service.activation_guard = Mock()
        self.orchestrator_service.activation_guard.can_activate_orchestrator = AsyncMock(return_value=False)
        
        # Obtener estado del orquestador
        status = await self.orchestrator_service.get_orchestrator_status("user_123")
        
        # Verificar que incluye métricas del sistema
        assert 'system_metrics' in status
        system_metrics = status['system_metrics']
        assert 'readiness_stats' in system_metrics
        assert 'waiting_stats' in system_metrics
        
        # Verificar valores
        assert system_metrics['readiness_stats']['total_resources'] == 5
        assert system_metrics['waiting_stats']['pending_resources_count'] == 2
    
    @pytest.mark.asyncio
    async def test_get_system_metrics(self):
        """Test: get_system_metrics obtiene métricas comprehensivas"""
        # Mock de métricas comprehensivas
        comprehensive_metrics = {
            'system_overview': {'health_score': 85},
            'readiness_stats': {'total_resources': 5},
            'waiting_stats': {'pending_resources_count': 2}
        }
        
        self.mock_readiness_metrics.get_comprehensive_metrics = AsyncMock(return_value=comprehensive_metrics)
        
        self.mock_system_readiness_manager.get_detailed_readiness_status = AsyncMock(return_value={
            'overall_ready': True
        })
        
        # Obtener métricas del sistema
        result = await self.orchestrator_service.get_system_metrics("user_123")
        
        # Verificar resultado
        assert result['type'] == 'success'
        assert 'system_metrics' in result
        assert result['system_metrics']['system_overview']['health_score'] == 85
        
        # Verificar que incluye información específica del usuario
        assert 'user_specific' in result['system_metrics']
        assert result['system_metrics']['user_specific']['user_id'] == "user_123"
    
    @pytest.mark.asyncio
    async def test_get_system_metrics_without_user(self):
        """Test: get_system_metrics funciona sin usuario específico"""
        # Mock de métricas comprehensivas
        comprehensive_metrics = {
            'system_overview': {'health_score': 85},
            'readiness_stats': {'total_resources': 5}
        }
        
        self.mock_readiness_metrics.get_comprehensive_metrics = AsyncMock(return_value=comprehensive_metrics)
        
        # Obtener métricas del sistema sin usuario
        result = await self.orchestrator_service.get_system_metrics()
        
        # Verificar resultado
        assert result['type'] == 'success'
        assert 'system_metrics' in result
        assert 'user_specific' not in result['system_metrics']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
