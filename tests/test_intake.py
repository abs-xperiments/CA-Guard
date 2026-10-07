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


# --- restoring types to a ledger that arrived as text ------------------------


def test_csv_round_trip_restores_working_types(tmp_path: Path, ledger) -> None:
    """CSV has no types, and the detectors need numbers to be numbers.

    Without this an uploaded file failed deep inside the detectors with a
    comparison error that told a reviewer nothing.
    """
    import pandas as pd

    from caguard.intake.coerce import to_canonical_types

    path = tmp_path / "ledger.csv"
    ledger.lines.head(200).to_csv(path, index=False)
    typed = to_canonical_types(read_table(path))

    assert typed.debit_paise.dtype == "int64"
    assert typed.credit_paise.dtype == "int64"
    assert typed.is_manual.dtype == bool
    assert pd.api.types.is_datetime64_any_dtype(typed.voucher_date)
    assert pd.api.types.is_datetime64_any_dtype(typed.posted_at)


def test_blank_means_absent_not_empty(tmp_path: Path, ledger) -> None:
    """An empty string is not a document reference.

    Treating it as one would quietly erase the evidence gap the whole product
    is built around.
    """
    from caguard.intake.coerce import to_canonical_types

    path = tmp_path / "ledger.csv"
    ledger.lines.head(200).to_csv(path, index=False)
    typed = to_canonical_types(read_table(path))

    assert typed.document_ref.isna().any(), "no absent references survived the round trip"
    assert not (typed.document_ref.dropna() == "").any()


def test_coercion_is_safe_on_already_typed_data(ledger) -> None:
    """Callers should not need to know where their data came from."""
    from caguard.intake.coerce import to_canonical_types

    once = to_canonical_types(ledger.lines)
    twice = to_canonical_types(once)
    assert once.debit_paise.equals(twice.debit_paise)
    assert once.is_manual.equals(twice.is_manual)


def test_common_document_and_posting_headings_are_recognised() -> None:
    """Found while preparing the sample ledger: both were silently unmapped, so every
    entry looked undocumented and posting times were lost."""
    mapping = infer_mapping(
        ["Voucher No", "Date", "Ledger", "Debit", "Credit", "Doc Ref", "Posted"]
    )
    assert mapping.resolved["Doc Ref"] == "document_ref"
    assert mapping.resolved["Posted"] == "posted_at"
