# TESTING.md
# Testing Strategy
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026

---

## 1. Testing Philosophy

The testing strategy follows a **pragmatic pyramid** approach calibrated for a development-phase platform with external dependencies (NSE, Yahoo Finance) that cannot be controlled. The key principle is: **mock all external I/O at the boundary, test business logic deterministically.**

```
           ▲
          /E2E\          ← Manual smoke tests + 1 automated script
         /──────\
        /  Integ  \      ← FastAPI TestClient, Redis + DB in-process
       /────────────\
      /  Unit Tests   \  ← Adapters (mocked), Validator, Aggregator, ETL
     /──────────────────\
```

**Testing Priorities:**
1. **Validation logic** — incorrect OHLC must never reach the DB (highest risk, highest impact)
2. **Aggregator failover** — source switching must be deterministic
3. **ETL pipeline** — deduplication, `is_closed` flag, transform correctness
4. **WebSocket behavior** — connection lifecycle, reconnection
5. **REST API contracts** — request/response schema correctness
6. **Frontend behavior** — data merging logic, chart update flow

---

## 2. Test Categories

### 2.1 Unit Tests

**Scope:** Individual classes and pure functions, zero external I/O.

**Coverage targets:** 80%+ on all `backend/core/` and `backend/adapters/` modules.

#### 2.1.1 DataValidator Tests

**File:** `tests/unit/test_validator.py`

| Test ID | Description | Input | Expected |
|---------|-------------|-------|----------|
| UV-01 | Valid candle passes all rules | `{h:100, l:90, o:95, c:98}` | `valid=True` |
| UV-02 | `high < low` rejected | `{h:90, l:100}` | `valid=False`, rule 1 in errors |
| UV-03 | `open > high` rejected | `{o:110, h:100}` | `valid=False`, rule 2 in errors |
| UV-04 | `close < low` rejected | `{c:80, l:90}` | `valid=False`, rule 3 in errors |
| UV-05 | `close > high` rejected | `{c:110, h:100}` | `valid=False`, rule 4 in errors |
| UV-06 | Missing timestamp rejected | No `timestamp` field | `valid=False`, rule 5 in errors |
| UV-07 | Timestamp > 24h old rejected | `timestamp = now - 25h` | `valid=False` |
| UV-08 | Empty symbol rejected | `symbol=""` | `valid=False`, rule 6 in errors |
| UV-09 | Volume = 0 accepted | `volume=0` | `valid=True` (volume optional) |
| UV-10 | Volume = None accepted | `volume=None` | `valid=True` |
| UV-11 | Multiple violations reported | `h<l AND o>h` | Both errors in `errors` list |

```python
# Example test structure
def test_high_less_than_low_is_invalid():
    raw = make_raw_ohlc(high=90.0, low=100.0)
    result = DataValidator().validate(raw)
    assert result.valid is False
    assert any("high" in err.lower() for err in result.errors)
```

#### 2.1.2 NSEAdapter Tests

**File:** `tests/unit/test_nse_adapter.py`

| Test ID | Description | Mock | Expected |
|---------|-------------|------|----------|
| UN-01 | Successful fetch returns list of RawData | HTTP 200 with valid JSON | Non-empty list |
| UN-02 | 403 response raises AdapterError | HTTP 403 | `AdapterError` raised, logged |
| UN-03 | 429 response raises AdapterError | HTTP 429 | `AdapterError` raised |
| UN-04 | Connection timeout raises AdapterError | `requests.Timeout` | `AdapterError` raised |
| UN-05 | Malformed JSON raises AdapterError | HTTP 200, invalid JSON | `AdapterError` raised |
| UN-06 | User-Agent is rotated across calls | 3 consecutive calls | 3 different UA strings |
| UN-07 | `health_check()` returns True on 200 | HTTP 200 | `True` |
| UN-08 | `health_check()` returns False on failure | `ConnectionError` | `False` |

```python
# Example: mock HTTP using pytest-mock or responses library
@responses.activate
def test_nse_adapter_403_raises_adapter_error():
    responses.add(responses.GET, NSE_URL, status=403)
    with pytest.raises(AdapterError):
        NSEAdapter().fetch("NIFTY")
```

