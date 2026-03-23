from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from app.schemas.ohlc import OHLCBase
from app.core.logging_config import logger


class TransformService:
    def transform(self, raw_data: dict) -> Optional[OHLCBase]:
        try:
            normalized = self._normalize_data(raw_data)
            validated = self._validate_data(normalized)
            return OHLCBase(**validated)
        except Exception as e:
            logger.error("transform_failed", error=str(e), data=raw_data)
            return None

    def _normalize_data(self, data: dict) -> dict:
        normalized = {
            "symbol": self._normalize_symbol(data.get("symbol", "")),
            "timestamp": self._normalize_timestamp(data.get("timestamp")),
            "timeframe": data.get("timeframe", "1m"),
            "open": self._normalize_decimal(data.get("open")),
            "high": self._normalize_decimal(data.get("high")),
            "low": self._normalize_decimal(data.get("low")),
            "close": self._normalize_decimal(data.get("close")),
            "volume": data.get("volume"),
            "source": data.get("source", "unknown"),
            "is_closed": data.get("is_closed", False),
        }
        return normalized

    def _normalize_symbol(self, symbol: str) -> str:
        if not symbol:
            return ""
        return symbol.upper().strip()

    def _normalize_timestamp(self, timestamp: any) -> datetime:
        if isinstance(timestamp, datetime):
            return timestamp
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.now(timezone.utc)

    def _normalize_decimal(self, value: any) -> Decimal:
        if value is None:
            return Decimal("0")
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value)
            except InvalidOperation:
                return Decimal("0")
        return Decimal("0")

    def _validate_data(self, data: dict) -> dict:
        if not data.get("symbol"):
            raise ValueError("Symbol is required")

        if data.get("high", Decimal("0")) < data.get("low", Decimal("0")):
            raise ValueError("High cannot be less than low")

        return data


transform_service = TransformService()
