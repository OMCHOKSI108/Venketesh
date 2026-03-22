# MODULE: backend/api/v1/websocket.py
# TASK:   CHECKLIST.md §2.5
# SPEC:   BACKEND.md §5.1.3
# PHASE:  2
# STATUS: In Progress

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC
from datetime import datetime

from fastapi import APIRouter
from fastapi import Query
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from backend.core.config import settings

try:
    from backend.db.redis_client import get_redis_client

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    get_redis_client = None

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/ohlc/{symbol}")
async def websocket_ohlc(
    websocket: WebSocket,
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
) -> None:
    """Stream OHLC updates over WebSocket for a symbol.

    Args:
        websocket: FastAPI WebSocket connection.
        symbol: Market symbol.
        timeframe: Requested candle timeframe.

    Edge Cases:
        - Sends cached latest candle immediately after connect when available.
        - Closes gracefully on client disconnect or pubsub termination.
    """

    symbol_upper = symbol.upper()
    redis = await get_redis_client()
    pubsub = None
    await websocket.accept()

    try:
        latest = await redis.get_latest_candle(symbol_upper, timeframe)
        if latest is not None:
            await websocket.send_json(
                {
                    "type": "ohlc",
                    "data": latest,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )

        channel = f"ohlc:updates:{symbol_upper}"
        pubsub = await redis.subscribe(channel)
        if pubsub is None:
            await websocket.send_json(
                {
                    "type": "status",
                    "status": "degraded",
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )

        heartbeat_task = asyncio.create_task(_send_heartbeat(websocket))
        listener_task = (
            asyncio.create_task(_relay_pubsub(pubsub, websocket))
            if pubsub is not None
            else None
        )

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(
            "ws_client_disconnected",
            extra={
                "source": "websocket",
                "symbol": symbol_upper,
                "latency_ms": 0,
                "status": "ok",
            },
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.error(
            "ws_stream_failed",
            extra={
                "source": "websocket",
                "symbol": symbol_upper,
                "latency_ms": 0,
                "status": "error",
                "error": str(exc),
            },
        )
    finally:
        if "heartbeat_task" in locals():
            heartbeat_task.cancel()
        if "listener_task" in locals() and listener_task is not None:
            listener_task.cancel()
        if pubsub is not None:
            await pubsub.unsubscribe()
            await pubsub.close()


async def _send_heartbeat(websocket: WebSocket) -> None:
    """Send periodic heartbeat messages to client.

    Args:
        websocket: Active websocket connection.

    Edge Cases:
        - Stops silently when task is cancelled.
    """

    try:
        while True:
            await asyncio.sleep(settings.ws_heartbeat_interval)
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            )
    except asyncio.CancelledError:
        return


async def _relay_pubsub(pubsub: object, websocket: WebSocket) -> None:
    """Forward Redis pub/sub messages to websocket.

    Args:
        pubsub: Redis pubsub object.
        websocket: Active websocket connection.

    Edge Cases:
        - Ignores malformed JSON payloads.
    """

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw_data = message.get("data")
            if not isinstance(raw_data, str):
                continue
            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                continue
            await websocket.send_json(payload)
    except asyncio.CancelledError:
        return
