from __future__ import annotations

from pathlib import Path

import pytest

from caguard.intake.mapping import explain_ambiguity, infer_mapping
from caguard.intake.readers import IntakeError, read_table
from caguard.intake.validation import (
    build_vouchers,
    find_unbalanced,
    frame_to_records,
    validate_lines,
)

TALLY_HEADERS = ["Date", "Particulars", "Vch Type", "Vch No.", "Debit", "Credit", "Narration"]
SAP_HEADERS = [
    "document_id",
    "line_number",
    "document_date",
    "document_type",
    "gl_account",
    "account_description",
    "debit_amount",
    "credit_amount",
    "created_by",
    "reference",
]


def test_tally_headers_map_cleanly() -> None:
    mapping = infer_mapping(TALLY_HEADERS)
    assert mapping.resolved["Vch No."] == "voucher_id"
    assert mapping.resolved["Particulars"] == "account_name"
    assert mapping.is_usable


def test_sap_headers_map_cleanly() -> None:
    mapping = infer_mapping(SAP_HEADERS)
    assert mapping.resolved["gl_account"] == "account_code"
    assert mapping.is_usable


def test_two_headers_claiming_one_field_is_ambiguous_not_guessed() -> None:
    """Silently choosing between 'Voucher No' and 'Doc No' would be a coin flip."""
    mapping = infer_mapping(["Voucher No", "Doc No", "Date", "Ledger", "Amount"])
    assert set(mapping.ambiguous) == {"Voucher No", "Doc No"}


def test_overrides_beat_inference() -> None:
    mapping = infer_mapping(TALLY_HEADERS, overrides={"Particulars": "narration"})
    assert mapping.resolved["Particulars"] == "narration"


def test_missing_required_fields_are_named() -> None:
    mapping = infer_mapping(["Colour", "Size"])
    assert "voucher_id" in mapping.missing_required
    assert "debit/credit or amount" in mapping.missing_required
    assert not mapping.is_usable


def test_unknown_headers_are_listed_not_dropped_silently() -> None:
    assert infer_mapping(["Date", "Sparkle Factor"]).unmapped == ["Sparkle Factor"]


def test_tally_particulars_ambiguity_is_explained() -> None:
    assert "Tally" in (explain_ambiguity("Particulars") or "")


def test_missing_file_gives_a_readable_error(tmp_path: Path) -> None:
    with pytest.raises(IntakeError, match="File not found"):
        read_table(tmp_path / "nope.csv")


def test_unsupported_type_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "ledger.docx"
    bad.write_text("x")
    with pytest.raises(IntakeError, match="Unsupported file type"):
        read_table(bad)


def test_empty_file_is_refused(tmp_path: Path) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("a,b\n")
    with pytest.raises(IntakeError, match="no rows"):
        read_table(empty)


def test_csv_round_trip(tmp_path: Path, ledger) -> None:
    path = tmp_path / "ledger.csv"
    ledger.lines.head(50).to_csv(path, index=False)
    assert len(read_table(path)) == 50


def test_one_bad_row_does_not_abort_the_file(ledger) -> None:
    """A CA needs the other 40,000 rows, plus a list of what failed and why."""
    records = frame_to_records(ledger.lines.head(30))
    records[3]["debit_paise"] = 0
    records[3]["credit_paise"] = 0

    report = validate_lines(records)
    assert report.accepted == 29
    assert len(report.errors) == 1
    assert report.errors[0].row_number == 5  # header is row 1
    assert "exactly one of debit/credit" in report.errors[0].reason


def test_report_summary_is_human_readable(ledger) -> None:
    report = validate_lines(frame_to_records(ledger.lines.head(20)))
    assert "lines accepted" in report.summary()


def test_generated_ledger_validates_completely(ledger) -> None:
    report = validate_lines(frame_to_records(ledger.lines))
    assert report.ok, report.summary()
    assert report.accepted == len(ledger.lines)


def test_unbalanced_vouchers_are_reported_with_the_gap(ledger) -> None:
    report = validate_lines(frame_to_records(ledger.lines))
    lines = [ln for ln in report.lines if ln.line_number > 1 or ln.voucher_id != "V000001"]
    gaps = find_unbalanced(lines)
    assert "V000001" in gaps


def test_build_vouchers_skips_unbalanced_rather_than_raising(ledger) -> None:
    report = validate_lines(frame_to_records(ledger.lines))
    broken = [ln for ln in report.lines if not (ln.voucher_id == "V000002" and ln.line_number == 1)]
    vouchers, rejected = build_vouchers(broken)
    assert "V000002" in rejected
    assert vouchers
