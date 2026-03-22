# MODULE: backend/api/v1/websocket.py
# TASK:   CHECKLIST.md §2.5 WebSocket Endpoint
# SPEC:   BACKEND.md §5.1.3 (WebSocket)
# PHASE:  2
# STATUS: In Progress

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect
from pydantic import BaseModel

from backend.db.redis_client import get_redis_client

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

DEFAULT_TIMEFRAME = "1m"


class WebSocketMessage(BaseModel):
    """WebSocket message structure."""

    type: str
    data: Optional[dict] = None
    timestamp: str


class ConnectionManager:
    """Manages WebSocket connections per symbol."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, symbol: str, websocket: WebSocket) -> None:
        """Register a new WebSocket connection."""
        await websocket.accept()
        if symbol.upper() not in self._connections:
            self._connections[symbol.upper()] = set()
        self._connections[symbol.upper()].add(websocket)
        logger.info(
            "WebSocket connected",
            extra={
                "symbol": symbol,
                "connections": len(self._connections[symbol.upper()]),
            },
        )

    def disconnect(self, symbol: str, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if symbol.upper() in self._connections:
            self._connections[symbol.upper()].discard(websocket)
            logger.info(
                "WebSocket disconnected",
                extra={
                    "symbol": symbol,
                    "connections": len(self._connections[symbol.upper()]),
                },
            )

    async def send_to_symbol(self, symbol: str, message: dict) -> None:
        """Send message to all connections for a symbol."""
        if symbol.upper() not in self._connections:
            return

        disconnected = set()
        for websocket in self._connections[symbol.upper()]:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.add(websocket)

        for ws in disconnected:
            self._connections[symbol.upper()].discard(ws)

    def get_connection_count(self, symbol: str) -> int:
        """Get count of connections for a symbol."""
        return len(self._connections.get(symbol.upper(), set()))


manager = ConnectionManager()

_heartbeat_task: Optional[asyncio.Task] = None


async def heartbeat_sender():
    """Broadcast heartbeat messages to all connected clients."""
    while True:
        await asyncio.sleep(30)
        message = {
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for symbol in list(manager._connections.keys()):
            await manager.send_to_symbol(symbol, message)


@router.websocket("/ws/ohlc/{symbol}")
async def websocket_ohlc(
    websocket: WebSocket,
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME, pattern="^[0-9]+[mhd]$"),
):
    """WebSocket endpoint for real-time OHLC data.

    - On connect: sends last cached candle immediately
    - Subscribes to Redis channel for updates
    - Sends heartbeat every 30 seconds
    """
    symbol = symbol.upper()
    channel = f"ohlc:updates:{symbol}"

    await manager.connect(symbol, websocket)

    redis = await get_redis_client()

    try:
        latest = await redis.get_latest_candle(symbol, timeframe)
        if latest:
            await websocket.send_json(
                {
                    "type": "ohlc",
                    "data": latest,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        await websocket.send_json(
            {
                "type": "connected",
                "symbol": symbol,
                "timeframe": timeframe,
            }
        )

        pubsub = await redis.subscribe(channel)
        if pubsub:
            asyncio.create_task(_listen_pubsub(pubsub, symbol, websocket))
        else:
            logger.warning("Failed to subscribe to Redis pubsub")

        while True:
            await asyncio.sleep(30)
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

    except WebSocketDisconnect:
        logger.info("Client disconnected", extra={"symbol": symbol})
    except Exception as e:
        logger.error(
            "WebSocket error",
            extra={"symbol": symbol, "error": str(e)},
        )
    finally:
        manager.disconnect(symbol, websocket)


async def _listen_pubsub(pubsub, symbol: str, websocket: WebSocket):
    """Listen for messages from Redis pubsub and forward to WebSocket."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in pubsub message")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(
            "PubSub listener error",
            extra={"symbol": symbol, "error": str(e)},
        )
