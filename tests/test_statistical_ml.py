"""Tests for the statistical layer, the model, and the baseline comparison.

The comparison test is the point of the phase. Our planted anomalies are
rule-shaped, so a model fed features derived from those same attributes will
find them and prove nothing. What these tests pin down is the honest finding:
on this benchmark the model surfaces **nothing the rules missed**, and it queues
legitimate entries that are statistically unusual but perfectly proper.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from caguard.benchmark.generator import GeneratedLedger, GeneratorConfig, generate
from caguard.detect.context import build_context
from caguard.detect.features import FEATURE_NAMES, amount_deviation, build_features
from caguard.detect.model import MODEL_VERSION, detect_ml_anomaly, score_ledger
from caguard.detect.statistics import (
    BENFORD_EXPECTED,
    benford_by_account,
    benford_frame,
    run_statistical_signals,
)
from caguard.detect.types import DetectorConfig, SignalKind
from caguard.evaluation.baselines import build_approaches, compare

CFG = DetectorConfig()


@pytest.fixture(scope="module")
def ledger_101() -> GeneratedLedger:
    return generate(GeneratorConfig(seed=101, n_vouchers=2000))


@pytest.fixture(scope="module")
def ctx(ledger_101: GeneratedLedger):
    return build_context(ledger_101.lines)


# --- features ----------------------------------------------------------------


def test_feature_columns_are_pinned(ctx) -> None:
    """Order is part of the contract: a model score means nothing without it."""
    assert list(build_features(ctx).columns) == list(FEATURE_NAMES)


def test_features_are_finite(ctx) -> None:
    frame = build_features(ctx)
    assert not frame.isna().to_numpy().any()
    assert np.isfinite(frame.to_numpy()).all()


def test_features_are_deterministic(ctx) -> None:
    pd.testing.assert_frame_equal(build_features(ctx), build_features(ctx))


def test_features_contain_nothing_from_the_ground_truth(ctx) -> None:
    """No feature may encode how the data was planted (ADR-0003 rule 1)."""
    forbidden = {"anomaly", "decoy", "truth", "label", "planted", "fraud"}
    for name in FEATURE_NAMES:
        assert not any(word in name.lower() for word in forbidden)


def test_amount_deviation_uses_the_account_as_its_baseline(ctx) -> None:
    """A large machinery purchase is ordinary on Plant & Machinery."""
    deviation = amount_deviation(ctx)
    assert (deviation >= 0).all()
    assert deviation.max() > 0


# --- Benford -----------------------------------------------------------------


def test_benford_expected_matches_the_law() -> None:
    assert BENFORD_EXPECTED[0] == pytest.approx(0.301, abs=0.001)
    assert sum(BENFORD_EXPECTED) == pytest.approx(1.0, abs=1e-9)


def test_benford_is_reported_per_account_not_per_voucher(ctx) -> None:
    """A single number has no distribution, so a single voucher cannot violate Benford."""
    results = benford_by_account(ctx)
    assert results
    assert all(r.sample_size >= CFG.benford_min_sample for r in results)
    assert len({r.account_code for r in results}) == len(results)


def test_benford_ignores_accounts_with_too_few_entries(ctx) -> None:
    strict = benford_by_account(ctx, DetectorConfig(benford_min_sample=10_000))
    assert strict == []


def test_benford_conformity_labels_are_ordered(ctx) -> None:
    results = benford_by_account(ctx)
    assert results == sorted(results, key=lambda r: -r.mad)
    assert set(benford_frame(results).conformity) <= {
        "close",
        "acceptable",
        "marginal",
        "non-conforming",
    }


# --- amount outlier ----------------------------------------------------------


def test_amount_outlier_fires_on_a_within_account_outlier(ctx) -> None:
    hits = run_statistical_signals(ctx, CFG)
    assert hits
    assert {h.kind for h in hits} == {SignalKind.AMOUNT_OUTLIER}
    assert all(h.evidence["robust_deviations"] >= CFG.amount_deviation_threshold for h in hits)


def test_amount_outlier_respects_its_threshold(ctx) -> None:
    lenient = run_statistical_signals(ctx, DetectorConfig(amount_deviation_threshold=3.0))
    strict = run_statistical_signals(ctx, DetectorConfig(amount_deviation_threshold=20.0))
    assert len(lenient) >= len(strict)


# --- model -------------------------------------------------------------------


def test_model_scores_are_deterministic(ctx) -> None:
    """A reviewer reopening an engagement must see the same queue."""
    first, second = score_ledger(ctx, CFG), score_ledger(ctx, CFG)
    pd.testing.assert_series_equal(first.scores, second.scores)
    assert first.version == MODEL_VERSION


def test_model_flags_about_the_contamination_share(ctx) -> None:
    """Contamination is set from the review budget, never from the planted rate."""
    hits = detect_ml_anomaly(ctx, CFG)
    share = len(hits) / len(ctx)
    assert 0.005 <= share <= 0.05


def test_model_hits_name_what_drove_them(ctx) -> None:
    """A bare score is not reviewable, and Phase 5 may explain only from evidence."""
    for hit in detect_ml_anomaly(ctx, CFG):
        assert hit.evidence["model_version"] == MODEL_VERSION
        assert hit.evidence["top_features"]
        assert set(hit.evidence["top_features"]) <= set(FEATURE_NAMES)


# --- the comparison that matters ---------------------------------------------


def test_every_approach_runs(ledger_101: GeneratedLedger) -> None:
    _, approaches = build_approaches(ledger_101.lines, CFG)
    assert set(approaches) == {"rules", "statistics", "model", "statistics+model", "all"}


def test_rules_outperform_the_model_on_this_benchmark(
    ledger_101: GeneratedLedger,
) -> None:
    """Recorded as a fact about the benchmark, not as a claim about ML generally.

    The planted anomalies are rule-shaped by construction, so the rules have
    every advantage here. The value of stating it is that it stops anyone
    reading the fusion results in Phase 4 as evidence the model contributed.
    """
    result = compare(ledger_101.lines, ledger_101.truth.anomalous_ids, ledger_101.truth.decoy_ids)
    assert result.outcomes["rules"].recall > result.outcomes["model"].recall


def test_the_model_finds_nothing_the_rules_missed(ledger_101: GeneratedLedger) -> None:
    """The honest question this phase exists to answer.

    If the model ever does surface a planted anomaly the rules missed, this test
    fails and the finding should be written up — it would be the first evidence
    the model earns its place.
    """
    result = compare(ledger_101.lines, ledger_101.truth.anomalous_ids, ledger_101.truth.decoy_ids)
    unique = result.unique_finds("model", "rules") & ledger_101.truth.anomalous_ids
    assert not unique, (
        f"the model found {len(unique)} anomalies the rules missed — "
        "re-run the baseline comparison and update the write-up"
    )


def test_the_model_queues_legitimate_entries_and_the_rules_do_not(
    ledger_101: GeneratedLedger,
) -> None:
    """The core finding of this phase.

    Round rent, a fixed monthly instalment and auto-posted bank charges are all
    statistically unusual and all entirely proper. An unsupervised model cannot
    tell the difference, because the difference lies in evidence and business
    context rather than in the numbers.
    """
    result = compare(ledger_101.lines, ledger_101.truth.anomalous_ids, ledger_101.truth.decoy_ids)
    assert result.decoys_queued["rules"] == 0
    assert result.decoys_queued["model"] > 0


def test_comparison_frame_reports_every_approach(ledger_101: GeneratedLedger) -> None:
    frame = compare(ledger_101.lines, ledger_101.truth.anomalous_ids).to_frame()
    assert len(frame) == 5
    assert set(frame.columns) == {
        "approach",
        "flagged",
        "queue_share",
        "recall",
        "precision",
        "decoys_queued",
    }


def test_model_reasons_avoid_developer_language(ctx) -> None:
    """A reviewer must never be shown a variable name.

    "the largest differences are in has_evidence, evidence_coverage" means
    something to us and nothing to a CA, and a finding that reads like a
    variable dump undermines everything around it.
    """

    for hit in detect_ml_anomaly(ctx, CFG):
        for raw in FEATURE_NAMES:
            assert raw not in hit.reason, f"{raw!r} leaked into: {hit.reason}"
        assert "_" not in hit.reason.replace("CA-Guard", "")


def test_every_feature_has_a_readable_name() -> None:
    from caguard.detect.model import FEATURE_LABELS, describe_feature

    assert set(FEATURE_LABELS) == set(FEATURE_NAMES)
    assert describe_feature("unknown_thing") == "unknown thing"
