# PRD.md
# Product Requirements Document
**Product:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026 | **Status:** Dev Phase MVP

---

## 1. Executive Summary

The **Indian Index Market Data Platform** is a lightweight, self-hosted, browser-based system that provides near-real-time candlestick chart visualization for major Indian market indices — primarily **NIFTY 50** and **BANKNIFTY**. It is built for developers and algorithmic traders who need reliable OHLC data infrastructure without paying for expensive institutional data feeds.

The platform aggregates 1-minute OHLC data from multiple free and unofficial sources (NSE unofficial APIs, Yahoo Finance via `yfinance`, and optionally Upstox), normalizes and validates the data through an ETL pipeline, caches it in Redis for sub-second retrieval, persists it in PostgreSQL for historical replay, and streams it to the browser via WebSocket for live chart updates.

**The core value proposition:** A developer opens `index.html` and sees a live-updating NIFTY candlestick chart within seconds — without paying for any data subscription.

---

## 2. Problem Statement

### The Problem
Individual developers and small trading operations need access to Indian index market data for building trading strategies, running backtests, and creating dashboards. The official NSE data feed and commercial providers (TrueData, Zerodha Data, Upstox premium) cost ₹2,000–₹10,000/month, which is prohibitive for personal development work.

Free alternatives (Yahoo Finance, NSE website scraping) are unreliable on their own — they block IPs, change API formats, and go down during peak hours.

### The Gap
No existing free solution provides:
- A unified data pipeline with automatic failover across sources
- Clean, validated, deduplicated OHLC data in a standard schema
- A live-updating charting interface ready to use out of the box
- A modular architecture that can be extended to backtesting or signal generation

### The Solution
This platform fills that gap with a layered, fault-tolerant approach: multiple data sources in priority order, strict data validation, Redis-backed caching, PostgreSQL persistence, and WebSocket streaming to a lightweight frontend.

---

## 3. Target Users

### Primary — Developer Trader (MVP Focus)

| Attribute | Value |
|-----------|-------|
| Age | 25–40 |
| Technical level | Python developer, basic web dev |
| Goal | Live NIFTY chart for free; foundation for algo trading |
| Pain point | NSE blocks IPs; Yahoo is stale; no affordable unified solution |
| Success | Opens `index.html`, sees live chart, data persisted for backtesting |

### Secondary — Algo Builder (Post-MVP)

| Attribute | Value |
|-----------|-------|
| Technical level | Quantitative developer |
| Goal | Clean historical OHLC data in PostgreSQL for strategy backtesting |
| Pain point | Data gaps, timezone misalignment, duplicate rows from scraping |
| Success | `SELECT * FROM ohlc_data WHERE symbol='NIFTY'` returns gapless, deduplicated data |

### Tertiary — Future Stakeholders (Out of Scope Now)

- Sponsors / collaborators evaluating architecture quality
- Small trading firms evaluating a low-cost data infrastructure starting point

---

## 4. Product Goals & Success Metrics

### 4.1 Primary Goals (Dev Phase)

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **G1 — Pseudo-live chart** | Browser shows live-updating NIFTY 1m candles during market hours | End-to-end latency P50 ≤ 5 s |
| **G2 — Source reliability** | System keeps working even when NSE blocks the IP | Failover succeeds in < 1 polling cycle; chart never goes blank |
| **G3 — Data integrity** | No duplicate, invalid, or misaligned candles in the DB | Zero rows with `high < low` or duplicate `(symbol, timestamp, timeframe)` |
| **G4 — Historical continuity** | Chart shows ≥ 200 past candles on fresh page load | REST endpoint returns ≥ 200 closed candles after 4 hours of running |
| **G5 — Developer experience** | New developer can set up and run the system quickly | Setup complete in < 30 minutes following README |

### 4.2 Secondary Goals (Robustness)

| Goal | Description | Success Metric |
|------|-------------|----------------|
| **G6 — Observability** | Failures are visible without debugging code | Every ETL failure produces a structured log line with source name and reason |
| **G7 — Resilience** | Polling loop survives crashes | Auto-restarts within 5 s of unhandled exception |
| **G8 — Extensibility** | Adding a new data source requires minimal code change | New adapter can be added by implementing 3 methods in `DataSourceAdapter` |

---

## 5. Key Features

### 5.1 Core Features (MVP — Required)

#### F1 — Live Candlestick Chart
**User story:** As a developer, I want to open `index.html` and immediately see a live NIFTY 1m candlestick chart.
- Powered by TradingView Lightweight Charts (CDN)
- Updates current (rightmost) candle every 1–3 seconds via WebSocket
- Historical bars loaded on page open from REST API
- No page reload required

