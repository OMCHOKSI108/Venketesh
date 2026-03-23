# VSCODE.md
# Developer Environment Setup — VS Code
**Project:** Pseudo-Live Indian Index Market Data Platform
**Version:** 1.0 | **Date:** March 2026
**Applies To:** VS Code (primary IDE) + GitHub Copilot integration
**Responsibility:** Environment, tooling, extensions, debug config, workspace layout
**Do NOT overlap with:** OPENCODE.md (execution workflow) · CODEX.md (code generation rules)

---

## 1. Prerequisites

Before opening VS Code, ensure the following are installed on your machine:

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | `pyenv install 3.11.8` or official installer |
| Node.js | 18+ (for Vite/frontend tooling in Phase 4) | `nvm install 18` |
| Redis | 7+ | `brew install redis` / `apt install redis-server` |
| PostgreSQL | 15+ with TimescaleDB | See TimescaleDB install docs |
| Git | 2.40+ | `git --version` |
| VS Code | Latest stable | code.visualstudio.com |

**Verify before first run:**
```bash
python --version          # 3.11.x
redis-cli ping            # PONG
psql --version            # 15.x
git --version             # 2.40+
```

---

## 2. Workspace Setup

### 2.1 Clone & Open

```bash
https://github.com/OMCHOKSI108/Venketesh
cd market-data-platform
code .                    # opens VS Code in project root
```

### 2.2 Python Virtual Environment

```bash


# Activate
source .venv/bin/activate       # Linux/macOS
.venv\Scripts\activate          # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Verify FastAPI works
uvicorn backend.main:app --reload --port 8000
```

### 2.3 Environment File

```bash
cp .env.example .env
# Edit .env with your local values:
```

```ini
# .env (local only — never commit)
APP_NAME=market-data-platform
DEBUG=true
LOG_LEVEL=debug
ENVIRONMENT=development

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/marketdata_dev
DATABASE_POOL_SIZE=5

REDIS_URL=redis://localhost:6379/0
REDIS_POOL_SIZE=10

NSE_ENABLED=true
YAHOO_ENABLED=true
UPSTOX_ENABLED=false
NSE_BASE_URL=https://www.nseindia.com
POLL_INTERVAL=2

RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
WS_HEARTBEAT_INTERVAL=30
```

---

## 3. VS Code Workspace Configuration

### 3.1 `.vscode/settings.json`

Create this file at project root:

```json
{
  // Python interpreter — always use project venv
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.terminal.activateEnvironment": true,

  // Formatting
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "ms-python.black-formatter",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": "explicit"
    }
  },
  "[javascript]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true
  },
  "[html]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode"
  },

  // Linting
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.linting.flake8Args": [
    "--max-line-length=88",
    "--extend-ignore=E203,W503"
  ],
  "python.linting.pylintEnabled": false,

  // Type checking
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true,

  // Testing
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/", "-v", "--tb=short"],
  "python.testing.unittestEnabled": false,
  "python.testing.cwd": "${workspaceFolder}",

  // Editor behaviour
  "editor.rulers": [88],
  "editor.tabSize": 4,
  "editor.insertSpaces": true,
  "editor.trimAutoWhitespace": true,
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true,

  // File associations
  "files.associations": {
    "*.env.example": "dotenv",
    "*.prompt.md": "markdown"
  },

  // Explorer
  "explorer.fileNesting.enabled": true,
  "explorer.fileNesting.patterns": {
    "*.py": "${capture}.pyi",
    ".env.example": ".env",
    "requirements.txt": "requirements-dev.txt"
  },

  // Terminal
  "terminal.integrated.defaultProfile.linux": "bash",
  "terminal.integrated.env.linux": {
    "PYTHONPATH": "${workspaceFolder}"
  },
  "terminal.integrated.env.osx": {
    "PYTHONPATH": "${workspaceFolder}"
  },

  // Git
  "git.autofetch": true,
  "git.confirmSync": false
}
```

### 3.2 `.vscode/extensions.json`

```json
{
  "recommendations": [
    // Python core
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "ms-python.vscode-pylance",
    "ms-python.flake8",

    // AI assistance
    "github.copilot",
    "github.copilot-chat",

    // Database
    "mtxr.sqltools",
    "mtxr.sqltools-driver-pg",
    "cweijan.vscode-redis-client",

    // REST / API testing
    "humao.rest-client",

    // Frontend / HTML
    "esbenp.prettier-vscode",
    "bradlc.vscode-tailwindcss",
    "ritwickdey.liveserver",

    // Markdown
    "yzhang.markdown-all-in-one",
    "davidanson.vscode-markdownlint",

    // Git
    "eamodio.gitlens",
    "mhutchie.git-graph",

    // Environment
    "mikestead.dotenv",

    // Productivity
    "gruntfuggly.todo-tree",
    "streetsidesoftware.code-spell-checker",
    "christian-kohler.path-intellisense",
    "ms-vscode.live-share"
  ]
}
```

