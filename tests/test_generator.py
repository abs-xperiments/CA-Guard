"""Tests for the synthetic Indian ledger.

The centrepiece is :func:`test_planted_anomalies_are_grounded`. Phase 0 rejected
the VynFi corpus because its labels showed 0.31x-1.0x lift against the patterns
they named — the labels were decorative. This test runs that same measurement
against our own generator, so the failure mode we found in someone else's data
cannot silently appear in ours.
"""

from __future__ import annotations

import pandas as pd
import pytest

from caguard.benchmark import coa
from caguard.benchmark.anomalies import AnomalyKind, DecoyKind
from caguard.benchmark.generator import (
    GeneratedLedger,
    GeneratorConfig,
    generate,
    iter_vouchers,
)

MIN_LIFT = 5.0


@pytest.fixture(scope="module")
def vouchers(ledger: GeneratedLedger) -> pd.DataFrame:
    """Voucher-level view — the unit of review, never the line (Phase 0 finding)."""
    view = pd.DataFrame(
        ledger.lines.groupby("voucher_id").agg(
            date=("voucher_date", "first"),
            posted=("posted_at", "first"),
            amount=("debit_paise", "sum"),
            doc=("document_ref", "first"),
            approver=("approved_by", "first"),
            author=("created_by", "first"),
            post_close=("is_post_close", "first"),
            accounts=("account_code", frozenset),
        )
    )
    view["hour"] = view.posted.dt.hour
    view["weekday"] = view.date.dt.dayofweek
    return view


# Naive surface tests, one per planted kind. These are deliberately the crude
# checks a first-pass detector would use — the point is that the planted signal
# is visible to them at all.
SURFACE_TESTS = {
    AnomalyKind.ROUND_AMOUNT: lambda d: d.amount % 100_000_00 == 0,
    AnomalyKind.AFTER_HOURS_POSTING: lambda d: d.hour.between(1, 4),
    AnomalyKind.WEEKEND_POSTING: lambda d: d.weekday == 6,
    AnomalyKind.PERIOD_END_CONCENTRATION: lambda d: (
        (d.date.dt.month == 3) & (d.date.dt.day == 31) & d.doc.isna()
    ),
    AnomalyKind.THRESHOLD_ADJACENT: lambda d: d.amount.between(
        coa.APPROVAL_LIMIT_PAISE - 80_00, coa.APPROVAL_LIMIT_PAISE - 1
    ),
    AnomalyKind.MISSING_DOCUMENT_REF: lambda d: d.doc.isna(),
    AnomalyKind.POST_CLOSE_ENTRY: lambda d: d.post_close,
    AnomalyKind.RARE_ACCOUNT_PAIR: lambda d: d.accounts.map(lambda s: {"5110", "1800"} <= s),
    AnomalyKind.UNUSUAL_PREPARER_ACCOUNT: lambda d: d.apply(
        lambda r: (
            r.author in coa.PREPARER_SCOPE and not (r.accounts & coa.PREPARER_SCOPE[r.author])
        ),
        axis=1,
    ),
}


@pytest.mark.parametrize("kind", list(SURFACE_TESTS), ids=lambda k: k.value)
def test_planted_anomalies_are_grounded(
    ledger: GeneratedLedger, vouchers: pd.DataFrame, kind: AnomalyKind
) -> None:
    """Each label must correspond to a pattern actually present in the data.

    This is the exact check that disqualified VynFi. A label with no lift is a
    label that cannot be measured against, which makes the benchmark worthless.
    """
    test = SURFACE_TESTS[kind]
    ids = ledger.truth.ids_with(kind)
    assert ids, f"{kind.value} was never planted"

    labelled = test(vouchers.loc[list(ids)]).mean()
    baseline = test(vouchers).mean()
    lift = labelled / max(baseline, 1e-9)

    assert labelled == pytest.approx(1.0), (
        f"{kind.value}: only {labelled:.0%} of labelled vouchers show the pattern"
    )
    assert lift >= MIN_LIFT, f"{kind.value}: lift {lift:.1f}x is below {MIN_LIFT}x"


def test_duplicate_payments_actually_duplicate(
    ledger: GeneratedLedger, vouchers: pd.DataFrame
) -> None:
    """VynFi's duplicates duplicated *less* than baseline. Ours must duplicate more."""
    key = vouchers.amount.astype(str) + "|" + vouchers.doc.fillna("")
    is_dup = key.duplicated(keep=False) & vouchers.doc.notna()
    ids = ledger.truth.ids_with(AnomalyKind.DUPLICATE_PAYMENT)

    labelled, baseline = is_dup.loc[list(ids)].mean(), is_dup.mean()
    assert labelled == pytest.approx(1.0)
    assert labelled / baseline >= MIN_LIFT


@pytest.mark.parametrize(
    "decoy,anomaly",
    [
        (DecoyKind.LEGIT_SATURDAY_POSTING, AnomalyKind.WEEKEND_POSTING),
        (DecoyKind.LEGIT_YEAR_END_ACCRUAL, AnomalyKind.PERIOD_END_CONCENTRATION),
    ],
    ids=lambda v: v.value,
)
def test_decoys_do_not_trigger_the_matching_surface_test(
    ledger: GeneratedLedger, vouchers: pd.DataFrame, decoy: DecoyKind, anomaly: AnomalyKind
) -> None:
    """A decoy must survive the crude test, forcing a detector to look deeper."""
    ids = ledger.truth.ids_with(decoy)
    assert ids, f"{decoy.value} was never planted"
    assert SURFACE_TESTS[anomaly](vouchers.loc[list(ids)]).mean() == 0.0


