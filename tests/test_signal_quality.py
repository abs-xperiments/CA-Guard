"""The two-sided bar: does each signal find its pattern, and does it leave the decoys alone?

Recall alone is worthless here. A detector that flagged every round number and
every 31 March entry would score 100% and be unusable in a practice, because a
CA would spend the first morning dismissing false alarms. So every signal is
measured against both the anomalies planted for it and the legitimate look-alike
built to trap it.

Floors are set from principle, not from what was observed. A floor tuned to the
measured number is a floor tuned to this benchmark.
"""

from __future__ import annotations

import pytest

from caguard.benchmark.anomalies import AnomalyKind, DecoyKind
from caguard.benchmark.generator import GeneratedLedger, GeneratorConfig, generate
from caguard.detect import SignalKind, run_signals
from caguard.detect.runner import flagged_vouchers
from caguard.evaluation.metrics import false_positive_rate, precision_at_k, score

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

#: The legitimate entry built to trap each signal. Flagging one is a false positive.
TRAP: dict[SignalKind, DecoyKind] = {
    SignalKind.DUPLICATE_ENTRY: DecoyKind.LEGIT_RECURRING_EMI,
    SignalKind.ROUND_AMOUNT: DecoyKind.LEGIT_ROUND_RENT,
    SignalKind.WEEKEND_POSTING: DecoyKind.LEGIT_SATURDAY_POSTING,
    SignalKind.PERIOD_END_CONCENTRATION: DecoyKind.LEGIT_YEAR_END_ACCRUAL,
    SignalKind.THRESHOLD_ADJACENT: DecoyKind.LEGIT_BELOW_THRESHOLD,
    SignalKind.MISSING_EVIDENCE: DecoyKind.LEGIT_SYSTEM_NO_DOCUMENT,
}

#: Recall floors. The rule-shaped signals are definitional — the pattern is
#: either present or it is not — so they must find all of it. The two that
#: depend on the surrounding population get a lower floor, set well below the
#: observed minimum on purpose.
RECALL_FLOOR: dict[SignalKind, float] = dict.fromkeys(RESPONSIBILITY, 1.0) | {
    SignalKind.RARE_ACCOUNT_PAIR: 0.75,
    # Observed 90% mean / 75% worst seed. The floor sits below that on purpose:
    # this signal needs the account to have a clear regular owner, and not every
    # account in a real ledger does. A floor pinned to the observed minimum would
    # be a floor tuned to this benchmark, and would break on the next seed.
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: 0.60,
}

#: Seeds never used while developing the thresholds (ADR-0003 rule 4, ADR-0004).
HELD_OUT_SEEDS = (101, 102, 103)


@pytest.fixture(scope="module", params=HELD_OUT_SEEDS, ids=lambda s: f"seed{s}")
def held_out(request: pytest.FixtureRequest) -> GeneratedLedger:
    return generate(GeneratorConfig(seed=request.param, n_vouchers=2000))


@pytest.fixture(scope="module")
def hits(held_out: GeneratedLedger) -> list:
    return run_signals(held_out.lines)


@pytest.mark.parametrize("signal", list(RESPONSIBILITY), ids=lambda s: s.value)
def test_signal_finds_what_it_is_responsible_for(
    held_out: GeneratedLedger, hits: list, signal: SignalKind
) -> None:
    planted = held_out.truth.ids_with(RESPONSIBILITY[signal])
    assert planted, f"{signal.value} has nothing planted to find"

    outcome = score(flagged_vouchers(hits, signal), planted)
    assert outcome.recall >= RECALL_FLOOR[signal], (
        f"{signal.value}: {outcome} — below its floor of {RECALL_FLOOR[signal]:.0%}"
    )


@pytest.mark.parametrize("signal", list(TRAP), ids=lambda s: s.value)
def test_signal_does_not_fall_for_its_trap(
    held_out: GeneratedLedger, hits: list, signal: SignalKind
) -> None:
    """The decoy exists specifically to catch this signal being naive."""
    innocent = held_out.truth.ids_with(TRAP[signal])
    assert innocent, f"{TRAP[signal].value} was never planted"

    rate = false_positive_rate(flagged_vouchers(hits, signal), innocent)
    assert rate == 0.0, (
        f"{signal.value} flagged {rate:.0%} of {TRAP[signal].value}, which is legitimate"
    )


def test_no_decoy_reaches_the_queue_by_any_route(held_out: GeneratedLedger, hits: list) -> None:
    """Stricter than the per-signal trap test.

    A decoy caught by some *other* signal is still a legitimate voucher landing
    on a reviewer's desk, so the queue as a whole is measured too.
    """
    wrongly_queued = flagged_vouchers(hits) & held_out.truth.decoy_ids
    assert not wrongly_queued, (
        f"{len(wrongly_queued)} legitimate vouchers were queued: {sorted(wrongly_queued)[:5]}"
    )


def test_the_queue_is_small_enough_to_review(held_out: GeneratedLedger, hits: list) -> None:
    """A queue that is a third of the ledger has not prioritised anything."""
    share = len(flagged_vouchers(hits)) / held_out.truth.total_vouchers
    assert share <= 0.10, f"queue is {share:.1%} of the ledger — too large to be a queue"


def test_the_queue_contains_almost_every_planted_anomaly(
    held_out: GeneratedLedger, hits: list
) -> None:
    outcome = score(flagged_vouchers(hits), held_out.truth.anomalous_ids)
    assert outcome.recall >= 0.90, f"queue-level recall {outcome}"


def test_top_of_the_queue_is_worth_a_reviewer_s_time(held_out: GeneratedLedger, hits: list) -> None:
    """A reviewer works down a finite list; the top of it must earn the attention."""
    ranked = sorted(
        flagged_vouchers(hits),
        key=lambda v: -sum(h.strength for h in hits if h.voucher_id == v),
    )
    assert precision_at_k(ranked, held_out.truth.anomalous_ids, 25) >= 0.5


def test_signals_are_reported_separately_not_blended(hits: list) -> None:
    """ADR-0003 rule 5: a single number that hides which signal failed is not a result."""
    assert len({h.kind for h in hits}) > 1
    assert all(h.kind in RESPONSIBILITY for h in hits)
