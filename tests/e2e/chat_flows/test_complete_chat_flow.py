"""
🧪 TESTS END-TO-END - Flujo Completo de Chat

Tests para validar el flujo completo de chat del sistema Explorer/Guided,
simulando interacciones reales de usuario.
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
from app.services.ai.prompt_builder_service import PromptBuilderService
from app.services.ai.smart_ai_orchestrator import SmartAIOrchestrator
from app.models.enums import Mode, QueryIntent, FallbackType


class TestCompleteChatFlow:
    """Tests end-to-end para el flujo completo de chat"""
    
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
    # 🎭 TESTS DE FLUJO COMPLETO DE EXPLORACIÓN
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_exploration_flow(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo de exploración"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        resource_priority = ResourcePriorityService()
        prompt_builder = PromptBuilderService()
        ai_orchestrator = SmartAIOrchestrator()
        
        # 2. Simular sesión de exploración completa
        exploration_flow = [
            {
                "query": "¿Qué hay en mi base de datos?",
                "expected_mode": Mode.EXPLORER,
                "expected_response_type": "resource_listing",
                "user_intent": "explore_resources"
            },
            {
                "query": "Muéstrame más detalles de la base de datos PostgreSQL",
                "expected_mode": Mode.EXPLORER,
                "expected_response_type": "detailed_analysis",
                "user_intent": "deep_exploration"
            },
            {
                "query": "¿Cuál es el rendimiento actual?",
                "expected_mode": Mode.EXPLORER,
                "expected_response_type": "performance_metrics",
                "user_intent": "performance_check"
            },
            {
                "query": "Explora las aplicaciones disponibles",
                "expected_mode": Mode.EXPLORER,
                "expected_response_type": "application_listing",
                "user_intent": "application_exploration"
            }
        ]
        
        current_mode = Mode.EXPLORER
        session_context = {
            "mode": current_mode,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "exploration_history": [],
            "resource_context": {
                "database_count": 5,
                "app_count": 12,
                "strategy_count": 8
            }
        }
        
        # 3. Ejecutar flujo de exploración
        for i, step in enumerate(exploration_flow):
            print(f"\n🔍 Paso {i+1}: {step['query']}")
            
            # Detectar modo
            detection_result = await mode_detection.detect_mode(
                user=mock_user,
                query=step["query"],
                context=session_context
            )
            
            # Verificar que se mantiene en modo Explorer
            assert detection_result["suggested_mode"] == Mode.EXPLORER
            assert detection_result["confidence"] >= 0.7
            
            # Construir prompt para el modo
            system_prompt = await prompt_builder.build_system_prompt(
                user=mock_user,
                mode=current_mode,
                resource_context=session_context["resource_context"],
                context=session_context
            )
            
            assert system_prompt is not None
            assert "EXPLORER" in system_prompt.upper()
            
            # Priorizar recursos si es necesario
            if "resource" in step["query"].lower():
                priority_result = await resource_priority.prioritize_resources(
                    user=mock_user,
                    resources=session_context["resource_context"],
                    context=session_context
                )
                
                assert priority_result is not None
                assert "priority_order" in priority_result
            
            # Simular respuesta del orquestador de IA
            ai_response = await ai_orchestrator.process_query(
                user=mock_user,
                query=step["query"],
                mode=current_mode,
                context=session_context
            )
            
            assert ai_response is not None
            assert "response" in ai_response
            assert "mode" in ai_response
            assert ai_response["mode"] == Mode.EXPLORER
            
            # Actualizar contexto de sesión
            session_context["exploration_history"].append({
                "query": step["query"],
                "response": ai_response["response"],
                "timestamp": datetime.now(),
                "mode": current_mode
            })
            
            print(f"✅ Respuesta generada en modo {current_mode}")
        
        # 4. Verificar que se mantuvo en modo Explorer
        assert current_mode == Mode.EXPLORER
        assert len(session_context["exploration_history"]) == 4
        
        print(f"\n🎯 Flujo de exploración completado exitosamente")
        print(f"   - Modo mantenido: {current_mode}")
        print(f"   - Pasos ejecutados: {len(session_context['exploration_history'])}")

    # =============================================================================
    # 🎯 TESTS DE FLUJO COMPLETO GUIADO
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_guided_flow(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo guiado"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        prompt_builder = PromptBuilderService()
        ai_orchestrator = SmartAIOrchestrator()
        
        # 2. Simular transición a modo Guided
        initial_query = "¿Puedes guiarme paso a paso para analizar mi base de datos?"
        
        detection_result = await mode_detection.detect_mode(
            user=mock_user,
            query=initial_query,
            context={"mode": Mode.EXPLORER, "user_id": mock_user.id, "session_id": mock_session.id}
        )
        
        assert detection_result["suggested_mode"] == Mode.GUIDED
        
        # 3. Ejecutar transición
        transition_evaluation = await mode_transition.evaluate_transition(
            user=mock_user,
            current_mode=Mode.EXPLORER,
            suggested_mode=Mode.GUIDED,
            context={"mode": Mode.EXPLORER, "user_id": mock_user.id, "session_id": mock_session.id},
            detection_result=detection_result
        )
        
        transition_result = await orchestrator.execute_transition(
            user=mock_user,
            from_mode=Mode.EXPLORER,
            to_mode=Mode.GUIDED,
            context={"mode": Mode.EXPLORER, "user_id": mock_user.id, "session_id": mock_session.id},
            evaluation=transition_evaluation
        )
        
        assert transition_result["transition_successful"] is True
        current_mode = Mode.GUIDED
        
        # 4. Simular sesión guiada
        guided_flow = [
            {
                "query": "¿Cuál es el primer paso?",
                "expected_response_type": "step_instruction",
                "step_number": 1
            },
            {
                "query": "He completado el primer paso, ¿qué sigue?",
                "expected_response_type": "next_step",
                "step_number": 2
            },
            {
                "query": "¿Puedes explicar más sobre este paso?",
                "expected_response_type": "detailed_explanation",
                "step_number": 2
            },
            {
                "query": "¿Cuántos pasos quedan?",
                "expected_response_type": "progress_update",
                "step_number": 2
            }
        ]
        
        session_context = {
            "mode": current_mode,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "guided_progress": {"current_step": 1, "total_steps": 5},
            "step_history": []
        }
        
        # 5. Ejecutar flujo guiado
        for i, step in enumerate(guided_flow):
            print(f"\n🎯 Paso {i+1}: {step['query']}")
            
            # Verificar que se mantiene en modo Guided
            detection_result = await mode_detection.detect_mode(
                user=mock_user,
                query=step["query"],
                context=session_context
            )
            
            assert detection_result["suggested_mode"] == Mode.GUIDED
            assert detection_result["confidence"] >= 0.8
            
            # Construir prompt guiado
            system_prompt = await prompt_builder.build_system_prompt(
                user=mock_user,
                mode=current_mode,
                resource_context={},
                context=session_context
            )
            
            assert system_prompt is not None
            assert "GUIDED" in system_prompt.upper()
            assert "STEP" in system_prompt.upper()
            
            # Procesar query con IA
            ai_response = await ai_orchestrator.process_query(
                user=mock_user,
                query=step["query"],
                mode=current_mode,
                context=session_context
            )
            
            assert ai_response is not None
            assert "response" in ai_response
            assert "mode" in ai_response
            assert ai_response["mode"] == Mode.GUIDED
            
            # Actualizar progreso
            session_context["guided_progress"]["current_step"] = step["step_number"]
            session_context["step_history"].append({
                "query": step["query"],
                "response": ai_response["response"],
                "step_number": step["step_number"],
                "timestamp": datetime.now()
            })
            
            print(f"✅ Paso {step['step_number']} completado")
        
        # 6. Verificar progreso del flujo guiado
        assert current_mode == Mode.GUIDED
        assert len(session_context["step_history"]) == 4
        assert session_context["guided_progress"]["current_step"] == 2
        
        print(f"\n🎯 Flujo guiado completado exitosamente")
        print(f"   - Modo mantenido: {current_mode}")
        print(f"   - Pasos ejecutados: {len(session_context['step_history'])}")
        print(f"   - Progreso: {session_context['guided_progress']['current_step']}/{session_context['guided_progress']['total_steps']}")

    # =============================================================================
    # 🔄 TESTS DE FLUJO CON TRANSICIONES MÚLTIPLES
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_flow_with_transitions(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo con múltiples transiciones de modo"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        prompt_builder = PromptBuilderService()
        ai_orchestrator = SmartAIOrchestrator()
        
        # 2. Flujo con transiciones
        flow_with_transitions = [
            {
                "query": "¿Qué hay en mi base de datos?",
                "expected_mode": Mode.EXPLORER,
                "action": "explore"
            },
            {
                "query": "¿Puedes guiarme paso a paso?",
                "expected_mode": Mode.GUIDED,
                "action": "transition_to_guided"
            },
            {
                "query": "¿Cuál es el primer paso?",
                "expected_mode": Mode.GUIDED,
                "action": "guided_step"
            },
            {
                "query": "Muéstrame todos los recursos para explorar libremente",
                "expected_mode": Mode.EXPLORER,
                "action": "transition_to_explorer"
            },
            {
                "query": "Explora las aplicaciones",
                "expected_mode": Mode.EXPLORER,
                "action": "explore"
            }
        ]
        
        current_mode = Mode.EXPLORER
        session_context = {
            "mode": current_mode,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "transition_history": [],
            "mode_history": [Mode.EXPLORER]
        }
        
        # 3. Ejecutar flujo con transiciones
        for i, step in enumerate(flow_with_transitions):
            print(f"\n🔄 Paso {i+1}: {step['query']}")
            print(f"   Modo actual: {current_mode}")
            
            # Detectar modo sugerido
            detection_result = await mode_detection.detect_mode(
                user=mock_user,
                query=step["query"],
                context=session_context
            )
            
            suggested_mode = detection_result["suggested_mode"]
            print(f"   Modo sugerido: {suggested_mode}")
            
            # Verificar si se necesita transición
            if suggested_mode != current_mode:
                print(f"   🔄 Transición requerida: {current_mode} → {suggested_mode}")
                
                # Evaluar transición
                transition_evaluation = await mode_transition.evaluate_transition(
                    user=mock_user,
                    current_mode=current_mode,
                    suggested_mode=suggested_mode,
                    context=session_context,
                    detection_result=detection_result
                )
                
                if transition_evaluation["transition_recommended"]:
                    # Ejecutar transición
                    transition_result = await orchestrator.execute_transition(
                        user=mock_user,
                        from_mode=current_mode,
                        to_mode=suggested_mode,
                        context=session_context,
                        evaluation=transition_evaluation
                    )
                    
                    assert transition_result["transition_successful"] is True
                    current_mode = suggested_mode
                    
                    # Registrar transición
                    session_context["transition_history"].append({
                        "from_mode": step["expected_mode"],
                        "to_mode": current_mode,
                        "timestamp": datetime.now(),
                        "reason": detection_result["reasoning"]
                    })
                    
                    session_context["mode_history"].append(current_mode)
                    
                    print(f"   ✅ Transición completada: {current_mode}")
            
            # Construir prompt para el modo actual
            system_prompt = await prompt_builder.build_system_prompt(
                user=mock_user,
                mode=current_mode,
                resource_context={},
                context=session_context
            )
            
            assert system_prompt is not None
            
            # Procesar query
            ai_response = await ai_orchestrator.process_query(
                user=mock_user,
                query=step["query"],
                mode=current_mode,
                context=session_context
            )
            
            assert ai_response is not None
            assert "response" in ai_response
            assert ai_response["mode"] == current_mode
            
            print(f"   ✅ Query procesada en modo {current_mode}")
        
        # 4. Verificar historial de transiciones
        assert len(session_context["transition_history"]) >= 2  # Al menos 2 transiciones
        assert len(session_context["mode_history"]) >= 3       # Al menos 3 cambios de modo
        
        print(f"\n🔄 Flujo con transiciones completado exitosamente")
        print(f"   - Transiciones ejecutadas: {len(session_context['transition_history'])}")
        print(f"   - Modos utilizados: {set(session_context['mode_history'])}")

    # =============================================================================
    # 🚨 TESTS DE FLUJO CON FALLBACKS
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_flow_with_fallbacks(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo con activación de fallbacks"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        fallback_service = SmartFallbackService()
        prompt_builder = PromptBuilderService()
        ai_orchestrator = SmartAIOrchestrator()
        
        # 2. Flujo con fallbacks
        flow_with_fallbacks = [
            {
                "query": "¿Qué hay en mi base de datos?",
                "expected_mode": Mode.EXPLORER,
                "fallback_expected": False
            },
            {
                "query": "¿Qué?",
                "expected_mode": Mode.EXPLORER,
                "fallback_expected": True,
                "fallback_type": FallbackType.AMBIGUOUS_QUERY
            },
            {
                "query": "¿Puedes guiarme paso a paso?",
                "expected_mode": Mode.GUIDED,
                "fallback_expected": False
            },
            {
                "query": "Hmm...",
                "expected_mode": Mode.GUIDED,
                "fallback_expected": True,
                "fallback_type": FallbackType.AMBIGUOUS_QUERY
            },
            {
                "query": "¿Cuál es el siguiente paso?",
                "expected_mode": Mode.GUIDED,
                "fallback_expected": False
            }
        ]
        
        current_mode = Mode.EXPLORER
        session_context = {
            "mode": current_mode,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "fallback_count": 0,
            "fallback_history": []
        }
        
        # 3. Ejecutar flujo con fallbacks
        for i, step in enumerate(flow_with_fallbacks):
            print(f"\n🚨 Paso {i+1}: {step['query']}")
            print(f"   Modo actual: {current_mode}")
            
            # Detectar fallback si es esperado
            if step["fallback_expected"]:
                print(f"   🚨 Fallback esperado: {step['fallback_type']}")
                
                fallback_detection = await fallback_service.detect_fallback(
                    user=mock_user,
                    query=step["query"],
                    context=session_context
                )
                
                assert fallback_detection["fallback_detected"] is True
                assert fallback_detection["fallback_type"] == step["fallback_type"]
                
                # Generar respuesta de fallback
                fallback_response = await fallback_service.generate_fallback_response(
                    user=mock_user,
                    fallback_info=fallback_detection,
                    context=session_context
                )
                
                assert fallback_response is not None
                assert "response" in fallback_response
                assert "options" in fallback_response
                
                # Registrar fallback
                session_context["fallback_count"] += 1
                session_context["fallback_history"].append({
                    "query": step["query"],
                    "fallback_type": step["fallback_type"],
                    "response": fallback_response["response"],
                    "timestamp": datetime.now()
                })
                
                print(f"   ✅ Fallback manejado: {fallback_response['response'][:50]}...")
                
            else:
                # Procesar query normalmente
                detection_result = await mode_detection.detect_mode(
                    user=mock_user,
                    query=step["query"],
                    context=session_context
                )
                
                # Actualizar modo si es necesario
                if detection_result["suggested_mode"] != current_mode:
                    current_mode = detection_result["suggested_mode"]
                    session_context["mode"] = current_mode
                    print(f"   🔄 Modo cambiado a: {current_mode}")
                
                # Construir prompt
                system_prompt = await prompt_builder.build_system_prompt(
                    user=mock_user,
                    mode=current_mode,
                    resource_context={},
                    context=session_context
                )
                
                # Procesar con IA
                ai_response = await ai_orchestrator.process_query(
                    user=mock_user,
                    query=step["query"],
                    mode=current_mode,
                    context=session_context
                )
                
                assert ai_response is not None
                print(f"   ✅ Query procesada normalmente en modo {current_mode}")
        
        # 4. Verificar manejo de fallbacks
        assert session_context["fallback_count"] == 2
        assert len(session_context["fallback_history"]) == 2
        
        print(f"\n🚨 Flujo con fallbacks completado exitosamente")
        print(f"   - Fallbacks manejados: {session_context['fallback_count']}")
        print(f"   - Modo final: {current_mode}")

    # =============================================================================
    # 📊 TESTS DE FLUJO CON MÉTRICAS COMPLETAS
    # =============================================================================

    @pytest.mark.asyncio
    @pytest.mark.e2e
    async def test_complete_flow_with_metrics(self, mock_user, mock_session, mock_database_service, mock_redis_service):
        """Test del flujo completo con recolección de métricas"""
        
        # 1. Configurar servicios
        mode_detection = ModeDetectionService()
        mode_transition = ModeTransitionService()
        orchestrator = ModeTransitionOrchestrator()
        fallback_service = SmartFallbackService()
        prompt_builder = PromptBuilderService()
        ai_orchestrator = SmartAIOrchestrator()
        
        # 2. Flujo completo con métricas
        complete_flow = [
            "¿Qué hay en mi base de datos?",
            "¿Puedes guiarme paso a paso?",
            "¿Cuál es el primer paso?",
            "Muéstrame todos los recursos",
            "Explora las aplicaciones",
            "¿Cuál es el rendimiento?",
            "Guíame en la optimización",
            "¿Qué estrategias tengo?"
        ]
        
        current_mode = Mode.EXPLORER
        session_context = {
            "mode": current_mode,
            "user_id": mock_user.id,
            "session_id": mock_session.id,
            "metrics": {
                "total_queries": 0,
                "mode_changes": 0,
                "fallbacks": 0,
                "response_times": [],
                "user_satisfaction": []
            }
        }
        
        # 3. Ejecutar flujo completo
        start_time = datetime.now()
        
        for i, query in enumerate(complete_flow):
            print(f"\n📊 Paso {i+1}: {query}")
            
            # Medir tiempo de respuesta
            query_start = datetime.now()
            
            # Detectar modo
            detection_result = await mode_detection.detect_mode(
                user=mock_user,
                query=query,
                context=session_context
            )
            
            # Manejar transiciones de modo
            if detection_result["suggested_mode"] != current_mode:
                transition_evaluation = await mode_transition.evaluate_transition(
                    user=mock_user,
                    current_mode=current_mode,
                    suggested_mode=detection_result["suggested_mode"],
                    context=session_context,
                    detection_result=detection_result
                )
                
                if transition_evaluation["transition_recommended"]:
                    transition_result = await orchestrator.execute_transition(
                        user=mock_user,
                        from_mode=current_mode,
                        to_mode=detection_result["suggested_mode"],
                        context=session_context,
                        evaluation=transition_evaluation
                    )
                    
                    if transition_result["transition_successful"]:
                        current_mode = detection_result["suggested_mode"]
                        session_context["mode"] = current_mode
                        session_context["metrics"]["mode_changes"] += 1
            
            # Construir prompt
            system_prompt = await prompt_builder.build_system_prompt(
                user=mock_user,
                mode=current_mode,
                resource_context={},
                context=session_context
            )
            
            # Procesar query
            ai_response = await ai_orchestrator.process_query(
                user=mock_user,
                query=query,
                mode=current_mode,
                context=session_context
            )
            
            # Calcular tiempo de respuesta
            query_end = datetime.now()
            response_time = (query_end - query_start).total_seconds() * 1000
            
            # Actualizar métricas
            session_context["metrics"]["total_queries"] += 1
            session_context["metrics"]["response_times"].append(response_time)
            session_context["metrics"]["user_satisfaction"].append(0.8)  # Simulado
            
            print(f"   ✅ Procesado en {response_time:.2f}ms (modo: {current_mode})")
        
        total_time = (datetime.now() - start_time).total_seconds()
        
        # 4. Verificar métricas completas
        metrics = session_context["metrics"]
        
        assert metrics["total_queries"] == 8
        assert metrics["mode_changes"] >= 1  # Al menos una transición
        assert len(metrics["response_times"]) == 8
        assert len(metrics["user_satisfaction"]) == 8
        
        # Calcular estadísticas
        avg_response_time = sum(metrics["response_times"]) / len(metrics["response_times"])
        max_response_time = max(metrics["response_times"])
        min_response_time = min(metrics["response_times"])
        
        # Verificar performance
        assert avg_response_time < 200, f"Tiempo promedio de respuesta: {avg_response_time:.2f}ms, debe ser < 200ms"
        assert max_response_time < 500, f"Tiempo máximo de respuesta: {max_response_time:.2f}ms, debe ser < 500ms"
        assert total_time < 10, f"Tiempo total del flujo: {total_time:.2f}s, debe ser < 10s"
        
        print(f"\n📊 Flujo completo con métricas finalizado")
        print(f"   - Queries totales: {metrics['total_queries']}")
        print(f"   - Cambios de modo: {metrics['mode_changes']}")
        print(f"   - Tiempo promedio de respuesta: {avg_response_time:.2f}ms")
        print(f"   - Tiempo total del flujo: {total_time:.2f}s")
        print(f"   - Modo final: {current_mode}")
