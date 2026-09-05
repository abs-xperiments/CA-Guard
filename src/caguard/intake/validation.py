"""Turning a mapped frame into canonical lines, and reporting what would not convert.

A bad row must never abort the file. A CA uploading a year's ledger needs to see
"these 14 rows are unusable, and here is why", not a traceback — and the other
40,000 rows should still be reviewable. Errors carry the source row number so
they can be found in the original spreadsheet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd
from pydantic import ValidationError

from caguard.schema import JournalLine, Voucher

MAX_REPORTED_ERRORS = 500


@dataclass(frozen=True)
class RowError:
    """One row that could not be converted."""

    row_number: int
    reason: str

    def __str__(self) -> str:
        return f"row {self.row_number}: {self.reason}"


@dataclass
class ValidationReport:
    """The outcome of validating one file."""

    lines: list[JournalLine] = field(default_factory=list)
    errors: list[RowError] = field(default_factory=list)
    unbalanced_vouchers: dict[str, int] = field(default_factory=dict)
    truncated_errors: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors and not self.unbalanced_vouchers

    @property
    def accepted(self) -> int:
        return len(self.lines)

    def summary(self) -> str:
        parts = [f"{self.accepted:,} lines accepted"]
        if self.errors:
            shown = f"{len(self.errors):,}{'+' if self.truncated_errors else ''}"
            parts.append(f"{shown} rows rejected")
        if self.unbalanced_vouchers:
            parts.append(f"{len(self.unbalanced_vouchers):,} vouchers do not balance")
        return "; ".join(parts)


def validate_lines(records: list[dict[str, object]]) -> ValidationReport:
    """Validate canonical-shaped dicts into :class:`JournalLine` objects.

    ``records`` must already use canonical field names — mapping happens
    upstream so that this stage has exactly one job.
    """
    report = ValidationReport()

    for offset, record in enumerate(records, start=2):  # row 1 is the header
        try:
            report.lines.append(JournalLine.model_validate(record))
        except ValidationError as exc:
            if len(report.errors) < MAX_REPORTED_ERRORS:
                report.errors.append(RowError(offset, _readable(exc)))
            else:
                report.truncated_errors = True

    report.unbalanced_vouchers = find_unbalanced(report.lines)
    return report


def find_unbalanced(lines: list[JournalLine]) -> dict[str, int]:
    """Vouchers whose debits and credits differ, mapped to the gap in paise.

    Reported rather than raised: a real export can contain a genuinely broken
    voucher, and the reviewer needs to see which one and by how much.
    """
    totals: dict[str, int] = {}
    for line in lines:
        totals[line.voucher_id] = totals.get(line.voucher_id, 0) + line.signed_paise
    return {vid: gap for vid, gap in totals.items() if gap != 0}


def build_vouchers(lines: list[JournalLine]) -> tuple[list[Voucher], dict[str, int]]:
    """Group validated lines into balanced vouchers, skipping ones that do not balance."""
    grouped: dict[str, list[JournalLine]] = {}
    for line in lines:
        grouped.setdefault(line.voucher_id, []).append(line)

    vouchers: list[Voucher] = []
    rejected: dict[str, int] = {}
    for vid, group in grouped.items():
        gap = sum(ln.signed_paise for ln in group)
        if gap != 0:
            rejected[vid] = gap
            continue
        vouchers.append(Voucher(voucher_id=vid, lines=sorted(group, key=lambda ln: ln.line_number)))
    return vouchers, rejected


def frame_to_records(frame: pd.DataFrame) -> list[dict[str, object]]:
    """Convert a canonical-columned frame to plain dicts, turning NaN into None."""
    return [
        {k: (None if pd.isna(v) else v) for k, v in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _readable(exc: ValidationError) -> str:
    """Flatten a Pydantic error into one line a non-programmer can act on."""
    parts = []
    for err in exc.errors():
        location = ".".join(str(p) for p in err["loc"]) or "row"
        parts.append(f"{location}: {err['msg']}")
    return "; ".join(parts[:4])
