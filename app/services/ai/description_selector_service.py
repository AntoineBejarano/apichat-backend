# app/services/description_selector_service.py
"""
DescriptionSelectorService
─────────────────────────
Selecciona automáticamente DBs y Apps basándose en similitud de texto
entre el mensaje del usuario y las descripciones/nombres de los recursos.

Usa difflib para similarity matching sin dependencias externas.
"""
from __future__ import annotations

import logging
import difflib
from typing import Dict, List, Tuple, Any, Optional, TYPE_CHECKING
from uuid import UUID

from app.services.base_service import BaseService

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class DescriptionSelectorService(BaseService):
    """
    Servicio para selección automática de recursos basada en similitud de texto.
    
    Funcionalidades:
    - Obtiene descripciones de DBs y Apps del usuario
    - Calcula similitud usando difflib.SequenceMatcher
    - Selecciona candidatos con threshold y top_k
    """
    
    def __init__(self, factory: "ServiceFactory") -> None:
        super().__init__(factory)
        logger.info(f"[DescriptionSelectorService] ✅ Inicializado para user_id={self.user.id}")
    
    def fetch_descriptions(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Obtiene descripciones de todas las DBs y Apps del usuario.
        
        Returns:
            Dict con 'dbs' y 'apps', cada uno con lista de {id, name, description}
        """
        try:
            # Obtener DBs del usuario
            database_service = self.factory.get_database_service()
            db_connections = database_service.get_connections()
            
            dbs = []
            for db_conn in db_connections:
                dbs.append({
                    "id": str(db_conn.id),  # Convertir UUID a string para JSON serialization
                    "name": db_conn.name or f"DB_{db_conn.id}",
                    "description": db_conn.description or ""
                })
            
            # Obtener Apps del usuario
            app_service = self.factory.get_app_service()
            user_apps = app_service.get_all()
            
            apps = []
            for app in user_apps:
                apps.append({
                    "id": str(app.id),  # App ID como string
                    "name": app.name or f"App_{app.id}",
                    "description": app.description or ""
                })
            
            logger.info(f"[DescriptionSelectorService] 📋 Fetched {len(dbs)} DBs, {len(apps)} apps")
            
            return {
                "dbs": dbs,
                "apps": apps
            }
            
        except Exception as e:
            logger.exception(f"[DescriptionSelectorService] ❌ Error fetching descriptions: {e}")
            return {"dbs": [], "apps": []}
    
    def select(
        self, 
        user_text: str, 
        top_k: int = 2, 
        threshold: float = 0.55
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Selecciona DBs y Apps más relevantes basándose en similitud de texto.
        
        Args:
            user_text: Texto del mensaje del usuario
            top_k: Máximo número de candidatos por tipo
            threshold: Umbral mínimo de similitud (0.0-1.0)
            
        Returns:
            Dict con 'db_candidates' y 'app_candidates', cada uno lista de (id, score)
        """
        if not user_text or not user_text.strip():
            logger.warning("[DescriptionSelectorService] ⚠️ Empty user_text provided")
            return {"db_candidates": [], "app_candidates": []}
        
        user_text_lower = user_text.lower().strip()
        descriptions = self.fetch_descriptions()
        
        # Calcular similitud para DBs
        db_candidates = []
        for db in descriptions["dbs"]:
            similarity = self._calculate_similarity(
                user_text_lower, 
                db["name"], 
                db["description"]
            )
            if similarity >= threshold:
                db_candidates.append((db["id"], similarity))
        
        # Calcular similitud para Apps
        app_candidates = []
        for app in descriptions["apps"]:
            similarity = self._calculate_similarity(
                user_text_lower, 
                app["name"], 
                app["description"]
            )
            if similarity >= threshold:
                app_candidates.append((app["id"], similarity))
        
        # Ordenar por score descendente y limitar a top_k
        db_candidates.sort(key=lambda x: x[1], reverse=True)
        app_candidates.sort(key=lambda x: x[1], reverse=True)
        
        db_candidates = db_candidates[:top_k]
        app_candidates = app_candidates[:top_k]
        
        logger.info(f"[DescriptionSelectorService] 🎯 Selected {len(db_candidates)} DBs, {len(app_candidates)} apps (threshold={threshold})")
        
        if db_candidates:
            logger.info(f"[DescriptionSelectorService] 🗄️ DB candidates: {[(id[:8], f'{score:.3f}') for id, score in db_candidates]}")
        if app_candidates:
            logger.info(f"[DescriptionSelectorService] 📱 App candidates: {[(id[:8], f'{score:.3f}') for id, score in app_candidates]}")
        
        return {
            "db_candidates": db_candidates,
            "app_candidates": app_candidates
        }
    
    def _calculate_similarity(
        self, 
        user_text: str, 
        name: str, 
        description: str
    ) -> float:
        """
        Calcula similitud entre user_text y name/description usando difflib.
        
        Args:
            user_text: Texto del usuario (ya en lowercase)
            name: Nombre del recurso
            description: Descripción del recurso
            
        Returns:
            Score de similitud (0.0-1.0)
        """
        # Preparar textos para comparación
        name_lower = (name or "").lower().strip()
        desc_lower = (description or "").lower().strip()
        
        # Combinar name y description con peso mayor al name
        combined_text = f"{name_lower} {name_lower} {desc_lower}".strip()  # Name duplicado para mayor peso
        
        if not combined_text:
            return 0.0
        
        # Calcular similitud usando SequenceMatcher
        matcher = difflib.SequenceMatcher(None, user_text, combined_text)
        similarity = matcher.ratio()
        
        # Bonus por palabras exactas encontradas
        user_words = set(user_text.split())
        combined_words = set(combined_text.split())
        word_overlap = len(user_words.intersection(combined_words))
        
        if word_overlap > 0:
            word_bonus = min(0.2, word_overlap * 0.1)  # Máximo 0.2 bonus
            similarity = min(1.0, similarity + word_bonus)
        
        return similarity
