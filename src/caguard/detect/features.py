"""The voucher feature matrix used by the statistical layer and the model.

Every column is derived from the uploaded ledger. Nothing here can reach the
benchmark or its planted truth — the same rule as the rest of ``detect``, and
the reason the isolation test covers this package strictly.

The column order is pinned. An Isolation Forest is sensitive to what it is fed
and in what order, so a stable order is what makes two runs comparable and a
recorded model version meaningful.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from caguard.detect.context import LedgerContext

#: Pinned feature order. Appending is safe; reordering or removing changes what
#: a stored model means, so it goes with a version bump in `model.py`.
FEATURE_NAMES: tuple[str, ...] = (
    "log_amount",
    "line_count",
    "first_digit",
    "trailing_zeros",
    "is_round_thousand",
    "posting_hour",
    "has_posting_time",
    "day_of_week",
    "days_to_year_end",
    "posting_lag_days",
    "is_manual",
    "is_post_close",
    "has_evidence",
    "evidence_coverage",
    "has_approver",
    "account_pair_rarity",
    "preparer_familiarity",
    "amount_deviation",
)


def build_features(ctx: LedgerContext) -> pd.DataFrame:
    """Voucher-level features, indexed by voucher id, in :data:`FEATURE_NAMES` order."""
    vouchers = ctx.vouchers
    amount = vouchers.amount_paise.astype("float64").clip(lower=1.0)

    posted = vouchers.posted_at
    has_time = ctx.has_posting_times
    frame = pd.DataFrame(index=vouchers.index)

    frame["log_amount"] = np.log10(amount)
    frame["line_count"] = vouchers.line_count.astype("float64")
    frame["first_digit"] = _first_digit(amount)
    frame["trailing_zeros"] = _trailing_zeros(vouchers.amount_paise)
    frame["is_round_thousand"] = (vouchers.amount_paise % 1_000_00 == 0).astype("float64")

    # A source without real posting times must say so rather than contribute a
    # column of midnights that the model would read as a pattern.
    frame["posting_hour"] = posted.dt.hour.astype("float64") if has_time else -1.0
    frame["has_posting_time"] = float(has_time)
    frame["day_of_week"] = vouchers.voucher_date.dt.dayofweek.astype("float64")

    year_end = ctx.year_end
    frame["days_to_year_end"] = (
        (year_end - vouchers.voucher_date).dt.days.astype("float64")
        if year_end is not None
        else 0.0
    )
    frame["posting_lag_days"] = (
        (posted.dt.normalize() - vouchers.voucher_date.dt.normalize())
        .dt.days.astype("float64")
        .fillna(0.0)
    )

    frame["is_manual"] = vouchers.is_manual.astype("float64")
    frame["is_post_close"] = vouchers.is_post_close.astype("float64")
    frame["has_evidence"] = (vouchers.evidence_lines > 0).astype("float64")
    frame["evidence_coverage"] = (
        vouchers.evidence_lines / vouchers.line_count.clip(lower=1)
    ).astype("float64")
    frame["has_approver"] = vouchers.approved_by.notna().astype("float64")

    frame["account_pair_rarity"] = _pair_rarity(ctx)
    frame["preparer_familiarity"] = _preparer_familiarity(ctx)
    frame["amount_deviation"] = amount_deviation(ctx)

    ordered = frame.loc[:, list(FEATURE_NAMES)]
    return pd.DataFrame(ordered).fillna(0.0).astype("float64")


def amount_deviation(ctx: LedgerContext) -> pd.Series:
    """How far a voucher's amount sits from the usual amount on its accounts.

    Measured in median-absolute-deviation units rather than standard deviations.
    A ledger contains a handful of very large entries, and those inflate a
    standard deviation until nothing looks unusual any more; the median is not
    moved by them.
    """
    vouchers = ctx.vouchers
    amounts = np.log10(vouchers.amount_paise.astype("float64").clip(lower=1.0))

    account_of = vouchers.debit_accounts.map(lambda s: min(s) if s else "")
    grouped = amounts.groupby(account_of)
    median = grouped.transform("median")
    mad = grouped.transform(lambda s: (s - s.median()).abs().median())

    # 0.6745 puts MAD on the same scale as a standard deviation for normal data.
    scale = (mad / 0.6745).replace(0.0, np.nan)
    return ((amounts - median).abs() / scale).fillna(0.0)


def _first_digit(amount: pd.Series) -> pd.Series:
    """Leading significant digit — the quantity Benford's law describes."""
    exponent = np.floor(np.log10(amount))
    return np.floor(amount / np.power(10.0, exponent)).clip(1, 9)


def _trailing_zeros(paise: pd.Series) -> pd.Series:
    """How many zeros an amount ends in. A blunt but effective roundness measure."""
    counts = pd.Series(0.0, index=paise.index)
    remaining = paise.astype("int64").abs()
    active = remaining > 0
    for _ in range(10):
        divisible = active & (remaining % 10 == 0)
        if not divisible.any():
            break
        counts[divisible] += 1
        remaining = remaining.where(~divisible, remaining // 10)
    return counts


def _pair_rarity(ctx: LedgerContext) -> pd.Series:
    """Negative log frequency of the voucher's rarest account pairing."""
    total = max(len(ctx), 1)

    def rarity(row: tuple[frozenset[str], frozenset[str]]) -> float:
        debited, credited = row
        counts = [ctx.pair_counts.get((d, c), 0) for d in sorted(debited) for c in sorted(credited)]
        seen = min((c for c in counts if c > 0), default=1)
        return float(-np.log10(seen / total))

    return pd.Series(
        [
            rarity(pair)
            for pair in zip(ctx.vouchers.debit_accounts, ctx.vouchers.credit_accounts, strict=True)
        ],
        index=ctx.vouchers.index,
    )


def _preparer_familiarity(ctx: LedgerContext) -> pd.Series:
    """Smallest share of any of the voucher's accounts held by its preparer."""
    totals: dict[str, int] = {}
    for (_person, account), count in ctx.preparer_account_counts.items():
        totals[account] = totals.get(account, 0) + count

    shares: list[float] = []
    for person, accounts in zip(ctx.vouchers.created_by, ctx.vouchers.accounts, strict=True):
        values = [
            ctx.preparer_account_counts.get((person, account), 0) / totals[account]
            for account in accounts
            if totals.get(account)
        ]
        shares.append(min(values) if values else 1.0)
    return pd.Series(shares, index=ctx.vouchers.index)
