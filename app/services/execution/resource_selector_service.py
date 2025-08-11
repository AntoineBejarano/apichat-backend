# app/services/execution/resource_selector_service.py
"""
Servicio para selección automática de recursos (DB + App) en modo Guided.
Implementa heurísticas de scoring basadas en intención, cobertura funcional, frescura, etc.
"""
import logging
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ResourceScore:
    """Puntuación individual de un recurso."""
    resource_id: str
    resource_name: str
    score: float
    reasons: List[str]
    metadata: Dict[str, Any]


@dataclass
class ResourceSelection:
    """Resultado de la selección de recursos."""
    database: ResourceScore
    application: ResourceScore
    combined_score: float
    selection_reasons: List[str]
    confidence: float


class ResourceSelectorService:
    """
    Servicio para selección automática de recursos en modo Guided.
    
    Heurísticas de scoring:
    - Intención del usuario (match semántico)
    - Cobertura funcional
    - Frescura de datos
    - Coste/latencia
    - Riesgo/permisos
    - Confianza del esquema
    """
    
    def __init__(self):
        # Umbrales configurables
        self.APP_MIN_THRESHOLD = 0.6
        self.DB_MIN_THRESHOLD = 0.5
        self.COMBINED_MIN_THRESHOLD = 0.7
        
        # Pesos para cada factor de scoring
        self.WEIGHTS = {
            'intent_match': 0.3,
            'functional_coverage': 0.25,
            'freshness': 0.15,
            'cost_latency': 0.1,
            'risk_permissions': 0.1,
            'schema_confidence': 0.1
        }
    
    async def select_for_guided(
        self, 
        prompt: str, 
        candidate_dbs: List[Dict[str, Any]], 
        candidate_apps: List[Dict[str, Any]]
    ) -> ResourceSelection:
        """
        Selecciona automáticamente 1 DB + 1 App para modo Guided.
        
        Args:
            prompt: Mensaje del usuario
            candidate_dbs: Lista de bases de datos candidatas
            candidate_apps: Lista de aplicaciones candidatas
            
        Returns:
            ResourceSelection con la mejor combinación
        """
        logger.info(f"[ResourceSelector] 🔍 Seleccionando recursos para prompt: '{prompt[:100]}...'")
        logger.info(f"[ResourceSelector] 📊 Candidatos: {len(candidate_dbs)} DBs, {len(candidate_apps)} Apps")
        
        # Validar que tenemos candidatos
        if not candidate_dbs or not candidate_apps:
            raise ValueError("Se requieren tanto bases de datos como aplicaciones candidatas")
        
        # Calcular scores para cada recurso
        db_scores = await self._score_databases(prompt, candidate_dbs)
        app_scores = await self._score_applications(prompt, candidate_apps)
        
        # Filtrar por umbrales mínimos
        valid_dbs = [db for db in db_scores if db.score >= self.DB_MIN_THRESHOLD]
        valid_apps = [app for app in app_scores if app.score >= self.APP_MIN_THRESHOLD]
        
        if not valid_dbs or not valid_apps:
            logger.warning(f"[ResourceSelector] ⚠️ No hay recursos válidos después de filtrar umbrales")
            # Usar los mejores disponibles aunque estén por debajo del umbral
            valid_dbs = sorted(db_scores, key=lambda x: x.score, reverse=True)[:3]
            valid_apps = sorted(app_scores, key=lambda x: x.score, reverse=True)[:3]
        
        # Encontrar la mejor combinación
        best_combination = await self._find_best_combination(valid_dbs, valid_apps)
        
        logger.info(f"[ResourceSelector] ✅ Selección completada:")
        logger.info(f"  🗄️  DB: {best_combination.database.resource_name} (score: {best_combination.database.score:.2f})")
        logger.info(f"  📱 App: {best_combination.application.resource_name} (score: {best_combination.application.score:.2f})")
        logger.info(f"  🎯 Score combinado: {best_combination.combined_score:.2f}")
        logger.info(f"  🎯 Confianza: {best_combination.confidence:.2f}")
        
        return best_combination
    
    async def propose_for_explorer(
        self, 
        prompt: str, 
        all_dbs: List[Dict[str, Any]], 
        all_apps: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Propone top-2 combinaciones de recursos para modo Explorer.
        
        Args:
            prompt: Mensaje del usuario
            all_dbs: Lista completa de bases de datos disponibles
            all_apps: Lista completa de aplicaciones disponibles
            
        Returns:
            Lista de top-2 propuestas con scores y razones
        """
        logger.info(f"[ResourceSelector] 🎯 Proponiendo recursos para Explorer: '{prompt[:100]}...'")
        logger.info(f"[ResourceSelector] 📊 Recursos disponibles: {len(all_dbs)} DBs, {len(all_apps)} Apps")
        
        if not all_dbs or not all_apps:
            logger.warning(f"[ResourceSelector] ⚠️ No hay suficientes recursos para proponer")
            return []
        
        # Calcular scores para todos los recursos
        db_scores = await self._score_databases(prompt, all_dbs)
        app_scores = await self._score_applications(prompt, all_apps)
        
        # Tomar top-3 de cada tipo para generar combinaciones
        top_dbs = db_scores[:3]
        top_apps = app_scores[:3]
        
        # Generar todas las combinaciones posibles
        combinations = []
        for db in top_dbs:
            for app in top_apps:
                # Score combinado con bonus por compatibilidad
                combined_score = (db.score + app.score) / 2
                compatibility_bonus = self._calculate_compatibility_bonus(db, app)
                combined_score += compatibility_bonus
                
                combination = {
                    "database": {
                        "id": db.resource_id,
                        "name": db.resource_name,
                        "score": db.score,
                        "reasons": db.reasons[:2],  # Top 2 razones
                        "metadata": {
                            "table_count": db.metadata.get('table_count', 0),
                            "size_mb": db.metadata.get('size_mb', 0),
                            "last_updated": db.metadata.get('last_updated')
                        }
                    },
                    "application": {
                        "id": app.resource_id,
                        "name": app.resource_name,
                        "score": app.score,
                        "reasons": app.reasons[:2],  # Top 2 razones
                        "metadata": {
                            "api_count": app.metadata.get('api_count', 0),
                            "last_updated": app.metadata.get('last_updated')
                        }
                    },
                    "combined_score": combined_score,
                    "selection_reasons": db.reasons[:2] + app.reasons[:2] + [f"Compatibilidad: {compatibility_bonus:.2f}"],
                    "confidence": min(combined_score, 1.0)
                }
                combinations.append(combination)
        
        # Ordenar por score combinado y tomar top-2
        combinations.sort(key=lambda x: x["combined_score"], reverse=True)
        top_combinations = combinations[:2]
        
        logger.info(f"[ResourceSelector] ✅ Propuestas generadas:")
        for i, combo in enumerate(top_combinations, 1):
            logger.info(f"  🎯 Opción {i}:")
            logger.info(f"    🗄️  DB: {combo['database']['name']} (score: {combo['database']['score']:.2f})")
            logger.info(f"    📱 App: {combo['application']['name']} (score: {combo['application']['score']:.2f})")
            logger.info(f"    🎯 Score combinado: {combo['combined_score']:.2f}")
        
        return top_combinations
    
    async def _score_databases(self, prompt: str, dbs: List[Dict[str, Any]]) -> List[ResourceScore]:
        """Calcula scores para bases de datos candidatas."""
        scores = []
        
        for db in dbs:
            score = 0.0
            reasons = []
            
            # Intent match (match semántico con nombre/descripción)
            intent_score = self._calculate_intent_match(prompt, db.get('name', ''), db.get('description', ''))
            score += intent_score * self.WEIGHTS['intent_match']
            if intent_score > 0.7:
                reasons.append(f"Match alto con intención: '{db.get('name', '')}'")
            
            # Functional coverage (número de tablas/funcionalidades)
            coverage_score = self._calculate_coverage_score(db)
            score += coverage_score * self.WEIGHTS['functional_coverage']
            if coverage_score > 0.8:
                reasons.append(f"Alta cobertura funcional: {db.get('table_count', 0)} tablas")
            
            # Freshness (última actualización)
            freshness_score = self._calculate_freshness_score(db)
            score += freshness_score * self.WEIGHTS['freshness']
            if freshness_score > 0.8:
                reasons.append("Datos muy recientes")
            
            # Cost/latency (estimación)
            cost_score = self._calculate_cost_score(db)
            score += cost_score * self.WEIGHTS['cost_latency']
            if cost_score > 0.8:
                reasons.append("Bajo coste/latencia estimada")
            
            # Risk/permissions
            risk_score = self._calculate_risk_score(db)
            score += risk_score * self.WEIGHTS['risk_permissions']
            if risk_score > 0.8:
                reasons.append("Bajo riesgo, permisos adecuados")
            
            # Schema confidence
            schema_score = self._calculate_schema_confidence(db)
            score += schema_score * self.WEIGHTS['schema_confidence']
            if schema_score > 0.8:
                reasons.append("Esquema bien documentado y validado")
            
            scores.append(ResourceScore(
                resource_id=db.get('id', ''),
                resource_name=db.get('name', ''),
                score=score,
                reasons=reasons,
                metadata=db
            ))
        
        return sorted(scores, key=lambda x: x.score, reverse=True)
    
    async def _score_applications(self, prompt: str, apps: List[Dict[str, Any]]) -> List[ResourceScore]:
        """Calcula scores para aplicaciones candidatas."""
        scores = []
        
        for app in apps:
            score = 0.0
            reasons = []
            
            # Intent match
            intent_score = self._calculate_intent_match(prompt, app.get('name', ''), app.get('description', ''))
            score += intent_score * self.WEIGHTS['intent_match']
            if intent_score > 0.7:
                reasons.append(f"Match alto con intención: '{app.get('name', '')}'")
            
            # Functional coverage (APIs disponibles)
            coverage_score = self._calculate_app_coverage_score(app)
            score += coverage_score * self.WEIGHTS['functional_coverage']
            if coverage_score > 0.8:
                reasons.append(f"Alta cobertura de APIs: {app.get('api_count', 0)} endpoints")
            
            # Freshness (última actualización de la app)
            freshness_score = self._calculate_app_freshness_score(app)
            score += freshness_score * self.WEIGHTS['freshness']
            if freshness_score > 0.8:
                reasons.append("Aplicación actualizada recientemente")
            
            # Cost/latency
            cost_score = self._calculate_app_cost_score(app)
            score += cost_score * self.WEIGHTS['cost_latency']
            if cost_score > 0.8:
                reasons.append("Bajo coste/latencia estimada")
            
            # Risk/permissions
            risk_score = self._calculate_app_risk_score(app)
            score += risk_score * self.WEIGHTS['risk_permissions']
            if risk_score > 0.8:
                reasons.append("Bajo riesgo, permisos adecuados")
            
            # Schema confidence (OpenAPI spec)
            schema_score = self._calculate_app_schema_confidence(app)
            score += schema_score * self.WEIGHTS['schema_confidence']
            if schema_score > 0.8:
                reasons.append("OpenAPI spec bien documentado")
            
            scores.append(ResourceScore(
                resource_id=app.get('id', ''),
                resource_name=app.get('name', ''),
                score=score,
                reasons=reasons,
                metadata=app
            ))
        
        return sorted(scores, key=lambda x: x.score, reverse=True)
    
    async def _find_best_combination(
        self, 
        db_scores: List[ResourceScore], 
        app_scores: List[ResourceScore]
    ) -> ResourceSelection:
        """Encuentra la mejor combinación DB + App."""
        best_combination = None
        best_score = 0.0
        
        # Probar combinaciones de top DBs y Apps
        top_dbs = db_scores[:3]
        top_apps = app_scores[:3]
        
        for db in top_dbs:
            for app in top_apps:
                # Score combinado con bonus por compatibilidad
                combined_score = (db.score + app.score) / 2
                compatibility_bonus = self._calculate_compatibility_bonus(db, app)
                combined_score += compatibility_bonus
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_combination = ResourceSelection(
                        database=db,
                        application=app,
                        combined_score=combined_score,
                        selection_reasons=db.reasons + app.reasons + [f"Compatibilidad: {compatibility_bonus:.2f}"],
                        confidence=min(combined_score, 1.0)
                    )
        
        return best_combination
    
    def _calculate_intent_match(self, prompt: str, name: str, description: str) -> float:
        """Calcula match semántico entre prompt y recurso."""
        # Implementación simple basada en palabras clave
        prompt_lower = prompt.lower()
        name_lower = name.lower()
        desc_lower = description.lower() if description else ""
        
        # Score por nombre exacto
        if name_lower in prompt_lower:
            return 0.9
        
        # Score por palabras clave en nombre
        name_words = set(name_lower.split())
        prompt_words = set(prompt_lower.split())
        name_match = len(name_words.intersection(prompt_words)) / max(len(name_words), 1)
        
        # Score por palabras clave en descripción
        desc_words = set(desc_lower.split())
        desc_match = len(desc_words.intersection(prompt_words)) / max(len(desc_words), 1)
        
        return max(name_match, desc_match * 0.7)
    
    def _calculate_coverage_score(self, db: Dict[str, Any]) -> float:
        """Calcula score de cobertura funcional para DB."""
        table_count = db.get('table_count', 0)
        if table_count > 100:
            return 1.0
        elif table_count > 50:
            return 0.8
        elif table_count > 20:
            return 0.6
        elif table_count > 10:
            return 0.4
        else:
            return 0.2
    
    def _calculate_freshness_score(self, db: Dict[str, Any]) -> float:
        """Calcula score de frescura para DB."""
        last_updated = db.get('last_updated')
        if not last_updated:
            return 0.5  # Valor por defecto
        
        try:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            
            now = datetime.now(timezone.utc)
            days_old = (now - last_updated).days
            
            if days_old <= 1:
                return 1.0
            elif days_old <= 7:
                return 0.9
            elif days_old <= 30:
                return 0.7
            elif days_old <= 90:
                return 0.5
            else:
                return 0.3
        except:
            return 0.5
    
    def _calculate_cost_score(self, db: Dict[str, Any]) -> float:
        """Calcula score de coste/latencia para DB."""
        # Implementación simple - asumir que DBs más pequeñas son más rápidas
        size_mb = db.get('size_mb', 1000)
        if size_mb < 100:
            return 1.0
        elif size_mb < 500:
            return 0.8
        elif size_mb < 1000:
            return 0.6
        else:
            return 0.4
    
    def _calculate_risk_score(self, db: Dict[str, Any]) -> float:
        """Calcula score de riesgo para DB."""
        # Implementación simple - asumir que DBs de solo lectura son más seguras
        is_readonly = db.get('is_readonly', False)
        if is_readonly:
            return 1.0
        else:
            return 0.7
    
    def _calculate_schema_confidence(self, db: Dict[str, Any]) -> float:
        """Calcula score de confianza del esquema para DB."""
        # Implementación simple - asumir que DBs con más metadatos son más confiables
        has_comments = db.get('has_comments', False)
        has_constraints = db.get('has_constraints', False)
        has_indexes = db.get('has_indexes', False)
        
        score = 0.5  # Base
        if has_comments:
            score += 0.2
        if has_constraints:
            score += 0.2
        if has_indexes:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_app_coverage_score(self, app: Dict[str, Any]) -> float:
        """Calcula score de cobertura funcional para App."""
        api_count = app.get('api_count', 0)
        if api_count > 50:
            return 1.0
        elif api_count > 25:
            return 0.8
        elif api_count > 10:
            return 0.6
        elif api_count > 5:
            return 0.4
        else:
            return 0.2
    
    def _calculate_app_freshness_score(self, app: Dict[str, Any]) -> float:
        """Calcula score de frescura para App."""
        last_updated = app.get('last_updated')
        if not last_updated:
            return 0.5
        
        try:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            
            now = datetime.now(timezone.utc)
            days_old = (now - last_updated).days
            
            if days_old <= 7:
                return 1.0
            elif days_old <= 30:
                return 0.8
            elif days_old <= 90:
                return 0.6
            elif days_old <= 180:
                return 0.4
            else:
                return 0.2
        except:
            return 0.5
    
    def _calculate_app_cost_score(self, app: Dict[str, Any]) -> float:
        """Calcula score de coste/latencia para App."""
        # Implementación simple
        rate_limit = app.get('rate_limit', 1000)
        if rate_limit > 10000:
            return 1.0
        elif rate_limit > 5000:
            return 0.8
        elif rate_limit > 1000:
            return 0.6
        else:
            return 0.4
    
    def _calculate_app_risk_score(self, app: Dict[str, Any]) -> float:
        """Calcula score de riesgo para App."""
        # Implementación simple
        requires_auth = app.get('requires_auth', True)
        has_rate_limiting = app.get('has_rate_limiting', True)
        
        score = 0.5  # Base
        if requires_auth:
            score += 0.3
        if has_rate_limiting:
            score += 0.2
        
        return min(score, 1.0)
    
    def _calculate_app_schema_confidence(self, app: Dict[str, Any]) -> float:
        """Calcula score de confianza del esquema para App."""
        # Implementación simple
        has_openapi = app.get('has_openapi_spec', False)
        has_examples = app.get('has_examples', False)
        has_descriptions = app.get('has_descriptions', False)
        
        score = 0.5  # Base
        if has_openapi:
            score += 0.3
        if has_examples:
            score += 0.1
        if has_descriptions:
            score += 0.1
        
        return min(score, 1.0)
    
    def _calculate_compatibility_bonus(self, db: ResourceScore, app: ResourceScore) -> float:
        """Calcula bonus por compatibilidad entre DB y App."""
        # Implementación simple - bonus si ambos tienen scores altos
        if db.score > 0.8 and app.score > 0.8:
            return 0.1
        elif db.score > 0.6 and app.score > 0.6:
            return 0.05
        else:
            return 0.0
