# Copilot Instructions - Market Data Platform

## Project Identity
Python 3.11 FastAPI platform for pseudo-live Indian index market data
(NIFTY, BANKNIFTY).

Stack: FastAPI, Pydantic v2, Redis (asyncio), PostgreSQL + TimescaleDB,
httpx, Tailwind CSS, TradingView Lightweight Charts.

## Non-Negotiable Rules
- Always async/await for every I/O operation (HTTP, DB, Redis)
- Always Pydantic v2 syntax: model_validator(mode='after'), field_validator;
  never @validator
- Always Google-style docstrings on every public function and class
- Always type hints on every function signature
- Never print(); use logger = logging.getLogger(__name__)
- Never bare except; catch specific exception types only
- Never hardcode URLs, timeouts, or credentials; import from
  backend/core/config.py settings
- Always PEP 8, max 88 char lines

## Architecture Rules
- Every new adapter must extend DataSourceAdapter from backend/adapters/base.py
- OHLC timestamps must be UTC, floored to minute boundary
- Redis key format: ohlc:{symbol}:{timeframe}:current
- DB upsert: ON CONFLICT (symbol, timestamp, timeframe) DO UPDATE
- is_closed=False for current partial candle, True for all historical candles
- Log fields required: source, symbol, latency_ms, status

## File Structure
- New backend modules -> backend/{adapters|api|core|db|services}/
- New frontend components -> frontend/src/components/
- New tests -> tests/unit/ or tests/integration/ mirroring source path

## Acceptance Checklist
Before accepting any Copilot suggestion, verify:
- [ ] No non-existent imports
- [ ] Type hints present
- [ ] No hardcoded values
- [ ] Exception handling present on I/O operations
- [ ] Aligns with current task in plan/checklist.md
