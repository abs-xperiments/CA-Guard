"""Unit tests for the signals: each must fire on the pattern and stay silent otherwise.

These are hand-built ledgers, deliberately tiny, so a failure points at one rule
rather than at the benchmark. The population-level measurements live in
``test_signal_quality.py``.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from caguard.detect import DetectorConfig, SignalKind, run_signals
from caguard.detect.context import build_context
from caguard.detect.rules import DETECTORS
from caguard.detect.runner import count_by_kind, flagged_vouchers, group_by_voucher
from caguard.schema import AccountGroup, TimeFidelity, VoucherType

CFG = DetectorConfig()


def voucher(
    voucher_id: str,
    *,
    amount: int = 100_000_00,
    date: str = "2024-06-12",
    posted: str | None = None,
    debit: str = "5900",
    credit: str = "2000",
    by: str = "dshah",
    approver: str | None = "iyer.cfo",
    doc: str | None = "JV/24-25/0001",
    manual: bool = True,
    post_close: bool = False,
) -> list[dict[str, object]]:
    """Two canonical lines forming one balanced voucher."""
    stamp = pd.Timestamp(posted or f"{date} 11:30:00")
    common: dict[str, object] = {
        "voucher_id": voucher_id,
        "entity_id": "ACME-IN",
        "fiscal_year": "FY2024-25",
        "period": 3,
        "voucher_date": pd.Timestamp(date),
        "posted_at": stamp,
        "time_fidelity": TimeFidelity.DATE_AND_TIME.value,
        "voucher_type": VoucherType.JOURNAL.value,
        "account_group": AccountGroup.EXPENSE.value,
        "currency": "INR",
        "created_by": by,
        "approved_by": approver,
        "document_ref": doc,
        "narration": "Test entry",
        "cost_centre": None,
        "is_manual": manual,
        "is_post_close": post_close,
    }
    return [
        {
            **common,
            "line_id": f"{voucher_id}-01",
            "line_number": 1,
            "account_code": debit,
            "account_name": f"Account {debit}",
            "debit_paise": amount,
            "credit_paise": 0,
        },
        {
            **common,
            "line_id": f"{voucher_id}-02",
            "line_number": 2,
            "account_code": credit,
            "account_name": f"Account {credit}",
            "debit_paise": 0,
            "credit_paise": amount,
        },
    ]


def ledger(*vouchers: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame([row for v in vouchers for row in v])


def fired(frame: pd.DataFrame, kind: SignalKind) -> set[str]:
    return flagged_vouchers(run_signals(frame, CFG, enabled={kind}), kind)


# --- duplicates --------------------------------------------------------------


def test_duplicate_fires_within_the_window() -> None:
    frame = ledger(
        voucher("V1", date="2024-06-10"),
        voucher("V2", date="2024-06-13"),
    )
    assert fired(frame, SignalKind.DUPLICATE_ENTRY) == {"V2"}


def test_duplicate_ignores_a_monthly_recurrence() -> None:
    """A loan instalment repeats identically by contract; that is not duplication."""
    frame = ledger(
        voucher("V1", date="2024-06-10"),
        voucher("V2", date="2024-07-10"),
        voucher("V3", date="2024-08-10"),
    )
    assert fired(frame, SignalKind.DUPLICATE_ENTRY) == set()


# --- round amounts -----------------------------------------------------------


def test_round_amount_fires_on_a_one_off() -> None:
    frame = ledger(voucher("V1", amount=5_00_000_00))
    assert fired(frame, SignalKind.ROUND_AMOUNT) == {"V1"}


def test_round_amount_ignores_a_recurring_contractual_figure() -> None:
    """Rent is round because the lease fixed it, and it recurs."""
    frame = ledger(
        *[
            voucher(f"V{i}", amount=2_00_000_00, date=f"2024-0{i}-05", debit="5200")
            for i in range(1, 5)
        ]
    )
    assert fired(frame, SignalKind.ROUND_AMOUNT) == set()


def test_round_amount_ignores_small_amounts() -> None:
    assert fired(ledger(voucher("V1", amount=10_000_00)), SignalKind.ROUND_AMOUNT) == set()


# --- time-based --------------------------------------------------------------


def test_off_hours_fires_at_night() -> None:
    frame = ledger(voucher("V1", posted="2024-06-12 02:15:00"))
    assert fired(frame, SignalKind.OFF_HOURS_POSTING) == {"V1"}


def test_off_hours_silent_during_the_working_day() -> None:
    frame = ledger(voucher("V1", posted="2024-06-12 14:15:00"))
    assert fired(frame, SignalKind.OFF_HOURS_POSTING) == set()


def test_off_hours_returns_nothing_when_the_source_has_no_real_time() -> None:
    """The Phase 0 finding, as code.

    Every VynFi posting is midnight. Reading that as a real time would flag all
    667,584 lines as after-hours entries and produce a queue of pure noise.
    """
    frame = ledger(
        voucher("V1", posted="2024-06-12 00:00:00"),
        voucher("V2", posted="2024-06-13 00:00:00"),
    )
    assert build_context(frame).time_fidelity == TimeFidelity.DATE_ONLY
    assert fired(frame, SignalKind.OFF_HOURS_POSTING) == set()


def test_weekend_fires_on_sunday_posting() -> None:
    frame = ledger(voucher("V1", date="2024-06-16", posted="2024-06-16 11:00:00"))
    assert fired(frame, SignalKind.WEEKEND_POSTING) == {"V1"}


def test_weekend_silent_on_saturday() -> None:
    """Saturday is an ordinary working day in most Indian practices."""
    frame = ledger(voucher("V1", date="2024-06-15", posted="2024-06-15 11:00:00"))
    assert fired(frame, SignalKind.WEEKEND_POSTING) == set()


def test_weekend_reads_the_posting_day_not_the_voucher_date() -> None:
    """A month-end provision dated Sunday but entered on Monday is routine."""
    frame = ledger(voucher("V1", date="2024-06-16", posted="2024-06-17 11:00:00"))
    assert fired(frame, SignalKind.WEEKEND_POSTING) == set()


# --- period end --------------------------------------------------------------


def test_period_end_fires_on_an_undocumented_manual_year_end_entry() -> None:
    frame = ledger(voucher("V1", date="2025-03-31", doc=None, approver=None))
    assert fired(frame, SignalKind.PERIOD_END_CONCENTRATION) == {"V1"}


def test_period_end_silent_when_documented_and_approved() -> None:
    """Depreciation genuinely belongs on 31 March."""
    frame = ledger(voucher("V1", date="2025-03-31", doc="JV/1", approver="iyer.cfo"))
    assert fired(frame, SignalKind.PERIOD_END_CONCENTRATION) == set()


# --- threshold ---------------------------------------------------------------


def test_threshold_fires_just_below_the_limit_without_an_approver() -> None:
    frame = ledger(voucher("V1", amount=49_200_00, approver=None))
    assert fired(frame, SignalKind.THRESHOLD_ADJACENT) == {"V1"}


def test_threshold_silent_when_approved() -> None:
    """A genuine invoice under the limit, properly approved, is not structuring."""
    frame = ledger(voucher("V1", amount=49_200_00, approver="iyer.cfo"))
    assert fired(frame, SignalKind.THRESHOLD_ADJACENT) == set()


def test_threshold_respects_a_firm_specific_limit() -> None:
    frame = ledger(voucher("V1", amount=99_500_00, approver=None))
    cfg = DetectorConfig(approval_limit_paise=1_00_000_00)
    hits = run_signals(frame, cfg, enabled={SignalKind.THRESHOLD_ADJACENT})
    assert flagged_vouchers(hits) == {"V1"}


# --- evidence ----------------------------------------------------------------


def test_missing_evidence_fires_on_a_material_manual_entry() -> None:
    frame = ledger(voucher("V1", amount=80_000_00, doc=None))
    assert fired(frame, SignalKind.MISSING_EVIDENCE) == {"V1"}


def test_missing_evidence_silent_on_an_immaterial_system_entry() -> None:
    """Bank charges from a feed are never voucher-backed, and are trivial."""
    frame = ledger(voucher("V1", amount=500_00, doc=None, by="SYSTEM", manual=False))
    assert fired(frame, SignalKind.MISSING_EVIDENCE) == set()


# --- post close --------------------------------------------------------------


def test_post_close_fires_on_a_long_lag() -> None:
    frame = ledger(voucher("V1", date="2025-03-20", posted="2025-08-01 10:00:00"))
    assert fired(frame, SignalKind.POST_CLOSE_ENTRY) == {"V1"}


def test_post_close_fires_on_the_source_flag() -> None:
    assert fired(ledger(voucher("V1", post_close=True)), SignalKind.POST_CLOSE_ENTRY) == {"V1"}


def test_post_close_silent_on_a_normal_lag() -> None:
    frame = ledger(voucher("V1", date="2024-06-12", posted="2024-06-14 10:00:00"))
    assert fired(frame, SignalKind.POST_CLOSE_ENTRY) == set()


# --- runner behaviour --------------------------------------------------------


def test_every_hit_carries_structured_evidence(ledger_frame: pd.DataFrame) -> None:
    """Phase 5's model explains from this dict and may state nothing else."""
    hits = run_signals(ledger_frame)
    assert hits
    for hit in hits:
        assert hit.evidence, f"{hit.kind} produced no evidence"
        assert hit.reason.strip()
        assert 0.0 <= hit.strength <= 1.0


