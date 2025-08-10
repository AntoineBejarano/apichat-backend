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


class DetailedSchemaCacheService(BaseService):
    """
    Servicio de cache multi-capa para esquemas de base de datos.
    
    Implementa:
    - L1: Cache en memoria (fingerprint_light)
    - L2: Cache en BD (snapshot completo)  
    - L3: Invalidación inteligente
    """
    
    def __init__(self, factory):
        super().__init__(factory)
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
    
    # =====================================================
    # OPERACIONES PRINCIPALES
    # =====================================================
    
    def get_schema_cache(self, user_id: UUID, db_id: UUID, current_fingerprint_light: Optional[str] = None) -> Optional[DetailedSchemaCacheResponse]:
        """
        Obtiene cache de schema con validación de fingerprint.
        
        Args:
            user_id: ID del usuario
            db_id: ID de la base de datos
            current_fingerprint_light: Fingerprint actual para validación
            
        Returns:
            Cache válido o None si no existe/está obsoleto
        """
        logger.info(f"[SchemaCacheService] 🔍 Buscando cache para user={user_id}, db={db_id}")
        
        # L1: Verificar cache en memoria primero
        memory_cache = self._get_memory_cache(user_id, db_id)
        if memory_cache and current_fingerprint_light:
            if memory_cache['fingerprint_light'] == current_fingerprint_light:
                logger.info("[SchemaCacheService] ⚡ Cache L1 hit (memoria)")
                # Crear respuesta mínima desde memoria
                return self._create_minimal_response_from_memory(user_id, db_id, memory_cache)
        
        # L2: Buscar en base de datos
        cache_entry = self.db.query(DetailedSchemaCache).filter(
            and_(
                DetailedSchemaCache.user_id == user_id,
                DetailedSchemaCache.db_id == db_id
            )
        ).first()
        
        if not cache_entry:
            logger.info("[SchemaCacheService] ❌ No se encontró cache en BD")
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
        
        # Actualizar L1 cache
        self._set_memory_cache(user_id, db_id, cache_entry.fingerprint_light, cache_entry.compact)
        
        logger.info(f"[SchemaCacheService] ✅ Cache L2 hit (BD) - {cache_entry.table_count} tablas")
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
        
        # Buscar entrada existente
        existing = self.db.query(DetailedSchemaCache).filter(
            and_(
                DetailedSchemaCache.user_id == user_id,
                DetailedSchemaCache.db_id == db_id
            )
        ).first()
        
        if existing:
            # Actualizar existente
            logger.info("[SchemaCacheService] 🔄 Actualizando cache existente")
            existing.fingerprint = fingerprint_full
            existing.fingerprint_light = fingerprint_light
            existing.snapshot = snapshot.model_dump(mode="json")
            existing.compact = compact_schema
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
    
    def invalidate_cache(self, user_id: UUID, db_id: UUID) -> bool:
        """
        Invalida cache para una BD específica.
        
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
        
        # Eliminar de L2
        deleted_count = self.db.query(DetailedSchemaCache).filter(
            and_(
                DetailedSchemaCache.user_id == user_id,
                DetailedSchemaCache.db_id == db_id
            )
        ).delete()
        
        self.db.commit()
        
        logger.info(f"[SchemaCacheService] ✅ Cache invalidado - {deleted_count} entradas eliminadas")
        return deleted_count > 0
    
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
