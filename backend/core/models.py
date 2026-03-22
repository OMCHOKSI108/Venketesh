# MODULE: backend/core/models.py
# TASK:   CHECKLIST.md §1.3
# SPEC:   BACKEND.md §4.1
# PHASE:  1
# STATUS: In Progress

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, model_validator

RawData = dict[str, Any]


class OHLCData(BaseModel):
    """Normalized OHLC candle payload used across backend boundaries.

    Edge Cases:
        - `volume` can be `None` when the source does not provide it.
        - `timestamp` is expected to be timezone-aware UTC in later phases.
    """

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    source: str
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_price_relationships(self) -> "OHLCData":
        """Validate OHLC constraints.

        Edge Cases:
            - Rejects candles where `high < low`.
            - Rejects candles where `open > high`.
            - Rejects candles where `close < low`.
        """

        if self.high < self.low:
            raise ValueError(
                f"OHLC violation: high < low | high={self.high} low={self.low}"
            )
        if self.open > self.high:
            raise ValueError(
                f"OHLC violation: open > high | open={self.open} high={self.high}"
            )
        if self.close < self.low:
            raise ValueError(
                f"OHLC violation: close < low | close={self.close} low={self.low}"
            )
        if self.close > self.high:
            raise ValueError(
                f"OHLC violation: close > high | close={self.close} high={self.high}"
            )
        return self

    def to_lwc_format(self) -> dict[str, Any]:
        """Convert to TradingView Lightweight Charts format."""
        return {
            "time": int(self.timestamp.timestamp()),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
        }
