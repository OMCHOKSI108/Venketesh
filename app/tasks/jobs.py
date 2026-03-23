from app.tasks.celery_app import celery_app
from app.core.constants import SUPPORTED_SYMBOLS
from app.core.logging_config import logger


@celery_app.task(name="app.tasks.jobs.fetch_market_data")
def fetch_market_data():
    from app.services.database import get_db_context
    from app.etl.pipeline import etl_pipeline
    import asyncio

    logger.info("celery_fetch_started", symbols=SUPPORTED_SYMBOLS)

    async def run():
        with get_db_context() as db:
            for symbol in SUPPORTED_SYMBOLS:
                try:
                    await etl_pipeline.run(db, symbol, "1m")
                except Exception as e:
                    logger.error("celery_fetch_error", symbol=symbol, error=str(e))

    asyncio.run(run())
    logger.info("celery_fetch_completed")


@celery_app.task(name="app.tasks.jobs.health_check")
def check_sources_health():
    from app.adapters.factory import AdapterFactory
    from app.services.cache import cache_service
    import asyncio

    async def run():
        adapters = AdapterFactory.get_adapters()
        for name, adapter in adapters.items():
            try:
                is_healthy = await adapter.health_check()
                await cache_service.cache_source_health(
                    name, {"status": "healthy" if is_healthy else "degraded", "last_check": "now"}
                )
            except Exception as e:
                logger.error("health_check_error", source=name, error=str(e))

    asyncio.run(run())
