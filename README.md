# Market Data Platform

Real-time market data aggregation and distribution system for index-level data (NIFTY, BANKNIFTY, S&P 500, etc.).

## Features

- **Multi-Source Aggregation** — Failover across Upstox, NSE, and Yahoo Finance
- **Real-Time WebSocket Streams** — Live OHLC data with sub-5s latency
- **REST API** — Historical and latest OHLC data with multiple timeframes
- **ETL Pipeline** — Automated extract, transform, load with validation
- **Browser Visualization** — Lightweight charting interface

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git


### Access the Application

| Service | URL |
|---------|-----|
| API | http://localhost:8000/api/v1 |
| WebSocket | ws://localhost:8000/api/v1/ws/ohlc/{symbol} |
| Frontend | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

## API Usage

### Get Latest OHLC Data

```bash
curl http://localhost:8000/api/v1/ohlc/NIFTY/latest
```

### Get Historical Data

```bash
curl "http://localhost:8000/api/v1/ohlc/NIFTY?timeframe=5m&limit=100"
```

### WebSocket Connection

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/ohlc/NIFTY?timeframe=1m');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log(data);
};
```
