"""Reading uploaded ledger files.

Deliberately boring and defensive: an upload is untrusted input, and the file
sizes a CA will hand us range from a few hundred rows to a full year's ledger.
Limits are explicit constants rather than buried magic numbers so that raising
them is a visible decision.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_ROWS = 2_000_000
SUPPORTED_SUFFIXES = frozenset({".csv", ".xlsx", ".xls", ".parquet"})


class IntakeError(ValueError):
    """A file we cannot or should not read. The message is shown to the user."""


def safe_suffix(filename: str | None) -> str:
    """The file's extension, or nothing — never anything that could be a path.

    An uploaded filename is untrusted. ``Path("..\\..\\windows\\x").suffix`` on
    POSIX returns ``".\\windows\\x"``, because a backslash is not a separator
    there; putting that into a temporary filename would traverse on Windows. So
    the suffix is matched against what we support rather than trusted.
    """
    candidate = Path(filename or "").suffix.lower()
    return candidate if candidate in SUPPORTED_SUFFIXES else ""


def read_table(path: Path, *, sheet: str | int = 0) -> pd.DataFrame:
    """Read a ledger export into a DataFrame, with everything left as text where possible.

    Values are read as strings so that account codes keep leading zeros and
    amounts are parsed once, by us, rather than twice with different guesses.
    """
    path = Path(path)
    if not path.is_file():
        raise IntakeError(f"File not found: {path.name}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IntakeError(
            f"Unsupported file type {suffix!r}. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise IntakeError(
            f"File is {size / 1024 / 1024:.0f} MB, above the "
            f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB limit"
        )

    try:
        if suffix == ".csv":
            frame = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
        elif suffix == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_excel(path, sheet_name=sheet, dtype=str)
    except Exception as exc:  # surface a readable message, not a traceback
        raise IntakeError(f"Could not read {path.name}: {exc}") from exc

    if isinstance(frame, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise IntakeError("Workbook has multiple sheets; specify which one to read")
    if len(frame) > MAX_ROWS:
        raise IntakeError(f"File has {len(frame):,} rows, above the {MAX_ROWS:,} limit")
    if frame.empty:
        raise IntakeError(f"{path.name} contains no rows")

    frame.columns = [str(c).strip() for c in frame.columns]
    return frame
