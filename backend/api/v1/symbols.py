# MODULE: backend/api/v1/symbols.py
# TASK:   CHECKLIST.md §3.4
# SPEC:   BACKEND.md Appendix A
# PHASE:  3
# STATUS: In Progress

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/symbols", tags=["symbols"])


class SymbolsResponse(BaseModel):
    """Symbols list response.

    Edge Cases:
        - Returns static bootstrap list until DB-backed registry is enabled.
    """

    symbols: list[str]


@router.get("", response_model=SymbolsResponse)
async def get_symbols() -> SymbolsResponse:
    """Return supported symbols.

    Edge Cases:
        - Keeps minimum required symbols available even when DB is offline.
    """

    return SymbolsResponse(symbols=["NIFTY", "BANKNIFTY"])
