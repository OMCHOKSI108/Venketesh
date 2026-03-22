# CODEX.md
# AI Code Generation Rules & Prompt Patterns
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026
**Applies To:** OpenAI Codex · GitHub Copilot · Any LLM used for code generation
**Responsibility:** HOW code is generated — prompts, constraints, quality gates, patterns
**Do NOT overlap with:** OPENCODE.md (execution workflow) · VSCODE.md (environment setup)

---

## 1. Purpose & Scope

This document defines the rules for using any AI code generation model (Codex, Copilot, GPT-4, Claude) within this project. It covers:
- How to construct effective, high-yield prompts
- What constraints every generated code block must satisfy
- How to validate generated output before committing
- Common anti-patterns and how to avoid them

The goal is deterministic, spec-aligned code generation — not clever one-liners. Every generated module must be traceable to a spec document and independently testable.

---

## 2. Non-Negotiable Generation Constraints

Every piece of AI-generated code, regardless of prompt, must satisfy ALL of the following before being accepted into the codebase:

### 2.1 Structural Constraints
| Constraint | Rule |
|------------|------|
| **Type hints** | All function arguments and return values must have Python type annotations |
| **Docstrings** | All public classes and functions must have Google-style docstrings |
| **Imports** | Only import modules listed in `requirements.txt` or Python stdlib |
| **File path** | File must be created at the exact path specified in `BACKEND.md §10` or `DESIGN.md §12` |
| **Interface compliance** | Any adapter must implement `DataSourceAdapter` abstract base class exactly |
| **No global state** | No module-level mutable variables; use class attributes or injected dependencies |
| **No hardcoded values** | All config (URLs, timeouts, limits) must reference `settings` from `config.py` |

### 2.2 Quality Constraints
| Constraint | Rule |
|------------|------|
| **Exception handling** | Every I/O operation wrapped in try/except with structured logging |
| **No bare except** | Never use `except:` — always catch specific exception types |
| **No print()** | Use `logger = logging.getLogger(__name__)` everywhere |
| **No TODO without task ID** | Any `# TODO` must reference a `CHECKLIST.md` task ID, e.g. `# TODO: CHECKLIST §2.3` |
| **Async correctness** | All database and HTTP calls must be `async`; never block the event loop |
| **PEP 8** | Code must pass `flake8` with max-line-length=88; imports must be isort-sorted |

### 2.3 Alignment Constraints
| Constraint | Source |
|------------|--------|
| OHLC field names match schema exactly | `BACKEND.md §4.1` |
| API response shape matches documented contract | `BACKEND.md §5.1` |
| Redis key format: `ohlc:{symbol}:{timeframe}:current` | `BACKEND.md §4.3` |
| Timestamp always UTC, floored to minute | `SRS.md §3.2 F-05` |
| `is_closed` logic: current minute = False, past = True | `SRS.md §3.2 F-06` |
| Error response format: `{"detail": "..."}` | FastAPI default convention |
| Log fields: source, symbol, latency_ms, status | `OPENCODE.md §6.5` |

---

## 3. Prompt Architecture

Every prompt to a code generation model must follow this four-part structure:

```
[ROLE]       → Who the model is and what it knows
[CONTEXT]    → The specific spec, interface, or schema it must conform to
[TASK]       → Exactly what to generate (one module, one function, one test)
[CONSTRAINTS]→ What to never do; output format; validation requirement
```

Never submit a prompt missing any of these four parts.

---

## 4. Prompt Patterns by Task Type

### 4.1 Pattern — New Adapter

**Template:**
```
ROLE: You are a senior Python backend engineer building a market data platform.
You write clean, async, PEP 8-compliant Python 3.11 code with full type hints and Google-style docstrings.

CONTEXT:
- Abstract base class DataSourceAdapter is defined in backend/adapters/base.py with methods:
    fetch(symbol: str) -> list[dict]
    health_check() -> bool
    get_priority() -> int
    property name: str
- All config (base URLs, timeouts) must be read from `settings` object imported from backend/core/config.py
- Exceptions must raise AdapterError (defined in backend/core/exceptions.py)
- Logging: use structured logging with fields: source, symbol, latency_ms, status

TASK: Generate the complete file backend/adapters/nse.py implementing NSEAdapter.
Requirements:
  1. Rotate User-Agent from a list of 3+ real browser UA strings on each request
  2. Handle HTTP 403 and 429 by raising AdapterError with ban_detected=True
  3. Handle requests.Timeout and requests.ConnectionError
  4. Parse the NSE JSON response and return list of dicts with keys: symbol, timestamp, open, high, low, close, volume
  5. Floor timestamp to the nearest minute boundary (UTC)
  6. health_check() does a lightweight GET to NSE base URL, returns True on 200
  7. get_priority() returns 2

CONSTRAINTS:
  - No hardcoded URLs; use settings.NSE_BASE_URL
  - No print(); use logger = logging.getLogger(__name__)
  - No bare except
  - Async HTTP using httpx.AsyncClient, not requests (sync is allowed only if explicitly noted)
  - Output: complete file only, no explanation prose, no markdown fences
```

