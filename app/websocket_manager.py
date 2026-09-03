import json
from typing import Dict
from fastapi import WebSocket
import redis.asyncio as aioredis
from app.config import settings

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_personal_message(self, message: dict, client_id: str):
        websocket = self.active_connections.get(client_id)
        if websocket:
            await websocket.send_text(json.dumps(message))

ws_manager = WebSocketManager()

async def redis_pubsub_listener():
    """Фоновая корутина для чтения сообщений из Redis и отправки в WebSocket"""
    r = aioredis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("task_updates")

    async for message in pubsub.listen():
        if message["type"] == "message":
            data = json.loads(message["data"])
            client_id = data.get("client_id")
            if client_id:
                await ws_manager.send_personal_message(data, client_id)