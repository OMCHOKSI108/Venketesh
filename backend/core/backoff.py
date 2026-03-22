# MODULE: backend/core/backoff.py
# TASK:   CHECKLIST.md §4.2 Exponential Backoff
# SPEC:   BACKEND.md §7.1 (Data Source Security)
# PHASE:  4
# STATUS: In Progress

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ExponentialBackoff:
    """Exponential backoff for retry logic.

    Edge Cases:
        - Caps at max_wait seconds to avoid excessive delays.
        - Resets attempt count on successful operation.
    """

    def __init__(
        self,
        base_wait: float = 1.0,
        max_wait: float = 60.0,
        max_retries: int = 5,
    ) -> None:
        self.base_wait = base_wait
        self.max_wait = max_wait
        self.max_retries = max_retries
        self._attempt = 0

    @property
    def attempt(self) -> int:
        """Current attempt number."""
        return self._attempt

    def reset(self) -> None:
        """Reset attempt counter."""
        self._attempt = 0

    async def wait(self, attempt: Optional[int] = None) -> float:
        """Wait for exponential backoff period.

        Args:
            attempt: Optional override for current attempt number

        Returns:
            Number of seconds waited
        """
        if attempt is not None:
            self._attempt = attempt

        wait_time = min(self.base_wait * (2**self._attempt), self.max_wait)
        self._attempt += 1

        logger.debug(
            "backoff_wait",
            extra={
                "attempt": self._attempt,
                "wait_seconds": wait_time,
            },
        )

        await asyncio.sleep(wait_time)
        return wait_time

    def should_retry(self, attempt: Optional[int] = None) -> bool:
        """Check if more retries should be attempted."""
        check_attempt = attempt if attempt is not None else self._attempt
        return check_attempt < self.max_retries
