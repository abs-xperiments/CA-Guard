"""Restoring types to a ledger that arrived as text.

CSV has no types. Everything is read as a string on purpose — that is how
account codes keep their leading zeros and how amounts get parsed exactly once,
by us, rather than twice by two libraries with different opinions.

But the detectors need numbers to be numbers. This is the one place that
conversion happens, so a ledger from a CSV upload and one built in memory reach
the pipeline in the same shape. Without it, an uploaded file fails deep inside
the detectors with a comparison error that says nothing useful to a reviewer.
"""

from __future__ import annotations

import pandas as pd

#: Whole numbers. Amounts are paise (see :mod:`caguard.money`) and stay integral.
INTEGER_COLUMNS = ("line_number", "period", "debit_paise", "credit_paise")
DATE_COLUMNS = ("voucher_date", "posted_at")
BOOLEAN_COLUMNS = ("is_manual", "is_post_close")

#: Columns where "absent" is meaningful — an evidence gap, not an empty string.
NULLABLE_TEXT_COLUMNS = (
    "approved_by",
    "document_ref",
    "narration",
    "cost_centre",
)

_TRUE = frozenset({"true", "t", "yes", "y", "1"})


def to_canonical_types(frame: pd.DataFrame) -> pd.DataFrame:
    """Cast a canonical-columned frame to the types the pipeline expects.

    Safe to call on a frame that is already typed, so callers do not have to
    know where their data came from.
    """
    typed = frame.copy()

    for column in INTEGER_COLUMNS:
        if column in typed.columns:
            numeric = pd.Series(pd.to_numeric(typed[column], errors="coerce"))
            typed[column] = numeric.fillna(0).astype("int64")

    for column in DATE_COLUMNS:
        if column in typed.columns:
            typed[column] = pd.to_datetime(typed[column], errors="coerce")

    for column in BOOLEAN_COLUMNS:
        if column in typed.columns:
            typed[column] = _as_bool(pd.Series(typed[column]))

    for column in NULLABLE_TEXT_COLUMNS:
        if column in typed.columns:
            typed[column] = _as_optional_text(pd.Series(typed[column]))

    return typed


def _as_bool(series: pd.Series) -> pd.Series:
    """Read a boolean however the file happened to spell it."""
    if series.dtype == bool:
        return series
    return series.astype(str).str.strip().str.lower().isin(_TRUE).fillna(False).astype(bool)


def _as_optional_text(series: pd.Series) -> pd.Series:
    """Blank means absent.

    A CSV round trip turns ``None`` into an empty string, and an empty string is
    not the same thing as a document reference. Treating it as one would erase
    the evidence gap this product is built around.
    """
    text = series.astype("object").where(series.notna(), None)
    return text.map(lambda value: None if value is None or not str(value).strip() else str(value))
