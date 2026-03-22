# OPENCODE.md
# Coding Agent Execution Workflow
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026
**Applies To:** OpenCode CLI · GitHub Copilot · Codex (see CODEX.md for generation rules)
**Responsibility:** HOW tasks are executed, ordered, tracked, and committed
**Do NOT overlap with:** CODEX.md (code generation rules) · VSCODE.md (environment setup)

---

## 1. Purpose & Scope

This document defines the **execution protocol** for any AI coding agent working on this project. It answers:
- In what order should tasks be picked up?
- How should a task be interpreted before writing any code?
- What must happen before and after each coding session?
- How are progress, blockers, and completions recorded?

Every coding agent — human-assisted or fully autonomous — must follow this protocol. Deviations must be logged in `WORKLOG.md` with a reason.

---

## 2. Source of Truth Hierarchy

Before starting any task, the agent must resolve conflicts using this priority order:

```
SRS.md          ← Functional & non-functional requirements (highest authority)
BACKEND.md      ← Architecture, schema, API contract, tech stack
DESIGN.md       ← Frontend structure, UX, component design
PHASE_PLAN.md   ← Phase scope, deliverables, dependencies
CHECKLIST.md    ← Atomic task list (primary task queue)
PRD.md          ← Product goals, success metrics
CODEX.md        ← Code generation rules (HOW to write code)
WORKLOG.md      ← Execution history and blockers (runtime record)
```

If a task in `CHECKLIST.md` conflicts with `BACKEND.md`, `BACKEND.md` wins. Always cite the source when making an architectural decision in a comment or log entry.

---

## 3. Pre-Session Checklist (Run Before Every Coding Session)

Before writing a single line of code, complete all of the following:

```
[ ] 1. Open WORKLOG.md — read the last 10 entries to understand current state
[ ] 2. Identify the current phase (1–4) from PHASE_PLAN.md
[ ] 3. Find the next unchecked [  ] task in CHECKLIST.md for that phase
[ ] 4. Read the full task block (including 🧪 Validation steps)
[ ] 5. Identify which source-of-truth documents are relevant to this task
[ ] 6. Check if any dependencies (previous tasks) are marked complete [x]
[ ] 7. Confirm the environment is ready (virtual env, Redis, Postgres if needed)
[ ] 8. Open WORKLOG.md and write a SESSION START entry (see §8)
```

**Do not begin coding if steps 6 or 7 are incomplete.** Log the blocker in `WORKLOG.md` instead.

---

## 4. Task Interpretation Protocol

When a task from `CHECKLIST.md` is assigned, follow this interpretation sequence:

### Step 1 — Parse the Task
Identify:
- **What** must be built (module, function, endpoint, component)
- **Where** it lives in the project structure (path from `BACKEND.md §10` or `DESIGN.md §12`)
- **What interface** it must conform to (base class, Pydantic model, API schema)
- **What the 🧪 Validation step requires** (the definition of done)

### Step 2 — Locate the Spec
For every task, trace it to its source document:

| Task Type | Primary Spec Source |
|-----------|-------------------|
| Data adapter | `BACKEND.md §2.2.1` + adapter interface in `CHECKLIST.md §1.4` |
| Pydantic model / validator | `BACKEND.md §4.1` + `CHECKLIST.md §1.3` |
| REST endpoint | `BACKEND.md §5.1` + response schema examples |
| WebSocket | `BACKEND.md §5.1.3` + `DESIGN.md §11` |
| ETL pipeline step | `BACKEND.md §2.2.2` ETL flow diagram |
| Frontend component | `DESIGN.md §5` component table + `§6` store structure |
| Database schema | `BACKEND.md §4.1` SQL DDL |
| Test | `TESTING.md` — find the matching test ID (e.g., UV-01) |

### Step 3 — Write a Task Summary Comment
At the top of every new file created by the agent, include:

```python
# ============================================================
# MODULE: backend/adapters/nse.py
# TASK:   CHECKLIST.md § Phase 1 › 1.5 NSE Adapter
# SPEC:   BACKEND.md §2.2.1 (DataSourceAdapter interface)
# PHASE:  1
# STATUS: In Progress
# ============================================================
```

### Step 4 — Identify Edge Cases Before Coding
Before writing implementation, list at minimum 3 edge cases relevant to the task:
- Example for NSEAdapter: network timeout, malformed JSON response, 403 ban
- Example for DataValidator: all-zero OHLC, None volume, future timestamp

Log these in the file's module docstring under `Edge Cases:`.

---

## 5. Coding Execution Rules

### 5.1 One Task at a Time
- Complete and validate ONE checklist task before starting the next.
- Never start a Phase 2 task while a Phase 1 validation step is failing.
- If a task is too large (estimated > 2 hours), split it and log both sub-tasks in `WORKLOG.md`.

### 5.2 File Creation Rules

