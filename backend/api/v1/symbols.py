# MODULE: backend/api/v1/symbols.py
# TASK:   CHECKLIST.md §3.4
# SPEC:   BACKEND.md Appendix A
# PHASE:  3
# STATUS: In Progress

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from backend.db.database import get_database
from backend.db.models import SymbolDb

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/symbols", tags=["symbols"])


class SymbolItem(BaseModel):
    """Symbol metadata item.

    Edge Cases:
        - `exchange` and `instrument_type` may be absent in bootstrap entries.
    """

    symbol: str
    name: str
    exchange: str | None = None
    instrument_type: str | None = None
    currency: str | None = None


class SymbolsResponse(BaseModel):
    """Symbols response payload.

    Edge Cases:
        - Falls back to minimum bootstrap list when DB is unavailable.
    """

    symbols: list[SymbolItem]


@router.get("", response_model=SymbolsResponse)
async def get_symbols() -> SymbolsResponse:
    """Return active symbols list.

    Edge Cases:
        - Returns fallback symbols if DB query fails.
    """

    try:
        database = await get_database()
        async with database.get_session() as session:
            result = await session.execute(
                select(SymbolDb)
                .where(SymbolDb.is_active.is_(True))
                .order_by(SymbolDb.symbol.asc())
            )
            rows = result.scalars().all()
        if rows:
            return SymbolsResponse(
                symbols=[
                    SymbolItem(
                        symbol=row.symbol,
                        name=row.name,
                        exchange=row.exchange,
                        instrument_type=row.instrument_type,
                        currency=row.currency,
                    )
                    for row in rows
                ]
            )
    except (RuntimeError, ValueError, TypeError) as exc:
        logger.warning(
            "symbols_db_query_failed",
            extra={
                "source": "postgres",
                "symbol": "",
                "latency_ms": 0,
                "status": "error",
                "error": str(exc),
            },
        )

    return SymbolsResponse(
        symbols=[
            SymbolItem(symbol="NIFTY", name="NIFTY 50"),
            SymbolItem(symbol="BANKNIFTY", name="NIFTY BANK"),
        ]
    )
