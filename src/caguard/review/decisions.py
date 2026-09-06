"""What a reviewer concluded about a finding, and when.

CA-Guard raises observations; a professional decides what they mean. This module
holds that decision, and it is deliberately more careful about *rejection* than
about acceptance.

Accepting a finding says "yes, I looked at this". Rejecting says "this is not a
concern" — and that is the judgement an engagement quality reviewer will ask
about six months later, when nobody remembers the invoice. So a rejection has to
carry a reason, enforced here rather than requested in a UI.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from caguard.review.finding import RiskBand


class ReviewAction(StrEnum):
    """What a reviewer did with a finding."""

    #: Looked at it and agrees it needs following up.
    ACCEPT = "accept"
    #: Looked at it and it is not a concern. Requires a reason.
    REJECT = "reject"
    #: Needs more work before a view can be taken.
    INVESTIGATE = "investigate"
    #: Agrees it matters, but not at the priority the software assigned.
    ADJUST = "adjust"

    @property
    def is_closing(self) -> bool:
        """Whether this settles the finding or leaves it open."""
        return self in {ReviewAction.ACCEPT, ReviewAction.REJECT}


#: Actions a reviewer must justify. Rejection is the one that later needs
#: defending; the others leave a trail that speaks for itself.
REQUIRES_NOTE: frozenset[ReviewAction] = frozenset({ReviewAction.REJECT})

MIN_NOTE_WORDS = 3


class Decision(BaseModel):
    """One entry in the review trail. Never edited, never deleted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    engagement_id: str = Field(min_length=1)
    voucher_id: str = Field(min_length=1)
    action: ReviewAction
    reviewer: str = Field(min_length=1)
    note: str | None = None
    adjusted_band: RiskBand | None = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    sequence: int | None = Field(
        default=None, description="Position in the trail; assigned by the store"
    )

    @model_validator(mode="after")
    def _justify_a_rejection(self) -> Decision:
        if self.action not in REQUIRES_NOTE:
            return self
        words = len((self.note or "").split())
        if words < MIN_NOTE_WORDS:
            raise ValueError(
                f"a {self.action.value} needs a reason of at least "
                f"{MIN_NOTE_WORDS} words. Someone will ask why this was dismissed, "
                "and the answer should not be lost."
            )
        return self

    @model_validator(mode="after")
    def _adjustment_names_a_band(self) -> Decision:
        if self.action is ReviewAction.ADJUST and self.adjusted_band is None:
            raise ValueError("an adjustment must say which band the reviewer chose")
        return self

    def summary(self) -> str:
        stamp = self.decided_at.strftime("%d-%m-%Y %H:%M")
        line = f"{self.reviewer} {self.action.value}ed {self.voucher_id} on {stamp}"
        if self.adjusted_band:
            line += f" (moved to {self.adjusted_band.value})"
        return f"{line}: {self.note}" if self.note else line
