import uuid
from sqlalchemy import Column, String, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base_model import BaseTable

class DatabaseConnection(BaseTable):
    __tablename__ = "database_connections"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    name = Column(String, nullable=False)
    db_type = Column(String, nullable=False)
    host = Column(String, nullable=False)
    port = Column(Integer, nullable=False)
    database = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 🔧 FASE 1: Pipeline completo de schema con estados y progreso
    schema_status = Column(String, nullable=False, default="pending", 
                          comment="Estado del schema: pending, generating, ready, error, failed")
    
    # 🔧 FASE 1: Campos del pipeline
    current_stage = Column(String, nullable=True, 
                          comment="Stage actual del pipeline: validate_db_access, extract_schema_snapshot, build_graph, generate_chunks, embed_chunks, vector_upsert, finalize_snapshot_active")
    progress_pct = Column(Integer, nullable=True, default=0,
                         comment="Progreso del pipeline (0-100)")
    error_code = Column(String, nullable=True,
                       comment="Código de error si falla el pipeline")
    error_detail = Column(String, nullable=True,
                         comment="Detalle del error si falla el pipeline")
    started_at = Column(DateTime(timezone=True), nullable=True,
                       comment="Cuándo inició el pipeline")
    finished_at = Column(DateTime(timezone=True), nullable=True,
                        comment="Cuándo terminó el pipeline")
    retry_count = Column(Integer, nullable=False, default=0,
                        comment="Número de reintentos del pipeline")
    last_retry_at = Column(DateTime(timezone=True), nullable=True,
                          comment="Cuándo fue el último reintento")

    user = relationship("User", back_populates="databases")
    agent_links = relationship("AgentDatabaseLink", back_populates="database", cascade="all, delete-orphan")
    
    # 🔧 FASE 1: Relación con el pipeline de schema
    schema_pipelines = relationship("SchemaPipeline", back_populates="database", cascade="all, delete-orphan")
    
    # 🔧 FASE 2: Relación con el grafo de schema
    schema_graphs = relationship("SchemaGraph", back_populates="database", cascade="all, delete-orphan")
