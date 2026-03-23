from decimal import Decimal
from typing import Any
from pydantic import ValidationError
from app.schemas.ohlc import OHLCBase
from app.core.exceptions import DataValidationException
from app.core.logging_config import logger


class ValidatorService:
    def validate_ohlc(self, data: dict) -> OHLCBase:
        try:
            return OHLCBase(**data)
        except ValidationError as e:
            errors = e.errors()
            logger.warning("ohlc_validation_failed", errors=errors, raw_data=data)
            raise DataValidationException(
                message="OHLC data validation failed", details={"errors": errors}
            )

    def validate_symbol(self, symbol: str) -> bool:
        if not symbol or not symbol.strip():
            return False
        if len(symbol) > 20:
            return False
        return True

    def validate_timeframe(self, timeframe: str) -> bool:
        valid_timeframes = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
        return timeframe in valid_timeframes

    def validate_date_range(self, from_time: Any, to_time: Any) -> bool:
        if from_time and to_time:
            if from_time > to_time:
                return False
        return True


validator_service = ValidatorService()
