# Market Data Platform

Pseudo-live Indian index OHLC platform with FastAPI backend, Redis cache,
TimescaleDB persistence target, and lightweight chart frontend.

## Features

- Multi-source aggregation with NSE and Yahoo Finance
- Real-time WebSocket streaming
- Historical data storage (PostgreSQL/TimescaleDB)
- Data validation (OHLC business rules)
- Structured logging
- Resilient polling with auto-restart

## Services

- Backend API: `http://localhost:8000/api/v1`
- API docs: `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/api/v1/ws/ohlc/NIFTY?timeframe=1m`
- Frontend: Open `frontend/index.html` in browser
- Redis: `localhost:6379` (optional)
- PostgreSQL (TimescaleDB): `localhost:5432` (optional)

## Quick Start

### Python Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements-fastapi.txt

# Run server
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

```bash
docker compose up --build -d
```

Check logs:

```bash
docker compose logs -f backend
```

Stop all services:

```bash
docker compose down
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Service health check |
| `/api/v1/health/sources` | GET | Data source health status |
| `/api/v1/ohlc/{symbol}` | GET | Get OHLC candles |
| `/api/v1/ohlc/{symbol}/latest` | GET | Get latest candle |
| `/api/v1/ws/ohlc/{symbol}` | WS | WebSocket for real-time data |

## API Examples

Latest candle:

```bash
curl http://localhost:8000/api/v1/ohlc/NIFTY/latest
```

Historical candles:

```bash
curl "http://localhost:8000/api/v1/ohlc/NIFTY?timeframe=1m&limit=100"
```

With time filters:

```bash
curl "http://localhost:8000/api/v1/ohlc/NIFTY?from=2026-01-01T00:00:00Z&to=2026-01-02T00:00:00Z"
```

## Configuration

Environment variables (see `.env.example`):

- `REDIS_URL`: Redis connection URL (default: redis://localhost:6379/0)
- `DATABASE_URL`: PostgreSQL connection URL
- `POLL_INTERVAL`: Polling interval seconds (default: 2)
- `LOG_LEVEL`: Logging level (default: INFO)
- `NSE_BASE_URL`: NSE endpoint (default: https://www.nseindia.com)

## Architecture

```
Client → FastAPI → Aggregator → Adapters (NSE/Yahoo)
                              ↓
                        ETL Pipeline
                              ↓
                    Storage (Redis/PostgreSQL)
```

## Data Sources

| Source | Priority | Description |
|--------|----------|-------------|
| Yahoo Finance | 3 | Primary working source |
| NSE India | 2 | May require proxy |

## Notes

- Runtime settings are environment-driven via `backend/core/config.py`.
- Redis key pattern: `ohlc:{symbol}:{timeframe}:current`.
- Poller runs in app startup and publishes updates to `ohlc:updates:{symbol}`.
