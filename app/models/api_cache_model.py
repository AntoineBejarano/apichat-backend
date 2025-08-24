#!/usr/bin/env python3
"""
APICache - Modelo para cache de definiciones OpenAPI
────────────────────────────────────────────────────
Implementa:
- Cache comprimido de definiciones OpenAPI
- Fingerprints para invalidación automática
- Estados de generación y cache
- Estadísticas de uso y compresión
"""

from sqlalchemy import Column, String, Text, BigInteger, Integer, ForeignKey, TIMESTAMP, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.models.base_model import BaseTable
from uuid import uuid4
from enum import IntEnum


class APICacheStatus(IntEnum):
    """Estados del cache de API"""
    PENDING = 0      # Pendiente de generación
    GENERATING = 1   # Generando cache
    READY = 2        # Cache listo
    ERROR = 3        # Error en generación
    UPDATING = 4     # Actualizando cache
    OBSOLETE = 5     # Cache obsoleto


class APICache(BaseTable):
    """
    Modelo para cache de definiciones OpenAPI de apps.
    
    Características:
    - Cache comprimido con Gzip
    - Fingerprints para invalidación automática
    - Estados de generación y cache
    - Estadísticas de uso y compresión
    - TTL configurable por tipo de API
    """
    
    __tablename__ = "api_cache"
    
    # Identificadores
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=False)
    
    # Fingerprints para invalidación automática
    fingerprint = Column(Text, nullable=False, comment="Fingerprint completo del OpenAPI")
    fingerprint_light = Column(Text, nullable=False, comment="Fingerprint ligero para cambios estructurales")
    
    # OpenAPI comprimido y optimizado
    openapi_compressed = Column(Text, nullable=False, comment="OpenAPI comprimido con Gzip")
    openapi_original_size = Column(BigInteger, nullable=False, comment="Tamaño original del OpenAPI en bytes")
    openapi_compressed_size = Column(BigInteger, nullable=False, comment="Tamaño comprimido en bytes")
    
    # Metadatos del cache
    status = Column(Integer, nullable=False, default=APICacheStatus.PENDING.value, comment="Estado del cache")
    enrichment_level = Column(Integer, nullable=False, default=1, comment="Nivel de enriquecimiento (1-3)")
    
    # Estadísticas de uso
    access_count = Column(BigInteger, nullable=False, default=0, comment="Número de accesos al cache")
    last_accessed = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), comment="Último acceso")
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), comment="Fecha de creación")
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), onupdate=func.now(), comment="Fecha de actualización")
    
    # Metadatos adicionales
    version = Column(String(50), nullable=True, comment="Versión del OpenAPI")
    title = Column(String(255), nullable=True, comment="Título de la API")
    description = Column(Text, nullable=True, comment="Descripción de la API")
    
    # Configuración de cache
    ttl_hours = Column(Integer, nullable=False, default=24, comment="TTL en horas")
    compression_ratio = Column(Integer, nullable=True, comment="Ratio de compresión (porcentaje)")
    
    # Errores y warnings
    last_error = Column(Text, nullable=True, comment="Último error encontrado")
    warnings = Column(JSONB, nullable=True, comment="Warnings del parsing")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('user_id', 'app_id', name='uq_api_cache_user_app'),
        Index('idx_api_cache_fingerprint', 'fingerprint'),
        Index('idx_api_cache_user_app', 'user_id', 'app_id'),
        Index('idx_api_cache_last_accessed', 'last_accessed'),
        Index('idx_api_cache_status', 'status'),
        Index('idx_api_cache_fingerprint_light', 'fingerprint_light'),
        Index('idx_api_cache_enrichment_level', 'enrichment_level'),
        Index('idx_api_cache_ttl', 'ttl_hours'),
        Index('idx_api_cache_compression', 'compression_ratio'),
        Index('idx_api_cache_version', 'version'),
        Index('idx_api_cache_title', 'title'),
        Index('idx_api_cache_created_at', 'created_at'),
        Index('idx_api_cache_updated_at', 'updated_at'),
        Index('idx_api_cache_access_count', 'access_count'),
        Index('idx_api_cache_error_status', 'status', 'last_error'),
        Index('idx_api_cache_user_status', 'user_id', 'status'),
        Index('idx_api_cache_app_status', 'app_id', 'status'),
        Index('idx_api_cache_obsolete', 'status', 'updated_at'),
        Index('idx_api_cache_performance', 'access_count', 'last_accessed'),
        Index('idx_api_cache_compression_efficiency', 'openapi_original_size', 'openapi_compressed_size'),
    )
    
    def __repr__(self):
        return f"<APICache(id={self.id}, user_id={self.user_id}, app_id={self.app_id}, status={self.status})>"
    
    @property
    def is_ready(self) -> bool:
        """Verifica si el cache está listo para usar"""
        return self.status == APICacheStatus.READY.value
    
    @property
    def is_obsolete(self) -> bool:
        """Verifica si el cache está obsoleto"""
        return self.status == APICacheStatus.OBSOLETE.value
    
    @property
    def compression_efficiency(self) -> float:
        """Calcula la eficiencia de compresión"""
        if self.openapi_original_size == 0:
            return 0.0
        return ((self.openapi_original_size - self.openapi_compressed_size) / self.openapi_original_size) * 100
    
    @property
    def age_hours(self) -> int:
        """Calcula la edad del cache en horas"""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        age = now - self.updated_at
        return int(age.total_seconds() / 3600)
    
    @property
    def is_expired(self) -> bool:
        """Verifica si el cache ha expirado"""
        return self.age_hours > self.ttl_hours
    
    def mark_as_accessed(self):
        """Marca el cache como accedido"""
        self.access_count += 1
        self.last_accessed = func.now()
    
    def mark_as_obsolete(self):
        """Marca el cache como obsoleto"""
        self.status = APICacheStatus.OBSOLETE.value
        self.updated_at = func.now()
    
    def get_status_display(self) -> str:
        """Obtiene el estado en formato legible"""
        status_map = {
            APICacheStatus.PENDING: "Pendiente",
            APICacheStatus.GENERATING: "Generando",
            APICacheStatus.READY: "Listo",
            APICacheStatus.ERROR: "Error",
            APICacheStatus.UPDATING: "Actualizando",
            APICacheStatus.OBSOLETE: "Obsoleto"
        }
        return status_map.get(APICacheStatus(self.status), "Desconocido")
