# MODULE: backend/adapters/nse.py
# TASK:   CHECKLIST.md §1.5
# SPEC:   BACKEND.md §2.2
# PHASE:  1
# STATUS: In Progress

from __future__ import annotations

import itertools
import logging
import time
from datetime import UTC
from datetime import datetime
from typing import Any

import httpx

from backend.adapters.base import DataSourceAdapter
from backend.core.config import settings
from backend.core.exceptions import AdapterError
from backend.core.models import RawData

logger = logging.getLogger(__name__)


class NSEAdapter(DataSourceAdapter):
    """Adapter for fetching pseudo-live market data from NSE endpoints.

    Edge Cases:
        - NSE may return different JSON shapes depending on endpoint behavior.
        - Request can fail with ban-like status codes such as 403/429.
    """

    def __init__(self) -> None:
        """Initialize adapter internals.

        Edge Cases:
            - User-agent rotation falls back to a default tuple from settings.
        """

        self._ua_cycle = itertools.cycle(settings.nse_user_agents)

    @property
    def name(self) -> str:
        """Return adapter identifier.

        Edge Cases:
            - Name remains lowercase for consistent logging keys.
        """

        return "nse"

    def get_priority(self) -> int:
        """Return source priority for the adapter chain.

        Edge Cases:
            - Lower value indicates higher priority in aggregator order.
        """

        return 2

    async def health_check(self) -> bool:
        """Check whether NSE base endpoint is reachable.

        Returns:
            True if the endpoint responds with HTTP 200, else False.

        Edge Cases:
            - Network timeouts return False instead of raising.
        """

        request_started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=settings.nse_timeout_seconds) as client:
                response = await client.get(
                    settings.nse_base_url,
                    headers=self._build_headers(),
                )
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            status_ok = response.status_code == httpx.codes.OK
            logger.info(
                "nse_health_check",
                extra={
                    "source": self.name,
                    "symbol": "",
                    "latency_ms": latency_ms,
                    "status": "ok" if status_ok else "degraded",
                },
            )
            return status_ok
        except (httpx.RequestError, httpx.TimeoutException) as exc:
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            logger.error(
                "nse_health_check_failed",
                extra={
                    "source": self.name,
                    "symbol": "",
                    "latency_ms": latency_ms,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return False

    async def fetch(self, symbol: str) -> list[RawData]:
        """Fetch latest candles for the requested symbol.

        Args:
            symbol: Symbol name such as NIFTY.

        Returns:
            A normalized raw list with OHLC fields.

        Raises:
            AdapterError: If request fails or payload cannot be parsed.

        Edge Cases:
            - Handles HTTP 403/429 as explicit adapter failures.
            - Handles unknown payload structures by raising AdapterError.
        """

        request_started = time.perf_counter()
        symbol_upper = symbol.upper()
        try:
            async with httpx.AsyncClient(timeout=settings.nse_timeout_seconds) as client:
                response = await client.get(
                    settings.nse_quote_url,
                    params={"symbol": symbol_upper},
                    headers=self._build_headers(),
                )

            if response.status_code in (httpx.codes.FORBIDDEN, httpx.codes.TOO_MANY_REQUESTS):
                latency_ms = int((time.perf_counter() - request_started) * 1000)
                logger.error(
                    "nse_fetch_blocked",
                    extra={
                        "source": self.name,
                        "symbol": symbol_upper,
                        "latency_ms": latency_ms,
                        "status": "error",
                        "http_status": response.status_code,
                    },
                )
                raise AdapterError(
                    "NSE blocked request",
                    source=self.name,
                    symbol=symbol_upper,
                    http_status=response.status_code,
                )

            response.raise_for_status()
            payload = response.json()
            rows = self._parse_payload(symbol_upper, payload)
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            logger.info(
                "nse_fetch_success",
                extra={
                    "source": self.name,
                    "symbol": symbol_upper,
                    "latency_ms": latency_ms,
                    "status": "ok",
                },
            )
            return rows
        except httpx.HTTPStatusError as exc:
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            logger.error(
                "nse_fetch_http_error",
                extra={
                    "source": self.name,
                    "symbol": symbol_upper,
                    "latency_ms": latency_ms,
                    "status": "error",
                    "http_status": exc.response.status_code,
                    "error": str(exc),
                },
            )
            raise AdapterError(
                "NSE HTTP error",
                source=self.name,
                symbol=symbol_upper,
                http_status=exc.response.status_code,
            ) from exc
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            logger.error(
                "nse_fetch_network_error",
                extra={
                    "source": self.name,
                    "symbol": symbol_upper,
                    "latency_ms": latency_ms,
                    "status": "error",
                    "error": str(exc),
                },
            )
            raise AdapterError(
                "NSE network failure",
                source=self.name,
                symbol=symbol_upper,
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            latency_ms = int((time.perf_counter() - request_started) * 1000)
            logger.error(
                "nse_fetch_parse_error",
                extra={
                    "source": self.name,
                    "symbol": symbol_upper,
                    "latency_ms": latency_ms,
                    "status": "error",
                    "error": str(exc),
                },
            )
            raise AdapterError(
                "NSE parse failure",
                source=self.name,
                symbol=symbol_upper,
            ) from exc

    def _build_headers(self) -> dict[str, str]:
        """Construct request headers with rotating user-agent.

        Returns:
            Header dictionary for outbound NSE requests.

        Edge Cases:
            - User-agent rotates on every call for ban-risk reduction.
        """

        return {
            "User-Agent": next(self._ua_cycle),
            "Accept": "application/json,text/plain,*/*",
            "Referer": settings.nse_base_url,
        }

    def _parse_payload(self, symbol: str, payload: dict[str, Any]) -> list[RawData]:
        """Parse varying NSE response structures into raw rows.

        Args:
            symbol: Requested symbol in uppercase.
            payload: JSON payload from NSE endpoint.

        Returns:
            Parsed raw OHLC rows.

        Raises:
            ValueError: If no parseable candle is available.

        Edge Cases:
            - Supports chart payload with `grapthData` arrays.
            - Supports quote payload with `priceInfo` fallback.
        """

        if "grapthData" in payload and isinstance(payload["grapthData"], list):
            records: list[RawData] = []
            for candle in payload["grapthData"]:
                if not isinstance(candle, list) or len(candle) < 6:
                    continue
                timestamp = self._floor_to_minute(datetime.fromtimestamp(candle[0], tz=UTC))
                records.append(
                    {
                        "symbol": symbol,
                        "timestamp": timestamp,
                        "open": float(candle[1]),
                        "high": float(candle[2]),
                        "low": float(candle[3]),
                        "close": float(candle[4]),
                        "volume": int(candle[5]) if candle[5] is not None else None,
                    }
                )
            if records:
                return records

        price_info = payload.get("priceInfo")
        if isinstance(price_info, dict):
            high_value = float(price_info.get("intraDayHighLow", {}).get("max", 0.0))
            low_value = float(price_info.get("intraDayHighLow", {}).get("min", 0.0))
            open_value = float(price_info.get("open", 0.0))
            close_value = float(price_info.get("lastPrice", 0.0))
            if high_value == 0.0 and low_value == 0.0:
                raise ValueError("Missing intraday high/low values in NSE payload.")
            timestamp = self._floor_to_minute(datetime.now(tz=UTC))
            return [
                {
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "open": open_value if open_value > 0 else low_value,
                    "high": high_value,
                    "low": low_value,
                    "close": close_value if close_value > 0 else open_value,
                    "volume": None,
                }
            ]

        raise ValueError("Unsupported NSE payload format.")

    def _floor_to_minute(self, timestamp: datetime) -> datetime:
        """Floor a datetime object to UTC minute boundary.

        Args:
            timestamp: Timestamp to normalize.

        Returns:
            UTC minute floored timestamp.

        Edge Cases:
            - Converts naive datetimes to UTC.
        """

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp_utc = timestamp.astimezone(UTC)
        return timestamp_utc.replace(second=0, microsecond=0)
