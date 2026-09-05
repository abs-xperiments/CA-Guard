"""What a signal is, and the knobs that govern it.

Two ideas matter here.

**Evidence, not just a score.** Every hit carries a dict of the actual facts
behind it. Phase 5's local model explains findings *from* that dict and may
state nothing outside it, so the guarantee that explanations are grounded is
built now, in the shape of the data, rather than bolted on later as a prompt
instruction.

**Thresholds live in one place.** A firm's approval limit, what counts as
material, how round is round — all configuration, all named, all recorded in
ADR-0004 and frozen before any held-out evaluation (ADR-0003 rule 4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SignalKind(StrEnum):
    """What a signal observed.

    Deliberately a separate vocabulary from the benchmark's ``AnomalyKind``.
    These are observations about a ledger; those are facts about how synthetic
    data was planted. Only the evaluation harness is allowed to relate them.
    """

    DUPLICATE_ENTRY = "duplicate_entry"
    ROUND_AMOUNT = "round_amount"
    OFF_HOURS_POSTING = "off_hours_posting"
    WEEKEND_POSTING = "weekend_posting"
    PERIOD_END_CONCENTRATION = "period_end_concentration"
    RARE_ACCOUNT_PAIR = "rare_account_pair"
    THRESHOLD_ADJACENT = "threshold_adjacent"
    MISSING_EVIDENCE = "missing_evidence"
    UNUSUAL_PREPARER_ACCOUNT = "unusual_preparer_account"
    POST_CLOSE_ENTRY = "post_close_entry"


@dataclass(frozen=True)
class SignalHit:
    """One voucher, flagged by one signal, with the facts behind it."""

    voucher_id: str
    kind: SignalKind
    strength: float
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"strength must be in [0, 1], got {self.strength}")
        if not self.reason.strip():
            raise ValueError("a hit without a reason cannot be reviewed")


@dataclass(frozen=True)
class DetectorConfig:
    """Firm-configurable thresholds.

    Defaults suit a mid-size Indian firm and are recorded in ADR-0004. They are
    *defaults*, not truths: a delegation limit differs between practices, and a
    detector that hardcoded the benchmark's own limit would be marking its own
    homework.
    """

    #: Delegation-of-authority limit. Entries just below it, unapproved, are of
    #: interest. Firm-specific — override per engagement.
    approval_limit_paise: int = 50_000_00

    #: How far below the limit still counts as "adjacent". Ten percent of a
    #: ₹50,000 limit. A band of a few hundred rupees would only catch someone
    #: hugging the line to the last rupee, which is not how a payment gets split.
    threshold_band_paise: int = 5_000_00

    #: Below this, an entry is too small to be worth a reviewer's attention.
    materiality_paise: int = 25_000_00

    #: An amount is "round" if it divides evenly by this and is at least
    #: :attr:`round_min_paise`. ₹10,000 catches manufactured figures without
    #: firing on every invoice that ends in a zero.
    round_step_paise: int = 10_000_00
    round_min_paise: int = 50_000_00

    #: An (account, amount) pair seen at least this many times is routine —
    #: a lease or an instalment — not a manufactured round figure.
    routine_repeat_count: int = 3

    #: Postings at or after the first hour, or before the second, are off-hours.
    off_hours_start: int = 22
    off_hours_end: int = 6

    #: Two entries this close together, identical in amount and accounts, look
    #: like a double payment. Wide enough to catch a re-run, narrow enough that
    #: a monthly instalment never qualifies.
    duplicate_window_days: int = 7

    #: Entries dated within this many days of year end get period-end scrutiny.
    period_end_window_days: int = 3

    #: An account pair is rare if it occurs no more than this many times, or in
    #: no more than this share of vouchers — whichever is larger. A fixed count
    #: does not scale: eight occurrences is common in a 200-voucher ledger and
    #: plainly rare in one of 40,000.
    rare_pair_max_count: int = 2
    rare_pair_max_share: float = 0.001

    #: If applying that ceiling would flag more than this share of the ledger,
    #: the signal abstains. On a chart of accounts with thousands of GL codes
    #: almost every pairing is rare, so "rare" stops distinguishing anything —
    #: the same reasoning that keeps the off-hours signal quiet on a source with
    #: no real posting times. Abstaining is more useful than flagging everything.
    rare_pair_max_flag_share: float = 0.10

    #: A preparer is off their patch when the account has a clear regular owner
    #: and this person is not it. Both halves are needed: with six preparers the
    #: average share is already 17%, so a bare share test flags almost everyone.
    #: The account must also be genuinely well used, or a one-off account would
    #: flag every person who ever touched it.
    #: Both a low share *and* few absolute entries. Share alone is not enough:
    #: an automated bank feed can hold 2% of a busy cash account while having
    #: posted to it thirty times, and thirty entries is not unfamiliarity.
    unfamiliar_preparer_max_share: float = 0.05
    unfamiliar_preparer_max_entries: int = 3
    dominant_owner_min_share: float = 0.50
    unfamiliar_preparer_min_account_entries: int = 8

    #: A posting lag beyond this suggests the entry was made after the close.
    post_close_lag_days: int = 45

    def __post_init__(self) -> None:
        if self.off_hours_start <= self.off_hours_end:
            raise ValueError(
                "off-hours must wrap midnight, e.g. start=22, end=6; "
                f"got start={self.off_hours_start}, end={self.off_hours_end}"
            )
        if self.threshold_band_paise >= self.approval_limit_paise:
            raise ValueError("threshold band must be smaller than the approval limit")