#### 2.1.3 YahooAdapter Tests

**File:** `tests/unit/test_yahoo_adapter.py`

| Test ID | Description | Mock | Expected |
|---------|-------------|------|----------|
| UY-01 | Successful fetch returns valid data | Mock `yfinance.Ticker` | Non-empty list |
| UY-02 | yfinance exception → AdapterError | `Exception` in download | `AdapterError` raised |
| UY-03 | Empty DataFrame → AdapterError | Empty DataFrame | `AdapterError` raised |
| UY-04 | Symbol mapping: NIFTY → `^NSEI` | Any call | yfinance called with `^NSEI` |

#### 2.1.4 AggregatorService Tests

**File:** `tests/unit/test_aggregator.py`

| Test ID | Description | Setup | Expected |
|---------|-------------|-------|----------|
| UA-01 | First source succeeds → returns data | NSE returns data | NSE data returned, active_source="nse" |
| UA-02 | First fails, second succeeds → fallback | NSE raises, Yahoo returns | Yahoo data returned, active_source="yahoo" |
| UA-03 | All sources fail → raises error | Both raise AdapterError | `AllSourcesFailedError` raised |
| UA-04 | Failure of first source is logged | NSE raises | Log contains "nse" and "failed" |
| UA-05 | Sources tried in priority order | NSE=1, Yahoo=2 | NSE tried before Yahoo |

#### 2.1.5 ETL Pipeline Tests

**File:** `tests/unit/test_etl.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| UE-01 | Valid candle stored in Redis | `redis.get(key)` returns JSON after run |
| UE-02 | Valid candle upserted to DB | DB row count increases by 1 |
| UE-03 | Invalid candle skipped, not stored | DB count unchanged; warning logged |
| UE-04 | Duplicate candle → single DB row | Insert same candle twice → 1 row |
| UE-05 | `is_closed=True` for minute-old candle | Closed candle flagged correctly |
| UE-06 | `is_closed=False` for current candle | Current candle flagged correctly |
| UE-07 | ETL job row created on run | `etl_jobs` table has 1 row after run |
| UE-08 | ETL job status = "completed" on success | `etl_jobs.status = "completed"` |
| UE-09 | ETL job status = "failed" on error | `etl_jobs.status = "failed"` with `error_message` |

#### 2.1.6 Timestamp Flooring Tests

**File:** `tests/unit/test_transforms.py`

| Test ID | Input Timestamp | Expected Floored TS |
|---------|-----------------|---------------------|
| UT-01 | `09:15:37 IST` | `09:15:00 IST` |
| UT-02 | `09:15:00 IST` | `09:15:00 IST` (idempotent) |
| UT-03 | `09:15:59 IST` | `09:15:00 IST` |
| UT-04 | `15:29:01 IST` | `15:29:00 IST` |

#### 2.1.7 ExponentialBackoff Tests

**File:** `tests/unit/test_backoff.py`

| Test ID | Attempt | Expected Wait (s) |
|---------|---------|-------------------|
| UB-01 | 0 | 1 |
| UB-02 | 1 | 2 |
| UB-03 | 3 | 8 |
| UB-04 | 10 | 60 (capped) |

---

### 2.2 Integration Tests

**Scope:** Multiple real components interacting. Uses real Redis (or `fakeredis`) and a test PostgreSQL database. No mocking of internal services — only external HTTP calls are mocked.

**File location:** `tests/integration/`

#### 2.2.1 REST API Integration Tests

**File:** `tests/integration/test_api_ohlc.py`
**Tool:** FastAPI `TestClient` (sync) or `AsyncClient` (httpx)

| Test ID | Endpoint | Setup | Expected |
|---------|----------|-------|----------|
| IR-01 | `GET /api/v1/ohlc/NIFTY` | DB seeded with 10 candles | HTTP 200, `data` array length 10 |
| IR-02 | `GET /api/v1/ohlc/NIFTY?limit=5` | DB has 10 candles | Returns 5 candles |
| IR-03 | `GET /api/v1/ohlc/NIFTY/latest` | Redis has current candle | HTTP 200, single candle object |
| IR-04 | `GET /api/v1/ohlc/NIFTY/latest` | Redis empty, DB has data | Falls back to DB, returns latest |
| IR-05 | `GET /api/v1/ohlc/UNKNOWN` | Symbol not in DB | HTTP 404 |
| IR-06 | `GET /api/v1/symbols` | 2 symbols seeded | HTTP 200, 2-item array |
| IR-07 | `GET /api/v1/health` | Normal operation | HTTP 200, `status: "ok"` |
| IR-08 | `GET /api/v1/health/sources` | NSE = healthy, Yahoo = healthy | HTTP 200, 2 sources with status |
| IR-09 | `GET /api/v1/ohlc/NIFTY` with `from` and `to` | 20 candles in range | Returns only candles in range |
| IR-10 | 101 requests same IP | Rate limiter active | 101st returns HTTP 429 |

#### 2.2.2 WebSocket Integration Tests

**File:** `tests/integration/test_websocket.py`
**Tool:** `httpx` + `websockets` library or FastAPI `WebSocketTestSession`

| Test ID | Description | Expected |
|---------|-------------|----------|
| IW-01 | Connect to `/api/v1/ws/ohlc/NIFTY` | Connection established; immediate candle sent |
| IW-02 | Receive candle within 5 s of polling | Message received with valid OHLC fields |
| IW-03 | Receive heartbeat within 35 s | `{"type": "heartbeat"}` message received |
| IW-04 | Disconnect and reconnect | No server error; new connection accepted |
| IW-05 | Two simultaneous clients on same symbol | Both clients receive same candle update |
| IW-06 | Client sends invalid message | Server does not crash; optionally returns error frame |

```python
# Example WebSocket integration test
async def test_websocket_receives_candle():
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/api/v1/ws/ohlc/NIFTY") as ws:
            data = await asyncio.wait_for(ws.receive_json(), timeout=5.0)
            assert "open" in data
            assert "close" in data
            assert "timestamp" in data
