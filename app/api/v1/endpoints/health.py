from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text
from app.schemas.common import HealthResponse, SourceHealthResponse, SourceHealthListResponse
from app.adapters.factory import AdapterFactory
from app.services.cache import cache_service

router = APIRouter(prefix="/health", tags=["Health"])

start_time = datetime.now(timezone.utc)


@router.get("", response_model=HealthResponse)
async def health_check():
    from app.services.database import engine
    from app.config import get_settings

    settings = get_settings()
    uptime = int((datetime.now(timezone.utc) - start_time).total_seconds())

    db_status = "healthy"
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    try:
        await cache_service.get_client()
    except Exception:
        redis_status = "unhealthy"

    sources = AdapterFactory.get_all_sources()

    overall_status = "healthy"
    if db_status != "healthy" or redis_status != "healthy":
        overall_status = "degraded"
    if db_status == "unhealthy" or redis_status == "unhealthy":
        overall_status = "unhealthy"

    return HealthResponse(
        status=overall_status,
        uptime_seconds=uptime,
        components={"database": db_status, "redis": redis_status, "data_sources": sources},
    )


@router.get("/sources", response_model=SourceHealthListResponse)
async def sources_health():
    sources = []
    adapters = AdapterFactory.get_adapters()

    for name, adapter in adapters.items():
        try:
            is_healthy = await adapter.health_check()
            health = await cache_service.get_source_health(name)
            sources.append(
                SourceHealthResponse(
                    source=name,
                    status="healthy" if is_healthy else "down",
                    last_success=datetime.now(timezone.utc) if is_healthy else None,
                    latency_ms=100,
                )
            )
        except Exception:
            sources.append(SourceHealthResponse(source=name, status="down"))

    return SourceHealthListResponse(sources=sources)
