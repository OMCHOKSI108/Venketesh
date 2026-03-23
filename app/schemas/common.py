from datetime import datetime, timezone
from typing import Optional, Any
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[dict] = None
    timestamp: datetime = datetime.now(timezone.utc)
    path: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    uptime_seconds: int
    components: dict


class SourceHealthResponse(BaseModel):
    source: str
    status: str
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    latency_ms: Optional[int] = None


class SourceHealthListResponse(BaseModel):
    sources: list[SourceHealthResponse]


class MetaInfo(BaseModel):
    count: int
    source: Optional[str] = None
    cached: bool = False
    query_time_ms: Optional[int] = None
