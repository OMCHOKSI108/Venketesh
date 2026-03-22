# MODULE: backend/core/exceptions.py
# TASK:   CHECKLIST.md §1.4
# SPEC:   BACKEND.md §2.1
# PHASE:  1
# STATUS: In Progress

from typing import Any


class AdapterError(Exception):
    """Raised when an adapter cannot fetch or parse data.

    Edge Cases:
        - Captures optional context for structured logging and diagnostics.
    """

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize adapter error with optional context.

        Edge Cases:
            - Context can be empty, in which case details are not attached.
        """

        super().__init__(message)
        self.message = message
        self.context = context


class AllSourcesFailedError(Exception):
    """Raised when all configured adapters fail for a request.

    Edge Cases:
        - Can include per-source errors for aggregate debugging.
    """

    def __init__(self, message: str, **context: Any) -> None:
        """Initialize multi-source failure with optional context.

        Edge Cases:
            - Context remains optional for lightweight usage in early phases.
        """

        super().__init__(message)
        self.message = message
        self.context = context
