"""Tests for turning a real ledger export into the canonical schema.

Written after a bug report: uploading a Tally-style CSV produced "Internal
Server Error". The upload path assumed canonical column names, so any file a CA
actually has crashed with `KeyError: 'voucher_date'` deep inside the detectors.

Two things are asserted throughout. That real-world files work — and that when
one does not, the user is told what is wrong with *their file* rather than shown
a stack trace.
"""

from __future__ import annotations

import pandas as pd
import pytest

from caguard.detect.context import build_context
from caguard.intake.normalise import NormalisationError, normalise
from caguard.review.fusion import build_findings
from caguard.schema import TimeFidelity


def tally_export() -> pd.DataFrame:
    """The shape Tally actually exports, as text, the way a CSV arrives."""
    return pd.DataFrame(
        {
            "Date": ["01-04-2024", "01-04-2024", "15-04-2024", "15-04-2024"],
            "Vch No.": ["V001", "V001", "V002", "V002"],
            "Vch Type": ["Payment", "Payment", "Sales", "Sales"],
            "Particulars": ["Rent", "HDFC Bank", "Sundry Debtors", "Sales - Domestic"],
            "Debit": ["2,00,000.00", "", "1,18,000.00", ""],
            "Credit": ["", "2,00,000.00", "", "1,18,000.00"],
            "Narration": ["Office rent", "Office rent", "Invoice 41", "Invoice 41"],
        }
    )


# --- the file that caused the bug report --------------------------------------


def test_a_tally_export_becomes_a_ledger() -> None:
    result = normalise(tally_export())
    lines = result.lines

    assert len(lines) == 4
    assert set(lines.voucher_id) == {"V001", "V002"}
    assert list(lines.line_id[:2]) == ["V001-01", "V001-02"]


def test_rupees_are_converted_to_paise() -> None:
    """A hundred-fold error here would be invisible and catastrophic."""
    lines = normalise(tally_export()).lines
    assert lines.debit_paise.iloc[0] == 2_00_000_00
    assert lines.credit_paise.iloc[1] == 2_00_000_00


def test_indian_dates_are_read_day_first() -> None:
    """03-04-2025 in an Indian ledger is 3 April, not 4 March."""
    frame = tally_export()
    frame["Date"] = ["03-04-2024"] * 4
    lines = normalise(frame).lines
    assert lines.voucher_date.iloc[0].month == 4
    assert lines.voucher_date.iloc[0].day == 3


def test_the_fiscal_year_and_period_are_derived() -> None:
    lines = normalise(tally_export()).lines
    assert set(lines.fiscal_year) == {"FY2024-25"}
    assert lines.period.iloc[0] == 1  # April


def test_voucher_types_are_recognised() -> None:
    lines = normalise(tally_export()).lines
    assert set(lines.voucher_type) == {"payment", "sales"}


def test_an_account_code_is_derived_when_the_file_has_none() -> None:
    """Account-level signals still work, and a reviewer still recognises the name."""
    lines = normalise(tally_export()).lines
    assert "Rent" in set(lines.account_code)


def test_a_normalised_export_flows_through_the_whole_pipeline() -> None:
    """The real test: it does not merely parse, it analyses."""
    lines = normalise(tally_export()).lines
    context = build_context(lines)
    assert len(context) == 2
    build_findings(lines)  # must not raise


def test_amounts_survive_currency_symbols_and_brackets() -> None:
    frame = tally_export()
    frame["Debit"] = ["₹ 2,00,000.00", "", "(1,000.00)", ""]
    lines = normalise(frame).lines
    assert lines.debit_paise.iloc[0] == 2_00_000_00
    assert lines.debit_paise.iloc[2] == -1_000_00


def test_a_single_signed_amount_column_is_split() -> None:
    frame = pd.DataFrame(
        {
            "Date": ["31-03-2025", "31-03-2025"],
            "Voucher": ["V1", "V1"],
            "Ledger": ["Rent", "Bank"],
            "Amount": ["1,50,000.00", "-1,50,000.00"],
        }
    )
    lines = normalise(frame).lines
    assert lines.debit_paise.iloc[0] == 1_50_000_00
    assert lines.credit_paise.iloc[1] == 1_50_000_00


# --- telling the user what the file did not contain ---------------------------


def test_missing_columns_are_reported_not_silently_defaulted() -> None:
    """A limitation of the file must never look like a finding about the client."""
    report = normalise(tally_export()).report
    assert "document_ref" in report.defaulted
    assert "approved_by" in report.defaulted
    assert any("no supporting-document column" in note for note in report.notes)
    assert any("no approver column" in note for note in report.notes)


def test_absent_posting_times_are_marked_unknown() -> None:
    """Otherwise every entry would look like it was made at midnight."""
    lines = normalise(tally_export()).lines
    assert set(lines.time_fidelity) == {TimeFidelity.UNKNOWN.value}


def test_the_report_says_what_it_recognised() -> None:
    report = normalise(tally_export()).report
    assert report.rows_in == 4
    assert report.rows_out == 4
    assert "Vch No." in report.mapped
    assert "columns recognised" in report.summary()


# --- refusing badly, but clearly ----------------------------------------------


def test_a_file_that_is_not_a_ledger_explains_itself() -> None:
    frame = pd.DataFrame({"Colour": ["red"], "Size": ["large"]})
    with pytest.raises(NormalisationError) as caught:
        normalise(frame)

    message = str(caught.value)
    assert "does not look like a ledger" in message
    assert "a voucher number" in message
    assert "a date" in message


def test_a_missing_amount_column_is_named() -> None:
    frame = pd.DataFrame({"Date": ["01-04-2024"], "Vch No.": ["V1"], "Particulars": ["Rent"]})
    with pytest.raises(NormalisationError, match="debit/credit or amount"):
        normalise(frame)


def test_an_empty_file_is_refused_clearly() -> None:
    with pytest.raises(NormalisationError, match="no rows"):
        normalise(pd.DataFrame())


def test_rows_without_a_date_or_voucher_are_dropped_and_counted() -> None:
    frame = tally_export()
    frame.loc[4] = ["", "", "Journal", "Suspense", "100.00", "", ""]
    result = normalise(frame)
    assert result.report.rows_in == 5
    assert result.report.rows_out == 4


# --- a canonical file still passes straight through ---------------------------


def test_a_canonical_ledger_is_not_re_mapped(ledger) -> None:
    result = normalise(ledger.lines)
    assert result.report.rows_out == len(ledger.lines)
    assert not result.report.derived
    pd.testing.assert_series_equal(
        result.lines.debit_paise, ledger.lines.debit_paise, check_dtype=False
    )


@pytest.mark.parametrize(
    "headers",
    [
        ["Date", "Voucher", "Ledger", "Amount"],
        ["Txn Date", "Txn ID", "Account Head", "Dr", "Cr"],
        ["Date", "Vch No.", "Particulars", "Debit", "Credit"],
        ["posting_date", "document_id", "account_description", "debit", "credit"],
    ],
)
def test_real_world_header_shapes_are_usable(headers: list[str]) -> None:
    """Each of these is a shape a real export actually has."""
    frame = pd.DataFrame(
        {header: (["01-04-2024"] if "ate" in header else ["100"]) for header in headers}
    )
    frame[headers[1]] = ["V1"]
    frame[headers[2]] = ["Rent"]
    normalise(frame)  # must not raise
