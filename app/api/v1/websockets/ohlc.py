import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set
from app.services.aggregator import aggregator_service
from app.services.cache import cache_service
from app.schemas.ohlc import WebSocketMessage
from app.core.constants import SUPPORTED_SYMBOLS, WS_HEARTBEAT_INTERVAL
from app.core.logging_config import logger
from app.core.metrics import ACTIVE_CONNECTIONS

router = APIRouter()

ConnectionManager: Dict[str, Set[WebSocket]] = {}


class WSConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, symbol: str):
        await websocket.accept()
        if symbol not in self.active_connections:
            self.active_connections[symbol] = set()
        self.active_connections[symbol].add(websocket)
        ACTIVE_CONNECTIONS.inc()
        logger.info("ws_connected", symbol=symbol, total=len(self.active_connections[symbol]))

    def disconnect(self, websocket: WebSocket, symbol: str):
        if symbol in self.active_connections:
            self.active_connections[symbol].discard(websocket)
            ACTIVE_CONNECTIONS.dec()
            logger.info("ws_disconnected", symbol=symbol)

    async def broadcast(self, symbol: str, message: dict):
        if symbol in self.active_connections:
            dead_connections = set()
            for connection in self.active_connections[symbol]:
                try:
                    await connection.send_json(message)
                except Exception:
                    dead_connections.add(connection)

            for dead in dead_connections:
                self.disconnect(dead, symbol)


ws_manager = WSConnectionManager()


@router.websocket("/ws/ohlc/{symbol}")
async def websocket_ohlc(websocket: WebSocket, symbol: str = "", timeframe: str = Query("1m")):
    symbol = symbol.upper()

    if symbol not in SUPPORTED_SYMBOLS:
        await websocket.send_json(
            {
                "type": "error",
                "code": "INVALID_SYMBOL",
                "message": f"Symbol {symbol} is not supported",
            }
        )
        await websocket.close()
        return

    await ws_manager.connect(websocket, symbol)

    await websocket.send_json(
        WebSocketMessage(type="connected", symbol=symbol, timeframe=timeframe).model_dump()
    )

    heartbeat_task = asyncio.create_task(send_heartbeat(websocket, symbol))

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "ping":
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()}
                )
            elif action == "unsubscribe":
                break

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", symbol=symbol)
    except Exception as e:
        logger.error("ws_error", symbol=symbol, error=str(e))
    finally:
        heartbeat_task.cancel()
        ws_manager.disconnect(websocket, symbol)


async def send_heartbeat(websocket: WebSocket, symbol: str):
    while True:
        try:
            await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            await websocket.send_json(
                {"type": "heartbeat", "timestamp": datetime.now(timezone.utc).isoformat()}
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("heartbeat_error", error=str(e))
            break


async def broadcast_ohlc_update(symbol: str, data: dict):
    message = {
        "type": "ohlc",
        "symbol": symbol,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    await ws_manager.broadcast(symbol, message)
