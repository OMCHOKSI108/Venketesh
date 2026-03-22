
# BACKEND.md

## Market Data Infrastructure Platform
### Real-time Index Data Aggregation & Distribution System

## 1. Project Overview & Core Objectives

### 1.1 Vision
Build a robust, scalable market data infrastructure layer that aggregates index-level data (NIFTY, BANKNIFTY, S&P 500, etc.) from multiple free-tier sources, normalizes it into a unified schema, and distributes it via REST APIs and WebSocket streams to frontend visualization clients.

### 1.2 Core Objectives
| Objective | Description | Success Metric |
|-----------|-------------|----------------|
| **Data Reliability** | 99.9% uptime with automatic failover across data sources | <0.1% data gaps |
| **Low Latency** | Sub-5 second end-to-end latency (development phase) | P95 < 5s |
| **Source Agnostic** | Unified interface regardless of underlying data provider | Seamless failover |
| **Scalability** | Handle 1000+ concurrent WebSocket connections | Horizontal scaling ready |
| **Data Integrity** | Validated OHLC data with duplicate prevention | Zero invalid candles |

### 1.3 Target Users
- Retail traders requiring index tracking
- Algorithmic trading strategy backtesting
- Financial visualization dashboards
- Future integration with signal generation engines

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Web App     │  │  Mobile App  │  │  Trading Bot │  │  Dashboard   │      │
│  │  (index.html)│  │  (Future)    │  │  (Future)    │  │  (Future)    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
└─────────┼─────────────────┼─────────────────┼─────────────────┼──────────────┘
          │                 │                 │                 │
          └─────────────────┴────────┬────────┴─────────────────┘
                                       │
                              ┌────────▼────────┐
                              │   API Gateway   │
                              │  (Nginx/Traefik)│
                              │  Rate Limiting  │
                              └────────┬────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────┐
│                           SERVICE LAYER                                    │
│  ┌───────────────────────────────────┼───────────────────────────────────┐ │
│  │                         FastAPI Backend                               │ │
│  │  ┌──────────────┐  ┌──────────────┼──────────────┐  ┌──────────────┐  │ │
│  │  │   REST API   │  │  WebSocket   │   Manager    │  │   Health     │  │ │
│  │  │   (HTTP)     │  │  (Real-time) │              │  │   Checks     │  │ │
│  │  └──────────────┘  └──────────────┘              │  └──────────────┘  │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐│ │
│  │  │                    Aggregation Service                             ││ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            ││ │
│  │  │  │   Source     │  │   Source     │  │   Source     │            ││ │
│  │  │  │   Priority   │  │   Priority   │  │   Priority   │            ││ │
│  │  │  │     1        │  │     2        │  │     3        │            ││ │
│  │  │  │  (Upstox)    │  │   (NSE)      │  │  (Yahoo)     │            ││ │
│  │  │  └──────────────┘  └──────────────┘  └──────────────┘            ││ │
│  │  └─────────────────────────────────────────────────────────────────────┘│ │
│  └───────────────────────────────────┬───────────────────────────────────┘ │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────┐
│                           DATA LAYER                                         │
│  ┌───────────────────────────────────┼───────────────────────────────────┐ │
│  │                         ETL Pipeline                                  │ │
│  │  ┌──────────────┐  ┌──────────────┼──────────────┐  ┌──────────────┐  │ │
│  │  │   Extract    │  │  Transform   │   Validate   │  │    Load      │  │ │
│  │  │   Adapters   │  │  Normalizer  │   Engine     │  │   Storage    │  │ │
│  │  └──────────────┘  └──────────────┘              │  └──────┬───────┘  │ │
│  └───────────────────────────────────┬──────────────┴─────────┼──────────┘ │
│                                      │                        │           │
│  ┌───────────────────────────────────┼────────────────────────┼─────────┐ │
│  │                         Storage Layer                                 │ │
│  │  ┌───────────────────────────────┘                        │         │ │
│  │  │                              ┌─────────────────────────┘         │ │
│  │  │                              │                                     │ │
│  │  ▼                              ▼                                     │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │ │
│  │  │      Redis       │  │   PostgreSQL     │  │   TimescaleDB    │      │ │
│  │  │   (Real-time)    │  │   (Historical)   │  │   (Time-series)  │      │ │
│  │  │   - Hot cache    │  │   - OHLC data    │  │   - Aggregations │      │ │
│  │  │   - Pub/Sub      │  │   - Metadata     │  │   - Analytics    │      │ │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘      │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component-Level Architecture

