"""One command that regenerates every number this project claims.

Six phases produced measurements scattered across ADRs and journal entries. A
reader wanting to check them had to trust prose. That is not good enough for
work being written up, so the headline claims are computed here instead:

* per-signal recall, and the decoy false positives that keep it honest
* whether the model finds anything the rules missed
* what ranking does to the top of a reviewer's queue
* whether evidence information is actually load-bearing

**It reports; it does not tune.** There is no option that improves the result,
because a benchmark you can adjust is one that will be adjusted. Thresholds come
from the frozen configuration (ADR-0004, ADR-0006) and the seeds are held out
(ADR-0003 rule 4). If a number in the write-up disagrees with this output, the
write-up is wrong.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pandas as pd

from caguard.benchmark.anomalies import AnomalyKind, DecoyKind
from caguard.benchmark.generator import GeneratorConfig, generate
from caguard.detect import SignalKind, run_signals
from caguard.detect.model import MODEL_VERSION
from caguard.detect.runner import flagged_vouchers
from caguard.detect.types import DetectorConfig
from caguard.evaluation.ablation import compare_variants
from caguard.evaluation.baselines import compare
from caguard.evaluation.metrics import false_positive_rate, score
from caguard.review.fusion import EVIDENCE_WEIGHT, SIGNAL_WEIGHTS

#: Seeds never used while developing thresholds or weights (ADR-0003 rule 4).
HELD_OUT_SEEDS: tuple[int, ...] = (101, 102, 103, 104, 105)

#: Seeds that *were* used during development. Reporting on these would be
#: reporting on the answer sheet, so the runner refuses.
TUNING_SEEDS: frozenset[int] = frozenset({20250906, 1, 2, 3, 77, 999})

DEFAULT_VOUCHERS = 4000

#: Which planted anomaly each signal is responsible for finding.
RESPONSIBILITY: dict[SignalKind, AnomalyKind] = {
    SignalKind.DUPLICATE_ENTRY: AnomalyKind.DUPLICATE_PAYMENT,
    SignalKind.ROUND_AMOUNT: AnomalyKind.ROUND_AMOUNT,
    SignalKind.OFF_HOURS_POSTING: AnomalyKind.AFTER_HOURS_POSTING,
    SignalKind.WEEKEND_POSTING: AnomalyKind.WEEKEND_POSTING,
    SignalKind.PERIOD_END_CONCENTRATION: AnomalyKind.PERIOD_END_CONCENTRATION,
    SignalKind.RARE_ACCOUNT_PAIR: AnomalyKind.RARE_ACCOUNT_PAIR,
    SignalKind.THRESHOLD_ADJACENT: AnomalyKind.THRESHOLD_ADJACENT,
    SignalKind.MISSING_EVIDENCE: AnomalyKind.MISSING_DOCUMENT_REF,
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: AnomalyKind.UNUSUAL_PREPARER_ACCOUNT,
    SignalKind.POST_CLOSE_ENTRY: AnomalyKind.POST_CLOSE_ENTRY,
}

#: The legitimate look-alike built to trap each signal.
TRAP: dict[SignalKind, DecoyKind] = {
    SignalKind.DUPLICATE_ENTRY: DecoyKind.LEGIT_RECURRING_EMI,
    SignalKind.ROUND_AMOUNT: DecoyKind.LEGIT_ROUND_RENT,
    SignalKind.WEEKEND_POSTING: DecoyKind.LEGIT_SATURDAY_POSTING,
    SignalKind.PERIOD_END_CONCENTRATION: DecoyKind.LEGIT_YEAR_END_ACCRUAL,
    SignalKind.THRESHOLD_ADJACENT: DecoyKind.LEGIT_BELOW_THRESHOLD,
    SignalKind.MISSING_EVIDENCE: DecoyKind.LEGIT_SYSTEM_NO_DOCUMENT,
}


class TuningSeedError(ValueError):
    """Raised when asked to report on a seed used during development."""


@dataclass
class BenchmarkResult:
    """Everything the runner measured, ready to be written up."""

    seeds: tuple[int, ...]
    vouchers_per_seed: int
    signals: pd.DataFrame
    approaches: pd.DataFrame
    ranking: pd.DataFrame
    model_unique_finds: list[int]
    decoys_by_kind: dict[str, int]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def model_adds_nothing(self) -> bool:
        return not any(self.model_unique_finds)

    def fingerprint(self) -> str:
        """A stable digest of the numbers, so two runs can be compared at a glance."""
        import hashlib

        payload = "".join(
            frame.round(4).to_csv(index=True)
            for frame in (self.signals, self.approaches, self.ranking)
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


def run(
    seeds: tuple[int, ...] = HELD_OUT_SEEDS,
    vouchers: int = DEFAULT_VOUCHERS,
    config: DetectorConfig | None = None,
) -> BenchmarkResult:
    """Measure everything, on held-out seeds, against frozen thresholds."""
    used_for_tuning = sorted(set(seeds) & TUNING_SEEDS)
    if used_for_tuning:
        raise TuningSeedError(
            f"Seeds {used_for_tuning} were used while developing the thresholds. "
            "Reporting on them would be reporting on the answer sheet. "
            f"Held-out seeds are {list(HELD_OUT_SEEDS)}."
        )

    cfg = config or DetectorConfig()
    per_signal: dict[SignalKind, dict[str, list[float]]] = {
        signal: {"recall": [], "trap_fp": []} for signal in RESPONSIBILITY
    }
    approach_frames: list[pd.DataFrame] = []
    ranking_frames: list[pd.DataFrame] = []
    unique_finds: list[int] = []
    decoys_by_kind: dict[str, int] = {}

    for seed in seeds:
        ledger = generate(GeneratorConfig(seed=seed, n_vouchers=vouchers))
        truth = ledger.truth
        hits = run_signals(ledger.lines, cfg)

        for signal, anomaly in RESPONSIBILITY.items():
            planted = truth.ids_with(anomaly)
            found = flagged_vouchers(hits, signal)
            per_signal[signal]["recall"].append(score(found, planted).recall)
            trap = TRAP.get(signal)
            per_signal[signal]["trap_fp"].append(
                false_positive_rate(found, truth.ids_with(trap)) if trap else 0.0
            )

        comparison = compare(ledger.lines, truth.anomalous_ids, truth.decoy_ids)
        approach_frames.append(comparison.to_frame())
        unique_finds.append(len(comparison.unique_finds("model", "rules") & truth.anomalous_ids))

        by_voucher = {v.voucher_id: v for v in truth.vouchers}
        for voucher_id in comparison.flagged["model"] & truth.decoy_ids:
            kind = by_voucher[voucher_id].decoys[0].value
            decoys_by_kind[kind] = decoys_by_kind.get(kind, 0) + 1

        ranking_frames.append(compare_variants(ledger.lines, truth.anomalous_ids))

    return BenchmarkResult(
        seeds=tuple(seeds),
        vouchers_per_seed=vouchers,
        signals=_signal_frame(per_signal),
        approaches=_mean_by(pd.concat(approach_frames), "approach"),
        ranking=_mean_by(pd.concat(ranking_frames), "variant"),
        model_unique_finds=unique_finds,
        decoys_by_kind=dict(sorted(decoys_by_kind.items(), key=lambda kv: -kv[1])),
    )


def _signal_frame(measured: dict[SignalKind, dict[str, list[float]]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal": signal.value,
                "mean_recall": round(statistics.mean(values["recall"]), 4),
                "min_recall": round(min(values["recall"]), 4),
                "trap_false_positives": round(sum(values["trap_fp"]), 4),
                "weight": SIGNAL_WEIGHTS.get(signal, 0.0),
            }
            for signal, values in measured.items()
        ]
    ).set_index("signal")


def _mean_by(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    numeric = frame.select_dtypes("number").columns
    return pd.DataFrame(frame.groupby(key, sort=False)[list(numeric)].mean()).round(4)


def as_markdown(result: BenchmarkResult) -> str:
    """The results, formatted for `docs/RESULTS.md`."""
    stamp = result.generated_at.strftime("%Y-%m-%d %H:%M UTC")
    ranking = result.ranking
    full = ranking.loc["fusion (full)"]
    unranked = ranking.loc["unranked (ledger order)"]
    stripped = ranking.loc["no evidence at all"]

    precision_gain = f"{unranked['p@25']:.0%} unranked → {full['p@25']:.0%} ranked"
    effort_saved = f"{unranked['items_for_95pct']:.0f} → {full['items_for_95pct']:.0f} vouchers"

    return f"""# Results