def test_results_are_deterministic(ledger_frame: pd.DataFrame) -> None:
    """A reviewer reopening an engagement must see the same queue, in the same order."""
    assert run_signals(ledger_frame) == run_signals(ledger_frame)


def test_enabled_subset_runs_only_those_signals(ledger_frame: pd.DataFrame) -> None:
    hits = run_signals(ledger_frame, enabled={SignalKind.MISSING_EVIDENCE})
    assert {h.kind for h in hits} <= {SignalKind.MISSING_EVIDENCE}


def test_grouping_and_counting(ledger_frame: pd.DataFrame) -> None:
    hits = run_signals(ledger_frame)
    grouped = group_by_voucher(hits)
    assert sum(len(v) for v in grouped.values()) == len(hits)
    # The deterministic rules only; the statistical and model layers are
    # separate producers (see the architecture) and are counted alongside.
    assert set(count_by_kind(hits)) == set(DETECTORS)


def test_empty_ledger_is_handled() -> None:
    frame = ledger(voucher("V1"))
    assert run_signals(frame.iloc[0:0]) == []


@pytest.fixture
def ledger_frame() -> pd.DataFrame:
    return ledger(
        voucher("V1", amount=5_00_000_00),
        voucher("V2", amount=49_200_00, approver=None),
        voucher("V3", amount=80_000_00, doc=None),
        voucher("V4", posted="2024-06-12 03:00:00"),
        voucher("V5", date="2025-03-31", doc=None, approver=None),
    )


