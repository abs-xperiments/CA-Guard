"""How each signal is spoken about — one place, so nothing can drift.

The finding card, the deterministic explanation and the guard all read from
here. If the card calls something "Posted after close", the guard looks for the
same idea in a model's prose, and the next step a reviewer is offered is the
one written for that signal.

**Suggested steps are review procedures, never conclusions.** Each says what a
reviewer could look at next. None says what the answer will be.

**Standards are guidance, not compliance claims.** Where a signal corresponds
to a characteristic named in a public ICAI Standard on Auditing, the standard
is named so a reviewer can connect the observation to their own working
papers. Where no standard names the characteristic, none is claimed. See
`docs/RESEARCH_SA_MAPPING.md` for sources.
"""

from __future__ import annotations

from dataclasses import dataclass

from caguard.detect.types import SignalKind

#: Below this weighted strength a signal is "also noted" rather than a reason
#: in its own right. It keeps the ML layer — which ADR-0005 found adds nothing
#: on its own — from appearing as a headline reason at a 2% contribution.
MINOR_CONTRIBUTION = 0.05

#: Contribution bands shown to a reviewer, on the signal's weighted strength.
HIGH_CONTRIBUTION = 0.60
MEDIUM_CONTRIBUTION = 0.30


@dataclass(frozen=True)
class SignalVocabulary:
    title: str
    #: Completes "Prioritised for review because it …".
    phrase: str
    next_step: str
    #: Words whose presence shows a piece of prose has mentioned this concern.
    cues: tuple[str, ...]
    standard: str | None = None


VOCABULARY: dict[SignalKind, SignalVocabulary] = {
    SignalKind.MISSING_EVIDENCE: SignalVocabulary(
        title="No supporting document",
        phrase="has no supporting document",
        next_step=(
            "Obtain the supporting document (invoice, contract or approval note) and "
            "agree the amount, date and account to it."
        ),
        cues=("document", "support", "invoice", "unsupported"),
        standard="SA 500 (audit evidence); SA 240 (entries with little or no explanation)",
    ),
    SignalKind.DUPLICATE_ENTRY: SignalVocabulary(
        title="Possible duplicate",
        phrase="may repeat an earlier entry",
        next_step=(
            "Compare with the earlier voucher shown and check whether the two relate to "
            "separate transactions — for example, two invoices — before treating either "
            "as a duplicate."
        ),
        cues=("duplicate", "earlier", "repeat", "twice", "same amount", "again"),
    ),
    SignalKind.PERIOD_END_CONCENTRATION: SignalVocabulary(
        title="Year-end adjustment",
        phrase="is a manual entry at the year end",
        next_step=(
            "Ask what the year-end entry adjusts, and obtain the working or calculation behind it."
        ),
        cues=("year end", "year-end", "period end", "period-end", "close", "closing"),
        standard="SA 240 (entries made at the end of a reporting period)",
    ),
    SignalKind.POST_CLOSE_ENTRY: SignalVocabulary(
        title="Posted after close",
        phrase="was entered after the books closed",
        next_step=(
            "Find out why the entry was made after the close and who authorised posting "
            "into a closed period."
        ),
        cues=("after", "later", "post-close", "delay", "closed"),
        standard="SA 240 (post-closing entries)",
    ),
    SignalKind.RARE_ACCOUNT_PAIR: SignalVocabulary(
        title="Unusual account pairing",
        phrase="uses an account pairing seldom seen in this ledger",
        next_step=(
            "Confirm the business reason for this combination of accounts with the "
            "preparer or the accounts lead."
        ),
        cues=("rare", "seldom", "pairing", "together", "combination", "unusual pair"),
        standard="SA 240 (entries to unusual or seldom-used accounts)",
    ),
    SignalKind.OFF_HOURS_POSTING: SignalVocabulary(
        title="Entered out of hours",
        phrase="was entered outside working hours",
        next_step=(
            "Check whether entries at this time are normal for this preparer — a scheduled "
            "batch or month-end overtime, for example."
        ),
        cues=("hour", "working day", "entered at", "night", "outside working", "out of hours"),
    ),
    SignalKind.ROUND_AMOUNT: SignalVocabulary(
        title="Round amount",
        phrase="is a round amount",
        next_step=(
            "Check whether the round amount is an estimate or a provision, and obtain the "
            "basis for it."
        ),
        cues=("round",),
        standard="SA 240 (entries with round or consistent ending numbers)",
    ),
    SignalKind.UNUSUAL_PREPARER_ACCOUNT: SignalVocabulary(
        title="Outside preparer's area",
        phrase="was entered by someone who does not usually post to this account",
        next_step=(
            "Confirm why this preparer posted to the account and whether they were authorised to."
        ),
        cues=("preparer", "prepared", "usually", "normally", "regular", "entered by"),
        standard="SA 240 (entries by individuals who do not usually make them)",
    ),
    SignalKind.WEEKEND_POSTING: SignalVocabulary(
        title="Entered on a Sunday",
        phrase="was entered on a Sunday",
        next_step="Check whether Sunday working is normal for this entity at this time of year.",
        cues=("sunday", "weekend", "holiday"),
    ),
    SignalKind.AMOUNT_OUTLIER: SignalVocabulary(
        title="Unusual amount for the account",
        phrase="is unusually large or small for its account",
        next_step=(
            "Compare with the comparable entries shown and obtain the explanation for the "
            "difference in size."
        ),
        cues=("amount", "usual", "typical", "larger", "smaller", "higher", "deviat"),
        standard="SA 520 (an amount that differs from the expected pattern)",
    ),
    SignalKind.THRESHOLD_ADJACENT: SignalVocabulary(
        title="Just below approval limit",
        phrase="sits just below an approval limit",
        next_step=(
            "Check whether the transaction was split or priced to stay below the approval "
            "limit, and look for related entries around the same date."
        ),
        cues=("limit", "threshold", "just below", "approval"),
    ),
    SignalKind.ML_ANOMALY: SignalVocabulary(
        title="Statistically unusual",
        phrase="is statistically unusual against the rest of the ledger",
        next_step="No separate step: this signal only reinforces the others.",
        cues=("statistic", "unusual", "pattern"),
    ),
}


def vocabulary(kind: SignalKind | str) -> SignalVocabulary:
    return VOCABULARY[SignalKind(kind)]


def contribution_level(contribution: float) -> str:
    """High / Medium / Low, from the signal's weighted strength."""
    if contribution >= HIGH_CONTRIBUTION:
        return "High"
    if contribution >= MEDIUM_CONTRIBUTION:
        return "Medium"
    return "Low"


def is_minor(contribution: float) -> bool:
    return contribution < MINOR_CONTRIBUTION


def mentions(text: str, kind: SignalKind | str) -> bool:
    """Whether ``text`` talks about this concern at all."""
    lowered = text.lower()
    return any(cue in lowered for cue in vocabulary(kind).cues)
