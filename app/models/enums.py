from enum import Enum


class TimeFrame(str, Enum):
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"


class DataSource(str, Enum):
    NSE = "nse"
    YAHOO = "yahoo"
    UPSTOX = "upstox"


class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"
    NYSE = "NYSE"
    NASDAQ = "NASDAQ"


class InstrumentType(str, Enum):
    INDEX = "INDEX"
    STOCK = "STOCK"
    ETF = "ETF"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"


class SourceStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