### 3.3 `.vscode/launch.json` — Debug Configurations

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI: Dev Server",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "backend.main:app",
        "--reload",
        "--port", "8000",
        "--log-level", "debug"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "ENV_FILE": "${workspaceFolder}/.env"
      },
      "console": "integratedTerminal",
      "justMyCode": true
    },
    {
      "name": "FastAPI: Production Mode",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "backend.main:app",
        "--port", "8000",
        "--workers", "1"
      ],
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "ENVIRONMENT": "production"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "Pytest: All Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/", "-v", "--tb=short"],
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Pytest: Unit Tests Only",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/unit/", "-v", "--tb=short"],
      "console": "integratedTerminal"
    },
    {
      "name": "Pytest: Integration Tests",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["tests/integration/", "-v", "--tb=short"],
      "console": "integratedTerminal"
    },
    {
      "name": "Smoke Test",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/tests/smoke_test.py",
      "console": "integratedTerminal"
    },
    {
      "name": "Debug: NSE Adapter (standalone)",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/backend/adapters/nse.py",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    },
    {
      "name": "Debug: Current File",
      "type": "python",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal",
      "env": {
        "PYTHONPATH": "${workspaceFolder}"
      }
    }
  ]
}
```

### 3.4 `.vscode/tasks.json` — Common Tasks

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Start: Redis",
      "type": "shell",
      "command": "redis-server",
      "isBackground": true,
      "presentation": { "group": "services", "reveal": "silent" }
    },
    {
      "label": "Start: FastAPI Dev",
      "type": "shell",
      "command": "source .venv/bin/activate && uvicorn backend.main:app --reload --port 8000",
      "isBackground": true,
      "presentation": { "group": "services", "reveal": "always" },
      "problemMatcher": []
    },
    {
      "label": "Start: All Services",
      "dependsOn": ["Start: Redis", "Start: FastAPI Dev"],
      "group": { "kind": "build", "isDefault": true }
    },
    {
      "label": "Test: Unit",
      "type": "shell",
      "command": "source .venv/bin/activate && pytest tests/unit/ -v --tb=short",
      "group": { "kind": "test", "isDefault": true },
      "presentation": { "reveal": "always" }
    },
    {
      "label": "Test: All",
      "type": "shell",
      "command": "source .venv/bin/activate && pytest tests/ -v --tb=short --cov=backend --cov-report=term-missing",
      "group": "test"
    },
    {
      "label": "Lint: Flake8",
      "type": "shell",
      "command": "source .venv/bin/activate && flake8 backend/ --max-line-length=88",
      "group": "test"
    },
    {
      "label": "Format: Black",
      "type": "shell",
      "command": "source .venv/bin/activate && black backend/ tests/",
      "group": "none"
    },
    {
      "label": "DB: Run Migrations",
      "type": "shell",
      "command": "psql $DATABASE_URL -f backend/db/migrations/001_initial_schema.sql",
      "group": "none",
      "presentation": { "reveal": "always" }
    },
    {
      "label": "Smoke Test",
      "type": "shell",
      "command": "source .venv/bin/activate && python tests/smoke_test.py",
      "group": "test"
    },
    {
      "label": "Open: API Docs",
      "type": "shell",
      "command": "open http://localhost:8000/docs || xdg-open http://localhost:8000/docs",
      "group": "none"
    },
    {
      "label": "Open: Frontend",
      "type": "shell",
      "command": "open frontend/index.html || xdg-open frontend/index.html",
      "group": "none"
    }
  ]
}
```

---

## 4. Project Structure in Explorer

The VS Code Explorer should show this structure (aligned with `BACKEND.md §10` and `DESIGN.md §12`):

