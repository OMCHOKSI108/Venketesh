from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "market-data-platform"
    debug: bool = False
    log_level: str = "info"
    environment: str = "development"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql://postgres:postgres@localhost:5432/marketdata"
    database_pool_size: int = 20
    database_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    redis_pool_size: int = 50

    secret_key: str = "change-this-to-a-random-secret-key-in-production"
    api_key_header: str = "X-API-Key"

    nse_enabled: bool = True
    nse_base_url: str = "https://www.nseindia.com"
    yahoo_enabled: bool = True
    upstox_enabled: bool = False
    upstox_api_key: str = ""
    upstox_secret: str = ""

    rate_limit_requests: int = 100
    rate_limit_window: int = 60

    ws_heartbeat_interval: int = 30
    ws_max_connections_per_ip: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
