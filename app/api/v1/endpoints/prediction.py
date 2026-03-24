from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.services.aggregator import aggregator_service
from app.services.ml_prediction import ml_prediction_service
from app.services.news_service import news_service

router = APIRouter(prefix="/prediction", tags=["Prediction"])


async def get_symbol_sentiment_score(db: Session, symbol: str) -> float:
    """Get sentiment score for a symbol from news"""
    sentiment = await news_service.get_cached_sentiment(db)
    for s in sentiment:
        if s.get("symbol", "").upper() == symbol.upper():
            return s.get("sentiment_score", 0.0)
    return 0.0


@router.get("/{symbol}/signals")
async def get_signals(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    limit: int = Query(100, ge=20, le=500),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()

    ohlc_records = await aggregator_service.get_historical(db, symbol, timeframe, None, None, limit)

    if not ohlc_records or len(ohlc_records) < 20:
        return {
            "symbol": symbol,
            "error": "Insufficient data for prediction",
            "signals": [],
        }

    ohlc_data = [
        {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume or 0,
        }
        for r in ohlc_records
    ]

    sentiment_score = await get_symbol_sentiment_score(db, symbol)

    result = ml_prediction_service.get_signals(ohlc_data, sentiment_score)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "signals": result["signals"],
        "direction": result["direction"],
        "levels": result["levels"],
        "forecast": result["forecast"],
        "timestamp": result["timestamp"],
    }


@router.get("/{symbol}/direction")
async def get_direction(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    limit: int = Query(100, ge=20, le=500),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()

    ohlc_records = await aggregator_service.get_historical(db, symbol, timeframe, None, None, limit)

    if not ohlc_records or len(ohlc_records) < 20:
        return {
            "symbol": symbol,
            "error": "Insufficient data",
            "direction": "UNKNOWN",
            "confidence": 0,
        }

    ohlc_data = [
        {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume or 0,
        }
        for r in ohlc_records
    ]

    sentiment_score = await get_symbol_sentiment_score(db, symbol)

    result = ml_prediction_service.predict_direction(ohlc_data, sentiment_score)

    return {
        "symbol": symbol,
        "direction": result["direction"],
        "confidence": result["confidence"],
        "probabilities": result["probabilities"],
    }


@router.get("/{symbol}/forecast")
async def get_forecast(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    days: int = Query(5, ge=1, le=30),
    limit: int = Query(100, ge=20, le=500),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()

    ohlc_records = await aggregator_service.get_historical(db, symbol, timeframe, None, None, limit)

    if not ohlc_records or len(ohlc_records) < 20:
        return {
            "symbol": symbol,
            "error": "Insufficient data",
            "forecast": [],
        }

    ohlc_data = [
        {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume or 0,
        }
        for r in ohlc_records
    ]

    result = ml_prediction_service.calculate_forecast(ohlc_data, days)

    return {
        "symbol": symbol,
        "forecast": result["forecast"],
        "confidence": result["confidence"],
        "trend": result["trend"],
    }


@router.get("/{symbol}/levels")
async def get_support_resistance(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    window: int = Query(20, ge=5, le=100),
    limit: int = Query(100, ge=20, le=500),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()

    ohlc_records = await aggregator_service.get_historical(db, symbol, timeframe, None, None, limit)

    if not ohlc_records or len(ohlc_records) < window:
        return {
            "symbol": symbol,
            "error": "Insufficient data",
            "support": None,
            "resistance": None,
        }

    ohlc_data = [
        {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume or 0,
        }
        for r in ohlc_records
    ]

    result = ml_prediction_service.calculate_support_resistance(ohlc_data, window)

    return {
        "symbol": symbol,
        "support": result["support"],
        "resistance": result["resistance"],
        "support_distance_pct": result["support_distance_pct"],
        "resistance_distance_pct": result["resistance_distance_pct"],
        "current_price": result["current_price"],
    }


@router.post("/{symbol}/train")
async def train_model(
    symbol: str,
    timeframe: str = Query("1d", pattern="^(1m|5m|15m|30m|1h|4h|1d|1w)$"),
    limit: int = Query(500, ge=100, le=2000),
    db: Session = Depends(get_db),
):
    symbol = symbol.upper()

    ohlc_records = await aggregator_service.get_historical(db, symbol, timeframe, None, None, limit)

    if not ohlc_records or len(ohlc_records) < 50:
        return {
            "symbol": symbol,
            "status": "error",
            "message": "Insufficient training data",
        }

    ohlc_data = [
        {
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": r.volume or 0,
        }
        for r in ohlc_records
    ]

    result = ml_prediction_service.train(ohlc_data)

    return {
        "symbol": symbol,
        "status": result["status"],
        "message": result.get("message", ""),
        "train_accuracy": result.get("train_accuracy", 0),
        "test_accuracy": result.get("test_accuracy", 0),
        "samples": result.get("samples", 0),
    }
