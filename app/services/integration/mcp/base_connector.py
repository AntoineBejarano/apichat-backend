# app/services/mcp/base_connector.py
class BaseMCPConnector:
    def __init__(self, metadata: dict):
        self.metadata = metadata

    def list_tools(self) -> list[dict]:
        raise NotImplementedError

    def call_tool(self, name: str, parameters: dict) -> dict:
        raise NotImplementedError
