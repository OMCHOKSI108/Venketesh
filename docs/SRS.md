# Software Requirements Specification (SRS)  
**Project Name:** Pseudo-Live Indian Index Market Data Platform (Dev Phase)

**Version:** 1.0  
**Date:** March 2026  
**Status:** Draft – Development Phase

## 1. Project Overview and Objectives

### 1.1 Overview
The system is a lightweight, browser-based market data visualization platform focused on major Indian indices (primarily **NIFTY 50**, **BANKNIFTY**, later extensible to **FINNIFTY**, **SENSEX**, etc.) and optionally global indices (**S&P 500**, etc.).  

It aggregates near real-time OHLC (Open, High, Low, Close, Volume) data using a **hybrid polling + pseudo-live** approach (no paid real-time feeds), stores data in a fast cache (Redis) and persistent store (PostgreSQL), exposes it via **FastAPI**, and visualizes it in a simple single-page **index.html** using **TradingView Lightweight Charts**.

Goal = create a reliable **market data infrastructure layer** suitable for future extension to backtesting, signal generation, and execution engines.

### 1.2 Business / Product Objectives
- Provide ~1–5 second latency pseudo-live candlestick updates in development phase
- Achieve acceptable uptime / failover across free/unofficial data sources
- Minimize blocking & ban risk from NSE servers
- Build modular ETL + aggregator pattern for future paid sources
- Keep frontend extremely lightweight (single HTML file + CDN libraries)

### 1.3 Success Vision (MVP)
User opens `index.html` → sees live-updating candlestick chart of NIFTY 1-minute bars with < 5 s delay most of the time during market hours.

## 2. Stakeholders and User Personas

| Stakeholder       | Role                          | Interest / Success Metric                                 |
|-------------------|-------------------------------|-------------------------------------------------------------|
| Developer / Builder (you) | Owner, architect, implementer | Fast feedback loop, modular & testable code, easy to extend |
| Future Traders / Algos   | End users                     | Reliable pseudo-live data, clean OHLC, historical replay   |
| Potential Sponsors       | Investors / collaborators     | Clean architecture, clear failure modes, future monetization path |

**Primary Persona – Dev Trader**  
- 25–40 years old, knows Python & basic web dev  
- Wants to see live index chart without paying ₹2000+/mo for data  
- Will later build strategies on top of this data layer

## 3. Functional Requirements

### 3.1 Core Modules

| ID   | Module / Component          | Description                                                                 |
|------|-----------------------------|-----------------------------------------------------------------------------|
| FR-01| Data Extract Adapters       | Pluggable classes: UpstoxAdapter (preferred if logged-in), NSEAdapter (unofficial), YahooAdapter (fallback via yfinance) |
| FR-02| Data Validator              | Business rules: high ≥ low, open ≤ high, close ≤ high, low ≤ close, timestamp present & reasonable |
| FR-03| Aggregator Service          | Tries sources in priority order → returns first valid transformed OHLC     |
| FR-04| ETL / Polling Loop          | Background task: fetch → validate → transform → store (Redis + PostgreSQL) every ~1–3 s |
| FR-05| Redis Real-time Cache       | Key = symbol:timeframe, Value = latest OHLC JSON                           |
| FR-06| PostgreSQL Historical Store | Table `ohlc_1m` (symbol, timestamp, o, h, l, c, v, is_closed, source)     |
| FR-07| FastAPI REST API            | GET /ohlc/{symbol}?timeframe=1m → latest + recent history                 |
| FR-08| FastAPI WebSocket           | /ws/{symbol}?timeframe=1m → pushes latest candle every ~1 s               |
| FR-09| Frontend – index.html       | Single page + Lightweight Charts → connects WS → updates current candle   |

### 3.2 Key Features & Acceptance Criteria

| Feature ID | Feature                              | Acceptance Criteria                                                                                           |
|------------|--------------------------------------|---------------------------------------------------------------------------------------------------------------|
| F-01       | Fetch latest 1m candle (NIFTY)       | Given market open, within 5 s of real candle close, system returns correct OHLC from highest-priority source |
| F-02       | Source failover                      | When Upstox fails / not logged-in → falls back to NSE → then Yahoo → no crash, logs failure                   |
| F-03       | Pseudo-live WebSocket updates        | Chart updates current candle (rightmost bar) every 1–3 s without page reload                                 |
| F-04       | Historical candles on load           | On page load, chart shows last 200–500 candles (from PostgreSQL or aggregated recent)                         |
| F-05       | Timestamp alignment & deduplication  | Candles use floor(60-second) timestamp; no duplicate (symbol, timestamp) rows                                 |
| F-06       | Partial / closed candle flag         | Current (incomplete) candle marked is_closed=False; historical = True                                        |

## 4. Non-Functional Requirements