def test_round_rent_decoy_is_a_real_trap(ledger: GeneratedLedger, vouchers: pd.DataFrame) -> None:
    """Rent is exactly as round as the planted anomaly.

    Only evidence and approval separate them, so a detector keying on roundness
    alone is penalised — which is the entire purpose of a decoy.
    """
    rent = vouchers.loc[list(ledger.truth.ids_with(DecoyKind.LEGIT_ROUND_RENT))]
    planted = vouchers.loc[list(ledger.truth.ids_with(AnomalyKind.ROUND_AMOUNT))]

    round_test = SURFACE_TESTS[AnomalyKind.ROUND_AMOUNT]
    assert round_test(rent).mean() == pytest.approx(1.0)
    assert round_test(planted).mean() == pytest.approx(1.0)
    assert rent.approver.notna().all()
    assert not planted.approver.notna().any()


def test_generation_is_reproducible() -> None:
    """Same seed, same content hash. Different seed, different ledger."""
    a = generate(GeneratorConfig(n_vouchers=300))
    b = generate(GeneratorConfig(n_vouchers=300))
    c = generate(GeneratorConfig(n_vouchers=300, seed=999))

    assert a.manifest["content_sha256"] == b.manifest["content_sha256"]
    assert a.manifest["content_sha256"] != c.manifest["content_sha256"]
    pd.testing.assert_frame_equal(a.lines, b.lines)


def test_every_voucher_balances_exactly(ledger: GeneratedLedger) -> None:
    """Including the anomalous ones: an irregular entry is still double entry."""
    sums = ledger.lines.groupby("voucher_id").apply(
        lambda g: int(g.debit_paise.sum() - g.credit_paise.sum()), include_groups=False
    )
    assert (sums == 0).all(), f"{(sums != 0).sum()} vouchers do not balance"


def test_anomaly_rate_stays_in_the_realistic_band(ledger: GeneratedLedger) -> None:
    """ADR-0003 rule 3: ~1-3%. A convenient 20% would flatter every metric."""
    assert 0.01 <= ledger.truth.anomaly_rate <= 0.03


def test_decoys_outnumber_anomalies(ledger: GeneratedLedger) -> None:
    """In a real ledger the innocent explanations outnumber the guilty ones."""
    assert len(ledger.truth.decoy_ids) > len(ledger.truth.anomalous_ids)


def test_every_kind_appears(ledger: GeneratedLedger) -> None:
    """Per-type recall (ADR-0003 rule 5) is only reportable if every type is present."""
    for kind in list(AnomalyKind) + list(DecoyKind):
        assert ledger.truth.ids_with(kind), f"{kind.value} missing from the ledger"


def test_anomalies_and_decoys_never_overlap(ledger: GeneratedLedger) -> None:
    assert not (ledger.truth.anomalous_ids & ledger.truth.decoy_ids)


def test_voucher_ids_do_not_leak_the_label(ledger: GeneratedLedger) -> None:
    """Vouchers are renumbered in date order.

    Anomalies are emitted before the ordinary background, so without renumbering
    the voucher number itself would predict the label and every metric would be
    inflated by a detector that learned nothing.
    """
    numbers = pd.Series([int(v.voucher_id[1:]) for v in ledger.truth.vouchers if v.is_anomalous])
    total = ledger.truth.total_vouchers
    # Planted vouchers should sit across the whole range, not bunched at the start.
    assert numbers.max() > total * 0.6
    assert numbers.mean() > total * 0.25


def test_ledger_is_recognisably_indian(ledger: GeneratedLedger) -> None:
    frame = ledger.lines
    assert (frame.currency == "INR").all()
    assert frame.fiscal_year.str.match(r"FY\d{4}-\d{2}").all()
    assert frame.posted_at.dt.hour.nunique() > 1, "posting times must carry a real hour"

    names = set(frame.account_name)
    assert any("GST" in n for n in names)
    assert any("TDS" in n for n in names)
    assert any("Sundry" in n for n in names)


def test_rejects_an_unrealistic_anomaly_rate() -> None:
    with pytest.raises(ValueError, match="ADR-0003 rule 3"):
        GeneratorConfig(anomaly_rate=0.20)


def test_iter_vouchers_groups_lines(ledger: GeneratedLedger) -> None:
    seen = dict(iter_vouchers(ledger.lines))
    assert len(seen) == ledger.truth.total_vouchers
    assert all(len(g) >= 2 for g in seen.values()), "double entry needs at least two lines"


@pytest.mark.parametrize(
    "kind", [DecoyKind.LEGIT_ROUND_RENT, DecoyKind.LEGIT_RECURRING_EMI], ids=lambda k: k.value
)
def test_monthly_decoys_occur_once_a_month(ledger: GeneratedLedger, kind: DecoyKind) -> None:
    """A monthly charge happens twelve times a year, on twelve different dates.

    Caught by reading the generated sample as a CA would: an early version put
    four rent payments on 1 April, which no practitioner would believe.
    """
    ids = ledger.truth.ids_with(kind)
    dates = (
        ledger.lines[ledger.lines.voucher_id.isin(ids)].groupby("voucher_id").voucher_date.first()
    )
    assert len(ids) == 12
    assert dates.dt.month.nunique() == 12
    assert dates.value_counts().max() == 1
