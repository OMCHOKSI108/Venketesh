# PHASE_PLAN.md
# Phase-wise Development Plan
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026 | **Status:** Active Development

---

## Overview

This plan breaks the project into four sequential development phases, mirroring the timeline defined in `SRS.md` (§9) and the backend architecture described in `BACKEND.md` (§12). Each phase builds upon the previous and delivers an independently testable, runnable increment.

```
Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4
[Skeleton]  [Live Core]  [ETL + DB]  [Polish + Robust]
 1–2 days    2–3 days     2–4 days     2–3 days
```

---

## Phase 1 — Minimal Viable Chart (NSE + REST + Static Chart)

### Goal
Deliver the most basic working slice of the system: a FastAPI server with a single NSE adapter exposing a REST endpoint, and a static `index.html` rendering a candlestick chart from the API response. Prove end-to-end connectivity before adding complexity.

### Scope
- Project scaffolding (folder structure, virtual environment, dependencies)
- NSE adapter (the highest-risk, most fragile component — validate first)
- FastAPI application with a single `GET /api/v1/ohlc/{symbol}` endpoint
- In-memory OHLC cache (Python dict, no Redis yet)
- `index.html` with TradingView Lightweight Charts, populated via a single REST fetch on load
- Structured logging (console, basic format)
- `.env` file and configuration loader

### Deliverables

| # | Deliverable | Acceptance Criteria |
|---|-------------|---------------------|
| D1.1 | Project skeleton with `requirements.txt` and folder structure matching `BACKEND.md §10` | `uvicorn main:app` starts without errors |
| D1.2 | `NSEAdapter` class implementing `DataSourceAdapter` interface | Returns valid OHLC dict for `NIFTY`; logs failure gracefully |
| D1.3 | `GET /api/v1/ohlc/{symbol}` endpoint | Returns last 100 1m candles as JSON array |
| D1.4 | `index.html` with Lightweight Charts | Chart renders ≥ 50 candles on load |
| D1.5 | `GET /api/v1/health` endpoint | Returns `{"status": "ok"}` with 200 |
| D1.6 | Basic logging config | Source name, success/fail, timestamp printed per poll |

### Dependencies
- Python 3.11+, `fastapi`, `uvicorn`, `requests`, `pydantic v2`
- Local internet access (NSE endpoint reachable)
- No Redis, no PostgreSQL, no WebSocket

### Milestones & Checkpoints

| Checkpoint | Signal |
|------------|--------|
| ✅ CP1-A | `NSEAdapter.fetch("NIFTY")` returns a non-empty list in isolation |
| ✅ CP1-B | FastAPI starts and `/api/v1/health` returns 200 |
| ✅ CP1-C | `/api/v1/ohlc/NIFTY` returns valid OHLC JSON |
| ✅ CP1-D | `index.html` loaded in browser shows a candlestick chart |

### Risks in This Phase
- NSE endpoint format may differ from expectations — have YahooAdapter ready as fallback validator
- CORS must be enabled on FastAPI for local `file://` access to the API

---

## Phase 2 — WebSocket + Redis + Multi-Source Failover (Pseudo-Live Core)

### Goal
Transform the static chart into a pseudo-live dashboard. Add WebSocket push, Redis hot cache, Yahoo Finance as a fallback adapter, and the Aggregator Service that selects the best available source automatically.

### Scope
- `YahooAdapter` (using `yfinance`) as fallback
- `AggregatorService` with source priority chain: NSE → Yahoo (Upstox deferred to Phase 4)
- Redis integration for real-time OHLC cache (key: `ohlc:{symbol}:{timeframe}:current`)
- FastAPI WebSocket endpoint: `GET /api/v1/ws/ohlc/{symbol}`
- Polling loop (background `asyncio` task) running every 1–3 seconds during market hours
- Frontend `WebSocketManager` component with exponential backoff reconnection
- `StatusIndicator` component — shows active source and WS connection state
- Heartbeat messages from the server every 30 seconds

### Deliverables

