# CHECKLIST.md
# Coding Agent Task Checklist
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026

---

## How to Use This Checklist

- Each task is atomic and independently verifiable.
- Tasks are ordered; dependencies are noted where non-obvious.
- Mark tasks `[x]` as complete; mark `[~]` if partially done / blocked.
- Validation steps (🧪) must pass before moving to the next task.
- Priority: 🔴 Critical Path | 🟡 Required | 🟢 Enhancement

---

## Phase 1 — Project Skeleton & NSE Adapter

### 1.1 Environment & Project Setup

- [x] 🔴 Create project root directory with the following structure:
  ```
  market-data-platform/
  ├── backend/
  │   ├── adapters/
  │   ├── api/
  │   ├── core/
  │   ├── db/
  │   ├── services/
  │   └── main.py
  ├── frontend/
  │   ├── index.html
  │   └── src/
  ├── tests/
  ├── .env.example
  ├── requirements.txt
  └── README.md
  ```
- [x] 🔴 Create `requirements.txt` with pinned versions:
  - `fastapi>=0.110.0`
  - `uvicorn[standard]>=0.29.0`
  - `pydantic>=2.0.0`
  - `requests>=2.31.0`
  - `python-dotenv>=1.0.0`
  - `redis>=5.0.0`
  - `yfinance>=0.2.37`
  - `psycopg2-binary>=2.9.9`
  - `sqlalchemy>=2.0.0`
  - `pytest>=8.0.0`
  - `pytest-asyncio>=0.23.0`
  - `httpx>=0.27.0`
- [x] 🔴 Create and activate a Python 3.11+ virtual environment
- [x] 🔴 Create `.env.example` with all required variables (see `BACKEND.md Appendix B`)
- [x] 🔴 Create `backend/core/config.py` — loads env vars using `pydantic-settings` or `python-dotenv`

  🧪 **Validation:** `python -c "from backend.core.config import settings; print(settings)"` prints config without error.

### 1.2 FastAPI Application Bootstrap

- [x] 🔴 Create `backend/main.py` with:
  - `FastAPI` app instance
  - CORS middleware enabled for all origins (dev phase)
  - Router inclusion for `api/v1` prefix
  - Startup and shutdown event handlers (stubs)
- [x] 🔴 Create `backend/api/v1/health.py` — `GET /api/v1/health` returns `{"status": "ok", "timestamp": "<ISO>"}`
- [x] 🔴 Register health router in `main.py`

  🧪 **Validation:** `uvicorn backend.main:app --reload` starts; `curl localhost:8000/api/v1/health` returns 200 with JSON body.

### 1.3 Data Models (Pydantic)

- [x] 🔴 Create `backend/core/models.py` with:
  - `OHLCData` — fields: `symbol`, `timestamp` (datetime), `open`, `high`, `low`, `close`, `volume` (optional), `is_closed` (bool), `source` (str)
  - `RawData` — loosely typed dict for raw adapter output before normalization
  - Validators: `high >= low`, `open <= high`, `close >= low`

  🧪 **Validation:** Instantiate `OHLCData` with invalid data (e.g., `high=100, low=200`) — Pydantic raises `ValidationError`.

### 1.4 DataSourceAdapter Interface

- [x] 🔴 Create `backend/adapters/base.py`:
  - Abstract base class `DataSourceAdapter`
  - Abstract methods: `fetch(symbol: str) -> list[RawData]`, `health_check() -> bool`, `get_priority() -> int`
  - Property: `name: str`

### 1.5 NSE Adapter

- [x] 🔴 Create `backend/adapters/nse.py` — `NSEAdapter(DataSourceAdapter)`:
  - Implement `fetch()`: HTTP GET to NSE unofficial endpoint for latest 1m candles for given symbol
  - Rotate `User-Agent` headers on each request (minimum 3 UA strings)
  - Handle `403`, `429`, `ConnectionError`, `Timeout` — log and raise `AdapterError`
  - Parse response JSON → return `list[RawData]`
  - `health_check()`: lightweight GET to NSE base URL; return True if 200
  - `get_priority()`: return `2` (Upstox=1 deferred; NSE is current primary)
