"""Tests for the VynFi adapter.

Most run against a small hand-built frame in the corpus's shape, so the suite
stays fast and offline. The ``slow`` test runs the real 667,584-line corpus when
it has been downloaded, which is the Phase 1 acceptance criterion.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from caguard.adapters.vynfi import LABEL_COLUMNS, adapt
from caguard.intake.validation import build_vouchers, frame_to_records, validate_lines
from caguard.schema import TimeFidelity, VoucherType

CORPUS = Path(__file__).resolve().parents[1] / "data" / "external"


def sample_frame() -> pd.DataFrame:
    """Two balanced lines in the corpus's shape, including its label columns."""
    return pd.DataFrame(
        {
            "document_id": ["D1", "D1"],
            "line_number": [1, 2],
            "company_code": [1000, 1000],
            "document_date": pd.to_datetime(["2024-05-10", "2024-05-10"]),
            "posting_date": pd.to_datetime(["2024-05-12", "2024-05-12"]),
            "document_type": ["KR", "KR"],
            "gl_account": [5000, 2000],
            "account_description": ["Raw Material", "Trade Payables"],
            "financial_statement_category": ["expense", "liability"],
            "debit_amount": [1234.56, 0.0],
            "credit_amount": [0.0, 1234.56],
            "currency": ["USD", "USD"],
            "created_by": ["USER0001", "USER0001"],
            "reference": ["INV-9", None],
            "line_text": ["Purchase", None],
            "header_text": ["Vendor invoice", "Vendor invoice"],
            "cost_center": [None, None],
            "is_manual": [True, True],
            "is_post_close": [False, False],
            # Label columns that must never survive adaptation:
            "is_fraud": [True, True],
            "is_anomaly": [True, True],
            "fraud_type": ["FictitiousTransaction", "FictitiousTransaction"],
            "anomaly_type": ["DuplicateEntry", "DuplicateEntry"],
        }
    )


def test_labels_are_dropped_not_merely_ignored() -> None:
    """ADR-0001: these labels are not recoverable from the data.

    Carrying them through would invite someone downstream to score against them
    and publish a near-random number as a result.
    """
    out = adapt(sample_frame())
    assert not LABEL_COLUMNS & set(out.columns)


def test_posting_time_is_marked_date_only() -> None:
    """Every posting_date in the corpus is midnight.

    Recording that as a real time would make all 667,584 lines look like
    after-hours entries to any time-of-day signal.
    """
    out = adapt(sample_frame())
    assert (out.time_fidelity == TimeFidelity.DATE_ONLY.value).all()


def test_fiscal_year_is_recomputed_on_the_indian_convention() -> None:
    """The corpus carries calendar-based periods; the canonical schema owns this."""
    out = adapt(sample_frame())
    assert (out.fiscal_year == "FY2024-25").all()
    assert (out.period == 2).all()  # May is period 2 of an April-March year


def test_document_types_map_to_voucher_types() -> None:
    frame = sample_frame()
    frame["document_type"] = ["DR", "DZ"]
    out = adapt(frame)
    assert list(out.voucher_type) == [VoucherType.SALES.value, VoucherType.RECEIPT.value]


def test_unknown_document_type_falls_back_to_other() -> None:
    frame = sample_frame()
    frame["document_type"] = ["ZZ", "ZZ"]
    assert (adapt(frame).voucher_type == VoucherType.OTHER.value).all()


def test_amounts_become_exact_paise() -> None:
    out = adapt(sample_frame())
    assert out.debit_paise.tolist() == [123456, 0]
    assert out.credit_paise.tolist() == [0, 123456]


def test_adapted_rows_validate_and_balance() -> None:
    report = validate_lines(frame_to_records(adapt(sample_frame())))
    assert report.ok, report.summary()
    vouchers, rejected = build_vouchers(report.lines)
    assert len(vouchers) == 1 and not rejected


@pytest.mark.slow
def test_full_corpus_ingests() -> None:
    """Phase 1 acceptance: the whole corpus passes through the canonical schema.

    Skipped unless the corpus has been downloaded, so the default suite stays
    offline and fast.
    """
    shards = sorted(CORPUS.glob("shard*.parquet"))
    if not shards:
        pytest.skip("VynFi corpus not downloaded; run `make data` to fetch it")

    raw = pd.concat([pd.read_parquet(p) for p in shards], ignore_index=True)
    report = validate_lines(frame_to_records(adapt(raw)))

    assert len(raw) > 600_000
    # A real export contains some broken rows; the bar is that the run completes
    # and reports them, not that the source data is perfect.
    assert report.accepted / len(raw) > 0.99
    vouchers, rejected = build_vouchers(report.lines)
    assert len(vouchers) > 100_000
    assert len(rejected) / (len(vouchers) + len(rejected)) < 0.01
