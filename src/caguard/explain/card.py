"""The explanation a reviewer reads first: structured, deterministic, checkable.

This is the answer to "Explain this finding". It is built entirely from the
finding's recorded facts, the ledger it came from and fixed wording — no model
is involved, so there is nothing to hallucinate and nothing to wait for. A local
model may add prose on top (see :mod:`caguard.explain.service`); it never
supplies a fact that appears here.

It answers, in order, what a reviewer under time pressure asks:

1. **Why is this here?** — one sentence, then each signal with its working.
2. **What evidence exists?** — present, missing, not expected, or simply not in
   the file, which are four different things.
3. **Compared with what?** — the account's ordinary range and similar entries.
4. **What do I look at next?** — review steps, never conclusions.
5. **What must I not conclude?** — stated plainly, every time.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel

from caguard.detect.context import LedgerContext
from caguard.detect.types import DetectorConfig, SignalHit, SignalKind
from caguard.explain.vocabulary import contribution_level, is_minor, vocabulary
from caguard.money import format_inr
from caguard.review.comparables import account_profile, similar_entries
from caguard.review.finding import Finding

LIMITATION = (
    "This finding means the entry deserves review. It does not, by itself, establish "
    "an error, a misstatement or wrongdoing — that judgement is the reviewer's."
)

#: Shown with the priority, because contributions do not add up and a reviewer
#: who tries to sum them will otherwise think the numbers are wrong.
PRIORITY_METHOD = (
    "Each signal's contribution is its weight × strength. Signals combine as "
    "independent reasons (priority = 1 − Π(1 − contribution)), so they do not add up; "
    "missing evidence then lifts what is left."
)

EvidenceState = Literal["present", "missing", "not_expected", "not_in_file"]


class WorkingRow(BaseModel):
    label: str
    value: str


class SignalCard(BaseModel):
    kind: str
    title: str
    reason: str
    contribution: float
    level: str
    minor: bool
    working: list[WorkingRow]
    standard: str | None


class EvidenceItem(BaseModel):
    name: str
    state: EvidenceState
    detail: str


class ProfileOut(BaseModel):
    account_code: str
    account_name: str
    entries: int
    median: str
    typical_range: str


class ComparableOut(BaseModel):
    voucher_id: str
    voucher_date: str
    amount_display: str
    has_document: bool
    narration: str | None
    created_by: str | None
    is_flagged: bool
    basis: str


class ExplanationCard(BaseModel):
    summary: str
    limitation: str
    priority: float
    priority_method: str
    evidence_uplift: float
    signals: list[SignalCard]
    evidence: list[EvidenceItem]
    evidence_present: int
    evidence_expected: int
    profile: ProfileOut | None
    similar: list[ComparableOut]
    next_steps: list[str]


def build_card(
    finding: Finding,
    ctx: LedgerContext,
    *,
    account_names: Mapping[str, str],
    not_in_file: frozenset[str] | set[str] = frozenset(),
    flagged: frozenset[str] | set[str] = frozenset(),
    config: DetectorConfig | None = None,
) -> ExplanationCard:
    """Everything a reviewer needs to understand one finding, without a model."""
    cfg = config or DetectorConfig()
    ordered = sorted(finding.signals, key=lambda h: -finding.contributions.get(h.kind, 0.0))
    cards = [_signal_card(hit, finding, account_names) for hit in ordered]
    evidence = _evidence_items(finding, ctx, not_in_file, cfg)
    expected = [item for item in evidence if item.state in {"present", "missing"}]

    profile = account_profile(ctx, finding.voucher_id)
    major = [card for card in cards if not card.minor] or cards[:1]

    return ExplanationCard(
        summary=_summary(major),
        limitation=LIMITATION,
        priority=round(finding.priority, 4),
        priority_method=PRIORITY_METHOD,
        evidence_uplift=round(float(finding.contributions.get("evidence_gap", 0.0)), 4),  # type: ignore[call-overload]
        signals=cards,
        evidence=evidence,
        evidence_present=sum(1 for item in expected if item.state == "present"),
        evidence_expected=len(expected),
        profile=(
            ProfileOut(
                account_code=profile.account_code,
                account_name=account_names.get(profile.account_code, ""),
                entries=profile.entries,
                median=format_inr(profile.median_paise),
                typical_range=f"{format_inr(profile.low_paise)} – {format_inr(profile.high_paise)}",
            )
            if profile
            else None
        ),
        similar=[
            ComparableOut(
                voucher_id=c.voucher_id,
                voucher_date=_date(c.voucher_date),
                amount_display=format_inr(c.amount_paise),
                has_document=c.has_document,
                narration=c.narration,
                created_by=c.created_by,
                is_flagged=c.is_flagged,
                basis=c.basis,
            )
            for c in similar_entries(ctx, finding.voucher_id, flagged)
        ],
        next_steps=_next_steps(major),
    )


# --- signals -----------------------------------------------------------------


def _signal_card(hit: SignalHit, finding: Finding, names: Mapping[str, str]) -> SignalCard:
    words = vocabulary(hit.kind)
    contribution = round(float(finding.contributions.get(hit.kind, 0.0)), 4)
    return SignalCard(
        kind=hit.kind.value,
        title=words.title,
        reason=hit.reason,
        contribution=contribution,
        level=contribution_level(contribution),
        minor=is_minor(contribution),
        working=[WorkingRow(label=k, value=v) for k, v in _working(hit, names)],
        standard=words.standard,
    )


def _working(hit: SignalHit, names: Mapping[str, str]) -> list[tuple[str, str]]:
    """The calculation behind one signal, from what the signal recorded."""
    e: dict[str, Any] = dict(hit.evidence)
    kind = hit.kind

    if kind is SignalKind.AMOUNT_OUTLIER:
        rows = [
            ("Amount", _inr(e.get("amount_paise"))),
            ("Account", _account(e.get("account_code"), names)),
        ]
        if "account_median_paise" in e:
            rows += [
                ("Usual amount (median)", _inr(e["account_median_paise"])),
                (
                    "Typical range (middle 80%)",
                    f"{_inr(e['typical_low_paise'])} – {_inr(e['typical_high_paise'])}",
                ),
                ("Entries compared", f"{int(e['entries_compared']):,}"),
            ]
        rows += [
            (
                "How far from usual",
                f"{e.get('robust_deviations')}× the account's typical spread "
                f"(flagged at {e.get('threshold')}× or more)",
            ),
            (
                "Measured how",
                "Against the account's median on a logarithmic scale, so a few very "
                "large entries cannot distort what counts as usual",
            ),
        ]
        return rows

    if kind is SignalKind.MISSING_EVIDENCE:
        return [
            (
                "Lines with a document reference",
                f"{e.get('lines_with_evidence')} of {e.get('lines')}",
            ),
            ("Amount", _inr(e.get("amount_paise"))),
            ("Materiality threshold used", _inr(e.get("materiality_paise"))),
            ("Manual entry", "Yes" if e.get("is_manual") else "No"),
        ]

    if kind is SignalKind.DUPLICATE_ENTRY:
        return [
            ("Amount", _inr(e.get("amount_paise"))),
            (
                "Earlier voucher",
                f"{e.get('earlier_voucher_id')} dated {_date(e.get('earlier_date'))}",
            ),
            ("Days apart", str(e.get("days_apart"))),
        ]

    if kind is SignalKind.PERIOD_END_CONCENTRATION:
        missing = e.get("missing") or []
        return [
            ("Voucher date", _date(e.get("voucher_date"))),
            ("Year end", _date(e.get("year_end"))),
            ("Days before close", str(e.get("days_before_close"))),
            ("Missing", ", ".join(missing) if missing else "nothing"),
        ]

    if kind is SignalKind.POST_CLOSE_ENTRY:
        return [
            ("Voucher date", _date(e.get("voucher_date"))),
            ("Entered", _datetime(e.get("posted_at"))),
            ("Delay", f"{e.get('lag_days')} days"),
            ("Marked post-close in the file", "Yes" if e.get("source_flag") else "No"),
        ]

    if kind is SignalKind.RARE_ACCOUNT_PAIR:
        return [
            ("Debit", _account(e.get("debit_account"), names)),
            ("Credit", _account(e.get("credit_account"), names)),
            (
                "Seen together",
                f"{e.get('times_seen')} time(s) in "
                f"{int(e.get('vouchers_in_ledger', 0)):,} vouchers",
            ),
            ("Counted as rare below", f"{e.get('rare_below')} occurrences"),
        ]

    if kind is SignalKind.OFF_HOURS_POSTING:
        window = e.get("working_window") or ["?", "?"]
        return [
            ("Entered", _datetime(e.get("posted_at"))),
            ("Working hours assumed", f"{window[0]}:00 – {window[1]}:00"),
        ]

    if kind is SignalKind.WEEKEND_POSTING:
        return [
            ("Date", f"{_date(e.get('date'))} ({e.get('weekday')})"),
            ("Based on", str(e.get("basis", "")).replace("_", " ")),
        ]

    if kind is SignalKind.ROUND_AMOUNT:
        accounts = e.get("accounts") or []
        return [
            ("Amount", _inr(e.get("amount_paise"))),
            ("A multiple of", _inr(e.get("round_step_paise"))),
            ("Times this figure recurs on these accounts", str(e.get("times_seen_on_account"))),
            ("Accounts", ", ".join(_account(a, names) for a in accounts)),
        ]

    if kind is SignalKind.THRESHOLD_ADJACENT:
        return [
            ("Amount", _inr(e.get("amount_paise"))),
            ("Approval limit", _inr(e.get("approval_limit_paise"))),
            ("Below the limit by", _inr(e.get("shortfall_paise"))),
        ]

    if kind is SignalKind.UNUSUAL_PREPARER_ACCOUNT:
        share = e.get("regular_owner_share")
        return [
            ("Entered by", str(e.get("created_by"))),
            ("Account", _account(e.get("account_code"), names)),
            (
                "Usually posted by",
                f"{e.get('regular_owner')}"
                + (f" ({float(share):.0%} of entries)" if share is not None else ""),
            ),
            ("Entries by this preparer here", str(e.get("entries_by_this_preparer"))),
        ]

    if kind is SignalKind.ML_ANOMALY:
        features = e.get("top_features") or {}
        return [
            ("Model", str(e.get("model_version"))),
            ("Score", f"{e.get('score')} (flagged above {e.get('threshold')})"),
            ("Driven mostly by", ", ".join(str(f).replace("_", " ") for f in features)),
            ("Note", "Reinforces other signals only; never raises a finding alone."),
        ]

    return [(str(k).replace("_", " "), str(v)) for k, v in e.items()]


# --- evidence -------------------------------------------------------------------


def _evidence_items(
    finding: Finding,
    ctx: LedgerContext,
    not_in_file: frozenset[str] | set[str],
    cfg: DetectorConfig,
) -> list[EvidenceItem]:
    """Present, missing, not expected, or not in the file — never conflated.

    A ledger exported without a document column makes every entry look
    undocumented. That is a fact about the file, not about the client, and the
    reviewer must be able to tell the two apart.
    """
    score = finding.evidence
    row = ctx.vouchers.loc[finding.voucher_id] if finding.voucher_id in ctx.vouchers.index else None
    lines = int(row.line_count) if row is not None else len(finding.line_ids)
    with_doc = int(row.evidence_lines) if row is not None else 0

    if "document_ref" in not_in_file:
        document = EvidenceItem(
            name="Supporting document",
            state="not_in_file",
            detail="The uploaded file has no document-reference column, so this cannot be checked.",
        )
    elif score.has_document:
        detail = (
            f"Reference on all {lines} lines."
            if with_doc >= lines
            else f"Reference on {with_doc} of {lines} lines."
        )
        document = EvidenceItem(name="Supporting document", state="present", detail=detail)
    else:
        document = EvidenceItem(
            name="Supporting document",
            state="missing",
            detail=f"No document reference on any of the {lines} lines.",
        )

    limit = format_inr(cfg.approval_limit_paise)
    if "approved_by" in not_in_file:
        approval = EvidenceItem(
            name="Approval",
            state="not_in_file",
            detail="The uploaded file has no approver column, so this cannot be checked.",
        )
    elif score.has_approval:
        approver = _text(row.approved_by) if row is not None else None
        approval = EvidenceItem(
            name="Approval",
            state="present",
            detail=f"Approved by {approver}." if approver else "An approver is recorded.",
        )
    elif not score.approval_expected:
        approval = EvidenceItem(
            name="Approval",
            state="not_expected",
            detail=f"Not required: below the approval limit of {limit}.",
        )
    else:
        approval = EvidenceItem(
            name="Approval",
            state="missing",
            detail=f"Above the approval limit of {limit}, and no approver is recorded.",
        )

    if "narration" in not_in_file:
        narration = EvidenceItem(
            name="Narration",
            state="not_in_file",
            detail="The uploaded file has no narration column.",
        )
    elif score.has_narration:
        narration = EvidenceItem(
            name="Narration", state="present", detail="A narration is recorded."
        )
    else:
        narration = EvidenceItem(name="Narration", state="missing", detail="No narration recorded.")

    return [document, approval, narration]


# --- words ------------------------------------------------------------------------


def _summary(cards: list[SignalCard]) -> str:
    phrases = [vocabulary(card.kind).phrase for card in cards]
    if not phrases:
        return "Prioritised for review."
    joined = phrases[0] if len(phrases) == 1 else ", ".join(phrases[:-1]) + " and " + phrases[-1]
    lead = "mainly because it" if len(phrases) > 2 else "because it"
    return f"Prioritised for review {lead} {joined}."


def _next_steps(cards: list[SignalCard]) -> list[str]:
    steps: list[str] = []
    for card in cards:
        step = vocabulary(card.kind).next_step
        if step not in steps:
            steps.append(step)
    return steps


def _inr(paise: object) -> str:
    try:
        return format_inr(int(paise))  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError):
        return "—"


def _account(code: object, names: Mapping[str, str]) -> str:
    if code is None:
        return "—"
    code = str(code)
    name = names.get(code)
    return f"{name} ({code})" if name else code


def _date(iso: object) -> str:
    """``2025-03-31`` → ``31-03-2025``."""
    text = str(iso or "")[:10]
    parts = text.split("-")
    return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else (text or "—")


def _datetime(value: object) -> str:
    if value is None or str(value) in {"", "NaT", "None"}:
        return "not recorded"
    text = str(value)
    return f"{_date(text[:10])} {text[11:16]}".strip()


def _text(value: object) -> str | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    text = str(value).strip()
    return text or None
