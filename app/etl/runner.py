"""
ETL Pipeline Runner with Logging
Can be run standalone or called from Airflow
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any
import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

SYMBOLS = {
    "indian": ["NIFTY", "BANKNIFTY", "SENSEX", "NIFTYIT"],
    "us": ["DOWJONES", "NASDAQ", "SP500"],
    "world": ["FTSE", "DAX", "NIKKEI"],
}

YAHOO_SYMBOL_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX": "^BSESN",
    "NIFTYIT": "^NSEMDCP",
    "DOWJONES": "^DJI",
    "NASDAQ": "^NDX",
    "SP500": "^GSPC",
    "FTSE": "^FTSE",
    "DAX": "^GDAXI",
    "NIKKEI": "^N225",
}


class ETLPipeline:
    def __init__(self, api_base: str = None):
        self.api_base = api_base or "http://localhost:8000"
        self.logs: List[Dict[str, Any]] = []

    def add_log(self, level: str, message: str, details: dict = None):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "details": details or {},
        }
        self.logs.append(log_entry)
        getattr(logger, level.lower())(message)

    async def extract_from_yahoo(self, symbol: str) -> dict:
        """EXTRACT: Fetch data from Yahoo Finance"""
        yahoo_symbol = YAHOO_SYMBOL_MAP.get(symbol, f"{symbol}.NS")
        self.add_log("info", f"Extracting {symbol} from Yahoo (mapped to {yahoo_symbol})")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
                params = {"interval": "1d", "range": "5d", "events": "history"}

                response = await client.get(url, params=params)

                if response.status_code != 200:
                    self.add_log(
                        "warning", f"Yahoo API returned {response.status_code}, using fallback"
                    )
                    return self._generate_fallback_data(symbol)

                data = response.json()

                if "chart" not in data or "result" not in data["chart"]:
                    self.add_log("warning", "No chart data found, using fallback")
                    return self._generate_fallback_data(symbol)

                result = data["chart"]["result"]
                if not result:
                    self.add_log("warning", "Empty result from Yahoo, using fallback")
                    return self._generate_fallback_data(symbol)

                meta = result[0].get("meta", {})
                indicators = result[0].get("indicators", {}).get("quote", [{}])[0]

                close_prices = indicators.get("close", [])
                open_prices = indicators.get("open", [])
                high_prices = indicators.get("high", [])
                low_prices = indicators.get("low", [])
                timestamps = result[0].get("timestamp", [])

                valid_prices = [(i, p) for i, p in enumerate(close_prices) if p is not None]

                if not valid_prices:
                    return self._generate_fallback_data(symbol)

                latest_idx = valid_prices[-1][0]
                regular_price = meta.get("regularMarketPrice") or close_prices[latest_idx]

                extracted_data = {
                    "symbol": symbol,
                    "timestamp": datetime.fromtimestamp(
                        timestamps[latest_idx], tz=timezone.utc
                    ).isoformat()
                    if timestamps
                    else datetime.now(timezone.utc).isoformat(),
                    "timeframe": "1d",
                    "open": float(open_prices[latest_idx])
                    if open_prices[latest_idx]
                    else float(regular_price),
                    "high": float(meta.get("regularMarketDayHigh"))
                    or float(high_prices[latest_idx])
                    if high_prices[latest_idx]
                    else float(regular_price * 1.005),
                    "low": float(meta.get("regularMarketDayLow")) or float(low_prices[latest_idx])
                    if low_prices[latest_idx]
                    else float(regular_price * 0.995),
                    "close": float(regular_price),
                    "volume": int(meta.get("regularMarketVolume")) or 1000000,
                    "is_closed": meta.get("marketState") == "CLOSED",
                    "source": "yahoo",
                }

                self.add_log(
                    "info", f"Extracted {symbol}: Close={extracted_data['close']}", extracted_data
                )
                return extracted_data

        except Exception as e:
            self.add_log("error", f"Error extracting {symbol}: {str(e)}")
            return self._generate_fallback_data(symbol)

    def _generate_fallback_data(self, symbol: str) -> dict:
        """Generate realistic fallback data"""
        import random

        base_prices = {
            "NIFTY": 22500,
            "BANKNIFTY": 48000,
            "SENSEX": 73000,
            "NIFTYIT": 32000,
            "DOWJONES": 46000,
            "NASDAQ": 17500,
            "SP500": 5800,
            "FTSE": 7800,
            "DAX": 17500,
            "NIKKEI": 39000,
        }
        base = base_prices.get(symbol, 10000)
        price = base * (1 + (random.random() - 0.5) * 0.02)

        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timeframe": "1d",
            "open": float(price),
            "high": float(price * 1.005),
            "low": float(price * 0.995),
            "close": float(price),
            "volume": random.randint(500000, 5000000),
            "is_closed": False,
            "source": "yahoo-generated",
        }

    async def transform(self, data: dict) -> dict:
        """TRANSFORM: Add calculated fields"""
        self.add_log("info", f"Transforming data for {data['symbol']}")

        data["change"] = round(data["close"] - data["open"], 2)
        data["change_percent"] = (
            round((data["change"] / data["open"]) * 100, 2) if data["open"] > 0 else 0
        )

        data["day_range"] = round(data["high"] - data["low"], 2)
        data["volatility"] = round((data["high"] - data["low"]) / data["close"] * 100, 2)

        self.add_log(
            "info",
            f"Transformed {data['symbol']}: Change={data['change']}, Change%={data['change_percent']}%",
            data,
        )
        return data

    async def load_to_api(self, data: dict) -> bool:
        """LOAD: Send to API to store in database"""
        self.add_log("info", f"Loading {data['symbol']} to database via API")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base}/api/v1/ohlc/{data['symbol']}/fetch",
                    params={"timeframe": "1d"},
                )

                if response.status_code == 200:
                    result = response.json()
                    success = result.get("success", False)
                    if success:
                        self.add_log("info", f"Successfully loaded {data['symbol']} to database")
                    else:
                        self.add_log("warning", f"API returned failure for {data['symbol']}")
                    return success
                else:
                    self.add_log("error", f"API returned {response.status_code}")
                    return False
        except Exception as e:
            self.add_log("error", f"Error loading to API: {str(e)}")
            return False

    async def run_pipeline(
        self, symbols: List[str] = None, category: str = "all"
    ) -> Dict[str, Any]:
        """Run complete ETL pipeline"""
        self.logs = []
        self.add_log("info", f"Starting ETL pipeline for category: {category}")

        if symbols is None:
            symbols = []
            if category == "all":
                for cat_symbols in SYMBOLS.values():
                    symbols.extend(cat_symbols)
            else:
                symbols = SYMBOLS.get(category, [])

        results = {"success": 0, "failed": 0, "symbols": []}

        for symbol in symbols:
            try:
                self.add_log("info", f"Processing {symbol}")

                extracted = await self.extract_from_yahoo(symbol)
                transformed = await self.transform(extracted)
                loaded = await self.load_to_api(transformed)

                if loaded:
                    results["success"] += 1
                else:
                    results["failed"] += 1

                results["symbols"].append(
                    {
                        "symbol": symbol,
                        "success": loaded,
                        "close": transformed.get("close"),
                        "change": transformed.get("change"),
                        "change_percent": transformed.get("change_percent"),
                    }
                )

            except Exception as e:
                self.add_log("error", f"Failed to process {symbol}: {str(e)}")
                results["failed"] += 1
                results["symbols"].append({"symbol": symbol, "success": False, "error": str(e)})

        self.add_log(
            "info", f"Pipeline complete: {results['success']} success, {results['failed']} failed"
        )
        return results

    def get_logs(self) -> List[Dict[str, Any]]:
        return self.logs


async def run_etl_with_logs(category: str = "all"):
    """Run ETL and return logs"""
    pipeline = ETLPipeline()
    results = await pipeline.run_pipeline(category=category)
    return {"results": results, "logs": pipeline.get_logs()}


if __name__ == "__main__":
    import json

    result = asyncio.run(run_etl_with_logs())
    print("\n" + "=" * 50)
    print("ETL PIPELINE RESULTS")
    print("=" * 50)
    print(json.dumps(result["results"], indent=2))
    print("\n" + "=" * 50)
    print("LOGS")
    print("=" * 50)
    for log in result["logs"]:
        print(f"[{log['timestamp']}] {log['level'].upper()}: {log['message']}")
