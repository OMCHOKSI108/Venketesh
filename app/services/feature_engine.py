import math
from typing import List, Dict, Optional
from datetime import datetime, timezone
import numpy as np


class FeatureEngine:
    """Feature engineering for stock price prediction"""

    def __init__(self):
        self.feature_cache = {}

    def compute_all_features(self, ohlc_data: List[Dict], sentiment_score: float = 0.0) -> Dict:
        """Compute all features from OHLC data and sentiment"""
        if not ohlc_data or len(ohlc_data) < 20:
            return {}

        closes = [d["close"] for d in ohlc_data]
        highs = [d["high"] for d in ohlc_data]
        lows = [d["low"] for d in ohlc_data]
        opens = [d["open"] for d in ohlc_data]
        volumes = [d.get("volume", 0) for d in ohlc_data]

        features = {}

        features["price_features"] = self._compute_price_features(closes, highs, lows, opens)
        features["moving_averages"] = self._compute_moving_averages(closes)
        features["momentum_indicators"] = self._compute_momentum(closes, highs, lows)
        features["volatility_indicators"] = self._compute_volatility(closes, highs, lows)
        features["volume_indicators"] = self._compute_volume_indicators(closes, volumes)
        features["pattern_features"] = self._compute_pattern_features(closes, highs, lows, opens)
        features["sentiment_features"] = {
            "news_sentiment": sentiment_score,
            "sentiment_impact": self._sentiment_impact(sentiment_score),
        }

        return features

    def _compute_price_features(self, closes: List, highs: List, lows: List, opens: List) -> Dict:
        """Basic price-based features"""
        c = np.array(closes)
        current_price = c[-1]

        returns = np.diff(c) / c[:-1] * 100 if len(c) > 1 else [0]

        return {
            "current_price": current_price,
            "returns_1d": returns[-1] if len(returns) > 0 else 0,
            "returns_5d": np.mean(returns[-5:])
            if len(returns) >= 5
            else np.mean(returns)
            if len(returns) > 0
            else 0,
            "returns_10d": np.mean(returns[-10:])
            if len(returns) >= 10
            else np.mean(returns)
            if len(returns) > 0
            else 0,
            "returns_20d": np.mean(returns[-20:])
            if len(returns) >= 20
            else np.mean(returns)
            if len(returns) > 0
            else 0,
            "price_range_1d": (highs[-1] - lows[-1]) / closes[-2] * 100 if len(closes) > 1 else 0,
            "gap_up": (opens[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0,
        }

    def _compute_moving_averages(self, closes: List) -> Dict:
        """Moving average features"""
        c = np.array(closes)
        ma_features = {}

        for period in [5, 10, 20, 50, 100, 200]:
            if len(c) >= period:
                ma = np.mean(c[-period:])
                ma_features[f"ma_{period}"] = ma
                ma_features[f"ma_{period}_slope"] = self._compute_slope(c[-period:])
                ma_features[f"ma_{period}_position"] = (c[-1] - ma) / ma * 100

        if "ma_20" in ma_features and "ma_50" in ma_features:
            ma_features["ma_cross_20_50"] = 1 if ma_features["ma_20"] > ma_features["ma_50"] else -1
        if "ma_50" in ma_features and "ma_200" in ma_features:
            ma_features["ma_cross_50_200"] = (
                1 if ma_features["ma_50"] > ma_features["ma_200"] else -1
            )

        return ma_features

    def _compute_momentum(self, closes: List, highs: List, lows: List) -> Dict:
        """Momentum indicators"""
        c = np.array(closes)
        h = np.array(highs)
        l = np.array(lows)
        n = len(c)

        momentum = {}

        if n >= 14:
            delta = c[-14:]
            gains = np.where(np.diff(delta) > 0, np.diff(delta), 0)
            losses = np.where(np.diff(delta) < 0, -np.diff(delta), 0)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)

            if avg_loss != 0:
                rs = avg_gain / avg_loss
                momentum["rsi_14"] = 100 - (100 / (1 + rs))
            else:
                momentum["rsi_14"] = 100

        if n >= 12:
            ema12 = self._ema(c, 12)
            ema26 = self._ema(c, 26)
            momentum["macd"] = ema12 - ema26
            momentum["macd_signal"] = self._ema(np.array([ema12 - ema26]), 9)

        if n >= 20:
            sma20 = np.mean(c[-20:])
            std20 = np.std(c[-20:])
            momentum["bb_upper"] = sma20 + 2 * std20
            momentum["bb_lower"] = sma20 - 2 * std20
            momentum["bb_width"] = (momentum["bb_upper"] - momentum["bb_lower"]) / sma20 * 100
            momentum["bb_position"] = (
                (c[-1] - momentum["bb_lower"]) / (momentum["bb_upper"] - momentum["bb_lower"]) * 100
            )

        if n >= 14:
            high14 = np.max(h[-14:])
            low14 = np.min(l[-14:])
            if high14 != low14:
                momentum["stoch_k"] = ((c[-1] - low14) / (high14 - low14)) * 100
            else:
                momentum["stoch_k"] = 50

        if n >= 9:
            momentum["stoch_d"] = momentum.get("stoch_k", 50)

        return momentum

    def _compute_volatility(self, closes: List, highs: List, lows: List) -> Dict:
        """Volatility indicators"""
        c = np.array(closes)
        h = np.array(highs)
        l = np.array(lows)
        n = len(c)

        volatility = {}

        if n >= 14:
            returns = np.diff(c[-14:]) / c[-15:-1]
            volatility["atr_14"] = np.mean(
                np.maximum(
                    h[-14:] - l[-14:],
                    np.maximum(abs(h[-14:] - c[-15:-1]), abs(l[-14:] - c[-15:-1])),
                )
            )

        if n >= 20:
            returns = np.diff(c[-20:]) / c[-21:-1]
            volatility["volatility_20d"] = np.std(returns) * math.sqrt(252) * 100
            volatility["volatility_5d"] = np.std(returns[-5:]) * math.sqrt(252) * 100

        if n >= 252:
            yearly_returns = np.diff(c[-252:]) / c[-253:-1]
            volatility["historical_volatility"] = np.std(yearly_returns) * math.sqrt(252) * 100

        return volatility

    def _compute_volume_indicators(self, closes: List, volumes: List) -> Dict:
        """Volume-based features"""
        v = np.array(volumes)
        c = np.array(closes)
        n = len(c)

        volume_features = {}

        if n >= 20:
            volume_features["volume_ma_20"] = np.mean(v[-20:])
            volume_features["volume_ratio"] = (
                v[-1] / volume_features["volume_ma_20"]
                if volume_features["volume_ma_20"] > 0
                else 1
            )

        if n >= 1:
            volume_features["obv"] = self._obv(c, v)
            volume_features["obv_ma"] = np.mean(v[-10:]) if len(v) >= 10 else v[-1]

        if "volume_ratio" in volume_features:
            if volume_features["volume_ratio"] > 2:
                volume_features["volume_surge"] = 1
            elif volume_features["volume_ratio"] < 0.5:
                volume_features["volume_drop"] = 1
            else:
                volume_features["volume_normal"] = 1

        return volume_features

    def _compute_pattern_features(self, closes: List, highs: List, lows: List, opens: List) -> Dict:
        """Candlestick pattern features"""
        c = np.array(closes)
        h = np.array(highs)
        l = np.array(lows)
        o = np.array(opens)
        n = len(c)

        patterns = {}

        if n >= 1:
            body = abs(c[-1] - o[-1])
            upper_shadow = h[-1] - max(c[-1], o[-1])
            lower_shadow = min(c[-1], o[-1]) - l[-1]
            total_range = h[-1] - l[-1]

            if total_range > 0:
                patterns["body_ratio"] = body / total_range
                patterns["upper_shadow_ratio"] = upper_shadow / total_range
                patterns["lower_shadow_ratio"] = lower_shadow / total_range

            patterns["is_bullish"] = 1 if c[-1] > o[-1] else 0
            patterns["is_doji"] = 1 if body < total_range * 0.1 else 0

        if n >= 3:
            patterns["three_white_soldiers"] = self._detect_three_white_soldiers(c, o)
            patterns["three_black_crows"] = self._detect_three_black_crows(c, o)

        return patterns

    def _sentiment_impact(self, sentiment_score: float) -> Dict:
        """Calculate sentiment impact on price"""
        if sentiment_score > 0.5:
            impact = "STRONG_BULLISH"
        elif sentiment_score > 0.2:
            impact = "BULLISH"
        elif sentiment_score < -0.5:
            impact = "STRONG_BEARISH"
        elif sentiment_score < -0.2:
            impact = "BEARISH"
        else:
            impact = "NEUTRAL"

        return {
            "impact_label": impact,
            "impact_score": abs(sentiment_score),
            "impact_direction": 1 if sentiment_score > 0 else -1 if sentiment_score < 0 else 0,
        }

    def _ema(self, data: np.array, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return np.mean(data)

        ema = np.mean(data[:period])
        multiplier = 2 / (period + 1)

        for price in data[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _compute_slope(self, data: np.array) -> float:
        """Calculate slope of linear regression"""
        n = len(data)
        if n < 2:
            return 0

        x = np.arange(n)
        y = data

        x_mean = np.mean(x)
        y_mean = np.mean(y)

        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean) ** 2)

        if denominator == 0:
            return 0

        return numerator / denominator

    def _obv(self, closes: np.array, volumes: np.array) -> float:
        """On-Balance Volume"""
        obv = 0
        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv += volumes[i]
            elif closes[i] < closes[i - 1]:
                obv -= volumes[i]
        return obv

    def _detect_three_white_soldiers(self, closes: np.array, opens: np.array) -> int:
        """Detect Three White Soldiers pattern"""
        if len(closes) < 3:
            return 0

        for i in range(-3, 0):
            if closes[i] <= opens[i]:
                return 0
            if i > -3 and closes[i] <= closes[i + 1]:
                return 0
        return 1

    def _detect_three_black_crows(self, closes: np.array, opens: np.array) -> int:
        """Detect Three Black Crows pattern"""
        if len(closes) < 3:
            return 0

        for i in range(-3, 0):
            if closes[i] >= opens[i]:
                return 0
            if i > -3 and closes[i] >= closes[i + 1]:
                return 0
        return 1

    def flatten_features(self, features: Dict) -> Dict:
        """Flatten nested feature dictionary for ML models"""
        flat = {}
        for category, cat_features in features.items():
            if isinstance(cat_features, dict):
                for key, value in cat_features.items():
                    flat[f"{category}_{key}"] = value
            else:
                flat[category] = cat_features
        return flat


feature_engine = FeatureEngine()
