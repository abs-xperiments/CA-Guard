"""Slowing down password guessing, without a server or a dependency.

Keyed by account, not by address. Behind the workspace's own proxy every
request arrives from 127.0.0.1, so a per-address limit would let one person's
typos lock out the whole firm. Per account, it stops the attack that matters
here — someone guessing a known reviewer's password — and it costs a reviewer
who mistypes nothing until the sixth attempt.

In-process memory is enough: CA-Guard runs as one API process, and a restart
forgetting the counts is an acceptable trade for not running Redis.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

#: Failed attempts allowed inside the window before sign-in is refused.
MAX_FAILURES = 5

#: How long failures are remembered, and how long a locked account waits.
WINDOW_SECONDS = 15 * 60


@dataclass
class LoginThrottle:
    """Counts recent failed sign-ins per account."""

    max_failures: int = MAX_FAILURES
    window_seconds: float = WINDOW_SECONDS
    clock: Callable[[], float] = time.monotonic
    _failures: dict[str, list[float]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def retry_after(self, account: str) -> int:
        """Seconds until this account may try again; 0 if it may try now."""
        with self._lock:
            recent = self._recent(account)
            if len(recent) < self.max_failures:
                return 0
            return max(1, int(recent[0] + self.window_seconds - self.clock()) + 1)

    def failed(self, account: str) -> None:
        with self._lock:
            self._recent(account).append(self.clock())

    def succeeded(self, account: str) -> None:
        with self._lock:
            self._failures.pop(_key(account), None)

    def _recent(self, account: str) -> list[float]:
        cutoff = self.clock() - self.window_seconds
        key = _key(account)
        recent = [t for t in self._failures.get(key, []) if t > cutoff]
        self._failures[key] = recent
        return recent


def _key(account: str) -> str:
    return account.strip().lower()