**Good prompt signal:** Specific class name, specific method signatures, specific error types, specific field names, references to config.

---

### 4.2 Pattern — Pydantic Model / Validator

**Template:**
```
ROLE: Senior Python engineer, Pydantic v2 expert.

CONTEXT:
- Project uses Pydantic v2 (not v1 — use model_validator, field_validator syntax)
- All timestamps must be datetime objects in UTC timezone
- Schema reference: BACKEND.md §4.1 ohlc_data table definition

TASK: Generate backend/core/models.py containing:
  1. OHLCData model with fields: symbol (str), timestamp (datetime), timeframe (str),
     open/high/low/close (Decimal, 15,4), volume (int | None), source (str),
     is_closed (bool, default False)
  2. Field validators:
     - high >= low (ValidationError if violated)
     - open between low and high inclusive
     - close between low and high inclusive
     - timestamp must be timezone-aware
  3. RawData = dict[str, Any] type alias for pre-validation adapter output
  4. ValidationResult dataclass: valid (bool), errors (list[str])

CONSTRAINTS:
  - Pydantic v2 syntax only (model_validator(mode='after'), not @validator)
  - All validators raise ValueError with descriptive message including field values
  - No ORM mode needed yet
  - Output: complete file, no prose, no markdown fences
```

---

### 4.3 Pattern — FastAPI Endpoint

**Template:**
```
ROLE: Senior FastAPI engineer. Expert in async Python, Pydantic v2, dependency injection.

CONTEXT:
- FastAPI app is in backend/main.py
- Router prefix is /api/v1
- DB session injected via Depends(get_db_session)
- Redis client injected via Depends(get_redis)
- Response schema from BACKEND.md §5.1.1:
    {symbol, timeframe, data: [OHLCData], meta: {count, source, cached, query_time_ms}}

TASK: Generate backend/api/v1/ohlc.py containing:
  1. GET /ohlc/{symbol} with query params: timeframe (default "1m"), limit (default 100, max 1000),
     from (optional datetime), to (optional datetime)
  2. Logic: check Redis cache first → if miss, query PostgreSQL → return results
  3. GET /ohlc/{symbol}/latest — reads only from Redis; falls back to DB if Redis miss
  4. Both endpoints return proper 404 if symbol not found
  5. Both endpoints include query_time_ms in meta

CONSTRAINTS:
  - Async def for both endpoints
  - All DB queries use async SQLAlchemy (await session.execute(...))
  - Never query DB if Redis has fresh data (TTL check)
  - Return FastAPI JSONResponse with correct status codes
  - Add response_model= declarations
  - No hardcoded symbol validation — query symbols table
  - Output: complete file, no prose
```

---

### 4.4 Pattern — Unit Test

**Template:**
```
ROLE: Senior Python test engineer. Expert in pytest, pytest-asyncio, and test design.

CONTEXT:
- Test framework: pytest with pytest-asyncio
- Mocking HTTP: use responses library (not unittest.mock patch for HTTP)
- Fake Redis: use fakeredis.FakeRedis(decode_responses=True)
- Test data factory: OHLCFactory from tests/factories.py
- Test IDs from TESTING.md must appear as pytest marks: @pytest.mark.test_id("UV-01")

TASK: Generate tests/unit/test_validator.py containing tests UV-01 through UV-11
as defined in TESTING.md §2.1.1. Each test:
  1. Uses a descriptive function name matching the test description
  2. Creates input via make_raw_ohlc() helper (define this helper in the file)
  3. Calls DataValidator().validate(raw)
  4. Asserts ValidationResult.valid and ValidationResult.errors content
  5. Has a one-line docstring stating what it tests

CONSTRAINTS:
  - No integration dependencies (no Redis, no DB, no HTTP)
  - Each test function is independent (no shared mutable state)
  - Use pytest.mark.parametrize where multiple similar cases exist
  - All tests must pass with: pytest tests/unit/test_validator.py -v
  - Output: complete file, no prose
```

---

### 4.5 Pattern — Frontend Component (Vanilla JS)