```

#### 2.2.3 ETL + Storage Integration Tests

**File:** `tests/integration/test_etl_pipeline.py`

| Test ID | Description | Expected |
|---------|-------------|----------|
| IE-01 | Full ETL cycle writes to Redis | Redis key `ohlc:NIFTY:1m:current` exists |
| IE-02 | Full ETL cycle writes to PostgreSQL | 1 row in `ohlc_data` after 1 cycle |
| IE-03 | Second ETL cycle with same candle | Still 1 row (no duplicate) |
| IE-04 | ETL with invalid candle (NSE returns bad data) | 0 rows in DB; warning log exists |
| IE-05 | Aggregator fallback during ETL | Yahoo data reaches DB with `source='yahoo'` |
| IE-06 | `source_health` updated after ETL | Row in `source_health` with recent `checked_at` |

---

### 2.3 End-to-End Tests

**Scope:** Full system running (FastAPI + Redis + PostgreSQL) tested from the outside. These tests treat the system as a black box.

#### 2.3.1 Automated Smoke Test

**File:** `tests/smoke_test.py`
**Run with:** `python tests/smoke_test.py`

```python
# Smoke test assertions (all must pass for green):
assert GET("/api/v1/health").status == 200
assert GET("/api/v1/ohlc/NIFTY").data count >= 1
assert websocket_receives_message_within(symbol="NIFTY", timeout=5)
assert db_row_count("ohlc_data") > 0
assert GET("/api/v1/health/sources").json has "nse" key
```

**Pass Criteria:** Script exits with code 0. Failure prints which assertion failed.

#### 2.3.2 Manual E2E Scenarios

Performed manually during market hours (9:15–15:30 IST):

| Scenario | Steps | Pass Criteria |
|----------|-------|---------------|
| **E2E-01: Happy path** | Start backend, open `index.html` | Chart renders, updates live |
| **E2E-02: Failover** | Block NSE via `/etc/hosts`, open chart | Source indicator switches to Yahoo; updates continue |
| **E2E-03: WS reconnect** | Kill and restart backend mid-session | "Reconnecting…" shown; reconnects on backend return |
| **E2E-04: Historical on load** | Run backend 1 hour; reload page | ≥ 60 historical bars visible immediately on load |
| **E2E-05: Deduplication check** | Run 30 min; query `SELECT COUNT(*)` | Count = minutes elapsed (not more) |

---

### 2.4 Frontend / Component Tests

**Tool:** Jest + jsdom (for future formal testing; see `DESIGN.md §7`)
**MVP:** Manual browser testing using Chrome DevTools

#### 2.4.1 Manual Browser Checklist

| Test | Steps | Pass |
|------|-------|------|
| Chart renders on load | Open `index.html` with backend running | ✅ Candlesticks visible |
| Current candle updates | Watch rightmost candle for 30 s | ✅ Close price changes |
| WS status shows connected | Check header indicator | ✅ Green dot |
| Reconnect on disconnect | Stop backend, wait, restart backend | ✅ Status → yellow → green |
| InfoPanel shows price | Check footer panel | ✅ Non-zero last price |
| Symbol switch | Click BANKNIFTY in dropdown | ✅ New chart data loads |
| Dark mode | Click theme toggle | ✅ UI switches to dark theme |
| Keyboard nav | Tab through all controls | ✅ Focus visible on all elements |

#### 2.4.2 Data Merging Logic Tests (Unit — JavaScript)

**File:** `frontend/tests/dataMerger.test.js`

| Test | Description | Expected |
|------|-------------|----------|
| DM-01 | `is_closed=true` candle appended to history | `historicalData.length` increases by 1 |
| DM-02 | `is_closed=false` replaces `realtimeCandle` | `realtimeCandle` updated; `historicalData` unchanged |
| DM-03 | Multiple closed candles added in sequence | History array grows correctly, no duplicates |
| DM-04 | Out-of-order candle (older timestamp) | Ignored or sorted correctly |

---

## 3. Test Infrastructure

### 3.1 Tools & Frameworks

| Tool | Version | Purpose |
|------|---------|---------|
| `pytest` | ≥8.0 | Python test runner |
| `pytest-asyncio` | ≥0.23 | Async test support |
| `httpx` | ≥0.27 | FastAPI async test client |
| `responses` | ≥0.25 | Mock HTTP responses for adapter tests |
| `fakeredis` | ≥2.20 | In-process Redis mock (no local Redis needed for unit tests) |
| `pytest-cov` | ≥4.0 | Coverage reporting |
| `factory-boy` | ≥3.3 | Test data factories for OHLC objects |
| `pytest-mock` | ≥3.12 | `mocker` fixture for clean mocking |
| `Jest` (JS) | ≥29 | Frontend unit tests |
| `jsdom` | ≥24 | DOM simulation for JS component tests |

### 3.2 Test Data Factories

**File:** `tests/factories.py`

```python
import factory
from backend.core.models import OHLCData
from datetime import datetime, timezone

