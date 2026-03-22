# MODULE: backend/core/config.py
# TASK:   CHECKLIST.md §1.1
# SPEC:   BACKEND.md Appendix B
# PHASE:  1
# STATUS: In Progress

from functools import lru_cache

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Edge Cases:
        - Missing environment variables will fall back to explicit defaults.
        - Extra environment variables are ignored to avoid startup failure.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="market-data-platform")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    environment: str = Field(default="development")
    api_v1_prefix: str = Field(default="/api/v1")

    database_url: str = Field(
        default="postgresql+asyncpg://user:pass@localhost:5432/marketdata"
    )
    database_pool_size: int = Field(default=20)

    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_pool_size: int = Field(default=50)
    redis_ohlc_ttl_seconds: int = Field(default=60)

    nse_base_url: str = Field(default="https://www.nseindia.com")
    nse_quote_url: str = Field(
        default="https://www.nseindia.com/api/quote-equity"
    )
    nse_timeout_seconds: float = Field(default=10.0)

    poll_interval: int = Field(default=2)
    ws_heartbeat_interval: int = Field(default=30)

    nse_enabled: bool = Field(default=True)
    yahoo_enabled: bool = Field(default=True)
    upstox_enabled: bool = Field(default=False)
    upstox_api_key: str = Field(default="")
    upstox_secret: str = Field(default="")

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: object) -> bool:
        """Parse debug flag from flexible boolean-like inputs.

        Edge Cases:
            - Treats values such as `release`, `production`, and `prod`
              as `False`.
            - Treats values such as `development`, `dev`, and `debug`
              as `True`.
        """

        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "development", "dev"}:
                return True
            if normalized in {
                "0",
                "false",
                "no",
                "off",
                "release",
                "production",
                "prod",
            }:
                return False
        raise ValueError("Invalid DEBUG value. Use boolean-like input.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance.

    Edge Cases:
        - Repeated calls return the same settings object for performance.
    """

    return Settings()


settings: Settings = get_settings()