Regenerated by `caguard benchmark` on {stamp}.
**Do not edit by hand.** If a number here disagrees with the runner, the runner is right.

- Held-out seeds: `{list(result.seeds)}` — never used while developing thresholds or weights
- Ledger size: {result.vouchers_per_seed:,} vouchers per seed, ~2% planted anomalies, ~5% decoys
- Detector thresholds: frozen in ADR-0004 · Fusion weights: frozen in ADR-0006
- Model: `{MODEL_VERSION}` · Evidence uplift: {EVIDENCE_WEIGHT}
- Fingerprint: `{result.fingerprint()}`

## 1. The ten deterministic signals

Each signal is measured twice: does it find the anomalies planted for it, and does
it fall for the legitimate look-alike built to trap it. Recall alone is worthless —
a detector that flags everything scores 100% and is unusable.

{_markdown_table(result.signals)}

**Trap false positives across every seed: {int(result.signals.trap_false_positives.sum())}.**

## 2. Does the model add anything?

{_markdown_table(result.approaches)}

Anomalies the model found that the rules missed, per seed: `{result.model_unique_finds}`.

{_model_verdict(result)}

What it queued instead — legitimate entries, across all seeds:

{_decoy_table(result.decoys_by_kind)}

Every one of those is statistically unusual and entirely proper. What makes them
legitimate is a lease, a bank mandate or an approval — none of which is in the
numbers. Statistical unusualness is not audit relevance.