- [x] 🔴 Map NSE response fields to `RawData` schema (symbol, timestamp, o, h, l, c, v)
- [x] 🔴 Apply `floor(timestamp to minute boundary)` in transformer

  🧪 **Validation:** Run `NSEAdapter().fetch("NIFTY")` in isolation — returns a non-empty list; each item has `open`, `high`, `low`, `close`, `timestamp`.
  🧪 **Validation:** Mock HTTP 403 response — adapter raises `AdapterError` and logs the failure.

### 1.6 In-Memory Cache (Phase 1 Temporary)

- [x] 🟡 Create `backend/core/memory_cache.py`:
  - Simple dict-based store: `{symbol: {timeframe: [OHLCData]}}`
  - Methods: `set(symbol, tf, data)`, `get(symbol, tf) -> list`
  - Thread-safe using `asyncio.Lock`

### 1.7 OHLC REST Endpoint

- [x] 🔴 Create `backend/api/v1/ohlc.py`:
  - `GET /api/v1/ohlc/{symbol}` with query params: `timeframe` (default `1m`), `limit` (default 100, max 1000)
  - Fetches from in-memory cache; if empty, calls `NSEAdapter.fetch()` directly
  - Returns response matching schema in `BACKEND.md §5.1.1`
- [x] 🔴 Add `GET /api/v1/ohlc/{symbol}/latest` — returns only the most recent candle

  🧪 **Validation:** `GET /api/v1/ohlc/NIFTY` returns HTTP 200 with `data` array containing ≥ 1 candle.
  🧪 **Validation:** `/latest` returns exactly one candle object.

### 1.8 Frontend — Static Chart (Phase 1)

- [x] 🔴 Create `frontend/index.html` with:
  - TradingView Lightweight Charts loaded from CDN
  - Tailwind CSS loaded from CDN
  - Chart container `<div>` with `width: 100%, height: 70vh`
  - On `DOMContentLoaded`: fetch `GET /api/v1/ohlc/NIFTY?timeframe=1m&limit=200` → render candlestick series
  - Map REST response to `{time, open, high, low, close}` format for LWC
- [x] 🟡 Add hardcoded header bar: Symbol label, Timeframe label, placeholder source indicator

  🧪 **Validation:** Open `index.html` in browser (with backend running) — candlestick chart renders with ≥ 50 bars visible.

---

## Phase 2 — WebSocket + Redis + Aggregator

### 2.1 Yahoo Finance Adapter

- [x] 🔴 Create `backend/adapters/yahoo.py` — `YahooAdapter(DataSourceAdapter)`:
  - Use `yfinance.download()` or `Ticker.history()` with `period="1d"`, `interval="1m"`
  - Map NIFTY symbol to Yahoo symbol (`^NSEI`)
  - `get_priority()`: return `3`
  - Handle exceptions (network, parse errors) — log and raise `AdapterError`

  🧪 **Validation:** `YahooAdapter().fetch("NIFTY")` returns list with valid OHLC; test in isolation.

### 2.2 Aggregator Service

- [x] 🔴 Create `backend/services/aggregator.py` — `AggregatorService`:
  - Accepts a list of adapters sorted by priority
  - `fetch(symbol, timeframe)`: tries adapters in order; returns first successful result
  - Logs: which source was tried, which succeeded, latency per attempt
  - On all sources failing: raises `AllSourcesFailedError` (do not crash)
  - Exposes `active_source` property (name of last successful adapter)

  🧪 **Validation:** Disable NSEAdapter by injecting a mock that always raises — AggregatorService falls back to YahooAdapter and returns data.
  🧪 **Validation:** Disable both adapters — `AllSourcesFailedError` is raised; no crash.

### 2.3 Redis Integration

- [x] 🔴 Create `backend/db/redis_client.py`:
  - Async Redis client via `redis.asyncio`
  - Connection pool configured from `.env`
  - Helper methods: `set_ohlc(symbol, tf, data)`, `get_ohlc(symbol, tf) -> dict|None`, `publish(channel, message)`
  - Redis key pattern: `ohlc:{symbol}:{timeframe}:current` (TTL: 60s)
