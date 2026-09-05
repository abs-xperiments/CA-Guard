"""The statistical layer: Benford conformity and robust amount outliers.

Two different kinds of thing live here, and the distinction matters.

**Benford's law describes a distribution**, not a transaction. Asking whether one
voucher violates Benford is meaningless — a single number has no distribution.
It is therefore reported per *account*, as a conformity statistic a reviewer can
act on, and fed to the model as a feature. It never flags an individual voucher.

**A robust amount outlier is a per-voucher statement** and is a signal like any
other. It uses median absolute deviation rather than standard deviation, because
a ledger contains a handful of very large entries and those inflate a standard
deviation until nothing looks unusual any more.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from caguard.detect.context import LedgerContext
from caguard.detect.features import amount_deviation
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind
from caguard.money import format_inr

#: Expected first-digit frequencies under Benford's law.
BENFORD_EXPECTED: tuple[float, ...] = tuple(
    float(np.log10(1 + 1 / digit)) for digit in range(1, 10)
)

#: Conventional reading of the mean absolute deviation statistic for first
#: digits (Nigrini). Above 0.015 the fit is generally called non-conforming.
BENFORD_MAD_CLOSE = 0.006
BENFORD_MAD_ACCEPTABLE = 0.012
BENFORD_MAD_NONCONFORMING = 0.015


@dataclass(frozen=True)
class BenfordResult:
    """First-digit conformity for one account."""

    account_code: str
    sample_size: int
    observed: tuple[float, ...]
    mad: float

    @property
    def conformity(self) -> str:
        if self.mad <= BENFORD_MAD_CLOSE:
            return "close"
        if self.mad <= BENFORD_MAD_ACCEPTABLE:
            return "acceptable"
        if self.mad <= BENFORD_MAD_NONCONFORMING:
            return "marginal"
        return "non-conforming"

    def summary(self) -> str:
        return (
            f"Account {self.account_code}: {self.conformity} fit to Benford's law "
            f"(MAD {self.mad:.4f} over {self.sample_size:,} entries)"
        )


def benford_by_account(
    ctx: LedgerContext, config: DetectorConfig | None = None
) -> list[BenfordResult]:
    """First-digit conformity per account, for accounts with enough entries.

    A population diagnostic. It tells a reviewer which accounts to look at as a
    whole; it does not accuse any individual entry.
    """
    cfg = config or DetectorConfig()
    amounts = ctx.vouchers.amount_paise.astype("float64").clip(lower=1.0)
    digits = np.floor(amounts / np.power(10.0, np.floor(np.log10(amounts)))).clip(1, 9)
    account_of = ctx.vouchers.debit_accounts.map(lambda s: min(s) if s else "")

    results: list[BenfordResult] = []
    for account, group in digits.groupby(account_of, sort=True):
        if not account or len(group) < cfg.benford_min_sample:
            continue
        counts = group.value_counts(normalize=True)
        observed = tuple(float(counts.get(float(d), 0.0)) for d in range(1, 10))
        mad = float(np.mean([abs(o - e) for o, e in zip(observed, BENFORD_EXPECTED, strict=True)]))
        results.append(BenfordResult(str(account), len(group), observed, round(mad, 6)))
    return sorted(results, key=lambda r: -r.mad)


def detect_amount_outlier(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """An amount far from what this account normally carries.

    Deviation is measured against the account's own median, so a ₹40 lakh
    machinery purchase is unremarkable on Plant & Machinery and notable on
    Travelling & Conveyance.
    """
    deviation = amount_deviation(ctx)
    account_of = ctx.vouchers.debit_accounts.map(lambda s: min(s) if s else "")

    hits: list[SignalHit] = []
    for voucher_id, score in deviation.items():
        if score < cfg.amount_deviation_threshold:
            continue
        row = ctx.vouchers.loc[voucher_id]
        hits.append(
            SignalHit(
                voucher_id=str(voucher_id),
                kind=SignalKind.AMOUNT_OUTLIER,
                strength=float(min(1.0, score / (cfg.amount_deviation_threshold * 3))),
                reason=(
                    f"{format_inr(int(row.amount_paise))} is {score:.1f} robust deviations "
                    f"from the usual amount on account {account_of[voucher_id]}."
                ),
                evidence={
                    "amount_paise": int(row.amount_paise),
                    "account_code": str(account_of[voucher_id]),
                    "robust_deviations": round(float(score), 2),
                    "threshold": cfg.amount_deviation_threshold,
                    "measure": "median absolute deviation of log10 amount",
                },
            )
        )
    return hits


def run_statistical_signals(
    ctx: LedgerContext, config: DetectorConfig | None = None
) -> list[SignalHit]:
    """Every per-voucher statistical signal, sorted for reproducibility."""
    cfg = config or DetectorConfig()
    hits = detect_amount_outlier(ctx, cfg)
    return sorted(hits, key=lambda hit: (hit.voucher_id, hit.kind.value))


def benford_frame(results: list[BenfordResult]) -> pd.DataFrame:
    """Benford results as a table, for reporting."""
    return pd.DataFrame(
        [
            {
                "account_code": r.account_code,
                "sample_size": r.sample_size,
                "mad": r.mad,
                "conformity": r.conformity,
            }
            for r in results
        ]
    )
