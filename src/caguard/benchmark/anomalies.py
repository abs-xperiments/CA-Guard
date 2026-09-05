"""What the generator plants, and what it plants to catch a careless detector.

Two taxonomies live here.

:class:`AnomalyKind` is what a reviewer should surface. Each one is drawn from a
characteristic SA 240 associates with journal entries warranting attention
(unusual accounts, unusual users, period-end and post-closing entries, round
numbers, entries outside the normal course of business), treated strictly as
audit-review heuristics rather than compliance assertions.

:class:`DecoyKind` is the more important half. ADR-0003 rule 2 requires that
every anomaly class ship with a legitimate look-alike, because a detector that
flags "round number" without flagging round *rent* has learned nothing. Decoys
are ordinary business reality; flagging one counts as a false positive.
"""

from __future__ import annotations

from enum import StrEnum


class AnomalyKind(StrEnum):
    """Planted irregularities. Ground truth — never readable by a detector."""

    DUPLICATE_PAYMENT = "duplicate_payment"
    ROUND_AMOUNT = "round_amount"
    AFTER_HOURS_POSTING = "after_hours_posting"
    WEEKEND_POSTING = "weekend_posting"
    PERIOD_END_CONCENTRATION = "period_end_concentration"
    RARE_ACCOUNT_PAIR = "rare_account_pair"
    THRESHOLD_ADJACENT = "threshold_adjacent"
    MISSING_DOCUMENT_REF = "missing_document_ref"
    UNUSUAL_PREPARER_ACCOUNT = "unusual_preparer_account"
    POST_CLOSE_ENTRY = "post_close_entry"


class DecoyKind(StrEnum):
    """Legitimate entries that *resemble* an anomaly. Flagging one is a false positive."""

    LEGIT_ROUND_RENT = "legit_round_rent"
    LEGIT_SATURDAY_POSTING = "legit_saturday_posting"
    LEGIT_YEAR_END_ACCRUAL = "legit_year_end_accrual"
    LEGIT_RECURRING_EMI = "legit_recurring_emi"
    LEGIT_BELOW_THRESHOLD = "legit_below_threshold"
    LEGIT_SYSTEM_NO_DOCUMENT = "legit_system_no_document"


#: Why each anomaly matters to a reviewer. Used in the CA validation pack and in
#: evaluation reporting, so that a per-type recall table is readable.
ANOMALY_RATIONALE: dict[AnomalyKind, str] = {
    AnomalyKind.DUPLICATE_PAYMENT: (
        "The same vendor invoice appears to have been settled twice within days, "
        "on separate vouchers — a common cause of leakage."
    ),
    AnomalyKind.ROUND_AMOUNT: (
        "A large, exactly round amount posted to an account whose values are "
        "normally irregular, suggesting an estimate or a manufactured figure."
    ),
    AnomalyKind.AFTER_HOURS_POSTING: (
        "Entered between 01:00 and 05:00, well outside the hours the accounts team works."
    ),
    AnomalyKind.WEEKEND_POSTING: (
        "Entered on a Sunday, when the office is closed. Saturday is a normal "
        "working day in most Indian firms and is deliberately NOT anomalous here."
    ),
    AnomalyKind.PERIOD_END_CONCENTRATION: (
        "One of a burst of manual journals dated 31 March with no supporting "
        "document — the classic year-end adjustment pattern."
    ),
    AnomalyKind.RARE_ACCOUNT_PAIR: (
        "An account combination that appears almost nowhere else in the ledger, "
        "typically routing value through the suspense account."
    ),
    AnomalyKind.THRESHOLD_ADJACENT: (
        "Sits just below the delegation-of-authority limit, consistent with "
        "splitting a payment to avoid the next approval level."
    ),
    AnomalyKind.MISSING_DOCUMENT_REF: (
        "A material manual entry with no supporting document reference at all — "
        "the evidence gap this project treats as a first-class signal."
    ),
    AnomalyKind.UNUSUAL_PREPARER_ACCOUNT: (
        "Posted by a staff member who never otherwise touches this account, "
        "outside their normal area of work."
    ),
    AnomalyKind.POST_CLOSE_ENTRY: (
        "Dated within the year but entered well after the books were closed."
    ),
}

#: What each decoy tests. A detector that flags these has learned the surface
#: pattern instead of the underlying concern.
DECOY_RATIONALE: dict[DecoyKind, str] = {
    DecoyKind.LEGIT_ROUND_RENT: (
        "Monthly rent is contractually an exact round figure, fully documented "
        "and approved. Tests: round-number detection must not fire on it."
    ),
    DecoyKind.LEGIT_SATURDAY_POSTING: (
        "Saturday is a working day. Tests: weekend detection must key on Sunday, "
        "not on 'not a weekday'."
    ),
    DecoyKind.LEGIT_YEAR_END_ACCRUAL: (
        "Depreciation and provisions legitimately fall on 31 March, with "
        "documents and approval. Tests: period-end concentration must consider "
        "evidence and approval, not the date alone."
    ),
    DecoyKind.LEGIT_RECURRING_EMI: (
        "A term-loan EMI is identical every month by contract. Tests: duplicate "
        "detection must not fire on legitimate recurring entries."
    ),
    DecoyKind.LEGIT_BELOW_THRESHOLD: (
        "A genuine invoice that happens to fall just under the approval limit, "
        "with a document and an approver. Tests: threshold adjacency alone is "
        "not sufficient evidence."
    ),
    DecoyKind.LEGIT_SYSTEM_NO_DOCUMENT: (
        "Bank charges auto-posted by the bank feed carry no voucher reference "
        "and are immaterial. Tests: the evidence gap must be weighted by "
        "materiality and source, not applied flatly."
    ),
}
