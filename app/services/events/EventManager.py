from typing import Dict, Set, Optional
import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from redis.asyncio import Redis
from app.core.config import settings

class EventManager:
    """
    Manages WebSocket connections for real-time log events.
    
    Separation of Concerns: Handles only WS lifecycle and broadcasting.
    Uses existing Redis pub/sub for event distribution (no direct coupling to LogService).
    Singleton pattern for global access; initialized with shared Redis client.
    
    Best Practices:
    - Async-friendly with background listeners per vault.
    - Graceful disconnect handling.
    - No blocking operations; uses asyncio for concurrency.
    - Type hints for clarity and IDE support.
    - Logs errors without crashing (add structured logging in prod).
    """
    
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.connections: Dict[str, Set[WebSocket]] = {}  # vault_id -> set of active WS
        self.listeners: Dict[str, asyncio.Task] = {}  # vault_id -> pubsub listener task

    async def connect(self, websocket: WebSocket, vault_id: int, prefixes: list[str]):
        """
        Connect a WebSocket client and subscribe to vault events.
        
        Args:
            websocket: The WebSocket connection.
            vault_id: The vault to subscribe to.
            prefixes: Event type prefixes for client-side filtering (logged for audit).
        """
        # await websocket.accept()  # FastAPI auto-accepts; manual accept causes ASGI error
        print(f"WS connected for vault {vault_id} with prefixes {prefixes}")
        
        if vault_id not in self.connections:
            self.connections[vault_id] = set()
        
        self.connections[vault_id].add(websocket)
        
        # Start vault listener if first connection
        if vault_id not in self.listeners:
            self.listeners[vault_id] = asyncio.create_task(
                self._listen_for_vault_events(vault_id)
            )
        
        # Send subscription confirmation
        await websocket.send_json({
            "type": "subscribe_ack",
            "vault_id": vault_id,
            "prefixes": prefixes
        })
        
        # Start heartbeat for this connection
        asyncio.create_task(self._heartbeat(websocket))
        
    async def _listen_for_vault_events(self, vault_id: int):
        """
        Background task: Listen to Redis channel for new logs and broadcast to WS clients.
        
        Args:
            vault_id: The vault to listen for.
        """
        channel = f"new_log:vault_{vault_id}"
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message.get("type") == "message":
                    try:
                        log_data = json.loads(message["data"])
                        await self._broadcast_to_vault(vault_id, log_data)
                    except json.JSONDecodeError:
                        print(f"Invalid JSON in Redis message for vault {vault_id}")
        except Exception as e:
            print(f"Redis listener error for vault {vault_id}: {e}")
        finally:
            await pubsub.unsubscribe(channel)
            if vault_id in self.listeners:
                self.listeners.pop(vault_id, None)
    
    async def _broadcast_to_vault(self, vault_id: int, log_data: dict):
        """
        Broadcast a new log to all connected WS for a vault.
        
        Args:
            vault_id: The vault ID.
            log_data: The log entry as dict.
        """
        if vault_id not in self.connections:
            return
            
        disconnected = []
        for ws in list(self.connections[vault_id]):
            try:
                await ws.send_json({
                    "type": "new_log",
                    "log": log_data
                })
            except Exception as e:
                print(f"Failed to send to WS for vault {vault_id}: {e}")
                disconnected.append(ws)
        
        # Clean up disconnected
        for ws in disconnected:
            self.connections[vault_id].discard(ws)
        
        if not self.connections[vault_id]:
            del self.connections[vault_id]
            if vault_id in self.listeners:
                self.listeners[vault_id].cancel()
    
    async def _heartbeat(self, websocket: WebSocket):
        """
        Send periodic pings to keep WS alive (respond to client pings implicitly by staying open).
        """
        while True:
            try:
                await asyncio.sleep(25)  # 25s interval < 30s client ping
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"type": "pong"})
            except Exception:
                break  # Connection closed
    
    async def disconnect(self, websocket: WebSocket, vault_id: int):
        """
        Disconnect a WS client from a vault.
        
        Args:
            websocket: The WS to disconnect.
            vault_id: The subscribed vault.
        """
        if vault_id in self.connections:
            self.connections[vault_id].discard(websocket)
            if not self.connections[vault_id]:
                del self.connections[vault_id]
                if vault_id in self.listeners:
                    self.listeners[vault_id].cancel()
                    del self.listeners[vault_id]
        
        print(f"WS disconnected from vault {vault_id}")