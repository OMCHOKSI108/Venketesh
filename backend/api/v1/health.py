# MODULE: backend/api/v1/health.py
# TASK:   CHECKLIST.md §4.3 Source Health Tracking
# SPEC:   BACKEND.md §5.1.3 (Health)
# PHASE:  4
# STATUS: In Progress

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.db.database import get_database
from backend.db.redis_client import get_redis_client

router = APIRouter(tags=["health"])


class SourceHealthStatus(BaseModel):
    """Health status for a data source."""

    status: str = Field(default="unknown")
    last_success: Optional[str] = None
    last_failure: Optional[str] = None
    latency_ms: Optional[int] = None
    failure_count: int = 0


class HealthResponse(BaseModel):
    """Health-check API response."""

    status: str = Field(default="ok")
    timestamp: str
    version: str = "1.0.0"
    components: dict = Field(default_factory=dict)


class SourcesHealthResponse(BaseModel):
    """Data sources health response."""

    sources: dict[str, SourceHealthStatus]


_in_memory_health: dict[str, dict] = {}


async def _check_db() -> bool:
    """Check database connectivity."""
    try:
        db = await get_database()
        async with db.get_session() as session:
            await session.execute("SELECT 1")
        return True
    except Exception:
        return False


async def _check_redis() -> bool:
    """Check Redis connectivity."""
    try:
        redis = await get_redis_client()
        await redis.ping()
        return True
    except Exception:
        return False


def update_source_health(
    source_name: str,
    status: str,
    latency_ms: Optional[int] = None,
    success: bool = True,
) -> None:
    """Update source health in memory ( Phase 4.3)."""
    now = datetime.now(timezone.utc).isoformat()

    if source_name not in _in_memory_health:
        _in_memory_health[source_name] = {
            "status": "unknown",
            "last_success": None,
            "last_failure": None,
            "latency_ms": None,
            "failure_count": 0,
        }

    health = _in_memory_health[source_name]
    health["status"] = status
    health["latency_ms"] = latency_ms

    if success:
        health["last_success"] = now
        health["failure_count"] = max(0, health.get("failure_count", 1) - 1)
    else:
        health["last_failure"] = now
        health["failure_count"] = health.get("failure_count", 0) + 1


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return basic health signal for API uptime."""
    now_utc = datetime.now(timezone.utc).isoformat()
    db_ok = await _check_db()
    redis_ok = await _check_redis()
    overall_status = "ok" if db_ok and redis_ok else "degraded"
    return HealthResponse(
        status=overall_status,
        timestamp=now_utc,
        version="1.0.0",
        components={
            "api": "ok",
            "db": "ok" if db_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    )


@router.get("/health/sources", response_model=SourcesHealthResponse)
async def get_sources_health() -> SourcesHealthResponse:
    """Return health status for all data sources."""
    sources = {}

    for source_name in ["nse", "yahoo"]:
        if source_name in _in_memory_health:
            health = _in_memory_health[source_name]
            sources[source_name] = SourceHealthStatus(
                status=health.get("status", "unknown"),
                last_success=health.get("last_success"),
                last_failure=health.get("last_failure"),
                latency_ms=health.get("latency_ms"),
                failure_count=health.get("failure_count", 0),
            )
        else:
            sources[source_name] = SourceHealthStatus(status="unknown")

    return SourcesHealthResponse(sources=sources)


@router.get("/health/db")
async def get_db_health():
    """Check database health."""
    ok = await _check_db()
    return {"status": "ok" if ok else "error"}


@router.get("/health/redis")
async def get_redis_health():
    """Check Redis health."""
    ok = await _check_redis()
    return {"status": "ok" if ok else "error"}
