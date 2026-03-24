import asyncio
from datetime import datetime, timezone
from app.core.logging_config import logger
from app.core.constants import SUPPORTED_SYMBOLS
from app.config import get_settings

settings = get_settings()


class ETLScheduler:
    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._interval_seconds = 300
        self._last_run: datetime | None = None
        self._news_interval_seconds = 600

    async def start(self, interval_seconds: int = 300):
        if self._running:
            logger.warning("scheduler_already_running")
            return

        self._interval_seconds = interval_seconds
        self._running = True
        self._task = asyncio.create_task(self._run_loop(interval_seconds))
        logger.info("scheduler_started", interval=interval_seconds, symbols=SUPPORTED_SYMBOLS)

        await self._run_job()
        await self._run_news_job()

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
            await self._run_job()
            self._last_run = datetime.now(timezone.utc)
            logger.info("scheduler_cycle_complete", last_run=self._last_run.isoformat())
            await asyncio.sleep(interval)

    async def _run_job(self):
        from app.services.database import get_db_context
        from app.etl.pipeline import etl_pipeline

        logger.info(
            "scheduler_tick_start",
            symbols=SUPPORTED_SYMBOLS,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        results = {"success": 0, "failed": 0, "symbols": []}

        with get_db_context() as db:
            for symbol in SUPPORTED_SYMBOLS:
                try:
                    success = await etl_pipeline.run(db, symbol, "1d")
                    results["symbols"].append({"symbol": symbol, "success": success})
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.error("symbol_fetch_error", symbol=symbol, error=str(e))
                    results["failed"] += 1
                    results["symbols"].append({"symbol": symbol, "success": False, "error": str(e)})

        logger.info("scheduler_tick_complete", **results)
        return results

    async def _run_news_job(self):
        from app.services.database import get_db_context
        from app.services.news_service import news_service

        logger.info("news_etl_start")

        try:
            with get_db_context() as db:
                count = await news_service.fetch_and_store_news(db)
                logger.info("news_etl_complete", articles_added=count)
                return {"articles_added": count}
        except Exception as e:
            logger.error("news_etl_error", error=str(e))
            return {"error": str(e)}

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "interval_seconds": self._interval_seconds,
            "news_interval_seconds": self._news_interval_seconds,
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }


scheduler = ETLScheduler()
