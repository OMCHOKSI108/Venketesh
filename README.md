# Market Data Platform

Pseudo-live Indian index OHLC platform with FastAPI backend, Redis cache,
TimescaleDB persistence target, and lightweight chart frontend.

## Services

- Backend API: `http://localhost:8000/api/v1`
- API docs: `http://localhost:8000/docs`
- WebSocket: `ws://localhost:8000/api/v1/ws/ohlc/NIFTY?timeframe=1m`
- Frontend: `http://localhost:3000`
- Redis: `localhost:6379`
- PostgreSQL (TimescaleDB): `localhost:5432`

## Docker Quick Start

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

## API Examples

Latest candle:

```bash
curl http://localhost:8000/api/v1/ohlc/NIFTY/latest
```

Historical candles:

```bash
curl "http://localhost:8000/api/v1/ohlc/NIFTY?timeframe=1m&limit=100"
```

## Notes

- Runtime settings are environment-driven via `backend/core/config.py`.
- Redis key pattern: `ohlc:{symbol}:{timeframe}:current`.
- Poller runs in app startup and publishes updates on:
  `ohlc:updates:{symbol}`.
