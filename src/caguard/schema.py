"""The canonical journal-entry schema — the single source of truth for shape.

Every ingestion path (Indian CSV/XLSX exports, the SAP-shaped VynFi corpus, the
project's own generator) converges here. Detectors in later phases read only
this, so they never learn the quirks of any one source.

Three decisions are baked in, each from a Phase 0 finding:

* **Money is integer paise** (see :mod:`caguard.money`) so vouchers balance exactly.
* **The line is the record; the voucher is the unit of review.** VynFi replicated
  document-level labels onto every line, inflating its apparent anomaly rate from
  7.6% to 20.9%. Aggregating to ``voucher_id`` is what keeps metrics honest.
* **``posted_at`` is optional and distinct from ``voucher_date``.** VynFi's posting
  timestamps are ``00:00:00`` on every row. A source without a real posting time
  must say so, not present midnight as fact — otherwise every row looks like an
  after-hours entry.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from caguard.money import paise_to_rupees

FY_PATTERN = re.compile(r"^FY(\d{4})-(\d{2})$")


class VoucherType(StrEnum):
    """Indian voucher types, plus a bucket for foreign sources."""

    JOURNAL = "journal"
    PAYMENT = "payment"
    RECEIPT = "receipt"
    CONTRA = "contra"
    SALES = "sales"
    PURCHASE = "purchase"
    DEBIT_NOTE = "debit_note"
    CREDIT_NOTE = "credit_note"
    OPENING_BALANCE = "opening_balance"
    OTHER = "other"


class AccountGroup(StrEnum):
    """Schedule III-flavoured grouping, coarse enough to be source-agnostic."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class TimeFidelity(StrEnum):
    """How much of ``posted_at`` is real.

    Exists because VynFi has date-only postings. A signal that depends on
    time-of-day must be able to ask, rather than assume, whether the hour means
    anything on this dataset.
    """

    DATE_AND_TIME = "date_and_time"
    DATE_ONLY = "date_only"
    UNKNOWN = "unknown"


NonNegPaise = Annotated[int, Field(ge=0, description="Amount in paise; never negative")]


class JournalLine(BaseModel):
    """One debit or credit line of a voucher."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    line_id: str = Field(min_length=1)
    voucher_id: str = Field(min_length=1)
    line_number: int = Field(ge=1)

    entity_id: str = Field(min_length=1, description="Company/branch the books belong to")
    fiscal_year: str = Field(pattern=FY_PATTERN.pattern, examples=["FY2024-25"])
    period: int = Field(ge=1, le=12, description="1 = April … 12 = March (Indian FY)")

    voucher_date: date = Field(description="Accounting date of the transaction")
    posted_at: datetime | None = Field(
        default=None, description="When it was actually entered; None if the source omits it"
    )
    time_fidelity: TimeFidelity = TimeFidelity.UNKNOWN

    voucher_type: VoucherType
    account_code: str = Field(min_length=1)
    account_name: str = Field(min_length=1)
    account_group: AccountGroup

    debit_paise: NonNegPaise = 0
    credit_paise: NonNegPaise = 0
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")

    created_by: str = Field(min_length=1, description="Preparer")
    approved_by: str | None = None

    document_ref: str | None = Field(
        default=None,
        description="Supporting document reference. Its ABSENCE is the evidence-gap signal.",
    )
    narration: str | None = None
    cost_centre: str | None = None

    is_manual: bool = False
    is_post_close: bool = False

    @model_validator(mode="after")
    def _exactly_one_side(self) -> Self:
        """A line is a debit or a credit — never both, never neither."""
        if bool(self.debit_paise) == bool(self.credit_paise):
            raise ValueError(
                f"line {self.line_id}: exactly one of debit/credit must be non-zero "
                f"(got debit={self.debit_paise}, credit={self.credit_paise})"
            )
        return self

    @model_validator(mode="after")
    def _period_matches_fiscal_year(self) -> Self:
        """The voucher date must fall inside the fiscal year and period claimed."""
        expected_fy = fiscal_year_of(self.voucher_date)
        if expected_fy != self.fiscal_year:
            raise ValueError(
                f"line {self.line_id}: voucher_date {self.voucher_date} falls in "
                f"{expected_fy}, not the declared {self.fiscal_year} "
                "(the Indian fiscal year starts on 1 April)"
            )
        expected = fiscal_period_of(self.voucher_date)
        if expected != self.period:
            raise ValueError(
                f"line {self.line_id}: voucher_date {self.voucher_date} is period "
                f"{expected}, not the declared {self.period}"
            )
        return self

    @property
    def amount_paise(self) -> int:
        """The line's magnitude, whichever side it sits on."""
        return self.debit_paise or self.credit_paise

    @property
    def signed_paise(self) -> int:
        """Debit positive, credit negative — the convention balance checks use."""
        return self.debit_paise - self.credit_paise

    @property
    def amount_rupees(self) -> Decimal:
        return paise_to_rupees(self.amount_paise)

    @property
    def has_evidence(self) -> bool:
        """Whether a supporting document is referenced at all."""
        return bool(self.document_ref and self.document_ref.strip())


class Voucher(BaseModel):
    """A balanced set of lines — the unit a reviewer actually looks at."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    voucher_id: str = Field(min_length=1)
    lines: list[JournalLine] = Field(min_length=1)

    @model_validator(mode="after")
    def _coherent_and_balanced(self) -> Self:
        mismatched = [ln.line_id for ln in self.lines if ln.voucher_id != self.voucher_id]
        if mismatched:
            raise ValueError(f"voucher {self.voucher_id}: foreign lines {mismatched}")

        imbalance = sum(ln.signed_paise for ln in self.lines)
        if imbalance != 0:
            raise ValueError(
                f"voucher {self.voucher_id}: debits and credits differ by "
                f"{imbalance} paise (double entry must net to exactly zero)"
            )
        return self

    @property
    def total_paise(self) -> int:
        """Voucher size: the debit side, which equals the credit side."""
        return sum(ln.debit_paise for ln in self.lines)

    @property
    def voucher_date(self) -> date:
        return self.lines[0].voucher_date

    @property
    def voucher_type(self) -> VoucherType:
        return self.lines[0].voucher_type

    @property
    def created_by(self) -> str:
        return self.lines[0].created_by

    @property
    def evidence_coverage(self) -> float:
        """Fraction of lines carrying a document reference.

        The evidence-gap signal in Phase 4 is built on this. Kept as a plain
        ratio here; the weighting that turns it into risk lives with the
        detectors, not with the schema.
        """
        return sum(ln.has_evidence for ln in self.lines) / len(self.lines)


def fiscal_year_of(day: date) -> str:
    """Indian fiscal year containing ``day``. April–March, so 2025-03-31 is FY2024-25."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"FY{start}-{(start + 1) % 100:02d}"


def fiscal_period_of(day: date) -> int:
    """Period number within the Indian fiscal year: April = 1 … March = 12."""
    return day.month - 3 if day.month >= 4 else day.month + 9
