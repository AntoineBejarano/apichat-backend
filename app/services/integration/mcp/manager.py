# app/services/mcp/manager.py
from app.services.mcp.connector_factory import get_connector

class MCPConnectorManager:
    def __init__(self, integration_metadata: dict):
        self.connector = get_connector(integration_metadata)

    def get_tools(self) -> list[dict]:
        return self.connector.list_tools()

    def execute_tool(self, tool_name: str, parameters: dict) -> dict:
        return self.connector.call_tool(tool_name, parameters)
