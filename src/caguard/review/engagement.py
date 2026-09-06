"""An engagement: one ledger, opened for review, with its identity recorded.

The content hash matters more than it looks. Findings are never stored — they
are recomputed from the ledger — so the only way to know that the decisions in
the database still describe the same book is to have recorded what that book was
when the reviewer looked at it.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class Engagement(BaseModel):
    """One ledger under review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    entity_id: str = ""
    fiscal_year: str = ""
    source_name: str = ""
    content_sha256: str = Field(min_length=8)
    voucher_count: int = Field(ge=0)
    opened_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def short_hash(self) -> str:
        return self.content_sha256[:12]

    def matches(self, lines: pd.DataFrame) -> bool:
        """Whether a ledger is the same book this engagement was opened on."""
        return ledger_hash(lines) == self.content_sha256


def ledger_hash(lines: pd.DataFrame) -> str:
    """A stable hash of a ledger's content.

    Deliberately over the values rather than the file: the same ledger saved as
    CSV and as parquet is the same book, and should open the same engagement.
    """
    columns = sorted(lines.columns)
    ordered = lines.loc[:, columns]

    # Sort by something unique. Sorting on the first couple of columns leaves
    # ties, and ties mean the same ledger can hash two different ways depending
    # on the order it happened to arrive in.
    key = ["line_id"] if "line_id" in columns else columns
    canonical = ordered.sort_values(key, kind="mergesort").reset_index(drop=True)
    return hashlib.sha256(canonical.to_csv(index=False).encode()).hexdigest()


def open_engagement(
    lines: pd.DataFrame,
    *,
    name: str | None = None,
    source: str | Path = "uploaded ledger",
) -> Engagement:
    """Build an engagement from a ledger, deriving what it can from the data."""
    digest = ledger_hash(lines)
    entity = _first(lines, "entity_id")
    fiscal_year = _first(lines, "fiscal_year")
    source_name = Path(source).name if isinstance(source, Path) else str(source)

    return Engagement(
        id=digest[:16],
        name=name or f"{entity or 'Ledger'} {fiscal_year}".strip(),
        entity_id=entity,
        fiscal_year=fiscal_year,
        source_name=source_name,
        content_sha256=digest,
        voucher_count=_voucher_count(lines),
    )


def _voucher_count(lines: pd.DataFrame) -> int:
    if "voucher_id" not in lines.columns:
        return 0
    return int(pd.Series(lines["voucher_id"]).nunique())


def _first(lines: pd.DataFrame, column: str) -> str:
    if column not in lines.columns or lines.empty:
        return ""
    values = lines[column].dropna()
    return str(values.iloc[0]) if len(values) else ""
