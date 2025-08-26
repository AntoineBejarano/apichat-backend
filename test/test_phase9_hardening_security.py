import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
import asyncio
import time
from datetime import datetime, timezone

from app.services.security.system_hardening_service import (
    SystemHardeningService, SecurityLevel, SecurityConfig
)
from app.services.security.timeout_retry_service import (
    TimeoutRetryService, RetryConfig, TimeoutConfig, CircuitBreakerConfig,
    RetryStrategy, CircuitState
)
from app.services.security.rate_limiting_service import (
    RateLimitingService, RateLimitConfig, RateLimitResult, RateLimitStrategy, RateLimitScope
)

class TestSystemHardeningService:
    """Tests para el servicio de hardening del sistema"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        return Mock()
    
    @pytest.fixture
    def hardening_service(self, mock_factory):
        """Instancia del servicio de hardening"""
        return SystemHardeningService(mock_factory)
    
    def test_security_levels_enum(self):
        """Test de que los niveles de seguridad están definidos correctamente"""
        assert SecurityLevel.LOW == "low"
        assert SecurityLevel.MEDIUM == "medium"
        assert SecurityLevel.HIGH == "high"
        assert SecurityLevel.CRITICAL == "critical"
    
    def test_security_config_defaults(self):
        """Test de configuración por defecto"""
        config = SecurityConfig()
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0
        assert config.rate_limit_requests == 100
        assert config.enable_validation == True
    
    def test_hardening_service_initialization(self, hardening_service):
        """Test de inicialización del servicio"""
        assert hardening_service.factory is not None
        assert len(hardening_service.level_configs) == 4
        assert SecurityLevel.LOW in hardening_service.level_configs
        assert SecurityLevel.CRITICAL in hardening_service.level_configs
    
    def test_level_configs_different(self, hardening_service):
        """Test de que las configuraciones por nivel son diferentes"""
        low_config = hardening_service.level_configs[SecurityLevel.LOW]
        critical_config = hardening_service.level_configs[SecurityLevel.CRITICAL]
        
        assert low_config.max_retries < critical_config.max_retries
        assert low_config.timeout_seconds < critical_config.timeout_seconds
        assert low_config.rate_limit_requests > critical_config.rate_limit_requests
    
    @pytest.mark.asyncio
    async def test_secure_operation_success(self, hardening_service):
        """Test de operación segura exitosa"""
        async def test_operation(data="test"):
            return f"success: {data}"
        
        result = await hardening_service.secure_operation(
            test_operation,
            SecurityLevel.MEDIUM,
            data="test_data"
        )
        
        assert result == "success: test_data"
    
    @pytest.mark.asyncio
    async def test_secure_operation_validation_failure(self, hardening_service):
        """Test de fallo en validación de entrada"""
        async def test_operation(data="test"):
            return f"success: {data}"
        
        # Simular datos demasiado grandes
        large_data = "x" * (hardening_service.level_configs[SecurityLevel.HIGH].max_request_size + 1000)
        
        with pytest.raises(ValueError, match="Datos demasiado grandes"):
            await hardening_service.secure_operation(
                test_operation,
                SecurityLevel.HIGH,
                data=large_data
            )
    
    @pytest.mark.asyncio
    async def test_content_security_validation(self, hardening_service):
        """Test de validación de contenido por seguridad"""
        # Contenido sospechoso
        suspicious_content = "javascript:alert('xss')"
        
        with pytest.raises(ValueError, match="Contenido sospechoso detectado"):
            await hardening_service._validate_content_security(
                suspicious_content,
                SecurityLevel.HIGH
            )
        
        # Contenido normal no debe fallar
        normal_content = "SELECT * FROM users WHERE id = 1"
        await hardening_service._validate_content_security(
            normal_content,
            SecurityLevel.HIGH
        )
    
    @pytest.mark.asyncio
    async def test_rate_limit_check(self, hardening_service):
        """Test de verificación de rate limit"""
        # Primera verificación debe pasar
        await hardening_service._check_rate_limit(SecurityLevel.MEDIUM)
        
        # Configurar límite muy bajo para forzar fallo
        hardening_service.level_configs[SecurityLevel.MEDIUM].rate_limit_requests = 1
        
        # Segunda verificación debe fallar
        with pytest.raises(Exception, match="Rate limit excedido"):
            await hardening_service._check_rate_limit(SecurityLevel.MEDIUM)
    
    @pytest.mark.asyncio
    async def test_get_security_status(self, hardening_service):
        """Test de obtención de estado de seguridad"""
        status = await hardening_service.get_security_status()
        
        assert "security_levels" in status
        assert "rate_limiters" in status
        assert "security_events_count" in status
        assert "timestamp" in status
        
        # Verificar que todos los niveles están incluidos
        for level in SecurityLevel:
            assert level.value in status["security_levels"]
    
    @pytest.mark.asyncio
    async def test_update_security_config(self, hardening_service):
        """Test de actualización de configuración de seguridad"""
        result = await hardening_service.update_security_config(
            SecurityLevel.MEDIUM,
            max_retries=5,
            timeout_seconds=45.0
        )
        
        assert result["success"] == True
        assert "Configuración actualizada" in result["message"]
        
        # Verificar que la configuración se actualizó
        updated_config = hardening_service.level_configs[SecurityLevel.MEDIUM]
        assert updated_config.max_retries == 5
        assert updated_config.timeout_seconds == 45.0
    
    @pytest.mark.asyncio
    async def test_update_security_config_invalid(self, hardening_service):
        """Test de actualización con valores inválidos"""
        result = await hardening_service.update_security_config(
            SecurityLevel.MEDIUM,
            max_retries=-1  # Valor inválido
        )
        
        assert result["success"] == False
        assert "error" in result

class TestTimeoutRetryService:
    """Tests para el servicio de timeout y reintentos"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        return Mock()
    
    @pytest.fixture
    def timeout_service(self, mock_factory):
        """Instancia del servicio de timeout"""
        return TimeoutRetryService(mock_factory)
    
    def test_retry_strategies_enum(self):
        """Test de estrategias de reintento"""
        assert RetryStrategy.LINEAR == "linear"
        assert RetryStrategy.EXPONENTIAL == "exponential"
        assert RetryStrategy.FIBONACCI == "fibonacci"
    
    def test_circuit_states_enum(self):
        """Test de estados del circuit breaker"""
        assert CircuitState.CLOSED == "closed"
        assert CircuitState.OPEN == "open"
        assert CircuitState.HALF_OPEN == "half_open"
    
    def test_retry_config_defaults(self):
        """Test de configuración por defecto de reintentos"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.strategy == RetryStrategy.EXPONENTIAL
        assert config.jitter == True
    
    def test_timeout_config_defaults(self):
        """Test de configuración por defecto de timeouts"""
        config = TimeoutConfig()
        assert config.operation_timeout == 30.0
        assert config.total_timeout == 300.0
        assert config.connection_timeout == 10.0
    
    def test_circuit_breaker_config_defaults(self):
        """Test de configuración por defecto del circuit breaker"""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
    
    def test_timeout_service_initialization(self, timeout_service):
        """Test de inicialización del servicio"""
        assert timeout_service.factory is not None
        assert timeout_service.default_retry_config is not None
        assert timeout_service.default_timeout_config is not None
        assert timeout_service.default_circuit_config is not None
    
    def test_calculate_retry_delay_linear(self, timeout_service):
        """Test de cálculo de delay lineal"""
        config = RetryConfig(strategy=RetryStrategy.LINEAR, base_delay=1.0)
        
        delay1 = timeout_service._calculate_retry_delay(0, config)
        delay2 = timeout_service._calculate_retry_delay(1, config)
        delay3 = timeout_service._calculate_retry_delay(2, config)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 3.0
    
    def test_calculate_retry_delay_exponential(self, timeout_service):
        """Test de cálculo de delay exponencial"""
        config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, base_delay=1.0)
        
        delay1 = timeout_service._calculate_retry_delay(0, config)
        delay2 = timeout_service._calculate_retry_delay(1, config)
        delay3 = timeout_service._calculate_retry_delay(2, config)
        
        assert delay1 == 1.0
        assert delay2 == 2.0
        assert delay3 == 4.0
    
    def test_fibonacci_calculation(self, timeout_service):
        """Test de cálculo de Fibonacci"""
        assert timeout_service._fibonacci(0) == 0
        assert timeout_service._fibonacci(1) == 1
        assert timeout_service._fibonacci(2) == 1
        assert timeout_service._fibonacci(3) == 2
        assert timeout_service._fibonacci(4) == 3
        assert timeout_service._fibonacci(5) == 5
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_retry_success(self, timeout_service):
        """Test de ejecución exitosa con timeout y reintentos"""
        async def test_operation():
            return "success"
        
        result = await timeout_service.execute_with_timeout_retry(
            test_operation,
            operation_name="test_op"
        )
        
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_execute_with_timeout_retry_timeout(self, timeout_service):
        """Test de timeout en ejecución"""
        async def slow_operation():
            await asyncio.sleep(2.0)  # Más lento que el timeout
            return "success"
        
        # Configurar timeout muy bajo
        timeout_service.default_timeout_config.operation_timeout = 0.1
        
        with pytest.raises(Exception, match="Timeout después de"):
            await timeout_service.execute_with_timeout_retry(
                slow_operation,
                operation_name="slow_op"
            )
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self, timeout_service):
        """Test de circuit breaker en estado cerrado"""
        # Circuit breaker debe estar cerrado inicialmente
        can_execute = await timeout_service._can_execute_circuit_breaker("test_key")
        assert can_execute == True
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_failure_threshold(self, timeout_service):
        """Test de umbral de fallos del circuit breaker"""
        key = "test_cb"
        
        # Simular fallos hasta alcanzar el umbral
        for i in range(timeout_service.default_circuit_config.failure_threshold):
            await timeout_service._record_circuit_breaker_failure(key)
        
        # El circuit breaker debe estar abierto
        can_execute = await timeout_service._can_execute_circuit_breaker(key)
        assert can_execute == False
        
        # Verificar estado
        status = await timeout_service.get_circuit_breaker_status(key)
        assert status["state"] == "open"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery(self, timeout_service):
        """Test de recuperación del circuit breaker"""
        key = "test_cb_recovery"
        
        # Abrir circuit breaker
        for i in range(timeout_service.default_circuit_config.failure_threshold):
            await timeout_service._record_circuit_breaker_failure(key)
        
        # Simular paso del tiempo para recuperación
        timeout_service.circuit_breakers[key]["last_state_change"] = (
            time.time() - timeout_service.default_circuit_config.recovery_timeout - 1
        )
        
        # Debe cambiar a half-open
        can_execute = await timeout_service._can_execute_circuit_breaker(key)
        assert can_execute == True
        
        # Verificar estado
        status = await timeout_service.get_circuit_breaker_status(key)
        assert status["state"] == "half_open"
    
    @pytest.mark.asyncio
    async def test_get_retry_statistics(self, timeout_service):
        """Test de obtención de estadísticas de reintentos"""
        # Ejecutar algunas operaciones para generar estadísticas
        async def test_operation():
            return "success"
        
        await timeout_service.execute_with_timeout_retry(test_operation, "test_op1")
        await timeout_service.execute_with_timeout_retry(test_operation, "test_op2")
        
        # Obtener estadísticas
        stats = await timeout_service.get_retry_statistics()
        assert "operations" in stats
        assert "test_op1" in stats["operations"]
        assert "test_op2" in stats["operations"]
        
        # Verificar estadísticas específicas
        op1_stats = await timeout_service.get_retry_statistics("test_op1")
        assert op1_stats["total_calls"] == 1
        assert op1_stats["successful_calls"] == 1
        assert op1_stats["success_rate"] == 100.0

class TestRateLimitingService:
    """Tests para el servicio de rate limiting"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock"""
        return Mock()
    
    @pytest.fixture
    def rate_limit_service(self, mock_factory):
        """Instancia del servicio de rate limiting"""
        return RateLimitingService(mock_factory)
    
    def test_rate_limit_strategies_enum(self):
        """Test de estrategias de rate limiting"""
        assert RateLimitStrategy.FIXED_WINDOW == "fixed_window"
        assert RateLimitStrategy.SLIDING_WINDOW == "sliding_window"
        assert RateLimitStrategy.TOKEN_BUCKET == "token_bucket"
        assert RateLimitStrategy.LEAKY_BUCKET == "leaky_bucket"
    
    def test_rate_limit_scopes_enum(self):
        """Test de scopes de rate limiting"""
        assert RateLimitScope.USER == "user"
        assert RateLimitScope.IP == "ip"
        assert RateLimitScope.ENDPOINT == "endpoint"
        assert RateLimitScope.GLOBAL == "global"
    
    def test_rate_limit_config_defaults(self):
        """Test de configuración por defecto"""
        config = RateLimitConfig()
        assert config.max_requests == 100
        assert config.window_seconds == 60
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW
    
    def test_rate_limit_service_initialization(self, rate_limit_service):
        """Test de inicialización del servicio"""
        assert rate_limit_service.factory is not None
        assert len(rate_limit_service.default_configs) == 4
        assert RateLimitScope.USER in rate_limit_service.default_configs
        assert RateLimitScope.GLOBAL in rate_limit_service.default_configs
    
    @pytest.mark.asyncio
    async def test_fixed_window_rate_limiting(self, rate_limit_service):
        """Test de rate limiting de ventana fija"""
        # Configurar límite muy bajo para testing
        config = RateLimitConfig(
            max_requests=2,
            window_seconds=60,
            strategy=RateLimitStrategy.FIXED_WINDOW
        )
        
        # Primera request debe pasar
        result1 = await rate_limit_service._check_fixed_window("test_key", config)
        assert result1.allowed == True
        assert result1.remaining == 1
        
        # Segunda request debe pasar
        result2 = await rate_limit_service._check_fixed_window("test_key", config)
        assert result2.allowed == True
        assert result2.remaining == 0
        
        # Tercera request debe fallar
        result3 = await rate_limit_service._check_fixed_window("test_key", config)
        assert result3.allowed == False
        assert result3.limit_exceeded == True
    
    @pytest.mark.asyncio
    async def test_sliding_window_rate_limiting(self, rate_limit_service):
        """Test de rate limiting de ventana deslizante"""
        config = RateLimitConfig(
            max_requests=2,
            window_seconds=1,  # Ventana muy pequeña para testing
            strategy=RateLimitStrategy.SLIDING_WINDOW
        )
        
        # Primera request debe pasar
        result1 = await rate_limit_service._check_sliding_window("test_key", config)
        assert result1.allowed == True
        assert result1.remaining == 1
        
        # Segunda request debe pasar
        result2 = await rate_limit_service._check_sliding_window("test_key", config)
        assert result2.allowed == True
        assert result2.remaining == 0
        
        # Tercera request debe fallar
        result3 = await rate_limit_service._check_sliding_window("test_key", config)
        assert result3.allowed == False
        assert result3.limit_exceeded == True
    
    @pytest.mark.asyncio
    async def test_token_bucket_rate_limiting(self, rate_limit_service):
        """Test de rate limiting con token bucket"""
        config = RateLimitConfig(
            max_requests=2,
            window_seconds=60,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_size=2,
            refill_rate=0.1  # Muy lento para testing
        )
        
        # Primera request debe pasar
        result1 = await rate_limit_service._check_token_bucket("test_key", config)
        assert result1.allowed == True
        assert result1.remaining == 1
        
        # Segunda request debe pasar
        result2 = await rate_limit_service._check_token_bucket("test_key", config)
        assert result2.allowed == True
        assert result2.remaining == 0
        
        # Tercera request debe fallar
        result3 = await rate_limit_service._check_token_bucket("test_key", config)
        assert result3.allowed == False
        assert result3.limit_exceeded == True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_with_strategy(self, rate_limit_service):
        """Test de verificación de rate limit con estrategia específica"""
        # Usar estrategia de ventana fija
        result = await rate_limit_service.check_rate_limit(
            RateLimitScope.USER,
            "test_user",
            RateLimitConfig(
                max_requests=1,
                window_seconds=60,
                strategy=RateLimitStrategy.FIXED_WINDOW
            )
        )
        
        assert result.allowed == True
        assert result.remaining == 0
        
        # Segunda request debe fallar
        result2 = await rate_limit_service.check_rate_limit(
            RateLimitScope.USER,
            "test_user",
            RateLimitConfig(
                max_requests=1,
                window_seconds=60,
                strategy=RateLimitStrategy.FIXED_WINDOW
            )
        )
        
        assert result2.allowed == False
        assert result2.limit_exceeded == True
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_status(self, rate_limit_service):
        """Test de obtención de estado de rate limiting"""
        # Crear algunos limiters
        await rate_limit_service.check_rate_limit(RateLimitScope.USER, "user1")
        await rate_limit_service.check_rate_limit(RateLimitScope.IP, "192.168.1.1")
        
        # Obtener estado general
        status = await rate_limit_service.get_rate_limit_status()
        assert "limiters" in status
        assert status["total_limiters"] >= 2
        
        # Obtener estado específico
        user_status = await rate_limit_service.get_rate_limit_status(
            RateLimitScope.USER, "user1"
        )
        assert user_status["scope"] == "user"
        assert user_status["identifier"] == "user1"
    
    @pytest.mark.asyncio
    async def test_reset_rate_limits(self, rate_limit_service):
        """Test de reseteo de rate limits"""
        # Crear algunos limiters
        await rate_limit_service.check_rate_limit(RateLimitScope.USER, "user1")
        await rate_limit_service.check_rate_limit(RateLimitScope.USER, "user2")
        
        # Verificar que existen
        status_before = await rate_limit_service.get_rate_limit_status()
        assert status_before["total_limiters"] >= 2
        
        # Resetear todos
        await rate_limit_service.reset_rate_limits()
        
        # Verificar que se resetearon
        status_after = await rate_limit_service.get_rate_limit_status()
        assert status_after["total_limiters"] == 0
    
    @pytest.mark.asyncio
    async def test_get_rate_limit_metrics(self, rate_limit_service):
        """Test de obtención de métricas de rate limiting"""
        metrics = await rate_limit_service.get_rate_limit_metrics()
        
        assert "total_limiters" in metrics
        assert "limiters_by_scope" in metrics
        assert "configs" in metrics
        assert "timestamp" in metrics
        
        # Verificar que todas las configuraciones están incluidas
        for scope in RateLimitScope:
            assert scope.value in metrics["configs"]