- [x] 🔴 Replace in-memory cache with Redis calls in OHLC REST endpoint

  🧪 **Validation:** After ETL cycle runs, `redis-cli GET ohlc:NIFTY:1m:current` returns valid JSON.

### 2.4 Background Polling Loop

- [x] 🔴 Create `backend/services/poller.py` — `PollingLoop`:
  - `asyncio` background task; runs every `POLL_INTERVAL` seconds (default: 2, from `.env`)
  - Each cycle: `AggregatorService.fetch()` → validate → write to Redis → (Phase 3: write to DB)
  - Exception handling: catch all exceptions, log, sleep briefly, continue loop (never stop)
  - Exposes `is_running: bool` property
- [x] 🔴 Start polling loop on FastAPI `startup` event in `main.py`
- [x] 🔴 Cancel polling loop on FastAPI `shutdown` event

  🧪 **Validation:** With backend running, check Redis every 3 seconds — `ohlc:NIFTY:1m:current` value changes (timestamp or close price updates).

### 2.5 WebSocket Endpoint

- [x] 🔴 Create `backend/api/v1/websocket.py`:
  - `GET /api/v1/ws/ohlc/{symbol}` WebSocket endpoint
  - On connect: send last cached candle immediately (from Redis)
  - Subscribe to Redis Pub/Sub channel `ohlc:updates:{symbol}`
  - Forward published messages to connected WS client
  - Send heartbeat `{"type": "heartbeat", "timestamp": "..."}` every 30 s
  - On disconnect: unsubscribe, clean up; no crash
- [x] 🔴 Polling loop publishes to Redis Pub/Sub after each successful fetch
- [x] 🔴 Add WebSocket route to FastAPI app

  🧪 **Validation:** Connect via `wscat -c ws://localhost:8000/api/v1/ws/ohlc/NIFTY` — receives candle JSON every ~2 s and heartbeat every 30 s.

### 2.6 Frontend — Live WebSocket Integration

- [~] 🔴 Create `frontend/src/services/websocket.js` — `WebSocketManager`:
  - `connect(symbol)` — opens WS connection
  - `disconnect()` — closes connection cleanly
  - Exponential backoff reconnection (max 30 s delay)
  - Emits events: `onCandle(data)`, `onHeartbeat()`, `onStatusChange(status)`
- [~] 🔴 Create `frontend/src/store.js` — central store with structure from `DESIGN.md §6`
- [~] 🔴 Update `frontend/src/main.js`:
  - On load: fetch historical data via REST → populate store
  - Connect WebSocket → on candle: update `store.realtimeCandle`
- [~] 🔴 Create `frontend/src/components/Chart.js`:
  - Initialise LWC candlestick series
  - `loadHistory(data)` — bulk sets historical candles
  - `updateCandle(candle)` — calls LWC `update()` for partial candle
  - `appendCandle(candle)` — calls LWC `update()` for new closed candle
- [~] 🔴 Create `frontend/src/components/StatusIndicator.js`:
  - Shows `wsConnected`, `dataSource` from store
  - Animated dot: green (connected), yellow (reconnecting), red (offline)

  🧪 **Validation:** Open `index.html` — rightmost chart candle updates every ~2 s without page reload. Status dot is green.
  🧪 **Validation:** Kill backend — status dot turns red/yellow and shows "Reconnecting…"; on restart, reconnects automatically.

---

## Phase 3 — ETL Pipeline + PostgreSQL Storage

### 3.1 PostgreSQL Setup

- [x] 🔴 Install TimescaleDB extension on PostgreSQL instance
- [x] 🔴 Create `backend/db/migrations/001_initial_schema.sql` with all tables from `BACKEND.md §4.1`:
  - `ohlc_data` (hypertable)
  - `symbols`
  - `source_health`
  - `etl_jobs`
  - `api_requests` (hypertable)
  - All indexes as specified
- [x] 🔴 Create `backend/db/database.py` — SQLAlchemy async engine + session factory
- [x] 🔴 Run migration and verify in `psql`

  🧪 **Validation:** `\dt` in psql shows all 5 tables; `SELECT * FROM timescaledb_information.hypertables` shows `ohlc_data`.

### 3.2 Data Validator

