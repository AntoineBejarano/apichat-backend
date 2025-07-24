import logging
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy.orm import Session

from app.models.mcp_integration_model import MCPIntegration
from app.schemas.mcp_integration_schema import (
    MCPIntegrationCreate,
    MCPIntegrationUpdate,
)

if TYPE_CHECKING:
    from app.core.service_factory import ServiceFactory

logger = logging.getLogger(__name__)


class MCPIntegrationService:
    """CRUD y utilidades para integraciones MCP."""

    def __init__(self, factory: "ServiceFactory") -> None:
        self.db: Session = factory.db
        logger.info("[MCPIntegrationService] Inicializado")

    def create(self, data: MCPIntegrationCreate) -> MCPIntegration:
        logger.info("[MCPIntegrationService] ➕ Creando MCP ‘%s’", data.name)
        mcp = MCPIntegration(
            name=data.name,
            mcp_type=data.mcp_type,
            mcp_metadata=data.mcp_metadata.model_dump(),
        )
        self.db.add(mcp)
        self.db.commit()
        self.db.refresh(mcp)
        return mcp

    def list_all(self) -> List[MCPIntegration]:
        return self.db.query(MCPIntegration).all()

    def get_by_id(self, mcp_id: int) -> Optional[MCPIntegration]:
        return self.db.query(MCPIntegration).filter_by(id=mcp_id).first()

    def update(self, mcp_id: int, data: MCPIntegrationUpdate) -> MCPIntegration:
        mcp = self.get_by_id(mcp_id)
        if not mcp:
            raise ValueError("MCP integration not found")

        if data.name is not None:
            mcp.name = data.name
        if data.mcp_type is not None:
            mcp.mcp_type = data.mcp_type
        if data.mcp_metadata is not None:
            mcp.mcp_metadata = data.mcp_metadata.model_dump()
        mcp.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(mcp)
        return mcp

    def delete(self, mcp_id: int) -> bool:
        mcp = self.get_by_id(mcp_id)
        if not mcp:
            raise ValueError("MCP integration not found")
        self.db.delete(mcp)
        self.db.commit()
        return True
