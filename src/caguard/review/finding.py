"""What a reviewer actually opens: one voucher, its priority, and the working.

A finding is the unit of review. It carries the signals that fired, how much
each contributed to the priority, how complete the evidence trail is, and the
ledger lines behind it — so a professional can check the claim rather than
accept it.

That completeness is also what makes Phase 5 possible. The local model will be
allowed to explain a finding using only what is recorded here and nothing else,
which turns "the AI must not invent things" into a property of the data rather
than an instruction in a prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from caguard.detect.types import SignalHit, SignalKind
from caguard.review.evidence import EvidenceScore


class RiskBand(StrEnum):
    """The three buckets a reviewer triages by."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


#: Band boundaries on the fused priority. Chosen so the high band stays small
#: enough to be worked through in a sitting.
HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40


def band_for(priority: float) -> RiskBand:
    if priority >= HIGH_THRESHOLD:
        return RiskBand.HIGH
    if priority >= MEDIUM_THRESHOLD:
        return RiskBand.MEDIUM
    return RiskBand.LOW


@dataclass(frozen=True)
class Finding:
    """One voucher worth a reviewer's attention, with its full justification."""

    voucher_id: str
    priority: float
    band: RiskBand
    signals: tuple[SignalHit, ...]
    evidence: EvidenceScore
    contributions: dict[SignalKind, float] = field(default_factory=dict)
    line_ids: tuple[str, ...] = ()
    amount_paise: int = 0
    voucher_date: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.priority <= 1.0:
            raise ValueError(f"priority must be in [0, 1], got {self.priority}")
        if not self.signals:
            raise ValueError("a finding with no signals cannot be justified")

    @property
    def kinds(self) -> tuple[SignalKind, ...]:
        return tuple(sorted({hit.kind for hit in self.signals}, key=lambda k: k.value))

    @property
    def reasons(self) -> tuple[str, ...]:
        """Every signal's reason, in the order they contributed most."""
        ordered = sorted(
            self.signals,
            key=lambda hit: -self.contributions.get(hit.kind, 0.0),
        )
        return tuple(hit.reason for hit in ordered)

    @property
    def top_concern(self) -> SignalKind:
        """The signal that contributed most — what to lead with."""
        return max(self.contributions.items(), key=lambda item: item[1])[0]

    def structured_facts(self) -> dict[str, Any]:
        """Everything a grounded explanation may draw on, and nothing else.

        Phase 5's prompt is built from exactly this. Anything absent here is
        something the model has no basis to say.
        """
        return {
            "voucher_id": self.voucher_id,
            "voucher_date": self.voucher_date,
            "amount_paise": self.amount_paise,
            "priority": round(self.priority, 4),
            "band": self.band.value,
            "evidence_completeness": self.evidence.completeness,
            "evidence_missing": self.evidence.missing,
            "source_lines": list(self.line_ids),
            "signals": [
                {
                    "kind": hit.kind.value,
                    "reason": hit.reason,
                    "strength": round(hit.strength, 3),
                    "contribution": round(self.contributions.get(hit.kind, 0.0), 4),
                    "evidence": hit.evidence,
                }
                for hit in self.signals
            ],
        }
