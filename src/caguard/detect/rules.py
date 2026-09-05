"""The ten deterministic audit-review signals.

Each is a pure function of the prepared ledger and the configuration: same
input, same hits, always. That matters for more than tidiness — a reviewer who
re-opens an engagement must see the same queue, and an evaluation that cannot be
re-run cannot be published.

These are framed throughout as **review heuristics**, drawn from characteristics
SA 240 associates with journal entries warranting attention. None of them
determines that anything is wrong; each says only "a person should look at
this, and here is why".

The hard part of every rule below is not finding the pattern. It is *not* firing
on the legitimate entry that shares the pattern — the round rent, the monthly
instalment, the documented year-end depreciation. Those cases drive most of the
conditions here.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise

import pandas as pd

from caguard.detect.context import LedgerContext
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind
from caguard.money import format_inr

Detector = Callable[[LedgerContext, DetectorConfig], list[SignalHit]]


def detect_duplicate_entry(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """The same amount, to the same accounts, twice within a few days.

    The window is what separates duplication from recurrence. A rent payment or
    a loan instalment repeats identically every month by contract; a double
    payment happens within days of the first. Widening this window past a week
    would turn every standing instruction into a false positive.
    """
    hits: list[SignalHit] = []
    frame = ctx.vouchers
    keys = list(zip(frame.amount_paise, frame.accounts, strict=True))
    buckets: dict[tuple[int, frozenset[str]], list[tuple[str, pd.Timestamp]]] = {}
    for (voucher_id, row), key in zip(frame.iterrows(), keys, strict=True):
        buckets.setdefault(key, []).append((str(voucher_id), row.voucher_date))

    for (amount, _accounts), members in buckets.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda m: m[1])
        for (earlier_id, earlier_date), (later_id, later_date) in pairwise(members):
            gap = (later_date - earlier_date).days
            if 0 <= gap <= cfg.duplicate_window_days:
                hits.append(
                    SignalHit(
                        voucher_id=later_id,
                        kind=SignalKind.DUPLICATE_ENTRY,
                        strength=1.0 - gap / (cfg.duplicate_window_days + 1),
                        reason=(
                            f"Same amount {format_inr(int(amount))} posted to the same "
                            f"accounts {gap} day(s) after {earlier_id}."
                        ),
                        evidence={
                            "amount_paise": int(amount),
                            "days_apart": gap,
                            "earlier_voucher_id": earlier_id,
                            "earlier_date": str(earlier_date.date()),
                        },
                    )
                )
    return hits


def detect_round_amount(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """A large, exactly round figure that is not a routine recurring charge.

    Roundness alone is a poor signal: rent, retainers and instalments are round
    because a contract fixed them. The discriminator is repetition — if this
    exact amount has hit this account several times across the period, it is a
    standing arrangement, not a manufactured number.
    """
    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        amount = int(row.amount_paise)
        if amount < cfg.round_min_paise or amount % cfg.round_step_paise != 0:
            continue

        repeats = max(
            (ctx.account_amount_counts.get((code, amount), 0) for code in row.accounts),
            default=0,
        )
        if repeats >= cfg.routine_repeat_count:
            continue  # a lease or an instalment, not a manufactured figure

        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.ROUND_AMOUNT,
                strength=0.7,
                reason=(
                    f"{format_inr(amount)} is an exactly round amount and this figure "
                    f"does not recur on these accounts (seen {repeats} time(s))."
                ),
                evidence={
                    "amount_paise": amount,
                    "round_step_paise": cfg.round_step_paise,
                    "times_seen_on_account": repeats,
                    "accounts": sorted(row.accounts),
                },
            )
        )
    return hits


def detect_off_hours_posting(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """Entered late at night or before the working day.

    Returns nothing when the source has no real posting time. The VynFi corpus
    timestamps every one of its 667,584 lines at midnight; reading that as fact
    would flag the entire population and produce a queue of pure noise.
    """
    if not ctx.has_posting_times:
        return []

    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        if pd.isna(row.posted_at):
            continue
        hour = int(row.posted_at.hour)
        if hour >= cfg.off_hours_start or hour < cfg.off_hours_end:
            hits.append(
                SignalHit(
                    voucher_id=voucher_id,
                    kind=SignalKind.OFF_HOURS_POSTING,
                    strength=0.8,
                    reason=(
                        f"Entered at {row.posted_at:%H:%M}, outside the working day "
                        f"({cfg.off_hours_end:02d}:00–{cfg.off_hours_start:02d}:00)."
                    ),
                    evidence={
                        "posted_at": str(row.posted_at),
                        "hour": hour,
                        "working_window": [cfg.off_hours_end, cfg.off_hours_start],
                    },
                )
            )
    return hits


def detect_weekend_posting(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:  # noqa: ARG001
    """Someone was entering vouchers on a Sunday.

    Two deliberate choices. **Sunday only** — Saturday is an ordinary working day
    in most Indian practices, and treating "the weekend" as one thing would flag
    a normal week's work. And it reads the *posting* day rather than the voucher
    date, because the concern is when a person was working, not which day the
    transaction belongs to: a month-end provision dated Sunday 31st but entered
    on Monday is entirely routine.
    """
    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        when = row.posted_at if ctx.has_posting_times and not pd.isna(row.posted_at) else None
        basis = "posted" if when is not None else "dated"
        if when is None:
            when = row.voucher_date
        if pd.isna(when) or when.dayofweek != 6:
            continue
        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.WEEKEND_POSTING,
                strength=0.6,
                reason=f"Entry {basis} on Sunday {when:%d-%m-%Y}, when the office is closed.",
                evidence={
                    "basis": basis,
                    "date": str(when.date()),
                    "weekday": "Sunday",
                    "voucher_date": str(row.voucher_date.date()),
                },
            )
        )
    return hits


def detect_period_end_concentration(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """A manual year-end entry that is missing its document or its approval.

    Being dated 31 March is not itself suspicious — depreciation and provisions
    belong there. What warrants a look is a manual year-end adjustment with no
    supporting document and nobody's approval on it.
    """
    if ctx.year_end is None:
        return []

    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        if pd.isna(row.voucher_date):
            continue
        days_to_close = (ctx.year_end - row.voucher_date).days
        if not 0 <= days_to_close <= cfg.period_end_window_days or not row.is_manual:
            continue

        missing = [
            label
            for label, value in (
                ("supporting document", row.document_ref),
                ("approval", row.approved_by),
            )
            if value is None or (isinstance(value, float) and pd.isna(value))
        ]
        if not missing:
            continue  # documented and approved — an ordinary year-end entry

        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.PERIOD_END_CONCENTRATION,
                strength=0.85,
                reason=(
                    f"Manual entry dated {row.voucher_date:%d-%m-%Y}, at the year end, "
                    f"with no {' and no '.join(missing)}."
                ),
                evidence={
                    "voucher_date": str(row.voucher_date.date()),
                    "year_end": str(ctx.year_end.date()),
                    "days_before_close": days_to_close,
                    "missing": missing,
                },
            )
        )
    return hits


def detect_rare_account_pair(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """An account combination that almost never occurs in this ledger.

    Rarity is measured inside the uploaded data, so the signal adapts to each
    client's chart of accounts instead of relying on a fixed list of "suspicious"
    ledgers that would be wrong for the next engagement.
    """
    ceiling = max(cfg.rare_pair_max_count, round(len(ctx) * cfg.rare_pair_max_share))
    hits: list[SignalHit] = []

    if _would_flag_most_of_the_ledger(ctx, ceiling, cfg):
        # A ledger whose chart of accounts is mostly long-tail makes every pairing
        # look rare. Saying nothing is more honest than saying everything.
        return hits

    for voucher_id, row in ctx.rows():
        pairs = [
            (pair, count)
            for pair, count in (
                (p, ctx.pair_counts.get(p, 0))
                for p in _pairs_within(row.debit_accounts, row.credit_accounts)
            )
            if 0 < count <= ceiling
        ]
        if not pairs:
            continue

        (debit, credit), count = min(pairs, key=lambda item: item[1])
        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.RARE_ACCOUNT_PAIR,
                strength=0.75,
                reason=(
                    f"Accounts {debit} and {credit} appear together only "
                    f"{count} time(s) in a ledger of {len(ctx):,} vouchers."
                ),
                evidence={
                    "debit_account": debit,
                    "credit_account": credit,
                    "times_seen": count,
                    "rare_below": ceiling,
                    "vouchers_in_ledger": len(ctx),
                    "account_names": row.account_names,
                },
            )
        )
    return hits


def detect_threshold_adjacent(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """Just under the approval limit, and unapproved.

    Sitting below a limit is unremarkable on its own — most payments do. It is
    the combination with a missing approver that is consistent with structuring
    a payment to stay beneath the next level of authority.
    """
    floor = cfg.approval_limit_paise - cfg.threshold_band_paise
    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        amount = int(row.amount_paise)
        approved = row.approved_by is not None and not (
            isinstance(row.approved_by, float) and pd.isna(row.approved_by)
        )
        if not (floor <= amount < cfg.approval_limit_paise) or approved:
            continue

        shortfall = cfg.approval_limit_paise - amount
        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.THRESHOLD_ADJACENT,
                strength=0.8,
                reason=(
                    f"{format_inr(amount)} falls {format_inr(shortfall)} below the "
                    f"{format_inr(cfg.approval_limit_paise)} approval limit and carries "
                    "no approver."
                ),
                evidence={
                    "amount_paise": amount,
                    "approval_limit_paise": cfg.approval_limit_paise,
                    "shortfall_paise": shortfall,
                    "approved_by": None,
                },
            )
        )
    return hits


def detect_missing_evidence(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """A material manual entry with no supporting document at all.

    This is the evidence gap the project treats as a first-class concern. Both
    qualifiers matter: bank charges auto-posted by a feed are never
    voucher-backed and are immaterial, and flagging them would bury the entries
    that genuinely lack support.
    """
    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        amount = int(row.amount_paise)
        has_evidence = row.evidence_lines > 0
        if has_evidence or amount < cfg.materiality_paise or not row.is_manual:
            continue

        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.MISSING_EVIDENCE,
                strength=0.9,
                reason=(
                    f"Manual entry of {format_inr(amount)} with no supporting document "
                    f"reference on any of its {int(row.line_count)} lines."
                ),
                evidence={
                    "amount_paise": amount,
                    "materiality_paise": cfg.materiality_paise,
                    "lines": int(row.line_count),
                    "lines_with_evidence": int(row.evidence_lines),
                    "is_manual": True,
                },
            )
        )
    return hits


def detect_unusual_preparer_account(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """An account with a clear regular owner, touched by someone who is not them.

    "Normal" is each preparer's own history in this ledger, so the signal needs
    no org chart and works on a client we have never seen. It deliberately needs
    a *dominant* owner rather than merely a low share: with six people on the
    team the average share of any account is already 17%, so a bare share test
    would flag almost every voucher in the book.
    """
    hits: list[SignalHit] = []
    account_totals: dict[str, int] = {}
    owner_share: dict[str, tuple[str, float]] = {}
    for (_person, account), count in ctx.preparer_account_counts.items():
        account_totals[account] = account_totals.get(account, 0) + count
    for (person, account), count in ctx.preparer_account_counts.items():
        share = count / account_totals[account]
        if share > owner_share.get(account, ("", 0.0))[1]:
            owner_share[account] = (person, share)

    for voucher_id, row in ctx.rows():
        person = row.created_by
        unfamiliar = [
            account
            for account in sorted(row.accounts)
            if account_totals.get(account, 0) >= cfg.unfamiliar_preparer_min_account_entries
            and owner_share.get(account, ("", 0.0))[1] >= cfg.dominant_owner_min_share
            and owner_share[account][0] != person
            and ctx.preparer_account_counts.get((person, account), 0)
            <= max(
                1,
                min(
                    cfg.unfamiliar_preparer_max_entries,
                    cfg.unfamiliar_preparer_max_share * account_totals[account],
                ),
            )
        ]
        if not unfamiliar:
            continue

        account = unfamiliar[0]
        seen = ctx.preparer_account_counts.get((person, account), 0)
        owner, share = owner_share[account]
        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.UNUSUAL_PREPARER_ACCOUNT,
                strength=0.7,
                reason=(
                    f"Account {account} is normally handled by {owner} ({share:.0%} of its "
                    f"{account_totals[account]} entries), but this voucher was posted by "
                    f"{person}, who has touched it {seen} time(s)."
                ),
                evidence={
                    "created_by": person,
                    "account_code": account,
                    "regular_owner": owner,
                    "regular_owner_share": round(share, 3),
                    "entries_by_this_preparer": seen,
                    "entries_on_account_total": account_totals[account],
                },
            )
        )
    return hits


def detect_post_close_entry(ctx: LedgerContext, cfg: DetectorConfig) -> list[SignalHit]:
    """Dated inside the period but entered long after it closed."""
    hits: list[SignalHit] = []
    for voucher_id, row in ctx.rows():
        lag = (
            None
            if pd.isna(row.posted_at) or pd.isna(row.voucher_date)
            else (row.posted_at.normalize() - row.voucher_date.normalize()).days
        )
        flagged = bool(row.is_post_close)
        late = lag is not None and lag > cfg.post_close_lag_days
        if not (flagged or late):
            continue

        reason = (
            f"Dated {row.voucher_date:%d-%m-%Y} but entered {lag} days later."
            if late
            else f"Marked as posted after the books were closed ({row.voucher_date:%d-%m-%Y})."
        )
        hits.append(
            SignalHit(
                voucher_id=voucher_id,
                kind=SignalKind.POST_CLOSE_ENTRY,
                strength=0.85,
                reason=reason,
                evidence={
                    "voucher_date": str(row.voucher_date.date()),
                    "posted_at": None if pd.isna(row.posted_at) else str(row.posted_at),
                    "lag_days": lag,
                    "source_flag": flagged,
                },
            )
        )
    return hits


def _pairs_within(debited: frozenset[str], credited: frozenset[str]) -> list[tuple[str, str]]:
    """The pairings this voucher actually makes, in the direction it makes them.

    Direction matters. Dr Sundry Creditors / Cr Bank is how every vendor payment
    is written; the reverse is a refund from a supplier and is genuinely rare.
    Looking up both directions and taking the rarer one flagged ordinary
    payments as unusual pairings — 18% of the ledger.
    """
    return [(d, c) for d in sorted(debited) for c in sorted(credited)]


def _would_flag_most_of_the_ledger(ctx: LedgerContext, ceiling: int, cfg: DetectorConfig) -> bool:
    """Whether rarity has stopped discriminating on this ledger.

    Measured on the pairings themselves rather than by running the rule twice:
    if most pairings in the book fall under the ceiling, the ledger simply has a
    long-tail chart of accounts and "rare" describes the norm.
    """
    if not ctx.pair_counts:
        return True
    rare = sum(1 for count in ctx.pair_counts.values() if count <= ceiling)
    return rare / len(ctx.pair_counts) > 1 - cfg.rare_pair_max_flag_share


#: Every signal, in the order a reviewer sees them. Registry rather than
#: discovery: adding a detector should be a deliberate, reviewable edit.
DETECTORS: dict[SignalKind, Detector] = {
    SignalKind.DUPLICATE_ENTRY: detect_duplicate_entry,
    SignalKind.ROUND_AMOUNT: detect_round_amount,
    SignalKind.OFF_HOURS_POSTING: detect_off_hours_posting,
    SignalKind.WEEKEND_POSTING: detect_weekend_posting,
    SignalKind.PERIOD_END_CONCENTRATION: detect_period_end_concentration,
    SignalKind.RARE_ACCOUNT_PAIR: detect_rare_account_pair,
    SignalKind.THRESHOLD_ADJACENT: detect_threshold_adjacent,
    SignalKind.MISSING_EVIDENCE: detect_missing_evidence,
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: detect_unusual_preparer_account,
    SignalKind.POST_CLOSE_ENTRY: detect_post_close_entry,
}
