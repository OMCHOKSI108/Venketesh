# Market Data Platform

Real-time Index Data Aggregation & Distribution System

## Quick Start

### One-Command Setup (Docker)

```bash
docker-compose up --build
```

Then open: **http://localhost:8000**

## Commands

### Development Mode
```bash
# Install dependencies
pip install -r requirements.txt

# Run with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Mode
```bash
# Build and start
docker-compose up --build

# Stop services
docker-compose down

# Rebuild after changes
docker-compose up --build --force-recreate

# View logs
docker-compose logs -f app
```

## Features

- Real-time market data (NIFTY, BANKNIFTY, SENSEX)
- Interactive price chart with Chart.js
- WebSocket streaming
- REST API for historical data
- Redis caching
- PostgreSQL storage

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Frontend Dashboard |
| GET | `/api/v1/ohlc/{symbol}` | Get OHLC data |
| GET | `/api/v1/ohlc/{symbol}/latest` | Latest candle |
| GET | `/api/v1/symbols` | List symbols |
| GET | `/api/v1/health` | Health check |
| WS | `/ws/ohlc/{symbol}` | Real-time stream |

## Example API Calls

```bash
# Get latest NIFTY data
curl http://localhost:8000/api/v1/ohlc/NIFTY/latest

# Get historical data
curl "http://localhost:8000/api/v1/ohlc/NIFTY?timeframe=5m&limit=100"

# Check health
curl http://localhost:8000/api/v1/health
```

## Project Structure

```
├── app/
│   ├── main.py          # FastAPI app
│   ├── api/             # REST endpoints
│   ├── adapters/        # Data source adapters
│   ├── services/        # Business logic
│   ├── models/          # Database models
│   └── etl/             # ETL pipeline
├── frontend/
│   └── index.html       # Dashboard UI
├── migrations/
│   └── init.sql         # Database schema
├── docker-compose.yml   # Container setup
└── Dockerfile           # App image
```

## License

MIT