#### F2 — Multi-Source Data Aggregation with Failover
**User story:** As a developer, I want automatic failover between data sources so the chart keeps updating even if NSE blocks my IP.
- Source priority: NSE unofficial (1) → Yahoo Finance (2) → [Upstox OAuth in Phase 2]
- Aggregator tries sources in order; returns first valid result
- Failed sources are logged with reason and latency
- Active source displayed in UI (e.g., "NSE" or "Yahoo fallback")

#### F3 — Data Validation & Deduplication
**User story:** As an algo builder, I want clean, normalized OHLC data stored in PostgreSQL.
- Business rule validation: `high ≥ low`, `open ≤ high`, `close ≥ low`, timestamp sanity
- Timestamp floored to minute boundary (`floor(ts / 60) * 60`)
- PostgreSQL upsert with `ON CONFLICT (symbol, timestamp, timeframe) DO UPDATE`
- `is_closed` flag: `True` for closed candles, `False` for current partial candle

#### F4 — WebSocket Pseudo-Live Streaming
**User story:** As a user, I want the current candle to keep updating smoothly without jumps.
- FastAPI WebSocket endpoint: `/api/v1/ws/ohlc/{symbol}`
- Polling loop publishes to Redis Pub/Sub every ~2 s
- WS manager subscribes and forwards to all connected clients
- Frontend auto-reconnects with exponential backoff on disconnect
- Server sends heartbeat every 30 s to keep connection alive

#### F5 — Redis Hot Cache
**User story:** As the system, I need to serve real-time data to WebSocket clients without hitting the database on every request.
- Key: `ohlc:{symbol}:{timeframe}:current` (TTL: 60 s)
- Updated every ETL cycle
- REST `/latest` endpoint reads from Redis first; falls back to DB
- Pub/Sub channel: `ohlc:updates:{symbol}` triggers WS push

#### F6 — PostgreSQL Historical Storage
**User story:** As an algo builder, I want historical OHLC data persisted across restarts.
- TimescaleDB hypertable (`ohlc_data`) partitioned by day
- Stores: symbol, timestamp, timeframe, OHLC, volume, source, is_closed
- Supports queries by symbol, timeframe, date range, and limit
- Continuous aggregates for future 5m, 15m, 1d rollups (schema-ready)

#### F7 — Health Monitoring Endpoints
**User story:** As a developer, I want to know at a glance if the system is healthy.
- `GET /api/v1/health` — overall system status + poller running status
- `GET /api/v1/health/sources` — per-source health: status, last success, latency
- Source health written to DB and Redis after every ETL cycle

### 5.2 Enhancement Features (Phase 4 — Recommended)

| Feature | Description |
|---------|-------------|
| **F8 — Structured Logging** | JSON logs per ETL cycle: source, symbol, latency, status |
| **F9 — Source Ban Detection** | Exponential backoff on 403/429 per adapter |
| **F10 — InfoPanel** | Last price, volume, daily H/L displayed below chart |
| **F11 — Symbol Selector** | Dropdown to switch between NIFTY and BANKNIFTY |
| **F12 — Dark/Light Theme** | Theme toggle, persisted in localStorage |
| **F13 — Rate Limiting** | 100 req/min per IP on REST endpoints; 429 response |

---

## 6. Non-Goals (Explicitly Out of Scope for MVP)

| Item | Reason |
|------|--------|
| Upstox OAuth2 login flow | Requires user account management; deferred to Phase 2 |
| Multi-timeframe charts (5m, 15m, 1d) | Backend aggregation needed; deferred post-MVP |
| Mobile-responsive design | Desktop/tablet only for MVP |
| Option chain, OI, Greeks data | Separate data domain; out of scope |
| User authentication / API key enforcement | Localhost only; no security concerns yet |
| Docker containerization | Deployment concern; post-MVP |
| Prometheus/Grafana monitoring | Operational overhead; post-MVP |
| Multiple simultaneous symbols in UI | Single symbol view sufficient for MVP |
| Cloud deployment | Local development only |

---

## 7. Technical Constraints

| Constraint | Detail |
|------------|--------|
| **No paid data feeds** | Only free-tier sources: NSE unofficial, Yahoo Finance, Upstox (if self-authenticated) |
| **No official NSE real-time WebSocket** | Must use polling at 1–3 s intervals |
| **Latency tolerance** | ≤ 5 s end-to-end is acceptable (not sub-second) |
| **Deployment** | Localhost only; no cloud, no Docker for MVP |
| **Frontend** | Single HTML file; no React/Vue; no build step required for MVP |
| **Dependencies** | Must be pip-installable; no heavy C++ libs |
| **Browser** | Modern browsers only (WebSocket + ES6 required) |

