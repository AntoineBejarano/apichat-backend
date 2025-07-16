# app/services/mcp/connector_factory.py
from app.services.mcp.http_connector import HTTPMCPConnector
from app.services.mcp.stdio_connector import StdioMCPConnector
from app.schemas.mcp_metadata import MCPMetadata

def get_connector(metadata: dict):
    validated = MCPMetadata(**metadata)

    if validated.mcp_type == "http":
        return HTTPMCPConnector(validated)
    elif validated.mcp_type == "stdio":
        return StdioMCPConnector(validated)
    else:
        raise ValueError(f"MCP type '{validated.mcp_type}' not soportado")