| Situation | Rule |
|-----------|------|
| New backend module | Create in the exact path specified in `BACKEND.md §10` |
| New frontend component | Create in `frontend/src/components/` per `DESIGN.md §12` |
| New test file | Mirror the source path under `tests/` (e.g., `backend/adapters/nse.py` → `tests/unit/test_nse_adapter.py`) |
| New config/env var | Add to `.env.example` AND document in `WORKLOG.md` |
| Schema change | Update both the migration SQL AND `WORKLOG.md` with the change reason |

### 5.3 Never Do the Following
- ❌ Do not skip the 🧪 Validation step — it is the definition of done
- ❌ Do not hardcode credentials, API keys, or URLs — always use `.env` + `config.py`
- ❌ Do not import from a module that doesn't exist yet — stub it first
- ❌ Do not write to the database without running the migration first
- ❌ Do not create files outside the project structure defined in `BACKEND.md §10`
- ❌ Do not modify `CHECKLIST.md` task descriptions — only mark `[x]` or `[~]`
- ❌ Do not silently swallow exceptions — always log with source, symbol, and reason

### 5.4 Modular Development Rules
Each module must be independently importable and testable without starting the full server:

```python
# Every adapter must be runnable standalone:
if __name__ == "__main__":
    import asyncio
    adapter = NSEAdapter()
    result = asyncio.run(adapter.fetch("NIFTY"))
    print(result)
```

Every service must accept its dependencies via constructor injection (not global imports):

```python
# GOOD — injectable, testable
class ETLPipeline:
    def __init__(self, aggregator: AggregatorService, redis: RedisClient, db: AsyncSession):
        ...

# BAD — hard dependency, untestable
class ETLPipeline:
    def __init__(self):
        self.aggregator = AggregatorService()  # ← creates hidden coupling
```

---

## 6. Coding Conventions (PEP 8 + Project Standards)

### 6.1 Python Style Rules

| Rule | Standard |
|------|----------|
| Indentation | 4 spaces, never tabs |
| Line length | Max 88 characters (Black-compatible) |
| String quotes | Double quotes `"` for all strings |
| Import order | stdlib → third-party → local (isort order) |
| Type hints | Required on all function signatures |
| Docstrings | Google-style docstrings on all public functions and classes |
| Constants | `UPPER_SNAKE_CASE` at module level |
| Private members | Single underscore prefix `_method_name` |
| Async functions | `async def` for all I/O-bound functions |

### 6.2 Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Module file | `snake_case.py` | `nse_adapter.py` |
| Class | `PascalCase` | `NSEAdapter` |
| Function / method | `snake_case` | `fetch_ohlc()` |
| Async function | `snake_case` (same) | `async def fetch()` |
| Pydantic model | `PascalCase` | `OHLCData` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRIES = 3` |
| FastAPI router | `snake_case` + `_router` suffix | `ohlc_router` |
| Test function | `test_` prefix + descriptive | `test_high_less_than_low_rejected` |
| Env variable | `UPPER_SNAKE_CASE` | `REDIS_URL` |

### 6.3 Docstring Template

```python
def fetch(self, symbol: str) -> list[RawData]:
    """Fetch latest 1-minute OHLC candles from NSE unofficial endpoint.

    Args:
        symbol: Market symbol string, e.g. "NIFTY", "BANKNIFTY".

    Returns:
        List of RawData dicts with keys: open, high, low, close,
        volume, timestamp, symbol.

    Raises:
        AdapterError: If HTTP request fails, returns non-200, or
            response JSON is malformed.

    Edge Cases:
        - 403 response: NSE IP ban detected; triggers backoff.
        - Empty response body: treated as AdapterError.
        - Volume field absent: set to 0 in transform step.
    """
```

### 6.4 Exception Handling Pattern

All adapter and service exceptions must follow this pattern:

```python
import logging
logger = logging.getLogger(__name__)

try:
    response = requests.get(url, headers=self._headers(), timeout=5)
    response.raise_for_status()
except requests.Timeout:
    logger.error(
        "NSEAdapter timeout",
        extra={"source": "nse", "symbol": symbol, "latency_ms": 5000}
    )
    raise AdapterError("NSE request timed out") from None
except requests.HTTPError as exc:
    logger.error(
        "NSEAdapter HTTP error",
        extra={"source": "nse", "symbol": symbol, "status_code": exc.response.status_code}
    )
    raise AdapterError(f"NSE returned {exc.response.status_code}") from exc
```

### 6.5 Structured Log Fields (Required on Every Log Entry)

Every log statement in backend modules must include these structured fields where applicable:

```python
logger.info("ETL cycle complete", extra={
    "source": "nse",          # which adapter was used
    "symbol": "NIFTY",        # which symbol
    "timeframe": "1m",        # timeframe
    "latency_ms": 142,        # time taken in ms
    "status": "success",      # "success" | "failed" | "fallback"
    "candles_written": 1,     # rows written to DB
    "phase": 3                # development phase
})
```

---

## 7. Commit Protocol

Every logical unit of completed work must be committed independently. Use **Conventional Commits** format:

### 7.1 Commit Message Format

```
<type>(<scope>): <short description>