---

## 8. User Experience Requirements

### 8.1 Critical UX Requirements (from DESIGN.md)

| Requirement | Detail |
|-------------|--------|
| **Single page, no navigation** | Entire experience in one `index.html` |
| **Connection status always visible** | WebSocket status dot in header at all times |
| **Data source visible** | Active source name (NSE/Yahoo) shown in header |
| **Chart fills viewport** | `height: 70vh`, `width: 100%` on desktop |
| **No stale chart** | If WS disconnects, show "Reconnecting…" immediately |
| **Page load < 3 s** | Only CDN resources; no local build step needed |

### 8.2 Accessibility Requirements

- All interactive controls keyboard-navigable
- `aria-label` on icon buttons
- `role="status"` on connection indicator
- `aria-live="polite"` on data source change notification
- WCAG AA colour contrast on both light and dark themes
- Respects `prefers-reduced-motion`

---

## 9. Data Requirements

### 9.1 OHLC Data Schema

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `symbol` | string | ✅ | e.g., "NIFTY", "BANKNIFTY" |
| `timestamp` | datetime (UTC) | ✅ | Floored to minute boundary |
| `timeframe` | string | ✅ | "1m" (MVP); "5m", "15m" deferred |
| `open` | decimal(15,4) | ✅ | |
| `high` | decimal(15,4) | ✅ | Must be ≥ low |
| `low` | decimal(15,4) | ✅ | Must be ≤ high |
| `close` | decimal(15,4) | ✅ | Must be between low and high |
| `volume` | bigint | ❌ | Optional; 0 if unavailable |
| `source` | string | ✅ | "nse", "yahoo", "upstox" |
| `is_closed` | boolean | ✅ | False for current partial candle |

### 9.2 Data Quality Rules

1. `high >= low` — always enforced (reject if violated)
2. `open` is between `low` and `high`
3. `close` is between `low` and `high`
4. Timestamp is within the last 24 hours (reject stale data)
5. Symbol is in the registered symbols list
6. No duplicate `(symbol, timestamp, timeframe)` in DB

---

## 10. API Contract Summary

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/ohlc/{symbol}` | None (dev) | Historical candles with optional `from`, `to`, `limit`, `timeframe` |
| GET | `/api/v1/ohlc/{symbol}/latest` | None (dev) | Most recent candle (from Redis cache) |
| GET | `/api/v1/symbols` | None | List of active symbols |
| GET | `/api/v1/health` | None | System health + poller status |
| GET | `/api/v1/health/sources` | None | Per-source health status |
| WS | `/api/v1/ws/ohlc/{symbol}` | None (dev) | Real-time OHLC stream |

---

## 11. Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| NSE blocks IP / changes API | High | High | Immediate Yahoo fallback; exponential backoff; rotate User-Agent |
| Data inconsistency across sources | Medium | High | Strict validation; prefer higher-priority source; log discrepancies |
| Duplicate or misaligned candles | Medium | Medium | Floor timestamps; DB upsert on conflict |
| Polling loop crash | Medium | High | Exception handling; auto-restart watchdog |
| WebSocket disconnects | Low | Medium | Auto-reconnect with backoff in frontend |
| yfinance rate limits | Medium | Low | 2 s polling interval; Yahoo is fallback only |

---

## 12. Success Definition (MVP Complete)

The MVP is considered **complete and successful** when:

1. ✅ Developer opens `index.html` → live NIFTY 1m chart visible within 5 seconds
2. ✅ Disabling NSE adapter → chart continues updating via Yahoo fallback with no user intervention
3. ✅ After 2 hours of running: `SELECT COUNT(*) FROM ohlc_data` > 120 (≥1 row/minute)
4. ✅ Zero rows with `high < low` in the database
5. ✅ Chart page loads in < 3 seconds on a decent internet connection
6. ✅ All smoke tests in `tests/smoke_test.py` pass
7. ✅ A new developer can set up and run the system in < 30 minutes

---

## 13. Alignment with Source Documents

| PRD Section | Aligned Source |
|-------------|----------------|
| Target users (§3) | SRS.md §2 |
| Feature list (§5) | SRS.md §3.1, §3.2 |
| Non-goals (§6) | SRS.md §10 |
| Technical constraints (§7) | SRS.md §5 |
| API contract (§10) | BACKEND.md §5.1, Appendix A |
| Data schema (§9) | BACKEND.md §4.1 |
| UX requirements (§8) | DESIGN.md §2, §4, §9 |
| Risks (§11) | SRS.md §7 |
| Success definition (§12) | SRS.md §1.3, §3.2 |

---

*Document Owner: Product Lead | Last Updated: March 2026*