```
market-data-platform/
│
├── 📁 .vscode/
│   ├── settings.json
│   ├── launch.json
│   ├── tasks.json
│   └── extensions.json
│
├── 📁 backend/
│   ├── 📁 adapters/
│   │   ├── base.py           ← DataSourceAdapter ABC
│   │   ├── nse.py            ← Phase 1
│   │   ├── yahoo.py          ← Phase 2
│   │   └── upstox.py         ← Phase 4 (stub)
│   ├── 📁 api/
│   │   └── 📁 v1/
│   │       ├── ohlc.py
│   │       ├── health.py
│   │       ├── symbols.py
│   │       └── websocket.py
│   ├── 📁 core/
│   │   ├── config.py         ← Settings / env loader
│   │   ├── models.py         ← Pydantic models + OHLCData
│   │   ├── validator.py      ← DataValidator
│   │   ├── exceptions.py     ← AdapterError, AllSourcesFailedError
│   │   ├── backoff.py        ← ExponentialBackoff
│   │   └── logging_config.py ← JSON structured logging
│   ├── 📁 db/
│   │   ├── database.py       ← SQLAlchemy async engine
│   │   ├── redis_client.py   ← Redis async client
│   │   └── 📁 migrations/
│   │       └── 001_initial_schema.sql
│   ├── 📁 services/
│   │   ├── aggregator.py     ← AggregatorService
│   │   ├── etl.py            ← ETLPipeline
│   │   └── poller.py         ← PollingLoop background task
│   └── main.py               ← FastAPI app entry point
│
├── 📁 frontend/
│   ├── index.html            ← Single-page app entry
│   └── 📁 src/
│       ├── main.js
│       ├── store.js
│       ├── 📁 components/
│       │   ├── App.js
│       │   ├── Chart.js
│       │   ├── SymbolSelector.js
│       │   ├── TimeframeSelector.js
│       │   ├── StatusIndicator.js
│       │   └── InfoPanel.js
│       ├── 📁 services/
│       │   ├── api.js
│       │   ├── websocket.js
│       │   └── dataMerger.js
│       └── 📁 utils/
│           ├── dom.js
│           ├── format.js
│           └── validation.js
│
├── 📁 tests/
│   ├── conftest.py
│   ├── factories.py
│   ├── smoke_test.py
│   ├── 📁 unit/
│   └── 📁 integration/
│
├── 📁 prompts/               ← Saved Codex prompts (see CODEX.md §9)
│   └── 📁 phase_1/
│
├── 📁 docs/                  ← Planning documents
│   ├── PHASE_PLAN.md
│   ├── CHECKLIST.md
│   ├── PRD.md
│   ├── TESTING.md
│   ├── OPENCODE.md
│   ├── CODEX.md
│   ├── VSCODE.md
│   └── WORKLOG.md
│
├── .env                      ← Local only, gitignored
├── .env.example              ← Committed, no secrets
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 5. Recommended Extension Configuration

### 5.1 GitLens
- Enable: Line blame annotations (`gitlens.currentLine.enabled: true`)
- Enable: File history in sidebar
- Use "Git Graph" extension alongside for branch visualization

### 5.2 SQLTools (PostgreSQL)
Configure a connection in the SQLTools sidebar:
```json
{
  "name": "MarketData Dev",
  "driver": "PostgreSQL",
  "server": "localhost",
  "port": 5432,
  "database": "marketdata_dev",
  "username": "postgres"
}
```
Use SQLTools to verify DB migrations, inspect `ohlc_data` rows, and run deduplication checks from `CHECKLIST.md`.

### 5.3 Redis Client (cweijan)
- Connect to `redis://localhost:6379`
- Use to inspect `ohlc:NIFTY:1m:current` key during live development
- Useful for Phase 2 & 3 validation steps

### 5.4 REST Client (humao.rest-client)
Create `backend/api/tests.http` for manual API testing:
```http
### Health Check
GET http://localhost:8000/api/v1/health

### OHLC History
GET http://localhost:8000/api/v1/ohlc/NIFTY?timeframe=1m&limit=10

### Latest Candle
GET http://localhost:8000/api/v1/ohlc/NIFTY/latest

### Source Health
GET http://localhost:8000/api/v1/health/sources

### Symbols List
GET http://localhost:8000/api/v1/symbols
```

### 5.5 TODO Tree
Configure to highlight project-specific tags:
```json
"todo-tree.general.tags": ["TODO", "FIXME", "BLOCKED", "CHECKLIST", "PHASE"],
"todo-tree.highlights.customHighlight": {
  "BLOCKED": { "foreground": "#ff0000", "type": "text" },
  "CHECKLIST": { "foreground": "#ffaa00", "type": "text" }
}
```

### 5.6 GitHub Copilot Chat — Workspace Prompt
Add to `.github/copilot-instructions.md` (Copilot reads this automatically):
```markdown
This is a Python 3.11 FastAPI market data platform.
- Always use async/await for I/O operations
- Always use Pydantic v2 syntax (model_validator, field_validator)
- Always use Google-style docstrings
- Never hardcode URLs or credentials; use settings from backend/core/config.py
- Log using structured JSON logger, never print()
- Follow PEP 8 with 88 char line limit
- Every new adapter must implement DataSourceAdapter from backend/adapters/base.py
- Refer to BACKEND.md for schema and DESIGN.md for frontend conventions
```

