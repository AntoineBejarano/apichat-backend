"""
🔧 FASE 1: Test de validación de SQL generado por LLM
────────────────────────────────────────────────────────
Verifica que la función is_valid_sql funciona correctamente y que
el sistema no ejecuta respuestas del LLM que no sean SQL válido.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from app.services.ai.langchain_service import LangchainService


class TestPhase1SQLValidation:
    """Test de la FASE 1: Validación de SQL generado por LLM"""
    
    @pytest.fixture
    def mock_factory(self):
        """Factory mock para LangchainService"""
        factory = Mock()
        factory.get_function_service = Mock(return_value=Mock())
        factory.get_apps_service = Mock(return_value=Mock())
        factory.get_database_service = Mock(return_value=Mock())
        return factory
    
    @pytest.fixture
    def langchain_service(self, mock_factory):
        """Instancia de LangchainService para testing"""
        return LangchainService(mock_factory)
    
    def test_is_valid_sql_with_valid_select(self, langchain_service):
        """🔧 FASE 1: Test que valida SQL SELECT válido"""
        valid_sqls = [
            "SELECT * FROM users",
            "SELECT id, name FROM customers WHERE active = true",
            "SELECT COUNT(*) FROM orders",
            "SELECT u.name, o.total FROM users u JOIN orders o ON u.id = o.user_id"
        ]
        
        for sql in valid_sqls:
            assert langchain_service.is_valid_sql(sql), f"SQL válido rechazado: {sql}"
            print(f"✅ SQL válido aceptado: {sql}")
    
    def test_is_valid_sql_with_invalid_sql(self, langchain_service):
        """🔧 FASE 1: Test que rechaza SQL inválido"""
        invalid_sqls = [
            "INSERT INTO users VALUES (1, 'test')",  # No es SELECT
            "UPDATE users SET name = 'test'",        # No es SELECT
            "DELETE FROM users",                     # No es SELECT
            "CREATE TABLE test",                     # No es SELECT
            "DROP TABLE users",                      # No es SELECT
            "ALTER TABLE users ADD COLUMN test",     # No es SELECT
            "SHOW TABLES",                          # No comienza con SELECT
            "DESCRIBE users"                        # No comienza con SELECT
        ]
        
        for sql in invalid_sqls:
            assert not langchain_service.is_valid_sql(sql), f"SQL inválido aceptado: {sql}"
            print(f"✅ SQL inválido rechazado: {sql}")
    
    def test_is_valid_sql_with_explanatory_text(self, langchain_service):
        """🔧 FASE 1: Test que rechaza texto explicativo del LLM"""
        explanatory_texts = [
            "Lo siento, no puedo generar SQL para esa pregunta",
            "Necesitaría más información sobre la base de datos",
            "No tengo acceso al esquema de la base de datos",
            "No hay tablas disponibles en este contexto",
            "No existe la tabla que mencionas",
            "No se puede ejecutar esa consulta",
            "Imposible generar SQL con la información disponible",
            "Error: no se pudo procesar la solicitud"
        ]
        
        for text in explanatory_texts:
            assert not langchain_service.is_valid_sql(text), f"Texto explicativo aceptado como SQL: {text}"
            print(f"✅ Texto explicativo rechazado: {text}")
    
    def test_is_valid_sql_with_edge_cases(self, langchain_service):
        """🔧 FASE 1: Test con casos edge"""
        edge_cases = [
            "",                                      # String vacío
            None,                                    # None
            "   ",                                   # Solo espacios
            "SELECT",                                # Solo SELECT sin FROM
            "FROM users",                            # Solo FROM sin SELECT
            "select * from users",                   # Minúsculas (debe funcionar)
            "SELECT * FROM users;",                  # Con punto y coma
            "  SELECT * FROM users  "               # Con espacios extra
        ]
        
        expected_results = [
            False,  # String vacío
            False,  # None
            False,  # Solo espacios
            False,  # Solo SELECT sin FROM
            False,  # Solo FROM sin SELECT
            True,   # Minúsculas (debe funcionar)
            True,   # Con punto y coma
            True    # Con espacios extra
        ]
        
        for sql, expected in zip(edge_cases, expected_results):
            result = langchain_service.is_valid_sql(sql)
            assert result == expected, f"SQL: '{sql}' - Esperado: {expected}, Obtenido: {result}"
            print(f"✅ Caso edge: '{sql}' -> {result}")
    
    @pytest.mark.asyncio
    async def test_generate_sql_from_question_rejects_invalid_llm_response(self, langchain_service):
        """🔧 FASE 1: Test que verifica que generate_sql_from_question rechaza respuestas inválidas del LLM"""
        # Mock del LLM que devuelve texto explicativo
        langchain_service.llm = AsyncMock()
        langchain_service.llm.ainvoke.return_value = Mock(
            content="Lo siento, no puedo generar SQL para esa pregunta porque no tengo acceso al esquema de la base de datos."
        )
        
        # Llamar a la función
        result = await langchain_service.generate_sql_from_question(
            question="¿Cuántos usuarios tengo?",
            db_id=uuid4()
        )
        
        # Verificar que se rechazó la respuesta inválida
        assert result["status"] == "llm_response"
        assert result["error"] == "Respuesta del modelo no es una consulta SQL ejecutable."
        assert result["sql"] == ""
        assert "Lo siento, no puedo generar SQL" in result["content"]
        
        print("✅ generate_sql_from_question rechaza correctamente respuestas inválidas del LLM")
    
    @pytest.mark.asyncio
    async def test_generate_sql_from_question_accepts_valid_llm_response(self, langchain_service):
        """🔧 FASE 1: Test que verifica que generate_sql_from_question acepta respuestas válidas del LLM"""
        # Mock del LLM que devuelve SQL válido
        langchain_service.llm = AsyncMock()
        langchain_service.llm.ainvoke.return_value = Mock(
            content="SELECT COUNT(*) FROM users"
        )
        
        # Llamar a la función
        result = await langchain_service.generate_sql_from_question(
            question="¿Cuántos usuarios tengo?",
            db_id=uuid4()
        )
        
        # Verificar que se aceptó la respuesta válida
        assert result["sql"] == "SELECT COUNT(*) FROM users LIMIT 100;"
        assert result["security_validated"] is True
        assert "error" not in result
        
        print("✅ generate_sql_from_question acepta correctamente respuestas válidas del LLM")
    
    def test_is_valid_sql_performance(self, langchain_service):
        """🔧 FASE 1: Test de rendimiento de is_valid_sql"""
        import time
        
        # SQL de prueba
        test_sql = "SELECT id, name, email FROM users WHERE active = true AND created_at > '2023-01-01'"
        
        # Medir tiempo de ejecución
        start_time = time.time()
        for _ in range(1000):
            langchain_service.is_valid_sql(test_sql)
        end_time = time.time()
        
        execution_time = end_time - start_time
        print(f"✅ 1000 validaciones ejecutadas en {execution_time:.4f} segundos")
        
        # Verificar que es razonablemente rápido (< 1 segundo para 1000 validaciones)
        assert execution_time < 1.0, f"Validación demasiado lenta: {execution_time:.4f}s"


if __name__ == "__main__":
    # Ejecutar tests manualmente si es necesario
    pytest.main([__file__, "-v"])
