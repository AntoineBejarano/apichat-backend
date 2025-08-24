"""
🧪 TESTS DE INTEGRACIÓN - Flujo de Transiciones de Modo

Tests para validar el flujo completo de transiciones entre modos
Explorer y Guided del sistema.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
import uuid

from app.services.ai.mode_detection_service import ModeDetectionService
from app.services.ai.mode_transition_service import ModeTransitionService
from app.services.ai.mode_transition_orchestrator import ModeTransitionOrchestrator
from app.services.ai.smart_fallback_service import SmartFallbackService
from app.services.ai.resource_priority_service import ResourcePriorityService
from app.models.enums import Mode, QueryIntent, FallbackType


class TestModeTransitionFlow:
    """Tests de integración para el flujo de transiciones de modo"""
    
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
    def mock_session(self):
        """Sesión mock para testing"""
        return Mock(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            mode=Mode.EXPLORER,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True
        )
    
    @pytest.fixture
    def mock_database_service(self):
        """Servicio de base de datos mock"""
        service = Mock()
        service.get_user_by_id = AsyncMock(return_value=mock_user())
        service.get_session_by_id = AsyncMock(return_value=mock_session())
        service.update_session = AsyncMock(return_value=True)
        service.create_session = AsyncMock(return_value=mock_session())
        return service
    
    @pytest.fixture
    def mock_redis_service(self):
        """Servicio de Redis mock"""
        service = Mock()
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock(return_value=True)
        service.delete = AsyncMock(return_value=True)
        return service

    # =============================================================================
    # 🔄 TESTS DE FLUJO COMPLETO EXPLORER → GUIDED
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_explorer_to_guided_transition_flow(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo de transición Explorer → Guided"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        resource_priority = ResourcePriorityService()
        
        # 2. Simular query que sugiere cambio a modo Guided
        query = "¿Puedes guiarme paso a paso para analizar mi base de datos?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "previous_queries": ["¿Qué hay en mi DB?"],
            "user_preferences": {"learning_style": "step_by_step"}
        }
        
        # 3. Detectar modo sugerido
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        assert detection_result is not None
        assert "suggested_mode" in detection_result
        assert detection_result["suggested_mode"] == Mode.GUIDED
        assert detection_result["confidence"] >= 0.7
        
        # 4. Evaluar si la transición es necesaria
        transition_evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context=context,
            detection_result=detection_result
        )
        
        assert transition_evaluation is not None
        assert "transition_recommended" in transition_evaluation
        assert transition_evaluation["transition_recommended"] is True
        assert "reasoning" in transition_evaluation
        
        # 5. Ejecutar transición
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.EXPLORER,
            to_mode=Mode.GUIDED,
            context=context,
            evaluation=transition_evaluation
        )
        
        assert transition_result is not None
        assert "transition_successful" in transition_result
        assert transition_result["transition_successful"] is True
        assert "new_mode" in transition_result
        assert transition_result["new_mode"] == Mode.GUIDED
        
        # 6. Verificar que la sesión se actualizó
        mock_database_service.update_session.assert_called_once()
        
        # 7. Verificar que se guardó en cache
        mock_redis_service.set.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_guided_to_explorer_transition_flow(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo de transición Guided → Explorer"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        
        # 2. Simular query que sugiere cambio a modo Explorer
        query = "Muéstrame todos los recursos disponibles para que pueda explorar libremente"
        context = {
            "mode": Mode.GUIDED,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "previous_queries": ["Guíame paso a paso", "¿Cuál es el siguiente paso?"],
            "user_preferences": {"exploration_style": "free_form"}
        }
        
        # 3. Detectar modo sugerido
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        assert detection_result is not None
        assert detection_result["suggested_mode"] == Mode.EXPLORER
        assert detection_result["confidence"] >= 0.7
        
        # 4. Evaluar transición
        transition_evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.GUIDED,
            suggested_mode=Mode.EXPLORER,
            context=context,
            detection_result=detection_result
        )
        
        assert transition_evaluation["transition_recommended"] is True
        
        # 5. Ejecutar transición
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.GUIDED,
            to_mode=Mode.EXPLORER,
            context=context,
            evaluation=transition_evaluation
        )
        
        assert transition_result["transition_successful"] is True
        assert transition_result["new_mode"] == Mode.EXPLORER

    # =============================================================================
    # 🚨 TESTS DE FLUJO CON FALLBACK
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transition_flow_with_fallback(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo de transición con activación de fallback"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        
        # 2. Simular query ambigua que activa fallback
        ambiguous_query = "¿Qué?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "fallback_count": 1
        }
        
        # 3. Detectar modo (debería fallar)
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=ambiguous_query,
            context=context
        )
        
        # 4. Verificar que se activó fallback
        fallback_detection = await fallback_service.detect_fallback(
            user=mock_user,
            query=ambiguous_query,
            context=context
        )
        
        assert fallback_detection["fallback_detected"] is True
        assert fallback_detection["fallback_type"] == FallbackType.AMBIGUOUS_QUERY
        
        # 5. Generar respuesta de fallback
        fallback_response = await fallback_service.generate_fallback_response(
            user=mock_user,
            fallback_info=fallback_detection,
            context=context
        )
        
        assert fallback_response is not None
        assert "response" in fallback_response
        assert "options" in fallback_response
        
        # 6. Verificar que no se ejecutó transición
        # (el fallback debería manejar la situación)
        assert "transition_successful" not in fallback_response

    # =============================================================================
    # 🔄 TESTS DE FLUJO CON TRANSICIONES MÚLTIPLES
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_multiple_transitions_flow(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo con múltiples transiciones en secuencia"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        
        # 2. Secuencia de queries que provocan transiciones
        transition_sequence = [
            {
                "query": "¿Puedes guiarme paso a paso?",
                "expected_mode": Mode.GUIDED,
                "context": {"mode": Mode.EXPLORER, "user_preferences": {"learning_style": "guided"}}
            },
            {
                "query": "Muéstrame todo para explorar libremente",
                "expected_mode": Mode.EXPLORER,
                "context": {"mode": Mode.GUIDED, "user_preferences": {"exploration_style": "free_form"}}
            },
            {
                "query": "Necesito ayuda estructurada",
                "expected_mode": Mode.GUIDED,
                "context": {"mode": Mode.EXPLORER, "user_preferences": {"help_style": "structured"}}
            }
        ]
        
        current_mode = Mode.EXPLORER
        
        # 3. Ejecutar secuencia de transiciones
        for i, transition in enumerate(transition_sequence):
            # Detectar modo sugerido
            detection_result = await mode_detection.detect_mode(
                user=mock_user,
                query=transition["query"],
                context={**transition["context"], "user_id": mock_user.id, "session_id": mock_session.id}
            )
            
            assert detection_result["suggested_mode"] == transition["expected_mode"]
            
            # Evaluar transición
            evaluation = await mode_transition.evaluate_transition(
                user=mock_user,
                current_mode=current_mode,
                suggested_mode=transition["expected_mode"],
                context=transition["context"],
                detection_result=detection_result
            )
            
            if evaluation["transition_recommended"]:
                # Ejecutar transición
                result = await orchestrator.execute_transition(
                    user=mock_user,
                    from_mode=current_mode,
                    to_mode=transition["expected_mode"],
                    context=transition["context"],
                    evaluation=evaluation
                )
                
                assert result["transition_successful"] is True
                current_mode = transition["expected_mode"]
                
                # Verificar que se actualizó la sesión
                mock_database_service.update_session.assert_called()
                
                # Verificar que se guardó en cache
                mock_redis_service.set.assert_called()

    # =============================================================================
    # 📊 TESTS DE FLUJO CON MÉTRICAS Y LOGGING
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transition_flow_with_metrics(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo de transición con recolección de métricas"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        
        # 2. Simular transición con métricas
        query = "¿Puedes guiarme paso a paso?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "collect_metrics": True
        }
        
        # 3. Ejecutar flujo completo con métricas
        start_time = datetime.now()
        
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context=context,
            detection_result=detection_result
        )
        
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.EXPLORER,
            to_mode=Mode.GUIDED,
            context=context,
            evaluation=evaluation
        )
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 4. Verificar métricas
        assert transition_result["transition_successful"] is True
        assert "metrics" in transition_result
        assert "detection_time" in transition_result["metrics"]
        assert "evaluation_time" in transition_result["metrics"]
        assert "transition_time" in transition_result["metrics"]
        assert "total_time" in transition_result["metrics"]
        
        # Verificar que el tiempo total es razonable
        assert transition_result["metrics"]["total_time"] < 5.0  # Menos de 5 segundos

    # =============================================================================
    # 🎯 TESTS DE FLUJO CON VALIDACIONES
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transition_flow_validation(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo de transición con validaciones"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        
        # 2. Simular transición con validaciones
        query = "¿Puedes guiarme paso a paso?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "validate_transition": True
        }
        
        # 3. Ejecutar flujo con validaciones
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        # Validar detección
        assert detection_result["suggested_mode"] == Mode.GUIDED
        assert detection_result["confidence"] >= 0.7
        
        evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context=context,
            detection_result=detection_result
        )
        
        # Validar evaluación
        assert evaluation["transition_recommended"] is True
        assert "validation_checks" in evaluation
        assert all(check["passed"] for check in evaluation["validation_checks"])
        
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.EXPLORER,
            to_mode=Mode.GUIDED,
            context=context,
            evaluation=evaluation
        )
        
        # Validar resultado
        assert transition_result["transition_successful"] is True
        assert "validation_summary" in transition_result
        assert transition_result["validation_summary"]["all_validations_passed"] is True

    # =============================================================================
    # 🚨 TESTS DE FLUJO CON ERRORES
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transition_flow_with_errors(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo de transición con manejo de errores"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        
        # 2. Simular error en base de datos
        mock_database_service.update_session.side_effect = Exception("Database error")
        
        query = "¿Puedes guiarme paso a paso?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id
        }
        
        # 3. Ejecutar flujo hasta el error
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context=context,
            detection_result=detection_result
        )
        
        # 4. Intentar transición (debería fallar)
        with pytest.raises(Exception, match="Database error"):
            await orchestrator.execute_transition(
                user=mock_user,
                from_mode=Mode.EXPLORER,
                to_mode=Mode.GUIDED,
                context=context,
                evaluation=evaluation
            )
        
        # 5. Verificar que se activó fallback por error
        fallback_detection = await fallback_service.detect_fallback(
            user=mock_user,
            query=query,
            context={**context, "error_occurred": True}
        )
        
        assert fallback_detection["fallback_detected"] is True
        assert fallback_detection["fallback_type"] == FallbackType.TECHNICAL_ERROR

    # =============================================================================
    # 🔧 TESTS DE FLUJO CON CONFIGURACIÓN PERSONALIZADA
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_transition_flow_custom_config(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo de transición con configuración personalizada"""
        
        # 1. Configurar servicios con configuración personalizada
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        
        # 2. Configuración personalizada
        custom_config = {
            "transition_threshold": 0.6,  # Umbral más bajo
            "max_transitions_per_session": 10,
            "transition_cooldown": 30,  # 30 segundos
            "preferred_modes": [Mode.GUIDED, Mode.EXPLORER]
        }
        
        # 3. Aplicar configuración personalizada
        mode_detection.update_config(custom_config)
        mode_transition.update_config(custom_config)
        orchestrator.update_config(custom_config)
        
        # 4. Ejecutar flujo con configuración personalizada
        query = "¿Puedes ayudarme?"
        context = {
            "mode": Mode.EXPLORER,
            "user_id": mock_user.id,
            "session_id": mock_session.id
        }
        
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=query,
            context=context
        )
        
        # Con umbral más bajo, debería detectar Guided
        assert detection_result["suggested_mode"] == Mode.GUIDED
        assert detection_result["confidence"] >= 0.6  # Umbral personalizado
        
        evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context=context,
            detection_result=detection_result
        )
        
        assert evaluation["transition_recommended"] is True
        
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.EXPLORER,
            to_mode=Mode.GUIDED,
            context=context,
            evaluation=evaluation
        )
        
        assert transition_result["transition_successful"] is True
        assert "config_applied" in transition_result
        assert transition_result["config_applied"] == custom_config
