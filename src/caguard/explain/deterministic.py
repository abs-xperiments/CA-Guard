"""The explanation CA-Guard writes without any model at all.

This is a first-class deliverable, not a placeholder. It is what a firm running
with no model installed reads, and what every reviewer reads whenever the
model's output fails the grounding check. It therefore has to be good enough to
ship on its own, and it is the one path that can never fail.

It is built from the finding's own structured facts, in the same order of
importance the fusion assigned, and it deliberately stops short of a conclusion.
"""

from __future__ import annotations

from caguard.money import format_inr
from caguard.review.finding import Finding, RiskBand

#: Appended to every explanation, generated or not. CA-Guard offers observations
#: for review; the professional reaches the conclusion.
DISCLAIMER = (
    "This is a prioritised observation for review, not a conclusion. "
    "The professional judgement remains with the reviewer."
)

_BAND_PHRASE = {
    RiskBand.HIGH: "warrants attention first",
    RiskBand.MEDIUM: "is worth a look",
    RiskBand.LOW: "is noted for completeness",
}


def explain_deterministically(finding: Finding) -> str:
    """Render a finding as plain prose, using only what the finding records."""
    return "\n\n".join(
        part
        for part in (
            _headline(finding),
            _concerns(finding),
            _evidence(finding),
            _provenance(finding),
            DISCLAIMER,
        )
        if part
    )


def _headline(finding: Finding) -> str:
    date = _readable_date(finding.voucher_date)
    return (
        f"Voucher {finding.voucher_id} for {format_inr(finding.amount_paise)}, "
        f"dated {date}, {_BAND_PHRASE[finding.band]} "
        f"(priority {finding.priority:.2f})."
    )


def _concerns(finding: Finding) -> str:
    reasons = list(finding.reasons)
    if not reasons:
        return ""

    count = len(reasons)
    noun = "concern was" if count == 1 else "concerns were"
    lead = f"{_spell(count)} {noun} raised on this voucher."

    if count == 1:
        return f"{lead} {reasons[0]}"

    body = [f"The strongest is this: {reasons[0]}"]
    if len(reasons) > 1:
        rest = " ".join(reasons[1:])
        body.append(f"Alongside it: {rest}")
    return f"{lead} " + " ".join(body)


def _evidence(finding: Finding) -> str:
    score = finding.evidence
    completeness = f"The evidence trail is {score.completeness:.0%} complete."
    if not score.missing:
        return f"{completeness} A supporting document, an approval and a narration are all present."
    return f"{completeness} {score.summary()}"


def _provenance(finding: Finding) -> str:
    lines = ", ".join(finding.line_ids)
    if not lines:
        return ""
    plural = "line" if len(finding.line_ids) == 1 else "lines"
    return f"Drawn from ledger {plural} {lines}."


def _readable_date(iso: str) -> str:
    """``2025-03-29`` → ``29-03-2025``, the order an Indian reader expects."""
    parts = iso.split("-")
    return f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else iso


_NUMBER_WORDS = (
    "No",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
)


def _spell(count: int) -> str:
    """Spell small counts, so the guard is not asked to justify a bare digit."""
    return _NUMBER_WORDS[count] if count < len(_NUMBER_WORDS) else str(count)
