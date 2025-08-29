#!/usr/bin/env python3
"""
PlannerService - Servicio de planificación para la Fase 5
──────────────────────────────────────────────────────────
Implementa:
- Planificación usando el grafo para joins permitidos
- Tablas base, joins válidos, filtros, proyecciones
- Validación de relaciones permitidas
- Generación de plan ejecutable
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class PlannerService:
    """
    Servicio para crear planes de consulta usando el grafo de relaciones.
    
    Implementa la cuarta etapa de la Fase 5:
    - Planificación con el grafo
    - Joins permitidos
    - Filtros y proyecciones
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 5: Servicios necesarios
        self.graph_service = None
        self.schema_service = None
        
        # Intentar obtener servicios
        try:
            self.graph_service = factory.get_schema_graph_service()
        except:
            pass
            
        try:
            self.schema_service = factory.get_detailed_schema_cache_service()
        except:
            pass
    
    async def create_plan(
        self, 
        query: str, 
        context: Dict[str, Any], 
        grounding_result: Dict[str, Any], 
        intent_result: Any
    ) -> Dict[str, Any]:
        """
        Crea un plan de consulta usando el grafo de relaciones.
        
        Args:
            query: Consulta del usuario
            context: Contexto completo
            grounding_result: Resultado del grounding
            intent_result: Resultado de la clasificación de intención
            
        Returns:
            Plan de consulta con tablas, joins, filtros, etc.
        """
        try:
            start_time = time.time()
            self.logger.info(f"[PlannerService] 🧭 Creando plan para: '{query[:50]}...'")
            
            # 🔧 FASE 5: 1. Analizar la consulta para identificar entidades
            entities = await self._extract_entities(query, grounding_result)
            if not entities:
                return {
                    "status": "needs_clarification",
                    "message": "No se pudieron identificar entidades en la consulta",
                    "clarification_questions": [
                        "¿Qué tablas específicas quieres consultar?",
                        "¿Qué tipo de información buscas?"
                    ],
                    "missing_info": {
                        "tables": "No se identificaron tablas",
                        "columns": "No se identificaron columnas"
                    }
                }
            
            # 🔧 FASE 5: 2. Identificar tablas base
            base_tables = await self._identify_base_tables(entities, context)
            if not base_tables:
                return {
                    "status": "needs_clarification",
                    "message": "No se pudieron identificar las tablas base para la consulta",
                    "clarification_questions": [
                        "¿Podrías especificar qué tablas quieres consultar?",
                        "¿Hay algún nombre específico de tabla que deba usar?"
                    ],
                    "missing_info": {
                        "base_tables": "No se identificaron tablas base"
                    }
                }
            
            # 🔧 FASE 5: 3. Identificar joins necesarios
            joins = await self._identify_joins(base_tables, entities, context)
            
            # 🔧 FASE 5: 4. Identificar filtros
            filters = await self._identify_filters(query, entities, context)
            
            # 🔧 FASE 5: 5. Identificar proyecciones
            projections = await self._identify_projections(query, entities, context)
            
            # 🔧 FASE 5: 6. Identificar ordenamiento
            ordering = await self._identify_ordering(query, entities, context)
            
            # 🔧 FASE 5: 7. Construir plan completo
            plan = {
                "status": "ready",
                "query": query,
                "entities": entities,
                "base_tables": base_tables,
                "joins": joins,
                "filters": filters,
                "projections": projections,
                "ordering": ordering,
                "estimated_complexity": self._estimate_complexity(base_tables, joins),
                "execution_hints": self._generate_execution_hints(base_tables, joins),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "processing_time_ms": int((time.time() - start_time) * 1000)
            }
            
            self.logger.info(f"[PlannerService] ✅ Plan creado: {len(base_tables)} tablas, {len(joins)} joins en {plan['processing_time_ms']}ms")
            return plan
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error creando plan: {e}")
            return {
                "status": "error",
                "message": f"Error creando plan: {str(e)}",
                "error_details": str(e)
            }
    
    async def _extract_entities(self, query: str, grounding_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extrae entidades (tablas, columnas) de la consulta usando el grounding"""
        try:
            entities = []
            chunks = grounding_result.get('chunks', [])
            
            # 🔧 FASE 5: Procesar chunks del grounding
            for chunk in chunks:
                chunk_type = chunk.get('type', 'unknown')
                metadata = chunk.get('metadata', {})
                
                if chunk_type == 'table':
                    entities.append({
                        "type": "table",
                        "name": metadata.get('table_name', 'unknown'),
                        "info": metadata.get('table_info', {}),
                        "match_score": metadata.get('match_score', 0),
                        "match_type": metadata.get('match_type', 'unknown')
                    })
                elif chunk_type == 'column':
                    entities.append({
                        "type": "column",
                        "table": metadata.get('table_name', 'unknown'),
                        "name": metadata.get('column_name', 'unknown'),
                        "info": metadata.get('column_info', {}),
                        "match_score": metadata.get('match_score', 0),
                        "match_type": metadata.get('match_type', 'unknown')
                    })
                elif chunk_type == 'relationship':
                    entities.append({
                        "type": "relationship",
                        "name": metadata.get('relationship_info', {}).get('name', 'unknown'),
                        "info": metadata.get('relationship_info', {}),
                        "match_score": metadata.get('match_score', 0),
                        "match_type": metadata.get('match_type', 'unknown')
                    })
            
            # 🔧 FASE 5: Ordenar por score
            entities.sort(key=lambda x: x.get('match_score', 0), reverse=True)
            
            self.logger.info(f"[PlannerService] 🔍 Entidades extraídas: {len(entities)} entidades")
            return entities
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error extrayendo entidades: {e}")
            return []
    
    async def _identify_base_tables(self, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> List[str]:
        """Identifica las tablas base para la consulta"""
        try:
            base_tables = set()
            schema = context.get('schema', {})
            tables = schema.get('tables', {})
            
            # 🔧 FASE 5: Buscar tablas en entidades
            for entity in entities:
                if entity.get('type') == 'table':
                    table_name = entity.get('name')
                    if table_name in tables:
                        base_tables.add(table_name)
                elif entity.get('type') == 'column':
                    table_name = entity.get('table')
                    if table_name in tables:
                        base_tables.add(table_name)
                elif entity.get('type') == 'relationship':
                    rel_info = entity.get('info', {})
                    source_table = rel_info.get('source_table')
                    target_table = rel_info.get('target_table')
                    if source_table in tables:
                        base_tables.add(source_table)
                    if target_table in tables:
                        base_tables.add(target_table)
            
            # 🔧 FASE 5: Si no hay tablas específicas, usar tablas principales
            if not base_tables and tables:
                # Usar las primeras 3 tablas como base
                base_tables = set(list(tables.keys())[:3])
                self.logger.info(f"[PlannerService] ⚠️ No se identificaron tablas específicas, usando tablas principales: {list(base_tables)}")
            
            base_tables_list = list(base_tables)
            self.logger.info(f"[PlannerService] 🏗️ Tablas base identificadas: {base_tables_list}")
            return base_tables_list
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error identificando tablas base: {e}")
            return []
    
    async def _identify_joins(self, base_tables: List[str], entities: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identifica los joins necesarios entre las tablas base"""
        try:
            joins = []
            schema = context.get('schema', {})
            relationships = schema.get('relationships', [])
            
            # 🔧 FASE 5: Buscar relaciones entre tablas base
            for rel in relationships:
                source_table = rel.get('source_table')
                target_table = rel.get('target_table')
                
                if source_table in base_tables and target_table in base_tables:
                    join_info = {
                        "type": rel.get('type', 'FK'),
                        "source_table": source_table,
                        "target_table": target_table,
                        "source_column": rel.get('source_column'),
                        "target_column": rel.get('target_column'),
                        "relationship_name": rel.get('name', f"{source_table}_to_{target_table}"),
                        "cardinality": rel.get('cardinality', '1:N'),
                        "is_optional": rel.get('is_optional', True),
                        "join_type": "INNER" if not rel.get('is_optional', True) else "LEFT"
                    }
                    joins.append(join_info)
            
            # 🔧 FASE 5: Ordenar joins por prioridad
            joins.sort(key=lambda x: 0 if x['type'] == 'FK' else 1)
            
            self.logger.info(f"[PlannerService] 🔗 Joins identificados: {len(joins)} joins")
            return joins
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error identificando joins: {e}")
            return []
    
    async def _identify_filters(self, query: str, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identifica filtros potenciales en la consulta"""
        try:
            filters = []
            query_lower = query.lower()
            
            # 🔧 FASE 5: Buscar palabras clave de filtros
            filter_keywords = [
                'activo', 'active', 'activos', 'actives',
                'reciente', 'recent', 'último', 'last',
                'mayor', 'greater', 'menor', 'less',
                'igual', 'equal', 'diferente', 'different'
            ]
            
            for keyword in filter_keywords:
                if keyword in query_lower:
                    # Buscar columnas relacionadas en entidades
                    for entity in entities:
                        if entity.get('type') == 'column':
                            col_info = entity.get('info', {})
                            if any(filter_word in col_info.get('comment', '').lower() for filter_word in filter_keywords):
                                filters.append({
                                    "column": f"{entity['table']}.{entity['name']}",
                                    "table": entity['table'],
                                    "suggested_operator": "=",
                                    "suggested_value": "placeholder",
                                    "confidence": 0.7,
                                    "source": "keyword_match"
                                })
            
            self.logger.info(f"[PlannerService] 🔍 Filtros identificados: {len(filters)} filtros")
            return filters
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error identificando filtros: {e}")
            return []
    
    async def _identify_projections(self, query: str, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identifica las proyecciones (columnas a seleccionar)"""
        try:
            projections = []
            
            # 🔧 FASE 5: Buscar columnas específicas en entidades
            for entity in entities:
                if entity.get('type') == 'column':
                    projections.append({
                        "column": f"{entity['table']}.{entity['name']}",
                        "table": entity['table'],
                        "alias": entity['name'],
                        "type": entity['info'].get('data_type', 'unknown'),
                        "is_primary_key": entity['info'].get('is_primary_key', False),
                        "confidence": entity.get('match_score', 0.5)
                    })
            
            # 🔧 FASE 5: Si no hay columnas específicas, sugerir columnas principales
            if not projections:
                schema = context.get('schema', {})
                tables = schema.get('tables', {})
                
                for table_name in tables.keys():
                    table_info = tables[table_name]
                    columns = table_info.get('columns', {})
                    
                    # Agregar columnas principales (PK, nombres descriptivos)
                    for col_name, col_info in columns.items():
                        if col_info.get('is_primary_key') or 'name' in col_name.lower() or 'title' in col_name.lower():
                            projections.append({
                                "column": f"{table_name}.{col_name}",
                                "table": table_name,
                                "alias": col_name,
                                "type": col_info.get('data_type', 'unknown'),
                                "is_primary_key": col_info.get('is_primary_key', False),
                                "confidence": 0.6,
                                "suggested": True
                            })
            
            # 🔧 FASE 5: Limitar proyecciones
            projections = projections[:10]
            
            self.logger.info(f"[PlannerService] 📊 Proyecciones identificadas: {len(projections)} columnas")
            return projections
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error identificando proyecciones: {e}")
            return []
    
    async def _identify_ordering(self, query: str, entities: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Identifica el ordenamiento de la consulta"""
        try:
            query_lower = query.lower()
            
            # 🔧 FASE 5: Buscar palabras clave de ordenamiento
            order_keywords = {
                'ascendente': 'ASC',
                'ascending': 'ASC',
                'descendente': 'DESC',
                'descending': 'DESC',
                'más reciente': 'DESC',
                'most recent': 'DESC',
                'más antiguo': 'ASC',
                'oldest': 'ASC',
                'mayor': 'DESC',
                'greater': 'DESC',
                'menor': 'ASC',
                'less': 'ASC'
            }
            
            for keyword, direction in order_keywords.items():
                if keyword in query_lower:
                    # Buscar columna relacionada
                    for entity in entities:
                        if entity.get('type') == 'column':
                            col_info = entity.get('info', {})
                            if any(order_word in col_info.get('comment', '').lower() for order_word in order_keywords.keys()):
                                return {
                                    "column": f"{entity['table']}.{entity['name']}",
                                    "table": entity['table'],
                                    "direction": direction,
                                    "confidence": 0.8,
                                    "source": "keyword_match"
                                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"[PlannerService] ❌ Error identificando ordenamiento: {e}")
            return None
    
    def _estimate_complexity(self, base_tables: List[str], joins: List[Dict[str, Any]]) -> str:
        """Estima la complejidad del plan"""
        try:
            table_count = len(base_tables)
            join_count = len(joins)
            
            if table_count == 1 and join_count == 0:
                return "simple"
            elif table_count <= 3 and join_count <= 2:
                return "moderate"
            elif table_count <= 5 and join_count <= 4:
                return "complex"
            else:
                return "very_complex"
                
        except Exception as e:
            return "unknown"
    
    def _generate_execution_hints(self, base_tables: List[str], joins: List[Dict[str, Any]]) -> List[str]:
        """Genera hints para la ejecución"""
        try:
            hints = []
            
            if len(base_tables) > 1:
                hints.append("Considerar índices en columnas de join")
            
            if any(join.get('type') == 'M2M' for join in joins):
                hints.append("Joins M2M pueden ser costosos, verificar índices")
            
            if len(base_tables) > 3:
                hints.append("Considerar subconsultas para simplificar")
            
            return hints
            
        except Exception as e:
            return ["Error generando hints"]