class TestSecurityIntegration:
    """Tests de integración de servicios de seguridad"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock con servicios de seguridad"""
        factory = Mock()
        
        # Mock de servicios de seguridad
        security_factory = Mock()
        factory.security = security_factory
        
        # Mock de SystemHardeningService
        hardening_service = Mock()
        hardening_service.get_security_status = AsyncMock(return_value={
            "security_levels": {"medium": {"max_retries": 3}},
            "rate_limiters": {},
            "security_events_count": 0,
            "timestamp": "2025-08-27T00:00:00Z"
        })
        hardening_service.get_security_metrics = Mock(return_value={
            "total_security_events": 0,
            "error_events": 0,
            "success_events": 0,
            "error_rate": 0.0,
            "timestamp": "2025-08-27T00:00:00Z"
        })
        security_factory.get_system_hardening_service.return_value = hardening_service
        
        # Mock de TimeoutRetryService
        timeout_service = Mock()
        timeout_service.get_circuit_breaker_status = AsyncMock(return_value={
            "circuit_breakers": {},
            "total_circuit_breakers": 0
        })
        timeout_service.get_retry_statistics = AsyncMock(return_value={
            "operations": {},
            "total_operations": 0
        })
        security_factory.get_timeout_retry_service.return_value = timeout_service
        
        # Mock de RateLimitingService
        rate_limit_service = Mock()
        rate_limit_service.get_rate_limit_status = AsyncMock(return_value={
            "limiters": {},
            "total_limiters": 0
        })
        rate_limit_service.get_rate_limit_metrics = AsyncMock(return_value={
            "total_limiters": 0,
            "limiters_by_scope": {},
            "configs": {},
            "timestamp": "2025-08-27T00:00:00Z"
        })
        security_factory.get_rate_limiting_service.return_value = rate_limit_service
        
        return factory
    
    @pytest.mark.asyncio
    async def test_security_services_work_together(self, mock_factory):
        """Test de que los servicios de seguridad trabajan juntos"""
        # Verificar que todos los servicios están disponibles
        assert mock_factory.security.get_system_hardening_service() is not None
        assert mock_factory.security.get_timeout_retry_service() is not None
        assert mock_factory.security.get_rate_limiting_service() is not None
        
        # Verificar que pueden obtener estado
        hardening_status = await mock_factory.security.get_system_hardening_service().get_security_status()
        assert "security_levels" in hardening_status
        
        timeout_status = await mock_factory.security.get_timeout_retry_service().get_circuit_breaker_status()
        assert "total_circuit_breakers" in timeout_status
        
        rate_limit_status = await mock_factory.security.get_rate_limiting_service().get_rate_limit_status()
        assert "total_limiters" in rate_limit_status
    
    @pytest.mark.asyncio
    async def test_security_configuration_consistency(self, mock_factory):
        """Test de consistencia en configuración de seguridad"""
        hardening_service = mock_factory.security.get_system_hardening_service()
        
        # Verificar que los niveles de seguridad tienen configuraciones válidas
        status = await hardening_service.get_security_status()
        
        for level_name, config in status["security_levels"].items():
            assert config["max_retries"] > 0
            assert config["timeout_seconds"] > 0
            assert config["rate_limit_requests"] > 0
            assert config["rate_limit_window"] > 0
    
    @pytest.mark.asyncio
    async def test_security_metrics_consistency(self, mock_factory):
        """Test de consistencia en métricas de seguridad"""
        hardening_service = mock_factory.security.get_system_hardening_service()
        metrics = hardening_service.get_security_metrics()
        
        # Verificar que las métricas son consistentes
        assert metrics["total_security_events"] >= 0
        assert metrics["error_events"] >= 0
        assert metrics["success_events"] >= 0
        assert 0 <= metrics["error_rate"] <= 100
        
        # Verificar que el total es la suma
        total_calculated = metrics["error_events"] + metrics["success_events"]
        assert metrics["total_security_events"] == total_calculated
