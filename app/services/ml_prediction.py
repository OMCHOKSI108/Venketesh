import math
import pickle
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import json
import os

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


class MLPredictionService:
    def __init__(self):
        self.models = {}
        self.scalers = {}
        self.feature_engine = None
        self._init_models()

    def _init_models(self):
        try:
            from app.services.feature_engine import FeatureEngine

            self.feature_engine = FeatureEngine()
        except ImportError:
            pass

        self.direction_model = GradientBoostingClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )

        self.volatility_model = GradientBoostingClassifier(
            n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42
        )

        self.price_scaler = StandardScaler()
        self.volatility_scaler = StandardScaler()

        self.is_trained = False

    def prepare_features(
        self, ohlc_data: List[Dict], sentiment_score: float = 0.0
    ) -> Optional[np.ndarray]:
        if not self.feature_engine:
            return None

        features = self.feature_engine.compute_all_features(ohlc_data, sentiment_score)
        flat_features = self.feature_engine.flatten_features(features)

        feature_vector = self._extract_model_features(flat_features)

        if feature_vector is None or len(feature_vector) < 10:
            return None

        return np.array(feature_vector).reshape(1, -1)

    def _extract_model_features(self, features: Dict) -> List[float]:
        feature_list = []

        key_features = [
            "price_features_returns_1d",
            "price_features_returns_5d",
            "price_features_returns_10d",
            "moving_averages_rsi_14",
            "momentum_indicators_macd",
            "momentum_indicators_macd_signal",
            "momentum_indicators_bb_position",
            "momentum_indicators_stoch_k",
            "volatility_indicators_atr_14",
            "volatility_indicators_volatility_20d",
            "volume_indicators_volume_ratio",
            "pattern_features_is_bullish",
            "sentiment_features_sentiment_impact_impact_score",
        ]

        for key in key_features:
            value = features.get(key, 0.0)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                value = 0.0
            feature_list.append(float(value))

        if len(feature_list) < 13:
            feature_list.extend([0.0] * (13 - len(feature_list)))

        return feature_list[:13]

    def create_training_data(self, historical_data: List[Dict]) -> Tuple[np.ndarray, np.ndarray]:
        if len(historical_data) < 50:
            return None, None

        X = []
        y_direction = []
        y_volatility = []

        for i in range(50, len(historical_data)):
            window = historical_data[i - 50 : i]

            ohlc_for_features = [
                {
                    "open": d["open"],
                    "high": d["high"],
                    "low": d["low"],
                    "close": d["close"],
                    "volume": d.get("volume", 0),
                }
                for d in window
            ]

            features = self.prepare_features(ohlc_for_features)
            if features is not None:
                X.append(features[0])

                future_return = (
                    (historical_data[i]["close"] - historical_data[i - 1]["close"])
                    / historical_data[i - 1]["close"]
                    * 100
                )

                if future_return > 0.5:
                    y_direction.append(1)
                elif future_return < -0.5:
                    y_direction.append(-1)
                else:
                    y_direction.append(0)

                volatility = abs(future_return)
                y_volatility.append(1 if volatility > 1.0 else 0)

        if len(X) < 20:
            return None, None

        return np.array(X), np.array(y_direction)

    def train(self, historical_data: List[Dict]) -> Dict:
        X, y = self.create_training_data(historical_data)

        if X is None or len(X) < 20:
            return {"status": "error", "message": "Insufficient training data"}

        try:
            X_scaled = self.price_scaler.fit_transform(X)

            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )

            self.direction_model.fit(X_train, y_train)

            train_score = self.direction_model.score(X_train, y_train)
            test_score = self.direction_model.score(X_test, y_test)

            self.is_trained = True

            return {
                "status": "success",
                "train_accuracy": round(train_score, 3),
                "test_accuracy": round(test_score, 3),
                "samples": len(X),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def predict_direction(self, ohlc_data: List[Dict], sentiment_score: float = 0.0) -> Dict:
        if not self.is_trained:
            return self._get_default_prediction()

        features = self.prepare_features(ohlc_data, sentiment_score)

        if features is None:
            return self._get_default_prediction()

        try:
            features_scaled = self.price_scaler.transform(features)

            prediction = self.direction_model.predict(features_scaled)[0]
            probabilities = self.direction_model.predict_proba(features_scaled)[0]

            confidence = max(probabilities) if max(probabilities) > 0.5 else 0.5

            direction_map = {-1: "DOWN", 0: "SIDEWAYS", 1: "UP"}

            return {
                "direction": direction_map.get(prediction, "UNKNOWN"),
                "confidence": round(confidence, 3),
                "probabilities": {
                    "down": round(probabilities[0], 3),
                    "sideways": round(probabilities[1], 3) if len(probabilities) > 2 else 0.0,
                    "up": round(probabilities[2], 3)
                    if len(probabilities) > 2
                    else round(probabilities[1], 3),
                },
            }
        except Exception as e:
            return self._get_default_prediction()

    def _get_default_prediction(self) -> Dict:
        return {
            "direction": "SIDEWAYS",
            "confidence": 0.33,
            "probabilities": {"down": 0.33, "sideways": 0.34, "up": 0.33},
        }

    def calculate_support_resistance(self, ohlc_data: List[Dict], window: int = 20) -> Dict:
        if len(ohlc_data) < window:
            return {"support": None, "resistance": None}

        closes = [d["close"] for d in ohlc_data[-window:]]

        support = min(closes)
        resistance = max(closes)

        current_price = closes[-1]

        support_distance = ((current_price - support) / current_price) * 100
        resistance_distance = ((resistance - current_price) / current_price) * 100

        return {
            "support": round(support, 2),
            "resistance": round(resistance, 2),
            "support_distance_pct": round(support_distance, 2),
            "resistance_distance_pct": round(resistance_distance, 2),
            "current_price": round(current_price, 2),
        }

    def calculate_forecast(self, ohlc_data: List[Dict], days: int = 5) -> Dict:
        if len(ohlc_data) < 20:
            return {"forecast": [], "confidence": 0}

        closes = [d["close"] for d in ohlc_data]

        returns = np.diff(closes) / closes[:-1]
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        current_price = closes[-1]

        forecast = []
        for i in range(1, days + 1):
            predicted_price = current_price * (1 + mean_return * i)
            upper_bound = current_price * (1 + (mean_return + 2 * std_return) * i)
            lower_bound = current_price * (1 + (mean_return - 2 * std_return) * i)

            forecast.append(
                {
                    "day": i,
                    "predicted": round(predicted_price, 2),
                    "upper": round(upper_bound, 2),
                    "lower": round(lower_bound, 2),
                }
            )

        confidence = 1 - min(abs(std_return) * 10, 1)

        return {
            "forecast": forecast,
            "confidence": round(confidence, 2),
            "trend": "BULLISH"
            if mean_return > 0.001
            else "BEARISH"
            if mean_return < -0.001
            else "SIDEWAYS",
        }

    def get_signals(self, ohlc_data: List[Dict], sentiment: float = 0.0) -> Dict:
        direction = self.predict_direction(ohlc_data, sentiment)
        sr_levels = self.calculate_support_resistance(ohlc_data)
        forecast = self.calculate_forecast(ohlc_data)

        signals = []

        if direction["direction"] == "UP" and direction["confidence"] > 0.6:
            signals.append(
                {"type": "BUY", "strength": direction["confidence"], "reason": "Bullish momentum"}
            )

        if direction["direction"] == "DOWN" and direction["confidence"] > 0.6:
            signals.append(
                {"type": "SELL", "strength": direction["confidence"], "reason": "Bearish momentum"}
            )

        if sentiment > 0.3:
            signals.append(
                {
                    "type": "BUY",
                    "strength": min(abs(sentiment), 1.0),
                    "reason": "Positive news sentiment",
                }
            )
        elif sentiment < -0.3:
            signals.append(
                {
                    "type": "SELL",
                    "strength": min(abs(sentiment), 1.0),
                    "reason": "Negative news sentiment",
                }
            )

        current_price = ohlc_data[-1]["close"] if ohlc_data else 0
        if sr_levels.get("resistance") and current_price > 0:
            distance_to_resistance = sr_levels["resistance_distance_pct"]
            if distance_to_resistance < 2:
                signals.append(
                    {
                        "type": "SELL",
                        "strength": 0.7,
                        "reason": f"Near resistance {sr_levels['resistance']}",
                    }
                )
            elif distance_to_resistance > 10:
                signals.append(
                    {
                        "type": "BUY",
                        "strength": 0.6,
                        "reason": f"Room to grow to {sr_levels['resistance']}",
                    }
                )

        return {
            "signals": signals,
            "direction": direction,
            "levels": sr_levels,
            "forecast": forecast,
            "timestamp": datetime.now().isoformat(),
        }


ml_prediction_service = MLPredictionService()
