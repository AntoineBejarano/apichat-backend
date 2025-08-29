#!/usr/bin/env python3
"""
GroundingService - Servicio de grounding para la Fase 5
─────────────────────────────────────────────────────────
Implementa:
- Grounding structured: lookup directo en catálogo
- Grounding diffuse: embeddings top-k
- Selección automática del método
- Cache de resultados de grounding
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime, timezone

from app.utils.logger import logger


class GroundingService:
    """
    Servicio para realizar grounding de consultas usando diferentes métodos.
    
    Implementa la tercera etapa de la Fase 5:
    - Grounding structured vs diffuse
    - Cache de resultados
    - Selección automática del método
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.logger = logger
        
        # 🔧 FASE 5: Servicios necesarios
        self.vector_service = None
        self.schema_service = None
        self.embedding_service = None
        
        # Intentar obtener servicios
        try:
            self.vector_service = factory.get_vector_service()
        except:
            pass
            
        try:
            self.schema_service = factory.get_detailed_schema_cache_service()
        except:
            pass
            
        try:
            self.embedding_service = factory.get_embedding_service()
        except:
            pass
    
    async def structured_grounding(
        self, 
        query: str, 
        context: Dict[str, Any], 
        intent_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Grounding estructurado: lookup directo en catálogo.
        
        Args:
            query: Consulta del usuario
            context: Contexto completo
            intent_metadata: Metadatos de la intención
            
        Returns:
            Resultado del grounding estructurado
        """
        try:
            start_time = time.time()
            self.logger.info(f"[GroundingService] 🔍 Grounding estructurado para: '{query[:50]}...'")
            
            # 🔧 FASE 5: Extraer información del schema
            schema = context.get('schema', {})
            tables = schema.get('tables', {})
            relationships = schema.get('relationships', [])
            
            # 🔧 FASE 5: Buscar coincidencias exactas en nombres de tablas
            table_matches = []
            for table_name, table_info in tables.items():
                if self._text_matches(query.lower(), table_name.lower()):
                    table_matches.append({
                        "type": "table",
                        "name": table_name,
                        "info": table_info,
                        "match_score": 1.0,
                        "match_type": "exact_name"
                    })
                elif self._text_matches(query.lower(), table_info.get('comment', '').lower()):
                    table_matches.append({
                        "type": "table",
                        "name": table_name,
                        "info": table_info,
                        "match_score": 0.8,
                        "match_type": "comment_match"
                    })
            
            # 🔧 FASE 5: Buscar coincidencias en nombres de columnas
            column_matches = []
            for table_name, table_info in tables.items():
                columns = table_info.get('columns', {})
                for col_name, col_info in columns.items():
                    if self._text_matches(query.lower(), col_name.lower()):
                        column_matches.append({
                            "type": "column",
                            "table": table_name,
                            "name": col_name,
                            "info": col_info,
                            "match_score": 1.0,
                            "match_type": "exact_name"
                        })
                    elif self._text_matches(query.lower(), col_info.get('comment', '').lower()):
                        column_matches.append({
                            "type": "column",
                            "table": table_name,
                            "name": col_name,
                            "info": col_info,
                            "match_score": 0.8,
                            "match_type": "comment_match"
                        })
            
            # 🔧 FASE 5: Buscar coincidencias en relaciones
            relationship_matches = []
            for rel in relationships:
                if self._text_matches(query.lower(), rel.get('name', '').lower()):
                    relationship_matches.append({
                        "type": "relationship",
                        "info": rel,
                        "match_score": 1.0,
                        "match_type": "exact_name"
                    })
            
            # 🔧 FASE 5: Construir resultado
            chunks = []
            
            # Agregar tablas encontradas
            for match in table_matches:
                chunks.append({
                    "id": f"table_{match['name']}",
                    "type": "table",
                    "content": f"Tabla: {match['name']} - {match['info'].get('comment', 'Sin descripción')}",
                    "metadata": {
                        "table_name": match['name'],
                        "table_info": match['info'],
                        "match_score": match['match_score'],
                        "match_type": match['match_type']
                    }
                })
            
            # Agregar columnas encontradas
            for match in column_matches:
                chunks.append({
                    "id": f"column_{match['table']}_{match['name']}",
                    "type": "column",
                    "content": f"Columna: {match['table']}.{match['name']} ({match['info'].get('data_type', 'unknown')}) - {match['info'].get('comment', 'Sin descripción')}",
                    "metadata": {
                        "table_name": match['table'],
                        "column_name": match['name'],
                        "column_info": match['info'],
                        "match_score": match['match_score'],
                        "match_type": match['match_type']
                    }
                })
            
            # Agregar relaciones encontradas
            for match in relationship_matches:
                chunks.append({
                    "id": f"relationship_{match['info'].get('name', 'unknown')}",
                    "type": "relationship",
                    "content": f"Relación: {match['info'].get('name', 'Sin nombre')} - {match['info'].get('source_table')} → {match['info'].get('target_table')}",
                    "metadata": {
                        "relationship_info": match['info'],
                        "match_score": match['match_score'],
                        "match_type": match['match_type']
                    }
                })
            
            # 🔧 FASE 5: Ordenar por score y limitar
            chunks.sort(key=lambda x: x['metadata']['match_score'], reverse=True)
            chunks = chunks[:20]  # Limitar a 20 chunks
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                "method": "structured",
                "chunks": chunks,
                "total_chunks": len(chunks),
                "table_matches": len(table_matches),
                "column_matches": len(column_matches),
                "relationship_matches": len(relationship_matches),
                "processing_time_ms": processing_time,
                "grounding_summary": f"Encontrados {len(chunks)} chunks relevantes usando grounding estructurado"
            }
            
            self.logger.info(f"[GroundingService] ✅ Grounding estructurado completado: {len(chunks)} chunks en {processing_time}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"[GroundingService] ❌ Error en grounding estructurado: {e}")
            return {
                "method": "structured",
                "chunks": [],
                "total_chunks": 0,
                "error": str(e),
                "processing_time_ms": 0
            }
    
    async def diffuse_grounding(
        self, 
        query: str, 
        context: Dict[str, Any], 
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Grounding difuso: embeddings top-k.
        
        Args:
            query: Consulta del usuario
            context: Contexto completo
            top_k: Número de chunks a retornar
            
        Returns:
            Resultado del grounding difuso
        """
        try:
            start_time = time.time()
            self.logger.info(f"[GroundingService] 🔍 Grounding difuso para: '{query[:50]}...' (top_k={top_k})")
            
            # 🔧 FASE 5: Verificar que tenemos servicios necesarios
            if not self.vector_service or not self.embedding_service:
                self.logger.warning("[GroundingService] ⚠️ Servicios de vector/embedding no disponibles, fallback a structured")
                return await self.structured_grounding(query, context)
            
            # 🔧 FASE 5: Generar embedding de la consulta
            query_embedding = await self.embedding_service.generate_embedding(query)
            if not query_embedding:
                self.logger.warning("[GroundingService] ⚠️ No se pudo generar embedding, fallback a structured")
                return await self.structured_grounding(query, context)
            
            # 🔧 FASE 5: Buscar chunks similares
            namespace = f"user_{context.get('user_id')}_db_{context.get('db_id')}_snapshot_{context.get('snapshot_id')}"
            
            search_results = await self.vector_service.search_similar(
                query_embedding=query_embedding,
                namespace=namespace,
                top_k=top_k * 2,  # Buscar más para filtrar después
                min_score=0.3
            )
            
            # 🔧 FASE 5: Procesar y filtrar resultados
            chunks = []
            for result in search_results:
                if result.get('score', 0) >= 0.3:  # Filtrar por score mínimo
                    chunks.append({
                        "id": result.get('id', 'unknown'),
                        "type": result.get('metadata', {}).get('type', 'unknown'),
                        "content": result.get('content', ''),
                        "metadata": {
                            "score": result.get('score', 0),
                            "source": result.get('metadata', {}),
                            "match_type": "vector_similarity"
                        }
                    })
            
            # 🔧 FASE 5: Ordenar por score y limitar
            chunks.sort(key=lambda x: x['metadata']['score'], reverse=True)
            chunks = chunks[:top_k]
            
            processing_time = int((time.time() - start_time) * 1000)
            
            result = {
                "method": "diffuse",
                "chunks": chunks,
                "total_chunks": len(chunks),
                "query_embedding_generated": True,
                "vector_search_performed": True,
                "min_score_threshold": 0.3,
                "processing_time_ms": processing_time,
                "grounding_summary": f"Encontrados {len(chunks)} chunks relevantes usando grounding difuso (vector search)"
            }
            
            self.logger.info(f"[GroundingService] ✅ Grounding difuso completado: {len(chunks)} chunks en {processing_time}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"[GroundingService] ❌ Error en grounding difuso: {e}")
            # 🔧 FASE 5: Fallback a grounding estructurado
            self.logger.info("[GroundingService] 🔄 Fallback a grounding estructurado")
            return await self.structured_grounding(query, context)
    
    async def auto_grounding(
        self, 
        query: str, 
        context: Dict[str, Any], 
        intent_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Grounding automático: selecciona el método basado en la consulta.
        
        Args:
            query: Consulta del usuario
            context: Contexto completo
            intent_metadata: Metadatos de la intención
            
        Returns:
            Resultado del grounding automático
        """
        try:
            start_time = time.time()
            self.logger.info(f"[GroundingService] 🤖 Grounding automático para: '{query[:50]}...'")
            
            # 🔧 FASE 5: Determinar método basado en la consulta
            method = self._determine_grounding_method(query, intent_metadata)
            
            # 🔧 FASE 5: Ejecutar grounding con el método seleccionado
            if method == "structured":
                result = await self.structured_grounding(query, context, intent_metadata)
            elif method == "diffuse":
                result = await self.diffuse_grounding(query, context)
            else:
                # Método mixto: intentar structured primero, luego diffuse si no hay suficientes resultados
                result = await self.structured_grounding(query, context, intent_metadata)
                if result.get('total_chunks', 0) < 5:
                    self.logger.info("[GroundingService] 🔄 Pocos resultados en structured, complementando con diffuse")
                    diffuse_result = await self.diffuse_grounding(query, context)
                    # Combinar resultados
                    result['chunks'].extend(diffuse_result.get('chunks', [])[:5])
                    result['total_chunks'] = len(result['chunks'])
                    result['method'] = 'mixed'
                    result['grounding_summary'] += f" + {len(diffuse_result.get('chunks', [])[:5])} chunks de grounding difuso"
            
            # 🔧 FASE 5: Agregar información del método automático
            result['auto_method_selected'] = method
            result['auto_selection_reason'] = self._get_selection_reason(method, query, intent_metadata)
            
            processing_time = int((time.time() - start_time) * 1000)
            result['processing_time_ms'] = processing_time
            
            self.logger.info(f"[GroundingService] ✅ Grounding automático completado: método '{method}', {result.get('total_chunks', 0)} chunks en {processing_time}ms")
            return result
            
        except Exception as e:
            self.logger.error(f"[GroundingService] ❌ Error en grounding automático: {e}")
            # Fallback a structured
            return await self.structured_grounding(query, context)
    
    def _determine_grounding_method(self, query: str, intent_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Determina el método de grounding basado en la consulta y metadatos"""
        try:
            # 🔧 FASE 5: Si tenemos metadatos de intención, usarlos
            if intent_metadata:
                intent_type = intent_metadata.get('intent_type', 'unknown')
                confidence = intent_metadata.get('confidence_score', 0)
                
                if intent_type == "db_query" and confidence > 0.7:
                    return "structured"
                elif intent_type == "chat_general" or confidence < 0.5:
                    return "diffuse"
            
            # 🔧 FASE 5: Análisis de la consulta
            query_lower = query.lower()
            
            # Palabras clave que sugieren consulta estructurada
            structured_keywords = [
                'tabla', 'columnas', 'select', 'from', 'where', 'count', 'sum', 'avg',
                'table', 'columns', 'cuántos', 'cuántas', 'mostrar', 'obtener'
            ]
            
            # Palabras clave que sugieren consulta difusa
            diffuse_keywords = [
                'explica', 'describe', 'qué es', 'cómo funciona', 'ayuda',
                'explain', 'describe', 'what is', 'how does', 'help'
            ]
            
            # Contar coincidencias
            structured_count = sum(1 for keyword in structured_keywords if keyword in query_lower)
            diffuse_count = sum(1 for keyword in diffuse_keywords if keyword in query_lower)
            
            if structured_count > diffuse_count:
                return "structured"
            elif diffuse_count > structured_count:
                return "diffuse"
            else:
                return "mixed"
                
        except Exception as e:
            self.logger.warning(f"[GroundingService] ⚠️ Error determinando método: {e}")
            return "mixed"
    
    def _get_selection_reason(self, method: str, query: str, intent_metadata: Optional[Dict[str, Any]] = None) -> str:
        """Genera la razón de selección del método"""
        try:
            if method == "structured":
                return "Consulta específica con nombres de tablas/columnas detectados"
            elif method == "diffuse":
                return "Consulta general o conceptual que requiere búsqueda semántica"
            elif method == "mixed":
                return "Combinación de métodos para máxima cobertura"
            else:
                return "Método seleccionado automáticamente"
        except Exception as e:
            return f"Selección automática (error: {e})"
    
    def _text_matches(self, query: str, text: str) -> bool:
        """Verifica si hay coincidencia entre la consulta y el texto"""
        try:
            if not query or not text:
                return False
            
            # 🔧 FASE 5: Coincidencia exacta
            if query in text or text in query:
                return True
            
            # 🔧 FASE 5: Coincidencia de palabras
            query_words = set(query.split())
            text_words = set(text.split())
            
            if query_words.intersection(text_words):
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"[GroundingService] ⚠️ Error en text_matches: {e}")
            return False