[optional body — what changed and why]
[optional footer — checklist task ID, phase]
```

### 7.2 Commit Types

| Type | When to Use |
|------|-------------|
| `feat` | New feature or module (adapter, endpoint, component) |
| `fix` | Bug fix in existing code |
| `test` | Adding or updating tests |
| `refactor` | Code restructure without behavior change |
| `chore` | Config, deps, `.env.example`, `requirements.txt` |
| `docs` | README, docstrings, comments |
| `db` | Schema migrations, DB changes |
| `log` | Changes to logging configuration or WORKLOG |

### 7.3 Commit Examples

```bash
# Good commits
git commit -m "feat(adapters): implement NSEAdapter with UA rotation and backoff"
git commit -m "feat(etl): add DataValidator with 6 OHLC business rules"
git commit -m "test(validator): add UV-01 through UV-11 unit tests"
git commit -m "db(migrations): create ohlc_data hypertable and indexes"
git commit -m "fix(aggregator): ensure Yahoo fallback triggers on 403 not just connection errors"
git commit -m "log(worklog): complete Phase 1 CP1-A through CP1-D"

# Bad commits — never do these
git commit -m "update"
git commit -m "fix stuff"
git commit -m "wip"
git commit -m "changes"
```

### 7.4 When to Commit
- After each 🧪 Validation step passes
- After completing each numbered sub-section in `CHECKLIST.md`
- Never commit broken/non-importable code to `main`
- Use `feat/phase-1-skeleton` style feature branches per phase

---

## 8. Progress Tracking Protocol

### 8.1 CHECKLIST.md Update Rules
- `[ ]` → Task not started
- `[~]` → Task in progress or blocked (add note in WORKLOG.md)
- `[x]` → Task complete and 🧪 Validation passed

Only mark `[x]` after the validation step passes. Never mark `[x]` speculatively.

### 8.2 WORKLOG.md Entry Requirements

Every coding session must produce at minimum:
1. A **SESSION START** entry (pre-session)
2. One **TASK COMPLETE** or **TASK BLOCKED** entry per task attempted
3. A **SESSION END** entry (post-session)

Full format defined in `WORKLOG.md` (see that document for templates).

### 8.3 Phase Gate Protocol
Before declaring a phase complete:
1. All `[x]` marks in that phase's section of `CHECKLIST.md`
2. All phase checkpoints (CP*) verified in `WORKLOG.md`
3. A `PHASE COMPLETE` entry written in `WORKLOG.md`
4. A git tag created: `git tag phase-1-complete`

---

## 9. Agent-Specific Execution Notes

### 9.1 OpenCode CLI Agent
- Always run in the project root directory
- Set context window to include: `CHECKLIST.md`, `BACKEND.md`, `WORKLOG.md`
- Use `--no-auto-commit` mode; commits are made manually after validation
- Feed one checklist task at a time via the task description
- After each task: run the 🧪 validation command and paste output into WORKLOG.md

### 9.2 GitHub Copilot (VS Code)
- Keep the relevant spec file open in a split pane (e.g., `BACKEND.md` when writing adapters)
- Use Copilot Chat with the prompt pattern from `CODEX.md §3`
- After Copilot generates code, verify against the checklist validation step before accepting
- Never accept Copilot suggestions that import non-existent modules
- Use `// @task: CHECKLIST §1.5` comments to give Copilot task context inline

### 9.3 Codex (API / Autonomous)
- Follow all prompt patterns defined in `CODEX.md` strictly
- Always include the full module task summary block (§4 Step 3) in the system prompt
- Codex output must pass the 🧪 Validation step before being written to disk
- See `CODEX.md` for input/output format and quality gates

---

## 10. Blocked Task Protocol

If a task cannot be completed (dependency missing, NSE endpoint down, etc.):

1. Mark the task `[~]` in `CHECKLIST.md`
2. Write a `TASK BLOCKED` entry in `WORKLOG.md` with:
   - Blocker description
   - Which dependency is missing
   - Workaround attempted (if any)
3. Skip to the next independent task in the same phase
4. Do NOT start Phase N+1 tasks while Phase N has unresolved `[~]` tasks

---

## 11. Rollback Protocol

If a completed task causes a regression (tests that previously passed now fail):

1. Run `git log --oneline -10` to identify the offending commit
2. Run `git revert <commit-hash>` — never `git reset --hard` on shared branches
3. Write a `ROLLBACK` entry in `WORKLOG.md`
4. Re-open the task in `CHECKLIST.md` (change `[x]` back to `[ ]`)
5. Re-diagnose using the edge cases listed in the module docstring

---

*Document Owner: Workflow Architect | Last Updated: March 2026*
*Responsibility boundary: WHAT to execute and WHEN. For HOW to generate code → see CODEX.md. For environment → see VSCODE.md.*