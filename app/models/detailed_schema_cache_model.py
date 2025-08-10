from sqlalchemy import Column, String, Integer, Text, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import TIMESTAMP
from sqlalchemy.sql import func
from uuid import UUID as PyUUID, uuid4
from typing import Dict, Any, Optional, List
from datetime import datetime
from pydantic import BaseModel, Field
from enum import IntEnum

from app.models.base_model import BaseTable


class EnrichmentLevel(IntEnum):
    """Niveles de enriquecimiento del schema cache"""
    BASIC = 1           # Solo tablas y columnas básicas
    WITH_RELATIONS = 2  # Incluye FKs y relaciones
    WITH_STATISTICS = 3 # Incluye estadísticas e índices


class DetailedSchemaCache(BaseTable):
    """
    Cache multi-capa para esquemas de base de datos.
    
    Proporciona:
    - L1: compact (para prompts AI)  
    - L2: detailed (para validación/rewrites)
    - L3: fingerprint (para invalidación barata)
    """
    __tablename__ = "detailed_schema_cache"
    
    # 🔑 Identificadores
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    db_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # 🔍 Fingerprints para invalidación
    fingerprint = Column(Text, nullable=False)          # Hash completo
    fingerprint_light = Column(Text, nullable=False)    # Hash ligero (solo nombres)
    
    # 📊 Snapshots del esquema
    snapshot = Column(JSONB, nullable=False)            # Schema detallado completo
    compact = Column(Text, nullable=False)              # Schema compacto para AI
    
    # ⚡ Metadatos de performance
    table_count = Column(Integer, nullable=False, default=0)
    total_columns = Column(Integer, nullable=False, default=0)
    enrichment_level = Column(Integer, nullable=False, default=EnrichmentLevel.BASIC)
    
    # 🕒 Timestamps
    generated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    last_accessed = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    enriched_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # 🔒 Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'db_id', name='uq_schema_cache_user_db'),
        Index('idx_schema_cache_user_db', 'user_id', 'db_id'),
        Index('idx_schema_cache_fingerprint', 'fingerprint_light'),
        Index('idx_schema_cache_accessed', 'last_accessed'),
        Index('idx_schema_cache_enrichment', 'enrichment_level', 'generated_at'),
    )


# =====================================================
# ESQUEMAS PYDANTIC
# =====================================================

class SchemaSnapshot(BaseModel):
    """Estructura del snapshot detallado del esquema"""
    tables: Dict[str, Dict[str, Any]] = Field(description="Tablas con sus columnas y metadatos")
    relations: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Foreign keys y relaciones")
    indexes: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Índices por tabla")
    statistics: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Estadísticas de tablas")
    dialect: Optional[str] = Field(None, description="Dialecto de la BD (postgresql, mysql, etc.)")
    version: str = Field(default="1.0", description="Versión del formato de snapshot")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DetailedSchemaCacheCreate(BaseModel):
    """Schema para crear entrada de cache"""
    user_id: PyUUID
    db_id: PyUUID
    fingerprint: str
    fingerprint_light: str
    snapshot: SchemaSnapshot
    compact: str
    table_count: int = 0
    total_columns: int = 0
    enrichment_level: EnrichmentLevel = EnrichmentLevel.BASIC


class DetailedSchemaCacheResponse(BaseModel):
    """Schema para respuesta de cache"""
    id: PyUUID
    user_id: PyUUID
    db_id: PyUUID
    fingerprint: str
    fingerprint_light: str
    snapshot: SchemaSnapshot
    compact: str
    table_count: int
    total_columns: int
    enrichment_level: EnrichmentLevel
    generated_at: datetime
    last_accessed: datetime
    enriched_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True
    }


class DetailedSchemaCacheUpdate(BaseModel):
    """Schema para actualizar entrada de cache"""
    fingerprint: Optional[str] = None
    fingerprint_light: Optional[str] = None
    snapshot: Optional[SchemaSnapshot] = None
    compact: Optional[str] = None
    table_count: Optional[int] = None
    total_columns: Optional[int] = None
    enrichment_level: Optional[EnrichmentLevel] = None
    enriched_at: Optional[datetime] = None


# =====================================================
# UTILIDADES
# =====================================================

class FingerprintGenerator:
    """Generador de fingerprints para detección de cambios"""
    
    @staticmethod
    def generate_light_fingerprint(table_names: List[str]) -> str:
        """
        Genera fingerprint ligero basado solo en nombres de tablas.
        Útil para detección rápida de cambios estructurales.
        """
        import hashlib
        sorted_tables = sorted(table_names)
        content = "|".join(sorted_tables)
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    @staticmethod
    def generate_full_fingerprint(snapshot: SchemaSnapshot) -> str:
        """
        Genera fingerprint completo basado en todo el schema.
        Detecta cambios en columnas, tipos, constraints, etc.
        """
        import hashlib
        import json
        from datetime import datetime, timezone
        
        def _serialize_datetime(obj):
            """Convierte objetos datetime a strings ISO para serialización JSON"""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: _serialize_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_serialize_datetime(item) for item in obj]
            else:
                return obj
        
        # Serializar snapshot de forma determinística, convirtiendo datetime a strings
        snapshot_dict = snapshot.model_dump()
        serializable_dict = _serialize_datetime(snapshot_dict)
        content = json.dumps(serializable_dict, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content.encode()).hexdigest()[:32]


class CompactSchemaFormatter:
    """Formateador de schema compacto para prompts AI"""
    
    @staticmethod
    def format_for_ai(snapshot: SchemaSnapshot) -> str:
        """
        Convierte snapshot detallado en formato compacto para AI.
        Optimizado para ser conciso pero informativo.
        """
        lines = []
        
        # Header con info general
        lines.append(f"-- DATABASE SCHEMA ({snapshot.dialect or 'unknown'}) --")
        lines.append(f"-- Tables: {len(snapshot.tables)}, Generated: {snapshot.generated_at.strftime('%Y-%m-%d %H:%M')} --")
        lines.append("")
        
        # Tablas ordenadas alfabéticamente
        for table_name in sorted(snapshot.tables.keys()):
            table_info = snapshot.tables[table_name]
            columns = table_info.get('columns', {})
            
            # Nombre de tabla con conteo de columnas
            lines.append(f"📋 {table_name} ({len(columns)} cols)")
            
            # Columnas principales (máximo 8 para mantenerlo compacto)
            col_items = list(columns.items())[:8]
            for col_name, col_info in col_items:
                col_type = col_info.get('type', 'unknown')
                nullable = '' if col_info.get('nullable', True) else ' NOT NULL'
                pk = ' 🔑' if col_info.get('primary_key', False) else ''
                lines.append(f"  • {col_name}: {col_type}{nullable}{pk}")
            
            # Indicar si hay más columnas
            if len(columns) > 8:
                lines.append(f"  ... y {len(columns) - 8} columnas más")
            
            lines.append("")
        
        return "\n".join(lines)
