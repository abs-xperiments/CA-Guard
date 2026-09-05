"""One pass over the ledger, shared by every signal.

Each detector needs the same background facts — what a voucher totals, which
accounts it touches, how often a pairing occurs, whether a preparer usually
works on an account. Computing those once keeps ten signals from making ten
passes, and it puts the definition of "normal" in a single readable place.

Everything here is derived from the ledger in front of us. That is not only an
ADR-0003 requirement; it is what lets the same code work on a real client's
books, where there is no generator and no answer key.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

from caguard.schema import TimeFidelity

if TYPE_CHECKING:
    from collections.abc import Iterator

# Columns the voucher view exposes. Detectors read these by name.
VOUCHER_COLUMNS = (
    "voucher_date",
    "posted_at",
    "amount_paise",
    "accounts",
    "account_names",
    "document_ref",
    "evidence_lines",
    "line_count",
    "approved_by",
    "created_by",
    "is_manual",
    "is_post_close",
    "voucher_type",
    "narration",
    "time_fidelity",
)


@dataclass
class LedgerContext:
    """A ledger prepared for detection: the voucher view plus frequency tables."""

    vouchers: pd.DataFrame
    pair_counts: Counter[tuple[str, str]]
    preparer_account_counts: Counter[tuple[str, str]]
    account_amount_counts: Counter[tuple[str, int]]
    time_fidelity: TimeFidelity
    year_end: pd.Timestamp | None

    @property
    def has_posting_times(self) -> bool:
        """Whether posting timestamps carry a real hour.

        The VynFi corpus posts everything at ``00:00:00``. Any signal that reads
        the clock must check this first, or it will flag the entire population.
        """
        return self.time_fidelity == TimeFidelity.DATE_AND_TIME

    def __len__(self) -> int:
        return len(self.vouchers)

    def rows(self) -> Iterator[tuple[str, pd.Series]]:
        for voucher_id, row in self.vouchers.iterrows():
            yield str(voucher_id), row


def build_context(lines: pd.DataFrame) -> LedgerContext:
    """Collapse canonical lines into a voucher view and the frequency tables.

    ``lines`` must use the canonical column names produced by
    :mod:`caguard.schema` — that is the whole point of having one schema.
    """
    frame = lines.copy()
    frame["voucher_date"] = pd.to_datetime(frame["voucher_date"])
    frame["posted_at"] = pd.to_datetime(frame["posted_at"])
    frame["account_code"] = frame["account_code"].astype(str)

    grouped = frame.groupby("voucher_id", sort=True)
    vouchers = pd.DataFrame(
        {
            "voucher_date": grouped.voucher_date.first(),
            "posted_at": grouped.posted_at.first(),
            "amount_paise": grouped.debit_paise.sum(),
            "accounts": grouped.account_code.agg(frozenset),
            "account_names": grouped.account_name.agg(lambda s: sorted(set(s))),
            "document_ref": grouped.document_ref.agg(_first_present),
            "evidence_lines": grouped.document_ref.agg(lambda s: int(s.notna().sum())),
            "line_count": grouped.line_number.count(),
            "approved_by": grouped.approved_by.agg(_first_present),
            "created_by": grouped.created_by.first(),
            "is_manual": grouped.is_manual.max(),
            "is_post_close": grouped.is_post_close.max(),
            "voucher_type": grouped.voucher_type.first(),
            "narration": grouped.narration.agg(_first_present),
        }
    )
    vouchers["time_fidelity"] = _dominant_fidelity(frame).value

    return LedgerContext(
        vouchers=vouchers,
        pair_counts=_count_pairs(frame),
        preparer_account_counts=Counter(zip(frame.created_by, frame.account_code, strict=True)),
        account_amount_counts=_count_account_amounts(frame),
        time_fidelity=_dominant_fidelity(frame),
        year_end=_infer_year_end(vouchers),
    )


def _first_present(series: pd.Series) -> object | None:
    """The first non-null value, or None. Vouchers often carry the reference once."""
    present = series.dropna()
    return present.iloc[0] if len(present) else None


def _dominant_fidelity(frame: pd.DataFrame) -> TimeFidelity:
    """How much of the posting timestamp is real, for the ledger as a whole.

    Taken from the data rather than trusted from the column: a source can claim
    a real time and still post everything at midnight, and that is exactly the
    case this protects against.
    """
    posted = frame["posted_at"].dropna()
    if posted.empty:
        return TimeFidelity.UNKNOWN
    if (posted.dt.hour == 0).all() and (posted.dt.minute == 0).all():
        return TimeFidelity.DATE_ONLY
    return TimeFidelity.DATE_AND_TIME


def _count_pairs(frame: pd.DataFrame) -> Counter[tuple[str, str]]:
    """How often each debit/credit account pairing occurs across the ledger."""
    counts: Counter[tuple[str, str]] = Counter()
    for _, group in frame.groupby("voucher_id", sort=False):
        debited = sorted(set(group.loc[group.debit_paise > 0, "account_code"]))
        credited = sorted(set(group.loc[group.credit_paise > 0, "account_code"]))
        counts.update((d, c) for d in debited for c in credited)
    return counts


def _count_account_amounts(frame: pd.DataFrame) -> Counter[tuple[str, int]]:
    """How often an exact amount recurs on an account.

    A lease or an instalment posts the same figure every month. That repetition
    is what separates a routine round number from a manufactured one.
    """
    debits = frame.loc[frame.debit_paise > 0]
    return Counter(zip(debits.account_code, debits.debit_paise.astype(int), strict=True))


def _infer_year_end(vouchers: pd.DataFrame) -> pd.Timestamp | None:
    """The 31 March closing the fiscal year that most of the ledger falls in.

    Inferred rather than configured so the signal works on any uploaded period.
    """
    dates = vouchers["voucher_date"].dropna()
    if dates.empty:
        return None
    fy_start_years = dates.dt.year.where(dates.dt.month >= 4, dates.dt.year - 1)
    closing = pd.Timestamp(year=int(fy_start_years.mode().iloc[0]) + 1, month=3, day=31)
    return closing if isinstance(closing, pd.Timestamp) else None
