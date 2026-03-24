from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.services.insight_engine import insight_engine

router = APIRouter(prefix="/insights", tags=["Insights"])


@router.get("")
async def get_all_insights(db: Session = Depends(get_db)):
    insights = await insight_engine.compute_all_insights(db)
    return {
        "data": insights,
        "meta": {
            "count": len(insights),
            "cached": False,
        },
    }


@router.get("/{symbol}")
async def get_symbol_insight(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    insight = await insight_engine.get_insight(db, symbol)
    if not insight:
        return {"error": "No data available", "symbol": symbol}
    return insight
