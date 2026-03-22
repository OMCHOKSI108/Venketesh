# MODULE: backend/api/v1/health.py
# TASK:   CHECKLIST.md §1.2
# SPEC:   BACKEND.md Appendix A
# PHASE:  1
# STATUS: In Progress

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Health-check API response.

    Edge Cases:
        - Timestamp is always generated server-side in UTC.
    """

    status: str = Field(default="ok")
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Return basic health signal for API uptime.

    Edge Cases:
        - Endpoint remains dependency-free to avoid false negatives.
    """

    now_utc = datetime.now(timezone.utc).isoformat()
    return HealthResponse(status="ok", timestamp=now_utc)
