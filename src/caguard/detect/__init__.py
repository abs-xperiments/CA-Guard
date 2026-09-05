"""Deterministic audit-review signals.

Everything here works from the uploaded ledger alone. No module in this package
may import :mod:`caguard.benchmark` — enforced strictly, with no allowlist, by
``tests/test_isolation.py``. A detector that could see how the benchmark was
planted would be scored against knowledge it will never have on a real client's
books.

Signals are independent by design. Combining them into a single priority score
is Phase 4's job; keeping them separate here is what lets a reviewer see *which*
concerns fired, rather than an opaque number.
"""

from caguard.detect.runner import run_signals
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind

__all__ = ["DetectorConfig", "SignalHit", "SignalKind", "run_signals"]
