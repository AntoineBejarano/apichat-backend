"""
🔧 FASE 2: Test de prevención de ejecución de respuestas explicativas
────────────────────────────────────────────────────────────────────
Verifica que el sistema no ejecute SQL cuando el contenido parece ser
una respuesta explicativa del LLM y no SQL ejecutable.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from app.services.execution.execution_engine_service import ExecutionEngineService


class TestPhase2ExplanatoryResponsePrevention:
    """Test de la FASE 2: Prevención de ejecución de respuestas explicativas"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock para ExecutionEngineService"""
        factory = Mock()
        factory.user = Mock()
        factory.user.id = uuid4()
        factory.get_chat_history_service = Mock(return_value=Mock())
        factory.get_database_service = Mock(return_value=Mock())
        factory.get_proxy_service = Mock(return_value=Mock())
        return factory
    
    @pytest.fixture
    def execution_engine(self, mock_factory):
        """Instancia de ExecutionEngineService para testing"""
        return ExecutionEngineService(mock_factory)
    
    def test_is_explanatory_response_with_valid_sql(self, execution_engine):
        """🔧 FASE 2: Test que acepta SQL válido"""
        valid_sqls = [
            "SELECT * FROM users",
            "SELECT id, name FROM customers WHERE active = true",
            "SELECT COUNT(*) FROM orders",
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        ]
        
        for sql in valid_sqls:
            assert not execution_engine._is_explanatory_response(sql), f"SQL válido rechazado: {sql}"
            print(f"✅ SQL válido aceptado: {sql}")
    
    def test_is_explanatory_response_with_explanatory_text(self, execution_engine):
        """🔧 FASE 2: Test que detecta texto explicativo del LLM"""
        explanatory_texts = [
            "Lo siento, no puedo generar SQL para esa pregunta",
            "Necesitaría más información sobre la base de datos",
            "No tengo acceso al esquema de la base de datos",
            "No hay tablas disponibles en este contexto",
            "No existe la tabla que mencionas",
            "No se puede ejecutar esa consulta",
            "Imposible generar SQL con la información disponible",
            "Error: no se pudo procesar la solicitud",
            "No tengo acceso a esa información",
            "No puedo acceder a la base de datos",
            "No se encuentra la tabla especificada",
            "No está disponible el esquema",
            "No puedo procesar esa solicitud",
            "No puedo generar la consulta SQL"
        ]
        
        for text in explanatory_texts:
            assert execution_engine._is_explanatory_response(text), f"Texto explicativo no detectado: {text}"
            print(f"✅ Texto explicativo detectado: {text}")
    
    def test_is_explanatory_response_with_invalid_sql(self, execution_engine):
        """🔧 FASE 2: Test que detecta SQL inválido"""
        invalid_sqls = [
            "INSERT INTO users VALUES (1, 'test')",  # No es SELECT
            "UPDATE users SET name = 'test'",        # No es SELECT
            "DELETE FROM users",                     # No es SELECT
            "CREATE TABLE test",                     # No es SELECT
            "DROP TABLE users",                      # No es SELECT
            "ALTER TABLE users ADD COLUMN test",     # No es SELECT
            "SHOW TABLES",                          # No comienza con SELECT
            "DESCRIBE users",                       # No comienza con SELECT
            "SELECT",                               # Solo SELECT sin FROM
            "FROM users"                            # Solo FROM sin SELECT
        ]
        
        for sql in invalid_sqls:
            assert execution_engine._is_explanatory_response(sql), f"SQL inválido no detectado: {sql}"
            print(f"✅ SQL inválido detectado: {sql}")
    
    def test_is_explanatory_response_with_edge_cases(self, execution_engine):
        """🔧 FASE 2: Test con casos edge"""
        edge_cases = [
            "",                                      # String vacío
            None,                                    # None
            "   ",                                   # Solo espacios
            "select * from users",                   # Minúsculas (debe funcionar)
            "  SELECT * FROM users  "               # Con espacios extra
        ]
        
        expected_results = [
            True,   # String vacío
            True,   # None
            True,   # Solo espacios
            False,  # Minúsculas (debe funcionar)
            False   # Con espacios extra
        ]
        
        for sql, expected in zip(edge_cases, expected_results):
            result = execution_engine._is_explanatory_response(sql)
            assert result == expected, f"SQL: '{sql}' - Esperado: {expected}, Obtenido: {result}"
            print(f"✅ Caso edge: '{sql}' -> {result}")
    
    @pytest.mark.asyncio
    async def test_run_db_query_blocks_explanatory_response(self, execution_engine):
        """🔧 FASE 2: Test que verifica que _run_db_query bloquea respuestas explicativas"""
        # Mock del database service
        db_service = Mock()
        db_service.get_dialect_name.return_value = "postgresql"
        db_service.get_sql_instance.return_value = Mock()
        execution_engine.factory.get_database_service.return_value = db_service
        
        # Mock del proxy service
        proxy_service = Mock()
        proxy_service.get_sql_config.return_value = None
        execution_engine.factory.get_proxy_service.return_value = proxy_service
        
        # Acción con SQL explicativo
        action = {
            "type": "db_query",
            "sql": "Lo siento, no puedo generar SQL para esa pregunta porque no tengo acceso al esquema de la base de datos.",
            "database_id": str(uuid4())
        }
        
        ctx = {"db_ids": [str(uuid4())]}
        
        # Llamar a la función
        result = await execution_engine._run_db_query(action, ctx)
        
        # Verificar que se bloqueó la ejecución
        assert result["status"] == "llm_response"
        assert result["error"] == "La IA no generó SQL ejecutable. Revisa si la base de datos fue conectada correctamente."
        assert result["blocked_execution"] is True
        assert "Lo siento, no puedo generar SQL" in result["content"]
        
        print("✅ _run_db_query bloquea correctamente respuestas explicativas del LLM")
    
    @pytest.mark.asyncio
    async def test_run_db_query_allows_valid_sql(self, execution_engine):
        """🔧 FASE 2: Test que verifica que _run_db_query permite SQL válido"""
        # Mock del database service
        db_service = Mock()
        db_service.get_dialect_name.return_value = "postgresql"
        db_service.get_sql_instance.return_value = Mock()
        db_service.execute_sql.return_value = [{"id": 1, "name": "test"}]
        execution_engine.factory.get_database_service.return_value = db_service
        
        # Mock del proxy service
        proxy_service = Mock()
        proxy_service.get_sql_config.return_value = None
        execution_engine.factory.get_proxy_service.return_value = proxy_service
        
        # Acción con SQL válido
        action = {
            "type": "db_query",
            "sql": "SELECT id, name FROM users LIMIT 10",
            "database_id": str(uuid4())
        }
        
        ctx = {"db_ids": [str(uuid4())]}
        
        # Llamar a la función
        result = await execution_engine._run_db_query(action, ctx)
        
        # Verificar que se permitió la ejecución
        assert "error" not in result
        # El resultado puede tener 'data' o 'rows' dependiendo del formato
        assert result.get("data") is not None or result.get("rows") is not None
        
        print("✅ _run_db_query permite correctamente SQL válido")
    
    def test_is_explanatory_response_performance(self, execution_engine):
        """🔧 FASE 2: Test de rendimiento de _is_explanatory_response"""
        import time
        
        # SQL de prueba
        test_sql = "Lo siento, no puedo generar SQL para esa pregunta porque no tengo acceso al esquema de la base de datos."
        
        # Medir tiempo de ejecución
        start_time = time.time()
        for _ in range(1000):
            execution_engine._is_explanatory_response(test_sql)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"✅ 1000 validaciones ejecutadas en {execution_time:.4f} segundos")
        
        # Verificar que es razonablemente rápido (< 1 segundo para 1000 validaciones)
        assert execution_time < 1.0, f"Validación demasiado lenta: {execution_time:.4f}s"


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
