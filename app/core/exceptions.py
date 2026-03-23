from enum import Enum
from typing import Optional, Dict, Any


class ErrorCode(Enum):
    SOURCE_UNAVAILABLE = "1001"
    SOURCE_RATE_LIMITED = "1002"
    SOURCE_INVALID_RESPONSE = "1003"

    INVALID_SYMBOL = "2001"
    INVALID_TIMEFRAME = "2002"
    INVALID_DATE_RANGE = "2003"
    DATA_VALIDATION_FAILED = "2004"

    DATABASE_ERROR = "3001"
    CACHE_ERROR = "3002"
    INTERNAL_ERROR = "3003"

    NOT_FOUND = "4001"
    UNAUTHORIZED = "4002"
    RATE_LIMIT_EXCEEDED = "4003"


class MarketDataException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)


class SourceUnavailableException(MarketDataException):
    def __init__(self, source: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.SOURCE_UNAVAILABLE,
            message=f"Data source {source} is currently unavailable",
            details=details,
            status_code=503,
        )


class SourceRateLimitedException(MarketDataException):
    def __init__(
        self, source: str, retry_after: int = 60, details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            code=ErrorCode.SOURCE_RATE_LIMITED,
            message=f"Data source {source} has rate limited",
            details={"retry_after": retry_after, **(details or {})},
            status_code=429,
        )


class SourceInvalidResponseException(MarketDataException):
    def __init__(self, source: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.SOURCE_INVALID_RESPONSE,
            message=f"Invalid response from data source {source}",
            details=details,
            status_code=502,
        )


class InvalidSymbolException(MarketDataException):
    def __init__(self, symbol: str):
        super().__init__(
            code=ErrorCode.INVALID_SYMBOL, message=f"Invalid symbol: {symbol}", status_code=400
        )


class InvalidTimeframeException(MarketDataException):
    def __init__(self, timeframe: str):
        super().__init__(
            code=ErrorCode.INVALID_TIMEFRAME,
            message=f"Invalid timeframe: {timeframe}",
            status_code=400,
        )


class InvalidDateRangeException(MarketDataException):
    def __init__(self, message: str = "Invalid date range"):
        super().__init__(code=ErrorCode.INVALID_DATE_RANGE, message=message, status_code=400)


class DataValidationException(MarketDataException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.DATA_VALIDATION_FAILED, message=message, details=details, status_code=422
        )


class DatabaseException(MarketDataException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.DATABASE_ERROR, message=message, details=details, status_code=500
        )


class CacheException(MarketDataException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.CACHE_ERROR, message=message, details=details, status_code=500
        )


class NotFoundException(MarketDataException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            code=ErrorCode.NOT_FOUND, message=f"{resource} not found: {identifier}", status_code=404
        )


class UnauthorizedException(MarketDataException):
    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(code=ErrorCode.UNAUTHORIZED, message=message, status_code=401)


class RateLimitException(MarketDataException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            code=ErrorCode.RATE_LIMIT_EXCEEDED,
            message="Rate limit exceeded",
            details={"retry_after": retry_after},
            status_code=429,
        )
