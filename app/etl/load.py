from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.ohlc import OHLCData
from app.schemas.ohlc import OHLCBase
from app.services.cache import cache_service
from app.core.logging_config import logger
from app.core.metrics import ETL_PROCESSED


class LoadService:
    async def load_ohlc(self, db: Session, ohlc_data: OHLCBase) -> bool:
        try:
            existing = self._check_existing(db, ohlc_data)
            if existing:
                self._update_existing(db, existing, ohlc_data)
                logger.info("ohlc_updated", symbol=ohlc_data.symbol)
            else:
                self._insert_new(db, ohlc_data)
                logger.info("ohlc_inserted", symbol=ohlc_data.symbol)

            db.commit()

            await self._update_cache(ohlc_data)

            ETL_PROCESSED.labels(source=ohlc_data.source, status="success").inc()

            return True

        except Exception as e:
            db.rollback()
            logger.error("load_failed", symbol=ohlc_data.symbol, error=str(e))
            ETL_PROCESSED.labels(source=ohlc_data.source, status="failed").inc()
            return False

    def _check_existing(self, db: Session, ohlc_data: OHLCBase) -> Optional[OHLCData]:
        from sqlalchemy import select, and_

        query = select(OHLCData).where(
            and_(
                OHLCData.symbol == ohlc_data.symbol,
                OHLCData.timestamp == ohlc_data.timestamp,
                OHLCData.timeframe == ohlc_data.timeframe,
            )
        )
        result = db.execute(query)
        return result.scalar_one_or_none()

    def _insert_new(self, db: Session, ohlc_data: OHLCBase):
        db_obj = OHLCData(
            symbol=ohlc_data.symbol,
            timestamp=ohlc_data.timestamp,
            timeframe=ohlc_data.timeframe,
            open=ohlc_data.open,
            high=ohlc_data.high,
            low=ohlc_data.low,
            close=ohlc_data.close,
            volume=ohlc_data.volume,
            source=ohlc_data.source,
            is_closed=ohlc_data.is_closed,
        )
        db.add(db_obj)

    def _update_existing(self, db: Session, existing: OHLCData, ohlc_data: OHLCBase):
        existing.open = ohlc_data.open
        existing.high = ohlc_data.high
        existing.low = ohlc_data.low
        existing.close = ohlc_data.close
        existing.volume = ohlc_data.volume
        existing.is_closed = ohlc_data.is_closed
        existing.source = ohlc_data.source

    async def _update_cache(self, ohlc_data: OHLCBase):
        cache_data = {
            "timestamp": ohlc_data.timestamp.isoformat(),
            "open": float(ohlc_data.open),
            "high": float(ohlc_data.high),
            "low": float(ohlc_data.low),
            "close": float(ohlc_data.close),
            "volume": ohlc_data.volume,
            "source": ohlc_data.source,
            "is_closed": ohlc_data.is_closed,
        }
        await cache_service.cache_ohlc(ohlc_data.symbol, ohlc_data.timeframe, cache_data)


load_service = LoadService()
