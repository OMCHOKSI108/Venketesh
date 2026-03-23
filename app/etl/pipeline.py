from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.etl.extract import extract_service
from app.etl.transform import transform_service
from app.etl.load import load_service
from app.schemas.ohlc import OHLCBase
from app.core.logging_config import logger
from app.models.etl_jobs import ETLJob


class ETLPipeline:
    async def run(
        self, db: Session, symbol: str, timeframe: str = "1m", source: Optional[str] = None
    ) -> bool:
        job = ETLJob(
            job_type="ohlc_fetch",
            symbol=symbol,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        db.add(job)
        db.commit()

        try:
            raw_data = await extract_service.extract(symbol, timeframe, source)
            if not raw_data:
                job.status = "failed"
                job.error_message = "No data extracted"
                db.commit()
                return False

            ohlc = transform_service.transform(raw_data)
            if not ohlc:
                job.status = "failed"
                job.error_message = "Data transformation failed"
                db.commit()
                return False

            success = await load_service.load_ohlc(db, ohlc)

            job.status = "completed" if success else "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.records_processed = 1 if success else 0
            db.commit()

            return success

        except Exception as e:
            logger.error("pipeline_failed", symbol=symbol, error=str(e))
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return False

    async def run_batch(self, db: Session, symbols: list[str], timeframe: str = "1m") -> dict:
        results = {"success": 0, "failed": 0, "total": len(symbols)}

        for symbol in symbols:
            success = await self.run(db, symbol, timeframe)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        return results


etl_pipeline = ETLPipeline()
