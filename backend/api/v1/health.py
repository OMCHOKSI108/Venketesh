# MODULE: backend/api/v1/health.py
# TASK:   CHECKLIST.md §4.3 Source Health Tracking
# SPEC:   BACKEND.md §5.1.3 (Health)
# PHASE:  4
# STATUS: In Progress

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field


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
    return HealthResponse(
        status="ok",
        timestamp=now_utc,
        version="1.0.0",
        components={
            "api": "ok",
            "cache": "ok",
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
