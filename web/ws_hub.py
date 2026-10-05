"""
WebSocket Connection Manager and Broadcast Hub for Real-Time Telemetry Streaming.
Maintains active client connections and broadcasts batched log frames and blackboard deltas.
"""

import asyncio
import json
from typing import List, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect


class StreamHub:
    """Manages active WebSockets and broadcasts live telemetry frames."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

    async def broadcast_json(self, message: Dict[str, Any]):
        """Broadcast JSON message to all connected clients."""
        async with self._lock:
            dead_connections = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                if dead in self.active_connections:
                    self.active_connections.remove(dead)

    @property
    def client_count(self) -> int:
        return len(self.active_connections)


ws_hub = StreamHub()
