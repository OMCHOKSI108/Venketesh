# MODULE: backend/main.py
# TASK:   CHECKLIST.md §1.2
# SPEC:   BACKEND.md §5.1
# PHASE:  1
# STATUS: In Progress

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.api.v1.router import api_v1_router
from backend.core.config import settings
from backend.db.database import get_database
from backend.db.models import APIRequest
from backend.db.redis_client import get_redis_client
from backend.services.poller import PollingLoop

logger = logging.getLogger(__name__)

poller = PollingLoop()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting and request logging middleware."""

    async def dispatch(self, request, call_next):
        client_id = request.client.host if request.client else "unknown"
        redis = await get_redis_client()
        key = f"ratelimit:{client_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 60)
        if count > 100:
            return JSONResponse(
                {"error": "Rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": "60"},
            )

        # Log request
        database = await get_database()
        async with database.get_session() as session:
            session.add(
                APIRequest(
                    client_id=client_id,
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=200,  # placeholder
                    response_time_ms=0,  # placeholder
                )
            )
            await session.commit()

        start = time.perf_counter()
        response = await call_next(request)
        latency = int((time.perf_counter() - start) * 1000)

        # Add headers
        response.headers["X-RateLimit-Limit"] = "100"
        response.headers["X-RateLimit-Remaining"] = str(max(0, 100 - count))

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown hooks.

    Edge Cases:
        - Startup/shutdown failures are logged and re-raised.
    """
    try:
        await poller.start()
        logger.info("startup_complete", extra={"status": "ok"})
        yield
    except RuntimeError as exc:
        logger.exception(
            "startup_failure",
            extra={"status": "error", "source": "app", "error": str(exc)},
        )
        raise
    finally:
        await poller.stop()
        logger.info("shutdown_complete", extra={"status": "ok"})


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