- [x] 🔴 Create `backend/core/validator.py` — `DataValidator`:
  - Rule 1: `high >= low`
  - Rule 2: `open <= high`
  - Rule 3: `close >= low`
  - Rule 4: `close <= high`
  - Rule 5: `timestamp` is present, is a valid datetime, and is within last 24 hours
  - Rule 6: `symbol` is non-empty string
  - Returns `ValidationResult(valid: bool, errors: list[str])`
  - Logs rejected candles with reason

  🧪 **Validation:** Unit test — feed 5 invalid OHLC samples (one per rule violation) — all return `valid=False` with correct error message.
  🧪 **Validation:** Feed a valid candle — returns `valid=True`.

### 3.3 ETL Pipeline

- [~] 🔴 Create `backend/services/etl.py` — `ETLPipeline`:
  - `run(symbol, timeframe)`:
    1. Extract: call `AggregatorService.fetch()`
    2. Transform: floor timestamp to minute, normalize field names
    3. Validate: pass each candle through `DataValidator`; skip invalid, log count
    4. Load: upsert valid candles to PostgreSQL using `ON CONFLICT DO UPDATE`; update Redis cache
  - `set_is_closed()`: candle with timestamp < current_minute floor → `is_closed=True`
  - Writes a row to `etl_jobs` on start/completion/failure
  - Updates `source_health` table after each cycle

- [x] 🔴 Replace direct `AggregatorService` call in `PollingLoop` with `ETLPipeline.run()`

  🧪 **Validation:** Run backend for 5 minutes — `SELECT COUNT(*) FROM ohlc_data WHERE symbol='NIFTY'` returns > 5.
  🧪 **Validation:** Insert same candle twice — row count remains 1 (deduplication working).
  🧪 **Validation:** Check `is_closed` — historical rows show `True`, latest row shows `False`.

### 3.4 Historical REST Endpoint (from DB)

- [x] 🔴 Update `GET /api/v1/ohlc/{symbol}` to query PostgreSQL for historical data:
  - Default: last 300 closed candles + current open candle from Redis
  - Support `from` and `to` query params (ISO 8601)
  - Cache query result in Redis for 60 s (avoid repeated DB hits)
- [x] 🟡 Add `GET /api/v1/symbols` — returns list from `symbols` table
- [x] 🟡 Seed `symbols` table with at minimum: `NIFTY`, `BANKNIFTY`

  🧪 **Validation:** `GET /api/v1/ohlc/NIFTY?limit=300` returns 300 candles from DB.
  🧪 **Validation:** On fresh page load, chart renders ≥ 200 historical bars.

---

## Phase 4 — Observability, Robustness & Frontend Polish

### 4.1 Structured Logging

- [x] 🔴 Create `backend/core/logging_config.py`:
  - JSON structured logger using Python `logging` + `python-json-logger` or manual formatter
  - Fields per log entry: `timestamp`, `level`, `source`, `symbol`, `latency_ms`, `status`, `message`
  - Configure in `main.py` startup; apply to all adapters, ETL, WebSocket manager
- [ ] 🔴 Replace all `print()` statements with structured logger calls

  🧪 **Validation:** ETL cycle produces log line parseable as JSON with all required fields.

### 4.2 Exponential Backoff & Source Ban Detection

- [x] 🔴 Create `backend/core/backoff.py` — `ExponentialBackoff`:
  - `wait(attempt: int)` — sleeps `min(2^attempt, 60)` seconds
  - Max retries configurable
- [x] 🔴 Integrate into `NSEAdapter`: on `403` or `429`, call `backoff.wait()`, log ban detection, raise after max retries
- [x] 🟡 Add User-Agent rotation on each retry (not just each request)

  🧪 **Validation:** Mock NSE to return 403 — adapter waits before each retry, logs ban detection, falls back after max retries.

### 4.3 Source Health Tracking

- [ ] 🔴 Update `ETLPipeline.run()` to write to `source_health` table after every fetch attempt:
  - Fields: `source_name`, `status` (healthy/degraded/down), `latency_ms`, `last_success_at` or `last_failure_at`
- [~] 🔴 Create `GET /api/v1/health/sources` — returns latest status per source from `source_health`
- [ ] 🟡 Cache health status in Redis key `health:{source_name}` with 30 s TTL

  🧪 **Validation:** `/api/v1/health/sources` returns `{"nse": {"status": "healthy", ...}, "yahoo": {...}}`.