## 3. What ranking does to a reviewer's queue

Recall was already complete after the deterministic signals, so fusion has to earn
its place on what a reviewer sees *first*.

{_markdown_table(ranking)}

- Precision in the first 25 items: **{precision_gain}**
- Work to reach 95% of the findings: **{effort_saved}**

## 4. Is the evidence gap load-bearing?

Removing evidence information entirely — both the uplift and the missing-document
rule — against the full model:

| | Full | No evidence at all |
|---|---|---|
| Precision @10 | {full["p@10"]:.0%} | {stripped["p@10"]:.0%} |
| Precision @25 | {full["p@25"]:.0%} | {stripped["p@25"]:.0%} |
| Items to reach 95% | {full["items_for_95pct"]:.0f} | {stripped["items_for_95pct"]:.0f} |
| Recall | {full["recall"]:.1%} | {stripped["recall"]:.1%} |

This is the mechanism `docs/03_PATENT_AND_IP.md` singles out. It remains a
**candidate**, not a novelty claim.

## Honest limits

1. **Synthetic data.** No real Indian ledger has been evaluated. The external CA
   review in `docs/ca_validation/` is still outstanding.
2. **The anomalies are rule-shaped**, because the same project wrote the rules and
   the planting. This is not evidence that unsupervised detection is useless on
   real books — see ADR-0005.
3. **One generator.** Every result rests on the benchmark in `caguard/benchmark`,
   whose integrity rules are in ADR-0003.
"""


def _markdown_table(frame: pd.DataFrame) -> str:
    """A markdown table, without pulling in a dependency to draw one.

    ``DataFrame.to_markdown`` needs ``tabulate``, which is a package added purely
    to place pipe characters. Ten lines here costs less than a dependency.
    """
    index_name = frame.index.name or ""
    headers = [index_name, *(str(column) for column in frame.columns)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for label, row in frame.iterrows():
        cells = [str(label)]
        for value in row:
            cells.append(f"{value:.4g}" if isinstance(value, (int, float)) else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _model_verdict(result: BenchmarkResult) -> str:
    if result.model_adds_nothing:
        return "**The model found nothing the rules missed, on any seed.**"
    return "**The model found anomalies the rules missed — ADR-0005 must be revisited.**"


def _decoy_table(counts: dict[str, int]) -> str:
    if not counts:
        return "_The model queued no legitimate entries._"
    rows = "\n".join(f"| {count} | `{kind}` |" for kind, count in counts.items())
    return f"| Count | Legitimate entry |\n|---|---|\n{rows}"