| # | Deliverable | Acceptance Criteria |
|---|-------------|---------------------|
| D2.1 | `YahooAdapter` class | Returns OHLC for `NIFTY` via yfinance; degrades gracefully on failure |
| D2.2 | `AggregatorService` with priority failover | When NSEAdapter raises, YahooAdapter is tried; no crash; failure is logged |
| D2.3 | Redis integration (L2 cache) | `ohlc:NIFTY:1m:current` key updated each poll cycle |
| D2.4 | Background polling loop | Runs every ~2 s; does not block API responses |
| D2.5 | WebSocket endpoint `/api/v1/ws/ohlc/{symbol}` | Pushes latest OHLC JSON to connected clients every ~1–2 s |
| D2.6 | Frontend WS client | Chart's rightmost candle updates without page reload |
| D2.7 | Source indicator in UI | Displays "NSE" or "Yahoo" and WS status (online/reconnecting) |

### Dependencies
- Phase 1 complete
- Redis 7+ running locally (`redis-server`)
- `redis-py`, `yfinance` added to dependencies
- Frontend `WebSocketManager` and `StatusIndicator` components (from `DESIGN.md §5`)

### Milestones & Checkpoints

| Checkpoint | Signal |
|------------|--------|
| ✅ CP2-A | Redis `PING` responds; `redis-py` client connects |
| ✅ CP2-B | `AggregatorService` returns Yahoo data when NSE is disabled |
| ✅ CP2-C | WebSocket client (`wscat` or browser) receives candle JSON every ~2 s |
| ✅ CP2-D | Browser chart updates current candle live without refresh |
| ✅ CP2-E | Source indicator switches from "NSE" to "Yahoo" when NSE is mocked to fail |

### Risks in This Phase
- `asyncio` polling loop and WebSocket manager must not block each other — use `asyncio.create_task`
- `yfinance` may return stale data during off-hours; handle gracefully
- Redis connection failure must not crash the API (fallback to in-memory store)

---

## Phase 3 — ETL Pipeline + PostgreSQL Historical Storage

### Goal
Introduce persistent storage so that historical candles survive restarts and the chart populates with real history on load. Build the full ETL pipeline (Extract → Transform → Validate → Load) and implement deduplication logic.

### Scope
- PostgreSQL schema: `ohlc_data`, `symbols`, `source_health`, `etl_jobs` (from `BACKEND.md §4.1`)
- TimescaleDB hypertable for `ohlc_data`
- `DataValidator` with business rules (high ≥ low, open ≤ high, timestamp sanity)
- `ETLPipeline` class orchestrating fetch → validate → transform → upsert
- Deduplication: `ON CONFLICT (symbol, timestamp, timeframe) DO UPDATE`
- `is_closed` flag set correctly (current candle = False, closed candle = True)
- REST endpoint updated to serve historical data from PostgreSQL (last 200–500 candles)
- `source_health` table updated per ETL cycle
- Environment variable configuration (`.env` with `DATABASE_URL`, `REDIS_URL`, etc.)

### Deliverables

| # | Deliverable | Acceptance Criteria |
|---|-------------|---------------------|
| D3.1 | PostgreSQL + TimescaleDB schema applied | Migration script runs without error; all 4 tables created |
| D3.2 | `DataValidator` with all business rules | Rejects candles where high < low; logs reason |
| D3.3 | ETL pipeline class | Full cycle completes: fetch → validate → write to Redis + PostgreSQL |
| D3.4 | Deduplication on upsert | Re-running the same candle twice yields exactly one DB row |
| D3.5 | `is_closed` flag logic | Candles with `floor(timestamp) < current_minute` marked `is_closed=True` |
| D3.6 | Historical REST endpoint returning from DB | `/api/v1/ohlc/NIFTY?limit=300` returns 300 DB rows |
| D3.7 | Chart loads 200+ historical candles on `index.html` open | Chart visually shows > 200 bars on fresh load |

### Dependencies
- Phase 2 complete
- PostgreSQL 15+ with TimescaleDB extension running locally
- `psycopg2-binary` or `asyncpg`, `sqlalchemy` added to dependencies
- `alembic` for schema migrations (optional but recommended)

### Milestones & Checkpoints

