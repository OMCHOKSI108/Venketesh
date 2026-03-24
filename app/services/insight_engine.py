from datetime import datetime, timezone
from typing import Optional
import math
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
from app.models.ohlc import OHLCData
from app.core.constants import SUPPORTED_SYMBOLS
from app.core.logging_config import logger
from app.services.cache import cache_service
from app.config import get_settings

settings = get_settings()
INSIGHTS_CACHE_TTL = 60


class InsightEngine:
    def __init__(self):
        self.symbols = SUPPORTED_SYMBOLS
        self.ma_periods = {"ma_20": 20, "ma_50": 50}
        self.volatility_period = 20

    async def compute_all_insights(self, db: Session) -> list[dict]:
        cached = await cache_service.get_json("insights:all")
        if cached:
            logger.info("insights_cache_hit")
            return cached

        insights = []
        for symbol in self.symbols:
            insight = await self.compute_insight(db, symbol)
            if insight:
                insights.append(insight)

        if insights:
            await cache_service.set("insights:all", insights, ttl=INSIGHTS_CACHE_TTL)

        return insights

    async def compute_insight(self, db: Session, symbol: str) -> Optional[dict]:
        records = await self._get_historical_data(db, symbol, limit=60)
        if not records or len(records) < 5:
            return None

        prices = [float(r.close) for r in reversed(records)]
        timestamps = [r.timestamp for r in reversed(records)]

        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) > 1 else current_price

        return_1d = ((current_price - prev_price) / prev_price * 100) if prev_price > 0 else 0

        ma_20 = self._calculate_ma(prices, 20)
        ma_50 = self._calculate_ma(prices, 50)

        volatility_20d = self._calculate_volatility(prices, 20)

        trend = "BULLISH" if ma_20 and ma_50 and ma_20 > ma_50 else "BEARISH"

        z_score = 0.0
        if volatility_20d > 0 and ma_20:
            z_score = (current_price - ma_20) / volatility_20d

        high_20 = max(prices[-20:]) if len(prices) >= 20 else max(prices)
        low_20 = min(prices[-20:]) if len(prices) >= 20 else min(prices)

        range_position = 0.0
        if high_20 > low_20:
            range_position = (current_price - low_20) / (high_20 - low_20)
        range_position = max(0.0, min(1.0, range_position))

        signal = self._compute_signal(z_score, trend)

        return {
            "symbol": symbol,
            "price": round(current_price, 2),
            "return_1d": round(return_1d, 2),
            "volatility_20d": round(volatility_20d, 2) if volatility_20d else 0.0,
            "ma_20": round(ma_20, 2) if ma_20 else 0.0,
            "ma_50": round(ma_50, 2) if ma_50 else 0.0,
            "trend": trend,
            "z_score": round(z_score, 2),
            "range_position": round(range_position, 3),
            "signal": signal,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _get_historical_data(
        self, db: Session, symbol: str, limit: int = 60
    ) -> list[OHLCData]:
        query = (
            select(OHLCData)
            .where(and_(OHLCData.symbol == symbol, OHLCData.timeframe == "1d"))
            .order_by(OHLCData.timestamp.desc())
            .limit(limit)
        )
        result = db.execute(query)
        return list(result.scalars().all())

    def _calculate_ma(self, prices: list[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    def _calculate_volatility(self, prices: list[float], period: int) -> Optional[float]:
        if len(prices) < period + 1:
            return None

        returns = []
        for i in range(1, min(period + 1, len(prices))):
            ret = (prices[-i] - prices[-i - 1]) / prices[-i - 1]
            returns.append(ret)

        if not returns:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        return std_dev * math.sqrt(252) * 100

    def _compute_signal(self, z_score: float, trend: str) -> str:
        if z_score < -1.5 and trend == "BULLISH":
            return "BUY"
        elif z_score > 1.5 and trend == "BEARISH":
            return "SELL"
        return "NEUTRAL"

    async def get_insight(self, db: Session, symbol: str) -> Optional[dict]:
        symbol = symbol.upper()
        insights = await self.compute_all_insights(db)
        for insight in insights:
            if insight["symbol"] == symbol:
                return insight
        return None


insight_engine = InsightEngine()
