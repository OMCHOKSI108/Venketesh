from typing import Optional
from app.adapters.factory import AdapterFactory
from app.core.logging_config import logger


class ExtractService:
    def __init__(self):
        self.adapters = AdapterFactory.get_adapters()

    async def extract(
        self, symbol: str, timeframe: str = "1m", source: Optional[str] = None
    ) -> Optional[dict]:
        if source:
            adapter = self.adapters.get(source)
            if not adapter:
                logger.warning("source_not_found", source=source)
                return None

            try:
                data = await adapter.fetch(symbol, timeframe)
                logger.info("data_extracted", symbol=symbol, source=source)
                return data
            except Exception as e:
                logger.error("extraction_failed", symbol=symbol, source=source, error=str(e))
                return None

        sources = sorted(self.adapters.keys(), key=lambda x: self.adapters[x].priority)

        for src in sources:
            try:
                data = await self.adapters[src].fetch(symbol, timeframe)
                if data:
                    logger.info("data_extracted", symbol=symbol, source=src)
                    return data
            except Exception as e:
                logger.warning("source_failed", source=src, error=str(e))
                continue

        logger.error("all_sources_failed", symbol=symbol)
        return None

    async def extract_historical(
        self, symbol: str, timeframe: str, from_time: str, to_time: str
    ) -> list[dict]:
        data = await self.extract(symbol, timeframe)
        return [data] if data else []


extract_service = ExtractService()
