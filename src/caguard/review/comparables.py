"""What else in this ledger looks like the flagged entry.

A reviewer's first question about an odd entry is "compared with what?". This
module answers it with entries from the same book: the account's ordinary range
and the few vouchers most like this one. It is deterministic — the same ledger
always gives the same comparables — and it uses the grouping the amount signal
itself uses (a voucher's primary debit account), so the context shown is the
context the detector measured against.

It compares within the uploaded ledger only. Nothing here is "prior-year
history", and the card says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from caguard.detect.context import LedgerContext

#: How many similar entries to show. Enough to compare; few enough to read.
DEFAULT_SIMILAR = 3


@dataclass(frozen=True)
class AccountProfile:
    """The ordinary shape of one account's entries in this ledger."""

    account_code: str
    entries: int
    median_paise: int
    low_paise: int
    high_paise: int


@dataclass(frozen=True)
class Comparable:
    voucher_id: str
    voucher_date: str
    amount_paise: int
    has_document: bool
    narration: str | None
    created_by: str | None
    is_flagged: bool
    #: Why it was chosen, in words: "same accounts", "same debit account".
    basis: str


def primary_accounts(ctx: LedgerContext) -> pd.Series:
    """Each voucher's primary debit account — the detector's comparison key."""
    return ctx.vouchers.debit_accounts.map(lambda s: min(s) if s else "")


def account_profile(ctx: LedgerContext, voucher_id: str) -> AccountProfile | None:
    """How entries on this voucher's primary account ordinarily look."""
    if voucher_id not in ctx.vouchers.index:
        return None
    accounts = primary_accounts(ctx)
    account = str(accounts.at[voucher_id])
    if not account:
        return None
    amounts = ctx.vouchers.amount_paise[accounts == account].astype("float64")
    return AccountProfile(
        account_code=account,
        entries=len(amounts),
        median_paise=round(float(amounts.median())),
        low_paise=round(float(amounts.quantile(0.10))),
        high_paise=round(float(amounts.quantile(0.90))),
    )


def similar_entries(
    ctx: LedgerContext,
    voucher_id: str,
    flagged: frozenset[str] | set[str],
    *,
    limit: int = DEFAULT_SIMILAR,
) -> list[Comparable]:
    """The entries most like this one: same accounts first, then nearest in amount.

    Ranking, in order: the exact same debit and credit accounts beat merely the
    same debit account; then the closest amount (on a log scale, so ₹10,000 vs
    ₹12,000 counts as closer than ₹10 lakh vs ₹10.2 lakh); then the nearest date.
    """
    vouchers = ctx.vouchers
    if voucher_id not in vouchers.index:
        return []
    target = vouchers.loc[voucher_id]
    accounts = primary_accounts(ctx)
    pool = vouchers[(accounts == accounts.at[voucher_id]) & (vouchers.index != voucher_id)]
    if pool.empty:
        return []

    same_pair = (pool.debit_accounts == target.debit_accounts) & (
        pool.credit_accounts == target.credit_accounts
    )
    target_log = math.log10(max(int(target.amount_paise), 1))
    pool_log = pool.amount_paise.clip(lower=1).astype("float64").map(math.log10)
    distance = (pool_log - target_log).abs()
    days = (pool.voucher_date - target.voucher_date).abs().dt.days

    ranked = pd.DataFrame({"pair": ~same_pair, "distance": distance, "days": days})
    order = ranked.sort_values(["pair", "distance", "days"], kind="mergesort").index[:limit]

    return [
        Comparable(
            voucher_id=str(other),
            voucher_date=str(pd.Timestamp(vouchers.at[other, "voucher_date"]).date()),
            amount_paise=int(vouchers.at[other, "amount_paise"]),
            has_document=bool(vouchers.at[other, "evidence_lines"] > 0),
            narration=_text(vouchers.at[other, "narration"]),
            created_by=_text(vouchers.at[other, "created_by"]),
            is_flagged=str(other) in flagged,
            basis="same accounts" if bool(same_pair[other]) else "same debit account",
        )
        for other in order
    ]


def _text(value: object) -> str | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    text = str(value).strip()
    return text or None