**Template:**
```
ROLE: Senior frontend JavaScript engineer. Vanilla JS expert, no frameworks.

CONTEXT:
- Project uses no build step in MVP (CDN only); Vite is optional for Phase 4
- Store pattern from DESIGN.md §6: store.js with symbol, timeframe, historicalData,
  realtimeCandle, dataSource, wsConnected, error fields
- Component communication via custom DOM events or store.subscribe()
- Chart library: TradingView Lightweight Charts v4 (CDN)
- Styling: Tailwind CSS (CDN utility classes only)

TASK: Generate frontend/src/components/StatusIndicator.js:
  1. Class StatusIndicator that renders into a given container element
  2. Shows wsConnected (green dot / "Connected" or yellow dot / "Reconnecting..." or red dot / "Offline")
  3. Shows dataSource name (e.g., "NSE" or "Yahoo fallback")
  4. Subscribes to store changes for wsConnected and dataSource
  5. Animates the dot with CSS class toggling (no JS animation library)
  6. Includes aria-label on the dot element and role="status" on the container

CONSTRAINTS:
  - Vanilla JS only, no jQuery, no framework
  - No inline styles; use Tailwind utility classes exclusively
  - Export as default class
  - Cleanup method: destroy() to remove store subscription and DOM listeners
  - Output: complete file, no prose
```

---

## 5. Good vs. Bad Prompts — Annotated Examples

### Example 1: NSE Adapter

❌ **BAD PROMPT:**
```
Write a Python class to fetch NIFTY data from NSE.
```
Problems:
- No interface specified (what base class?)
- No error handling requirements
- No field names specified
- No logging format
- Will generate a requests-based sync function with no type hints

✅ **GOOD PROMPT:**
```
ROLE: Senior async Python engineer.
CONTEXT: Implements DataSourceAdapter (backend/adapters/base.py).
  Uses httpx.AsyncClient. Config from settings.NSE_BASE_URL.
  Raises AdapterError on failure.
TASK: Generate NSEAdapter.fetch("NIFTY") that:
  - Rotates User-Agent headers (3 strings)
  - Handles 403/429/Timeout/ConnectionError
  - Returns list[dict] with keys: symbol, timestamp (UTC floor-minute), open, high, low, close, volume
CONSTRAINTS: async def, no print(), no hardcoded URLs, PEP 8, type hints required.
Output: complete function body only, no prose.
```

---

### Example 2: ETL Pipeline

❌ **BAD PROMPT:**
```
Write an ETL pipeline for market data.
```
Problems:
- No steps defined (Extract/Transform/Validate/Load is not implied)
- No output schema
- No dependency injection
- Will generate monolithic synchronous code

✅ **GOOD PROMPT:**
```
ROLE: Python async engineer working on a 4-step ETL pipeline.
CONTEXT: Steps: Extract (AggregatorService.fetch()) → Transform (floor timestamp, normalize fields)
  → Validate (DataValidator.validate()) → Load (upsert to PostgreSQL + set Redis key).
  All dependencies injected via __init__. Writes to etl_jobs table on start/complete/fail.
  Writes to source_health table after each fetch.
TASK: Generate ETLPipeline.run(symbol: str, timeframe: str) -> ETLResult.
  ETLResult dataclass: candles_written (int), source (str), duration_ms (int), errors (list[str]).
CONSTRAINTS: async def, structured logging on each step, no bare except,
  on validation failure skip candle + log, never raise to caller (catch all → ETLResult with errors).
Output: complete method, no prose.
```

---

### Example 3: Pydantic Validator

❌ **BAD PROMPT:**
```
Add validation to OHLCData.
```
Problems:
- No Pydantic version specified (v1 vs v2 syntax differs significantly)
- No specific rules listed
- Will likely generate @validator (v1 syntax) not model_validator (v2)

✅ **GOOD PROMPT:**
```
ROLE: Pydantic v2 expert.
CONTEXT: OHLCData uses Pydantic v2 BaseModel. Validators use @model_validator(mode='after')
  or @field_validator. Rule: high >= low, open in [low, high], close in [low, high].
TASK: Add three field validators to OHLCData enforcing these OHLC business rules.
  Each raises ValueError with message: "OHLC violation: {rule} | values: h={high} l={low}"
CONSTRAINTS: Pydantic v2 syntax only, no v1 @validator, all validators have type hints.
Output: only the validator methods, no full class redefinition.
```

---

### Example 4: WebSocket Endpoint

❌ **BAD PROMPT:**
```
Create a WebSocket that sends market data.
```

✅ **GOOD PROMPT:**
```
ROLE: FastAPI WebSocket expert.
CONTEXT: Redis Pub/Sub channel: ohlc:updates:{symbol}. On connect: send cached candle immediately.
  Subscribe to Redis channel → forward messages to WS client. Heartbeat every 30s: {"type":"heartbeat","timestamp":"<ISO>"}.
  On client disconnect: unsubscribe + cleanup. Never crash on client drop.
TASK: Generate /api/v1/ws/ohlc/{symbol} WebSocket endpoint.
CONSTRAINTS: async def, handles WebSocketDisconnect silently, uses asyncio.create_task for heartbeat,
  all Redis calls awaited, structured log on connect/disconnect with client host.
Output: complete endpoint function, no prose.
```

