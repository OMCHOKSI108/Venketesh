# MODULE: backend/api/v1/router.py
# TASK:   CHECKLIST.md §1.2
# SPEC:   BACKEND.md §5.1
# PHASE:  1
# STATUS: In Progress

from fastapi import APIRouter

from backend.api.v1.health import router as health_router
from backend.api.v1.ohlc import router as ohlc_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(ohlc_router)
