# Copilot Chat Session Starter

Paste this at the start of each implementation task in Copilot Chat.

## Template
I am working on CHECKLIST.md \u00a7[SECTION] - [TASK NAME] - Phase [N].

Current task spec:
[Paste the full task block from plan/checklist.md including the
Validation step]

Relevant spec excerpt:
[Paste 5-10 lines from docs/BACKEND.md or docs/DESIGN.md relevant to
this task]

Rules for this session:
- Generate complete, runnable Python/JS - no stubs, no TODOs
- PEP 8, max 88 chars, type hints on all signatures
- Google-style docstrings with Edge Cases section
- async def for all I/O
- No print(); use logger = logging.getLogger(__name__)
- No hardcoded config; use settings from backend/core/config.py
- Add module header block at top of every new file (OPENCODE.md
  section 4 step 3)

After you generate the code, I will run the Validation step and report
results.
If validation fails, I will paste the error and you will fix only the
failing part.

Generate [file path] now.
