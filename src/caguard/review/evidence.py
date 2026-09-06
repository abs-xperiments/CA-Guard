"""How complete the evidence behind a voucher is.

This is the input the project treats as distinctive: not *is this transaction
odd*, but *can it be supported*. An ordinary-looking entry with no document, no
approval and no narration deserves a reviewer's time more than an unusual one
that is fully vouched.

The scoring is deliberately context-aware. An approver is only expected above
the firm's delegation limit, so a small unapproved payment is not an evidence
gap — it is a payment nobody needed to approve. Getting that wrong would flag a
large part of any ordinary ledger, which is precisely the failure mode Phase 2
built decoys to catch.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from caguard.detect.context import LedgerContext
from caguard.detect.types import DetectorConfig

#: What each element of the evidence trail is worth. A source document is the
#: strongest form of support, so it carries the most weight; a narration is the
#: weakest, being only the preparer's own description.
DOCUMENT_WEIGHT = 0.55
APPROVAL_WEIGHT = 0.30
NARRATION_WEIGHT = 0.15


@dataclass(frozen=True)
class EvidenceScore:
    """How well supported one voucher is, and what is missing."""

    voucher_id: str
    completeness: float
    has_document: bool
    has_approval: bool
    approval_expected: bool
    has_narration: bool
    document_coverage: float

    @property
    def gap(self) -> float:
        """How much of the expected evidence trail is absent."""
        return 1.0 - self.completeness

    @property
    def missing(self) -> list[str]:
        """Plain-language list of what is not there, for the finding."""
        absent: list[str] = []
        if not self.has_document:
            absent.append("supporting document")
        if self.approval_expected and not self.has_approval:
            absent.append("approval")
        if not self.has_narration:
            absent.append("narration")
        return absent

    def summary(self) -> str:
        if not self.missing:
            return "Fully supported: document, approval and narration all present."
        return f"No {' and no '.join(self.missing)}."


def score_evidence(
    ctx: LedgerContext, config: DetectorConfig | None = None
) -> dict[str, EvidenceScore]:
    """Score the evidence trail of every voucher in the ledger."""
    cfg = config or DetectorConfig()
    scores: dict[str, EvidenceScore] = {}

    for voucher_id, row in ctx.rows():
        coverage = float(row.evidence_lines) / max(int(row.line_count), 1)
        has_document = bool(row.evidence_lines > 0)
        has_approval = _present(row.approved_by)
        has_narration = _present(row.narration)

        # Approval is only expected where the firm's own limit requires it.
        approval_expected = int(row.amount_paise) >= cfg.approval_limit_paise

        earned = DOCUMENT_WEIGHT * coverage
        available = DOCUMENT_WEIGHT + NARRATION_WEIGHT
        earned += NARRATION_WEIGHT * float(has_narration)
        if approval_expected:
            available += APPROVAL_WEIGHT
            earned += APPROVAL_WEIGHT * float(has_approval)

        scores[voucher_id] = EvidenceScore(
            voucher_id=voucher_id,
            completeness=round(earned / available, 4),
            has_document=has_document,
            has_approval=has_approval,
            approval_expected=approval_expected,
            has_narration=has_narration,
            document_coverage=round(coverage, 4),
        )
    return scores


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, float) and pd.isna(value):
        return False
    return bool(str(value).strip())
