"""Tests for evidence scoring, fusion, and the ranked review queue.

Phase 3 left a hard bar: the rules already reach 100% recall with no legitimate
entries queued, so fusion cannot win on recall. What it can improve is
**ordering** — how much of a reviewer's finite attention lands on something
real. These tests hold it to that, and to showing its working.
"""

from __future__ import annotations

import pandas as pd
import pytest

from caguard.benchmark.generator import GeneratedLedger, GeneratorConfig, generate
from caguard.detect.context import build_context
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind
from caguard.evaluation.ablation import assess, compare_variants
from caguard.review.evidence import score_evidence
from caguard.review.finding import RiskBand, band_for
from caguard.review.fusion import (
    EVIDENCE_WEIGHT,
    SIGNAL_WEIGHTS,
    build_findings,
    explain_weights,
    fuse,
)

CFG = DetectorConfig()


@pytest.fixture(scope="module")
def ledger() -> GeneratedLedger:
    return generate(GeneratorConfig(seed=101, n_vouchers=2000))


@pytest.fixture(scope="module")
def findings(ledger: GeneratedLedger):
    return build_findings(ledger.lines, CFG)


def hit(kind: SignalKind, strength: float = 1.0) -> SignalHit:
    return SignalHit(
        voucher_id="V1", kind=kind, strength=strength, reason="test", evidence={"x": 1}
    )


# --- evidence ----------------------------------------------------------------


def test_evidence_scores_a_well_supported_voucher_highly(ledger: GeneratedLedger) -> None:
    scores = score_evidence(build_context(ledger.lines), CFG)
    best = max(scores.values(), key=lambda e: e.completeness)
    assert best.completeness == pytest.approx(1.0)
    assert best.missing == []


def test_evidence_penalises_a_bare_manual_entry(ledger: GeneratedLedger) -> None:
    scores = score_evidence(build_context(ledger.lines), CFG)
    worst = min(scores.values(), key=lambda e: e.completeness)
    assert worst.completeness < 0.4
    assert "supporting document" in worst.missing


def test_a_small_unapproved_payment_is_not_an_evidence_gap(
    ledger: GeneratedLedger,
) -> None:
    """Approval is only expected above the firm's limit.

    Treating every unapproved payment as unsupported would flag most of an
    ordinary ledger — the failure mode the Phase 2 decoys exist to catch.
    """
    scores = score_evidence(build_context(ledger.lines), CFG)
    small = [e for e in scores.values() if not e.approval_expected and e.has_document]
    assert small
    assert all("approval" not in e.missing for e in small)


# --- fusion ------------------------------------------------------------------


def test_priority_stays_within_bounds() -> None:
    priority, _ = fuse([hit(k) for k in SIGNAL_WEIGHTS], None)
    assert 0.0 <= priority <= 1.0


def test_more_signals_never_lower_the_priority() -> None:
    one, _ = fuse([hit(SignalKind.ROUND_AMOUNT)], None)
    two, _ = fuse([hit(SignalKind.ROUND_AMOUNT), hit(SignalKind.DUPLICATE_ENTRY)], None)
    assert two >= one


def test_a_stronger_signal_outranks_several_weak_ones() -> None:
    """Why noisy-OR rather than a sum: weak concerns must not outvote a decisive one."""
    decisive, _ = fuse([hit(SignalKind.MISSING_EVIDENCE)], None)
    weak, _ = fuse(
        [hit(SignalKind.WEEKEND_POSTING, 0.4), hit(SignalKind.THRESHOLD_ADJACENT, 0.4)],
        None,
    )
    assert decisive > weak


def test_contributions_name_every_signal_that_counted() -> None:
    signals = [hit(SignalKind.MISSING_EVIDENCE), hit(SignalKind.ROUND_AMOUNT)]
    _, contributions = fuse(signals, None)
    assert set(contributions) == {SignalKind.MISSING_EVIDENCE, SignalKind.ROUND_AMOUNT}
    assert all(value > 0 for value in contributions.values())


def test_the_model_cannot_raise_a_voucher_on_its_own() -> None:
    """D-020, enforced in code rather than in prose.

    Phase 3 measured the model queueing legitimate entries it had no way to tell
    apart from real ones, so it may reinforce a concern but never originate one.
    """
    alone, contributions = fuse([hit(SignalKind.ML_ANOMALY)], None)
    assert alone == 0.0
    assert contributions == {}

    with_support, _ = fuse([hit(SignalKind.ML_ANOMALY), hit(SignalKind.ROUND_AMOUNT)], None)
    assert with_support > 0.0