| Checkpoint | Signal |
|------------|--------|
| ✅ CP3-A | `psql` can connect; TimescaleDB extension loaded |
| ✅ CP3-B | Migration script creates all tables and hypertable without error |
| ✅ CP3-C | `DataValidator` raises on invalid OHLC sample (unit test passes) |
| ✅ CP3-D | After 5 minutes of running, `SELECT COUNT(*) FROM ohlc_data` shows > 5 rows |
| ✅ CP3-E | Inserting the same candle twice results in 1 row (not 2) |
| ✅ CP3-F | `index.html` on fresh load shows historical bars (not just today's data) |

### Risks in This Phase
- TimescaleDB installation may need Docker — document setup steps
- ETL loop must handle DB connection pool exhaustion; use connection pooling config
- Floor-timestamp logic must be timezone-aware (use IST / `Asia/Kolkata`)

---

## Phase 4 — Validation, Logging, Observability, and Robustness

### Goal
Harden the system to production-grade reliability for the dev phase. Add structured logging, comprehensive exception handling, source health tracking, partial candle handling correctness, and frontend polish (responsive layout, accessibility, InfoPanel).

### Scope
- Structured JSON logging (source tried, latency, success/fail, timestamp) to console + optional file
- Per-source exponential backoff and ban detection (403/429 response codes)
- `source_health` table writes and health API endpoint (`GET /api/v1/health/sources`)
- Polling loop restart policy (auto-recover if loop crashes)
- Frontend: InfoPanel (last price, volume, high, low), responsive layout, ARIA labels
- Light/dark theme toggle (via `data-theme` attribute, Tailwind dark mode)
- Rate limiting on API endpoints (per-IP, configurable via `.env`)
- `GET /api/v1/symbols` endpoint returning registered symbols
- End-to-end smoke test script (Python or shell)
- `README.md` with setup instructions and architecture summary

### Deliverables

| # | Deliverable | Acceptance Criteria |
|---|-------------|---------------------|
| D4.1 | Structured logging (JSON format) | Each ETL cycle emits log with `source`, `latency_ms`, `status`, `symbol` |
| D4.2 | Exponential backoff per adapter | On 403/429, adapter waits 2^n seconds before retrying; logged |
| D4.3 | Source health tracking | `source_health` table updates after each fetch attempt |
| D4.4 | `GET /api/v1/health/sources` | Returns JSON with status per source |
| D4.5 | Polling loop auto-restart | If loop raises unhandled exception, it restarts within 5 s |
| D4.6 | InfoPanel in frontend | Shows last price, volume, daily high/low from latest candle |
| D4.7 | Responsive layout | UI renders correctly on 768px–1920px viewport widths |
| D4.8 | Rate limiting on REST endpoints | >100 req/min from same IP returns 429 |
| D4.9 | End-to-end smoke test | Script asserts chart data visible, WS delivers update, DB row count increases |
| D4.10 | `README.md` | New developer can set up and run the system in < 30 min |

### Dependencies
- Phase 3 complete
- Tailwind CSS available (CDN or local build via Vite, per `DESIGN.md §7`)
- No new backend services required for this phase

### Milestones & Checkpoints

| Checkpoint | Signal |
|------------|--------|
| ✅ CP4-A | Log output includes `source`, `latency_ms` fields in JSON |
| ✅ CP4-B | Mocking a 403 from NSE triggers backoff and fallback within one cycle |
| ✅ CP4-C | `/api/v1/health/sources` returns `{"nse": "healthy", "yahoo": "healthy"}` |
| ✅ CP4-D | Killing and restarting the polling coroutine is automatic (supervisor or try/except loop) |
| ✅ CP4-E | Frontend passes basic WCAG contrast check on both light and dark themes |
| ✅ CP4-F | Smoke test script exits with code 0 |

---

## Cross-Phase Dependency Map

```
[Phase 1: Skeleton]
  └─ NSEAdapter, FastAPI, in-memory cache, index.html chart
        │
        ▼
[Phase 2: Live Core]
  └─ YahooAdapter, AggregatorService, Redis, WebSocket, polling loop
        │
        ▼
[Phase 3: Persistence]
  └─ PostgreSQL/TimescaleDB, ETL pipeline, DataValidator, historical REST
        │
        ▼
[Phase 4: Robustness]
  └─ Structured logs, backoff, health tracking, InfoPanel, rate limiting
```

---

## Out of Scope (All Phases — Dev Phase MVP)

Per `SRS.md §10`, the following are explicitly deferred:
- Upstox OAuth2 login and real-time adapter
- Multi-timeframe aggregation (5m, 15m, 1d)
- Option chain, OI, Greeks data
- Symbol selector dropdown in UI (multiple symbols)
- Mobile responsive design beyond basic tablet support
- Docker containerization and cloud deployment
- User authentication / API key enforcement
- Monitoring stack (Prometheus, Grafana, ELK)

---

*Document Owner: Project Lead | Last Updated: March 2026*