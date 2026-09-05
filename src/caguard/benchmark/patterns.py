"""The three populations the generator emits: ordinary, planted, and decoy.

Ordinary vouchers are the background a reviewer should never have to look at.
Planted vouchers carry an irregularity that is genuinely present in the
observable fields — the property VynFi lacked. Decoys carry the *surface* of an
irregularity with a legitimate business reason behind it, and a detector that
flags them is measured as wrong (ADR-0003 rule 2).

Every function here takes the shared :class:`~caguard.benchmark.generator._Builder`
so that all randomness flows from the single seeded generator.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from caguard.benchmark import coa
from caguard.benchmark.anomalies import AnomalyKind
from caguard.benchmark.generator import Leg, _Builder
from caguard.schema import VoucherType

# --- ordinary business -------------------------------------------------------

_NORMAL_MIX: tuple[tuple[str, int], ...] = (
    ("sales", 30),
    ("purchase", 25),
    ("receipt", 15),
    ("pay_vendor", 12),
    ("pay_expense", 10),
    ("salary", 5),
    ("contra", 3),
)
_KINDS = [k for k, _ in _NORMAL_MIX]
_WEIGHTS = [w for _, w in _NORMAL_MIX]

# Ordinary expenses and the TDS section that applies to each.
_EXPENSE_MIX: tuple[tuple[str, int, str], ...] = (
    ("5500", coa.TDS_194J_PCT, "2201"),  # professional fees
    ("5300", coa.TDS_194C_PCT, "2200"),  # freight
    ("5400", coa.TDS_194C_PCT, "2200"),  # repairs
    ("5700", coa.TDS_194C_PCT, "2200"),  # advertisement
)


def emit_normal(b: _Builder) -> int:
    """One ordinary, well-documented voucher. Returns vouchers added."""
    kind = b.rng.choices(_KINDS, weights=_WEIGHTS)[0]
    day = b.working_day()
    posted = b.business_time(day)
    amount = b.amount_paise()

    if kind == "sales":
        customer = b.rng.choice(coa.CUSTOMERS)
        b.add(
            voucher_type=VoucherType.SALES,
            voucher_date=day,
            posted_at=posted,
            legs=b.sales_legs(amount),
            narration=f"Sales to {customer}",
            document_ref=b.doc_ref("INV"),
            approved_by=_approver(b, amount),
        )
    elif kind == "purchase":
        vendor = b.rng.choice(coa.VENDORS)
        b.add(
            voucher_type=VoucherType.PURCHASE,
            voucher_date=day,
            posted_at=posted,
            legs=b.purchase_legs(amount),
            narration=f"Purchase from {vendor}",
            document_ref=b.doc_ref("PINV"),
            approved_by=_approver(b, amount),
        )
    elif kind == "receipt":
        customer = b.rng.choice(coa.CUSTOMERS)
        b.add(
            voucher_type=VoucherType.RECEIPT,
            voucher_date=day,
            posted_at=posted,
            legs=[("1010", amount, 0), ("1100", 0, amount)],
            narration=f"Receipt from {customer} against invoice",
            document_ref=b.doc_ref("RCPT"),
        )
    elif kind == "pay_vendor":
        vendor = b.rng.choice(coa.VENDORS)
        b.add(
            voucher_type=VoucherType.PAYMENT,
            voucher_date=day,
            posted_at=posted,
            legs=[("2000", amount, 0), ("1010", 0, amount)],
            narration=f"Payment to {vendor}",
            document_ref=b.doc_ref("BP"),
            approved_by=_approver(b, amount),
        )
    elif kind == "pay_expense":
        code, tds_pct, tds_acct = b.rng.choice(_EXPENSE_MIX)
        b.add(
            voucher_type=VoucherType.PAYMENT,
            voucher_date=day,
            posted_at=posted,
            legs=b.expense_legs(code, amount, tds_pct, tds_acct),
            narration=f"{coa.account(code).name} paid, TDS deducted",
            document_ref=b.doc_ref("BP"),
            approved_by=_approver(b, amount),
        )
    elif kind == "salary":
        month_end = _month_end(day)
        b.add(
            voucher_type=VoucherType.JOURNAL,
            voucher_date=month_end,
            posted_at=b.business_time(month_end, lag_days=1),
            legs=b.salary_legs(amount * 4),
            narration="Salary payable for the month",
            document_ref=b.doc_ref("PAY"),
            approved_by=b.rng.choice(coa.APPROVERS),
            is_manual=True,
        )
    else:  # contra
        b.add(
            voucher_type=VoucherType.CONTRA,
            voucher_date=day,
            posted_at=posted,
            legs=[("1000", amount, 0), ("1010", 0, amount)],
            narration="Cash withdrawn from bank for office use",
            document_ref=b.doc_ref("CTR"),
        )
    return 1


def _approver(b: _Builder, amount: int) -> str | None:
    """Entries above the delegation limit are approved; smaller ones need not be."""
    return b.rng.choice(coa.APPROVERS) if amount >= coa.APPROVAL_LIMIT_PAISE else None


def _month_end(day: date) -> date:
    nxt = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


# --- planted irregularities --------------------------------------------------


def emit_anomaly(b: _Builder, kind: AnomalyKind) -> int:
    """Plant one irregularity of ``kind``. Returns the number of vouchers added."""
    match kind:
        case AnomalyKind.DUPLICATE_PAYMENT:
            return _duplicate_payment(b)
        case AnomalyKind.ROUND_AMOUNT:
            return _round_amount(b)
        case AnomalyKind.AFTER_HOURS_POSTING:
            return _after_hours(b)
        case AnomalyKind.WEEKEND_POSTING:
            return _sunday_posting(b)
        case AnomalyKind.PERIOD_END_CONCENTRATION:
            return _year_end_manual(b)
        case AnomalyKind.RARE_ACCOUNT_PAIR:
            return _rare_pair(b)
        case AnomalyKind.THRESHOLD_ADJACENT:
            return _threshold_adjacent(b)
        case AnomalyKind.MISSING_DOCUMENT_REF:
            return _missing_document(b)
        case AnomalyKind.UNUSUAL_PREPARER_ACCOUNT:
            return _unusual_preparer(b)
        case AnomalyKind.POST_CLOSE_ENTRY:
            return _post_close(b)


def _duplicate_payment(b: _Builder) -> int:
    """The same vendor invoice settled twice, days apart. The second is the anomaly."""
    vendor = b.rng.choice(coa.VENDORS)
    amount = b.amount_paise()
    ref = b.doc_ref("BP")
    day = b.working_day()
    legs: list[Leg] = [("2000", amount, 0), ("1010", 0, amount)]
    narration = f"Payment to {vendor} against invoice"

    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=legs,
        narration=narration,
        document_ref=ref,
        approved_by=_approver(b, amount),
    )
    again = day + timedelta(days=b.rng.randint(1, 4))
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=again,
        posted_at=b.business_time(again),
        legs=legs,
        narration=narration,
        document_ref=ref,
        approved_by=_approver(b, amount),
        anomalies=[AnomalyKind.DUPLICATE_PAYMENT],
        note=f"Second settlement of the same invoice {ref}, {(again - day).days} days later",
    )
    return 2


def _round_amount(b: _Builder) -> int:
    """A large, exactly round figure in an account whose values are normally irregular."""
    amount = b.rng.choice([2, 3, 5, 7, 10, 15]) * 100_000_00  # ₹2,00,000 … ₹15,00,000
    code = b.rng.choice(["5900", "5500", "5600"])
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[(code, amount, 0), ("2000", 0, amount)],
        narration=f"Provision towards {coa.account(code).name.lower()}",
        document_ref=b.doc_ref("JV"),
        is_manual=True,
        anomalies=[AnomalyKind.ROUND_AMOUNT],
        note="Exactly round amount in an account with otherwise irregular values",
    )
    return 1


def _after_hours(b: _Builder) -> int:
    day = b.working_day()
    lo, hi = coa.AFTER_HOURS
    posted = datetime(  # noqa: DTZ001 — local-time books
        day.year,
        day.month,
        day.day,
        b.rng.randrange(lo, hi),
        b.rng.randrange(0, 60),
        b.rng.randrange(0, 60),
    )
    amount = b.amount_paise()
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=posted,
        legs=[("5900", amount, 0), ("2000", 0, amount)],
        narration="Expense booked",
        document_ref=b.doc_ref("JV"),
        is_manual=True,
        anomalies=[AnomalyKind.AFTER_HOURS_POSTING],
        note=f"Entered at {posted:%H:%M}, outside the 09:00–19:00 working window",
    )
    return 1


def _sunday_posting(b: _Builder) -> int:
    day = b.working_day()
    sunday = day + timedelta(days=(6 - day.weekday()) % 7 or 7)
    if sunday > b.cfg.fy_end:
        sunday -= timedelta(days=7)
    amount = b.amount_paise()
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=sunday,
        posted_at=b.business_time(sunday, lag_days=0),
        legs=[("5900", amount, 0), ("2000", 0, amount)],
        narration="Expense booked",
        document_ref=b.doc_ref("JV"),
        is_manual=True,
        anomalies=[AnomalyKind.WEEKEND_POSTING],
        note="Entered on a Sunday, when the office is closed",
    )
    return 1


def _year_end_manual(b: _Builder) -> int:
    """An undocumented manual journal dated 31 March — the classic year-end adjustment."""
    amount = b.amount_paise(mu=12.5)
    code = b.rng.choice(["5900", "5400", "5700"])
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=b.cfg.fy_end,
        posted_at=b.business_time(b.cfg.fy_end, lag_days=b.rng.randint(0, 2)),
        legs=[(code, amount, 0), ("2400", 0, amount)],
        narration="Year-end adjustment",
        document_ref=None,
        is_manual=True,
        anomalies=[AnomalyKind.PERIOD_END_CONCENTRATION],
        note="Manual journal dated 31 March with no supporting document",
    )
    return 1


def _rare_pair(b: _Builder) -> int:
    """Value routed through the suspense account — a pairing that occurs nowhere else."""
    amount = b.amount_paise(mu=12.0)
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=b.working_day(),
        posted_at=b.business_time(b.working_day()),
        legs=[("5110", amount, 0), ("1800", 0, amount)],
        narration="Adjustment entry",
        document_ref=None,
        is_manual=True,
        anomalies=[AnomalyKind.RARE_ACCOUNT_PAIR],
        note="Director Remuneration settled against Suspense Account",
    )
    return 1


def _threshold_adjacent(b: _Builder) -> int:
    """Just under the delegation limit, and conveniently unapproved."""
    amount = coa.APPROVAL_LIMIT_PAISE - b.rng.randint(100, 80_00)
    vendor = b.rng.choice(coa.VENDORS)
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("2000", amount, 0), ("1010", 0, amount)],
        narration=f"Part payment to {vendor}",
        document_ref=b.doc_ref("BP"),
        approved_by=None,
        anomalies=[AnomalyKind.THRESHOLD_ADJACENT],
        note="Falls just below the approval limit and carries no approver",
    )
    return 1


def _missing_document(b: _Builder) -> int:
    """A material manual entry with no evidence at all — the evidence gap."""
    amount = b.amount_paise(mu=12.8)
    code = b.rng.choice(["5900", "5600", "5400"])
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[(code, amount, 0), ("1010", 0, amount)],
        narration="Expense reimbursed",
        document_ref=None,
        is_manual=True,
        anomalies=[AnomalyKind.MISSING_DOCUMENT_REF],
        note="Material manual entry with no supporting document reference",
    )
    return 1


def _unusual_preparer(b: _Builder) -> int:
    """Posted by someone who never otherwise touches these accounts."""
    amount = b.amount_paise()
    codes = ["5110", "1010"]
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=b.working_day(),
        posted_at=b.business_time(b.working_day()),
        legs=[(codes[0], amount, 0), (codes[1], 0, amount)],
        narration="Remuneration paid",
        document_ref=b.doc_ref("BP"),
        created_by=b.outsider_for(codes),
        is_manual=True,
        anomalies=[AnomalyKind.UNUSUAL_PREPARER_ACCOUNT],
        note="Preparer is outside their normal area of work for this account",
    )
    return 1


def _post_close(b: _Builder) -> int:
    """Dated inside the year but entered long after the books were closed."""
    day = b.cfg.fy_end - timedelta(days=b.rng.randint(0, 20))
    posted = b.business_time(b.cfg.fy_end + timedelta(days=b.rng.randint(60, 120)), lag_days=0)
    amount = b.amount_paise(mu=12.2)
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=posted,
        legs=[("5900", amount, 0), ("2400", 0, amount)],
        narration="Prior period expense recorded",
        document_ref=None,
        is_manual=True,
        is_post_close=True,
        anomalies=[AnomalyKind.POST_CLOSE_ENTRY],
        note=f"Dated {day} but entered on {posted:%Y-%m-%d}, after the books were closed",
    )
    return 1