#### 2.2.1 Data Source Adapters
```
┌─────────────────────────────────────────────────────────┐
│                  ADAPTER FACTORY                        │
├─────────────────────────────────────────────────────────┤
│  Interface: DataSourceAdapter                          │
│  - fetch(symbol: str) -> RawData                       │
│  - health_check() -> bool                              │
│  - rate_limit_remaining() -> int                       │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Upstox     │  │     NSE      │  │    Yahoo     │
│   Adapter    │  │   Adapter    │  │   Adapter    │
├──────────────┤  ├──────────────┤  ├──────────────┤
│ Auth: OAuth2 │  │ Auth: None   │  │ Auth: None   │
│ Rate: 10/s   │  │ Rate: 1/s    │  │ Rate: 2/s    │
│ Latency: 50ms│  │ Latency: 200ms│ │ Latency: 500ms│
│ Priority: 1  │  │ Priority: 2  │  │ Priority: 3  │
└──────────────┘  └──────────────┘  └──────────────┘
```

#### 2.2.2 ETL Pipeline Flow
```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  EXTRACT │────▶│ TRANSFORM│────▶│ VALIDATE │────▶│   LOAD   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
      │               │                │               │
      ▼               ▼                ▼               ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Multiple │     │ Normalize│     │ Schema   │     │ Redis +  │
│ Sources  │     │ Schema   │     │ Business │     │ Postgre  │
│          │     │ Enrich   │     │ Rules    │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## 3. Technology Stack

### 3.1 Core Technologies

| Layer | Technology | Justification |
|-------|------------|---------------|
| **Language** | Python 3.11+ | Rich ecosystem for data processing, async support, type hints |
| **Web Framework** | FastAPI | Native async/await, automatic OpenAPI docs, WebSocket support, high performance |
| **Task Queue** | Celery + Redis | Distributed task processing, scheduled ETL jobs, retry logic |
| **Database** | PostgreSQL 15+ | ACID compliance, JSON support, robust ecosystem |
| **Time-Series** | TimescaleDB | PostgreSQL extension, optimized for time-series, continuous aggregates |
| **Cache** | Redis 7+ | Sub-millisecond latency, pub/sub for real-time, data structures |
| **Message Broker** | Redis Streams | Lightweight alternative to Kafka for current scale |
| **HTTP Client** | httpx | Async HTTP/2 support, connection pooling, timeout management |
| **Validation** | Pydantic v2 | Runtime validation, serialization, OpenAPI integration |
| **Testing** | pytest + pytest-asyncio | Comprehensive async testing support |
| **Monitoring** | Prometheus + Grafana | Metrics collection, visualization, alerting |

### 3.2 Infrastructure

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Containerization** | Docker + Docker Compose | Development consistency, easy deployment |
| **Orchestration** | Docker Swarm (initial) → Kubernetes | Gradual scaling path |
| **Reverse Proxy** | Traefik | Automatic SSL, load balancing, service discovery |
| **CI/CD** | GitHub Actions | Automated testing, building, deployment |
| **Logging** | ELK Stack (Elasticsearch, Logstash, Kibana) | Centralized logging, search, analysis |
| **Secrets** | HashiCorp Vault / AWS Secrets Manager | Secure credential management |

### 3.3 Alternative Considerations

| Decision | Chosen | Alternative | Reason |
|----------|--------|-------------|--------|
| **Message Queue** | Redis Streams | Apache Kafka | Simpler ops, sufficient for <10k msg/s |
| **Database** | TimescaleDB | InfluxDB | PostgreSQL compatibility, SQL familiarity |
| **Cache** | Redis | Memcached | Persistence option, data structures |
| **WebSocket** | Native FastAPI | Socket.io | Lower complexity, sufficient features |

---

## 4. Database Design

### 4.1 Schema Overview

```sql
-- Core OHLC Data Table (TimescaleDB hypertable)
CREATE TABLE ohlc_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    timeframe VARCHAR(10) NOT NULL, -- '1m', '5m', '1h', '1d'
    open DECIMAL(15, 4) NOT NULL,
    high DECIMAL(15, 4) NOT NULL,
    low DECIMAL(15, 4) NOT NULL,
    close DECIMAL(15, 4) NOT NULL,
    volume BIGINT,
    source VARCHAR(50) NOT NULL, -- 'upstox', 'nse', 'yahoo'
    is_closed BOOLEAN DEFAULT FALSE, -- Is this candle finalized?
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (symbol, timestamp, timeframe)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('ohlc_data', 'timestamp', chunk_time_interval => INTERVAL '1 day');

-- Indexes for common queries
CREATE INDEX idx_ohlc_symbol_time ON ohlc_data (symbol, timestamp DESC);
CREATE INDEX idx_ohlc_timeframe ON ohlc_data (timeframe, timestamp DESC);

