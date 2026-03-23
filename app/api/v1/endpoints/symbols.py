from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.services.database import get_db
from app.models.symbol import Symbol
from app.schemas.symbol import SymbolResponse, SymbolListResponse
from app.core.constants import SUPPORTED_SYMBOLS

router = APIRouter(prefix="/symbols", tags=["Symbols"])


@router.get("", response_model=SymbolListResponse)
async def list_symbols(
    exchange: Optional[str] = Query(None),
    instrument_type: Optional[str] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    query = select(Symbol)

    if exchange:
        query = query.where(Symbol.exchange == exchange)
    if instrument_type:
        query = query.where(Symbol.instrument_type == instrument_type)
    if active_only:
        query = query.where(Symbol.is_active == True)

    result = db.execute(query)
    symbols = result.scalars().all()

    default_symbols = [
        SymbolResponse(symbol=s, name=s, exchange="NSE", instrument_type="INDEX", is_active=True)
        for s in SUPPORTED_SYMBOLS
    ]

    if not symbols:
        return SymbolListResponse(symbols=default_symbols, count=len(default_symbols))

    return SymbolListResponse(
        symbols=[SymbolResponse.model_validate(s) for s in symbols], count=len(symbols)
    )


@router.get("/{symbol}", response_model=SymbolResponse)
async def get_symbol(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()

    result = db.execute(select(Symbol).where(Symbol.symbol == symbol))
    db_symbol = result.scalar_one_or_none()

    if not db_symbol:
        return SymbolResponse(
            symbol=symbol, name=symbol, exchange="NSE", instrument_type="INDEX", is_active=True
        )

    return SymbolResponse.model_validate(db_symbol)