---

## 6. Debugging Workflows

### 6.1 Debugging FastAPI Endpoints

1. Set a breakpoint inside the endpoint function in `backend/api/v1/ohlc.py`
2. Launch **"FastAPI: Dev Server"** from Run & Debug panel (`F5`)
3. Hit the endpoint from the REST Client file (`tests.http`) or browser
4. Inspect variables in the VS Code debug panel

**Pro tip:** Use `debugpy` for attaching to a running uvicorn process:
```bash
python -m debugpy --listen 5678 -m uvicorn backend.main:app --reload
```
Then add a `"request": "attach"` configuration in `launch.json`.

### 6.2 Debugging Adapter Failures

1. Open `backend/adapters/nse.py`
2. Add a breakpoint inside the `fetch()` method
3. Launch **"Debug: NSE Adapter (standalone)"** config
4. Inspect the HTTP response and parsed JSON in real-time

### 6.3 Debugging WebSocket

1. Open Chrome DevTools → Network → filter by WS
2. Connect to `ws://localhost:8000/api/v1/ws/ohlc/NIFTY`
3. Watch frames in real-time in the DevTools WS inspector
4. Simultaneously set breakpoint in `backend/api/v1/websocket.py`

### 6.4 Debugging Tests

1. Click the beaker icon in the VS Code sidebar to open Test Explorer
2. Navigate to the failing test
3. Click the debug icon next to the test (bug + play icon)
4. VS Code drops into the test at the failure point with full stack inspection

---

## 7. Formatting & Linting Workflow

### 7.1 On Every Save (Automatic)
- **Black** formats Python code to 88-char limit
- **isort** sorts imports (stdlib → third-party → local)
- **Prettier** formats HTML and JavaScript

### 7.2 Pre-Commit (Manual for now — CI later)
```bash
# Run before every commit
black backend/ tests/
isort backend/ tests/
flake8 backend/ --max-line-length=88
pytest tests/unit/ -x -q
```

### 7.3 Coverage Report
```bash
pytest tests/ --cov=backend --cov-report=html
# Opens htmlcov/index.html in browser
open htmlcov/index.html
```

---

## 8. Split View Layout (Recommended)

For efficient development, use VS Code's split editor:

```
┌──────────────────────────┬──────────────────────────┐
│                          │                          │
│   Implementation file    │   Spec / Reference       │
│   (e.g., nse.py)         │   (e.g., BACKEND.md)     │
│                          │                          │
├──────────────────────────┼──────────────────────────┤
│                          │                          │
│   Test file              │   CHECKLIST.md           │
│   (e.g., test_nse.py)    │   (current task)         │
│                          │                          │
└──────────────────────────┴──────────────────────────┘
                    Terminal (bottom)
              uvicorn running + pytest output
```

**Keyboard shortcuts:**
- `Ctrl+\` — split editor right
- `Ctrl+1/2/3` — focus left/center/right panel
- `Ctrl+`` `` — toggle integrated terminal
- `F5` — start debug
- `Ctrl+Shift+P` → "Tasks: Run Task" — run any task from tasks.json

---

## 9. Git Workflow in VS Code

- Use the Source Control sidebar (`Ctrl+Shift+G`) for staging
- Use GitLens for line-by-line blame during code review
- Use Git Graph extension to visualize phase branches
- Branch naming convention: `feat/phase-{N}-{short-description}`

```bash
# Start new phase
git checkout -b feat/phase-1-skeleton

# After phase complete
git tag phase-1-complete
git push origin feat/phase-1-skeleton
git push origin --tags
```

---

## 10. Environment Validation Script

Run this once after setup to confirm everything is ready:

```bash
#!/bin/bash
# save as scripts/check_env.sh

echo "=== Environment Check ==="
python --version && echo "✅ Python OK" || echo "❌ Python missing"
pip show fastapi > /dev/null && echo "✅ FastAPI installed" || echo "❌ FastAPI missing"
redis-cli ping > /dev/null && echo "✅ Redis OK" || echo "❌ Redis not running"
psql $DATABASE_URL -c "SELECT 1;" > /dev/null && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL not reachable"
python -c "import yfinance; print('✅ yfinance OK')" || echo "❌ yfinance missing"
echo "=== Done ==="
```

```bash
chmod +x scripts/check_env.sh && ./scripts/check_env.sh
```

---

*Document Owner: DevOps / Environment Lead | Last Updated: March 2026*
*Responsibility boundary: Environment, tooling, extensions, debug config only. For execution workflow → see OPENCODE.md. For code generation → see CODEX.md.*