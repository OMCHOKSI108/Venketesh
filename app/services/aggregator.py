from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from app.models.ohlc import OHLCData
from app.models.enums import DataSource
from app.schemas.ohlc import OHLCBase
from app.services.cache import cache_service
from app.core.exceptions import SourceUnavailableException
from app.core.logging_config import logger


class AggregatorService:
    def __init__(self):
        self._adapters = {}

    def register_adapter(self, source: DataSource, adapter):
        self._adapters[source.value] = adapter
        logger.info("adapter_registered", source=source.value)

    async def fetch_ohlc(
        self, symbol: str, timeframe: str = "1m", source_priority: Optional[list[str]] = None
    ) -> OHLCBase:
        if source_priority is None:
            source_priority = ["nse", "yahoo"]

        last_error = None

        for source_name in source_priority:
            adapter = self._adapters.get(source_name)
            if not adapter:
                continue

            try:
                logger.info("fetching_from_source", symbol=symbol, source=source_name)
                data = await adapter.fetch(symbol, timeframe)
                if data:
                    data["source"] = source_name
                    await cache_service.cache_ohlc(symbol, timeframe, data)
                    return OHLCBase(**data)
            except Exception as e:
                logger.warning(
                    "source_fetch_failed", symbol=symbol, source=source_name, error=str(e)
                )
                last_error = e
                continue

        raise SourceUnavailableException(
            source="all", details={"last_error": str(last_error)} if last_error else None
        )

    async def get_historical(
        self,
        db: Session,
        symbol: str,
        timeframe: str = "1m",
        from_time: Optional[datetime] = None,
        to_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[OHLCData]:
        query = select(OHLCData).where(
            and_(OHLCData.symbol == symbol, OHLCData.timeframe == timeframe)
        )

        if from_time:
            query = query.where(OHLCData.timestamp >= from_time)
        if to_time:
            query = query.where(OHLCData.timestamp <= to_time)

        query = query.order_by(OHLCData.timestamp.desc()).limit(limit)

        result = db.execute(query)
        return list(result.scalars().all())

    async def get_latest(
        self, db: Session, symbol: str, timeframe: str = "1m"
    ) -> Optional[OHLCData]:
        cached = await cache_service.get_cached_ohlc(symbol, timeframe)
        if cached:
            return OHLCData(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=datetime.fromisoformat(cached["timestamp"]),
                open=cached["open"],
                high=cached["high"],
                low=cached["low"],
                close=cached["close"],
                volume=cached.get("volume"),
                source=cached["source"],
                is_closed=cached.get("is_closed", False),
            )

        query = (
            select(OHLCData)
            .where(and_(OHLCData.symbol == symbol, OHLCData.timeframe == timeframe))
            .order_by(OHLCData.timestamp.desc())
            .limit(1)
        )

        result = db.execute(query)
        return result.scalar_one_or_none()


aggregator_service = AggregatorService()
