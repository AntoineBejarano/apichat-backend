# app/services/mcp/http_connector.py
import requests

class HTTPMCPConnector(BaseMCPConnector):
    def list_tools(self):
        url = self.metadata.url + self.metadata.endpoints.get("list_tools", "/listTools")
        return requests.get(url, headers=self._auth_header()).json()

    def call_tool(self, name: str, parameters: dict):
        url = self.metadata.url + self.metadata.endpoints.get("call_tool", "/callTool")
        return requests.post(url, json={"name": name, "args": parameters}, headers=self._auth_header()).json()

    def _auth_header(self):
        token = self.metadata.env.get("GITHUB_PERSONAL_ACCESS_TOKEN")
        return {"Authorization": f"Bearer {token}"} if token else {}
