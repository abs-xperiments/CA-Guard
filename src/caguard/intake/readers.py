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


#: Encodings tried, in order, for a CSV that is not valid UTF-8. Excel on
#: Windows saves "CSV" in the system code page (CP1252 for English locales), and
#: some accounting exports write UTF-16 with a byte-order mark. Latin-1 is
#: deliberately absent: it decodes *any* bytes, so a binary file would be
#: "read" as nonsense instead of being refused.
CSV_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "cp1252")

_KIND = {".csv": "a CSV file", ".xlsx": "an Excel workbook", ".xls": "an Excel 97-2003 workbook"}


def read_table(
    path: Path, *, sheet: str | int = 0, display_name: str | None = None
) -> pd.DataFrame:
    """Read a ledger export into a DataFrame, with everything left as text where possible.

    Values are read as strings so that account codes keep leading zeros and
    amounts are parsed once, by us, rather than twice with different guesses.

    ``display_name`` is the name the user knows the file by. Messages use it
    rather than ``path``, which for an upload is an internal temporary file the
    user has never heard of.
    """
    path = Path(path)
    name = display_name or path.name
    if not path.is_file():
        raise IntakeError(f"File not found: {name}")

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise IntakeError(
            f"Unsupported file type {suffix!r}. Supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    size = path.stat().st_size
    if size == 0:
        raise IntakeError(f"{name} is empty. Nothing was saved.")
    if size > MAX_UPLOAD_BYTES:
        raise IntakeError(
            f"{name} is {size / 1024 / 1024:.0f} MB, above the "
            f"{MAX_UPLOAD_BYTES // 1024 // 1024} MB limit. Nothing was saved."
        )

    encoding: str | None = None
    try:
        if suffix == ".csv":
            frame, encoding = _read_csv(path, name)
        elif suffix == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_excel(path, sheet_name=sheet, dtype=str)
    except IntakeError:
        raise
    except Exception as exc:  # surface a readable message, not a traceback
        kind = _KIND.get(suffix, "a Parquet file")
        raise IntakeError(
            f"{name} could not be read as {kind}. Check that it opens in Excel and was "
            f"saved in that format, not renamed from another one. Nothing was saved. "
            f"(Detail: {type(exc).__name__})"
        ) from exc

    if isinstance(frame, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise IntakeError("Workbook has multiple sheets; specify which one to read")
    if len(frame) > MAX_ROWS:
        raise IntakeError(f"{name} has {len(frame):,} rows, above the {MAX_ROWS:,} limit")
    if frame.empty:
        raise IntakeError(f"{name} has column headings but no rows. Nothing was saved.")

    frame.columns = [str(c).strip() for c in frame.columns]
    if encoding is not None:
        # Recorded so the intake notice can say how the file was decoded.
        frame.attrs["encoding"] = encoding
    return frame


def _read_csv(path: Path, name: str) -> tuple[pd.DataFrame, str]:
    """Decode a CSV in the first encoding that fits it, and say which one."""
    with path.open("rb") as handle:
        head = handle.read(4096)
    candidates: tuple[str, ...] = CSV_ENCODINGS
    if head.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates = ("utf-16",)
    elif b"\x00" in head:
        # Null bytes in a text file mean it is not a text file at all.
        raise IntakeError(
            f"{name} does not look like a CSV file: it contains binary data. If it came "
            "from Excel, upload the .xlsx itself. Nothing was saved."
        )

    for encoding in candidates:
        try:
            frame = pd.read_csv(
                path, dtype=str, keep_default_na=False, na_values=[""], encoding=encoding
            )
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError as exc:
            raise IntakeError(f"{name} has no columns. Nothing was saved.") from exc
        return frame, encoding

    raise IntakeError(
        f"{name} is not readable text in any supported encoding (UTF-8, UTF-16 or "
        'Windows-1252). Re-save it from Excel as "CSV UTF-8" and upload again. '
        "Nothing was saved."
    )
