"""Adapter for the VynFi synthetic journal-entry corpus (SAP-shaped).

Phase 0 verified this corpus as Apache-2.0, ungated, 667,584 lines. It is used
here **only** to prove the canonical schema survives a foreign export, and to
exercise throughput. It is not an accuracy benchmark: its ``is_fraud`` and
``anomaly_type`` labels do not correspond to patterns in the observable fields
(ADR-0001), so :data:`LABEL_COLUMNS` are dropped on purpose and never surfaced.

Two conversions are deliberate rather than faithful:

* **Fiscal year and period are recomputed** from the document date using the
  Indian April–March convention. The corpus carries its own calendar-based
  values; the canonical schema owns this field, so trusting theirs would put
  a January entry in the wrong quarter.
* **Posting time is marked ``DATE_ONLY``.** Every ``posting_date`` in the corpus
  is exactly midnight. Recording that as a real time would make all 667,584
  lines look like after-hours entries.
"""

from __future__ import annotations

import pandas as pd

from caguard.money import float_rupees_to_paise
from caguard.schema import (
    AccountGroup,
    TimeFidelity,
    VoucherType,
    fiscal_period_of,
    fiscal_year_of,
)

#: Never read these. Kept named so the intent is explicit and testable.
LABEL_COLUMNS = frozenset({"is_fraud", "is_anomaly", "fraud_type", "anomaly_type"})

#: SAP document types present in the corpus.
DOCUMENT_TYPES: dict[str, VoucherType] = {
    "DR": VoucherType.SALES,  # customer invoice
    "KR": VoucherType.PURCHASE,  # vendor invoice
    "SA": VoucherType.JOURNAL,  # G/L account document
    "HR": VoucherType.JOURNAL,  # payroll
    "AA": VoucherType.JOURNAL,  # asset posting
    "DZ": VoucherType.RECEIPT,  # customer payment
    "KZ": VoucherType.PAYMENT,  # vendor payment
    "WE": VoucherType.PURCHASE,  # goods receipt
    "WL": VoucherType.SALES,  # goods issue
    "OPENING_BALANCE": VoucherType.OPENING_BALANCE,
}

CATEGORIES: dict[str, AccountGroup] = {
    "asset": AccountGroup.ASSET,
    "liability": AccountGroup.LIABILITY,
    "equity": AccountGroup.EQUITY,
    "income": AccountGroup.INCOME,
    "revenue": AccountGroup.INCOME,
    "expense": AccountGroup.EXPENSE,
}


def adapt(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert a raw VynFi frame into canonical columns.

    Returns a frame ready for :func:`caguard.intake.validation.validate_lines`.
    Label columns are dropped before anything else touches the data.
    """
    src = frame.drop(columns=[c for c in LABEL_COLUMNS if c in frame.columns])

    doc_date = pd.to_datetime(src["document_date"]).dt.date
    posting = pd.to_datetime(src["posting_date"])

    out = pd.DataFrame(
        {
            "line_id": src["document_id"].astype(str) + "-" + src["line_number"].astype(str),
            "voucher_id": src["document_id"].astype(str),
            "line_number": src["line_number"].astype(int),
            "entity_id": src["company_code"].astype(str),
            "fiscal_year": [fiscal_year_of(d) for d in doc_date],
            "period": [fiscal_period_of(d) for d in doc_date],
            "voucher_date": doc_date,
            "posted_at": posting,
            "time_fidelity": TimeFidelity.DATE_ONLY.value,
            "voucher_type": [
                DOCUMENT_TYPES.get(str(t), VoucherType.OTHER).value for t in src["document_type"]
            ],
            "account_code": src["gl_account"].astype(str),
            "account_name": src["account_description"].fillna("Unnamed account").astype(str),
            "account_group": [
                CATEGORIES.get(str(c).lower(), AccountGroup.ASSET).value
                for c in src["financial_statement_category"]
            ],
            "debit_paise": [
                float_rupees_to_paise(v or 0.0) for v in src["debit_amount"].fillna(0.0)
            ],
            "credit_paise": [
                float_rupees_to_paise(v or 0.0) for v in src["credit_amount"].fillna(0.0)
            ],
            "currency": src["currency"].fillna("USD").astype(str),
            "created_by": src["created_by"].fillna("UNKNOWN").astype(str),
            "approved_by": None,
            "document_ref": src["reference"].where(src["reference"].notna(), None),
            "narration": src["line_text"]
            .fillna(src["header_text"])
            .where(src["line_text"].notna() | src["header_text"].notna(), None),
            "cost_centre": src["cost_center"].where(src["cost_center"].notna(), None),
            "is_manual": src["is_manual"].fillna(False).astype(bool),
            "is_post_close": src["is_post_close"].fillna(False).astype(bool),
        }
    )
    return out
