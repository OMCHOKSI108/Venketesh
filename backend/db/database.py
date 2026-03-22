# MODULE: backend/db/database.py
# TASK:   CHECKLIST.md §3.1
# SPEC:   BACKEND.md §4.1
# PHASE:  3
# STATUS: In Progress

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base for ORM models.

    Edge Cases:
        - Shared metadata is used by all table models.
    """


class Database:
    """Async PostgreSQL database connection manager.

    Edge Cases:
        - Connection errors are logged and surfaced to the caller.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """Initialize database manager.

        Args:
            database_url: Optional override URL.

        Edge Cases:
            - Uses settings URL when no override is provided.
        """

        self._database_url = database_url or settings.database_url
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def connect(self) -> None:
        """Initialize async engine and session factory.

        Edge Cases:
            - Safe to call repeatedly; existing engine is reused.
        """

        if self._engine is not None:
            return
        self._engine = create_async_engine(
            self._database_url,
            echo=settings.debug,
            pool_size=settings.database_pool_size,
            max_overflow=10,
            future=True,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info(
            "database_connected",
            extra={
                "source": "postgres",
                "symbol": "",
                "latency_ms": 0,
                "status": "ok",
            },
        )

    async def disconnect(self) -> None:
        """Dispose engine resources.

        Edge Cases:
            - Safe when connection was never established.
        """

        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    def is_connected(self) -> bool:
        """Return whether engine is initialized.

        Edge Cases:
            - Returns `False` until `connect` succeeds.
        """

        return self._engine is not None and self._session_factory is not None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async SQLAlchemy session.

        Yields:
            Async database session.

        Edge Cases:
            - Automatically rolls back on exception.
        """

        if self._session_factory is None:
            await self.connect()
        if self._session_factory is None:
            raise RuntimeError("Database session factory is unavailable.")
        session = self._session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


db: Optional[Database] = None


async def get_database() -> Database:
    """Get singleton database manager.

    Edge Cases:
        - Creates and connects lazily on first request.
    """

    global db
    if db is None:
        db = Database()
        await db.connect()
    return db
