from typing import Dict
from app.adapters.base import DataSourceAdapter
from app.adapters.nse import NSEAdapter
from app.adapters.yahoo import YahooAdapter
from app.adapters.upstox import UpstoxAdapter
from app.adapters.alphavantage import AlphaVantageAdapter
from app.adapters.finnhub import FinnhubAdapter
from app.config import get_settings
from app.core.logging_config import logger

settings = get_settings()


class AdapterFactory:
    _adapters: Dict[str, DataSourceAdapter] = {}

    @classmethod
    def get_adapters(cls) -> Dict[str, DataSourceAdapter]:
        if not cls._adapters:
            cls._initialize_adapters()
        return cls._adapters

    @classmethod
    def _initialize_adapters(cls):
        if settings.nse_enabled:
            cls._adapters["nse"] = NSEAdapter()
            logger.info("adapter_initialized", source="nse")

        if settings.yahoo_enabled:
            cls._adapters["yahoo"] = YahooAdapter()
            logger.info("adapter_initialized", source="yahoo")

        if settings.upstox_enabled and settings.upstox_api_key:
            cls._adapters["upstox"] = UpstoxAdapter()
            logger.info("adapter_initialized", source="upstox")

        if settings.alphavantage_enabled and settings.alphavantage_api_key:
            cls._adapters["alphavantage"] = AlphaVantageAdapter(settings.alphavantage_api_key)
            logger.info("adapter_initialized", source="alphavantage")

        if settings.finnhub_enabled and settings.finnhub_api_key:
            cls._adapters["finnhub"] = FinnhubAdapter(settings.finnhub_api_key)
            logger.info("adapter_initialized", source="finnhub")

        if not cls._adapters:
            logger.warning("no_adapters_enabled")

    @classmethod
    def get_adapter(cls, source: str) -> DataSourceAdapter:
        adapters = cls.get_adapters()
        if source not in adapters:
            raise ValueError(f"Adapter for source '{source}' not found")
        return adapters[source]

    @classmethod
    def get_all_sources(cls) -> list[str]:
        return list(cls.get_adapters().keys())

    @classmethod
    async def close_all(cls):
        for adapter in cls._adapters.values():
            await adapter.close()
