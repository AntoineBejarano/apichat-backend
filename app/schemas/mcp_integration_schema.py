from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal
from datetime import datetime

class MCPIntegrationMetadata(BaseModel):
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[list[str]] = None
    env: Optional[Dict[str, str]] = None
    endpoints: Optional[Dict[str, str]] = Field(default_factory=dict)

class MCPIntegrationBase(BaseModel):
    name: str
    mcp_type: Literal["http", "stdio", "websocket"]
    mcp_metadata: MCPIntegrationMetadata

class MCPIntegrationUpdate(BaseModel):
    name: Optional[str] = None
    mcp_type: Optional[Literal["http", "stdio", "websocket"]] = None
    mcp_metadata: Optional[MCPIntegrationMetadata] = None

    class Config:
        schema_extra = {
            "example": {
                "name": "GitHub MCP",
                "mcp_type": "http",
                "mcp_metadata": {
                    "url": "http://localhost:3000",
                    "endpoints": {
                        "list_tools": "/api/v1/tools",
                        "call_tool": "/api/v1/execute"
                    },
                    "env": {
                        "GITHUB_PERSONAL_ACCESS_TOKEN": "xxxxx"
                    }
                }
            }
        }

class MCPIntegrationInDB(MCPIntegrationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class MCPIntegrationCreate(MCPIntegrationBase):
    class Config:
        schema_extra = {
            "example": {
                "name": "GitHub MCP",
                "mcp_type": "http",
                "mcp_metadata": {
                    "url": "https://mcp-server-github.com",
                    "endpoints": {
                        "list_tools": "/api/v1/tools",
                        "call_tool": "/api/v1/execute"
                    },
                    "env": {
                        "GITHUB_TOKEN": "abc123"
                    }
                }
            }
        }
