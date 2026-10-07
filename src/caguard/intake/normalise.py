"""Turning a real ledger export into the canonical schema.

A CA's file does not look like our schema. Tally writes "Vch No." and
"Particulars", an accountant's spreadsheet writes whatever the person who built
it wrote, and none of them carry a fiscal period or an account group. Before
this module existed the upload path simply assumed canonical column names and
failed with ``KeyError: 'voucher_date'`` — reported to the user as "Internal
Server Error", which tells them nothing and suggests the fault is ours to find.

So this does three things, and reports on all of them:

* **Maps** what it recognises, using :mod:`caguard.intake.mapping`.
* **Derives** what it can — the fiscal year and period follow from the date, the
  line number from position within the voucher, an account code from the ledger
  name when the file has no codes.
* **Defaults** what is genuinely absent, and *says so*, because a reviewer needs
  to know that "no supporting document" might mean "this file has no such
  column" rather than "this entry has no document".

That last distinction matters more than any of the mechanics. Silently
defaulting a missing column to empty would turn a limitation of the file into a
finding about the client.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from caguard.intake.mapping import ColumnMapping, has_amount_columns, infer_mapping
from caguard.schema import (
    AccountGroup,
    JournalLine,
    TimeFidelity,
    VoucherType,
    fiscal_period_of,
    fiscal_year_of,
)

#: Columns without which no amount of derivation produces a ledger.
ESSENTIAL = ("voucher_id", "voucher_date", "account_name")

#: Canonical columns already denominated in paise. Anything mapped from a plain
#: "Debit"/"Credit" column is rupees and must be multiplied — getting this
#: backwards is a hundred-fold error, so the two cases never share a code path.
PAISE_COLUMNS = frozenset({"debit_paise", "credit_paise"})

_VOUCHER_TYPE_WORDS: dict[str, VoucherType] = {
    "sales": VoucherType.SALES,
    "sale": VoucherType.SALES,
    "purchase": VoucherType.PURCHASE,
    "purc": VoucherType.PURCHASE,
    "receipt": VoucherType.RECEIPT,
    "payment": VoucherType.PAYMENT,
    "contra": VoucherType.CONTRA,
    "journal": VoucherType.JOURNAL,
    "jrnl": VoucherType.JOURNAL,
    "debit note": VoucherType.DEBIT_NOTE,
    "credit note": VoucherType.CREDIT_NOTE,
    "opening": VoucherType.OPENING_BALANCE,
}


class NormalisationError(ValueError):
    """The file cannot become a ledger. The message is shown to the user."""


@dataclass
class NormalisationReport:
    """What happened to each column, in language a reviewer can act on."""

    mapped: dict[str, str] = field(default_factory=dict)
    derived: list[str] = field(default_factory=list)
    defaulted: list[str] = field(default_factory=list)
    ignored: list[str] = field(default_factory=list)
    ambiguous: dict[str, list[str]] = field(default_factory=dict)
    rows_in: int = 0
    rows_out: int = 0
    #: How a CSV was decoded, when the reader recorded it.
    encoding: str | None = None
    #: Rows whose voucher date was present but could not be read as a date.
    unreadable_dates: int = 0

    @property
    def notes(self) -> list[str]:
        """Caveats worth putting in front of the reviewer before they trust the queue."""
        messages: list[str] = []
        if self.unreadable_dates:
            messages.append(
                f"{self.unreadable_dates:,} row(s) had a voucher date CA-Guard could not read "
                "and were left out of the review. Check the date column in the file."
            )
        if self.encoding and self.encoding != "utf-8-sig":
            messages.append(
                f"This file was not UTF-8; it was read as {self.encoding.upper()}. "
                "Check that names and narrations display correctly."
            )
        if "document_ref" in self.defaulted:
            messages.append(
                "This file has no supporting-document column, so every entry looks "
                "undocumented. Evidence findings will not be meaningful until one is "
                "supplied."
            )
        if "approved_by" in self.defaulted:
            messages.append("This file has no approver column, so approval cannot be checked.")
        if "posted_at" in self.defaulted:
            messages.append(
                "This file records no posting time, so out-of-hours entries cannot be identified."
            )
        return messages

    def summary(self) -> str:
        parts = [f"{len(self.mapped)} columns recognised"]
        if self.derived:
            parts.append(f"{len(self.derived)} derived")
        if self.defaulted:
            parts.append(f"{len(self.defaulted)} not present in the file")
        if self.ignored:
            parts.append(f"{len(self.ignored)} ignored")
        return ", ".join(parts)


@dataclass
class NormalisedLedger:
    lines: pd.DataFrame
    report: NormalisationReport


def normalise(frame: pd.DataFrame, *, overrides: dict[str, str] | None = None) -> NormalisedLedger:
    """Convert an arbitrary ledger export into the canonical schema.

    Raises :class:`NormalisationError` with an explanation a person can act on
    when the file is missing something no derivation can replace.
    """
    if frame.empty:
        raise NormalisationError("The file contains no rows.")

    # The reader keeps blank lines so that row numbers match what Excel shows.
    # Drop them here, keeping the original index, which is what source_row uses.
    frame = frame.dropna(how="all")
    if frame.empty:
        raise NormalisationError("The file contains no rows.")

    # A file already in canonical shape passes through with only typing applied.
    if _is_canonical(frame):
        from caguard.intake.coerce import to_canonical_types

        typed = to_canonical_types(frame)
        typed["source_row"] = _source_rows(frame.index)
        report = NormalisationReport(
            mapped={column: column for column in frame.columns},
            rows_in=len(frame),
            rows_out=len(typed),
            encoding=frame.attrs.get("encoding"),
        )
        return NormalisedLedger(typed, report)

    mapping = infer_mapping(list(frame.columns), overrides=overrides)
    _fall_back_to_posting_date(mapping)
    report = NormalisationReport(
        mapped=dict(mapping.resolved),
        ignored=list(mapping.unmapped),
        ambiguous=dict(mapping.ambiguous),
        rows_in=len(frame),
        encoding=frame.attrs.get("encoding"),
    )
    _check_usable(mapping, report)

    renamed = frame.rename(columns=mapping.resolved)
    out = pd.DataFrame(index=renamed.index)
    out["source_row"] = _source_rows(renamed.index)

    _carry_text(renamed, out, report)
    _amounts(renamed, out, report)
    _dates(renamed, out, report)
    _identity(renamed, out, report)
    _classification(renamed, out, report)
    _flags(renamed, out, report)

    out = out.dropna(subset=["voucher_id", "voucher_date"]).reset_index(drop=True)
    if out.empty:
        raise NormalisationError(
            "No usable rows: every row was missing a voucher reference or a date."
        )

    _line_numbers(out)
    report.rows_out = len(out)
    return NormalisedLedger(out, report)


# --- steps -------------------------------------------------------------------


#: The spreadsheet row of the first data record: row 1 is the header.
FIRST_DATA_ROW = 2


def _source_rows(index: pd.Index) -> pd.Series:
    """Each line's row in the original file, as a spreadsheet would number it.

    This is what lets a finding be traced to "ledger.xlsx, row 1,842" — the
    question a reviewer actually asks, and the one a regenerated file cannot
    answer.
    """
    return pd.Series(index.to_numpy() + FIRST_DATA_ROW, index=index, dtype="int64")


def _is_canonical(frame: pd.DataFrame) -> bool:
    """Every canonical column is present, so only typing is needed.

    All of them, not just the four that identify a ledger: a file with our
    headers but no document column used to take this path, skip the defaults
    the mapping path applies, and crash the analysis. Anything less than the
    full set goes through mapping, which fills and *records* what is missing.
    """
    return set(JournalLine.model_fields) <= set(frame.columns)


def _fall_back_to_posting_date(mapping: ColumnMapping) -> None:
    """Use the posting date as the voucher date when a file has only one.

    Some exports — SAP among them — carry a posting date and no separate
    document date. Refusing those would be pedantry: the posting date is the
    date the entry belongs to, and saying so is better than saying no.
    """
    values = set(mapping.resolved.values())
    if "voucher_date" in values or "posted_at" not in values:
        return
    header = next(h for h, field in mapping.resolved.items() if field == "posted_at")
    mapping.resolved[header] = "voucher_date"


def _check_usable(mapping: ColumnMapping, report: NormalisationReport) -> None:
    missing = [column for column in ESSENTIAL if column not in mapping.resolved.values()]
    has_amount = has_amount_columns(mapping.resolved.values())

    problems: list[str] = []
    if missing:
        problems.append("could not find " + ", ".join(_human(name) for name in missing))
    if not has_amount:
        problems.append("could not find a debit/credit or amount column")

    if problems:
        seen = ", ".join(sorted(report.mapped)) or "none"
        raise NormalisationError(
            "This file does not look like a ledger CA-Guard can read: "
            + "; ".join(problems)
            + f". Columns recognised: {seen}."
            + (f" Ambiguous: {', '.join(report.ambiguous)}." if report.ambiguous else "")
        )


def _carry_text(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    for column, default in (
        ("account_name", None),
        ("narration", None),
        ("document_ref", None),
        ("approved_by", None),
        ("cost_centre", None),
        ("created_by", "unknown"),
        ("entity_id", "UNKNOWN"),
    ):
        if column in src.columns:
            out[column] = _clean_text(src[column])
        else:
            out[column] = default
            report.defaulted.append(column)

    if "currency" in src.columns:
        out["currency"] = _clean_text(src["currency"]).fillna("INR")
    else:
        out["currency"] = "INR"
    if "currency" not in src.columns:
        report.defaulted.append("currency")


def _amounts(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    """Debits and credits, converted to paise.

    A mapped ``Debit`` column is rupees; a canonical ``debit_paise`` is already
    paise. Confusing the two is a hundred-fold error, so they are handled apart.
    """
    if "debit_paise" in src.columns or "credit_paise" in src.columns:
        out["debit_paise"] = _paise(src.get("debit_paise"))
        out["credit_paise"] = _paise(src.get("credit_paise"))
        return

    if "debit" in src.columns or "credit" in src.columns:
        out["debit_paise"] = _rupees_to_paise(src.get("debit"))
        out["credit_paise"] = _rupees_to_paise(src.get("credit"))
        report.derived.append("debit_paise / credit_paise (converted from rupees)")
        return

    # A single signed amount column: positive is a debit, negative a credit.
    amount = _rupees_to_paise(src.get("amount"))
    out["debit_paise"] = amount.clip(lower=0)
    out["credit_paise"] = (-amount).clip(lower=0)
    report.derived.append("debit_paise / credit_paise (split from a signed amount)")


def _dates(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    dates = parse_dates(src["voucher_date"])
    out["voucher_date"] = dates
    present = _has_text(pd.Series(src["voucher_date"]))
    report.unreadable_dates = int((dates.isna() & present).sum())

    if "posted_at" in src.columns:
        out["posted_at"] = parse_dates(src["posted_at"])
        stamps = pd.Series(pd.to_datetime(out["posted_at"], errors="coerce"))
        midnight_only = bool(
            stamps.dt.hour.fillna(0).eq(0).all() and stamps.dt.minute.fillna(0).eq(0).all()
        )
        real_time = bool(stamps.notna().any()) and not midnight_only
        out["time_fidelity"] = (
            TimeFidelity.DATE_AND_TIME.value if real_time else TimeFidelity.DATE_ONLY.value
        )
    else:
        out["posted_at"] = pd.NaT
        out["time_fidelity"] = TimeFidelity.UNKNOWN.value
        report.defaulted.append("posted_at")

    valid = dates.notna()
    out["fiscal_year"] = [
        fiscal_year_of(day.date()) if present else ""
        for day, present in zip(dates, valid, strict=True)
    ]
    out["period"] = [
        fiscal_period_of(day.date()) if present else 1
        for day, present in zip(dates, valid, strict=True)
    ]
    report.derived.extend(["fiscal_year", "period"])


#: ``2024-04-01``, ``2024/04/01``, optionally with a time: read year-first.
_ISO_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")

#: Excel stores dates as days since 30 December 1899. A bare number in this
#: range in a date column is one of those (1954 to 2119).
_EXCEL_SERIAL = (20_000, 80_000)


def parse_dates(values: object) -> pd.Series:
    """Dates as an Indian ledger writes them, without guessing from the first row.

    pandas, given a whole column, infers *one* format from the first value.
    With ``dayfirst=True`` an ISO ``2024-04-01`` is then read as year-day-month:
    1 April silently becomes 4 January, and every later date with a day above
    12 fails and its row is dropped. Exports from Excel arrive as exactly that
    ISO text. So each value is parsed on its own terms:

    - year-first values (ISO, as Excel and most systems write) as year-month-day;
    - everything else day-first, value by value — the Indian convention, so
      ``03/05/2024`` is 3 May;
    - bare Excel serial numbers as Excel dates.
    """
    texts = [_as_text(v) for v in pd.Series(values)]  # pyright: ignore[reportArgumentType]
    text = pd.Series(texts, dtype=object)
    parsed = pd.Series(pd.NaT, index=text.index, dtype="datetime64[ns]")

    iso = pd.Series([bool(_ISO_RE.match(t)) for t in texts], index=text.index)
    if iso.any():
        dashed = pd.Series([t.replace("/", "-") for t in texts], index=text.index)
        parsed[iso] = pd.to_datetime(dashed[iso], errors="coerce", format="ISO8601")

    numeric = pd.Series(pd.to_numeric(text, errors="coerce"), index=text.index)
    low, high = _EXCEL_SERIAL
    serial = ~iso & (numeric >= low) & (numeric <= high)
    if serial.any():
        parsed[serial] = pd.to_datetime(numeric[serial], unit="D", origin="1899-12-30")

    rest = ~iso & ~serial & (text != "")
    if rest.any():
        parsed[rest] = pd.to_datetime(text[rest], errors="coerce", dayfirst=True, format="mixed")
    return parsed


def _as_text(value: object) -> str:
    if value is None or value is pd.NaT or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip()


def _has_text(values: pd.Series) -> pd.Series:
    return pd.Series([_as_text(v) != "" for v in values], index=values.index)


def _identity(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    out["voucher_id"] = _clean_text(src["voucher_id"])
    if "account_code" in src.columns:
        out["account_code"] = _clean_text(src["account_code"]).fillna("UNKNOWN")
    else:
        # No codes in the file: use the ledger name itself, so account-level
        # signals still work and a reviewer still recognises what they are seeing.
        out["account_code"] = out["account_name"].fillna("UNKNOWN")
        report.derived.append("account_code (from the ledger name)")


def _classification(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    if "voucher_type" in src.columns:
        out["voucher_type"] = [_voucher_type(value) for value in src["voucher_type"]]
        report.derived.append("voucher_type (matched to known types)")
    else:
        out["voucher_type"] = VoucherType.OTHER.value
        report.defaulted.append("voucher_type")

    if "account_group" in src.columns:
        out["account_group"] = [_account_group(value) for value in src["account_group"]]
    else:
        # Unknown rather than guessed. A wrong group would quietly mislead every
        # account-level comparison built on top of it.
        out["account_group"] = AccountGroup.ASSET.value
        report.defaulted.append("account_group")


def _flags(src: pd.DataFrame, out: pd.DataFrame, report: NormalisationReport) -> None:
    for column in ("is_manual", "is_post_close"):
        if column in src.columns:
            out[column] = (
                src[column].astype(str).str.strip().str.lower().isin({"true", "yes", "1", "y"})
            )
        else:
            out[column] = False
            report.defaulted.append(column)


def _line_numbers(out: pd.DataFrame) -> None:
    """Number the lines within each voucher, and give every line an id."""
    out["line_number"] = out.groupby("voucher_id").cumcount() + 1
    out["line_id"] = (
        out["voucher_id"].astype(str) + "-" + out["line_number"].astype(str).str.zfill(2)
    )


# --- helpers -----------------------------------------------------------------


def _clean_text(series: object) -> pd.Series:
    if series is None:
        return pd.Series(dtype="object")
    column = pd.Series(series)  # pyright: ignore[reportArgumentType]
    text = column.astype("object").where(column.notna(), None)
    return text.map(
        lambda value: None if value is None or not str(value).strip() else str(value).strip()
    )


def _paise(series: object) -> pd.Series:
    """A column already in paise: whole numbers, taken as they are."""
    if series is None:
        return pd.Series(0, dtype="int64")
    numeric = pd.Series(pd.to_numeric(pd.Series(series), errors="coerce")).fillna(0)  # pyright: ignore[reportArgumentType]
    return numeric.round().astype("int64")


def _rupees_to_paise(series: object) -> pd.Series:
    """Rupees to paise, tolerating the commas and currency symbols a file carries."""
    if series is None:
        return pd.Series(0, dtype="int64")
    cleaned = (
        pd.Series(series)  # pyright: ignore[reportArgumentType]
        .astype(str)
        .str.replace(r"[₹,\s]", "", regex=True)
        .str.replace(r"^\((.*)\)$", r"-\1", regex=True)  # (1,200) means -1200
    )
    numeric = pd.Series(pd.to_numeric(cleaned, errors="coerce")).fillna(0.0)
    return (numeric * 100).round().astype("int64")


def _voucher_type(value: object) -> str:
    text = str(value or "").strip().lower()
    for word, kind in _VOUCHER_TYPE_WORDS.items():
        if word in text:
            return kind.value
    return VoucherType.OTHER.value


def _account_group(value: object) -> str:
    text = str(value or "").strip().lower()
    for group in AccountGroup:
        if group.value in text:
            return group.value
    if "revenue" in text or "income" in text:
        return AccountGroup.INCOME.value
    return AccountGroup.ASSET.value


def _human(column: str) -> str:
    return {
        "voucher_id": "a voucher number",
        "voucher_date": "a date",
        "account_name": "a ledger or account name",
    }.get(column, column)