class OHLCFactory(factory.Factory):
    class Meta:
        model = OHLCData
    
    symbol = "NIFTY"
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc).replace(second=0, microsecond=0))
    timeframe = "1m"
    open = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)
    high = factory.LazyAttribute(lambda o: o.open * 1.005)
    low = factory.LazyAttribute(lambda o: o.open * 0.995)
    close = factory.LazyAttribute(lambda o: (o.high + o.low) / 2)
    volume = factory.Faker("random_int", min=10000, max=5000000)
    is_closed = True
    source = "nse"
```

### 3.3 Test Database Setup

```python
# tests/conftest.py
import pytest
import fakeredis
from sqlalchemy import create_engine
from backend.db.database import Base

@pytest.fixture(scope="session")
def test_db():
    engine = create_engine("postgresql://test:test@localhost/test_marketdata")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)
```

### 3.4 Directory Structure

```
tests/
├── conftest.py                     # Shared fixtures
├── factories.py                    # OHLCFactory, etc.
├── smoke_test.py                   # E2E smoke test script
├── unit/
│   ├── test_validator.py
│   ├── test_nse_adapter.py
│   ├── test_yahoo_adapter.py
│   ├── test_aggregator.py
│   ├── test_etl.py
│   ├── test_transforms.py
│   └── test_backoff.py
├── integration/
│   ├── test_api_ohlc.py
│   ├── test_websocket.py
│   └── test_etl_pipeline.py
└── frontend/
    └── dataMerger.test.js
