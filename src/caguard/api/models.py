"""Request and response shapes for the API.

Separate from the domain models on purpose. A finding carries objects the
pipeline needs; a browser needs plain JSON with the amount already formatted and
the dates already in the order an Indian reader expects. Doing that conversion
here keeps presentation concerns out of the detection code.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from caguard.money import format_inr
from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement
from caguard.review.finding import Finding, RiskBand


class SignalOut(BaseModel):
    kind: str
    reason: str
    strength: float
    contribution: float
    evidence: dict[str, object] = Field(default_factory=dict)


class EvidenceOut(BaseModel):
    completeness: float
    missing: list[str]
    has_document: bool
    has_approval: bool
    approval_expected: bool
    has_narration: bool
    summary: str


class FindingOut(BaseModel):
    voucher_id: str
    voucher_date: str
    amount_paise: int
    amount_display: str
    priority: float
    band: RiskBand
    concerns: list[str]
    signals: list[SignalOut]
    evidence: EvidenceOut
    line_ids: list[str]
    status: str = "not yet reviewed"
    reviewer: str | None = None
    note: str | None = None

    @classmethod
    def build(cls, finding: Finding, decision: Decision | None = None) -> FindingOut:
        return cls(
            voucher_id=finding.voucher_id,
            voucher_date=finding.voucher_date,
            amount_paise=finding.amount_paise,
            amount_display=format_inr(finding.amount_paise),
            priority=round(finding.priority, 4),
            band=finding.band,
            concerns=[kind.value for kind in finding.kinds],
            signals=[
                SignalOut(
                    kind=hit.kind.value,
                    reason=hit.reason,
                    strength=round(hit.strength, 3),
                    contribution=round(finding.contributions.get(hit.kind, 0.0), 4),
                    evidence=dict(hit.evidence),
                )
                for hit in sorted(
                    finding.signals,
                    key=lambda h: -finding.contributions.get(h.kind, 0.0),
                )
            ],
            evidence=EvidenceOut(
                completeness=finding.evidence.completeness,
                missing=finding.evidence.missing,
                has_document=finding.evidence.has_document,
                has_approval=finding.evidence.has_approval,
                approval_expected=finding.evidence.approval_expected,
                has_narration=finding.evidence.has_narration,
                summary=finding.evidence.summary(),
            ),
            line_ids=list(finding.line_ids),
            status=decision.action.value if decision else "not yet reviewed",
            reviewer=decision.reviewer if decision else None,
            note=decision.note if decision else None,
        )


class EngagementOut(BaseModel):
    id: str
    name: str
    entity_id: str
    fiscal_year: str
    source_name: str
    voucher_count: int
    short_hash: str
    opened_at: datetime

    @classmethod
    def build(cls, engagement: Engagement) -> EngagementOut:
        return cls(
            id=engagement.id,
            name=engagement.name,
            entity_id=engagement.entity_id,
            fiscal_year=engagement.fiscal_year,
            source_name=engagement.source_name,
            voucher_count=engagement.voucher_count,
            short_hash=engagement.short_hash,
            opened_at=engagement.opened_at,
        )


class QueueOut(BaseModel):
    """The review queue, with enough summary for the header."""

    engagement: EngagementOut
    findings: list[FindingOut]
    total_vouchers: int
    flagged: int
    bands: dict[str, int]
    states: dict[str, int]
    model_available: bool


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voucher_id: str = Field(min_length=1)
    action: ReviewAction
    reviewer: str = Field(min_length=1, default="reviewer")
    note: str | None = None
    adjusted_band: RiskBand | None = None


class DecisionOut(BaseModel):
    voucher_id: str
    action: ReviewAction
    reviewer: str
    note: str | None
    adjusted_band: RiskBand | None
    decided_at: datetime
    sequence: int | None

    @classmethod
    def build(cls, decision: Decision) -> DecisionOut:
        return cls(
            voucher_id=decision.voucher_id,
            action=decision.action,
            reviewer=decision.reviewer,
            note=decision.note,
            adjusted_band=decision.adjusted_band,
            decided_at=decision.decided_at,
            sequence=decision.sequence,
        )


class ExplanationOut(BaseModel):
    voucher_id: str
    text: str
    source: str
    provider: str
    latency_seconds: float
    provenance: str
