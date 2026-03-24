import re
import math
from typing import Optional
from datetime import datetime, timezone
from app.core.logging_config import logger


class SentimentEngine:
    BULLISH_KEYWORDS = {
        "surge": 0.8,
        "soar": 0.9,
        "rally": 0.7,
        "gain": 0.5,
        "rise": 0.5,
        "growth": 0.6,
        "profit": 0.6,
        "beat": 0.6,
        "exceed": 0.5,
        "optimistic": 0.6,
        "bullish": 0.8,
        "upside": 0.7,
        "breakout": 0.7,
        "recovery": 0.5,
        "recover": 0.5,
        "strong": 0.5,
        "strength": 0.5,
        "growth": 0.6,
        "expand": 0.5,
        "upgrade": 0.6,
        "buy": 0.6,
        "outperform": 0.7,
        "overweight": 0.5,
        "accumulate": 0.5,
        "boom": 0.8,
        "boost": 0.6,
        "jump": 0.6,
        "spike": 0.7,
        "record": 0.6,
        "high": 0.4,
        "higher": 0.4,
        "best": 0.5,
        "improve": 0.5,
        "success": 0.6,
        "innovate": 0.5,
        "launch": 0.4,
        "partnership": 0.4,
        "deal": 0.4,
        "acquisition": 0.5,
    }

    BEARISH_KEYWORDS = {
        "crash": -0.9,
        "plunge": -0.8,
        "fall": -0.6,
        "drop": -0.5,
        "decline": -0.5,
        "loss": -0.6,
        "miss": -0.5,
        "weak": -0.5,
        "pessimistic": -0.6,
        "bearish": -0.8,
        "downside": -0.7,
        "recession": -0.8,
        "layoff": -0.7,
        "cut": -0.5,
        "reduce": -0.4,
        "sell": -0.6,
        "underperform": -0.7,
        "underweight": -0.5,
        "dump": -0.7,
        "slump": -0.7,
        "tumble": -0.7,
        "sink": -0.6,
        "slip": -0.4,
        "low": -0.4,
        "lower": -0.4,
        "worst": -0.6,
        "worse": -0.5,
        "concern": -0.5,
        "risk": -0.5,
        "volatile": -0.4,
        "uncertainty": -0.5,
        "inflation": -0.4,
        "debt": -0.5,
        "bankruptcy": -0.9,
        "fraud": -0.9,
        "lawsuit": -0.6,
        "investigation": -0.6,
        "probe": -0.5,
        "scandal": -0.8,
        "probe": -0.5,
        "violation": -0.6,
    }

    NEGATION_WORDS = {
        "not",
        "no",
        "never",
        "neither",
        "nobody",
        "nothing",
        "nowhere",
        "hardly",
        "scarcely",
        "barely",
    }

    INTENSIFIERS = {
        "very": 1.5,
        "extremely": 1.8,
        "highly": 1.5,
        "significantly": 1.4,
        "massive": 1.6,
        "huge": 1.5,
        "huge": 1.5,
        "major": 1.3,
        "small": 0.8,
    }

    def __init__(self):
        self.all_keywords = {}
        for word, score in self.BULLISH_KEYWORDS.items():
            self.all_keywords[word] = score
        for word, score in self.BEARISH_KEYWORDS.items():
            if word not in self.all_keywords:
                self.all_keywords[word] = score

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"http\S+|www\.\S+", "", text)
        text = re.sub(r"@\w+|#\w+", "", text)
        text = re.sub(r"\d+", " ", text)
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.lower().strip()

    def tokenize(self, text: str) -> list[str]:
        return self.clean_text(text).split()

    def analyze_sentiment(self, text: str) -> float:
        if not text:
            return 0.0

        tokens = self.tokenize(text)
        if not tokens:
            return 0.0

        scores = []
        n = len(tokens)

        for i, token in enumerate(tokens):
            if token in self.all_keywords:
                base_score = self.all_keywords[token]

                modifier = 1.0

                if i > 0:
                    prev_word = tokens[i - 1]
                    if prev_word in self.NEGATION_WORDS:
                        modifier *= -0.8
                    if prev_word in self.INTENSIFIERS:
                        modifier *= self.INTENSIFIERS[prev_word]

                if i < n - 1:
                    next_word = tokens[i + 1]
                    if next_word in self.INTENSIFIERS:
                        modifier *= self.INTENSIFIERS[next_word]

                scores.append(base_score * modifier)

        if not scores:
            return 0.0

        raw_score = sum(scores) / len(scores)

        return max(-1.0, min(1.0, raw_score))

    def get_sentiment_label(self, score: float) -> str:
        if score > 0.2:
            return "BULLISH"
        elif score < -0.2:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def analyze_article(self, title: str, summary: str = "", content: str = "") -> dict:
        full_text = f"{title} {summary} {content}"
        score = self.analyze_sentiment(full_text)

        title_score = self.analyze_sentiment(title)
        title_weight = 0.4
        content_score = score * (1 - title_weight)

        final_score = (title_score * title_weight) + (content_score * (1 - title_weight))

        final_score = max(-1.0, min(1.0, final_score))

        return {
            "score": round(final_score, 3),
            "label": self.get_sentiment_label(final_score),
            "title_score": round(title_score, 3),
        }

    def compute_weighted_score(self, articles: list[dict], decay_hours: int = 24) -> float:
        if not articles:
            return 0.0

        now = datetime.now(timezone.utc)
        total_weight = 0.0
        weighted_sum = 0.0

        for article in articles:
            published_at = article.get("published_at")
            if isinstance(published_at, str):
                try:
                    published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                except:
                    published_at = now

            hours_old = (now - published_at).total_seconds() / 3600
            decay = math.exp(-hours_old / decay_hours)

            weight = article.get("credibility", 1.0) * decay
            score = article.get("sentiment_score", 0.0)

            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0

        return max(-1.0, min(1.0, weighted_sum / total_weight))


sentiment_engine = SentimentEngine()
