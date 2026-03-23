import asyncio
from datetime import datetime
from typing import Callable, Awaitable
from app.core.logging_config import logger
from app.core.constants import SUPPORTED_SYMBOLS


class ETLScheduler:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self, interval_seconds: int = 60):
        if self._running:
            logger.warning("scheduler_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        logger.info("scheduler_started", interval=interval_seconds)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("scheduler_stopped")

    async def _run_loop(self, interval: int):
        while self._running:
            try:
                await self._run_job()
            except Exception as e:
                logger.error("scheduler_error", error=str(e))

            await asyncio.sleep(interval)

    async def _run_job(self):
        from app.services.database import get_db_context
        from app.etl.pipeline import etl_pipeline

        logger.info("scheduler_tick", symbols=SUPPORTED_SYMBOLS)

        with get_db_context() as db:
            for symbol in SUPPORTED_SYMBOLS:
                try:
                    await etl_pipeline.run(db, symbol, "1m")
                except Exception as e:
                    logger.error("symbol_fetch_error", symbol=symbol, error=str(e))


scheduler = ETLScheduler()
