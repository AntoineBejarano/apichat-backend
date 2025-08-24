"""
🧪 TESTS DE PERFORMANCE - Velocidad de Respuesta

Tests para validar la velocidad de respuesta del sistema Explorer/Guided
y asegurar que cumple con los requisitos de performance.
"""

import pytest
import asyncio
import time
import statistics
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import uuid

from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.smart_fallback_service import SmartFallbackService
from app.services.ai.resource_priority_service import ResourcePriorityService
from app.services.ai.prompt_builder_service import PromptBuilderService
from app.models.enums import Mode, QueryIntent


class TestResponseSpeed:
    """Tests de performance para velocidad de respuesta"""
    
    @pytest.fixture
    def mock_user(self):
        """Usuario mock para testing"""
        return Mock(
            id=uuid.uuid4(),
            username="test_user",
            is_premium=False,
            experience_level="INTERMEDIATE"
        )
    
    @pytest.fixture
    def mock_context(self):
        """Contexto mock para testing"""
        return {
            "mode": Mode.EXPLORER,
            "user_id": uuid.uuid4(),
            "session_id": uuid.uuid4(),
            "query_type": "resource_analysis"
        }

    # =============================================================================
    # ⚡ TESTS DE VELOCIDAD DE DETECCIÓN DE MODO
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_mode_detection_speed_basic(self, mock_user, mock_context):
        """Test de velocidad básica de detección de modo"""
        service = ModeDetectionService()
        
        # Query simple para test de velocidad
        query = "¿Cuál es el estado de mi base de datos?"
        
        # Medir tiempo de ejecución
        start_time = time.perf_counter()
        result = await service.detect_mode(
            user=mock_user,
            query=query,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        execution_time = (end_time - start_time) * 1000  # Convertir a ms
        
        # Verificar resultado
        assert result is not None
        assert "suggested_mode" in result
        
        # Verificar performance (debe ser < 100ms)
        assert execution_time < 100, f"Detección de modo tardó {execution_time:.2f}ms, debe ser < 100ms"
        
        print(f"✅ Detección de modo: {execution_time:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_mode_detection_speed_complex_query(self, mock_user, mock_context):
        """Test de velocidad con query compleja"""
        service = ModeDetectionService()
        
        # Query compleja para test de velocidad
        complex_query = "¿Puedes guiarme paso a paso para analizar el rendimiento de mi base de datos PostgreSQL que está experimentando lentitud en consultas complejas con múltiples joins?"
        
        # Medir tiempo de ejecución
        start_time = time.perf_counter()
        result = await service.detect_mode(
            user=mock_user,
            query=complex_query,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        execution_time = (end_time - start_time) * 1000  # Convertir a ms
        
        # Verificar resultado
        assert result is not None
        assert "suggested_mode" in result
        
        # Verificar performance (debe ser < 150ms para queries complejas)
        assert execution_time < 150, f"Detección de modo compleja tardó {execution_time:.2f}ms, debe ser < 150ms"
        
        print(f"✅ Detección de modo compleja: {execution_time:.2f}ms")

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_mode_detection_speed_batch(self, mock_user, mock_context):
        """Test de velocidad en lote de detecciones"""
        service = ModeDetectionService()
        
        # Queries de test en lote
        test_queries = [
            "¿Qué hay en mi base de datos?",
            "¿Puedes guiarme paso a paso?",
            "Muéstrame todos los recursos",
            "Necesito ayuda estructurada",
            "¿Cuál es el rendimiento actual?",
            "Guíame en el análisis",
            "Explora libremente",
            "¿Qué estrategias tengo disponibles?",
            "Ayuda con optimización",
            "Estado del sistema"
        ]
        
        execution_times = []
        
        # Ejecutar todas las queries y medir tiempo
        for query in test_queries:
            start_time = time.perf_counter()
            result = await service.detect_mode(
                user=mock_user,
                query=query,
                context=mock_context
            )
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000
            execution_times.append(execution_time)
            
            # Verificar resultado básico
            assert result is not None
            assert "suggested_mode" in result
        
        # Calcular estadísticas
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)
        min_time = min(execution_times)
        
        # Verificar performance en lote
        assert avg_time < 80, f"Tiempo promedio en lote: {avg_time:.2f}ms, debe ser < 80ms"
        assert max_time < 120, f"Tiempo máximo en lote: {max_time:.2f}ms, debe ser < 120ms"
        
        print(f"✅ Lote de detecciones:")
        print(f"   - Promedio: {avg_time:.2f}ms")
        print(f"   - Máximo: {max_time:.2f}ms")
        print(f"   - Mínimo: {min_time:.2f}ms")

    # =============================================================================
    # 🚀 TESTS DE VELOCIDAD DE FALLBACK
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_fallback_response_speed(self, mock_user, mock_context):
        """Test de velocidad de respuesta de fallback"""
        service = SmartFallbackService()
        
        # Query ambigua que activa fallback
        ambiguous_query = "¿Qué?"
        
        # Medir tiempo de detección de fallback
        start_time = time.perf_counter()
        fallback_info = await service.detect_fallback(
            user=mock_user,
            query=ambiguous_query,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        detection_time = (end_time - start_time) * 1000
        
        # Medir tiempo de generación de respuesta
        start_time = time.perf_counter()
        response = await service.generate_fallback_response(
            user=mock_user,
            fallback_info=fallback_info,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        response_time = (end_time - start_time) * 1000
        
        # Verificar resultados
        assert fallback_info["fallback_detected"] is True
        assert response is not None
        assert "response" in response
        
        # Verificar performance
        assert detection_time < 50, f"Detección de fallback tardó {detection_time:.2f}ms, debe ser < 50ms"
        assert response_time < 100, f"Generación de respuesta tardó {response_time:.2f}ms, debe ser < 100ms"
        
        total_time = detection_time + response_time
        assert total_time < 150, f"Tiempo total de fallback: {total_time:.2f}ms, debe ser < 150ms"
        
        print(f"✅ Fallback completo: {total_time:.2f}ms (detección: {detection_time:.2f}ms, respuesta: {response_time:.2f}ms)")

    # =============================================================================
    # 📊 TESTS DE VELOCIDAD DE PRIORIZACIÓN
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_resource_priority_speed(self, mock_user, mock_context):
        """Test de velocidad de priorización de recursos"""
        service = ResourcePriorityService()
        
        # Recursos de test
        test_resources = {
            "databases": [
                {"id": i, "name": f"db_{i}", "type": "postgresql", "priority": "HIGH"} 
                for i in range(50)
            ],
            "applications": [
                {"id": i, "name": f"app_{i}", "type": "web", "priority": "MEDIUM"} 
                for i in range(100)
            ],
            "strategies": [
                {"id": i, "name": f"strategy_{i}", "type": "optimization", "priority": "LOW"} 
                for i in range(25)
            ]
        }
        
        # Medir tiempo de priorización
        start_time = time.perf_counter()
        result = await service.prioritize_resources(
            user=mock_user,
            resources=test_resources,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        execution_time = (end_time - start_time) * 1000
        
        # Verificar resultado
        assert result is not None
        assert "prioritized_resources" in result
        assert "priority_order" in result
        
        # Verificar performance (debe ser < 200ms para 175 recursos)
        assert execution_time < 200, f"Priorización de recursos tardó {execution_time:.2f}ms, debe ser < 200ms"
        
        print(f"✅ Priorización de recursos (175 recursos): {execution_time:.2f}ms")

    # =============================================================================
    # 🎯 TESTS DE VELOCIDAD DE CONSTRUCCIÓN DE PROMPTS
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_prompt_builder_speed(self, mock_user, mock_context):
        """Test de velocidad de construcción de prompts"""
        service = PromptBuilderService()
        
        # Contexto de recursos para prompt
        resource_context = {
            "database_count": 25,
            "app_count": 50,
            "strategy_count": 15,
            "cache_hit_rate": 0.85,
            "last_sync": datetime.now() - timedelta(hours=2)
        }
        
        # Medir tiempo de construcción de prompt
        start_time = time.perf_counter()
        prompt = await service.build_system_prompt(
            user=mock_user,
            mode=Mode.EXPLORER,
            resource_context=resource_context,
            context=mock_context
        )
        end_time = time.perf_counter()
        
        execution_time = (end_time - start_time) * 1000
        
        # Verificar resultado
        assert prompt is not None
        assert len(prompt) > 0
        
        # Verificar performance (debe ser < 50ms)
        assert execution_time < 50, f"Construcción de prompt tardó {execution_time:.2f}ms, debe ser < 50ms"
        
        print(f"✅ Construcción de prompt: {execution_time:.2f}ms")

    # =============================================================================
    # 🔄 TESTS DE VELOCIDAD EN CONCURRENCIA
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_mode_detection_speed(self, mock_user, mock_context):
        """Test de velocidad de detección de modo en concurrencia"""
        service = ModeDetectionService()
        
        # Queries para test concurrente
        concurrent_queries = [
            "¿Qué hay en mi base de datos?",
            "¿Puedes guiarme paso a paso?",
            "Muéstrame todos los recursos",
            "Necesito ayuda estructurada",
            "¿Cuál es el rendimiento actual?"
        ]
        
        # Función para ejecutar detección
        async def detect_mode_concurrent(query):
            start_time = time.perf_counter()
            result = await service.detect_mode(
                user=mock_user,
                query=query,
                context=mock_context
            )
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000
            return result, execution_time
        
        # Ejecutar todas las queries concurrentemente
        start_time = time.perf_counter()
        tasks = [detect_mode_concurrent(query) for query in concurrent_queries]
        results = await asyncio.gather(*tasks)
        end_time = time.perf_counter()
        
        total_time = (end_time - start_time) * 1000
        individual_times = [execution_time for _, execution_time in results]
        
        # Verificar resultados
        for result, _ in results:
            assert result is not None
            assert "suggested_mode" in result
        
        # Verificar performance concurrente
        max_individual_time = max(individual_times)
        assert max_individual_time < 100, f"Tiempo máximo individual: {max_individual_time:.2f}ms, debe ser < 100ms"
        
        # El tiempo total debe ser menor que la suma de tiempos individuales
        # debido a la concurrencia
        sum_individual_times = sum(individual_times)
        assert total_time < sum_individual_times * 0.8, f"Concurrencia no efectiva: {total_time:.2f}ms vs {sum_individual_times:.2f}ms"
        
        print(f"✅ Detección concurrente:")
        print(f"   - Tiempo total: {total_time:.2f}ms")
        print(f"   - Tiempo máximo individual: {max_individual_time:.2f}ms")
        print(f"   - Tiempo suma individual: {sum_individual_times:.2f}ms")

    # =============================================================================
    # 📈 TESTS DE ESCALABILIDAD
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_scalability_mode_detection(self, mock_user, mock_context):
        """Test de escalabilidad de detección de modo"""
        service = ModeDetectionService()
        
        # Generar queries de diferentes tamaños
        query_sizes = [10, 50, 100, 200, 500]
        performance_results = {}
        
        for size in query_sizes:
            # Generar query del tamaño especificado
            query = "¿Cuál es el estado de mi base de datos? " + "con muchos detalles " * (size // 20)
            
            # Medir tiempo
            start_time = time.perf_counter()
            result = await service.detect_mode(
                user=mock_user,
                query=query,
                context=mock_context
            )
            end_time = time.perf_counter()
            
            execution_time = (end_time - start_time) * 1000
            performance_results[size] = execution_time
            
            # Verificar resultado
            assert result is not None
            assert "suggested_mode" in result
        
        # Verificar escalabilidad (tiempo no debe crecer exponencialmente)
        for i in range(1, len(query_sizes)):
            current_size = query_sizes[i]
            previous_size = query_sizes[i-1]
            current_time = performance_results[current_size]
            previous_time = performance_results[previous_size]
            
            # El tiempo no debe crecer más de 2x por cada 2.5x de tamaño
            time_ratio = current_time / previous_time
            size_ratio = current_size / previous_size
            
            # Verificar que el crecimiento del tiempo es razonable
            assert time_ratio < size_ratio * 0.8, f"Escalabilidad pobre: {time_ratio:.2f}x tiempo para {size_ratio:.2f}x tamaño"
        
        print(f"✅ Escalabilidad de detección de modo:")
        for size, execution_time in performance_results.items():
            print(f"   - {size} caracteres: {execution_time:.2f}ms")

    # =============================================================================
    # 🎯 TESTS DE LATENCIA CRÍTICA
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_critical_latency_requirements(self, mock_user, mock_context):
        """Test de requisitos críticos de latencia"""
        services = {
            "mode_detection": ModeDetectionService(),
            "fallback": SmartFallbackService(),
            "resource_priority": ResourcePriorityService(),
            "prompt_builder": PromptBuilderService()
        }
        
        # Queries de test
        test_cases = [
            {
                "service": "mode_detection",
                "query": "¿Qué hay en mi base de datos?",
                "max_time": 100,  # ms
                "description": "Detección de modo básica"
            },
            {
                "service": "fallback",
                "query": "¿Qué?",
                "max_time": 150,  # ms
                "description": "Fallback completo"
            },
            {
                "service": "resource_priority",
                "query": "Priorizar recursos",
                "max_time": 200,  # ms
                "description": "Priorización de recursos"
            },
            {
                "service": "prompt_builder",
                "query": "Construir prompt",
                "max_time": 50,   # ms
                "description": "Construcción de prompt"
            }
        ]
        
        # Ejecutar tests de latencia crítica
        for test_case in test_cases:
            service_name = test_case["service"]
            max_time = test_case["max_time"]
            description = test_case["description"]
            
            service = services[service_name]
            
            # Medir tiempo
            start_time = time.perf_counter()
            
            if service_name == "mode_detection":
                result = await service.detect_mode(mock_user, test_case["query"], mock_context)
            elif service_name == "fallback":
                fallback_info = await service.detect_fallback(mock_user, test_case["query"], mock_context)
                result = await service.generate_fallback_response(mock_user, fallback_info, mock_context)
            elif service_name == "resource_priority":
                test_resources = {"databases": [{"id": 1, "name": "test_db", "type": "postgresql"}]}
                result = await service.prioritize_resources(mock_user, test_resources, mock_context)
            elif service_name == "prompt_builder":
                result = await service.build_system_prompt(mock_user, Mode.EXPLORER, {}, mock_context)
            
            end_time = time.perf_counter()
            execution_time = (end_time - start_time) * 1000
            
            # Verificar requisito de latencia
            assert execution_time < max_time, f"{description} tardó {execution_time:.2f}ms, debe ser < {max_time}ms"
            
            print(f"✅ {description}: {execution_time:.2f}ms (límite: {max_time}ms)")

    # =============================================================================
    # 📊 TESTS DE MÉTRICAS DE PERFORMANCE
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_performance_metrics_collection(self, mock_user, mock_context):
        """Test de recolección de métricas de performance"""
        service = ModeDetectionService()
        
        # Configurar recolección de métricas
        mock_context["collect_metrics"] = True
        
        # Ejecutar servicio con métricas
        start_time = time.perf_counter()
        result = await service.detect_mode(
            user=mock_user,
            query="¿Cuál es el estado de mi base de datos?",
            context=mock_context
        )
        end_time = time.perf_counter()
        
        execution_time = (end_time - start_time) * 1000
        
        # Verificar que se recolectaron métricas
        assert result is not None
        assert "performance_metrics" in result
        
        metrics = result["performance_metrics"]
        assert "execution_time" in metrics
        assert "memory_usage" in metrics
        assert "cpu_usage" in metrics
        
        # Verificar que las métricas son razonables
        assert metrics["execution_time"] < 1000  # ms
        assert metrics["memory_usage"] < 100     # MB
        assert metrics["cpu_usage"] < 50         # %
        
        print(f"✅ Métricas de performance recolectadas:")
        print(f"   - Tiempo de ejecución: {metrics['execution_time']:.2f}ms")
        print(f"   - Uso de memoria: {metrics['memory_usage']:.2f}MB")
        print(f"   - Uso de CPU: {metrics['cpu_usage']:.2f}%")
