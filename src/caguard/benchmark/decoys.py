"""Legitimate entries that look irregular.

These are the reason the benchmark is worth anything. If the ledger contained
only ordinary vouchers and planted anomalies, a detector that flagged every
round number, every 31 March entry and every missing document would score
almost perfectly while being useless in a real practice — a CA would drown in
false positives on day one.

Each decoy is ordinary business reality wearing the surface of an anomaly:
rent genuinely is a round figure, depreciation genuinely falls on 31 March, an
EMI genuinely repeats unchanged every month. Flagging one counts as a false
positive in evaluation (ADR-0003 rule 2).

Decoys are emitted at a higher rate than anomalies, because in a real ledger the
innocent explanations outnumber the guilty ones.
"""

from __future__ import annotations

from datetime import date, timedelta

from caguard.benchmark import coa
from caguard.benchmark.anomalies import DecoyKind
from caguard.benchmark.generator import _Builder
from caguard.schema import VoucherType

# Contractual figures that are round by nature, not by manipulation.
# Exactly round on purpose: it must collide with the round-number signal.
MONTHLY_RENT_PAISE = 2_00_000_00
MONTHLY_EMI_PAISE = 2_47_318_00


def emit_decoy(b: _Builder, kind: DecoyKind) -> int:
    """Emit one legitimate look-alike. Returns the number of vouchers added."""
    match kind:
        case DecoyKind.LEGIT_ROUND_RENT:
            return _round_rent(b)
        case DecoyKind.LEGIT_SATURDAY_POSTING:
            return _saturday(b)
        case DecoyKind.LEGIT_YEAR_END_ACCRUAL:
            return _year_end_accrual(b)
        case DecoyKind.LEGIT_RECURRING_EMI:
            return _recurring_emi(b)
        case DecoyKind.LEGIT_BELOW_THRESHOLD:
            return _below_threshold(b)
        case DecoyKind.LEGIT_SYSTEM_NO_DOCUMENT:
            return _system_no_document(b)


def _round_rent(b: _Builder) -> int:
    """Round, recurring, documented, approved — and entirely legitimate."""
    day = _month_start(b, b.occurrence("rent"))
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("5200", MONTHLY_RENT_PAISE, 0), ("1010", 0, MONTHLY_RENT_PAISE)],
        narration="Office rent for the month as per lease agreement",
        document_ref=b.doc_ref("RENT"),
        approved_by=b.rng.choice(coa.APPROVERS),
        decoys=[DecoyKind.LEGIT_ROUND_RENT],
        note="Round because the lease fixes it; documented and approved",
    )
    return 1


def _saturday(b: _Builder) -> int:
    """Saturday is a normal working day in most Indian firms."""
    day = b.working_day()
    saturday = day + timedelta(days=(5 - day.weekday()) % 7)
    if saturday > b.cfg.fy_end:
        saturday -= timedelta(days=7)
    amount = b.amount_paise()
    b.add(
        voucher_type=VoucherType.SALES,
        voucher_date=saturday,
        posted_at=b.business_time(saturday, lag_days=0),
        legs=b.sales_legs(amount),
        narration=f"Sales to {b.rng.choice(coa.CUSTOMERS)}",
        document_ref=b.doc_ref("INV"),
        approved_by=b.rng.choice(coa.APPROVERS),
        decoys=[DecoyKind.LEGIT_SATURDAY_POSTING],
        note="Saturday is a working day; only Sunday is out of the ordinary",
    )
    return 1


def _year_end_accrual(b: _Builder) -> int:
    """Depreciation and provisions legitimately belong on 31 March."""
    amount = b.amount_paise(mu=11.6)
    is_depreciation = b.rng.random() < 0.5
    legs = (
        [("5920", amount, 0), ("1590", 0, amount)]
        if is_depreciation
        else [("5210", amount, 0), ("2400", 0, amount)]
    )
    narration = (
        "Depreciation charged for the year as per Companies Act"
        if is_depreciation
        else "Provision for electricity charges payable"
    )
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=b.cfg.fy_end,
        posted_at=b.business_time(b.cfg.fy_end, lag_days=1),
        legs=legs,
        narration=narration,
        document_ref=b.doc_ref("JV"),
        approved_by=b.rng.choice(coa.APPROVERS),
        is_manual=True,
        decoys=[DecoyKind.LEGIT_YEAR_END_ACCRUAL],
        note="A genuine year-end entry: documented, approved, and expected on 31 March",
    )
    return 1


def _recurring_emi(b: _Builder) -> int:
    """An identical term-loan instalment every month — duplicate-shaped, contractual."""
    day = _month_start(b, b.occurrence("emi"))
    interest = 47_318_00
    principal = MONTHLY_EMI_PAISE - interest
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("2500", principal, 0), ("5910", interest, 0), ("1010", 0, MONTHLY_EMI_PAISE)],
        narration="Term loan EMI debited by HDFC Bank",
        document_ref=b.doc_ref("EMI"),
        approved_by=b.rng.choice(coa.APPROVERS),
        decoys=[DecoyKind.LEGIT_RECURRING_EMI],
        note="Identical every month by contract; repetition is not duplication",
    )
    return 1


def _below_threshold(b: _Builder) -> int:
    """A real invoice that simply happens to fall under the limit — with evidence."""
    amount = coa.APPROVAL_LIMIT_PAISE - b.rng.randint(100, 4_500_00)
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("2000", amount, 0), ("1010", 0, amount)],
        narration=f"Payment to {b.rng.choice(coa.VENDORS)} against invoice",
        document_ref=b.doc_ref("BP"),
        approved_by=b.rng.choice(coa.APPROVERS),
        decoys=[DecoyKind.LEGIT_BELOW_THRESHOLD],
        note="Under the limit by coincidence, and still documented and approved",
    )
    return 1


def _system_no_document(b: _Builder) -> int:
    """Bank-fed charges carry no voucher and are immaterial. An evidence gap that is fine."""
    amount = b.rng.randint(50_00, 900_00)
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day, lag_days=0),
        legs=[("5800", amount, 0), ("1010", 0, amount)],
        narration="Bank charges debited by HDFC Bank",
        document_ref=None,
        created_by=coa.SYSTEM_USER,
        decoys=[DecoyKind.LEGIT_SYSTEM_NO_DOCUMENT],
        note="Auto-posted by the bank feed; immaterial and never voucher-backed",
    )
    return 1


def _month_start(b: _Builder, occurrence: int) -> date:
    """The first working day of month ``occurrence`` of the fiscal year.

    Cycles April→March so a monthly charge appears once a month, which is what
    rent and a loan instalment actually do.
    """
    month = (3 + occurrence % 12) % 12 + 1
    year = b.cfg.fy_start_year + (1 if month < 4 else 0)
    day = date(year, month, 1)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day
