"""Combining independent signals into one priority, transparently.

**Why noisy-OR and not a weighted sum.** A sum lets three weak concerns outrank
one decisive concern, and it runs past 1 without meaning anything. Noisy-OR —
``1 − Π(1 − wₖ·sₖ)`` — treats each signal as an independent piece of evidence,
stays inside [0, 1], and reads plainly: the chance that at least one of these
concerns is real. It also has the right shape for review work — a second weak
signal adds something, but far less than the first strong one.

**Why the evidence gap enters separately.** It is not another anomaly signal; it
is a statement about whether a transaction can be supported at all. An
ordinary-looking entry with nothing behind it deserves attention, and no
statistical signal will ever say so. This is the mechanism `docs/03_PATENT_AND_IP.md`
identifies as the one worth a professional's review — and Phase 4 is where it
becomes testable rather than asserted.

Weights are frozen in ADR-0006 and committed before any held-out scoring.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from caguard.detect.context import LedgerContext, build_context
from caguard.detect.model import detect_ml_anomaly
from caguard.detect.runner import run_on_context
from caguard.detect.statistics import run_statistical_signals
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind
from caguard.review.evidence import EvidenceScore, score_evidence
from caguard.review.finding import Finding, band_for

#: How much each signal is trusted. Set from measured behaviour, not intuition:
#: `threshold_adjacent` sits low because Phase 3 measured its precision at about
#: 5%, and `ml_anomaly` lowest of all because it found nothing the rules missed
#: while queueing legitimate entries (ADR-0005, D-020).
SIGNAL_WEIGHTS: dict[SignalKind, float] = {
    SignalKind.MISSING_EVIDENCE: 0.90,
    SignalKind.DUPLICATE_ENTRY: 0.85,
    SignalKind.PERIOD_END_CONCENTRATION: 0.80,
    SignalKind.POST_CLOSE_ENTRY: 0.75,
    SignalKind.RARE_ACCOUNT_PAIR: 0.70,
    SignalKind.OFF_HOURS_POSTING: 0.65,
    SignalKind.ROUND_AMOUNT: 0.60,
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: 0.60,
    SignalKind.WEEKEND_POSTING: 0.50,
    SignalKind.AMOUNT_OUTLIER: 0.40,
    SignalKind.THRESHOLD_ADJACENT: 0.35,
    SignalKind.ML_ANOMALY: 0.15,
}

#: How much a completely unsupported voucher is lifted. Applied to the headroom
#: left by the signals, so it sharpens the ordering rather than flattening it.
EVIDENCE_WEIGHT = 0.45

#: Signals that may not raise a voucher on their own (D-020). The model queued
#: legitimate entries it had no way to distinguish from real ones, so it is
#: allowed to reinforce a concern but never to originate one.
REQUIRES_CORROBORATION: frozenset[SignalKind] = frozenset({SignalKind.ML_ANOMALY})


def fuse(
    hits: list[SignalHit],
    evidence: EvidenceScore | None = None,
    *,
    use_evidence: bool = True,
) -> tuple[float, dict[SignalKind, float]]:
    """Combine one voucher's signals into a priority and a per-signal breakdown.

    Returns the priority and how much each signal contributed to it, so the
    number is never presented without its working.
    """
    usable = _corroborated(hits)
    if not usable:
        return 0.0, {}

    strongest: dict[SignalKind, float] = {}
    for hit in usable:
        weighted = SIGNAL_WEIGHTS.get(hit.kind, 0.0) * hit.strength
        strongest[hit.kind] = max(strongest.get(hit.kind, 0.0), weighted)

    survival = 1.0
    for weighted in strongest.values():
        survival *= 1.0 - min(weighted, 1.0)
    base = 1.0 - survival

    priority = base
    contributions = dict(strongest)
    if use_evidence and evidence is not None:
        # Applied to the headroom, so a voucher already near certainty is not
        # pushed past 1 and an ordinary-looking one with no support still rises.
        uplift = EVIDENCE_WEIGHT * evidence.gap * (1.0 - base)
        priority = base + uplift
        if uplift > 0:
            contributions["evidence_gap"] = round(uplift, 4)  # type: ignore[index]

    return min(max(priority, 0.0), 1.0), contributions


def build_findings(
    lines: pd.DataFrame,
    config: DetectorConfig | None = None,
    *,
    use_evidence: bool = True,
    use_model: bool = True,
    drop_signals: frozenset[SignalKind] = frozenset(),
    context: LedgerContext | None = None,
) -> list[Finding]:
    """Run every layer over a ledger and produce a ranked review queue.

    ``use_evidence`` and ``use_model`` exist so the ablation in
    :mod:`caguard.evaluation.ablation` can turn one thing off at a time.
    """
    cfg = config or DetectorConfig()
    ctx = context if context is not None else build_context(lines)

    hits = run_on_context(ctx, cfg) + run_statistical_signals(ctx, cfg)
    if use_model:
        hits += detect_ml_anomaly(ctx, cfg)
    if drop_signals:
        hits = [hit for hit in hits if hit.kind not in drop_signals]

    grouped: dict[str, list[SignalHit]] = defaultdict(list)
    for hit in hits:
        grouped[hit.voucher_id].append(hit)

    evidence = score_evidence(ctx, cfg)
    line_index = _lines_by_voucher(lines)

    findings: list[Finding] = []
    for voucher_id, voucher_hits in grouped.items():
        score = evidence.get(voucher_id)
        priority, contributions = fuse(voucher_hits, score, use_evidence=use_evidence)
        if priority <= 0.0 or score is None:
            continue

        row = ctx.vouchers.loc[voucher_id]
        findings.append(
            Finding(
                voucher_id=voucher_id,
                priority=round(priority, 6),
                band=band_for(priority),
                signals=tuple(sorted(voucher_hits, key=lambda h: h.kind.value)),
                evidence=score,
                contributions=contributions,
                line_ids=line_index.get(voucher_id, ()),
                amount_paise=int(row.amount_paise),
                voucher_date=str(row.voucher_date.date()),
            )
        )

    # Highest priority first; voucher id breaks ties so the order is stable.
    return sorted(findings, key=lambda f: (-f.priority, f.voucher_id))


def _corroborated(hits: list[SignalHit]) -> list[SignalHit]:
    """Drop signals that are not allowed to stand alone (D-020)."""
    kinds = {hit.kind for hit in hits}
    if kinds <= REQUIRES_CORROBORATION:
        return []
    return hits


def _lines_by_voucher(lines: pd.DataFrame) -> dict[str, tuple[str, ...]]:
    """Source-row linkage: every finding must point back at real ledger lines."""
    if "line_id" not in lines.columns:
        return {}
    grouped = lines.groupby("voucher_id").line_id.apply(lambda s: tuple(sorted(s)))
    return {str(k): v for k, v in grouped.items()}


def explain_weights() -> str:
    """The weight table, for the CLI and for anyone asking why something ranks."""
    rows = sorted(SIGNAL_WEIGHTS.items(), key=lambda item: -item[1])
    body = "\n".join(f"  {kind.value:28s} {weight:.2f}" for kind, weight in rows)
    return f"{body}\n  {'evidence gap (uplift)':28s} {EVIDENCE_WEIGHT:.2f}"