---

## 6. Output Validation Checklist

After receiving any AI-generated code, run this checklist before accepting:

```
[ ] 1. Imports — all modules exist in requirements.txt or stdlib?
[ ] 2. Type hints — all function signatures annotated?
[ ] 3. Docstring — public functions/classes have Google-style docstring?
[ ] 4. Exception handling — every I/O in try/except with specific exception type?
[ ] 5. Logging — no print(); logger = logging.getLogger(__name__) used?
[ ] 6. Config — no hardcoded URLs, keys, or timeouts?
[ ] 7. Interface — if adapter, does it implement all DataSourceAdapter methods?
[ ] 8. Schema — OHLC field names match BACKEND.md §4.1 exactly?
[ ] 9. Async — all DB/HTTP calls use await?
[ ] 10. Tests — does the code pass its corresponding 🧪 Validation step from CHECKLIST.md?
[ ] 11. PEP 8 — passes flake8 --max-line-length=88?
[ ] 12. Task header comment — file has the module header block from OPENCODE.md §4 Step 3?
```

If any item fails: reject the output, correct the prompt using §5 examples, regenerate.

---

## 7. Incremental Generation Strategy

For complex modules (ETL pipeline, WebSocket manager, AggregatorService), do NOT generate the entire file in one shot. Use this incremental sequence:

```
Step 1: Generate the class skeleton (class, __init__, method stubs with docstrings)
        ↓ Validate: file is importable, no syntax errors
Step 2: Generate one method at a time (fetch() first, then health_check(), etc.)
        ↓ Validate: method passes its unit test
Step 3: Generate the __main__ standalone runner block
        ↓ Validate: python -m backend.adapters.nse runs without error
Step 4: Generate the corresponding test file
        ↓ Validate: pytest tests/unit/test_nse_adapter.py -v all pass
```

Log each step as a separate task entry in `WORKLOG.md`.

---

## 8. Code Generation Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|---|---|---|
| Generating entire app in one prompt | Output is too long, misses spec details, hard to validate | One module per prompt |
| Asking for "best practices" without spec context | Generic code not aligned to schema | Always include CONTEXT section |
| Accepting output with `# TODO` stubs | Incomplete code merged to main | Run full output validation checklist |
| Using sync `requests` for async FastAPI routes | Blocks event loop, degrades performance | Always specify `httpx.AsyncClient` |
| Not specifying Pydantic version | Gets v1 syntax in a v2 project | Always state "Pydantic v2" in CONTEXT |
| Asking for comments/explanation in output | Wastes tokens, mixes prose with code | End every prompt with "Output: code only, no prose" |
| Reusing a prompt across phases | Phase 2 code may not have DB yet | Include phase number in CONTEXT |
| Generating tests without specifying test IDs | Tests don't map to TESTING.md | Always reference test IDs (e.g., UV-01) |

---

## 9. Prompt Storage Convention

All prompts used to generate production code must be saved for traceability:

**File:** `prompts/phase_{N}/{module_name}.prompt.md`

**Format:**
```markdown
# Prompt: NSEAdapter
- Date: 2026-03-15
- Phase: 1
- Checklist Task: §1.5
- Model: codex / gpt-4 / copilot
- Output file: backend/adapters/nse.py
- Validation passed: [x]

## Prompt Used
[full prompt text]

## Notes
[anything that required correction after first generation]
```

This ensures that if a generated module needs to be regenerated (e.g., after a spec change), the original prompt is available for updating.

---

## 10. Model-Specific Notes

### OpenAI Codex (API)
- Use `temperature: 0.2` for deterministic, spec-aligned output
- `max_tokens: 2000` per function; increase to 4000 for full-file generation
- Always use `system` role for the ROLE + CONTEXT sections; `user` role for TASK + CONSTRAINTS
- Prepend the relevant excerpt from `BACKEND.md` or `DESIGN.md` to the system prompt

### GitHub Copilot (VS Code)
- Open the relevant spec file in split view before prompting
- Use Copilot Chat (not inline completion) for full module generation
- Inline completions are acceptable only for repetitive boilerplate (import blocks, similar validators)
- Always review the full suggestion before Tab-accepting; never bulk-accept multi-line suggestions

### OpenCode CLI
- Feed prompts via `opencode --task` flag with the structured 4-part format
- Use `--context-file backend/adapters/base.py` to inject the interface definition automatically
- Pipe output to a temp file; run validation checklist before moving to final location

---

*Document Owner: AI Integration Lead | Last Updated: March 2026*
*Responsibility boundary: HOW to generate code. For WHEN and in what order → see OPENCODE.md. For environment → see VSCODE.md.*