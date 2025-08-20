# app/services/mcp/websocket_connector.py

import asyncio
import websockets
import json
import logging
from app.services.mcp.base_connector import BaseMCPConnector

logger = logging.getLogger(__name__)

class WebSocketMCPConnector(BaseMCPConnector):
    def __init__(self, metadata):
        super().__init__(metadata)
        self.url = metadata.url
        self.endpoints = metadata.endpoints or {}
        self.auth_token = metadata.env.get("AUTH_TOKEN")

    async def _send_and_receive(self, payload: dict) -> dict:
        headers = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        async with websockets.connect(self.url, extra_headers=headers) as websocket:
            logger.debug(f"📤 Enviando mensaje WebSocket: {payload}")
            await websocket.send(json.dumps(payload))

            response = await websocket.recv()
            logger.debug(f"📥 Respuesta recibida: {response}")
            return json.loads(response)

    def list_tools(self) -> list[dict]:
        """🔧 FASE 1: Método sync compatible con loops activos"""
        payload = {
            "action": self.endpoints.get("list_tools", "listTools")
        }
        
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                # Si estamos en un loop activo, crear una tarea futura
                future = asyncio.ensure_future(self._send_and_receive(payload))
                # Ejecutar en el loop actual
                return asyncio.run_coroutine_threadsafe(future, loop).result()
            else:
                # Si no hay loop activo, usar asyncio.run
                return asyncio.run(self._send_and_receive(payload))
        except RuntimeError:
            # No hay loop activo, usar asyncio.run
            return asyncio.run(self._send_and_receive(payload))

    def call_tool(self, name: str, parameters: dict) -> dict:
        """🔧 FASE 1: Método sync compatible con loops activos"""
        payload = {
            "action": self.endpoints.get("call_tool", "callTool"),
            "name": name,
            "args": parameters
        }
        
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                # Si estamos en un loop activo, crear una tarea futura
                future = asyncio.ensure_future(self._send_and_receive(payload))
                # Ejecutar en el loop actual
                return asyncio.run_coroutine_threadsafe(future, loop).result()
            else:
                # Si no hay loop activo, usar asyncio.run
                return asyncio.run(self._send_and_receive(payload))
        except RuntimeError:
            # No hay loop activo, usar asyncio.run
            return asyncio.run(self._send_and_receive(payload))
