# MODULE: backend/db/database.py
# TASK:   CHECKLIST.md §3.1 PostgreSQL Setup
# SPEC:   BACKEND.md §4.1 (Schema)
# PHASE:  3
# STATUS: In Progress

import logging
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from backend.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


class Database:
    """Async PostgreSQL database connection manager.

    Edge Cases:
        - If DATABASE_URL is not set, operations fail gracefully.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        self._engine = None
        self._session_factory = None
        self._database_url = database_url or settings.database_url

    async def connect(self) -> None:
        """Initialize database connection pool."""
        try:
            self._engine = create_async_engine(
                self._database_url,
                echo=settings.debug,
                poolclass=NullPool if settings.debug else None,
                pool_size=20,
                max_overflow=10,
            )
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info(
                "Database connected",
                extra={
                    "url": self._database_url.split("@")[-1]
                    if "@" in self._database_url
                    else "unknown"
                },
            )
        except Exception as e:
            logger.error("Database connection failed", extra={"error": str(e)})
            self._engine = None
            self._session_factory = None

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database disconnected")

    def is_connected(self) -> bool:
        """Check if database is connected."""
        return self._engine is not None

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session."""
        if not self._session_factory:
            raise RuntimeError("Database not connected")

        async with self._session_factory() as session:
            yield session


db: Optional[Database] = None


async def get_database() -> Database:
    """Get or create database singleton."""
    global db
    if db is None:
        db = Database()
        await db.connect()
    return db


async def init_db():
    """Initialize database on startup."""
    await get_database()
