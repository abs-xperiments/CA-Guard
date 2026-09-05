"""Comparing detection approaches on the same ledger.

The comparison this project actually needs is not "does adding a model raise a
number". Our planted anomalies are rule-shaped — round amounts, off-hours
postings, missing documents — so a model fed features derived from those same
attributes will find them, and that proves nothing.

The question worth asking is narrower:

    Does the model surface vouchers the rules missed, and were they worth it?

:func:`compare` answers it by reporting the overlap rather than only the totals.
If the model contributes nothing, that is what it will say.

Nothing here knows about planted truth. Callers pass in the sets to compare,
which is what keeps the evaluation library free of any route to the generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from caguard.detect.context import LedgerContext, build_context
from caguard.detect.model import detect_ml_anomaly
from caguard.detect.runner import flagged_vouchers, run_on_context
from caguard.detect.statistics import run_statistical_signals
from caguard.detect.types import DetectorConfig
from caguard.evaluation.metrics import Outcome, score


@dataclass(frozen=True)
class Approach:
    """One way of choosing which vouchers to review."""

    name: str
    flagged: set[str]


@dataclass
class Comparison:
    """What each approach found, and what each adds over the others."""

    total_vouchers: int
    outcomes: dict[str, Outcome] = field(default_factory=dict)
    flagged: dict[str, set[str]] = field(default_factory=dict)
    decoys_queued: dict[str, int] = field(default_factory=dict)

    def queue_share(self, name: str) -> float:
        return len(self.flagged[name]) / self.total_vouchers if self.total_vouchers else 0.0

    def unique_finds(self, name: str, versus: str) -> set[str]:
        """True positives this approach found that the other did not."""
        return self.flagged[name] - self.flagged[versus]

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "approach": name,
                    "flagged": len(self.flagged[name]),
                    "queue_share": round(self.queue_share(name), 4),
                    "recall": round(outcome.recall, 4),
                    "precision": round(outcome.precision, 4),
                    "decoys_queued": self.decoys_queued.get(name, 0),
                }
                for name, outcome in self.outcomes.items()
            ]
        )


def build_approaches(
    lines: pd.DataFrame, config: DetectorConfig | None = None
) -> tuple[LedgerContext, dict[str, set[str]]]:
    """Run each layer over one ledger and return what each would queue."""
    cfg = config or DetectorConfig()
    ctx = build_context(lines)

    rules = flagged_vouchers(run_on_context(ctx, cfg))
    stats = flagged_vouchers(run_statistical_signals(ctx, cfg))
    model = {hit.voucher_id for hit in detect_ml_anomaly(ctx, cfg)}

    return ctx, {
        "rules": rules,
        "statistics": stats,
        "model": model,
        "statistics+model": stats | model,
        "all": rules | stats | model,
    }


def compare(
    lines: pd.DataFrame,
    interesting: set[str],
    innocent: set[str] | None = None,
    config: DetectorConfig | None = None,
) -> Comparison:
    """Score every approach against the same target set.

    ``interesting`` is what should have been surfaced; ``innocent`` is what
    should not have been. Both are supplied by the caller so this module never
    needs to know how they were determined.
    """
    ctx, approaches = build_approaches(lines, config)
    innocent = innocent or set()

    result = Comparison(total_vouchers=len(ctx))
    for name, found in approaches.items():
        result.flagged[name] = found
        result.outcomes[name] = score(found, interesting)
        result.decoys_queued[name] = len(found & innocent)
    return result