```

---

## 4. Coverage Requirements

| Module | Min Coverage |
|--------|-------------|
| `backend/core/validator.py` | 95% |
| `backend/core/models.py` | 90% |
| `backend/adapters/nse.py` | 85% |
| `backend/adapters/yahoo.py` | 85% |
| `backend/services/aggregator.py` | 90% |
| `backend/services/etl.py` | 85% |
| `backend/api/v1/ohlc.py` | 80% |
| `backend/api/v1/websocket.py` | 75% |
| Overall backend | 80% |

Run coverage:
```bash
pytest --cov=backend --cov-report=html tests/unit/ tests/integration/
```

---

## 5. QA Workflow

### 5.1 Per-Feature QA Process

```
Developer completes a feature
        │
        ▼
Write / update unit tests for new logic
        │
        ▼
Run unit tests: pytest tests/unit/
        │
        ├─── FAIL → fix code → re-run
        │
        ▼ PASS
Run integration tests: pytest tests/integration/
        │
        ├─── FAIL → fix → re-run
        │
        ▼ PASS
Manual browser test (if frontend change)
        │
        ▼
Mark checklist item [x] in CHECKLIST.md
        │
        ▼
Run smoke test before moving to next phase
```

### 5.2 Phase Gate Testing

Before marking a phase complete, ALL of the following must pass:

| Phase | Gate Criteria |
|-------|--------------|
| Phase 1 | All UV-* and UN-* unit tests pass; manual chart renders |
| Phase 2 | All UA-* tests + IW-01 to IW-04 pass; live chart updates in browser |
| Phase 3 | All UE-* and IE-* tests pass; deduplication verified via SQL |
| Phase 4 | Smoke test exits 0; coverage ≥ 80% overall |

### 5.3 Bug Tracking Process

**For this development phase, use a simple `BUGS.md` file in the repo root.**

Each bug entry:
```markdown
## BUG-001: NSE Adapter returns stale data after market close
- Reported: 2026-03-15
- Severity: Medium
- Phase: 2
- Status: Open
- Repro: Run backend after 15:30 IST — NSE returns yesterday's last candle
- Expected: Adapter should return empty or flag as stale
- Fix: Add timestamp staleness check in DataValidator (Rule 5)
```

**Severity levels:**
- 🔴 **Critical** — Data corruption, crash, or complete feature failure
- 🟡 **High** — Feature degraded; workaround exists
- 🟢 **Medium/Low** — Minor UX or cosmetic issue

---

## 6. Regression Testing

After any change to adapters, aggregator, or ETL pipeline, re-run the full unit + integration suite:

```bash
# Full regression
pytest tests/unit/ tests/integration/ -v --tb=short

# Quick smoke (pre-commit hook)
pytest tests/unit/ -x -q
```

**Pre-commit hook recommendation** (`.git/hooks/pre-commit`):
```bash
#!/bin/bash
pytest tests/unit/ -x -q
if [ $? -ne 0 ]; then
    echo "Unit tests failed. Commit blocked."
    exit 1
fi
```

---

## 7. Performance Testing (Manual, Phase 4)

| Test | Method | Pass Criteria |
|------|--------|---------------|
| API response time | `time curl /api/v1/ohlc/NIFTY?limit=300` | < 100 ms |
| WebSocket latency | Log timestamp at publish vs. receive | P50 < 1 s, P95 < 3 s |
| ETL cycle duration | Log `start` and `end` per cycle | < 500 ms per full cycle |
| Page load time | Chrome DevTools → Network tab | DOMContentLoaded < 3 s |

---

*Document Owner: QA Lead | Last Updated: March 2026*