def test_evidence_gap_lifts_priority(ledger: GeneratedLedger) -> None:
    scores = score_evidence(build_context(ledger.lines), CFG)
    unsupported = min(scores.values(), key=lambda e: e.completeness)
    supported = max(scores.values(), key=lambda e: e.completeness)

    signals = [hit(SignalKind.ROUND_AMOUNT, 0.6)]
    low, _ = fuse(signals, supported)
    high, _ = fuse(signals, unsupported)
    assert high > low
    assert high - low <= EVIDENCE_WEIGHT


@pytest.mark.parametrize(
    "priority,expected",
    [
        (0.95, RiskBand.HIGH),
        (0.70, RiskBand.HIGH),
        (0.55, RiskBand.MEDIUM),
        (0.40, RiskBand.MEDIUM),
        (0.20, RiskBand.LOW),
    ],
)
def test_risk_bands(priority: float, expected: RiskBand) -> None:
    assert band_for(priority) == expected


# --- findings ----------------------------------------------------------------


def test_findings_are_ranked_highest_first(findings) -> None:
    priorities = [f.priority for f in findings]
    assert priorities == sorted(priorities, reverse=True)


def test_every_finding_links_to_its_source_rows(findings, ledger) -> None:
    """A reviewer must be able to check the claim, not just accept it."""
    valid = set(ledger.lines.line_id)
    for finding in findings:
        assert finding.line_ids
        assert set(finding.line_ids) <= valid


def test_every_finding_shows_its_working(findings) -> None:
    for finding in findings:
        assert finding.signals
        assert finding.contributions
        assert finding.reasons
        assert finding.top_concern in finding.kinds


def test_structured_facts_carry_everything_an_explanation_may_use(findings) -> None:
    """Phase 5 may draw on this and nothing else."""
    facts = findings[0].structured_facts()
    assert set(facts) >= {
        "voucher_id",
        "amount_paise",
        "priority",
        "band",
        "evidence_completeness",
        "evidence_missing",
        "source_lines",
        "signals",
    }
    assert facts["signals"]
    assert all("reason" in s and "contribution" in s for s in facts["signals"])


def test_findings_are_deterministic(ledger: GeneratedLedger) -> None:
    first = build_findings(ledger.lines, CFG)
    second = build_findings(ledger.lines, CFG)
    assert [(f.voucher_id, f.priority) for f in first] == [
        (f.voucher_id, f.priority) for f in second
    ]


def test_a_finding_needs_at_least_one_signal(findings) -> None:
    assert all(len(f.signals) >= 1 for f in findings)


def test_weights_are_explainable() -> None:
    text = explain_weights()
    assert "missing_evidence" in text
    assert "evidence gap" in text


# --- the ordering claim ------------------------------------------------------


def test_ranking_beats_an_unordered_queue(ledger: GeneratedLedger) -> None:
    """The whole point of Phase 4.

    Recall was already 100% after Phase 2, so fusion has to earn its place on
    what a reviewer sees first.
    """
    frame = compare_variants(ledger.lines, ledger.truth.anomalous_ids).set_index("variant")
    assert frame.loc["fusion (full)", "p@25"] > frame.loc["unranked (ledger order)", "p@25"] * 2


def test_evidence_information_is_load_bearing(ledger: GeneratedLedger) -> None:
    """Removing evidence entirely must measurably hurt the queue.

    This is the mechanism `docs/03_PATENT_AND_IP.md` singles out. If it ever
    stops mattering, the IP discussion has to change and so does this test.
    """
    frame = compare_variants(ledger.lines, ledger.truth.anomalous_ids).set_index("variant")
    full, stripped = frame.loc["fusion (full)"], frame.loc["no evidence at all"]

    # Asserted on the measures that hold on every seed tested. The saving in
    # items needed to reach 95% is real on the 4,000-voucher runs recorded in
    # ADR-0006 but is not reliable at this size, so it is reported there rather
    # than asserted here.
    assert full["p@10"] > stripped["p@10"]
    assert full["p@25"] > stripped["p@25"]
    assert full["recall"] >= stripped["recall"]


def test_assess_handles_an_empty_queue() -> None:
    quality = assess("empty", [], {"V1"})
    assert quality.first_hit_rank is None
    assert quality.recall == 0.0


def test_ablation_reports_every_variant(ledger: GeneratedLedger) -> None:
    frame = compare_variants(ledger.lines, ledger.truth.anomalous_ids)
    assert set(frame.variant) == {
        "fusion (full)",
        "no evidence uplift",
        "no evidence at all",
        "no model",
        "unranked (ledger order)",
    }
    assert isinstance(frame, pd.DataFrame)
