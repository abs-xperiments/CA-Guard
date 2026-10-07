"""Request and response shapes for the API.

Separate from the domain models on purpose. A finding carries objects the
pipeline needs; a browser needs plain JSON with the amount already formatted and
the dates already in the order an Indian reader expects. Doing that conversion
here keeps presentation concerns out of the detection code.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from caguard.api.jobs import STAGE_KEYS, STAGES, Job, JobState
from caguard.explain.card import ExplanationCard
from caguard.explain.vocabulary import contribution_level, is_minor
from caguard.money import format_inr
from caguard.review.decisions import Decision, ReviewAction
from caguard.review.engagement import Engagement
from caguard.review.finding import Finding, RiskBand
from caguard.review.store import EngagementSummary, SourceFile


class SignalOut(BaseModel):
    kind: str
    reason: str
    strength: float
    contribution: float
    #: High / Medium / Low, so a reviewer is not left to interpret 0.6375.
    level: str = "Low"
    #: Below the display floor: "also noted", not a headline reason.
    minor: bool = False
    evidence: dict[str, object] = Field(default_factory=dict)


class EvidenceOut(BaseModel):
    completeness: float
    missing: list[str]
    has_document: bool
    has_approval: bool
    approval_expected: bool
    has_narration: bool
    summary: str


class LineOut(BaseModel):
    """One ledger line behind a finding, with where it sits in the uploaded file."""

    line_id: str
    line_number: int | None = None
    account_code: str = ""
    account_name: str = ""
    debit_paise: int = 0
    credit_paise: int = 0
    debit_display: str = ""
    credit_display: str = ""
    narration: str | None = None
    document_ref: str | None = None
    voucher_type: str | None = None
    cost_centre: str | None = None
    created_by: str | None = None
    approved_by: str | None = None
    posted_at: str | None = None
    #: The row in the original file, numbered as a spreadsheet shows it.
    source_row: int | None = None

    @classmethod
    def from_frame(cls, lines: pd.DataFrame) -> list[LineOut]:
        out: list[LineOut] = []
        for record in lines.to_dict("records"):
            debit = _int(record.get("debit_paise"))
            credit = _int(record.get("credit_paise"))
            out.append(
                cls(
                    line_id=str(record.get("line_id", "")),
                    line_number=_int(record.get("line_number")) or None,
                    account_code=_text(record.get("account_code")) or "",
                    account_name=_text(record.get("account_name")) or "",
                    debit_paise=debit,
                    credit_paise=credit,
                    debit_display=format_inr(debit) if debit else "",
                    credit_display=format_inr(credit) if credit else "",
                    narration=_text(record.get("narration")),
                    document_ref=_text(record.get("document_ref")),
                    voucher_type=_text(record.get("voucher_type")),
                    cost_centre=_text(record.get("cost_centre")),
                    created_by=_text(record.get("created_by")),
                    approved_by=_text(record.get("approved_by")),
                    posted_at=_text(record.get("posted_at")),
                    source_row=_int(record.get("source_row")) or None,
                )
            )
        return out


class SourceFileOut(BaseModel):
    """An uploaded file as the reviewer sees it."""

    id: str
    engagement_id: str
    filename: str
    file_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime
    uploaded_by: str
    rows_read: int
    rows_used: int
    available: bool
    deleted_at: datetime | None = None
    deleted_by: str | None = None

    @classmethod
    def build(cls, source: SourceFile, *, available: bool) -> SourceFileOut:
        return cls(
            id=source.id,
            engagement_id=source.engagement_id,
            filename=source.filename,
            file_type=_FILE_TYPES.get(source.suffix, source.suffix),
            size_bytes=source.size_bytes,
            sha256=source.sha256,
            uploaded_at=source.uploaded_at,
            uploaded_by=source.uploaded_by,
            rows_read=source.rows_read,
            rows_used=source.rows_used,
            available=available and not source.is_deleted,
            deleted_at=source.deleted_at,
            deleted_by=source.deleted_by,
        )


class SourceRefOut(BaseModel):
    """Which uploaded file a finding's lines were read from."""

    id: str
    filename: str


class PreviewRowOut(BaseModel):
    row: int
    values: list[str | None]


class PreviewOut(BaseModel):
    """A window onto the uploaded file, exactly as it was read — before any mapping."""

    source_id: str
    filename: str
    columns: list[str]
    rows: list[PreviewRowOut]
    total_rows: int
    offset: int


_FILE_TYPES = {".csv": "CSV", ".xlsx": "Excel", ".xls": "Excel 97-2003", ".parquet": "Parquet"}


def _text(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value is pd.NaT:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0
    try:
        return int(value)  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError):
        return 0