-- Symbols/Instruments metadata
CREATE TABLE symbols (
    symbol VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(20) NOT NULL, -- 'NSE', 'BSE', 'NYSE'
    instrument_type VARCHAR(20) NOT NULL, -- 'INDEX', 'STOCK', 'ETF'
    currency VARCHAR(3) DEFAULT 'INR',
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data source health tracking
CREATE TABLE source_health (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL, -- 'healthy', 'degraded', 'down'
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    failure_count INT DEFAULT 0,
    latency_ms INT,
    metadata JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);

-- ETL job tracking
CREATE TABLE etl_jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'running', -- 'running', 'completed', 'failed'
    records_processed INT DEFAULT 0,
    error_message TEXT,
    metadata JSONB
);

-- API request logging (for rate limiting and analytics)
CREATE TABLE api_requests (
    id BIGSERIAL PRIMARY KEY,
    client_id VARCHAR(100),
    endpoint VARCHAR(255),
    method VARCHAR(10),
    status_code INT,
    response_time_ms INT,
    requested_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable
SELECT create_hypertable('api_requests', 'requested_at', chunk_time_interval => INTERVAL '7 days');
```

### 4.2 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     symbols     │       │    ohlc_data    │       │  source_health  │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ PK symbol       │◄──────┤ FK symbol       │       │ PK id           │
│    name         │       │ PK timestamp    │       │    source_name  │
│    exchange     │       │ PK timeframe    │       │    status       │
│    type         │       │    open         │       │    last_success │
│    is_active    │       │    high         │       │    last_failure │
│    metadata     │       │    low          │       │    latency_ms   │
└─────────────────┘       │    close        │       └─────────────────┘
                            │    volume       │                │
                            │    source       │                │
                            │    is_closed    │                │
                            └─────────────────┘                │
                                                                 │
                            ┌─────────────────┐                  │
                            │    etl_jobs     │◄─────────────────┘
                            ├─────────────────┤
                            │ PK id           │
                            │    job_type     │
                            │    symbol       │
                            │    status       │
                            │    records_proc │
                            │    error_msg    │
                            └─────────────────┘
```

### 4.3 Redis Data Structures

```
┌─────────────────────────────────────────────────────────────┐
│                      REDIS SCHEMA                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Real-time OHLC Cache                                   │
│  Key: ohlc:{symbol}:{timeframe}:current                    │
│  Type: Hash                                                │
│  Fields: open, high, low, close, volume, timestamp, source │
│  TTL: 60 seconds                                           │
│                                                             │
│  2. Latest Candle Timestamp                                │
│  Key: ohlc:{symbol}:{timeframe}:latest_ts                  │
│  Type: String                                              │
│  Value: ISO timestamp                                      │
│                                                             │
│  3. WebSocket Subscriptions                                │
│  Key: ws:subscriptions:{symbol}                            │
│  Type: Set                                                 │
│  Members: connection_ids                                   │
│                                                             │
│  4. Rate Limiting (per source)                             │
│  Key: ratelimit:{source_name}                              │
│  Type: Sliding Window (Redis Cell or custom)               │
│                                                             │
│  5. Source Health Cache                                    │
│  Key: health:{source_name}                                 │
│  Type: Hash                                                │
│  Fields: status, last_check, latency                       │
│  TTL: 30 seconds                                           │
│                                                             │
│  6. Pub/Sub Channels                                       │
│  Channel: ohlc:updates:{symbol}                            │
│  Message: JSON with OHLC data                              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. API Design

### 5.1 REST API Endpoints

#### Base URL: `/api/v1`

#### 5.1.1 OHLC Data

```yaml
GET /ohlc/{symbol}
Description: Get OHLC data for a symbol
Parameters:
  - symbol: string (path, required) - e.g., "NIFTY", "BANKNIFTY"
  - timeframe: string (query, default: "1m") - "1m", "5m", "15m", "1h", "1d"
  - from: string (query, optional) - ISO 8601 timestamp
  - to: string (query, optional) - ISO 8601 timestamp
  - limit: integer (query, default: 100, max: 1000) - Number of candles
  
Responses:
  200:
    content:
      application/json:
        schema:
          type: object
          properties:
            symbol: string
            timeframe: string
            data:
              type: array
              items:
                type: object
                properties:
                  timestamp: string (ISO 8601)
                  open: number
                  high: number
                  low: number
                  close: number
                  volume: integer
                  is_closed: boolean
            meta:
              type: object
              properties:
                count: integer
                source: string
                cached: boolean
```

```yaml
GET /ohlc/{symbol}/latest
Description: Get latest/current candle only
Parameters:
  - symbol: string (path, required)
  - timeframe: string (query, default: "1m")
  
Responses:
  200:
    content:
      application/json:
        schema:
          type: object
          properties:
            symbol: string
            timestamp: string
            open: number
            high: number
            low: number
            close: number
            volume: integer
            is_closed: boolean
            source: string
```

#### 5.1.2 Symbols Management

```yaml
GET /symbols
Description: List all available symbols
Parameters:
  - exchange: string (query, optional) - Filter by exchange
  - type: string (query, optional) - Filter by type
  - active_only: boolean (query, default: true)
  
Responses:
  200:
    content:
      application/json:
        schema:
          type: array
          items:
            type: object
            properties:
              symbol: string
              name: string
              exchange: string
              type: string
              is_active: boolean
```

```yaml
GET /symbols/{symbol}
Description: Get symbol details
Responses:
  200:
    content:
      application/json:
        schema:
          type: object
          properties:
            symbol: string
            name: string
            exchange: string
            type: string
            currency: string
            metadata: object
```

#### 5.1.3 Health & Status

```yaml
GET /health
Description: Service health check
Responses:
  200:
    content:
      application/json:
        schema:
          type: object
          properties:
            status: string (enum: ["healthy", "degraded", "unhealthy"])
            version: string
            uptime_seconds: integer
            components:
              type: object
              properties:
                database: string
                redis: string
                data_sources: array

GET /health/sources
Description: Data source health status
Responses:
  200:
    content:
      application/json:
        schema:
          type: array
          items:
            type: object
            properties:
              source: string
              status: string
              last_success: string (ISO 8601)
              last_failure: string (ISO 8601)
              latency_ms: integer
```

#### 5.1.4 WebSocket Endpoint

```yaml
WebSocket /ws/ohlc/{symbol}
Description: Real-time OHLC stream
Protocol: wss:// (secure) or ws:// (development)
Parameters:
  - symbol: string (path, required)
  - timeframe: string (query, default: "1m")
  
Message Flow:
  Client -> Server: {"action": "subscribe", "timeframe": "1m"}
  Server -> Client: {"type": "connected", "symbol": "NIFTY", "timeframe": "1m"}
  Server -> Client: {"type": "ohlc", "data": {...}, "timestamp": "..."}
  Server -> Client: {"type": "heartbeat", "timestamp": "..."}
  Client -> Server: {"action": "unsubscribe"}
  
Error Messages:
  {"type": "error", "code": "INVALID_SYMBOL", "message": "..."}
  {"type": "error", "code": "RATE_LIMITED", "message": "..."}
```

### 5.2 Request/Response Examples

#### Get Historical OHLC Data

**Request:**
```http
GET /api/v1/ohlc/NIFTY?timeframe=5m&from=2024-01-01T09:15:00Z&to=2024-01-01T15:30:00Z&limit=100
Authorization: Bearer <token>
```

**Response:**
```json
{
  "symbol": "NIFTY",
  "timeframe": "5m",
  "data": [
    {
      "timestamp": "2024-01-01T09:15:00Z",
      "open": 21750.15,
      "high": 21785.50,
      "low": 21745.20,
      "close": 21780.35,
      "volume": 1250000,
      "is_closed": true,
      "source": "nse"
    }
  ],
  "meta": {
    "count": 75,
    "source": "nse",
    "cached": false,
    "query_time_ms": 45
  }
}
```

#### WebSocket Connection

```javascript
// Client-side JavaScript
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/ohlc/NIFTY?timeframe=1m');

ws.onopen = () => {
  console.log('Connected to market data stream');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch(message.type) {
    case 'ohlc':
      updateChart(message.data);
      break;
    case 'heartbeat':
      console.log('Server heartbeat:', message.timestamp);
      break;
    case 'error':
      console.error('Stream error:', message.message);
      break;
  }
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Connection closed, attempting reconnect...');
  // Implement exponential backoff reconnect
};
```

### 5.3 Authentication & Security

#### Authentication Strategy (Phase 1: Development)
- **API Key**: Simple header-based authentication for development
- **Rate Limiting**: Per-IP and per-API-key limits

```http
Authorization: ApiKey <your_api_key>
X-Client-ID: <client_identifier>
```

#### Future: JWT Authentication
```http
Authorization: Bearer <jwt_token>
```

#### Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/ohlc/*` | 100 requests | 1 minute |
| `/symbols` | 1000 requests | 1 minute |
| WebSocket | 5 connections | Per IP |
| WebSocket | 50 subscriptions | Per connection |

---

## 6. Scalability & Performance

### 6.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API Response Time (p95) | < 100ms | From request to response |
| WebSocket Latency | < 1s | From data source to client |
| Database Query | < 50ms | Simple queries |
| ETL Processing | < 500ms | Per batch |
| Concurrent Connections | 1000+ | WebSocket clients |
| Throughput | 10,000+ | Requests/minute |

### 6.2 Caching Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                    CACHING LAYERS                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  L1: In-Memory (Application)                              │
│  - Latest candle per symbol                                 │
│  - Hot data (< 1 minute old)                                │
│  - TTL: 60 seconds                                          │
│                                                             │
│  L2: Redis                                                  │
│  - Recent OHLC data (last 24 hours)                         │
│  - Source health status                                     │
│  - Rate limiting counters                                   │
│  - TTL: 1 hour                                              │
│                                                             │
│  L3: PostgreSQL + TimescaleDB                               │
│  - Historical data                                          │
│  - Aggregated views (continuous aggregates)                 │
│  - Permanent storage                                        │
│                                                             │
│  Cache Invalidation:                                        │
│  - Time-based for real-time data                            │
│  - Event-based for historical corrections                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Database Optimization

#### TimescaleDB Continuous Aggregates
```sql
-- 5-minute aggregates from 1-minute data
CREATE MATERIALIZED VIEW ohlc_5m
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket('5 minutes', timestamp) as bucket,
    first(open, timestamp) as open,
    max(high) as high,
    min(low) as low,
    last(close, timestamp) as close,
    sum(volume) as volume
FROM ohlc_data
WHERE timeframe = '1m'
GROUP BY symbol, bucket;

-- Refresh policy
SELECT add_continuous_aggregate_policy('ohlc_5m',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes');
```

#### Partitioning Strategy
- **ohlc_data**: Partitioned by day (TimescaleDB chunks)
- **api_requests**: Partitioned by week (for analytics retention)

### 6.4 Horizontal Scaling Roadmap

```
Phase 1: Single Instance (Current)
┌─────────────────────────────────────┐
│  [FastAPI + Redis + PostgreSQL]    │
└─────────────────────────────────────┘

Phase 2: Separated Services
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   FastAPI    │  │    Redis     │  │  PostgreSQL  │
│   (x2)       │  │   (Cluster)  │  │  (Primary)   │
└──────────────┘  └──────────────┘  └──────────────┘

Phase 3: Microservices
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   API GW     │  │   ETL        │  │   WebSocket  │
│   (Traefik)  │  │   Workers    │  │   Service    │
└──────────────┘  └──────────────┘  └──────────────┘
       │                │                  │
       └────────────────┴──────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        ┌──────────────┐        ┌──────────────┐
        │    Redis     │        │  PostgreSQL  │
        │   Cluster    │        │   Cluster    │
        └──────────────┘        └──────────────┘
```

---

## 7. Security Best Practices

### 7.1 Data Source Security

```python
# Secure header rotation for NSE
class NSEAdapter:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
        # ... more
    ]
    
    def get_headers(self):
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }
    
    def fetch(self, symbol: str):
        # Implement exponential backoff
        # Rotate headers on 403 errors
        # Use proxy rotation if needed
```

### 7.2 API Security

| Threat | Mitigation |
|--------|------------|
| **DDoS** | Rate limiting, CloudFlare/WAF |
| **Injection** | Parameterized queries, Pydantic validation |
| **Data Exposure** | Field-level validation, response filtering |
| **Man-in-Middle** | TLS 1.3, certificate pinning |
| **Replay Attacks** | Request signing, timestamp validation |

### 7.3 Secrets Management

```python
# config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Database
    database_url: str
    redis_url: str
    
    # API Keys (for paid sources in future)
    upstox_api_key: str | None = None
    upstox_secret: str | None = None
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()
```

### 7.4 Data Validation

```python
from pydantic import BaseModel, validator, Field
from decimal import Decimal

class OHLCData(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    timestamp: datetime
    open: Decimal = Field(..., ge=0)
    high: Decimal = Field(..., ge=0)
    low: Decimal = Field(..., ge=0)
    close: Decimal = Field(..., ge=0)
    volume: int = Field(..., ge=0)
    
    @validator('high')
    def high_gte_low(cls, v, values):
        if 'low' in values and v < values['low']:
            raise ValueError('high must be >= low')
        return v
    
    @validator('low')
    def low_lte_high(cls, v, values):
        if 'high' in values and v > values['high']:
            raise ValueError('low must be <= high')
        return v
    
    @validator('open', 'close')
    def within_range(cls, v, values):
        if 'low' in values and 'high' in values:
            if not (values['low'] <= v <= values['high']):
                raise ValueError('open/close must be within low-high range')
        return v
```

---

## 8. Error Handling & Logging

### 8.1 Error Handling Strategy

```python
# exceptions.py
from enum import Enum
from typing import Optional, Dict, Any

class ErrorCode(Enum):
    # Data Source Errors (1xxx)
    SOURCE_UNAVAILABLE = "1001"
    SOURCE_RATE_LIMITED = "1002"
    SOURCE_INVALID_RESPONSE = "1003"
    
    # Validation Errors (2xxx)
    INVALID_SYMBOL = "2001"
    INVALID_TIMEFRAME = "2002"
    INVALID_DATE_RANGE = "2003"
    DATA_VALIDATION_FAILED = "2004"
    
    # System Errors (3xxx)
    DATABASE_ERROR = "3001"
    CACHE_ERROR = "3002"
    INTERNAL_ERROR = "3003"
    
    # API Errors (4xxx)
    NOT_FOUND = "4001"
    UNAUTHORIZED = "4002"
    RATE_LIMIT_EXCEEDED = "4003"

class MarketDataException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

# FastAPI exception handlers
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(MarketDataException)
async def market_data_exception_handler(request: Request, exc: MarketDataException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code.value,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.utcnow().isoformat(),
                "path": str(request.url)
            }
        }
    )
```

### 8.2 Structured Logging

```python
# logging_config.py
import structlog
import logging
from pythonjsonlogger import jsonlogger

def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Application logger
    logger = structlog.get_logger()
    return logger

# Usage in code
logger = structlog.get_logger()

# Data source fetch
logger.info(
    "fetching_market_data",
    symbol="NIFTY",
    source="nse",
    attempt=1,
    correlation_id="uuid-here"
)

# Validation failure
logger.warning(
    "data_validation_failed",
    symbol="NIFTY",
    source="nse",
    reason="high < low",
    raw_data={"high": 100, "low": 105},
    correlation_id="uuid-here"
)

# Error with context
logger.error(
    "source_unavailable",
    source="nse",
    error="Connection timeout",
    retry_in_seconds=5,
    correlation_id="uuid-here",
    exc_info=True
)
```

### 8.3 Log Levels & Retention

| Log Level | Use Case | Retention |
|-----------|----------|-----------|
| **DEBUG** | Detailed flow, variable inspection | 7 days |
| **INFO** | Business events, successful operations | 30 days |
| **WARNING** | Degraded performance, validation failures | 90 days |
| **ERROR** | Failed operations, exceptions | 1 year |
| **CRITICAL** | System failures, data corruption | Permanent |

### 8.4 Monitoring & Alerting

```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, Info

# Metrics
REQUEST_COUNT = Counter(
    'market_data_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'market_data_request_duration_seconds',
    'Request latency',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'market_data_websocket_connections',
    'Active WebSocket connections'
)

DATA_SOURCE_HEALTH = Gauge(
    'market_data_source_health',
    'Data source health status',
    ['source']
)

ETL_PROCESSED = Counter(
    'market_data_etl_processed_total',
    'ETL records processed',
    ['source', 'status']
)

# Usage
@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response
```

---

## 9. Deployment & Infrastructure

### 9.1 Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y libpq5 curl && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY ./app ./app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 9.2 Docker Compose (Development)

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/marketdata
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=info
    depends_on:
      - db
      - redis
    volumes:
      - ./app:/app/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  db:
    image: timescale/timescaledb:latest-pg15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=marketdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  celery_worker:
    build: .
    command: celery -A app.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/marketdata
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery_beat:
    build: .
    command: celery -A app.tasks beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/marketdata
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana

volumes:
  postgres_data:
  redis_data:
  grafana_data:
```

### 9.3 Production Deployment (AWS Example)

```
┌─────────────────────────────────────────────────────────────┐
│                         VPC                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   Public Subnet                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │  │
│  │  │   ALB        │  │   NAT GW     │  │  Bastion   │  │  │
│  │  │  (HTTPS)     │  │              │  │   Host     │  │  │
│  │  └──────┬───────┘  └──────────────┘  └────────────┘  │  │
│  │         │                                            │  │
│  └─────────┼──────────────────────────────────────────────┘  │
│            │                                                │
│  ┌─────────▼──────────────────────────────────────────────┐  │
│  │                  Private Subnet                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │              ECS Cluster / EKS                  │  │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │  │  │
│  │  │  │  FastAPI     │  │  FastAPI     │           │  │  │
│  │  │  │  Service     │  │  Service     │           │  │  │
│  │  │  └──────────────┘  └──────────────┘           │  │  │
│  │  │  ┌──────────────┐  ┌──────────────┐           │  │  │
│  │  │  │  Celery      │  │  Celery      │           │  │  │
│  │  │  │  Workers     │  │  Beat        │           │  │  │
│  │  │  └──────────────┘  └──────────────┘           │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  │  ┌──────────────┐  ┌──────────────────────────────┐  │  │
│  │  │   ElastiCache │  │         RDS                  │  │  │
│  │  │   (Redis)     │  │  (PostgreSQL + TimescaleDB)  │  │  │
│  │  └──────────────┘  └──────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 9.4 CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov
      
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t market-data:${{ github.sha }} .
      
      - name: Push to ECR
        run: |
          aws ecr get-login-password | docker login --username AWS --password-stdin ${{ secrets.ECR_REGISTRY }}
          docker push ${{ secrets.ECR_REGISTRY }}/market-data:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to ECS
        run: |
          aws ecs update-service --cluster market-data --service api --force-new-deployment
```

---

## 10. Folder/Project Structure

```
market-data-platform/
├── README.md
├── BACKEND.md
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── requirements.txt
├── pyproject.toml
├── pytest.ini
├── Makefile
│
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── config.py                  # Configuration management
│   ├── dependencies.py            # FastAPI dependencies
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── router.py          # API version aggregator
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── ohlc.py        # OHLC REST endpoints
│   │   │   │   ├── symbols.py     # Symbol management
│   │   │   │   └── health.py      # Health checks
│   │   │   └── websockets/
│   │   │       ├── __init__.py
│   │   │       └── ohlc.py        # WebSocket handlers
│   │   └── deps.py                # API dependencies
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constants.py           # System constants
│   │   ├── exceptions.py          # Custom exceptions
│   │   ├── logging_config.py      # Logging setup
│   │   ├── metrics.py             # Prometheus metrics
│   │   └── security.py            # Auth/security utilities
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py                # SQLAlchemy base
│   │   ├── ohlc.py                # OHLC data models
│   │   ├── symbol.py              # Symbol models
│   │   └── enums.py               # Enumerations
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── ohlc.py                # Pydantic schemas
│   │   ├── symbol.py
│   │   └── common.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── aggregator.py          # Core aggregation logic
│   │   ├── cache.py               # Redis cache service
│   │   ├── database.py            # DB session management
│   │   └── validator.py           # Data validation service
│   │
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── base.py                # Base adapter interface
│   │   ├── nse.py                 # NSE adapter
│   │   ├── yahoo.py               # Yahoo Finance adapter
│   │   ├── upstox.py              # Upstox adapter
│   │   └── factory.py             # Adapter factory
│   │
│   ├── etl/
│   │   ├── __init__.py
│   │   ├── extract.py             # Extraction logic
│   │   ├── transform.py           # Transformation logic
│   │   ├── load.py                # Loading logic
│   │   ├── pipeline.py            # Pipeline orchestrator
│   │   └── scheduler.py           # Job scheduling
│   │
│   └── tasks/
│       ├── __init__.py
│       └── celery_app.py          # Celery configuration
│
├── frontend/
│   ├── index.html                 # Main visualization
│   ├── css/
│   │   └── styles.css
│   └── js/
│       ├── chart.js               # Chart configuration
│       └── websocket.js           # WebSocket client
│
├── migrations/
│   ├── versions/
│   └── env.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_adapters.py
│   │   ├── test_aggregator.py
│   │   └── test_validation.py
│   ├── integration/
│   │   ├── test_api.py
│   │   └── test_websocket.py
│   └── fixtures/
│       └── sample_data.json
│
├── infrastructure/
│   ├── terraform/                 # IaC (future)
│   ├── kubernetes/                # K8s manifests (future)
│   ├── prometheus/
│   │   └── prometheus.yml
│   └── grafana/
│       └── dashboards/
│
└── docs/
    ├── architecture/
    ├── api/
    └── deployment/
```

---

## 11. Future Improvements & Extensibility

### 11.1 Phase 2: Enhanced Features

| Feature | Description | Priority |
|---------|-------------|----------|
| **Multi-timeframe Aggregation** | Auto-generate 5m, 15m, 1h, 1d from 1m | High |
| **Historical Backfill** | Fill gaps in historical data | High |
| **Technical Indicators** | RSI, MACD, Moving Averages API | Medium |
| **Alert System** | Price threshold alerts via WebSocket | Medium |
| **Data Export** | CSV/JSON export endpoint | Low |

### 11.2 Phase 3: Advanced Capabilities

```
┌─────────────────────────────────────────────────────────────┐
│                   FUTURE ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Backtesting │  │   Signal     │  │  Execution   │      │
│  │    Engine    │  │   Engine     │  │   Engine     │      │
│  │              │  │              │  │              │      │
│  │ - Strategy   │  │ - Pattern    │  │ - Paper      │      │
│  │   testing    │  │   detection  │  │   trading    │      │
│  │ - Performance│  │ - ML models  │  │ - Broker     │      │
│  │   metrics    │  │ - Alerts     │  │   integration│      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         └─────────────────┴─────────────────┘               │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │  Market Data    │                        │
│                  │  Platform       │                        │
│                  │  (Current)        │                        │
│                  └─────────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 11.3 Technology Evolution Roadmap

| Current | Future | Trigger |
|---------|--------|---------|
| Redis Streams | Apache Kafka | >10k messages/sec |
| TimescaleDB | ClickHouse | >100M rows/day analytics |
| Celery | Apache Airflow | Complex DAG dependencies |
| REST/WebSocket | gRPC | Internal service communication |
| Docker Swarm | Kubernetes | Multi-region deployment |

### 11.4 Machine Learning Integration

```python
# Future: Anomaly detection
class AnomalyDetector:
    def detect_price_anomaly(self, ohlc_data: OHLCData) -> bool:
        # Z-score based detection
        # Isolation Forest for outliers
        pass

# Future: Pattern recognition
class PatternRecognizer:
    def detect_candlestick_patterns(self, candles: List[OHLCData]):
        # Hammer, Doji, Engulfing, etc.
        pass
    
    def detect_support_resistance(self, candles: List[OHLCData]):
        # Automated level detection
        pass
```

### 11.5 Compliance & Data Governance

- **GDPR Compliance**: Data retention policies, right to deletion
- **Audit Logging**: Immutable audit trail for data changes
- **Data Lineage**: Track data from source to consumer
- **SLA Monitoring**: 99.9% uptime commitment tracking

---

## 12. Development Phases

### Phase 1: MVP (Weeks 1-2)
- [ ] FastAPI setup with single NSE adapter
- [ ] Basic OHLC endpoint
- [ ] Simple HTML frontend with Chart.js
- [ ] In-memory caching

### Phase 2: Core Infrastructure (Weeks 3-4)
- [ ] PostgreSQL + TimescaleDB integration
- [ ] Redis caching layer
- [ ] Multi-source aggregation with failover
- [ ] WebSocket implementation
- [ ] Docker containerization

### Phase 3: Production Readiness (Weeks 5-6)
- [ ] ETL pipeline with Celery
- [ ] Comprehensive error handling
- [ ] Monitoring & alerting (Prometheus/Grafana)
- [ ] Security hardening
- [ ] Load testing

### Phase 4: Scale & Optimize (Weeks 7-8)
- [ ] Horizontal scaling setup
- [ ] Advanced caching strategies
- [ ] Performance optimization
- [ ] Documentation & testing

---

## Appendix A: API Endpoint Summary

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/v1/ohlc/{symbol}` | Get OHLC data | API Key |
| GET | `/api/v1/ohlc/{symbol}/latest` | Get latest candle | API Key |
| GET | `/api/v1/symbols` | List symbols | None |
| GET | `/api/v1/symbols/{symbol}` | Symbol details | None |
| GET | `/api/v1/health` | Health check | None |
| GET | `/api/v1/health/sources` | Source health | None |
| WS | `/api/v1/ws/ohlc/{symbol}` | Real-time stream | API Key |

---

## Appendix B: Environment Variables

```bash
# Application
APP_NAME=market-data-platform
DEBUG=false
LOG_LEVEL=info
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/marketdata
DATABASE_POOL_SIZE=20

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=50

# Security
SECRET_KEY=your-secret-key-here
API_KEY_HEADER=X-API-Key

# Data Sources
NSE_ENABLED=true
YAHOO_ENABLED=true
UPSTOX_ENABLED=false
UPSTOX_API_KEY=
UPSTOX_SECRET=

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# WebSocket
WS_HEARTBEAT_INTERVAL=30
WS_MAX_CONNECTIONS_PER_IP=5
```

---

**Document Version:** 1.0  
**Last Updated:** 2024  
**Author:** Senior Backend Architect  
**Status:** Production-Ready Design Specification

---

This document provides a comprehensive blueprint for building a production-grade market data infrastructure. It balances immediate development needs with long-term scalability, ensuring the system can evolve from a simple data aggregator to a sophisticated trading infrastructure platform.