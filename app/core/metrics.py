from prometheus_client import Counter, Histogram, Gauge, Info

REQUEST_COUNT = Counter(
    "market_data_requests_total", "Total requests", ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "market_data_request_duration_seconds", "Request latency", ["method", "endpoint"]
)

ACTIVE_CONNECTIONS = Gauge("market_data_websocket_connections", "Active WebSocket connections")

DATA_SOURCE_HEALTH = Gauge("market_data_source_health", "Data source health status", ["source"])

ETL_PROCESSED = Counter(
    "market_data_etl_processed_total", "ETL records processed", ["source", "status"]
)

CACHE_HITS = Counter("market_data_cache_hits_total", "Cache hits", ["operation"])

CACHE_MISSES = Counter("market_data_cache_misses_total", "Cache misses", ["operation"])

APP_INFO = Info("market_data", "Application info")
