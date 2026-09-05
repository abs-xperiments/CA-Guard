from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from caguard.schema import (
    JournalLine,
    Voucher,
    fiscal_period_of,
    fiscal_year_of,
)


def test_line_must_be_debit_or_credit_not_both(make_line) -> None:
    with pytest.raises(ValidationError, match="exactly one of debit/credit"):
        make_line(debit_paise=100, credit_paise=50)


def test_line_must_have_an_amount(make_line) -> None:
    with pytest.raises(ValidationError, match="exactly one of debit/credit"):
        make_line(debit_paise=0, credit_paise=0)


def test_negative_amounts_are_rejected(make_line) -> None:
    with pytest.raises(ValidationError):
        make_line(debit_paise=-100)


def test_voucher_must_balance_to_zero_paise(make_line) -> None:
    """No tolerance: an accounting tool with an epsilon is a place for errors to hide."""
    a = make_line(line_id="V1-01", debit_paise=100_01)
    b = make_line(line_id="V1-02", line_number=2, debit_paise=0, credit_paise=100_00)
    with pytest.raises(ValidationError, match="differ by 1 paise"):
        Voucher(voucher_id="V1", lines=[a, b])


def test_balanced_voucher_is_accepted(make_line) -> None:
    a = make_line(line_id="V1-01", debit_paise=100_00)
    b = make_line(line_id="V1-02", line_number=2, debit_paise=0, credit_paise=100_00)
    voucher = Voucher(voucher_id="V1", lines=[a, b])
    assert voucher.total_paise == 100_00


def test_voucher_rejects_foreign_lines(make_line) -> None:
    a = make_line(line_id="V1-01", debit_paise=100_00)
    b = make_line(line_id="X-01", voucher_id="OTHER", debit_paise=0, credit_paise=100_00)
    with pytest.raises(ValidationError, match="foreign lines"):
        Voucher(voucher_id="V1", lines=[a, b])


def test_period_must_match_the_voucher_date(make_line) -> None:
    with pytest.raises(ValidationError, match="is period 1, not the declared 7"):
        make_line(period=7)


def test_fiscal_year_must_match_the_voucher_date(make_line) -> None:
    with pytest.raises(ValidationError, match="falls in FY2023-24"):
        make_line(voucher_date=date(2024, 3, 20), period=12)


@pytest.mark.parametrize(
    "day,fy,period",
    [
        (date(2024, 4, 1), "FY2024-25", 1),  # first day of the Indian FY
        (date(2024, 12, 31), "FY2024-25", 9),
        (date(2025, 3, 31), "FY2024-25", 12),  # year end — the date that matters most
        (date(2025, 4, 1), "FY2025-26", 1),
    ],
)
def test_indian_fiscal_year_runs_april_to_march(day: date, fy: str, period: int) -> None:
    assert fiscal_year_of(day) == fy
    assert fiscal_period_of(day) == period


def test_evidence_presence_is_exposed_on_the_line(make_line) -> None:
    assert make_line(document_ref="INV/24-25/0001").has_evidence
    assert not make_line(document_ref=None).has_evidence
    assert not make_line(document_ref="   ").has_evidence


def test_voucher_evidence_coverage(make_line) -> None:
    a = make_line(line_id="V1-01", debit_paise=100_00, document_ref="INV/1")
    b = make_line(line_id="V1-02", line_number=2, debit_paise=0, credit_paise=100_00)
    assert Voucher(voucher_id="V1", lines=[a, b]).evidence_coverage == 0.5


def test_lines_are_immutable(make_line) -> None:
    """Findings must reference data that cannot change underneath them."""
    line: JournalLine = make_line()
    with pytest.raises(ValidationError):
        line.debit_paise = 1  # pyright: ignore[reportAttributeAccessIssue]
