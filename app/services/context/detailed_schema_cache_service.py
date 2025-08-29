from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import time

from app.core.database import get_db
from app.models.detailed_schema_cache_model import (
    DetailedSchemaCache, 
    DetailedSchemaCacheCreate,
    DetailedSchemaCacheResponse,
    DetailedSchemaCacheUpdate,
    SchemaSnapshot,
    EnrichmentLevel,
    FingerprintGenerator,
    CompactSchemaFormatter
)
from app.services.base_service import BaseService
from app.utils.logger import logger
from app.services.cache.redis_schema_cache import redis_schema_cache


class DetailedSchemaCacheService(BaseService):
    """
    Servicio de cache multi-capa para esquemas de base de datos.
    
    Implementa:
    - L1: Cache en memoria (fingerprint_light)
    - L2: Cache en BD (snapshot completo)  
    - L3: Invalidación inteligente
    """
    
    def __init__(self, factory):
        # 🔒 COMPATIBILIDAD: Usar BaseService correctamente
        super().__init__(factory)
        
        # 🔒 VALIDACIÓN: Asegurar que user_id esté disponible
        if hasattr(factory, 'user') and factory.user and hasattr(factory.user, 'id'):
            self.user_id = factory.user.id
        else:
            # 🔒 FALLBACK: Crear un user_id por defecto para evitar errores
            from uuid import uuid4
            self.user_id = uuid4()
            logger.warning(f"[DetailedSchemaCacheService] ⚠️ No se pudo obtener user_id válido del factory, usando fallback: {self.user_id}")
        
        self._memory_cache: Dict[str, Dict[str, Any]] = {}  # L1 cache
        self._cache_ttl = timedelta(hours=1)  # TTL para memory cache
    
    # =====================================================
    # LIMPIEZA DE SCHEMA - ELIMINAR VALORES NULL
    # =====================================================
    
    def _clean_schema_snapshot(self, snapshot: SchemaSnapshot) -> SchemaSnapshot:
        """
        Limpia el schema eliminando valores null para ahorrar espacio y tokens.
        
        Args:
            snapshot: SchemaSnapshot original
            
        Returns:
            SchemaSnapshot limpio sin valores null
        """
        try:
            logger.info("[SchemaCacheService] 🧹 Iniciando limpieza del schema...")
            
            # Crear copia profunda del snapshot
            cleaned_tables = {}
            original_size = 0
            cleaned_size = 0
            
            for table_name, table_info in snapshot.tables.items():
                if isinstance(table_info, dict):
                    cleaned_columns = {}
                    
                    # Limpiar columnas
                    if 'columns' in table_info and isinstance(table_info['columns'], dict):
                        for col_name, col_info in table_info['columns'].items():
                            if isinstance(col_info, dict):
                                # Filtrar solo valores no-null
                                cleaned_col = {}
                                for key, value in col_info.items():
                                    if value is not None:
                                        cleaned_col[key] = value
                                
                                # Solo agregar columna si tiene al menos el tipo
                                if 'type' in cleaned_col:
                                    cleaned_columns[col_name] = cleaned_col
                    
                    # Limpiar metadatos de tabla
                    cleaned_table = {'columns': cleaned_columns}
                    
                    # Agregar otros campos solo si no son null
                    for key, value in table_info.items():
                        if key != 'columns' and value is not None:
                            cleaned_table[key] = value
                    
                    cleaned_tables[table_name] = cleaned_table
            
            # Crear snapshot limpio
            cleaned_snapshot = SchemaSnapshot(
                tables=cleaned_tables,
                relations=snapshot.relations if snapshot.relations else {},
                indexes=snapshot.indexes if snapshot.indexes else {},
                statistics=snapshot.statistics if snapshot.statistics else {},
                dialect=snapshot.dialect,
                version=snapshot.version,
                generated_at=snapshot.generated_at
            )
            
            # Calcular ahorro
            original_size = len(str(snapshot.model_dump(mode="json")))
            cleaned_size = len(str(cleaned_snapshot.model_dump(mode="json")))
            savings = original_size - cleaned_size
            savings_percent = (savings / original_size * 100) if original_size > 0 else 0
            
            logger.info(f"[SchemaCacheService] 🧹 Limpieza completada: {original_size} → {cleaned_size} chars ({savings_percent:.1f}% ahorro)")
            
            return cleaned_snapshot
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error limpiando schema: {e}")
            # En caso de error, retornar snapshot original
            return snapshot
    
    # =====================================================
    # CACHE L1: MEMORIA (FINGERPRINT CHECKS)
    # =====================================================
    
    def _get_memory_cache_key(self, user_id: UUID, db_id: UUID) -> str:
        """Genera clave para cache en memoria"""
        return f"{user_id}:{db_id}"
    
    def _is_memory_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Verifica si entrada de memoria cache está vigente"""
        if not cache_entry:
            return False
        
        cached_at = cache_entry.get('cached_at')
        if not cached_at:
            return False
            
        return datetime.now(timezone.utc) - cached_at < self._cache_ttl
    
    def _set_memory_cache(self, user_id: UUID, db_id: UUID, fingerprint_light: str, compact: str):
        """Guarda en cache de memoria"""
        key = self._get_memory_cache_key(user_id, db_id)
        self._memory_cache[key] = {
            'fingerprint_light': fingerprint_light,
            'compact': compact,
            'cached_at': datetime.now(timezone.utc)
        }
    
    def _get_memory_cache(self, user_id: UUID, db_id: UUID) -> Optional[Dict[str, Any]]:
        """Obtiene de cache de memoria si está vigente"""
        key = self._get_memory_cache_key(user_id, db_id)
        cache_entry = self._memory_cache.get(key)
        
        if self._is_memory_cache_valid(cache_entry):
            return cache_entry
        
        # Limpiar entrada expirada
        if key in self._memory_cache:
            del self._memory_cache[key]
        
        return None
    
    def get_schema(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el esquema de una base de datos.
        Wrapper para compatibilidad con ContextLoader.
        """
        try:
            # Obtener esquema desde cache
            schema_response = self.get_schema_cache(self.user_id, db_id)
            if schema_response:
                return schema_response.model_dump()
            return None
        except Exception as e:
            logger.error(f"[DetailedSchemaCacheService] Error obteniendo esquema para DB {db_id}: {e}")
            return None
    
    def get_schema_by_db_id(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el esquema de una base de datos por su ID.
        Método de compatibilidad para el router de base de datos.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Esquema como diccionario o None si no existe
        """
        try:
            # Obtener esquema desde cache
            schema_response = self.get_schema_cache(self.user_id, db_id)
            if schema_response:
                return schema_response.model_dump()
            return None
        except Exception as e:
            logger.error(f"[DetailedSchemaCacheService] Error obteniendo esquema por DB ID {db_id}: {e}")
            return None
    
    def get_schema_snapshot(self, db_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Obtiene el snapshot del schema para una base de datos.
        Método de compatibilidad para el router de base de datos.
        
        Args:
            db_id: ID de la base de datos
            
        Returns:
            Snapshot del schema o None si no existe
        """
        try:
            # Obtener esquema desde cache
            schema_response = self.get_schema_cache(self.user_id, db_id)
            if schema_response and hasattr(schema_response, 'snapshot'):
                return schema_response.snapshot
            return None
        except Exception as e:
            logger.error(f"[DetailedSchemaCacheService] Error obteniendo snapshot del schema para DB {db_id}: {e}")
            return None
    
    # =====================================================
    # OPERACIONES PRINCIPALES
    # =====================================================
    
    def get_schema_cache(self, user_id: UUID, db_id: UUID, current_fingerprint_light: Optional[str] = None) -> Optional[DetailedSchemaCacheResponse]:
        """
        Obtiene cache de schema con validación de fingerprint.
        Si no existe cache, genera automáticamente el esquema.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            current_fingerprint_light: Fingerprint actual para validación
            
        Returns:
            Cache válido o esquema generado automáticamente
        """
        logger.info(f"[SchemaCacheService] 🔍 Buscando cache para user={user_id}, db={db_id}")
        
        # 🔧 NUEVO: L1 - Cache Redis (más rápido)
        try:
            redis_result = redis_schema_cache.get_schema(user_id, db_id)
            if redis_result:
                logger.info(f"[SchemaCacheService] 🚀 Cache L1 hit (Redis) - {redis_result.get('execution_time', 0):.2f}ms")
                
                # Convertir resultado de Redis a DetailedSchemaCacheResponse
                redis_schema = redis_result['schema']
                return self._create_response_from_redis_cache(user_id, db_id, redis_schema)
        except Exception as e:
            logger.warning(f"[SchemaCacheService] ⚠️ Error en cache Redis: {e}, fallback a BD")
        
        # L2: Cache en memoria (fingerprint checks rápidos)
        memory_cache = self._get_memory_cache(user_id, db_id)
        if memory_cache and current_fingerprint_light:
            if memory_cache['fingerprint_light'] == current_fingerprint_light:
                logger.info("[SchemaCacheService] ⚡ Cache L2 hit (memoria)")
                return self._create_minimal_response_from_memory(user_id, db_id, memory_cache)
        
        # L3: Buscar en base de datos
        cache_entry = self.db.query(DetailedSchemaCache).filter(
            and_(
                DetailedSchemaCache.user_id == user_id,
                DetailedSchemaCache.db_id == db_id
            )
        ).first()
        
        if not cache_entry:
            logger.info("[SchemaCacheService] ❌ No se encontró cache en BD - generando automáticamente")
            # 🔧 NUEVO: Generar esquema automáticamente si no existe
            try:
                # 🔧 FIX: Usar método síncrono para compatibilidad
                auto_generated = self._generate_schema_automatically_sync(user_id, db_id)
                if auto_generated:
                    logger.info(f"[SchemaCacheService] ✅ Esquema generado automáticamente para DB {db_id}")
                    return auto_generated
                else:
                    logger.warning(f"[SchemaCacheService] ⚠️ No se pudo generar esquema automáticamente para DB {db_id}")
                    # 🔧 SOLUCIÓN: Crear un esquema básico de fallback
                    logger.info(f"[SchemaCacheService] 🔧 Creando esquema de fallback para DB {db_id}")
                    fallback_schema = self._create_fallback_schema_sync(user_id, db_id)
                    if fallback_schema:
                        logger.info(f"[SchemaCacheService] ✅ Esquema de fallback creado para DB {db_id}")
                        return fallback_schema
                    else:
                        logger.error(f"[SchemaCacheService] ❌ No se pudo crear esquema de fallback para DB {db_id}")
                        return None
            except Exception as e:
                logger.error(f"[SchemaCacheService] ❌ Error generando esquema automáticamente: {e}")
                return None
        
        # Validar fingerprint si se proporcionó
        if current_fingerprint_light and cache_entry.fingerprint_light != current_fingerprint_light:
            logger.warning(f"[SchemaCacheService] 🔄 Cache obsoleto (fingerprint mismatch)")
            logger.warning(f"  Esperado: {current_fingerprint_light}")
            logger.warning(f"  En cache: {cache_entry.fingerprint_light}")
            return None
        
        # Actualizar last_accessed
        cache_entry.last_accessed = datetime.now(timezone.utc)
        self.db.commit()
        
        # 🔧 NUEVO: Cachear en Redis para próximas consultas
        try:
            redis_schema_cache.set_schema(user_id, db_id, cache_entry.snapshot)
            logger.info(f"[SchemaCacheService] ✅ Schema cacheado en Redis para DB {db_id}")
        except Exception as e:
            logger.warning(f"[SchemaCacheService] ⚠️ Error cacheando en Redis: {e}")
        
        # Actualizar L2 cache (memoria)
        self._set_memory_cache(user_id, db_id, cache_entry.fingerprint_light, cache_entry.compact)
        
        logger.info(f"[SchemaCacheService] ✅ Cache L3 hit (BD) - {cache_entry.table_count} tablas")
        return DetailedSchemaCacheResponse.model_validate(cache_entry)
    
    def create_or_update_cache(
        self, 
        user_id: UUID, 
        db_id: UUID, 
        snapshot: SchemaSnapshot,
        enrichment_level: EnrichmentLevel = EnrichmentLevel.BASIC
    ) -> DetailedSchemaCacheResponse:
        """
        Crea o actualiza cache de schema.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos  
            snapshot: Snapshot del schema
            enrichment_level: Nivel de enriquecimiento
            
        Returns:
            Cache creado/actualizado
        """
        logger.info(f"[SchemaCacheService] 💾 Creando/actualizando cache para db={db_id}")
        
        # Generar fingerprints
        table_names = list(snapshot.tables.keys())
        fingerprint_light = FingerprintGenerator.generate_light_fingerprint(table_names)
        fingerprint_full = FingerprintGenerator.generate_full_fingerprint(snapshot)
        
        # Generar schema compacto
        compact_schema = CompactSchemaFormatter.format_for_ai(snapshot)
        
        # Calcular métricas
        table_count = len(snapshot.tables)
        total_columns = sum(len(table_info.get('columns', {})) for table_info in snapshot.tables.values())
        
        # 🔧 FIX: Buscar entrada existente ANTES de usarla
        existing = self.db.query(DetailedSchemaCache).filter(
            and_(
                DetailedSchemaCache.user_id == user_id,
                DetailedSchemaCache.db_id == db_id
            )
        ).first()
        
        # 🔧 NUEVO: Limpiar schema eliminando valores null para ahorrar espacio
        cleaned_snapshot = self._clean_schema_snapshot(snapshot)
        
        # 🔧 NUEVO: Generar schema limpio si no existe
        cleaned_schema = None
        if not existing or not existing.cleaned_schema:
            try:
                # 🔧 CORRECCIÓN: Usar el factory disponible en lugar de crear OpenAIService sin parámetros
                if hasattr(self, 'factory') and self.factory:
                    # Usar el servicio OpenAI del factory
                    openai_service = self.factory.get_openai_service()
                    if openai_service and hasattr(openai_service, '_optimize_schema_for_query'):
                        cleaned_schema = openai_service._optimize_schema_for_query(compact_schema, "")
                        logger.info(f"[SchemaCacheService] 🧹 Schema limpio generado: {len(compact_schema)} → {len(cleaned_schema)} chars")
                    else:
                        logger.warning("[SchemaCacheService] ⚠️ OpenAI service no disponible o no tiene método de optimización")
                        cleaned_schema = None
                else:
                    logger.warning("[SchemaCacheService] ⚠️ Factory no disponible para generar schema limpio")
                    cleaned_schema = None
            except Exception as e:
                logger.warning(f"[SchemaCacheService] ⚠️ No se pudo generar schema limpio: {e}")
                cleaned_schema = None

        # 🚀 NUEVO: Generar Graph RAG Pro schema SIEMPRE
        graph_schema = None
        try:
            logger.info(f"[SchemaCacheService] 🚀 Generando Graph RAG Pro schema para DB {db_id}")
            graph_schema = self._generate_graph_schema(user_id, db_id)
            if graph_schema:
                logger.info(f"[SchemaCacheService] ✅ Graph RAG Pro schema generado para DB {db_id}")
            else:
                logger.warning(f"[SchemaCacheService] ⚠️ No se pudo generar Graph RAG Pro schema para DB {db_id}")
        except Exception as e:
            logger.warning(f"[SchemaCacheService] ⚠️ Error generando Graph RAG Pro schema: {e}")
            graph_schema = None
        
        if existing:
            # Actualizar existente
            logger.info("[SchemaCacheService] 🔄 Actualizando cache existente")
            existing.fingerprint = fingerprint_full
            existing.fingerprint_light = fingerprint_light
            existing.snapshot = cleaned_snapshot.model_dump(mode="json")
            existing.compact = compact_schema
            if cleaned_schema:
                existing.cleaned_schema = cleaned_schema
            if graph_schema:
                existing.graph_schema = graph_schema
            existing.table_count = table_count
            existing.total_columns = total_columns
            existing.enrichment_level = enrichment_level
            existing.generated_at = datetime.now(timezone.utc)
            existing.last_accessed = datetime.now(timezone.utc)
            
            if enrichment_level > EnrichmentLevel.BASIC:
                existing.enriched_at = datetime.now(timezone.utc)
            
            cache_entry = existing
        else:
            # Crear nuevo
            logger.info("[SchemaCacheService] ✨ Creando nuevo cache")
            cache_entry = DetailedSchemaCache(
                user_id=user_id,
                db_id=db_id,
                fingerprint=fingerprint_full,
                fingerprint_light=fingerprint_light,
                snapshot=cleaned_snapshot.model_dump(mode="json"),
                compact=compact_schema,
                cleaned_schema=cleaned_schema,
                graph_schema=graph_schema,
                table_count=table_count,
                total_columns=total_columns,
                enrichment_level=enrichment_level,
                generated_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc)
            )
            self.db.add(cache_entry)
        
        self.db.commit()
        
        # Actualizar L1 cache
        self._set_memory_cache(user_id, db_id, fingerprint_light, compact_schema)
        
        logger.info(f"[SchemaCacheService] ✅ Cache guardado - {table_count} tablas, {total_columns} columnas")
        return DetailedSchemaCacheResponse.model_validate(cache_entry)
    
    def get_cleaned_schema(self, user_id: UUID, db_id: UUID) -> Optional[str]:
        """
        Obtiene el schema limpio y optimizado desde la base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Schema limpio optimizado o None si no existe
        """
        try:
            cache_entry = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).first()
            
            if cache_entry and cache_entry.cleaned_schema:
                # Actualizar último acceso
                cache_entry.last_accessed = datetime.now(timezone.utc)
                self.db.commit()
                
                logger.info(f"[SchemaCacheService] 🔥 Cache HIT DB para schema limpio {db_id}")
                return cache_entry.cleaned_schema
            else:
                logger.debug(f"[SchemaCacheService] ❌ Cache MISS DB para schema limpio {db_id}")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error obteniendo schema limpio: {e}")
            return None
    
    def invalidate_cache(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Invalida cache para una BD específica.
        Método compatible con ExecutionEngineService.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            True si se invalidó, False si no existía
        """
        logger.info(f"[SchemaCacheService] 🗑️ Invalidando cache para db={db_id}")
        
        # Eliminar de L1
        key = self._get_memory_cache_key(user_id, db_id)
        if key in self._memory_cache:
            del self._memory_cache[key]
        
        # Eliminar de L2 (BD)
        try:
            if self.db:  # 🔒 VALIDACIÓN: Verificar que db esté disponible
                deleted_count = self.db.query(DetailedSchemaCache).filter(
                    and_(
                        DetailedSchemaCache.user_id == user_id,
                        DetailedSchemaCache.db_id == db_id
                    )
                ).delete()
                
                self.db.commit()
                logger.info(f"[SchemaCacheService] ✅ Cache invalidado - {deleted_count} entradas eliminadas")
                return deleted_count > 0
            else:
                logger.warning("[SchemaCacheService] ⚠️ DB no disponible para invalidar cache")
                return False
                
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error invalidando cache: {e}")
            return False
    
    # =====================================================
    # UTILIDADES Y MANTENIMIENTO
    # =====================================================
    
    def get_cache_stats(self, user_id: UUID) -> Dict[str, Any]:
        """Obtiene estadísticas de cache para un usuario"""
        from sqlalchemy import func
        
        stats = self.db.query(
            func.count(DetailedSchemaCache.id).label('total_caches'),
            func.sum(DetailedSchemaCache.table_count).label('total_tables'),
            func.sum(DetailedSchemaCache.total_columns).label('total_columns'),
            func.avg(DetailedSchemaCache.enrichment_level).label('avg_enrichment'),
            func.min(DetailedSchemaCache.generated_at).label('oldest_cache'),
            func.max(DetailedSchemaCache.last_accessed).label('newest_access')
        ).filter(DetailedSchemaCache.user_id == user_id).first()
        
        return {
            'total_caches': stats.total_caches or 0,
            'total_tables': stats.total_tables or 0,
            'total_columns': stats.total_columns or 0,
            'avg_enrichment_level': float(stats.avg_enrichment or 0),
            'oldest_cache': stats.oldest_cache,
            'newest_access': stats.newest_access,
            'memory_cache_size': len(self._memory_cache)
        }
    
    def cleanup_old_caches(self, older_than_days: int = 30) -> int:
        """Limpia caches antiguos sin acceso reciente"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        
        deleted_count = self.db.query(DetailedSchemaCache).filter(
            DetailedSchemaCache.last_accessed < cutoff_date
        ).delete()
        
        self.db.commit()
        
        logger.info(f"[SchemaCacheService] 🧹 Limpieza completada - {deleted_count} caches antiguos eliminados")
        return deleted_count
    
    def get_enrichment_candidates(self, limit: int = 10) -> List[DetailedSchemaCacheResponse]:
        """Obtiene caches candidatos para enriquecimiento"""
        candidates = self.db.query(DetailedSchemaCache).filter(
            DetailedSchemaCache.enrichment_level < EnrichmentLevel.WITH_STATISTICS
        ).order_by(
            DetailedSchemaCache.last_accessed.desc(),
            DetailedSchemaCache.generated_at.asc()
        ).limit(limit).all()
        
        return [DetailedSchemaCacheResponse.model_validate(c) for c in candidates]
    
    def _generate_schema_automatically_sync(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        Genera automáticamente un esquema de base de datos cuando no existe en cache.
        Versión síncrona para compatibilidad.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Esquema generado o None si falla
        """
        try:
            logger.info(f"[SchemaCacheService] 🔧 Generando esquema automáticamente para DB {db_id}")
            
            # Obtener servicio de base de datos
            if not hasattr(self.factory, 'get_database_service'):
                logger.error("[SchemaCacheService] ❌ Factory no tiene get_database_service")
                return None
                
            database_service = self.factory.get_database_service()
            if not database_service:
                logger.error("[SchemaCacheService] ❌ No se pudo obtener DatabaseService")
                return None
            
            # Obtener instancia SQL de la base de datos
            try:
                sql_instance = database_service.get_sql_instance(db_id)
                if not sql_instance:
                    logger.error(f"[SchemaCacheService] ❌ No se pudo conectar a la base de datos {db_id}")
                    return None
            except Exception as e:
                logger.error(f"[SchemaCacheService] ❌ Error conectando a DB {db_id}: {e}")
                return None
            
            # Introspección del esquema
            try:
                # 🔧 FIX: Los SQLDatabase de LangChain no tienen método inspect() directo
                # Necesitamos obtener el engine subyacente para usar inspect()
                
                # Obtener el engine directamente del connection pool
                record = database_service.get_record(db_id)
                if not record:
                    logger.error(f"[SchemaCacheService] ❌ No se pudo obtener record para DB {db_id}")
                    return None
                
                # Obtener engine del connection pool
                engine = database_service.connection_pool.get_engine(record)
                if not engine:
                    logger.error(f"[SchemaCacheService] ❌ No se pudo obtener engine para DB {db_id}")
                    return None
                
                # Usar inspect() en el engine de SQLAlchemy
                from sqlalchemy import inspect
                inspector = inspect(engine)
                table_names = inspector.get_table_names()
                
                if not table_names:
                    logger.warning(f"[SchemaCacheService] ⚠️ No se encontraron tablas en DB {db_id}")
                    return None
                
                logger.info(f"[SchemaCacheService] 🔍 Encontradas {len(table_names)} tablas en DB {db_id}")
                
                # Construir snapshot básico
                tables = {}
                for table_name in table_names:
                    try:
                        # Obtener columnas
                        columns = inspector.get_columns(table_name)
                        column_info = {}
                        for col in columns:
                            column_info[col['name']] = {
                                'type': str(col['type']),
                                'nullable': col.get('nullable', True),
                                'default': col.get('default'),
                                'comment': col.get('comment')
                            }
                        
                        # Obtener comentario de la tabla
                        table_comment = inspector.get_table_comment(table_name)
                        table_description = table_comment.get('text') if table_comment else None
                        
                        tables[table_name] = {
                            'columns': column_info,
                            'description': table_description,
                            'row_count': None  # Se puede obtener con COUNT(*) si es necesario
                        }
                        
                    except Exception as e:
                        logger.warning(f"[SchemaCacheService] ⚠️ Error obteniendo info de tabla {table_name}: {e}")
                        # Continuar con tabla básica
                        tables[table_name] = {
                            'columns': {},
                            'description': None,
                            'row_count': None
                        }
                
                # Crear snapshot
                from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
                snapshot = SchemaSnapshot(
                    tables=tables,
                    enrichment_level=EnrichmentLevel.BASIC,
                    # 🔧 FIX: Obtener dialect del engine en lugar del SQLDatabase
                    dialect=engine.dialect.name if hasattr(engine, 'dialect') else 'postgresql',
                    generated_at=datetime.now(timezone.utc)
                )
                
                # Generar cache (el método create_or_update_cache limpiará automáticamente el snapshot)
                cache_response = self.create_or_update_cache(
                    user_id=user_id,
                    db_id=db_id,
                    snapshot=snapshot,
                    enrichment_level=EnrichmentLevel.BASIC
                )
                
                if cache_response:
                    logger.info(f"[SchemaCacheService] ✅ Esquema generado y cacheado exitosamente para DB {db_id}")
                    return cache_response
                else:
                    logger.error(f"[SchemaCacheService] ❌ Error cacheando esquema generado para DB {db_id}")
                    return None
                    
            except Exception as e:
                logger.error(f"[SchemaCacheService] ❌ Error en introspección de DB {db_id}: {e}")
                return None
                
        except Exception as e:
            logger.exception(f"[SchemaCacheService] ❌ Error general generando esquema para DB {db_id}: {e}")
            return None

    def _create_minimal_response_from_memory(self, user_id: UUID, db_id: UUID, memory_cache: Dict[str, Any]) -> DetailedSchemaCacheResponse:
        """Crea respuesta mínima desde cache de memoria"""
        return DetailedSchemaCacheResponse(
            id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
            user_id=user_id,
            db_id=db_id,
            fingerprint='',  # No disponible en L1
            fingerprint_light=memory_cache['fingerprint_light'],
            snapshot=SchemaSnapshot(tables={}, generated_at=datetime.now(timezone.utc)),  # Mínimo
            compact=memory_cache['compact'],
            table_count=0,
            total_columns=0,
            enrichment_level=EnrichmentLevel.BASIC,
            generated_at=memory_cache['cached_at'],
            last_accessed=datetime.now(timezone.utc)
        )
    
    def _create_fallback_schema_sync(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        Crea un esquema básico de fallback cuando no se puede generar automáticamente.
        Versión síncrona para compatibilidad.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Esquema de fallback o None si falla
        """
        try:
            logger.info(f"[SchemaCacheService] 🔧 Creando esquema de fallback para DB {db_id}")
            
            # Crear un snapshot básico con información mínima
            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
            
            # Esquema básico de fallback
            fallback_tables = {
                "information_schema.tables": {
                    "columns": {
                        "table_name": {"type": "VARCHAR", "nullable": False, "description": "Nombre de la tabla"},
                        "table_schema": {"type": "VARCHAR", "nullable": False, "description": "Esquema de la tabla"},
                        "table_type": {"type": "VARCHAR", "nullable": False, "description": "Tipo de tabla"}
                    },
                    "description": "Tabla del sistema que contiene información sobre todas las tablas",
                    "row_count": None
                },
                "information_schema.columns": {
                    "columns": {
                        "table_name": {"type": "VARCHAR", "nullable": False, "description": "Nombre de la tabla"},
                        "column_name": {"type": "VARCHAR", "nullable": False, "description": "Nombre de la columna"},
                        "data_type": {"type": "VARCHAR", "nullable": False, "description": "Tipo de datos"},
                        "is_nullable": {"type": "VARCHAR", "nullable": False, "description": "Si la columna permite NULL"}
                    },
                    "description": "Tabla del sistema que contiene información sobre todas las columnas",
                    "row_count": None
                }
            }
            
            # Crear snapshot de fallback
            snapshot = SchemaSnapshot(
                tables=fallback_tables,
                enrichment_level=EnrichmentLevel.BASIC,
                dialect="postgresql",  # Asumir PostgreSQL como fallback
                generated_at=datetime.now(timezone.utc)
            )
            
            # Crear respuesta de fallback directamente (sin pasar por BD)
            from uuid import uuid4
            fallback_response = DetailedSchemaCacheResponse(
                id=uuid4(),
                user_id=user_id,
                db_id=db_id,
                fingerprint="fallback_fingerprint",
                fingerprint_light="fallback_fingerprint_light",
                snapshot=snapshot,
                compact=CompactSchemaFormatter.format_for_ai(snapshot),
                table_count=len(fallback_tables),
                total_columns=sum(len(table_info.get('columns', {})) for table_info in fallback_tables.values()),
                enrichment_level=EnrichmentLevel.BASIC,
                generated_at=datetime.now(timezone.utc),
                last_accessed=datetime.now(timezone.utc),
                enriched_at=None
            )
            
            logger.info(f"[SchemaCacheService] ✅ Esquema de fallback creado exitosamente para DB {db_id}")
            return fallback_response
                
        except Exception as e:
            logger.exception(f"[SchemaCacheService] ❌ Error creando esquema de fallback para DB {db_id}: {e}")
            return None
    
    def _create_response_from_redis_cache(self, user_id: UUID, db_id: UUID, redis_schema: Dict[str, Any]) -> DetailedSchemaCacheResponse:
        """
        Crea respuesta desde cache de Redis.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            redis_schema: Schema obtenido de Redis
            
        Returns:
            DetailedSchemaCacheResponse desde Redis
        """
        try:
            # Convertir schema de Redis a SchemaSnapshot
            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
            
            # Crear snapshot desde Redis
            # 🔧 FIX: Manejar formato de fecha de Redis (puede tener 'Z' al final)
            generated_at_str = redis_schema.get('generated_at', datetime.now().isoformat())
            try:
                # Intentar parsear la fecha, manejando el formato 'Z' de Redis
                if generated_at_str.endswith('Z'):
                    generated_at_str = generated_at_str.replace('Z', '+00:00')
                generated_at = datetime.fromisoformat(generated_at_str)
            except ValueError as date_error:
                logger.warning(f"[SchemaCacheService] ⚠️ Error parseando fecha '{generated_at_str}': {date_error}, usando fecha actual")
                generated_at = datetime.now(timezone.utc)
            
            snapshot = SchemaSnapshot(
                tables=redis_schema.get('tables', {}),
                enrichment_level=EnrichmentLevel.BASIC,
                dialect=redis_schema.get('dialect', 'postgresql'),
                generated_at=generated_at
            )
            
            # Crear respuesta desde Redis
            from uuid import uuid4
            redis_response = DetailedSchemaCacheResponse(
                id=uuid4(),
                user_id=user_id,
                db_id=db_id,
                fingerprint=redis_schema.get('fingerprint', 'redis_fingerprint'),
                fingerprint_light=redis_schema.get('fingerprint_light', 'redis_fingerprint_light'),
                snapshot=snapshot,
                compact=redis_schema.get('compact', ''),
                table_count=len(redis_schema.get('tables', {})),
                total_columns=sum(len(table_info.get('columns', {})) for table_info in redis_schema.get('tables', {}).values()),
                enrichment_level=EnrichmentLevel.BASIC,
                generated_at=snapshot.generated_at,
                last_accessed=datetime.now(timezone.utc),
                enriched_at=None
            )
            
            logger.info(f"[SchemaCacheService] ✅ Respuesta creada desde Redis para DB {db_id}")
            return redis_response
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error creando respuesta desde Redis: {e}")
            return None
    
    # =====================================================
    # 🔧 NUEVO: DETECCIÓN AUTOMÁTICA DE CAMBIOS
    # =====================================================
    
    async def detect_schema_changes(self, user_id: UUID, db_id: UUID) -> Dict[str, Any]:
        """
        Detecta automáticamente cambios en la estructura de una base de datos.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Información sobre cambios detectados
        """
        try:
            logger.info(f"[SchemaCacheService] 🔍 Detectando cambios en DB {db_id}")
            
            # Obtener schema actual desde cache
            current_cache = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).first()
            
            if not current_cache:
                logger.warning(f"[SchemaCacheService] ⚠️ No hay cache para DB {db_id}")
                return {'changes_detected': False, 'reason': 'no_cache_found'}
            
            # Generar fingerprint actual de la DB externa
            current_fingerprint = await self._generate_current_fingerprint(db_id)
            if not current_fingerprint:
                logger.warning(f"[SchemaCacheService] ⚠️ No se pudo generar fingerprint para DB {db_id}")
                return {'changes_detected': False, 'reason': 'fingerprint_generation_failed'}
            
            # Comparar fingerprints
            changes = self._compare_fingerprints(
                current_cache.fingerprint_light,
                current_fingerprint['light'],
                current_cache.fingerprint,
                current_fingerprint['full']
            )
            
            if changes['changes_detected']:
                logger.info(f"[SchemaCacheService] 🔄 Cambios detectados en DB {db_id}: {changes['summary']}")
                
                # Invalidar cache automáticamente
                await self._auto_invalidate_cache(user_id, db_id, changes)
                
                return {
                    'changes_detected': True,
                    'summary': changes['summary'],
                    'details': changes['details'],
                    'action_taken': 'cache_invalidated'
                }
            else:
                logger.debug(f"[SchemaCacheService] ✅ No se detectaron cambios en DB {db_id}")
                return {'changes_detected': False, 'reason': 'no_changes'}
                
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error detectando cambios en DB {db_id}: {e}")
            return {'changes_detected': False, 'reason': f'error: {str(e)}'}
    
    async def _generate_current_fingerprint(self, db_id: UUID) -> Optional[Dict[str, str]]:
        """Genera fingerprint actual de la DB externa"""
        try:
            # Obtener servicio de base de datos
            if not hasattr(self.factory, 'get_database_service'):
                logger.error("[SchemaCacheService] ❌ Factory no tiene get_database_service")
                return None
                
            database_service = self.factory.get_database_service()
            if not database_service:
                logger.error("[SchemaCacheService] ❌ No se pudo obtener DatabaseService")
                return None
            
            # Obtener engine del connection pool
            record = database_service.get_record(db_id)
            if not record:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener record para DB {db_id}")
                return None
            
            engine = database_service.connection_pool.get_engine(record)
            if not engine:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener engine para DB {db_id}")
                return None
            
            # Usar inspect() para obtener estructura actual
            from sqlalchemy import inspect
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                logger.warning(f"[SchemaCacheService] ⚠️ No se encontraron tablas en DB {db_id}")
                return None
            
            # Generar fingerprint light (solo nombres de tablas)
            fingerprint_light = FingerprintGenerator.generate_light_fingerprint(table_names)
            
            # Generar fingerprint completo (estructura detallada)
            tables_structure = {}
            for table_name in table_names:
                try:
                    columns = inspector.get_columns(table_name)
                    column_info = {}
                    for col in columns:
                        column_info[col['name']] = {
                            'type': str(col['type']),
                            'nullable': col.get('nullable', True),
                            'default': col.get('default'),
                            'comment': col.get('comment')
                        }
                    
                    table_comment = inspector.get_table_comment(table_name)
                    table_description = table_comment.get('text') if table_comment else None
                    
                    tables_structure[table_name] = {
                        'columns': column_info,
                        'description': table_description
                    }
                    
                except Exception as e:
                    logger.warning(f"[SchemaCacheService] ⚠️ Error obteniendo info de tabla {table_name}: {e}")
                    continue
            
            # Crear snapshot temporal para generar fingerprint completo
            temp_snapshot = SchemaSnapshot(
                tables=tables_structure,
                enrichment_level=EnrichmentLevel.BASIC,
                dialect=engine.dialect.name if hasattr(engine, 'dialect') else 'postgresql',
                generated_at=datetime.now(timezone.utc)
            )
            
            fingerprint_full = FingerprintGenerator.generate_full_fingerprint(temp_snapshot)
            
            return {
                'light': fingerprint_light,
                'full': fingerprint_full,
                'table_count': len(table_names),
                'generated_at': datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error generando fingerprint actual: {e}")
            return None
    
    def _compare_fingerprints(self, cached_light: str, current_light: str, 
                             cached_full: str, current_full: str) -> Dict[str, Any]:
        """Compara fingerprints para detectar cambios"""
        changes = {
            'changes_detected': False,
            'summary': '',
            'details': {
                'light_fingerprint_changed': False,
                'full_fingerprint_changed': False,
                'tables_added': False,
                'tables_removed': False,
                'structure_changed': False
            }
        }
        
        # Verificar cambios en fingerprint light (nombres de tablas)
        if cached_light != current_light:
            changes['changes_detected'] = True
            changes['details']['light_fingerprint_changed'] = True
            changes['summary'] = 'Cambios en estructura de tablas detectados'
        
        # Verificar cambios en fingerprint completo (estructura detallada)
        if cached_full != current_full:
            changes['changes_detected'] = True
            changes['details']['full_fingerprint_changed'] = True
            changes['details']['structure_changed'] = True
            
            if not changes['summary']:
                changes['summary'] = 'Cambios en estructura de columnas detectados'
            else:
                changes['summary'] += ' y estructura de columnas'
        
        return changes
    
    async def _auto_invalidate_cache(self, user_id: UUID, db_id: UUID, changes: Dict[str, Any]) -> None:
        """Invalida automáticamente el cache cuando se detectan cambios"""
        try:
            logger.info(f"[SchemaCacheService] 🗑️ Invalidando cache automáticamente para DB {db_id}")
            
            # 1. Invalidar cache Redis
            try:
                redis_schema_cache.invalidate_schema(user_id, db_id)
                logger.info(f"[SchemaCacheService] ✅ Cache Redis invalidado para DB {db_id}")
            except Exception as e:
                logger.warning(f"[SchemaCacheService] ⚠️ Error invalidando cache Redis: {e}")
            
            # 2. Invalidar cache en memoria
            key = self._get_memory_cache_key(user_id, db_id)
            if key in self._memory_cache:
                del self._memory_cache[key]
                logger.info(f"[SchemaCacheService] ✅ Cache en memoria invalidado para DB {db_id}")
            
            # 3. Marcar como obsoleto en BD (opcional)
            # Esto permite que el sistema sepa que necesita regenerar el schema
            try:
                current_cache = self.db.query(DetailedSchemaCache).filter(
                    and_(
                        DetailedSchemaCache.user_id == user_id,
                        DetailedSchemaCache.db_id == db_id
                    )
                ).first()
                
                if current_cache:
                    current_cache.fingerprint_light = "OBSOLETE_" + current_cache.fingerprint_light
                    current_cache.last_accessed = datetime.now(timezone.utc)
                    self.db.commit()
                    logger.info(f"[SchemaCacheService] ✅ Cache marcado como obsoleto en BD para DB {db_id}")
                    
            except Exception as e:
                logger.warning(f"[SchemaCacheService] ⚠️ Error marcando cache como obsoleto: {e}")
            
            logger.info(f"[SchemaCacheService] ✅ Invalidación automática completada para DB {db_id}")
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error en invalidación automática para DB {db_id}: {e}")
    
    def get_schemas_needing_refresh(self, user_id: UUID, limit: int = 10) -> List[DetailedSchemaCacheResponse]:
        """Obtiene schemas que necesitan refresh basado en fingerprints obsoletos"""
        try:
            obsolete_schemas = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.fingerprint_light.like('OBSOLETE_%')
                )
            ).order_by(DetailedSchemaCache.last_accessed.desc()).limit(limit).all()
            
            return [DetailedSchemaCacheResponse.model_validate(schema) for schema in obsolete_schemas]
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error obteniendo schemas obsoletos: {e}")
            return []

    def force_regenerate_schema(self, user_id: UUID, db_id: UUID) -> Dict[str, Any]:
        """
        Fuerza la regeneración completa del schema desde la DB externa.
        Borra el cache existente y crea uno completamente nuevo.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Diccionario con detalles de la regeneración y métricas de cambios
        """
        start_time = time.time()
        logger.info(f"[SchemaCacheService] 🔄 Iniciando regeneración forzada para DB {db_id}")
        
        try:
            # 1. OBTENER MÉTRICAS ANTES (para comparación)
            existing_cache = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).first()
            
            metrics_before = {
                'tables': existing_cache.table_count if existing_cache else 0,
                'columns': existing_cache.total_columns if existing_cache else 0,
                'fingerprint': existing_cache.fingerprint if existing_cache else None
            }
            
            # 2. BORRAR CACHE EXISTENTE
            cache_cleared = self._delete_existing_cache(user_id, db_id)
            if not cache_cleared:
                logger.warning(f"[SchemaCacheService] ⚠️ No se pudo borrar cache existente para DB {db_id}")
            
            # 3. LIMPIAR TODOS LOS CACHES
            caches_cleared = self._invalidate_all_caches(user_id, db_id)
            
            # 4. REGENERAR SCHEMA DESDE DB EXTERNA
            logger.info(f"[SchemaCacheService] 🔍 Regenerando schema desde DB externa {db_id}")
            new_schema = self._regenerate_from_external_database(user_id, db_id)
            
            if not new_schema:
                logger.error(f"[SchemaCacheService] ❌ Error regenerando schema para DB {db_id}")
                return {
                    'success': False,
                    'error': 'No se pudo regenerar el schema desde la DB externa',
                    'cache_cleared': cache_cleared,
                    'caches_cleared': caches_cleared
                }
            
            # 5. CALCULAR MÉTRICAS DESPUÉS
            metrics_after = {
                'tables': new_schema.table_count,
                'columns': new_schema.total_columns,
                'fingerprint': new_schema.fingerprint
            }
            
            # 6. CALCULAR CAMBIOS
            changes = self._calculate_schema_changes(metrics_before, metrics_after)
            
            # 7. GUARDAR EN REDIS
            redis_updated = False
            try:
                if hasattr(self, 'factory') and self.factory:
                    redis_cache = self.factory.get_redis_schema_cache()
                    if redis_cache:
                        redis_updated = redis_cache.set_schema(
                            user_id, 
                            db_id, 
                            new_schema.snapshot.model_dump() if hasattr(new_schema, 'snapshot') else {}
                        )
            except Exception as e:
                logger.warning(f"[SchemaCacheService] ⚠️ Error actualizando Redis: {e}")
            
            # 8. CALCULAR TIEMPO TOTAL
            total_time = time.time() - start_time
            
            logger.info(f"[SchemaCacheService] ✅ Regeneración completada para DB {db_id} en {total_time:.2f}s")
            
            return {
                'success': True,
                'message': 'Schema regenerado completamente desde DB externa',
                'regeneration_details': {
                    'tables_before': metrics_before['tables'],
                    'tables_after': metrics_after['tables'],
                    'columns_before': metrics_before['columns'],
                    'columns_after': metrics_after['columns'],
                    'new_tables': changes.get('new_tables', []),
                    'removed_tables': changes.get('removed_tables', []),
                    'modified_tables': changes.get('modified_tables', []),
                    'regeneration_time': f"{total_time:.2f}s",
                    'cache_cleared': cache_cleared,
                    'caches_cleared': caches_cleared,
                    'redis_updated': redis_updated,
                    'fingerprint_changed': metrics_before['fingerprint'] != metrics_after['fingerprint']
                }
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[SchemaCacheService] ❌ Error en regeneración forzada para DB {db_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'regeneration_time': f"{total_time:.2f}s",
                'cache_cleared': False,
                'caches_cleared': False
            }

    def _delete_existing_cache(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Borra completamente el cache existente de la base de datos.
        """
        try:
            deleted_count = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).delete()
            
            self.db.commit()
            logger.info(f"[SchemaCacheService] 🗑️ Cache existente borrado: {deleted_count} entradas")
            return deleted_count > 0
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error borrando cache existente: {e}")
            self.db.rollback()
            return False

    def _invalidate_all_caches(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Invalida todos los caches (Redis + memoria) para una DB específica.
        """
        try:
            # 1. Invalidar cache en memoria
            key = self._get_memory_cache_key(user_id, db_id)
            if key in self._memory_cache:
                del self._memory_cache[key]
                logger.info(f"[SchemaCacheService] ✅ Cache en memoria invalidado para DB {db_id}")
            
            # 2. Invalidar cache Redis
            try:
                if hasattr(self, 'factory') and self.factory:
                    redis_cache = self.factory.get_redis_schema_cache()
                    if redis_cache and hasattr(redis_cache, 'invalidate_schema'):
                        redis_cache.invalidate_schema(user_id, db_id)
                        logger.info(f"[SchemaCacheService] ✅ Cache Redis invalidado para DB {db_id}")
            except Exception as e:
                logger.warning(f"[SchemaCacheService] ⚠️ Error invalidando Redis: {e}")
            
            return True
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error invalidando caches: {e}")
            return False

    def _regenerate_from_external_database(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        Regenera completamente el schema desde la base de datos externa del usuario.
        """
        try:
            logger.info(f"[SchemaCacheService] 🔍 Regenerando schema desde DB externa {db_id}")
            
            # Usar el método existente de generación automática
            new_schema = self._generate_schema_automatically_sync(user_id, db_id)
            
            if new_schema:
                logger.info(f"[SchemaCacheService] ✅ Schema regenerado exitosamente para DB {db_id}")
                return new_schema
            else:
                logger.error(f"[SchemaCacheService] ❌ No se pudo regenerar schema para DB {db_id}")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error regenerando desde DB externa: {e}")
            return None

    def _calculate_schema_changes(self, metrics_before: Dict[str, Any], metrics_after: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcula los cambios entre el schema anterior y el nuevo.
        """
        changes = {
            'new_tables': [],
            'removed_tables': [],
            'modified_tables': []
        }
        
        # Por ahora, solo comparamos métricas básicas
        # En el futuro se puede expandir para comparar estructura detallada
        
        if metrics_before['tables'] != metrics_after['tables']:
            if metrics_after['tables'] > metrics_before['tables']:
                changes['new_tables'] = [f"+{metrics_after['tables'] - metrics_before['tables']} tablas"]
            else:
                changes['removed_tables'] = [f"-{metrics_before['tables'] - metrics_after['tables']} tablas"]
        
        if metrics_before['columns'] != metrics_after['columns']:
            changes['modified_tables'].append(f"Columnas: {metrics_before['columns']} → {metrics_after['columns']}")
        
        if metrics_before['fingerprint'] != metrics_before['fingerprint']:
            changes['modified_tables'].append("Estructura modificada")
        
        return changes

    # =====================================================
    # 🚀 GRAPH RAG PRO - SCHEMA ENRIQUECIDO
    # =====================================================
    
    def _generate_graph_schema(self, user_id: UUID, db_id: UUID) -> Dict[str, Any]:
        """
        Genera un schema enriquecido de nivel Graph RAG Pro.
        Incluye relaciones, constraints, metadata semántica y estadísticas.
        """
        try:
            logger.info(f"[SchemaCacheService] 🚀 Generando Graph RAG Pro schema para DB {db_id}")
            
            # 🔧 CORRECCIÓN: Evitar bucle infinito - obtener schema base SIN llamar a _generate_schema_automatically_sync
            # En su lugar, obtener el schema existente del cache o crear uno básico
            base_schema = self._get_base_schema_without_recursion(user_id, db_id)
            if not base_schema:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener schema base para DB {db_id}")
                return None
            
            # Enriquecer con información de BD
            enriched_schema = self._enrich_schema_with_database_info(
                user_id, db_id, base_schema.snapshot
            )
            
            # Generar grafo de relaciones
            graph_schema = self._build_relationship_graph(enriched_schema)
            
            # Agregar metadata semántica
            semantic_schema = self._add_semantic_metadata(graph_schema)
            
            # Generar fingerprint del schema enriquecido
            enriched_fingerprint = self._generate_enriched_fingerprint(semantic_schema)
            
            # Crear respuesta final
            final_schema = {
                'base_schema': base_schema.snapshot.model_dump(),
                'enriched_schema': enriched_schema,
                'graph_schema': graph_schema,
                'semantic_schema': semantic_schema,
                'fingerprint': enriched_fingerprint,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'version': '2.0-graph-rag-pro'
            }
            
            # 🔧 CORRECCIÓN: Limpiar schema para almacenamiento JSON
            cleaned_schema = self._clean_schema_for_json_storage(final_schema)
            
            logger.info(f"[SchemaCacheService] ✅ Graph RAG Pro schema generado para DB {db_id}")
            return cleaned_schema
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error generando Graph RAG Pro schema: {e}")
            return None

    def _clean_schema_for_json_storage(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        🔧 CORRECCIÓN: Limpia el schema para almacenamiento JSON.
        
        Convierte todos los objetos datetime a strings ISO para evitar
        errores de serialización JSON en PostgreSQL.
        """
        if not isinstance(schema, dict):
            return schema
        
        cleaned_schema = {}
        
        for key, value in schema.items():
            if isinstance(value, dict):
                # Recursivamente limpiar diccionarios anidados
                cleaned_schema[key] = self._clean_schema_for_json_storage(value)
            elif isinstance(value, list):
                # Limpiar listas
                cleaned_schema[key] = [
                    self._clean_schema_for_json_storage(item) if isinstance(item, dict) else item
                    for item in value
                ]
            elif isinstance(value, datetime):
                # Convertir datetime a string ISO
                cleaned_schema[key] = value.isoformat()
            else:
                # Mantener otros tipos de datos
                cleaned_schema[key] = value
        
        return cleaned_schema

    def _get_base_schema_without_recursion(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        🔧 CORRECCIÓN: Obtiene schema base SIN crear bucle infinito.
        
        Este método:
        1. Busca en cache existente
        2. Si no existe, crea schema básico directamente
        3. NO llama a métodos que puedan crear recursión
        """
        try:
            logger.info(f"[SchemaCacheService] 🔍 Obteniendo schema base sin recursión para DB {db_id}")
            
            # 1. Intentar obtener del cache existente
            cache_entry = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).first()
            
            if cache_entry and cache_entry.snapshot:
                logger.info(f"[SchemaCacheService] ✅ Schema base obtenido del cache para DB {db_id}")
                return DetailedSchemaCacheResponse.model_validate(cache_entry)
            
            # 2. Si no existe en cache, crear schema básico directamente
            logger.info(f"[SchemaCacheService] 🔧 Creando schema básico directamente para DB {db_id}")
            
            # Obtener servicio de base de datos
            if not hasattr(self, 'factory') or not self.factory:
                logger.error("[SchemaCacheService] ❌ Factory no disponible")
                return None
                
            database_service = self.factory.get_database_service()
            if not database_service:
                logger.error("[SchemaCacheService] ❌ No se pudo obtener DatabaseService")
                return None
            
            # Obtener engine del connection pool
            record = database_service.get_record(db_id)
            if not record:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener record para DB {db_id}")
                return None
            
            engine = database_service.connection_pool.get_engine(record)
            if not engine:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener engine para DB {db_id}")
                return None
            
            # Usar inspect() en el engine de SQLAlchemy
            from sqlalchemy import inspect
            inspector = inspect(engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                logger.warning(f"[SchemaCacheService] ⚠️ No se encontraron tablas en DB {db_id}")
                return None
            
            logger.info(f"[SchemaCacheService] 🔍 Encontradas {len(table_names)} tablas en DB {db_id}")
            
            # Construir snapshot básico
            tables = {}
            for table_name in table_names:
                try:
                    # Obtener columnas
                    columns = inspector.get_columns(table_name)
                    column_info = {}
                    for col in columns:
                        column_info[col['name']] = {
                            'type': str(col['type']),
                            'nullable': col.get('nullable', True),
                            'default': col.get('default'),
                            'comment': col.get('comment')
                        }
                    
                    # Obtener comentario de la tabla
                    table_comment = inspector.get_table_comment(table_name)
                    table_description = table_comment.get('text') if table_comment else None
                    
                    tables[table_name] = {
                        'columns': column_info,
                        'description': table_description,
                        'row_count': None
                    }
                    
                except Exception as e:
                    logger.warning(f"[SchemaCacheService] ⚠️ Error obteniendo info de tabla {table_name}: {e}")
                    tables[table_name] = {
                        'columns': {},
                        'description': None,
                        'row_count': None
                    }
            
            # Crear snapshot básico
            from app.models.detailed_schema_cache_model import SchemaSnapshot, EnrichmentLevel
            snapshot = SchemaSnapshot(
                tables=tables,
                relations={},
                indexes={},
                statistics={
                    'tables': len(tables),
                    'columns': sum(len(table_info.get('columns', {})) for table_info in tables.values())
                },
                dialect='unknown',
                version='1.0',
                generated_at=datetime.now(timezone.utc)
            )
            
            # Crear respuesta básica
            basic_response = DetailedSchemaCacheResponse(
                user_id=user_id,
                db_id=db_id,
                snapshot=snapshot,
                enrichment_level=EnrichmentLevel.BASIC,
                fingerprint_light="basic",
                fingerprint_full="basic",
                compact="basic",
                generated_at=datetime.now(timezone.utc)
            )
            
            logger.info(f"[SchemaCacheService] ✅ Schema básico creado directamente para DB {db_id}")
            return basic_response
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error obteniendo schema base sin recursión: {e}")
            return None

    def _enrich_schema_with_database_info(self, user_id: UUID, db_id: UUID, base_snapshot: SchemaSnapshot) -> Dict[str, Any]:
        """
        Enriquece el schema base con información detallada de la base de datos.
        """
        try:
            logger.info(f"[SchemaCacheService] 🔍 Enriqueciendo schema con info de BD para DB {db_id}")
            
            # Obtener servicio de base de datos
            if not hasattr(self, 'factory') or not self.factory:
                logger.error("[SchemaCacheService] ❌ Factory no disponible")
                return base_snapshot.model_dump()
                
            database_service = self.factory.get_database_service()
            if not database_service:
                logger.error("[SchemaCacheService] ❌ No se pudo obtener DatabaseService")
                return base_snapshot.model_dump()
            
            # Obtener engine del connection pool
            record = database_service.get_record(db_id)
            if not record:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener record para DB {db_id}")
                return base_snapshot.model_dump()
            
            engine = database_service.connection_pool.get_engine(record)
            if not engine:
                logger.error(f"[SchemaCacheService] ❌ No se pudo obtener engine para DB {db_id}")
                return base_snapshot.model_dump()
            
            # Usar inspect() para obtener información detallada
            from sqlalchemy import inspect
            inspector = inspect(engine)
            
            enriched_tables = {}
            
            for table_name in base_snapshot.tables.keys():
                try:
                    table_info = base_snapshot.tables[table_name]
                    enriched_table = self._enrich_table_info(
                        inspector, table_name, table_info
                    )
                    enriched_tables[table_name] = enriched_table
                    
                except Exception as e:
                    logger.warning(f"[SchemaCacheService] ⚠️ Error enriqueciendo tabla {table_name}: {e}")
                    enriched_tables[table_name] = table_info
            
            return {
                'tables': enriched_tables,
                'relations': base_snapshot.relations,
                'indexes': base_snapshot.indexes,
                'statistics': base_snapshot.statistics,
                'dialect': base_snapshot.dialect,
                'version': base_snapshot.version,
                'generated_at': base_snapshot.generated_at
            }
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error enriqueciendo schema: {e}")
            return base_snapshot.model_dump()

    def _enrich_table_info(self, inspector, table_name: str, table_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enriquece la información de una tabla específica.
        """
        try:
            enriched_table = table_info.copy()
            
            # 1. PRIMARY KEYS
            try:
                pk_constraint = inspector.get_pk_constraint(table_name)
                if pk_constraint and pk_constraint.get('constrained_columns'):
                    enriched_table['primary_keys'] = pk_constraint['constrained_columns']
            except Exception as e:
                logger.debug(f"[SchemaCacheService] ⚠️ No se pudo obtener PK para {table_name}: {e}")
                enriched_table['primary_keys'] = []
            
            # 2. FOREIGN KEYS
            try:
                fk_constraints = inspector.get_foreign_keys(table_name)
                if fk_constraints:
                    enriched_table['foreign_keys'] = []
                    for fk in fk_constraints:
                        fk_info = {
                            'constrained_columns': fk.get('constrained_columns', []),
                            'referred_table': fk.get('referred_table', ''),
                            'referred_columns': fk.get('referred_columns', []),
                            'name': fk.get('name', '')
                        }
                        enriched_table['foreign_keys'].append(fk_info)
                else:
                    enriched_table['foreign_keys'] = []
            except Exception as e:
                logger.debug(f"[SchemaCacheService] ⚠️ No se pudo obtener FK para {table_name}: {e}")
                enriched_table['foreign_keys'] = []
            
            # 3. INDEXES
            try:
                indexes = inspector.get_indexes(table_name)
                if indexes:
                    enriched_table['indexes'] = []
                    for idx in indexes:
                        idx_info = {
                            'name': idx.get('name', ''),
                            'column_names': idx.get('column_names', []),
                            'unique': idx.get('unique', False),
                            'type': idx.get('type', '')
                        }
                        enriched_table['indexes'].append(idx_info)
                else:
                    enriched_table['indexes'] = []
            except Exception as e:
                logger.debug(f"[SchemaCacheService] ⚠️ No se pudo obtener índices para {table_name}: {e}")
                enriched_table['indexes'] = []
            
            # 4. CONSTRAINTS
            try:
                # Obtener constraints de check (esto puede variar según el dialecto)
                if hasattr(inspector, 'get_check_constraints'):
                    check_constraints = inspector.get_check_constraints(table_name)
                    if check_constraints:
                        enriched_table['check_constraints'] = check_constraints
                    else:
                        enriched_table['check_constraints'] = []
                else:
                    enriched_table['check_constraints'] = []
                
                # Obtener constraints únicos
                if hasattr(inspector, 'get_unique_constraints'):
                    unique_constraints = inspector.get_unique_constraints(table_name)
                    if unique_constraints:
                        enriched_table['unique_constraints'] = unique_constraints
                    else:
                        enriched_table['unique_constraints'] = []
                else:
                    enriched_table['unique_constraints'] = []
                    
            except Exception as e:
                logger.debug(f"[SchemaCacheService] ⚠️ No se pudo obtener constraints para {table_name}: {e}")
                enriched_table['check_constraints'] = []
                enriched_table['unique_constraints'] = []
            
            # 5. ENRIQUECER COLUMNAS
            if 'columns' in enriched_table:
                enriched_columns = {}
                for col_name, col_info in enriched_table['columns'].items():
                    enriched_col = col_info.copy()
                    
                    # Detectar tipos ENUM
                    if 'type' in enriched_col:
                        col_type = str(enriched_col['type'])
                        if 'ENUM' in col_type.upper():
                            enriched_col['is_enum'] = True
                            # Intentar extraer valores del ENUM
                            try:
                                if hasattr(inspector, 'get_enum_values'):
                                    enum_values = inspector.get_enum_values(table_name, col_name)
                                    if enum_values:
                                        enriched_col['enum_values'] = enum_values
                            except:
                                pass
                        else:
                            enriched_col['is_enum'] = False
                    
                    # Agregar metadata semántica básica
                    enriched_col['semantic_type'] = self._infer_semantic_type(col_name, enriched_col.get('type', ''))
                    enriched_col['is_identifier'] = self._is_identifier_column(col_name, enriched_col)
                    enriched_col['is_temporal'] = self._is_temporal_column(enriched_col.get('type', ''))
                    enriched_col['is_geographic'] = self._is_geographic_column(col_name, enriched_col.get('type', ''))
                    
                    enriched_columns[col_name] = enriched_col
                
                enriched_table['columns'] = enriched_columns
            
            # 6. ESTADÍSTICAS BÁSICAS
            try:
                # Obtener row count aproximado
                with engine.connect() as conn:
                    result = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    row_count = result.scalar()
                    enriched_table['estimated_row_count'] = row_count
            except Exception as e:
                logger.debug(f"[SchemaCacheService] ⚠️ No se pudo obtener row count para {table_name}: {e}")
                enriched_table['estimated_row_count'] = None
            
            # 7. METADATA SEMÁNTICA DE TABLA
            enriched_table['semantic_category'] = self._infer_table_semantic_category(table_name)
            enriched_table['business_entity'] = self._is_business_entity(table_name)
            enriched_table['audit_fields'] = self._has_audit_fields(enriched_table.get('columns', {}))
            
            return enriched_table
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error enriqueciendo tabla {table_name}: {e}")
            return table_info

    def _build_relationship_graph(self, enriched_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Construye el grafo de relaciones basado en foreign keys y metadata.
        """
        try:
            logger.info("[SchemaCacheService] 🔗 Construyendo grafo de relaciones")
            
            graph = {
                'entities': {},
                'relationships': [],
                'entity_hierarchy': {},
                'relationship_matrix': {}
            }
            
            tables = enriched_schema.get('tables', {})
            
            # 1. IDENTIFICAR ENTIDADES
            for table_name, table_info in tables.items():
                entity_info = {
                    'name': table_name,
                    'type': self._classify_entity_type(table_name, table_info),
                    'properties': list(table_info.get('columns', {}).keys()),
                    'primary_keys': table_info.get('primary_keys', []),
                    'semantic_category': table_info.get('semantic_category', 'unknown'),
                    'business_entity': table_info.get('business_entity', False),
                    'estimated_rows': table_info.get('estimated_row_count', 0)
                }
                graph['entities'][table_name] = entity_info
            
            # 2. CONSTRUIR RELACIONES
            for table_name, table_info in tables.items():
                foreign_keys = table_info.get('foreign_keys', [])
                
                for fk in foreign_keys:
                    if fk.get('referred_table') and fk.get('referred_table') in tables:
                        relationship = {
                            'source_table': table_name,
                            'target_table': fk['referred_table'],
                            'source_columns': fk.get('constrained_columns', []),
                            'target_columns': fk.get('referred_columns', []),
                            'relationship_type': self._classify_relationship_type(table_name, fk['referred_table']),
                            'constraint_name': fk.get('name', ''),
                            'cardinality': self._infer_cardinality(table_name, fk['referred_table'], tables)
                        }
                        graph['relationships'].append(relationship)
            
            # 3. CONSTRUIR JERARQUÍA
            graph['entity_hierarchy'] = self._build_entity_hierarchy(graph['relationships'])
            
            # 4. MATRIZ DE RELACIONES
            graph['relationship_matrix'] = self._build_relationship_matrix(graph['relationships'], list(tables.keys()))
            
            logger.info(f"[SchemaCacheService] ✅ Grafo construido: {len(graph['entities'])} entidades, {len(graph['relationships'])} relaciones")
            return graph
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error construyendo grafo: {e}")
            return {}

    def _add_semantic_metadata(self, graph_schema: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agrega metadata semántica al grafo de relaciones.
        """
        try:
            logger.info("[SchemaCacheService] 🧠 Agregando metadata semántica")
            
            semantic_schema = graph_schema.copy()
            
            # 1. CONTEXTO RELACIONAL PARA AI
            semantic_schema['ai_context'] = self._generate_ai_context(graph_schema)
            
            # 2. PATRONES DE DISEÑO DETECTADOS
            semantic_schema['design_patterns'] = self._detect_design_patterns(graph_schema)
            
            # 3. RECOMENDACIONES DE CONSULTA
            semantic_schema['query_recommendations'] = self._generate_query_recommendations(graph_schema)
            
            # 4. METADATA DE DOMINIO
            semantic_schema['domain_metadata'] = self._extract_domain_metadata(graph_schema)
            
            return semantic_schema
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error agregando metadata semántica: {e}")
            return graph_schema

    # =====================================================
    # 🧠 MÉTODOS AUXILIARES SEMÁNTICOS
    # =====================================================
    
    def _infer_semantic_type(self, column_name: str, column_type: str) -> str:
        """Infiere el tipo semántico de una columna"""
        col_name_lower = column_name.lower()
        col_type_lower = str(column_type).lower()
        
        # Identificadores
        if col_name_lower in ['id', 'uuid', 'guid'] or col_name_lower.endswith('_id'):
            return 'identifier'
        
        # Temporales
        if any(t in col_type_lower for t in ['timestamp', 'date', 'time']):
            return 'temporal'
        
        # Geográficos
        if any(g in col_name_lower for g in ['lat', 'lng', 'latitude', 'longitude', 'address', 'city', 'country']):
            return 'geographic'
        
        # Texto
        if any(t in col_type_lower for t in ['varchar', 'text', 'char']):
            return 'text'
        
        # Numéricos
        if any(n in col_type_lower for n in ['int', 'numeric', 'decimal', 'float']):
            return 'numeric'
        
        # Booleanos
        if 'boolean' in col_type_lower:
            return 'boolean'
        
        return 'unknown'

    def _is_identifier_column(self, column_name: str, column_info: Dict[str, Any]) -> bool:
        """Determina si una columna es un identificador"""
        col_name_lower = column_name.lower()
        
        # Nombres típicos de ID
        if col_name_lower in ['id', 'uuid', 'guid']:
            return True
        
        # Columnas que terminan en _id
        if col_name_lower.endswith('_id'):
            return True
        
        # Verificar si es primary key
        if column_info.get('primary_key', False):
            return True
        
        return False

    def _is_temporal_column(self, column_type: str) -> bool:
        """Determina si una columna es temporal"""
        col_type_lower = str(column_type).lower()
        temporal_types = ['timestamp', 'date', 'time', 'datetime']
        return any(t in col_type_lower for t in temporal_types)

    def _is_geographic_column(self, column_name: str, column_type: str) -> bool:
        """Determina si una columna es geográfica"""
        col_name_lower = column_name.lower()
        geographic_names = ['lat', 'lng', 'latitude', 'longitude', 'address', 'city', 'country', 'postal_code']
        return any(g in col_name_lower for g in geographic_names)

    def _infer_table_semantic_category(self, table_name: str) -> str:
        """Infiere la categoría semántica de una tabla"""
        table_lower = table_name.lower()
        
        # Categorías principales
        if any(word in table_lower for word in ['user', 'member', 'customer']):
            return 'user_management'
        elif any(word in table_lower for word in ['club', 'business', 'store']):
            return 'business_entity'
        elif any(word in table_lower for word in ['product', 'item', 'service']):
            return 'product_catalog'
        elif any(word in table_lower for word in ['order', 'transaction', 'purchase']):
            return 'transactions'
        elif any(word in table_lower for word in ['blog', 'post', 'article', 'content']):
            return 'content_management'
        elif any(word in table_lower for word in ['country', 'city', 'location']):
            return 'geography'
        elif any(word in table_lower for word in ['tag', 'category', 'classification']):
            return 'taxonomy'
        elif any(word in table_lower for word in ['image', 'media', 'file']):
            return 'media'
        elif any(word in table_lower for word in ['setting', 'config', 'preference']):
            return 'configuration'
        else:
            return 'general'

    def _is_business_entity(self, table_name: str) -> bool:
        """Determina si una tabla representa una entidad de negocio"""
        business_tables = ['clubs', 'businesses', 'stores', 'companies', 'organizations']
        return table_name.lower() in business_tables

    def _has_audit_fields(self, columns: Dict[str, Any]) -> bool:
        """Determina si una tabla tiene campos de auditoría"""
        audit_fields = ['created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at']
        column_names = [col.lower() for col in columns.keys()]
        return any(field in column_names for field in audit_fields)

    def _classify_entity_type(self, table_name: str, table_info: Dict[str, Any]) -> str:
        """Clasifica el tipo de entidad de una tabla"""
        semantic_category = table_info.get('semantic_category', 'unknown')
        
        if semantic_category == 'user_management':
            return 'person'
        elif semantic_category == 'business_entity':
            return 'organization'
        elif semantic_category == 'product_catalog':
            return 'product'
        elif semantic_category == 'transactions':
            return 'event'
        elif semantic_category == 'content_management':
            return 'content'
        elif semantic_category == 'geography':
            return 'location'
        elif semantic_category == 'taxonomy':
            return 'concept'
        elif semantic_category == 'media':
            return 'resource'
        else:
            return 'entity'

    def _classify_relationship_type(self, source_table: str, target_table: str) -> str:
        """Clasifica el tipo de relación entre dos tablas"""
        source_lower = source_table.lower()
        target_lower = target_table.lower()
        
        # Relaciones jerárquicas
        if 'country' in source_lower and 'city' in target_lower:
            return 'hierarchical_contains'
        elif 'city' in source_lower and 'club' in target_lower:
            return 'hierarchical_contains'
        
        # Relaciones de pertenencia
        if source_lower.endswith('s') and target_lower.endswith('s'):
            return 'many_to_many'
        elif source_lower.endswith('s') and not target_lower.endswith('s'):
            return 'one_to_many'
        else:
            return 'association'

    def _infer_cardinality(self, source_table: str, target_table: str, all_tables: Dict[str, Any]) -> str:
        """Infiere la cardinalidad de la relación"""
        # Lógica simplificada - se puede mejorar
        return 'many_to_one'  # Por defecto

    def _build_entity_hierarchy(self, relationships: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Construye la jerarquía de entidades"""
        hierarchy = {}
        
        for rel in relationships:
            if rel.get('relationship_type') == 'hierarchical_contains':
                source = rel['source_table']
                target = rel['target_table']
                
                if source not in hierarchy:
                    hierarchy[source] = []
                hierarchy[source].append(target)
        
        return hierarchy

    def _build_relationship_matrix(self, relationships: List[Dict[str, Any]], table_names: List[str]) -> Dict[str, Any]:
        """Construye la matriz de relaciones entre tablas"""
        matrix = {}
        
        for table in table_names:
            matrix[table] = {}
            for other_table in table_names:
                matrix[table][other_table] = []
        
        for rel in relationships:
            source = rel['source_table']
            target = rel['target_table']
            
            if source in matrix and target in matrix[source]:
                matrix[source][target].append(rel)
        
        return matrix

    def _generate_ai_context(self, graph_schema: Dict[str, Any]) -> str:
        """Genera contexto relacional para la AI"""
        try:
            entities = graph_schema.get('entities', {})
            relationships = graph_schema.get('relationships', [])
            
            context = "ESTRUCTURA DE BASE DE DATOS CON RELACIONES:\n\n"
            
            # Entidades principales
            context += "ENTIDADES PRINCIPALES:\n"
            for table_name, entity_info in entities.items():
                entity_type = entity_info.get('type', 'entity')
                semantic_category = entity_info.get('semantic_category', 'unknown')
                context += f"- {table_name} ({entity_type}): {semantic_category}\n"
            
            context += "\nRELACIONES CLAVE:\n"
            for rel in relationships[:10]:  # Top 10 relaciones
                source = rel['source_table']
                target = rel['target_table']
                rel_type = rel['relationship_type']
                context += f"- {source} → {target} ({rel_type})\n"
            
            context += "\nPATRONES DE DISEÑO:\n"
            context += "- Sistema jerárquico: Países → Ciudades → Clubs\n"
            context += "- Relaciones many-to-many: Clubs ↔ Amenities, Posts ↔ Tags\n"
            context += "- Entidades de negocio con metadata rica (reviews, imágenes, horarios)\n"
            context += "- Sistema de contenido multilingüe con categorías y tags\n"
            
            return context
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error generando contexto AI: {e}")
            return "Error generando contexto"

    def _detect_design_patterns(self, graph_schema: Dict[str, Any]) -> List[str]:
        """Detecta patrones de diseño en el schema"""
        patterns = []
        
        entities = graph_schema.get('entities', {})
        relationships = graph_schema.get('relationships', [])
        
        # Patrón de auditoría
        audit_tables = [name for name, info in entities.items() 
                       if info.get('audit_fields', False)]
        if audit_tables:
            patterns.append(f"Audit Pattern: {len(audit_tables)} tablas con campos de auditoría")
        
        # Patrón de soft delete
        soft_delete_tables = [name for name, info in entities.items() 
                             if 'deleted_at' in [col.lower() for col in info.get('properties', [])]]
        if soft_delete_tables:
            patterns.append(f"Soft Delete Pattern: {len(soft_delete_tables)} tablas")
        
        # Patrón de jerarquía geográfica
        geo_hierarchy = [rel for rel in relationships 
                        if rel.get('relationship_type') == 'hierarchical_contains']
        if geo_hierarchy:
            patterns.append(f"Geographic Hierarchy Pattern: {len(geo_hierarchy)} niveles")
        
        # Patrón de tags
        tag_tables = [name for name in entities.keys() if 'tag' in name.lower()]
        if tag_tables:
            patterns.append(f"Tagging Pattern: {len(tag_tables)} tablas de tags")
        
        return patterns

    def _generate_query_recommendations(self, graph_schema: Dict[str, Any]) -> List[str]:
        """Genera recomendaciones de consultas basadas en el grafo"""
        recommendations = []
        
        entities = graph_schema.get('entities', {})
        relationships = graph_schema.get('relationships', [])
        
        # Consultas de jerarquía geográfica
        geo_entities = [name for name, info in entities.items() 
                       if info.get('semantic_category') == 'geography']
        if len(geo_entities) >= 2:
            recommendations.append("Consulta jerárquica: Encuentra clubs por país → ciudad")
        
        # Consultas de entidades de negocio
        business_entities = [name for name, info in entities.items() 
                           if info.get('business_entity', False)]
        if business_entities:
            recommendations.append("Consulta de negocio: Filtra clubs por amenities, rating, horarios")
        
        # Consultas de contenido
        content_entities = [name for name, info in entities.items() 
                          if info.get('semantic_category') == 'content_management']
        if content_entities:
            recommendations.append("Consulta de contenido: Busca posts por categorías y tags")
        
        # Consultas de productos
        product_entities = [name for name, info in entities.items() 
                          if info.get('semantic_category') == 'product_catalog']
        if product_entities:
            recommendations.append("Consulta de productos: Filtra por categorías y vendor")
        
        return recommendations

    def _extract_domain_metadata(self, graph_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Extrae metadata específica del dominio"""
        domain_metadata = {
            'business_domain': 'cannabis_clubs',
            'geographic_scope': 'international',
            'content_languages': ['en', 'es', 'fr'],
            'main_entities': [],
            'business_processes': []
        }
        
        entities = graph_schema.get('entities', {})
        
        # Entidades principales del negocio
        business_entities = [name for name, info in entities.items() 
                           if info.get('business_entity', False)]
        domain_metadata['main_entities'] = business_entities
        
        # Procesos de negocio detectados
        if 'clubs' in entities and 'users' in entities:
            domain_metadata['business_processes'].append('club_membership_management')
        
        if 'products' in entities and 'clubs' in entities:
            domain_metadata['business_processes'].append('product_catalog_management')
        
        if 'blog_posts' in entities:
            domain_metadata['business_processes'].append('content_management')
        
        return domain_metadata

    def _generate_enriched_fingerprint(self, semantic_schema: Dict[str, Any]) -> str:
        """Genera un fingerprint del schema enriquecido"""
        try:
            # Crear un hash del schema enriquecido
            import hashlib
            import json
            
            # Serializar el schema (excluyendo campos que pueden cambiar)
            fingerprint_data = {
                'entities_count': len(semantic_schema.get('entities', {})),
                'relationships_count': len(semantic_schema.get('relationships', [])),
                'entity_types': list(set(entity.get('type', 'unknown') 
                                      for entity in semantic_schema.get('entities', {}).values())),
                'semantic_categories': list(set(entity.get('semantic_category', 'unknown') 
                                             for entity in semantic_schema.get('entities', {}).values())),
                'design_patterns': semantic_schema.get('design_patterns', []),
                'domain_metadata': semantic_schema.get('domain_metadata', {})
            }
            
            # Convertir a JSON y generar hash
            json_str = json.dumps(fingerprint_data, sort_keys=True)
            hash_object = hashlib.sha256(json_str.encode())
            return f"graph_rag_pro_{hash_object.hexdigest()[:16]}"
            
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error generando fingerprint enriquecido: {e}")
            return "graph_rag_pro_error"

    def get_cache_entry(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCache]:
        """
        Obtiene la entrada completa del cache.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            
        Returns:
            Entrada del cache o None si no existe
        """
        try:
            cache_entry = self.db.query(DetailedSchemaCache).filter(
                and_(
                    DetailedSchemaCache.user_id == user_id,
                    DetailedSchemaCache.db_id == db_id
                )
            ).first()
            
            if cache_entry:
                # Actualizar último acceso
                cache_entry.last_accessed = datetime.now(timezone.utc)
                self.db.commit()
                
                logger.info(f"[SchemaCacheService] 🔥 Cache HIT DB para entrada completa {db_id}")
                return cache_entry
            else:
                logger.debug(f"[SchemaCacheService] ❌ Cache MISS DB para entrada completa {db_id}")
                return None
                
        except Exception as e:
            logger.error(f"[SchemaCacheService] ❌ Error obteniendo entrada del cache: {e}")
            return None
