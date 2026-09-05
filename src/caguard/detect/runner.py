"""Running the signals over a ledger.

Signals stay independent here. Nothing in this module weighs one against
another or combines them into a score — that is Phase 4's job, and keeping the
two apart is what lets a reviewer see *which* concerns fired rather than a
single opaque number they cannot argue with.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from caguard.detect.context import LedgerContext, build_context
from caguard.detect.rules import DETECTORS
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind


def run_signals(
    lines: pd.DataFrame,
    config: DetectorConfig | None = None,
    *,
    enabled: set[SignalKind] | None = None,
) -> list[SignalHit]:
    """Run every enabled signal over canonical ledger lines.

    Results are sorted by voucher then signal so that two runs over the same
    input produce an identical list — a reviewer reopening an engagement must
    see the same queue in the same order.
    """
    cfg = config or DetectorConfig()
    context = build_context(lines)
    return run_on_context(context, cfg, enabled=enabled)


def run_on_context(
    context: LedgerContext,
    config: DetectorConfig | None = None,
    *,
    enabled: set[SignalKind] | None = None,
) -> list[SignalHit]:
    """Run signals over an already-prepared context, avoiding a second pass."""
    cfg = config or DetectorConfig()
    kinds = enabled if enabled is not None else set(DETECTORS)

    hits: list[SignalHit] = []
    for kind, detector in DETECTORS.items():
        if kind in kinds:
            hits.extend(detector(context, cfg))

    return sorted(hits, key=lambda hit: (hit.voucher_id, hit.kind.value))


def group_by_voucher(hits: list[SignalHit]) -> dict[str, list[SignalHit]]:
    """Collect hits per voucher — the unit a reviewer works in."""
    grouped: dict[str, list[SignalHit]] = defaultdict(list)
    for hit in hits:
        grouped[hit.voucher_id].append(hit)
    return dict(grouped)


def count_by_kind(hits: list[SignalHit]) -> dict[SignalKind, int]:
    """How many vouchers each signal flagged. The first thing to look at."""
    counts: dict[SignalKind, int] = dict.fromkeys(DETECTORS, 0)
    seen: set[tuple[str, SignalKind]] = set()
    for hit in hits:
        key = (hit.voucher_id, hit.kind)
        if key not in seen:
            seen.add(key)
            counts[hit.kind] += 1
    return counts


def flagged_vouchers(hits: list[SignalHit], kind: SignalKind | None = None) -> set[str]:
    """Voucher ids flagged, optionally by one signal."""
    return {h.voucher_id for h in hits if kind is None or h.kind == kind}
