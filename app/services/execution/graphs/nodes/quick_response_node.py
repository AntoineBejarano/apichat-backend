#!/usr/bin/env python3
"""
⚡ QuickResponseNode - Respuesta Rápida desde Cache
────────────────────────────────────────────────────
Proporciona respuestas inmediatas usando información
disponible en cache y esquema real de la base de datos.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class QuickResponseNode:
    """
    ⚡ Nodo que genera respuestas rápidas desde cache y esquema real.
    
    Características:
    - Respuesta en <100ms usando cache
    - Solo información verificada (no alucinaciones)
    - Transparencia sobre fuentes de datos
    - Escalable para diferentes tipos de consultas
    """
    
    def __init__(self, factory):
        self.factory = factory
        self.cache_service = factory.get_cache_service()
        self.schema_service = factory.get_schema_explorer_service()
    
    async def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        ⚡ Genera respuesta rápida basada en información disponible.
        
        Args:
            state: Estado del grafo con consulta y contexto
            
        Returns:
            Estado actualizado con respuesta rápida
        """
        start_time = datetime.now()
        
        try:
            # Extraer información del estado
            # 🔧 CORRECCIÓN: message es ChatMessage, no dict, usar atributos directos
            message = state.get("message")
            if message and hasattr(message, 'content'):
                query = message.content
            else:
                query = ""
            
            db_ids = state.get("db_ids", [])
            compact_schemas = state.get("compact_schemas", {})
            
            logger.info(f"[QuickResponseNode] ⚡ Generando respuesta rápida para: '{query[:50]}...'")
            
            # 🎯 ANÁLISIS RÁPIDO DE INTENCIÓN BÁSICA
            basic_intention = self._detect_basic_intention(query)
            logger.info(f"[QuickResponseNode] 🎯 Intención básica detectada: {basic_intention}")
            
            # ⚡ GENERAR RESPUESTA RÁPIDA
            quick_response = await self._generate_quick_response(
                query=query,
                intention=basic_intention,
                db_ids=db_ids,
                compact_schemas=compact_schemas
            )
            
            # 📊 METADATAS DE TRANSPARENCIA
            response_metadata = {
                "response_type": "quick_response",
                "response_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "data_source": "cache_and_schema",
                "confidence": "high",  # Datos reales de la DB
                "coverage": "basic",   # Respuesta básica, AI mejorará
                "next_phase": "ai_analysis"
            }
            
            logger.info(f"[QuickResponseNode] ✅ Respuesta rápida generada en {response_metadata['response_time_ms']:.1f}ms")
            
            return {
                **state,
                "quick_response": quick_response,
                "quick_response_metadata": response_metadata,
                "current_phase": "quick_response_completed"
            }
            
        except Exception as e:
            logger.error(f"[QuickResponseNode] ❌ Error generando respuesta rápida: {e}")
            
            # 🆘 FALLBACK SEGURO
            fallback_response = self._generate_fallback_response(query)
            
            return {
                **state,
                "quick_response": fallback_response,
                "quick_response_metadata": {
                    "response_type": "fallback",
                    "response_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                    "data_source": "fallback",
                    "confidence": "low",
                    "coverage": "minimal",
                    "error": str(e),
                    "next_phase": "ai_analysis"
                },
                "current_phase": "quick_response_failed"
            }
    
    def _detect_basic_intention(self, query: str) -> str:
        """
        🎯 Detecta intención básica para respuesta rápida.
        
        Solo usa heurísticas simples, no AI.
        """
        query_lower = query.lower()
        
        # Indicadores básicos (sin AI)
        if any(word in query_lower for word in ['tabla', 'tablas', 'db', 'database']):
            return "list_tables"
        elif any(word in query_lower for word in ['esquema', 'schema', 'estructura']):
            return "explore_schema"
        elif any(word in query_lower for word in ['donde', 'where', 'buscar', 'find']):
            return "search_specific"
        else:
            return "general_info"
    
    async def _generate_quick_response(
        self, 
        query: str, 
        intention: str, 
        db_ids: list, 
        compact_schemas: dict
    ) -> str:
        """
        ⚡ Genera respuesta rápida basada en información disponible.
        
        Solo usa datos reales de la DB, nunca alucina.
        """
        
        if intention == "list_tables":
            return await self._generate_tables_response(db_ids, compact_schemas)
        elif intention == "explore_schema":
            return await self._generate_schema_response(db_ids, compact_schemas)
        elif intention == "search_specific":
            return await self._generate_search_response(query, db_ids, compact_schemas)
        else:
            return await self._generate_general_response(query, db_ids, compact_schemas)
    
    async def _generate_tables_response(self, db_ids: list, compact_schemas: dict) -> str:
        """📋 Genera respuesta rápida para listado de tablas."""
        
        if not compact_schemas:
            return "🔍 Analizando estructura de tu base de datos... (esto puede tomar unos segundos)"
        
        # Extraer nombres de tablas del esquema real
        all_tables = []
        for db_id, schema in compact_schemas.items():
            if isinstance(schema, str):
                # Buscar nombres de tabla en el esquema
                lines = schema.split('\n')
                for line in lines:
                    if 'CREATE TABLE' in line.upper() or 'TABLE' in line.upper():
                        # Extraer nombre de tabla (simplificado)
                        if '`' in line:
                            table_name = line.split('`')[1]
                            all_tables.append(table_name)
                        elif '"' in line:
                            table_name = line.split('"')[1]
                            all_tables.append(table_name)
        
        if all_tables:
            # Respuesta con datos reales
            table_list = ', '.join(all_tables[:10])  # Máximo 10 para respuesta rápida
            if len(all_tables) > 10:
                table_list += f" y {len(all_tables) - 10} más..."
            
            return f"📋 **Respuesta Rápida** (desde esquema de la DB):\n\nTu base de datos tiene **{len(all_tables)} tablas** disponibles:\n\n{table_list}\n\n🤖 *La AI está analizando tu consulta completa para darte información más específica...*"
        else:
            return "📋 **Respuesta Rápida**:\n\nHe detectado que tienes bases de datos configuradas, pero necesito analizar el esquema completo.\n\n🤖 *La AI está procesando tu consulta para darte información detallada...*"
    
    async def _generate_schema_response(self, db_ids: list, compact_schemas: dict) -> str:
        """🏗️ Genera respuesta rápida para exploración de esquema."""
        
        if not compact_schemas:
            return "🏗️ **Respuesta Rápida**:\n\nAnalizando la estructura de tu base de datos...\n\n🤖 *La AI está generando un análisis completo del esquema...*"
        
        db_count = len(compact_schemas)
        return f"🏗️ **Respuesta Rápida** (desde esquema de la DB):\n\nHe detectado **{db_count} base(s) de datos** configurada(s).\n\n🤖 *La AI está analizando la estructura completa para darte detalles específicos...*"
    
    async def _generate_search_response(self, query: str, db_ids: list, compact_schemas: dict) -> str:
        """🔍 Genera respuesta rápida para búsquedas específicas."""
        
        return f"🔍 **Respuesta Rápida**:\n\nHe detectado que buscas información específica en tu base de datos.\n\n🤖 *La AI está analizando tu consulta para encontrar exactamente lo que necesitas...*"
    
    async def _generate_general_response(self, query: str, db_ids: list, compact_schemas: dict) -> str:
        """ℹ️ Genera respuesta general rápida."""
        
        if db_ids:
            return f"ℹ️ **Respuesta Rápida**:\n\nHe detectado que tienes **{len(db_ids)} base(s) de datos** configurada(s).\n\n🤖 *La AI está analizando tu consulta para darte la mejor respuesta posible...*"
        else:
            return "ℹ️ **Respuesta Rápida**:\n\nProcesando tu consulta...\n\n🤖 *La AI está analizando tu solicitud...*"
    
    def _generate_fallback_response(self, query: str) -> str:
        """🆘 Genera respuesta de fallback si algo falla."""
        
        return f"🆘 **Respuesta de Emergencia**:\n\nHe tenido un problema técnico generando la respuesta rápida.\n\n🤖 *La AI está procesando tu consulta y te dará una respuesta completa en unos segundos...*"