def test_context_infers_year_end() -> None:
    frame = ledger(voucher("V1", date="2024-06-12"))
    assert build_context(frame).year_end == pd.Timestamp("2025-03-31")


def test_context_reports_real_posting_times() -> None:
    frame = ledger(voucher("V1", posted="2024-06-12 15:00:00"))
    assert build_context(frame).has_posting_times


def test_config_rejects_an_inverted_off_hours_window() -> None:
    with pytest.raises(ValueError, match="wrap midnight"):
        DetectorConfig(off_hours_start=6, off_hours_end=22)


def test_hit_requires_a_reason() -> None:
    from caguard.detect.types import SignalHit

    with pytest.raises(ValueError, match="without a reason"):
        SignalHit(voucher_id="V1", kind=SignalKind.ROUND_AMOUNT, strength=0.5, reason="  ")


def test_datetime_fixture_sanity() -> None:
    assert isinstance(pd.Timestamp("2024-06-12 11:30:00").to_pydatetime(), datetime)


def test_rare_pair_abstains_when_every_pairing_is_rare() -> None:
    """A long-tail chart of accounts makes "rare" describe the norm.

    Found on the real VynFi corpus, where the signal flagged 95% of 53,291
    vouchers because thousands of GL codes each appear a handful of times.
    Saying nothing is more useful than saying everything — the same reasoning
    that keeps the off-hours signal quiet on a source with no real posting time.
    """
    frame = ledger(
        *[
            voucher(f"V{i}", debit=f"{7000 + i}", credit=f"{8000 + i}", date="2024-06-12")
            for i in range(40)
        ]
    )
    assert fired(frame, SignalKind.RARE_ACCOUNT_PAIR) == set()


def test_rare_pair_still_fires_when_it_can_discriminate() -> None:
    """One odd pairing against a background of ordinary, repeated ones."""
    routine = [voucher(f"R{i}", debit="5000", credit="2000", date="2024-06-12") for i in range(30)]
    routine += [voucher(f"S{i}", debit="4000", credit="1100", date="2024-06-12") for i in range(30)]
    odd = voucher("ODD", debit="5110", credit="1800", date="2024-06-12")
    assert fired(ledger(*routine, odd), SignalKind.RARE_ACCOUNT_PAIR) == {"ODD"}
