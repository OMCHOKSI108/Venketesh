from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
import csv
import io
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.services.aggregator import aggregator_service
from app.etl.pipeline import etl_pipeline
from app.core.constants import SUPPORTED_SYMBOLS, DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/ohlc", tags=["OHLC"])


@router.get("/{symbol}")
async def get_ohlc(
    symbol: str,
    timeframe: str = Query("1m", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = None,
):
    symbol = symbol.upper()
    db = next(get_db())

    from_dt = None
    to_dt = None

    if from_time:
        from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
    if to_time:
        to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))

    ohlc_records = await aggregator_service.get_historical(
        db, symbol, timeframe, from_dt, to_dt, limit
    )

    data = [
        {
            "timestamp": r.timestamp.isoformat(),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume,
            "is_closed": r.is_closed,
            "source": r.source,
        }
        for r in ohlc_records
    ]

    if not data:
        await etl_pipeline.run(db, symbol, timeframe)
        ohlc_records = await aggregator_service.get_historical(
            db, symbol, timeframe, from_dt, to_dt, limit
        )
        data = [
            {
                "timestamp": r.timestamp.isoformat(),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": r.volume,
                "is_closed": r.is_closed,
                "source": r.source,
            }
            for r in ohlc_records
        ]

    db.close()

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "data": data,
        "meta": {"count": len(data), "cached": False},
    }


@router.get("/{symbol}/latest")
async def get_latest(
    symbol: str,
    timeframe: str = Query("1m", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    db: Session = None,
):
    symbol = symbol.upper()
    db = next(get_db())

    ohlc = await aggregator_service.get_latest(db, symbol, timeframe)

    if not ohlc:
        await etl_pipeline.run(db, symbol, timeframe)
        ohlc = await aggregator_service.get_latest(db, symbol, timeframe)

    db.close()

    if not ohlc:
        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "open": 0,
            "high": 0,
            "low": 0,
            "close": 0,
            "volume": 0,
            "is_closed": False,
            "source": "none",
            "error": "No data available",
        }

    return {
        "symbol": ohlc.symbol,
        "timestamp": ohlc.timestamp.isoformat(),
        "open": float(ohlc.open),
        "high": float(ohlc.high),
        "low": float(ohlc.low),
        "close": float(ohlc.close),
        "volume": ohlc.volume,
        "is_closed": ohlc.is_closed,
        "source": ohlc.source,
    }


@router.get("/{symbol}/download")
async def download_historical(
    symbol: str,
    timeframe: str = Query("1m", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    from_time: Optional[str] = Query(None),
    to_time: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    format: str = Query("csv", pattern="^(csv|json)$"),
    db: Session = None,
):
    symbol = symbol.upper()
    db = next(get_db())

    from_dt = None
    to_dt = None

    if from_time:
        from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
    if to_time:
        to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))

    ohlc_records = await aggregator_service.get_historical(
        db, symbol, timeframe, from_dt, to_dt, limit
    )
    db.close()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["timestamp", "open", "high", "low", "close", "volume", "source", "is_closed"]
        )

        for r in reversed(ohlc_records):
            writer.writerow(
                [
                    r.timestamp.isoformat(),
                    float(r.open),
                    float(r.high),
                    float(r.low),
                    float(r.close),
                    r.volume or 0,
                    r.source,
                    r.is_closed,
                ]
            )

        output.seek(0)
        filename = f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    else:
        data = [
            {
                "timestamp": r.timestamp.isoformat(),
                "open": float(r.open),
                "high": float(r.high),
                "low": float(r.low),
                "close": float(r.close),
                "volume": r.volume,
                "source": r.source,
                "is_closed": r.is_closed,
            }
            for r in reversed(ohlc_records)
        ]
        filename = f"{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        return StreamingResponse(
            iter([str(data)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )


@router.post("/{symbol}/fetch")
async def fetch_data(symbol: str, timeframe: str = Query("1m")):
    symbol = symbol.upper()
    db = next(get_db())
    success = await etl_pipeline.run(db, symbol, timeframe)
    db.close()

    return {"symbol": symbol, "timeframe": timeframe, "success": success}


@router.post("/fetch-all")
async def fetch_all_data(timeframe: str = Query("1m"), background_tasks: BackgroundTasks = None):
    results = {"success": 0, "failed": 0, "symbols": []}
    db = next(get_db())

    for symbol in SUPPORTED_SYMBOLS:
        success = await etl_pipeline.run(db, symbol, timeframe)
        results["symbols"].append({"symbol": symbol, "success": success})
        if success:
            results["success"] += 1
        else:
            results["failed"] += 1

    db.close()
    return results
