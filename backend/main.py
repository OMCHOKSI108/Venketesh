# MODULE: backend/main.py
# TASK:   CHECKLIST.md §1.2
# SPEC:   BACKEND.md §5.1
# PHASE:  1
# STATUS: In Progress

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_v1_router
from backend.core.config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown hooks.

    Edge Cases:
        - Startup/shutdown failures are logged and re-raised.
    """

    try:
        logger.info("startup_complete", extra={"status": "ok"})
        yield
    except RuntimeError as exc:
        logger.exception(
            "startup_failure",
            extra={"status": "error", "source": "app", "error": str(exc)},
        )
        raise
    finally:
        logger.info("shutdown_complete", extra={"status": "ok"})


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
