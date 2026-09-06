"""Turning one thing off at a time, to see whether it was doing anything.

Phase 3 left fusion with a hard bar: the rules alone already reach 100% recall
with no legitimate entries queued, so there is no recall left to win. What
fusion can improve is **ordering** — how much of a reviewer's finite attention
lands on something real.

The measures here are therefore about the top of the queue, not its total:

* **precision@K** — of the first K items, how many deserved the attention
* **queue compression** — how few items still hold ~95% of what matters
* **rank of the first true find** — how long before the reviewer sees anything

The ablation that matters is the evidence term. `docs/03_PATENT_AND_IP.md`
identifies evidence-gap-driven prioritisation as the one candidate mechanism the
prior-art search did not find occupied, so whether it earns its place is a real
question with a real answer, and the answer may be no.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from caguard.detect.context import build_context
from caguard.detect.types import DetectorConfig, SignalKind
from caguard.evaluation.metrics import precision_at_k
from caguard.review.fusion import build_findings

#: Review budgets a professional might realistically work through in a sitting.
BUDGETS: tuple[int, ...] = (10, 25, 50, 100)


@dataclass(frozen=True)
class QueueQuality:
    """How good one ranked queue is, from a reviewer's point of view."""

    name: str
    size: int
    precision_at: dict[int, float]
    first_hit_rank: int | None
    items_for_ninety_five: int | None
    recall: float

    def row(self) -> dict[str, object]:
        data: dict[str, object] = {"variant": self.name, "queue": self.size}
        data.update({f"p@{k}": round(v, 3) for k, v in self.precision_at.items()})
        data["first_hit"] = self.first_hit_rank
        data["items_for_95pct"] = self.items_for_ninety_five
        data["recall"] = round(self.recall, 3)
        return data


def assess(name: str, ranked: list[str], interesting: set[str]) -> QueueQuality:
    """Score a ranked list of voucher ids against the set that mattered."""
    found = [item in interesting for item in ranked]
    total = len(interesting)

    first = next((i + 1 for i, hit in enumerate(found) if hit), None)

    needed = None
    if total:
        target = 0.95 * total
        seen = 0
        for index, hit in enumerate(found, start=1):
            seen += hit
            if seen >= target:
                needed = index
                break

    return QueueQuality(
        name=name,
        size=len(ranked),
        precision_at={k: precision_at_k(ranked, interesting, k) for k in BUDGETS},
        first_hit_rank=first,
        items_for_ninety_five=needed,
        recall=sum(found) / total if total else 0.0,
    )


def compare_variants(
    lines: pd.DataFrame,
    interesting: set[str],
    config: DetectorConfig | None = None,
) -> pd.DataFrame:
    """Score fusion with and without each component it is supposed to need."""
    cfg = config or DetectorConfig()
    ctx = build_context(lines)

    variants: dict[str, dict[str, object]] = {
        "fusion (full)": {},
        "no evidence uplift": {"use_evidence": False},
        # The real test of the mechanism: remove *all* evidence information,
        # both the uplift and the rule that looks for a missing document.
        "no evidence at all": {
            "use_evidence": False,
            "drop_signals": frozenset({SignalKind.MISSING_EVIDENCE}),
        },
        "no model": {"use_model": False},
    }

    rows: list[dict[str, object]] = []
    for name, options in variants.items():
        findings = build_findings(lines, cfg, context=ctx, **options)  # pyright: ignore[reportArgumentType]
        ranked = [finding.voucher_id for finding in findings]
        rows.append(assess(name, ranked, interesting).row())

    # What a reviewer faces without any ranking: the same vouchers, in ledger
    # order. This is the baseline fusion has to beat, since Phase 3 showed the
    # rules already find everything there is to find.
    unranked = sorted(finding.voucher_id for finding in build_findings(lines, cfg, context=ctx))
    rows.append(assess("unranked (ledger order)", unranked, interesting).row())

    return pd.DataFrame(rows)
