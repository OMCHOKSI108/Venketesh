# MODULE: backend/core/validator.py
# TASK:   CHECKLIST.md §3.2 Data Validator
# SPEC:   BACKEND.md §8.1 (Validation)
# PHASE:  3
# STATUS: In Progress

import logging
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from backend.core.models import OHLCData

logger = logging.getLogger(__name__)


class ValidationResult(NamedTuple):
    """Result of OHLC data validation."""

    valid: bool
    errors: list[str]


class DataValidator:
    """Validates OHLC data against business rules.

    Edge Cases:
        - Handles None volumes (treated as valid)
        - Handles timezone-aware and naive timestamps
        - Rejects candles older than 24 hours
    """

    @staticmethod
    def validate(candle: OHLCData) -> ValidationResult:
        """Validate OHLC candle against all business rules.

        Rules:
            1. high >= low
            2. open <= high
            3. close >= low
            4. close <= high
            5. timestamp is present, valid datetime, within last 24 hours
            6. symbol is non-empty string

        Args:
            candle: OHLCData to validate

        Returns:
            ValidationResult with valid status and list of errors
        """
        errors = []

        if candle.high < candle.low:
            errors.append(f"high ({candle.high}) < low ({candle.low})")

        if candle.open > candle.high:
            errors.append(f"open ({candle.open}) > high ({candle.high})")

        if candle.close < candle.low:
            errors.append(f"close ({candle.close}) < low ({candle.low})")

        if candle.close > candle.high:
            errors.append(f"close ({candle.close}) > high ({candle.high})")

        valid, ts_error = DataValidator._validate_timestamp(candle.timestamp)
        if not valid:
            errors.append(ts_error)

        if not candle.symbol or len(candle.symbol.strip()) == 0:
            errors.append("symbol is empty")

        if errors:
            logger.warning(
                "candle_validation_failed",
                extra={
                    "symbol": candle.symbol,
                    "timestamp": candle.timestamp.isoformat(),
                    "errors": errors,
                },
            )
            return ValidationResult(valid=False, errors=errors)

        return ValidationResult(valid=True, errors=[])

    @staticmethod
    def _validate_timestamp(timestamp: datetime) -> tuple[bool, str]:
        """Validate timestamp is present, valid, and within last 24 hours."""
        if timestamp is None:
            return False, "timestamp is None"

        if not isinstance(timestamp, datetime):
            return False, f"timestamp is not datetime: {type(timestamp)}"

        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if timestamp > now + timedelta(minutes=1):
            return False, f"timestamp is in the future: {timestamp}"

        if now - timestamp > timedelta(hours=24):
            return False, f"timestamp is older than 24 hours: {timestamp}"

        return True, ""
