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

    @property
    def seconds(self) -> int:
        mapping = {
            "1m": 60,
            "5m": 300,
            "15m": 900,
            "30m": 1800,
            "1h": 3600,
            "4h": 14400,
            "1d": 86400,
            "1w": 604800,
        }
        return mapping[self.value]


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


SUPPORTED_SYMBOLS = ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTYSENSEX"]

DEFAULT_TIMEFRAME = TimeFrame.MINUTE_1
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000

REDIS_KEY_PREFIX = "market_data"
OHLC_CACHE_TTL = 60
SOURCE_HEALTH_TTL = 30

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

RATE_LIMIT_REQUESTS_DEFAULT = 100
RATE_LIMIT_WINDOW_DEFAULT = 60

WS_HEARTBEAT_INTERVAL = 30
WS_MAX_CONNECTIONS_PER_IP = 5
WS_MAX_SUBSCRIPTIONS_PER_CONNECTION = 50
