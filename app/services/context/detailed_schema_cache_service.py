from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

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
    
    # =====================================================
    # OPERACIONES PRINCIPALES
    # =====================================================
    
    async def get_schema_cache(self, user_id: UUID, db_id: UUID, current_fingerprint_light: Optional[str] = None) -> Optional[DetailedSchemaCacheResponse]:
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
                auto_generated = await self._generate_schema_automatically(user_id, db_id)
                if auto_generated:
                    logger.info(f"[SchemaCacheService] ✅ Esquema generado automáticamente para DB {db_id}")
                    return auto_generated
                else:
                    logger.warning(f"[SchemaCacheService] ⚠️ No se pudo generar esquema automáticamente para DB {db_id}")
                    # 🔧 SOLUCIÓN: Crear un esquema básico de fallback
                    logger.info(f"[SchemaCacheService] 🔧 Creando esquema de fallback para DB {db_id}")
                    fallback_schema = await self._create_fallback_schema(user_id, db_id)
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
    
    async def create_or_update_cache(
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
        
        if existing:
            # Actualizar existente
            logger.info("[SchemaCacheService] 🔄 Actualizando cache existente")
            existing.fingerprint = fingerprint_full
            existing.fingerprint_light = fingerprint_light
            existing.snapshot = snapshot.model_dump(mode="json")
            existing.compact = compact_schema
            if cleaned_schema:
                existing.cleaned_schema = cleaned_schema
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
                snapshot=snapshot.model_dump(mode="json"),
                compact=compact_schema,
                cleaned_schema=cleaned_schema,
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
    
    async def _generate_schema_automatically(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        Genera automáticamente un esquema de base de datos cuando no existe en cache.
        
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
                
                # Generar cache
                cache_response = await self.create_or_update_cache(
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
    
    async def _create_fallback_schema(self, user_id: UUID, db_id: UUID) -> Optional[DetailedSchemaCacheResponse]:
        """
        Crea un esquema básico de fallback cuando no se puede generar automáticamente.
        
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
