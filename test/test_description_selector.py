# test/test_description_selector.py
"""
Tests para DescriptionSelectorService
───────────────────────────────────
Tests para verificar el ranking por description/name, umbral y top_k.
"""
import pytest
from unittest.mock import Mock, patch
from uuid import uuid4

from app.services.description_selector_service import DescriptionSelectorService


class TestDescriptionSelectorService:
    """Tests para el servicio de selección por descripción"""
    
    def setup_method(self):
        """Setup para cada test"""
        # Mock del factory y servicios
        self.mock_factory = Mock()
        self.mock_user = Mock()
        self.mock_user.id = uuid4()
        self.mock_factory.user = self.mock_user
        
        # Mock database service
        self.mock_db_service = Mock()
        self.mock_factory.get_database_service.return_value = self.mock_db_service
        
        # Mock app service  
        self.mock_app_service = Mock()
        self.mock_factory.get_app_service.return_value = self.mock_app_service
        
        # Mock db session
        self.mock_db = Mock()
        self.mock_factory.db = self.mock_db
        
        # Crear servicio
        self.service = DescriptionSelectorService(self.mock_factory)
    
    def test_fetch_descriptions_success(self):
        """Test fetch_descriptions devuelve DBs y Apps correctamente"""
        # Mock DB connections
        mock_db1 = Mock()
        mock_db1.id = uuid4()
        mock_db1.name = "Users DB"
        mock_db1.description = "Database with user information"
        
        mock_db2 = Mock()
        mock_db2.id = uuid4()
        mock_db2.name = "Products DB"
        mock_db2.description = "E-commerce product catalog"
        
        self.mock_db_service.get_connections.return_value = [mock_db1, mock_db2]
        
        # Mock Apps
        mock_app1 = Mock()
        mock_app1.id = "app1"
        mock_app1.name = "Email Service"
        mock_app1.description = "Send emails to users"
        
        mock_app2 = Mock()
        mock_app2.id = "app2"
        mock_app2.name = "Payment Gateway"
        mock_app2.description = "Process payments and transactions"
        
        self.mock_app_service.get_user_apps.return_value = [mock_app1, mock_app2]
        
        # Execute
        result = self.service.fetch_descriptions()
        
        # Assert
        assert "dbs" in result
        assert "apps" in result
        assert len(result["dbs"]) == 2
        assert len(result["apps"]) == 2
        
        # Verify DB structure
        db1_data = result["dbs"][0]
        assert db1_data["id"] == str(mock_db1.id)
        assert db1_data["name"] == "Users DB"
        assert db1_data["description"] == "Database with user information"
        
        # Verify App structure
        app1_data = result["apps"][0]
        assert app1_data["id"] == "app1"
        assert app1_data["name"] == "Email Service"
        assert app1_data["description"] == "Send emails to users"
    
    def test_fetch_descriptions_empty(self):
        """Test fetch_descriptions con listas vacías"""
        self.mock_db_service.get_connections.return_value = []
        self.mock_app_service.get_user_apps.return_value = []
        
        result = self.service.fetch_descriptions()
        
        assert result == {"dbs": [], "apps": []}
    
    def test_fetch_descriptions_exception(self):
        """Test fetch_descriptions maneja excepciones"""
        self.mock_db_service.get_connections.side_effect = Exception("DB Error")
        
        result = self.service.fetch_descriptions()
        
        assert result == {"dbs": [], "apps": []}
    
    @patch.object(DescriptionSelectorService, 'fetch_descriptions')
    def test_select_high_similarity(self, mock_fetch):
        """Test select con alta similitud"""
        # Mock data
        mock_fetch.return_value = {
            "dbs": [
                {"id": "db1", "name": "Users Database", "description": "Store user information and profiles"},
                {"id": "db2", "name": "Products DB", "description": "E-commerce product catalog"}
            ],
            "apps": [
                {"id": "app1", "name": "Email Service", "description": "Send notifications to users"},
                {"id": "app2", "name": "Analytics", "description": "Track user behavior"}
            ]
        }
        
        # Test con query relacionada a users
        result = self.service.select("show me user profiles", top_k=2, threshold=0.3)
        
        # Should find users-related resources
        assert "db_candidates" in result
        assert "app_candidates" in result
        
        # DB1 (Users Database) should have higher score than DB2 (Products)
        db_candidates = result["db_candidates"]
        if len(db_candidates) >= 2:
            db1_score = next((score for id, score in db_candidates if id == "db1"), 0)
            db2_score = next((score for id, score in db_candidates if id == "db2"), 0)
            assert db1_score > db2_score
    
    @patch.object(DescriptionSelectorService, 'fetch_descriptions')
    def test_select_threshold_filtering(self, mock_fetch):
        """Test select respeta el threshold"""
        mock_fetch.return_value = {
            "dbs": [
                {"id": "db1", "name": "Completely Unrelated", "description": "Nothing to do with the query"}
            ],
            "apps": []
        }
        
        # Query muy diferente con threshold alto
        result = self.service.select("user profiles and authentication", top_k=2, threshold=0.8)
        
        # No debería encontrar candidatos por el threshold alto
        assert result["db_candidates"] == []
        assert result["app_candidates"] == []
    
    @patch.object(DescriptionSelectorService, 'fetch_descriptions')
    def test_select_top_k_limiting(self, mock_fetch):
        """Test select respeta el límite top_k"""
        mock_fetch.return_value = {
            "dbs": [
                {"id": "db1", "name": "Users", "description": "user data"},
                {"id": "db2", "name": "User Profiles", "description": "user profiles"},
                {"id": "db3", "name": "User Settings", "description": "user preferences"},
                {"id": "db4", "name": "User Analytics", "description": "user behavior"}
            ],
            "apps": []
        }
        
        # Todas deberían matchear "user" pero limitar a top_k=2
        result = self.service.select("user information", top_k=2, threshold=0.1)
        
        # Solo debería devolver máximo 2
        assert len(result["db_candidates"]) <= 2
        
        # Deberían estar ordenados por score descendente
        if len(result["db_candidates"]) == 2:
            score1 = result["db_candidates"][0][1]
            score2 = result["db_candidates"][1][1]
            assert score1 >= score2
    
    def test_calculate_similarity_exact_match(self):
        """Test _calculate_similarity con match exacto"""
        similarity = self.service._calculate_similarity(
            "user database", 
            "User Database", 
            "Store user information"
        )
        
        # Debería ser alta similitud (ajustado para difflib)
        assert similarity > 0.6
    
    def test_calculate_similarity_no_match(self):
        """Test _calculate_similarity sin match"""
        similarity = self.service._calculate_similarity(
            "completely different text", 
            "Products", 
            "E-commerce catalog"
        )
        
        # Debería ser baja similitud
        assert similarity < 0.3
    
    def test_calculate_similarity_word_bonus(self):
        """Test _calculate_similarity aplica bonus por palabras exactas"""
        # Con palabra exacta
        similarity_with_word = self.service._calculate_similarity(
            "user profiles", 
            "User Management", 
            "Handle user accounts"
        )
        
        # Sin palabra exacta
        similarity_without_word = self.service._calculate_similarity(
            "customer profiles", 
            "User Management", 
            "Handle user accounts"
        )
        
        # Con palabra exacta debería tener mayor score
        assert similarity_with_word > similarity_without_word
    
    def test_select_empty_user_text(self):
        """Test select con texto vacío"""
        result = self.service.select("", top_k=2, threshold=0.5)
        
        assert result["db_candidates"] == []
        assert result["app_candidates"] == []
        
        result = self.service.select("   ", top_k=2, threshold=0.5)
        
        assert result["db_candidates"] == []
        assert result["app_candidates"] == []