### 4.4 Polling Loop Resilience

- [x] 🔴 Wrap polling loop body in `try/except Exception` — log error, sleep 5 s, continue
- [ ] 🔴 Add auto-restart: if polling task is found not running (e.g., via `asyncio.Task.done()`), restart it from a watchdog coroutine
- [ ] 🟡 Add `GET /api/v1/health` enhancement — include `poller_running: bool` and `last_poll_at` timestamp

  🧪 **Validation:** Inject an exception inside the polling loop body — loop restarts within 5 s and resumes updating Redis.

### 4.5 Rate Limiting

- [ ] 🟡 Add `slowapi` or manual Redis-based rate limiter middleware
  - `/api/v1/ohlc/*`: 100 requests/minute/IP
  - Return `429 Too Many Requests` with `Retry-After` header when exceeded

  🧪 **Validation:** Send 101 rapid requests from same IP — 101st returns HTTP 429.

### 4.6 Frontend — InfoPanel & Polish

- [~] 🟡 Create `frontend/src/components/InfoPanel.js`:
  - Displays: `Last Price`, `Volume`, `Daily High`, `Daily Low`
  - Updates on each WebSocket candle message
  - Responsive: collapses to icon row on small screens
- [ ] 🟡 Create `frontend/src/components/SymbolSelector.js` — dropdown for `["NIFTY", "BANKNIFTY"]`
  - On change: close old WS, fetch new historical data, open new WS
- [ ] 🟡 Create `frontend/src/components/TimeframeSelector.js` — dropdown for `["1m"]` (others disabled for MVP)
- [ ] 🟡 Add light/dark theme toggle button — toggles `data-theme="dark"` on `<html>`; persists in `localStorage`
- [ ] 🟢 Add `aria-label` to all icon buttons; `role="status"` to StatusIndicator; `aria-live="polite"` to source fallback notification

  🧪 **Validation:** InfoPanel shows non-zero last price after first WS message.
  🧪 **Validation:** Switching symbol changes chart title and fetches new data.

### 4.7 End-to-End Smoke Test

- [~] 🔴 Create `tests/smoke_test.py`:
  - Assert `GET /api/v1/health` returns 200
  - Assert `GET /api/v1/ohlc/NIFTY` returns ≥ 1 candle
  - Assert WebSocket connects and receives ≥ 1 message within 5 s
  - Assert `SELECT COUNT(*) FROM ohlc_data` > 0 (requires DB connection)
  - Assert `GET /api/v1/health/sources` returns valid JSON

  🧪 **Validation:** `python tests/smoke_test.py` exits with code 0.

### 4.8 Documentation

- [~] 🟡 Write `README.md`:
  - Prerequisites (Python 3.11, Redis, PostgreSQL + TimescaleDB)
  - Installation steps (clone, venv, `pip install -r requirements.txt`, `.env` setup)
  - Run instructions (`uvicorn`, Redis start, Postgres start)
  - Architecture diagram (text-based from `BACKEND.md §2.1`)
  - Known limitations (NSE ban risk, no auth, 1m only)
- [ ] 🟢 Auto-generate OpenAPI docs via FastAPI — verify at `http://localhost:8000/docs`

---

## Global Completion Criteria

The project is considered Phase 4 complete when ALL of the following are true:

| Criterion | Test |
|-----------|------|
| Chart shows live NIFTY 1m bars with < 5 s delay | Manual verification during market hours |
| Failover works: disable NSE adapter → chart keeps updating via Yahoo | Integration test |
| Historical bars on page load: ≥ 200 candles | Visual check + REST response count |
| DB deduplication: 0 duplicate rows for same `(symbol, timestamp, timeframe)` | SQL query |
| Polling loop survives injected exception | Automated test |
| `/health` and `/health/sources` return 200 | Smoke test |
| Structured log JSON parseable by `jq` | Shell test |
| Smoke test script exits 0 | CI or manual run |

---

*Document Owner: Project Lead | Last Updated: March 2026*
System.Text.RegularExpressions.MatchEvaluator