| Category       | Requirement                                                                 | Target (Dev Phase)              |
|----------------|-----------------------------------------------------------------------------|----------------------------------|
| Latency        | End-to-end update delay (fetch → WS push → chart)                           | ≤ 5 seconds (median)            |
| Availability   | Uptime during market hours (ignoring source bans)                           | ≥ 95%                           |
| Data Freshness | Age of displayed current candle                                             | ≤ 10 seconds most of time       |
| Scalability    | Concurrent symbols (browser tabs)                                           | 5–10 (not optimized yet)        |
| Security       | No authentication yet                                                       | Localhost only                  |
| Usability      | Single HTML file, no build step, uses CDN for charts                        | Load < 3 s on decent internet   |
| Maintainability| Modular adapters, clear logging, exception handling per source             | —                               |
| Observability  | Structured logging (source tried, success/fail, latency)                    | Console + optional file         |

## 5. Assumptions and Constraints

### Assumptions
- Market hours: 9:15–15:30 IST (system does not need to enforce)
- User runs everything locally (FastAPI + browser on same machine)
- NSE unofficial endpoints remain functional (high risk – see Risks)
- Upstox login is optional (not implemented in MVP)
- 1-minute timeframe is primary; others deferred
- Volume may be 0 or missing from some sources → acceptable

### Constraints
- No paid data feeds (no TrueData, Streak, NSE real-time subscription, etc.)
- No official NSE real-time WebSocket
- Cannot install heavy dependencies (keep lightweight)
- Browser must support modern WebSocket & ES6

## 6. User Stories (Prioritized)

1. As a developer, I want to open index.html and immediately see a live NIFTY 1m chart so I can validate the system works.
2. As a developer, I want automatic failover between data sources so the chart keeps updating even if NSE blocks my IP.
3. As a future algo builder, I want clean, normalized OHLC data stored in PostgreSQL so I can later run backtests.
4. As a user, I want the current candle to keep updating smoothly without jumps or missing bars.

## 7. Risks & Mitigation Strategies

| Risk ID | Risk Description                                      | Probability | Impact | Mitigation                                                                 |
|---------|-------------------------------------------------------|-------------|--------|----------------------------------------------------------------------------|
| R-01    | NSE blocks IP / changes unofficial endpoint           | High        | High   | Multiple sources, rotate User-Agent, exponential backoff, long fallback to Yahoo |
| R-02    | Data inconsistency across sources                     | Medium      | High   | Strict validation + logging; prefer Upstox > NSE > Yahoo                   |
| R-03    | Duplicate or misaligned candles                       | Medium      | Medium | Use (symbol, floor-minute-timestamp) as PK; reject invalid OHLC            |
| R-04    | Polling loop crashes / blocks                         | Medium      | High   | Run in background thread/task, restart policy, comprehensive exception logging |
| R-05    | WebSocket disconnects frequently                      | Low         | Medium | Auto-reconnect logic in frontend, exponential backoff                      |

## 8. Dependencies and External Integrations

| Dependency              | Purpose                        | Type         | Notes / Risk                              |
|-------------------------|--------------------------------|--------------|-------------------------------------------|
| FastAPI                 | Backend API & WebSocket        | Python lib   | Core                                      |
| redis-py                | Real-time cache                | Python lib   | Requires local Redis                      |
| psycopg2 / SQLAlchemy   | PostgreSQL persistence         | Python lib   | —                                         |
| yfinance                | Yahoo fallback                 | Python lib   | Rate limits possible                      |
| requests                | HTTP calls to NSE/others       | Python lib   | —                                         |
| TradingView Lightweight Charts | Browser chart rendering | CDN / npm    | ~45 KB, very reliable                     |
| Upstox API (optional)   | Best real-time source          | REST + WS    | Requires login → deferred to phase 2      |
| NSE unofficial endpoints| Primary near-real-time source  | HTTP         | High breakage risk                        |

## 9. Milestones & Suggested Timeline (Dev Phase)

| Phase | Milestone                                      | Duration | Deliverables                              |
|-------|------------------------------------------------|----------|-------------------------------------------|
| 1     | Minimal viable chart (NSE only + REST)         | 1–2 days | FastAPI + NSE adapter + index.html + Chart|
| 2     | Add WebSocket + Redis cache + Yahoo fallback   | 2–3 days | Pseudo-live updates, failover             |
| 3     | ETL background loop + PostgreSQL storage       | 2–4 days | Historical data, deduplication            |
| 4     | Validation, logging, partial candle handling   | 2–3 days | Production-grade robustness               |

## 10. Out of Scope (for MVP / Dev Phase)

- User authentication & Upstox login flow
- Multi-timeframe support (5m, 15m, daily…)
- Option chain / Greeks / OI data
- Multiple symbols selector in UI
- Mobile/responsive design
- Deployment (Docker, cloud)

---

This SRS provides a clear north star for the current development phase while leaving room for evolution into a full market data infrastructure.

Next recommended action: start **Phase 1** implementation → validate NSE adapter quickly (most fragile part).