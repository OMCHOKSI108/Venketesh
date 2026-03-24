# ML Pipeline Architecture - Production Finance Platform

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        REAL-TIME DATA INGESTION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Yahoo Finance │  │ Alpha Vintage│  │   Finnhub   │  │  News RSS   │   │
│  │   (Real-time) │  │   (Daily)   │  │   (Minute)  │  │  (Event)    │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                  │                  │                  │           │
│         ▼                  ▼                  ▼                  ▼           │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                    APACHE KAFKA / REDIS STREAM              │           │
│  │                    (Real-time Message Broker)               │           │
│  └──────────────────────────────┬──────────────────────────────┘           │
└──────────────────────────────────┼───────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                         PROCESSING LAYER                                     │
├──────────────────────────────────┼───────────────────────────────────────────┤
│                                  ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │              APACHE SPARK STRUCTURED STREAMING             │            │
│  │         (Real-time Processing + Feature Computation)         │            │
│  └──────────────────────────────┬──────────────────────────────┘            │
│                                   │                                           │
│         ┌────────────────────────┼────────────────────────┐                  │
│         ▼                        ▼                        ▼                  │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐              │
│  │  Features   │        │  Sentiment  │        │  Storage   │              │
│  │  Engine    │        │  Analyzer   │        │  (Postgres)│              │
│  └─────────────┘        └─────────────┘        └─────────────┘              │
└───────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                         ML LAYER                                             │
├──────────────────────────────────┼───────────────────────────────────────────┤
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                    MLFLOW MODEL REGISTRY                     │            │
│  │              (Versioning, Staging, Production)             │            │
│  └──────────────────────────────┬──────────────────────────────┘            │
│                                   │                                           │
│         ┌────────────────────────┼────────────────────────┐                  │
│         ▼                        ▼                        ▼                  │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐              │
│  │   LSTM      │        │  Prophet    │        │  Ensemble   │              │
│  │  Predictor  │        │ Forecaster │        │  Model      │              │
│  └─────────────┘        └─────────────┘        └─────────────┘              │
└───────────────────────────────────────────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼───────────────────────────────────────────┐
│                         API & DEPLOYMENT LAYER                              │
├──────────────────────────────────┼───────────────────────────────────────────┤
│                                  ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐            │
│  │                    FASTAPI (Prediction Server)               │            │
│  │         (Real-time inference, WebSocket for live updates)    │            │
│  └──────────────────────────────┬──────────────────────────────┘            │
│                                   │                                           │
│         ┌────────────────────────┼────────────────────────┐                  │
│         ▼                        ▼                        ▼                  │
│  ┌─────────────┐        ┌─────────────┐        ┌─────────────┐              │
│  │  Dashboard  │        │  Alerts     │        │  Reports    │              │
│  │  (React)   │        │  (Webhook)  │        │  (Email)   │              │
│  └─────────────┘        └─────────────┘        └─────────────┘              │
└───────────────────────────────────────────────────────────────────────────────┘

```

## 2. Data Pipeline Schedule

| Data Type | Source | Frequency | Trigger |
|-----------|--------|-----------|---------|
| **Stock Prices** | Yahoo/Alpha | Real-time (15s) | WebSocket + Fallback Cron |
| **OHLC Data** | All Sources | Every 1 min | Scheduled |
| **Daily OHLC** | All Sources | EOD (4:00 PM IST) | Market Close Event |
| **News Articles** | RSS/API | Every 5 min | Scheduled + New Article Event |
| **Sentiment** | NLP Engine | After News Fetch | Event-Driven |
| **Predictions** | ML Models | Every 15 min | Scheduled |
| **Model Retrain** | Training Pipeline | Weekly + Drift | Metric Threshold |

## 3. Feature Engineering

### Technical Indicators
```
- SMA (5, 10, 20, 50, 200)
- EMA (5, 10, 20, 50)
- RSI (14)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- ATR (14)
- Stochastic (14, 3)
- VWAP
- OBV
```

### Sentiment Features
```
- Title Sentiment Score
- Summary Sentiment Score
- Weighted Average Sentiment (Recency)
- Social Media Mentions (if available)
- News Volume
- Source Credibility Score
```

### Derived Features
```
- Returns (1m, 5m, 15m, 1h, 1d)
- Volatility (Rolling Std)
- Z-Score
- Range Position
- Momentum
- Cross-asset Correlation
```

## 4. ML Models

### Model 1: Price Direction Prediction (Classification)
- **Algorithm**: XGBoost + LSTM Ensemble
- **Target**: Next 15min direction (UP/DOWN/FLAT)
- **Features**: 50+ technical indicators + sentiment

### Model 2: Price Forecasting (Regression)
- **Algorithm**: Prophet + LSTM Hybrid
- **Target**: Next 1h, 4h, 1d price
- **Features**: Time-series + External signals

### Model 3: Sentiment Impact Prediction
- **Algorithm**: BERT + FinBERT Fine-tuned
- **Target**: Price change % based on news
- **Features**: News embeddings + Market context

## 5. Retraining Strategy

```
Trigger Conditions:
├── Weekly Scheduled (Sunday 2 AM)
├── Daily if Market Regime Changes
├── Accuracy Drop > 5%
├── Data Drift Detection (KS Test)
└── New Model Available in Registry

Retraining Pipeline:
1. Data Validation (Schema + Quality)
2. Feature Engineering
3. Train Models (Hyperparameter Tuning)
4. Cross-Validation
5. Model Comparison
6. Register if Better Than Production
7. A/B Testing (10% traffic)
8. Gradual Rollout
```

## 6. Monitoring & Alerting

```
Metrics to Monitor:
├── Prediction Accuracy (1h, 4h, 1d horizons)
├── Model Latency (p50, p95, p99)
├── Data Freshness
├── Feature Drift (Population Stability Index)
├── Prediction Distribution
└── Business Metrics (Engagement, Conversions)

Alert Thresholds:
├── Accuracy < 50% → Critical
├── Latency > 2s → Warning
├── Data Age > 5 min → Warning
└── Model Staleness > 7 days → Critical
```