def _headline_concerns(finding: Finding) -> list[str]:
    """The reasons worth a chip in the queue: strongest first, minor ones left out.

    Ordered by contribution, not alphabetically, so the first chip is the main
    reason. A signal under the display floor — usually the ML layer at ~2% —
    stays on the card as "also noted" instead of headlining every row.
    """
    ranked = sorted(finding.signals, key=lambda h: -finding.contributions.get(h.kind, 0.0))
    kinds: list[str] = []
    for hit in ranked:
        if hit.kind.value not in kinds and not is_minor(finding.contributions.get(hit.kind, 0.0)):
            kinds.append(hit.kind.value)
    return kinds or [ranked[0].kind.value]


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
    #: The transaction itself. Filled for a single finding, left empty in the
    #: queue so a 36,000-finding queue is not also 100,000 ledger lines.
    lines: list[LineOut] = Field(default_factory=list)
    source: SourceRefOut | None = None
    #: The structured explanation. Single finding only, like ``lines``.
    card: ExplanationCard | None = None
    #: For searching the queue: the voucher's account names and narration.
    accounts: list[str] = Field(default_factory=list)
    narration: str | None = None
    prepared_by: str | None = None

    @classmethod
    def build(
        cls,
        finding: Finding,
        decision: Decision | None = None,
        *,
        lines: pd.DataFrame | None = None,
        source: SourceFile | None = None,
        card: ExplanationCard | None = None,
        accounts: list[str] | None = None,
        narration: str | None = None,
        prepared_by: str | None = None,
        signal_evidence: bool = True,
    ) -> FindingOut:
        """``signal_evidence=False`` for queue rows: the table never shows each
        signal's evidence dictionary, and at ~1 KB a row it was most of the
        queue's weight. The single-finding view still carries it."""
        return cls(
            voucher_id=finding.voucher_id,
            voucher_date=finding.voucher_date,
            amount_paise=finding.amount_paise,
            amount_display=format_inr(finding.amount_paise),
            priority=round(finding.priority, 4),
            band=finding.band,
            concerns=_headline_concerns(finding),
            signals=[
                SignalOut(
                    kind=hit.kind.value,
                    reason=hit.reason,
                    strength=round(hit.strength, 3),
                    contribution=round(finding.contributions.get(hit.kind, 0.0), 4),
                    level=contribution_level(finding.contributions.get(hit.kind, 0.0)),
                    minor=is_minor(finding.contributions.get(hit.kind, 0.0)),
                    evidence=dict(hit.evidence) if signal_evidence else {},
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
            lines=LineOut.from_frame(lines) if lines is not None else [],
            source=SourceRefOut(id=source.id, filename=source.filename) if source else None,
            card=card,
            accounts=accounts or [],
            narration=narration,
            prepared_by=prepared_by,
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


class EngagementSummaryOut(BaseModel):
    """One row on the dashboard: what the engagement is and how far along it is."""

    engagement: EngagementOut
    flagged: int | None
    high: int | None
    medium: int | None
    reviewed: int
    last_activity: datetime
    latest_file: str | None

    @classmethod
    def build(cls, summary: EngagementSummary) -> EngagementSummaryOut:
        return cls(
            engagement=EngagementOut.build(summary.engagement),
            flagged=summary.flagged,
            high=summary.high,
            medium=summary.medium,
            reviewed=summary.reviewed,
            last_activity=summary.last_activity,
            latest_file=summary.latest_file,
        )


class RenameIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=120)


class IntakeReportOut(BaseModel):
    """What CA-Guard made of the uploaded file's columns.

    Shown to the reviewer because a limitation of the *file* must never be
    mistaken for a finding about the *client*: "no supporting document" means
    something very different when the file has no such column.
    """

    summary: str
    mapped: dict[str, str]
    derived: list[str]
    not_in_file: list[str]
    ignored: list[str]
    notes: list[str]
    rows_read: int
    rows_used: int


class QueueOut(BaseModel):
    """The review queue, with enough summary for the header."""

    engagement: EngagementOut
    findings: list[FindingOut]
    total_vouchers: int
    flagged: int
    bands: dict[str, int]
    states: dict[str, int]
    model_available: bool
    intake: IntakeReportOut | None = None


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    voucher_id: str = Field(min_length=1)
    action: ReviewAction
    # Deliberately absent: the reviewer comes from the signed-in session.
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


class JobStageOut(BaseModel):
    key: str
    label: str
    state: str  # "done" | "current" | "pending"


class JobOut(BaseModel):
    """A background analysis, as the upload screen shows it."""

    id: str
    state: str
    stage: str | None
    stages: list[JobStageOut]
    engagement_id: str | None
    error: str | None
    elapsed_seconds: float

    @classmethod
    def build(cls, job: Job) -> JobOut:
        reached = STAGE_KEYS.index(job.stage) if job.stage in STAGE_KEYS else -1
        finished = job.state is JobState.DONE
        stages = [
            JobStageOut(
                key=key,
                label=label,
                state=(
                    "done"
                    if finished or index < reached
                    else "current"
                    if index == reached
                    else "pending"
                ),
            )
            for index, (key, label) in enumerate(STAGES)
        ]
        return cls(
            id=job.id,
            state=job.state.value,
            stage=job.stage,
            stages=stages,
            engagement_id=job.engagement_id,
            error=job.error,
            elapsed_seconds=round(job.elapsed, 1),
        )


class ExplanationOut(BaseModel):
    voucher_id: str
    text: str
    source: str
    provider: str
    latency_seconds: float
    provenance: str
