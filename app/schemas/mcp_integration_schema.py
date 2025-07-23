from pydantic import BaseModel, Field
from typing import Optional, Dict, Literal, List
from datetime import datetime

class MCPIntegrationMetadata(BaseModel):
    url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    endpoints: Optional[Dict[str, str]] = Field(default_factory=dict)

    model_config = {
        "from_attributes": False
    }

class MCPIntegrationBase(BaseModel):
    name: str
    mcp_type: Literal["http", "stdio", "websocket"]
    mcp_metadata: MCPIntegrationMetadata

    model_config = {
        "from_attributes": False
    }

class MCPIntegrationUpdate(BaseModel):
    name: Optional[str] = None
    mcp_type: Optional[Literal["http", "stdio", "websocket"]] = None
    mcp_metadata: Optional[MCPIntegrationMetadata] = None

    model_config = {
        "from_attributes": False,
        "json_schema_extra": {
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
    }

class MCPIntegrationInDB(MCPIntegrationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class MCPIntegrationCreate(MCPIntegrationBase):
    model_config = {
        "from_attributes": False,
        "json_schema_extra": {
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
    }
