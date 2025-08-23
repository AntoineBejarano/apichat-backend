# app/services/schema_explorer_service.py
"""
SchemaExplorerService - Nivel Unicornio 🦄
───────────────────────────────────────────
Servicio para explorar y cachear esquemas de base de datos con información completa.
Integra con DetailedSchemaCache para mantener esquemas detallados actualizados.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from sqlalchemy import inspect, text, MetaData
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
from dataclasses import asdict

from app.services.data.cache_service import CacheService
from app.services.data.database_service import DatabaseService
from app.core.config import settings
from .detailed_schema_cache import DetailedSchemaCache, DatabaseSchema, TableInfo, ColumnInfo, ColumnType
from .synonyms_config_service import SynonymsConfigService

logger = logging.getLogger(__name__)


class SchemaExplorerService:
    """
    Servicio para explorar y cachear esquemas de base de datos con información completa.
    """
    
    def __init__(self, cache_service: CacheService, database_service: DatabaseService, factory=None):
        self.cache_service = cache_service
        self.database_service = database_service
        self.factory = factory  # 🔧 FIX: Inyectar ServiceFactory
        self.detailed_cache = DetailedSchemaCache()
        
        # 🔧 FASE 8: Inicializar servicio de configuración de sinónimos
        self.synonyms_service = SynonymsConfigService()
        
        # Umbrales para Fast Schema Path (Fase 7) desde configuración
        self.CONF_FAST = settings.CONF_FAST
        self.CONF_AMBIGUOUS = settings.CONF_AMBIGUOUS
        self.FAST_PATH_RESPONSE_TIME_MS = settings.FAST_PATH_RESPONSE_TIME_MS
        
        # Índices léxicos para búsqueda rápida
        self._lexical_indexes = {}  # {db_id: {term: [(table, column, score)]}}
        
        logger.info(f"[SchemaExplorerService] 🦄 Inicializado con Fast Schema Path (CONF_FAST={self.CONF_FAST})")
        logger.info(f"[SchemaExplorerService] 🔧 FASE 8: Servicio de sinónimos configurado")
        if factory:
            logger.info(f"[SchemaExplorerService] ✅ ServiceFactory inyectado correctamente")
        else:
            logger.warning(f"[SchemaExplorerService] ⚠️ ServiceFactory no inyectado - algunas funcionalidades pueden no estar disponibles")
    
    async def fast_lookup(
        self, 
        query: str, 
        db_ids: List[UUID]
    ) -> Tuple[Optional[Dict[str, Any]], float, str]:
        """
        Fast Schema Path: búsqueda rápida sin LLM usando índices léxicos.
        
        Args:
            query: Consulta del usuario (ej: "¿dónde está el campo email?")
            db_ids: Lista de IDs de bases de datos a buscar
            
        Returns:
            Tuple: (resultado, confianza, tipo_respuesta)
            - resultado: Dict con matches encontrados o None
            - confianza: Score de confianza (0.0 - 1.0)
            - tipo_respuesta: "fast", "ambiguous", "fallback"
        """
        try:
            logger.info(f"[SchemaExplorerService] 🚀 Fast lookup para: '{query}' en {len(db_ids)} DBs")
            
            # 1. Normalizar y tokenizar la query
            normalized_query = self._normalize_query(query)
            query_terms = self._extract_search_terms(normalized_query)
            
            if not query_terms:
                logger.info("[SchemaExplorerService] ⚠️ No se pudieron extraer términos de búsqueda")
                return None, 0.0, "fallback"
            
            # 2. Buscar en índices léxicos
            all_matches = []
            total_score = 0.0
            
            for db_id in db_ids:
                # Asegurar que el índice léxico esté construido
                if db_id not in self._lexical_indexes:
                    await self._build_lexical_index(db_id)
                
                # Buscar matches en este DB
                db_matches = self._search_lexical_index(db_id, query_terms)
                if db_matches:
                    all_matches.extend(db_matches)
                    total_score += sum(match['score'] for match in db_matches)
            
            if not all_matches:
                logger.info("[SchemaExplorerService] ⚠️ No se encontraron matches en índices léxicos")
                # 🔧 FASE 8: Intentar fallback inteligente con consultas de catálogo
                catalog_fallback = self._try_catalog_fallback(query, db_ids)
                if catalog_fallback:
                    logger.info(f"[SchemaExplorerService] 🔧 FASE 8: Fallback de catálogo exitoso: {catalog_fallback['query_type']}")
                    return catalog_fallback, 0.6, "catalog_fallback"  # Confianza media para fallback
                else:
                    logger.info("[SchemaExplorerService] 📉 No hay fallback de catálogo disponible, ir a LLM")
                    return None, 0.0, "fallback"
            
            # 3. Calcular confianza y determinar tipo de respuesta
            # 🔧 FASE 8: Mejorar cálculo de confianza con más factores
            if all_matches:
                # Calcular confianza base
                avg_confidence = total_score / len(all_matches)
                
                # 🔧 FASE 8: Factores adicionales para mejorar confianza
                confidence_boost = 0.0
                
                # Boost por número de matches (más matches = más confianza)
                if len(all_matches) >= 3:
                    confidence_boost += 0.1
                elif len(all_matches) >= 2:
                    confidence_boost += 0.05
                
                # Boost por calidad de matches (exactos vs parciales)
                exact_matches = sum(1 for match in all_matches if match.get('score', 0) >= 0.9)
                if exact_matches >= 2:
                    confidence_boost += 0.15
                elif exact_matches >= 1:
                    confidence_boost += 0.1
                
                # Boost por cobertura de tablas (más tablas = más contexto)
                unique_tables = len(set(match.get('table', '') for match in all_matches))
                if unique_tables >= 3:
                    confidence_boost += 0.1
                elif unique_tables >= 2:
                    confidence_boost += 0.05
                
                # Boost por términos de búsqueda específicos
                query_terms = self._extract_search_terms(self._normalize_query(query))
                if len(query_terms) >= 3:
                    confidence_boost += 0.05
                
                # Aplicar boost y cap en 1.0
                confidence = min(avg_confidence + confidence_boost, 1.0)
                
                logger.info(f"[SchemaExplorerService] 🔧 FASE 8: Confianza calculada: base={avg_confidence:.2f}, boost={confidence_boost:.2f}, final={confidence:.2f}")
            else:
                confidence = 0.0
            
            # 4. Determinar tipo de respuesta según umbrales
            if confidence >= self.CONF_FAST:
                response_type = "fast"
                result = self._format_fast_response(all_matches, confidence)
                logger.info(f"[SchemaExplorerService] ✅ Fast response con confianza {confidence:.2f}")
                
            elif confidence >= self.CONF_AMBIGUOUS:
                response_type = "ambiguous"
                result = self._format_ambiguous_response(all_matches, confidence)
                logger.info(f"[SchemaExplorerService] 🤔 Respuesta ambigua con confianza {confidence:.2f}")
                
            else:
                response_type = "fallback"
                result = None
                logger.info(f"[SchemaExplorerService] 📉 Fallback LLM con confianza {confidence:.2f}")
            
            return result, confidence, response_type
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error en fast_lookup: {e}")
            return None, 0.0, "fallback"

    def _try_catalog_fallback(self, query: str, db_ids: List[UUID]) -> Optional[Dict[str, Any]]:
        """
        🔧 FASE 8: Intenta generar una consulta de catálogo segura basada en la intención del usuario.
        
        Args:
            query: Consulta original del usuario
            db_ids: Lista de IDs de bases de datos
            
        Returns:
            Dict con consulta de catálogo segura o None si no es posible
        """
        try:
            logger.info(f"[SchemaExplorerService] 🔧 FASE 8: Intentando fallback de catálogo para: '{query}'")
            
            # Normalizar y analizar la consulta
            normalized_query = self._normalize_query(query)
            query_terms = self._extract_search_terms(normalized_query)
            
            # 🎯 DETECTAR INTENCIÓN ESPECÍFICA
            intention = self._detect_user_intention(query, query_terms)
            
            # 🚀 OPTIMIZACIÓN: Respuestas directas desde caché para intenciones simples
            if intention == "list_tables":
                # Intención: Listar tablas disponibles - RESPUESTA DIRECTA DESDE CACHÉ
                return self._generate_direct_cache_response(db_ids, "list_tables")
                
            elif intention == "explore_schema":
                # Intención: Explorar esquema completo - RESPUESTA DIRECTA DESDE CACHÉ
                return self._generate_direct_cache_response(db_ids, "explore_schema")
                
            elif intention == "get_table_stats":
                # Intención: Estadísticas básicas - RESPUESTA DIRECTA DESDE CACHÉ
                return self._generate_direct_cache_response(db_ids, "table_stats")
                
            elif intention == "find_specific_tables":
                # Intención: Buscar tablas específicas por palabras clave
                keywords = self._extract_safe_keywords(query_terms)
                if keywords:
                    return self._generate_safe_table_search_query(db_ids, keywords)
                    
            elif intention == "explore_table_structure":
                # Intención: Explorar estructura de tabla específica
                table_name = self._extract_table_name_from_query(query)
                if table_name:
                    return self._generate_safe_table_structure_query(db_ids, table_name)
                    
            elif intention == "find_relationships":
                # Intención: Encontrar relaciones entre tablas
                return self._generate_safe_relationships_query(db_ids)
                
            elif intention == "get_table_stats":
                # Intención: Obtener estadísticas de tablas
                return self._generate_safe_table_stats_query(db_ids)
                
            elif intention == "explore_schema":
                # Intención: Explorar esquema completo
                return self._generate_safe_schema_exploration_query(db_ids)
            
            # Si no se puede determinar la intención, usar consulta genérica de tablas
            logger.info("[SchemaExplorerService] 🔧 FASE 8: Intención no determinada, usando fallback genérico")
            return self._generate_safe_table_list_query(db_ids)
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error en fallback de catálogo: {e}")
            return None

    def _detect_user_intention(self, query: str, query_terms: List[str]) -> str:
        """
        🌍 FASE 8: Detecta la intención del usuario usando un protocolo genérico y MULTILINGÜE.
        Basado en análisis semántico y patrones de lenguaje natural en múltiples idiomas.
        """
        query_lower = query.lower()
        
        # 🌍 PROTOCOLO MULTILINGÜE: Análisis de intención por patrones semánticos
        
        # 🧠 DETECCIÓN INTELIGENTE AVANZADA: Consultas sobre BD en general
        # Si la consulta es sobre la base de datos (estructura, esquema, entidades)
        # pero NO específicamente sobre tablas, entonces es list_tables
        db_general_indicators = [
            'base de datos', 'database', 'base de données', 'datenbank', 'database', 'banco de dados',
            'estructura', 'structure', 'structure', 'struktur', 'struttura', 'estrutura',
            'esquema', 'schema', 'schéma', 'schema', 'schema', 'esquema',
            'entidad', 'entity', 'entité', 'entität', 'entità', 'entidade'
        ]
        
        if any(indicator in query_lower for indicator in db_general_indicators):
            # Si NO hay indicadores específicos de tablas, es list_tables
            if not any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
                return "list_tables"
        
        # 1. INTENCIÓN: Explorar estructura de base de datos (PRIORIDAD MEDIA)
        # Solo si NO hay indicadores de listado de tablas
        structure_indicators = [
            # Español
            'estructura', 'columna', 'campo', 'definicion', 'definición',
            # English
            'structure', 'column', 'field', 'definition',
            # Français
            'structure', 'colonne', 'champ', 'définition',
            # Deutsch
            'struktur', 'spalte', 'feld', 'definition',
            # Italiano
            'struttura', 'colonna', 'campo', 'definizione',
            # Português
            'estrutura', 'coluna', 'campo', 'definição'
        ]
        if any(indicator in query_lower for indicator in structure_indicators):
            # Si también hay indicadores de tablas, priorizar list_tables
            if any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
                return "list_tables"
            return "explore_table_structure"
        
        # 2. INTENCIÓN: Encontrar relaciones entre entidades
        relationship_indicators = [
            # Español
            'relacion', 'relación', 'foreign', 'key', 'conexion', 'conexión', 'vinculo', 'vínculo', 'link',
            # English
            'relationship', 'foreign', 'key', 'connection', 'link',
            # Français
            'relation', 'étrangère', 'clé', 'connexion', 'lien',
            # Deutsch
            'beziehung', 'fremd', 'schlüssel', 'verbindung', 'verknüpfung',
            # Italiano
            'relazione', 'straniera', 'chiave', 'connessione', 'collegamento',
            # Português
            'relação', 'estrangeira', 'chave', 'conexão', 'ligação'
        ]
        if any(indicator in query_lower for indicator in relationship_indicators):
            return "find_relationships"
        
        # 3. INTENCIÓN: Obtener métricas y estadísticas
        stats_indicators = [
            # Español
            'estadistica', 'estadística', 'tamaño', 'cantidad', 'numero', 'número', 'metrica', 'métrica',
            # English
            'stats', 'statistics', 'size', 'count', 'number', 'metric',
            # Français
            'statistique', 'taille', 'compte', 'nombre', 'métrique',
            # Deutsch
            'statistik', 'größe', 'anzahl', 'zahl', 'metrik',
            # Italiano
            'statistica', 'dimensione', 'conteggio', 'numero', 'metrica',
            # Português
            'estatística', 'tamanho', 'contagem', 'número', 'métrica'
        ]
        if any(indicator in query_lower for indicator in stats_indicators):
            return "get_table_stats"
        
        # 5. INTENCIÓN: Listado general de entidades disponibles (PRIORIDAD ALTA)
        list_indicators = [
            # Español
            'tabla', 'tablas', 'lista', 'listado', 'todo', 'todas', 'disponible', 'disponibles',
            # English
            'table', 'tables', 'list', 'all', 'available',
            # Français
            'table', 'tables', 'liste', 'tout', 'disponible',
            # Deutsch
            'tabelle', 'tabellen', 'liste', 'alle', 'verfügbar',
            # Italiano
            'tabella', 'tabelle', 'lista', 'tutto', 'disponibile',
            # Português
            'tabela', 'tabelas', 'lista', 'tudo', 'disponível'
        ]
        if any(indicator in query_lower for indicator in list_indicators):
            return "list_tables"
        
        # 4. INTENCIÓN: Búsqueda específica por contexto semántico (PRIORIDAD BAJA)
        # Solo palabras que claramente indican búsqueda específica, NO palabras genéricas
        search_indicators = [
            # Español
            'donde', 'buscar', 'encontrar', 'cual', 'cuál',
            # English
            'where', 'search', 'find', 'which',
            # Français
            'où', 'rechercher', 'trouver', 'quel', 'quelle',
            # Deutsch
            'wo', 'suchen', 'finden', 'welche',
            # Italiano
            'dove', 'cercare', 'trovare', 'quale',
            # Português
            'onde', 'procurar', 'encontrar', 'qual'
        ]
        if any(indicator in query_lower for indicator in search_indicators):
            return "find_specific_tables"
        
        # 6. INTENCIÓN: Explorar esquema completo (PRIORIDAD MEDIA)
        # Solo si NO hay indicadores de listado de tablas
        schema_indicators = [
            # Español
            'esquema', 'base de datos', 'modelo', 'diseño', 'diseño',
            # English
            'schema', 'database', 'model', 'design',
            # Français
            'schéma', 'base de données', 'modèle', 'conception',
            # Deutsch
            'schema', 'datenbank', 'modell', 'entwurf',
            # Italiano
            'schema', 'database', 'modello', 'progetto',
            # Português
            'esquema', 'banco de dados', 'modelo', 'design'
        ]
        if any(indicator in query_lower for indicator in schema_indicators):
            # Si también hay indicadores de tablas, priorizar list_tables
            if any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
                return "list_tables"
            return "explore_schema"
        
        # 🌍 DETECCIÓN MULTILINGÜE AVANZADA: Patrones específicos por idioma
        advanced_intention = self._detect_language_and_intention(query_lower)
        if advanced_intention:
            return advanced_intention
        
        # 🎯 DETECCIÓN INTELIGENTE: Si no hay match específico, analizar el contexto
        # "qué tablas hay" = list_tables, no find_specific_tables
        if any(word in query_lower for word in ['qué', 'que', 'what', 'quelles', 'welche', 'quali', 'quais']):
            if any(word in query_lower for word in ['tabla', 'table', 'tables', 'tablas']):
                return "list_tables"
            if any(word in query_lower for word in ['hay', 'tiene', 'are', 'there', 'y a-t-il', 'gibt es', 'ci sono', 'existem']):
                return "list_tables"
        
        # Por defecto: Listar tablas (más útil para usuarios)
        return "list_tables"

    def _detect_language_and_intention(self, query_lower: str) -> Optional[str]:
        """
        🌍 Detecta el idioma y la intención usando patrones específicos por idioma.
        """
        # 🇺🇸 ENGLISH PATTERNS
        english_patterns = {
            "list_tables": [
                "what tables", "show tables", "list tables", "all tables", "available tables",
                "what's in the database", "what's in my database", "database contents",
                "tables list", "table names", "database structure"
            ],
            "explore_schema": [
                "database schema", "database structure", "database design", "database model",
                "how is the database structured", "database layout", "database organization"
            ],
            "get_table_stats": [
                "how many tables", "table count", "database size", "database statistics",
                "table statistics", "database metrics", "how big is the database"
            ]
        }
        
        # 🇪🇸 SPANISH PATTERNS
        spanish_patterns = {
            "list_tables": [
                "qué tablas hay", "qué tablas tiene", "muestra las tablas", "lista de tablas",
                "todas las tablas", "tablas disponibles", "qué hay en la base de datos",
                "contenido de la base de datos", "estructura de la base de datos"
            ],
            "explore_schema": [
                "esquema de la base de datos", "estructura de la base de datos", "diseño de la base de datos",
                "cómo está estructurada la base de datos", "organización de la base de datos"
            ],
            "get_table_stats": [
                "cuántas tablas hay", "número de tablas", "tamaño de la base de datos",
                "estadísticas de la base de datos", "métricas de la base de datos"
            ]
        }
        
        # 🇫🇷 FRENCH PATTERNS
        french_patterns = {
            "list_tables": [
                "quelles tables", "montrer les tables", "liste des tables", "toutes les tables",
                "tables disponibles", "que contient la base de données", "contenu de la base de données"
            ],
            "explore_schema": [
                "schéma de la base de données", "structure de la base de données",
                "comment est structurée la base de données"
            ],
            "get_table_stats": [
                "combien de tables", "nombre de tables", "taille de la base de données",
                "statistiques de la base de données"
            ]
        }
        
        # 🇩🇪 GERMAN PATTERNS
        german_patterns = {
            "list_tables": [
                "welche tabellen", "tabellen anzeigen", "tabellen liste", "alle tabellen",
                "verfügbare tabellen", "was ist in der datenbank", "datenbank inhalt"
            ],
            "explore_schema": [
                "datenbank schema", "datenbank struktur", "wie ist die datenbank strukturiert"
            ],
            "get_table_stats": [
                "wie viele tabellen", "anzahl der tabellen", "datenbank größe",
                "datenbank statistiken"
            ]
        }
        
        # 🇮🇹 ITALIAN PATTERNS
        italian_patterns = {
            "list_tables": [
                "quali tabelle", "mostra le tabelle", "lista delle tabelle", "tutte le tabelle",
                "tabelle disponibili", "cosa c'è nel database", "contenuto del database"
            ],
            "explore_schema": [
                "schema del database", "struttura del database", "come è strutturato il database"
            ],
            "get_table_stats": [
                "quante tabelle", "numero di tabelle", "dimensione del database",
                "statistiche del database"
            ]
        }
        
        # 🇵🇹 PORTUGUESE PATTERNS
        portuguese_patterns = {
            "list_tables": [
                "quais tabelas", "mostrar tabelas", "lista de tabelas", "todas as tabelas",
                "tabelas disponíveis", "o que há na base de dados", "conteúdo da base de dados"
            ],
            "explore_schema": [
                "esquema da base de dados", "estrutura da base de dados",
                "como está estruturada a base de dados"
            ],
            "get_table_stats": [
                "quantas tabelas", "número de tabelas", "tamanho da base de dados",
                "estatísticas da base de dados"
            ]
        }
        
        # 🔍 BUSCAR EN TODOS LOS IDIOMAS
        all_patterns = {
            **english_patterns,
            **spanish_patterns,
            **french_patterns,
            **german_patterns,
            **italian_patterns,
            **portuguese_patterns
        }
        
        for intention, patterns in all_patterns.items():
            if any(pattern in query_lower for pattern in patterns):
                logger.info(f"[SchemaExplorerService] 🌍 Intención detectada en múltiples idiomas: {intention}")
                return intention
        
        return None

    def _extract_safe_keywords(self, query_terms: List[str]) -> List[str]:
        """
        Extrae palabras clave seguras para búsqueda de tablas.
        Solo permite palabras alfanuméricas y guiones bajos.
        """
        safe_keywords = []
        for term in query_terms:
            # Solo palabras seguras: alfanuméricas + guiones bajos
            if re.match(r'^[a-zA-Z0-9_]+$', term) and len(term) >= 3:
                safe_keywords.append(term.lower())
        return safe_keywords[:5]  # Máximo 5 palabras clave

    def _extract_table_name_from_query(self, query: str) -> Optional[str]:
        """
        Extrae el nombre de una tabla específica de la consulta.
        Solo permite nombres de tabla seguros.
        """
        # Buscar patrones como "tabla usuarios", "table users", etc.
        patterns = [
            r'tabla\s+([a-zA-Z0-9_]+)',
            r'table\s+([a-zA-Z0-9_]+)',
            r'([a-zA-Z0-9_]+)\s+table',
            r'([a-zA-Z0-9_]+)\s+tabla'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                table_name = match.group(1)
                # Verificar que sea un nombre de tabla seguro
                if re.match(r'^[a-zA-Z0-9_]+$', table_name) and len(table_name) >= 2:
                    return table_name
        return None

    def _generate_safe_table_list_query(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Genera consulta segura para listar todas las tablas disponibles.
        """
        return {
            "type": "catalog_query",
            "query_type": "list_tables",
            "sql": """
                SELECT 
                    table_name,
                    table_type,
                    table_schema
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                ORDER BY table_name 
                LIMIT 50
            """.strip(),
            "description": "Lista todas las tablas disponibles en la base de datos",
            "safe": True,
            "source": "catalog_fallback"
        }

    def _generate_safe_table_search_query(self, db_ids: List[UUID], keywords: List[str]) -> Dict[str, Any]:
        """
        🔧 FASE 8: Genera consulta segura para buscar tablas usando un protocolo genérico y configurable.
        Usa patrones predefinidos y análisis semántico, NO interpolación de texto del usuario.
        """
        # 🛡️ SEGURIDAD: Solo patrones predefinidos, sin interpolación
        normalized_keywords = [kw.lower().strip() for kw in keywords]
        
        # 🎯 PROTOCOLO GENÉRICO: Sistema de patrones semánticos configurable
        semantic_patterns = self._get_semantic_search_patterns()
        
        # Buscar el patrón semántico más apropiado
        best_pattern = self._find_best_semantic_pattern(normalized_keywords, semantic_patterns)
        
        if best_pattern:
            return {
                "type": "catalog_query",
                "query_type": f"search_{best_pattern['category']}",
                "sql": best_pattern['sql'],
                "description": best_pattern['description'],
                "safe": True,
                "source": "catalog_fallback",
                "semantic_category": best_pattern['category'],
                "confidence_score": best_pattern['confidence']
            }
        else:
            # Fallback genérico inteligente: búsqueda por similitud de nombres
            return self._generate_smart_generic_search_query(normalized_keywords)

    def _get_semantic_search_patterns(self) -> List[Dict[str, Any]]:
        """
        🔧 FASE 8: Define patrones semánticos genéricos para búsquedas de catálogo.
        Sistema completamente configurable y extensible.
        """
        return [
            # 🏢 PATRÓN: Entidades de negocio
            {
                "category": "business_entities",
                "keywords": ['user', 'usuario', 'cliente', 'customer', 'empresa', 'company', 'negocio', 'business'],
                "sql": """
                    SELECT 
                        table_name,
                        table_type,
                        table_schema
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                        AND (
                            table_name ILIKE '%user%' OR table_name ILIKE '%usuario%'
                            OR table_name ILIKE '%client%' OR table_name ILIKE '%cliente%'
                            OR table_name ILIKE '%company%' OR table_name ILIKE '%empresa%'
                            OR table_name ILIKE '%business%' OR table_name ILIKE '%negocio%'
                        )
                    ORDER BY table_name 
                    LIMIT 25
                """.strip(),
                "description": "Entidades principales de negocio (usuarios, clientes, empresas)",
                "confidence": 0.9
            },
            
            # 📧 PATRÓN: Comunicación y notificaciones
            {
                "category": "communication",
                "keywords": ['email', 'correo', 'message', 'mensaje', 'notification', 'notificacion', 'invitation', 'invitacion'],
                "sql": """
                    SELECT 
                        table_name,
                        table_type,
                        table_schema
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                        AND (
                            table_name ILIKE '%email%' OR table_name ILIKE '%correo%'
                            OR table_name ILIKE '%message%' OR table_name ILIKE '%mensaje%'
                            OR table_name ILIKE '%notification%' OR table_name ILIKE '%notificacion%'
                            OR table_name ILIKE '%invitation%' OR table_name ILIKE '%invitacion%'
                        )
                    ORDER BY table_name 
                    LIMIT 25
                """.strip(),
                "description": "Sistemas de comunicación y notificaciones",
                "confidence": 0.85
            },
            
            # 👥 PATRÓN: Grupos y comunidades
            {
                "category": "groups_communities",
                "keywords": ['group', 'grupo', 'club', 'community', 'comunidad', 'team', 'equipo', 'member', 'miembro'],
                "sql": """
                    SELECT 
                        table_name,
                        table_type,
                        table_schema
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                        AND (
                            table_name ILIKE '%group%' OR table_name ILIKE '%grupo%'
                            OR table_name ILIKE '%club%' OR table_name ILIKE '%community%'
                            OR table_name ILIKE '%comunidad%' OR table_name ILIKE '%team%'
                            OR table_name ILIKE '%equipo%' OR table_name ILIKE '%member%'
                        )
                    ORDER BY table_name 
                    LIMIT 25
                """.strip(),
                "description": "Grupos, comunidades y equipos",
                "confidence": 0.85
            },
            
            # 📊 PATRÓN: Datos y contenido
            {
                "category": "data_content",
                "keywords": ['data', 'dato', 'content', 'contenido', 'file', 'archivo', 'document', 'documento', 'media'],
                "sql": """
                    SELECT 
                        table_name,
                        table_type,
                        table_schema
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                        AND (
                            table_name ILIKE '%data%' OR table_name ILIKE '%dato%'
                            OR table_name ILIKE '%content%' OR table_name ILIKE '%contenido%'
                            OR table_name ILIKE '%file%' OR table_name ILIKE '%archivo%'
                            OR table_name ILIKE '%document%' OR table_name ILIKE '%documento%'
                        )
                    ORDER BY table_name 
                    LIMIT 25
                """.strip(),
                "description": "Datos, contenido y archivos",
                "confidence": 0.8
            },
            
            # 🔐 PATRÓN: Seguridad y autenticación
            {
                "category": "security_auth",
                "keywords": ['auth', 'authentication', 'autenticacion', 'permission', 'permiso', 'role', 'rol', 'security', 'seguridad'],
                "sql": """
                    SELECT 
                        table_name,
                        table_type,
                        table_schema
                    FROM information_schema.tables 
                    WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                        AND (
                            table_name ILIKE '%auth%' OR table_name ILIKE '%autenticacion%'
                            OR table_name ILIKE '%permission%' OR table_name ILIKE '%permiso%'
                            OR table_name ILIKE '%role%' OR table_name ILIKE '%rol%'
                            OR table_name ILIKE '%security%' OR table_name ILIKE '%seguridad%'
                        )
                    ORDER BY table_name 
                    LIMIT 25
                """.strip(),
                "description": "Sistemas de seguridad y autenticación",
                "confidence": 0.8
            }
        ]

    def _find_best_semantic_pattern(self, keywords: List[str], patterns: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        🔧 FASE 8: Encuentra el patrón semántico más apropiado basado en palabras clave.
        Usa scoring inteligente para seleccionar la mejor coincidencia.
        """
        best_pattern = None
        best_score = 0.0
        
        for pattern in patterns:
            # Calcular score de coincidencia
            pattern_keywords = pattern['keywords']
            matches = sum(1 for kw in keywords if any(pk in kw for pk in pattern_keywords))
            
            if matches > 0:
                # Score basado en número de coincidencias y confianza del patrón
                score = (matches / len(keywords)) * pattern['confidence']
                
                if score > best_score:
                    best_score = score
                    best_pattern = pattern
        
        # Solo devolver si el score es suficientemente alto
        return best_pattern if best_score >= 0.3 else None

    def _generate_smart_generic_search_query(self, keywords: List[str]) -> Dict[str, Any]:
        """
        🔧 FASE 8: Genera búsqueda genérica inteligente cuando no hay patrones semánticos específicos.
        Usa análisis de similitud y patrones de nombres comunes.
        """
        # Crear consulta genérica que busque por similitud de nombres
        # SIN interpolación del texto del usuario
        return {
            "type": "catalog_query",
            "query_type": "smart_generic_search",
            "sql": """
                SELECT 
                    table_name,
                    table_type,
                    table_schema
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                    AND (
                        table_name ILIKE '%user%' OR table_name ILIKE '%data%'
                        OR table_name ILIKE '%info%' OR table_name ILIKE '%log%'
                        OR table_name ILIKE '%config%' OR table_name ILIKE '%setting%'
                    )
                ORDER BY table_name 
                LIMIT 30
            """.strip(),
            "description": "Búsqueda genérica inteligente en el catálogo",
            "safe": True,
            "source": "catalog_fallback",
            "semantic_category": "generic",
            "confidence_score": 0.5
        }

    def _generate_safe_table_structure_query(self, db_ids: List[UUID], table_name: str) -> Dict[str, Any]:
        """
        Genera consulta segura para explorar estructura de una tabla específica.
        """
        return {
            "type": "catalog_query",
            "query_type": "table_structure",
            "sql": f"""
                SELECT 
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                    AND table_name = '{table_name}'
                ORDER BY ordinal_position
            """.strip(),
            "description": f"Estructura de la tabla {table_name}",
            "safe": True,
            "source": "catalog_fallback",
            "target_table": table_name
        }

    def _generate_safe_relationships_query(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        Genera consulta segura para encontrar relaciones entre tablas.
        """
        return {
            "type": "catalog_query",
            "query_type": "table_relationships",
            "sql": """
                SELECT 
                    kcu.table_name,
                    kcu.column_name,
                    kcu.referenced_table_name,
                    kcu.referenced_column_name,
                    tc.constraint_name
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc 
                    ON kcu.constraint_name = tc.constraint_name
                WHERE kcu.referenced_table_name IS NOT NULL
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND kcu.table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                ORDER BY kcu.table_name, kcu.ordinal_position
                LIMIT 50
            """.strip(),
            "description": "Relaciones entre tablas (foreign keys)",
            "safe": True,
            "source": "catalog_fallback"
        }

    def _generate_safe_table_stats_query(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        🔧 FASE 8: Genera consulta segura para obtener estadísticas de tablas.
        """
        return {
            "type": "catalog_query",
            "query_type": "table_stats",
            "sql": """
                SELECT 
                    table_name,
                    table_type,
                    table_schema
                FROM information_schema.tables 
                WHERE table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                    AND table_type = 'BASE TABLE'
                ORDER BY table_name
                LIMIT 30
            """.strip(),
            "description": "Estadísticas básicas de las tablas",
            "safe": True,
            "source": "catalog_fallback"
        }

    def _generate_safe_schema_exploration_query(self, db_ids: List[UUID]) -> Dict[str, Any]:
        """
        🔧 FASE 8: Genera consulta segura para explorar el esquema completo de la base de datos.
        """
        return {
            "type": "catalog_query",
            "query_type": "schema_exploration",
            "sql": """
                SELECT 
                    t.table_name,
                    t.table_type,
                    t.table_schema,
                    COUNT(c.column_name) as column_count,
                    COUNT(CASE WHEN c.primary_key = 'YES' THEN 1 END) as primary_keys,
                    COUNT(CASE WHEN c.foreign_key = 'YES' THEN 1 END) as foreign_keys
                FROM information_schema.tables t
                LEFT JOIN information_schema.columns c ON t.table_name = c.table_name 
                    AND t.table_schema = c.table_schema
                WHERE t.table_schema NOT IN ('information_schema', 'pg_catalog', 'mysql', 'performance_schema', 'sys')
                GROUP BY t.table_name, t.table_type, t.table_schema
                ORDER BY t.table_name
                LIMIT 40
            """.strip(),
            "description": "Exploración completa del esquema de la base de datos",
            "safe": True,
            "source": "catalog_fallback"
        }

    def _generate_direct_cache_response(self, db_ids: List[UUID], response_type: str) -> Dict[str, Any]:
        """
        🚀 OPTIMIZACIÓN: Genera respuestas directas desde caché para intenciones simples.
        Evita generar planes y usar LLM para consultas básicas que ya tenemos en caché.
        
        Args:
            db_ids: Lista de IDs de bases de datos
            response_type: Tipo de respuesta a generar
            
        Returns:
            Dict con respuesta directa desde caché
        """
        try:
            logger.info(f"[SchemaExplorerService] 🚀 Generando respuesta directa desde caché: {response_type}")
            
            # Obtener esquema desde caché (ya lo tenemos)
            schema_data = self._get_schema_from_cache(db_ids[0]) if db_ids else None
            
            if not schema_data:
                logger.warning("[SchemaExplorerService] ⚠️ FASE 3: No hay esquema en caché, devolviendo mensaje útil")
                return {
                    "type": "missing_schema_response",
                    "response_type": "missing_schema",
                    "content": "⚠️ No tengo acceso al esquema de tu base de datos. ¿Quieres cargarlo primero?\n\n**Opciones disponibles:**\n• Recargar esquema de la base de datos\n• Seleccionar una base de datos específica\n• Probar con una tabla específica",
                    "metadata": {
                        "total_tables": 0,
                        "source": "missing_schema",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": False,
                        "requires_schema_load": True
                    },
                    "safe": True,
                    "source": "missing_schema_fallback",
                    "status": "missing_schema"
                }
            
            tables = schema_data.get('tables', [])
            total_tables = len(tables)
            
            if response_type == "list_tables":
                # Respuesta directa: Lista de tablas disponibles
                table_names = [table.get('name', '') for table in tables if table.get('name')]
                table_names = [name for name in table_names if name]  # Filtrar nombres vacíos
                
                response = {
                    "type": "direct_cache_response",
                    "response_type": "list_tables",
                    "content": f"Tu base de datos tiene {total_tables} tablas disponibles:\n\n" + \
                              "\n".join([f"• {name}" for name in sorted(table_names)]),
                    "metadata": {
                        "total_tables": total_tables,
                        "source": "cache",
                        "response_time_ms": 0,  # Respuesta instantánea
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            elif response_type == "explore_schema":
                # Respuesta directa: Exploración del esquema
                table_summary = []
                for table in tables[:20]:  # Limitar a 20 tablas para respuesta rápida
                    name = table.get('name', '')
                    columns = table.get('columns', [])
                    column_count = len(columns)
                    
                    # Identificar columnas clave
                    id_columns = [col.get('name', '') for col in columns if 'id' in col.get('name', '').lower()]
                    primary_keys = [col.get('name', '') for col in columns if col.get('is_primary_key')]
                    
                    summary = f"• **{name}** ({column_count} columnas)"
                    if primary_keys:
                        summary += f" - PK: {', '.join(primary_keys)}"
                    if id_columns:
                        summary += f" - IDs: {', '.join(id_columns[:3])}"
                    
                    table_summary.append(summary)
                
                response = {
                    "type": "direct_cache_response",
                    "response_type": "explore_schema",
                    "content": f"**Esquema de tu base de datos** ({total_tables} tablas):\n\n" + \
                              "\n".join(table_summary) + \
                              f"\n\n*Mostrando primeras 20 tablas. Total: {total_tables} tablas disponibles.*",
                    "metadata": {
                        "total_tables": total_tables,
                        "tables_shown": min(20, total_tables),
                        "source": "cache",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            elif response_type == "table_stats":
                # Respuesta directa: Estadísticas básicas
                table_types = {}
                total_columns = 0
                
                for table in tables:
                    table_type = table.get('type', 'unknown')
                    table_types[table_type] = table_types.get(table_type, 0) + 1
                    total_columns += len(table.get('columns', []))
                
                stats_content = f"**Estadísticas de tu base de datos:**\n\n" + \
                               f"• **Total de tablas:** {total_tables}\n" + \
                               f"• **Total de columnas:** {total_columns}\n" + \
                               f"• **Promedio de columnas por tabla:** {total_columns/total_tables:.1f}\n\n" + \
                               f"• **Tipos de tablas:**\n"
                
                for table_type, count in sorted(table_types.items()):
                    stats_content += f"• {table_type}: {count} tablas\n"
                
                response = {
                    "type": "direct_cache_response",
                    "response_type": "table_stats",
                    "content": stats_content,
                    "metadata": {
                        "total_tables": total_tables,
                        "total_columns": total_columns,
                        "table_types": table_types,
                        "source": "cache",
                        "response_type": "table_stats",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            elif response_type == "find_specific_tables":
                # Respuesta directa: Búsqueda específica (equivalente a list_tables)
                table_names = [table.get('name', '') for table in tables if table.get('name')]
                table_names = [name for name in table_names if name]  # Filtrar nombres vacíos
                
                response = {
                    "type": "direct_cache_response",
                    "response_type": "find_specific_tables",
                    "content": f"**Tablas disponibles en tu base de datos:**\n\n" + \
                              "\n".join([f"• {name}" for name in sorted(table_names)]) + \
                              f"\n\n*Total: {total_tables} tablas disponibles para explorar.*",
                    "metadata": {
                        "total_tables": total_tables,
                        "source": "cache",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            elif response_type == "explore_table_structure":
                # Respuesta directa: Explorar estructura de tablas
                table_summary = []
                for table in tables[:15]:  # Limitar a 15 tablas para respuesta rápida
                    name = table.get('name', '')
                    columns = table.get('columns', [])
                    column_count = len(columns)
                    
                    # Identificar columnas clave
                    id_columns = [col.get('name', '') for col in columns if 'id' in col.get('name', '').lower()]
                    primary_keys = [col.get('name', '') for col in columns if col.get('is_primary_key')]
                    
                    summary = f"• **{name}** ({column_count} columnas)"
                    if primary_keys:
                        summary += f" - PK: {', '.join(primary_keys)}"
                    if id_columns:
                        summary += f" - IDs: {', '.join(id_columns[:3])}"
                    
                    table_summary.append(summary)
                
                response = {
                    "type": "direct_cache_response",
                    "response_type": "explore_table_structure",
                    "content": f"**Estructura de tu base de datos** ({total_tables} tablas):\n\n" + \
                              "\n".join(table_summary) + \
                              f"\n\n*Mostrando primeras 15 tablas. Total: {total_tables} tablas disponibles.*",
                    "metadata": {
                        "total_tables": total_tables,
                        "tables_shown": min(15, total_tables),
                        "source": "cache",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            elif response_type == "find_relationships":
                # Respuesta directa: Información sobre relaciones
                response = {
                    "type": "direct_cache_response",
                    "response_type": "find_relationships",
                    "content": f"**Información sobre relaciones en tu base de datos:**\n\n" + \
                              f"Tu base de datos tiene {total_tables} tablas. Para explorar las relaciones entre ellas, " + \
                              f"puedes usar consultas específicas sobre claves foráneas y restricciones.\n\n" + \
                              f"**Tablas disponibles para análisis de relaciones:**\n" + \
                              "\n".join([f"• {table.get('name', '')}" for table in tables[:10]]) + \
                              f"\n\n*Total: {total_tables} tablas. Usa consultas específicas para explorar relaciones.*",
                    "metadata": {
                        "total_tables": total_tables,
                        "tables_shown": min(10, total_tables),
                        "source": "cache",
                        "response_time_ms": 0,
                        "no_llm_required": True,
                        "cache_hit": True
                    },
                    "safe": True,
                    "source": "direct_cache"
                }
                
            else:
                logger.warning(f"[SchemaExplorerService] ⚠️ Tipo de respuesta no soportado: {response_type}")
                return None
            
            logger.info(f"[SchemaExplorerService] 🚀 Respuesta directa desde caché generada: {response_type}")
            return response
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error generando respuesta directa desde caché: {e}")
            # Fallback a consulta SQL si hay error
            return self._generate_safe_table_list_query(db_ids)

    def _get_schema_from_cache(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el esquema desde caché si está disponible.
        """
        try:
            # 🚀 OPTIMIZACIÓN: Usar el esquema que ya tenemos en el índice léxico
            if db_id in self._lexical_indexes:
                lexical_data = self._lexical_indexes[db_id]
                if 'tables' in lexical_data:
                    logger.info(f"[SchemaExplorerService] ✅ Esquema obtenido desde índice léxico para DB {db_id}")
                    return {
                        'tables': lexical_data['tables'],
                        'source': 'lexical_index',
                        'total_tables': len(lexical_data['tables'])
                    }
            
            # Fallback: Intentar obtener desde caché L1 (memoria)
            cache_key = f"schema:{db_id}"
            cached_schema = self.cache_service.get(cache_key)
            
            if cached_schema:
                logger.info(f"[SchemaExplorerService] ✅ Esquema obtenido desde caché L1 para DB {db_id}")
                return cached_schema
            
            # Si no está en caché L1, intentar obtener desde DetailedSchemaCache
            # (esto ya se hace en el método principal, pero por si acaso)
            logger.info(f"[SchemaExplorerService] ⚠️ Esquema no encontrado en caché L1 para DB {db_id}")
            return None
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error obteniendo esquema desde caché: {e}")
            return None
    
    async def get_compact_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene esquema compacto para optimización de tokens.
        Wrapper para compatibilidad con ContextLoader.
        """
        try:
            # 🔧 FIX: Usar DetailedSchemaCacheService para obtener schema real
            if self.factory and hasattr(self.factory, 'get_detailed_schema_cache_service'):
                try:
                    detailed_cache_service = self.factory.get_detailed_schema_cache_service()
                    if detailed_cache_service and hasattr(self.factory, 'user') and self.factory.user:
                        # Intentar obtener schema desde cache detallado
                        schema_response = await detailed_cache_service.get_schema_cache(self.factory.user.id, db_id)
                        if schema_response and schema_response.compact:
                            logger.info(f"[SchemaExplorerService] ✅ Schema compacto obtenido desde DetailedSchemaCache para DB {db_id}")
                            # Devolver el schema compacto real
                            return {
                                "db_id": str(db_id),
                                "compact": schema_response.compact,
                                "table_count": getattr(schema_response, 'table_count', 0),
                                "generated_at": getattr(schema_response, 'generated_at', datetime.now().isoformat()),
                                "type": "compact_from_cache"
                            }
                        else:
                            logger.warning(f"[SchemaExplorerService] ⚠️ No hay schema en DetailedSchemaCache para DB {db_id}")
                    else:
                        logger.warning(f"[SchemaExplorerService] ⚠️ DetailedSchemaCacheService o user no disponible")
                except Exception as e:
                    logger.warning(f"[SchemaExplorerService] ⚠️ Error obteniendo schema desde DetailedSchemaCache: {e}")
            else:
                logger.debug(f"[SchemaExplorerService] ℹ️ ServiceFactory no disponible, usando fallback local")
            
            # 🔧 FALLBACK: Si no hay schema en cache detallado, usar cache local
            cache_service = self.cache_service
            cache_key = f"compact_schema_{db_id}"
            
            # Intentar obtener desde cache local
            cached_schema = cache_service.get(cache_key)
            if cached_schema:
                logger.debug(f"[SchemaExplorerService] Esquema compacto obtenido desde cache local para DB {db_id}")
                return cached_schema
            
            # 🔧 FALLBACK: Si no hay cache, generar esquema mínimo
            logger.warning(f"[SchemaExplorerService] ⚠️ Generando esquema mínimo para DB {db_id} (no hay cache)")
            compact_schema = {
                "db_id": str(db_id),
                "compact": f"Database {db_id[:8]} - Schema no disponible en cache",
                "tables": [],
                "generated_at": datetime.now().isoformat(),
                "type": "compact_minimal"
            }
            
            # Guardar en cache local
            cache_service.set(cache_key, compact_schema, ttl=3600)  # 1 hora
            
            logger.debug(f"[SchemaExplorerService] Esquema mínimo generado para DB {db_id}")
            return compact_schema
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] Error obteniendo esquema compacto para DB {db_id}: {e}")
            return None
    
    def _normalize_query(self, query: str) -> str:
        """
        🔧 FASE 1: Normalizar query para búsqueda léxica multilenguaje y genérica.
        """
        try:
            # Convertir a minúsculas y remover caracteres especiales
            normalized = query.lower()
            normalized = re.sub(r'[^\w\s]', ' ', normalized)
            normalized = re.sub(r'\s+', ' ', normalized).strip()
            
            # 🔧 FASE 8: Detección de idioma y normalización usando el servicio de sinónimos
            # Detectar si es español basado en palabras comunes
            spanish_indicators = ['qué', 'dónde', 'cuándo', 'cómo', 'cuánto', 'cuánta', 'tabla', 'tablas', 'esquema', 'campo', 'campos']
            is_spanish = any(indicator in normalized for indicator in spanish_indicators)
            
            if is_spanish:
                # Usar el servicio de sinónimos para traducciones español-inglés
                try:
                    for word in normalized.split():
                        translation = self.synonyms_service.get_translation(word, "es", "en")
                        if translation:
                            normalized = normalized.replace(word, translation)
                    
                    logger.debug(f"[SchemaExplorerService] 🔧 FASE 8: Query normalizada usando servicio de sinónimos: '{query}' -> '{normalized}'")
                except Exception as e:
                    logger.warning(f"[SchemaExplorerService] ⚠️ Error en traducción automática: {e}")
                    # Fallback a traducciones básicas si falla el servicio
                    basic_translations = {
                        'tabla': 'table', 'tablas': 'tables', 'esquema': 'schema',
                        'campo': 'field', 'campos': 'fields', 'columna': 'column',
                        'columnas': 'columns', 'registro': 'record', 'registros': 'records'
                    }
                    for spanish, english in basic_translations.items():
                        normalized = normalized.replace(spanish, english)
            
            return normalized
            
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error en normalización de query: {e}, usando query original")
            return query.lower()
    
    def _extract_search_terms(self, normalized_query: str) -> List[str]:
        """
        🔧 FASE 1: Extrae términos de búsqueda relevantes de la query normalizada.
        Mejorado para ser multilenguaje y genérico.
        """
        try:
            # 🔧 FASE 8: Palabras comunes a filtrar usando el servicio de sinónimos
            try:
                # Obtener palabras comunes desde el servicio de sinónimos
                common_words = set()
                
                # Añadir palabras básicas que siempre se filtran
                basic_common = {
                    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero',
                    'en', 'sobre', 'a', 'para', 'con', 'sin', 'por', 'entre'
                }
                common_words.update(basic_common)
                
                # Añadir palabras comunes de sinónimos (solo las que son muy genéricas)
                generic_synonyms = ['donde', 'esta', 'estan', 'buscar', 'busco', 'quiero', 'necesito', 'puedo',
                                   'ver', 'mostrar', 'listar', 'obtener', 'traer', 'extraer',
                                   'encontrar', 'localizar', 'ubicar', 'situar', 'posicionar']
                common_words.update(generic_synonyms)
                
            except Exception as e:
                logger.warning(f"[SchemaExplorerService] ⚠️ Error obteniendo palabras comunes: {e}")
                # Fallback a lista básica
                common_words = {
                    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero',
                    'en', 'sobre', 'a', 'para', 'con', 'sin', 'por', 'entre'
                }
            
            # Filtrar palabras comunes y muy cortas
            words = normalized_query.split()
            terms = [word for word in words if len(word) >= 3 and word not in common_words]
            
            # 🔧 FASE 1: Si no hay términos específicos, usar palabras más largas
            if not terms:
                terms = [word for word in words if len(word) >= 4]
            
            # 🔧 FASE 1: Añadir términos relacionados si la query es muy corta
            if len(terms) < 2 and len(normalized_query) > 10:
                # Buscar palabras clave que podrían estar relacionadas
                for word in words:
                    if len(word) >= 4 and word not in terms and word not in common_words:
                        terms.append(word)
                        break
            
            # 🔧 FASE 1: Asegurar que tenemos al menos algunos términos útiles
            if not terms and len(normalized_query) > 5:
                # Usar palabras más largas incluso si son comunes
                terms = [word for word in words if len(word) >= 4][:3]
            
            logger.debug(f"[SchemaExplorerService] 🔧 FASE 1: Términos extraídos: {terms}")
            return terms[:5]  # Máximo 5 términos
            
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error extrayendo términos de búsqueda: {e}")
            # Fallback: usar palabras básicas
            words = normalized_query.split()
            return [word for word in words if len(word) >= 3][:3]
    
    async def _build_lexical_index(self, db_id: UUID) -> None:
        """Construye índice léxico para una base de datos específica"""
        try:
            if db_id in self._lexical_indexes:
                logger.debug(f"[SchemaExplorerService] ✅ Índice léxico ya existe para DB {db_id}")
                return
            
            logger.info(f"[SchemaExplorerService] 🔨 Construyendo índice léxico para DB {db_id}")
            
            # 🔧 FIX: Usar DetailedSchemaCacheService en lugar de intentar construir desde cero
            if self.factory and hasattr(self.factory, 'get_detailed_schema_cache_service'):
                try:
                    detailed_cache_service = self.factory.get_detailed_schema_cache_service()
                    if detailed_cache_service and hasattr(self.factory, 'user') and self.factory.user:
                        # Intentar obtener schema desde cache detallado
                        schema_response = await detailed_cache_service.get_schema_cache(self.factory.user.id, db_id)
                        if schema_response and schema_response.compact:
                            logger.info(f"[SchemaExplorerService] ✅ Schema obtenido desde DetailedSchemaCache para DB {db_id}")
                            # Construir índice desde el schema en cache
                            self._build_index_from_schema(db_id, schema_response)
                            return
                        else:
                            logger.warning(f"[SchemaExplorerService] ⚠️ No hay schema en DetailedSchemaCache para DB {db_id}")
                    else:
                        logger.warning(f"[SchemaExplorerService] ⚠️ DetailedSchemaCacheService o user no disponible")
                except Exception as e:
                    logger.warning(f"[SchemaExplorerService] ⚠️ Error obteniendo schema desde DetailedSchemaCache: {e}")
            else:
                logger.debug(f"[SchemaExplorerService] ℹ️ ServiceFactory no disponible, usando fallback local")
            
            # 🔧 FALLBACK: Si no hay schema en cache, crear índice mínimo
            logger.info(f"[SchemaExplorerService] 🔄 Creando índice mínimo para DB {db_id}")
            self._lexical_indexes[db_id] = {}
            
            # Crear índice básico con términos comunes
            basic_terms = ["table", "column", "field", "data", "record", "row"]
            for term in basic_terms:
                self._index_term(db_id, term, "general", "fallback", 0.5)
            
            logger.info(f"[SchemaExplorerService] ✅ Índice mínimo creado para DB {db_id}")
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error construyendo índice léxico para DB {db_id}: {e}")
            # Crear índice vacío para evitar errores futuros
            self._lexical_indexes[db_id] = {}
    
    def _build_index_from_schema(self, db_id: UUID, schema_response) -> None:
        """Construye índice léxico desde un schema en cache"""
        try:
            self._lexical_indexes[db_id] = {}
            
            # Extraer información del schema
            if hasattr(schema_response, 'snapshot') and schema_response.snapshot:
                snapshot = schema_response.snapshot
                if isinstance(snapshot, dict):
                    tables = snapshot.get('tables', {})
                else:
                    # Si snapshot es un objeto, intentar acceder a sus atributos
                    tables = getattr(snapshot, 'tables', {})
                    if not tables:
                        tables = {}
            else:
                tables = {}
            
            # 🔧 FASE 8: Indexar tablas con score alto
            for table_name, table_info in tables.items():
                if isinstance(table_info, dict):
                    # Indexar nombre de tabla con score alto
                    self._index_term(db_id, table_name, table_name, "table", 1.0)
                    
                    # 🔧 FASE 8: Indexar columnas con score alto
                    columns = table_info.get('columns', {})
                    for col_name, col_info in columns.items():
                        if isinstance(col_info, dict):
                            # Indexar nombre de columna con score alto
                            self._index_term(db_id, col_name, table_name, "column", 0.9)
                            
                            # 🔧 FASE 8: Indexar tipo de columna con score medio
                            col_type = col_info.get('type', '')
                            if col_type:
                                self._index_term(db_id, str(col_type), table_name, "semantic_type", 0.7)
                            
                            # 🔧 FASE 8: Indexar comentarios/descripciones con score medio
                            col_description = col_info.get('description', '')
                            if col_description:
                                # Indexar palabras individuales de la descripción
                                desc_words = col_description.split()
                                for word in desc_words:
                                    if len(word) >= 3:  # Solo palabras de 3+ caracteres
                                        self._index_term(db_id, word, table_name, "description", 0.6)
                            
                            # 🔧 FASE 8: Indexar constraints si están disponibles
                            if col_info.get('primary_key'):
                                self._index_term(db_id, 'primary_key', table_name, "constraint", 0.8)
                            if col_info.get('foreign_key'):
                                self._index_term(db_id, 'foreign_key', table_name, "constraint", 0.8)
                            if col_info.get('unique'):
                                self._index_term(db_id, 'unique', table_name, "constraint", 0.7)
                            if col_info.get('not_null'):
                                self._index_term(db_id, 'not_null', table_name, "constraint", 0.6)
            
            # 🔧 FASE 8: Indexar metadatos de la base de datos
            if hasattr(schema_response, 'table_count'):
                self._index_term(db_id, f"{schema_response.table_count}_tables", "metadata", "count", 0.5)
            if hasattr(schema_response, 'total_columns'):
                self._index_term(db_id, f"{schema_response.total_columns}_columns", "metadata", "count", 0.5)
            
            logger.info(f"[SchemaExplorerService] ✅ FASE 8: Índice léxico construido para DB {db_id} con {len(tables)} tablas")
            
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error construyendo índice desde schema: {e}")
            # Crear índice vacío para evitar errores futuros
            self._lexical_indexes[db_id] = {}
    
    def _index_term(self, db_id: UUID, term: str, table: str, term_type: str, base_score: float) -> None:
        """
        Indexa un término en el índice léxico con sinónimos y términos relacionados.
        Mejorado para Fase 8 con indexación más inteligente.
        """
        try:
            if db_id not in self._lexical_indexes:
                self._lexical_indexes[db_id] = {}
            
            # 🔧 FASE 8: Indexar término principal
            term_key = term.lower().strip()
            if term_key not in self._lexical_indexes[db_id]:
                self._lexical_indexes[db_id][term_key] = []
            
            # Añadir entrada principal
            entry = {
                'term': term,
                'table': table,
                'term_type': term_type,
                'score': base_score,
                'db_id': str(db_id)
            }
            
            # Evitar duplicados
            if not any(e['table'] == table and e['term_type'] == term_type for e in self._lexical_indexes[db_id][term_key]):
                self._lexical_indexes[db_id][term_key].append(entry)
            
            # 🔧 FASE 8: Indexar sinónimos automáticamente
            synonyms = self._get_synonyms(term)
            for synonym in synonyms:
                if synonym != term_key:
                    if synonym not in self._lexical_indexes[db_id]:
                        self._lexical_indexes[db_id][synonym] = []
                    
                    # Añadir sinónimo con score ligeramente menor
                    synonym_entry = entry.copy()
                    synonym_entry['term'] = synonym
                    synonym_entry['score'] = base_score * 0.8  # Score reducido para sinónimos
                    
                    if not any(e['table'] == table and e['term_type'] == term_type for e in self._lexical_indexes[db_id][synonym]):
                        self._lexical_indexes[db_id][synonym].append(synonym_entry)
            
            # 🔧 FASE 8: Indexar términos relacionados
            related_terms = self._get_related_terms(term, term_type)
            for related_term in related_terms:
                if related_term not in self._lexical_indexes[db_id]:
                    self._lexical_indexes[db_id][related_term] = []
                
                # Añadir término relacionado con score menor
                related_entry = entry.copy()
                related_entry['term'] = related_term
                related_entry['score'] = base_score * 0.6  # Score reducido para términos relacionados
                
                if not any(e['table'] == table and e['term_type'] == term_type for e in self._lexical_indexes[db_id][related_term]):
                    self._lexical_indexes[db_id][related_term].append(related_entry)
                    
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error indexando término '{term}': {e}")
    
    def _get_synonyms(self, term: str) -> List[str]:
        """
        🔧 FASE 8: Obtener sinónimos de un término usando el servicio de configuración.
        """
        try:
            # Usar el servicio de sinónimos para obtener todos los sinónimos disponibles
            all_synonyms = self.synonyms_service.get_all_synonyms_for_term(term)
            
            if all_synonyms:
                logger.debug(f"[SchemaExplorerService] 🔧 FASE 8: Encontrados {len(all_synonyms)} sinónimos para '{term}': {all_synonyms}")
                return all_synonyms
            else:
                logger.debug(f"[SchemaExplorerService] 🔧 FASE 8: No se encontraron sinónimos para '{term}'")
                return []
                
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error obteniendo sinónimos para '{term}': {e}")
            return []
    
    def _get_related_terms(self, term: str, term_type: str) -> List[str]:
        """
        🔧 FASE 8: Obtener términos relacionados de un término usando el servicio de configuración.
        """
        try:
            # Usar el servicio de sinónimos para obtener términos relacionados
            # Buscar en sinónimos de tablas y campos
            table_synonyms = self.synonyms_service.get_table_synonyms(term)
            field_synonyms = self.synonyms_service.get_field_synonyms(term)
            
            # Combinar y remover duplicados
            all_related = list(set(table_synonyms + field_synonyms))
            
            if all_related:
                logger.debug(f"[SchemaExplorerService] 🔧 FASE 8: Encontrados {len(all_related)} términos relacionados para '{term}': {all_related}")
                return all_related
            else:
                logger.debug(f"[SchemaExplorerService] 🔧 FASE 8: No se encontraron términos relacionados para '{term}'")
                return []
                
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error obteniendo términos relacionados para '{term}': {e}")
            return []
    
    def _generate_trigrams(self, text: str) -> List[str]:
        """Generar trigrams para búsqueda fuzzy"""
        if len(text) < 3:
            return [text]
        
        trigrams = []
        for i in range(len(text) - 2):
            trigrams.append(text[i:i+3])
        
        return trigrams
    
    def _search_lexical_index(self, db_id: UUID, query_terms: List[str]) -> List[Dict[str, Any]]:
        """Buscar términos en el índice léxico"""
        if db_id not in self._lexical_indexes:
            return []
        
        matches = []
        
        for term in query_terms:
            # Generar trigrams del término de búsqueda
            term_trigrams = self._generate_trigrams(term)
            
            for trigram in term_trigrams:
                if trigram in self._lexical_indexes[db_id]:
                    # Añadir todos los matches para este trigram
                    for entry in self._lexical_indexes[db_id][trigram]:
                        # Calcular score de match
                        match_score = self._calculate_match_score(term, entry)
                        if match_score > 0:
                            match_entry = entry.copy()
                            match_entry['score'] = match_score
                            match_entry['db_id'] = db_id
                            matches.append(match_entry)
        
        # Remover duplicados y ordenar por score
        unique_matches = {}
        for match in matches:
            key = (match['table'], match.get('column'), match['db_id'])
            if key not in unique_matches or match['score'] > unique_matches[key]['score']:
                unique_matches[key] = match
        
        # Ordenar por score descendente
        sorted_matches = sorted(unique_matches.values(), key=lambda x: x['score'], reverse=True)
        
        return sorted_matches[:10]  # Top 10 matches
    
    def _calculate_match_score(self, query_term: str, index_entry: Dict[str, Any]) -> float:
        """Calcular score de match entre término de búsqueda y entrada del índice"""
        original_term = index_entry['original_term'].lower()
        base_score = index_entry['score']
        
        # Score por tipo de término
        type_bonus = {
            "table": 1.0,
            "column": 0.9,
            "semantic_type": 0.7,
            "description": 0.6
        }
        
        type_score = type_bonus.get(index_entry['term_type'], 0.5)
        
        # Score por exactitud del match
        if query_term == original_term:
            exact_match = 1.0
        elif query_term in original_term:
            exact_match = 0.8
        elif original_term in query_term:
            exact_match = 0.7
        else:
            # Búsqueda fuzzy con trigrams
            query_trigrams = set(self._generate_trigrams(query_term))
            entry_trigrams = set(self._generate_trigrams(original_term))
            
            if query_trigrams and entry_trigrams:
                intersection = len(query_trigrams & entry_trigrams)
                union = len(query_trigrams | entry_trigrams)
                exact_match = intersection / union if union > 0 else 0.0
            else:
                exact_match = 0.0
        
        # Score final combinado
        final_score = base_score * type_score * exact_match
        return min(final_score, 1.0)
    
    def _format_fast_response(self, matches: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
        """Formatear respuesta rápida para alta confianza"""
        # Agrupar por tabla
        tables = {}
        for match in matches:
            table_name = match['table']
            if table_name not in tables:
                tables[table_name] = {
                    'name': table_name,
                    'db_id': match['db_id'],
                    'columns': [],
                    'score': 0.0
                }
            
            if match.get('column') and match['column'] != table_name:
                tables[table_name]['columns'].append({
                    'name': match['column'],
                    'type': match['term_type'],
                    'score': match['score']
                })
            
            tables[table_name]['score'] = max(tables[table_name]['score'], match['score'])
        
        # Ordenar tablas por score
        sorted_tables = sorted(tables.values(), key=lambda x: x['score'], reverse=True)
        
        return {
            'type': 'fast_schema_lookup',
            'confidence': confidence,
            'response_time_ms': self.FAST_PATH_RESPONSE_TIME_MS,  # Usar configuración
            'tables': sorted_tables[:5],  # Top 5 tablas
            'total_matches': len(matches),
            'message': f"Encontré {len(sorted_tables)} tablas relevantes con confianza {confidence:.1%}"
        }
    
    def _format_ambiguous_response(self, matches: List[Dict[str, Any]], confidence: float) -> Dict[str, Any]:
        """Formatear respuesta para confianza ambigua (requiere desambiguación)"""
        # Similar a fast_response pero con mensaje de desambiguación
        fast_response = self._format_fast_response(matches, confidence)
        fast_response['type'] = 'ambiguous_schema_lookup'
        fast_response['message'] = f"Encontré {len(fast_response['tables'])} posibles coincidencias. ¿Podrías ser más específico?"
        fast_response['requires_disambiguation'] = True
        
        return fast_response
    
    def get_schema_for_user_dbs(
        self, 
        user_id: UUID, 
        db_ids: List[UUID]
    ) -> Dict[UUID, List[Dict[str, Any]]]:
        """
        Obtener esquemas para las bases de datos de un usuario.
        Combina cache y exploración en tiempo real.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos
            
        Returns:
            Diccionario con esquemas: {db_id: [tables]}
        """
        if not db_ids:
            logger.info("[SchemaExplorerService] 📭 No hay bases de datos para explorar")
            return {}
        
        # 1. Intentar obtener desde cache detallado
        detailed_schemas = {}
        schemas_to_explore = []
        
        for db_id in db_ids:
            detailed_schema = self.detailed_cache.get_detailed_schema(db_id)
            if detailed_schema:
                detailed_schemas[db_id] = detailed_schema
                logger.info(f"[SchemaExplorerService] 🦄 Cache detallado hit: {db_id}")
            else:
                schemas_to_explore.append(db_id)
        
        # 2. Explorar las que no están cacheadas
        if schemas_to_explore:
            logger.info(f"[SchemaExplorerService] 🔍 Explorando {len(schemas_to_explore)} DBs en tiempo real")
            explored_schemas = self._explore_detailed_schemas(user_id, schemas_to_explore)
            
            # Combinar cache + exploración
            all_schemas = {**detailed_schemas, **explored_schemas}
        else:
            all_schemas = detailed_schemas
        
        logger.info(f"[SchemaExplorerService] ✅ Esquemas obtenidos: {len(all_schemas)}/{len(db_ids)} DBs")
        return all_schemas
    
    def get_schema_for_query(
        self, 
        user_id: UUID, 
        db_id: UUID, 
        user_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Obtener esquema optimizado para una query específica.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            user_query: Query del usuario
            
        Returns:
            Esquema optimizado para la query
        """
        return self.detailed_cache.get_schema_for_query(db_id, user_query)
    
    def _explore_detailed_schemas(
        self, 
        user_id: UUID, 
        db_ids: List[UUID]
    ) -> Dict[UUID, DatabaseSchema]:
        """
        Explorar esquemas detallados de bases de datos en tiempo real.
        
        Args:
            user_id: ID del usuario
            db_ids: Lista de IDs de bases de datos a explorar
            
        Returns:
            Diccionario con esquemas explorados: {db_id: DatabaseSchema}
        """
        explored_schemas = {}
        
        for db_id in db_ids:
            try:
                logger.info(f"[SchemaExplorerService] 🔍 Explorando DB detallado: {db_id}")
                schema = self._explore_single_db_detailed_schema(db_id)
                
                if schema:
                    # Cachear el esquema explorado
                    self.detailed_cache.cache_detailed_schema(db_id, schema)
                    explored_schemas[db_id] = schema
                    logger.info(f"[SchemaExplorerService] ✅ Explorado detallado: {len(schema.tables)} tablas en DB {db_id}")
                else:
                    logger.warning(f"[SchemaExplorerService] ⚠️ No se encontraron tablas en DB {db_id}")
                    
            except Exception as e:
                logger.error(f"[SchemaExplorerService] ❌ Error explorando DB {db_id}: {e}")
                # No cachear en caso de error
                continue
        
        return explored_schemas
    
    def _explore_single_db_detailed_schema(self, db_id: UUID) -> Optional[DatabaseSchema]:
        """
        Explorar esquema detallado de una base de datos específica.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Esquema detallado con información completa
        """
        try:
            # Obtener conexión SQL
            db_instance = self.database_service.get_sql_instance(db_id)
            
            # Crear metadata para reflection
            metadata = MetaData()
            metadata.reflect(bind=db_instance.engine)
            
            tables = {}
            relationships = {}
            
            # Obtener lista de tablas
            try:
                table_names = db_instance.get_usable_table_names()
            except AttributeError:
                table_names = db_instance.get_table_names()
            
            logger.info(f"[SchemaExplorerService] 📋 Encontradas {len(table_names)} tablas en DB {db_id}")
            
            for table_name in table_names:
                try:
                    # Explorar tabla detallada
                    table_info = self._explore_table_detailed(db_instance, table_name, metadata)
                    if table_info:
                        tables[table_name] = table_info
                        
                        # Explorar relaciones
                        relationships[table_name] = self._explore_table_relationships(table_name, metadata)
                        
                except Exception as e:
                    logger.warning(f"[SchemaExplorerService] ⚠️ Error explorando tabla {table_name}: {e}")
                    continue
            
            # Crear esquema detallado
            schema = DatabaseSchema(
                db_id=db_id,
                tables=tables,
                relationships=relationships,
                last_updated=datetime.now(),
                schema_hash=self._generate_schema_hash(tables),
                version="1.0"
            )
            
            logger.info(f"[SchemaExplorerService] 📊 Exploradas {len(tables)} tablas detalladas en DB {db_id}")
            return schema
            
        except SQLAlchemyError as e:
            logger.error(f"[SchemaExplorerService] ❌ Error de SQLAlchemy explorando DB {db_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error inesperado explorando DB {db_id}: {e}")
            raise
    
    def _explore_table_detailed(
        self, 
        db_instance, 
        table_name: str, 
        metadata: MetaData
    ) -> Optional[TableInfo]:
        """
        Explorar tabla con información detallada.
        
        Args:
            db_instance: Instancia de la base de datos
            table_name: Nombre de la tabla
            metadata: Metadata de SQLAlchemy
            
        Returns:
            Información detallada de la tabla
        """
        try:
            # Obtener información de la tabla desde metadata
            table = metadata.tables.get(table_name)
            if not table:
                return None
            
            columns = {}
            primary_keys = []
            foreign_keys = []
            indexes = []
            
            # Explorar columnas detalladas
            for column in table.columns:
                # Inferir tipo semántico
                semantic_type = self.detailed_cache._infer_semantic_type(column.name, str(column.type))
                
                # Información de foreign key
                foreign_key_info = None
                referenced_table = None
                referenced_column = None
                
                if column.foreign_keys:
                    fk = list(column.foreign_keys)[0]
                    foreign_key_info = f"{fk.column.table.name}.{fk.column.name}"
                    referenced_table = fk.column.table.name
                    referenced_column = fk.column.name
                
                # Crear información detallada de columna
                column_info = ColumnInfo(
                    name=column.name,
                    type=str(column.type),
                    nullable=column.nullable,
                    default=str(column.default) if column.default else None,
                    primary_key=column.primary_key,
                    unique=column.unique,
                    foreign_key=foreign_key_info,
                    referenced_table=referenced_table,
                    referenced_column=referenced_column,
                    semantic_type=semantic_type,
                    description=None
                )
                
                columns[column.name] = column_info
                
                # Recolectar primary keys
                if column.primary_key:
                    primary_keys.append(column.name)
                
                # Recolectar foreign keys
                if foreign_key_info:
                    foreign_keys.append({
                        "column": column.name,
                        "referenced_table": referenced_table,
                        "referenced_column": referenced_column
                    })
            
            # Explorar índices
            try:
                inspector = inspect(db_instance.engine)
                table_indexes = inspector.get_indexes(table_name)
                indexes = table_indexes
            except Exception as e:
                logger.debug(f"[SchemaExplorerService] ⚠️ No se pudieron obtener índices para {table_name}: {e}")
                indexes = []
            
            # Obtener row count (opcional)
            row_count = None
            try:
                result = db_instance.run(f"SELECT COUNT(*) FROM {table_name}")
                if result and isinstance(result, list) and len(result) > 0:
                    row_count = result[0].get('count', 0) if isinstance(result[0], dict) else result[0]
            except Exception as e:
                logger.debug(f"[SchemaExplorerService] ⚠️ No se pudo obtener row count para {table_name}: {e}")
            
            return TableInfo(
                name=table_name,
                columns=columns,
                primary_keys=primary_keys,
                foreign_keys=foreign_keys,
                indexes=indexes,
                row_count=row_count,
                description=None
            )
            
        except Exception as e:
            logger.warning(f"[SchemaExplorerService] ⚠️ Error explorando tabla detallada {table_name}: {e}")
            return None
    
    def _explore_table_relationships(self, table_name: str, metadata: MetaData) -> List[str]:
        """
        Explorar relaciones de una tabla.
        
        Args:
            table_name: Nombre de la tabla
            metadata: Metadata de SQLAlchemy
            
        Returns:
            Lista de tablas relacionadas
        """
        try:
            table = metadata.tables.get(table_name)
            if not table:
                return []
            
            related_tables = set()
            
            # Buscar tablas relacionadas por foreign keys
            for column in table.columns:
                if column.foreign_keys:
                    for fk in column.foreign_keys:
                        related_tables.add(fk.column.table.name)
            
            # Buscar tablas que referencian esta tabla
            for other_table in metadata.tables.values():
                for column in other_table.columns:
                    if column.foreign_keys:
                        for fk in column.foreign_keys:
                            if fk.column.table.name == table_name:
                                related_tables.add(other_table.name)
            
            return list(related_tables)
            
        except Exception as e:
            logger.debug(f"[SchemaExplorerService] ⚠️ Error explorando relaciones de {table_name}: {e}")
            return []
    
    def _generate_schema_hash(self, tables: Dict[str, TableInfo]) -> str:
        """Generar hash del esquema para detectar cambios"""
        import hashlib
        import json
        
        # Crear representación serializable de las tablas
        schema_data = {}
        for table_name, table_info in tables.items():
            schema_data[table_name] = {
                "columns": {col.name: str(col.type) for col in table_info.columns.values()},
                "primary_keys": table_info.primary_keys,
                "foreign_keys": table_info.foreign_keys
            }
        
        schema_str = json.dumps(schema_data, sort_keys=True, default=str)
        return hashlib.sha256(schema_str.encode()).hexdigest()
    
    def get_table_info(self, db_id: UUID, table_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información detallada de una tabla específica.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            
        Returns:
            Información detallada de la tabla o None si no existe
        """
        schema = self.detailed_cache.get_detailed_schema(db_id)
        if not schema:
            return None
        
        table_info = schema.tables.get(table_name)
        if not table_info:
            return None
        
        return {
            "name": table_info.name,
            "columns": {name: asdict(col) for name, col in table_info.columns.items()},
            "primary_keys": table_info.primary_keys,
            "foreign_keys": table_info.foreign_keys,
            "indexes": table_info.indexes,
            "row_count": table_info.row_count,
            "description": table_info.description
        }
    
    def validate_table_exists(self, db_id: UUID, table_name: str) -> bool:
        """
        Validar si una tabla existe en la base de datos.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            
        Returns:
            True si la tabla existe, False en caso contrario
        """
        schema = self.detailed_cache.get_detailed_schema(db_id)
        if not schema:
            return False
        
        return table_name in schema.tables
    
    def get_table_sample_data(self, db_id: UUID, table_name: str, limit: int = 5) -> Optional[List[Dict[str, Any]]]:
        """
        Obtener datos de muestra de una tabla.
        
        Args:
            db_id: ID de la base de datos
            table_name: Nombre de la tabla
            limit: Número máximo de filas a obtener
            
        Returns:
            Lista de filas de muestra o None si hay error
        """
        try:
            db_instance = self.database_service.get_sql_instance(db_id)
            
            # Query para obtener datos de muestra
            query = text(f"SELECT * FROM {table_name} LIMIT {limit}")
            result = db_instance.run(query)
            
            # Convertir a formato de diccionario
            if result and isinstance(result, list):
                return result
            else:
                return []
                
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error obteniendo datos de muestra de {table_name}: {e}")
            return None
    
    def refresh_schema_cache(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Forzar refresco del cache de esquema para una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            True si se refrescó correctamente, False en caso contrario
        """
        try:
            # Invalidar cache existente
            self.detailed_cache.invalidate_cache(db_id)
            
            # Explorar y cachear nuevo esquema
            schema = self._explore_single_db_detailed_schema(db_id)
            if schema:
                self.detailed_cache.cache_detailed_schema(db_id, schema)
                logger.info(f"[SchemaExplorerService] 🔄 Cache detallado refrescado: {len(schema.tables)} tablas en DB {db_id}")
                return True
            else:
                logger.warning(f"[SchemaExplorerService] ⚠️ No se pudieron explorar tablas en DB {db_id}")
                return False
                
        except Exception as e:
            logger.error(f"[SchemaExplorerService] ❌ Error refrescando cache para DB {db_id}: {e}")
            return False
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del cache detallado"""
        return self.detailed_cache.get_cache_stats()
