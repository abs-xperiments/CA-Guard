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

from datetime import datetime, timedelta

from caguard.benchmark import coa
from caguard.benchmark.anomalies import AnomalyKind
from caguard.benchmark.generator import Leg, _Builder
from caguard.schema import VoucherType

# --- ordinary business -------------------------------------------------------
# The trading cycles, payroll and statutory remittances live in
# :mod:`caguard.benchmark.cycles`. They were moved out when an internal review
# found the generator was producing vouchers rather than books; keeping them
# separate makes the distinction visible.

# Payroll and depreciation are emitted once a month by the generator, not drawn
# from here. Salary is a monthly run; drawing it at random produced roughly 280
# payroll runs in a single year and ₹39 crore of wages against ₹8 crore of sales.
_NORMAL_MIX: tuple[tuple[str, int], ...] = (
    ("sales", 34),
    ("purchase", 30),
    ("expense", 12),
    ("cash", 16),
)
_KINDS = [k for k, _ in _NORMAL_MIX]
_WEIGHTS = [w for _, w in _NORMAL_MIX]


def emit_normal(b: _Builder) -> int:
    """One ordinary business event. Returns the number of vouchers it produced.

    A sale or a purchase usually produces two vouchers, because the invoice and
    its settlement are the same event seen twice.
    """
    from caguard.benchmark import cycles

    kind = b.rng.choices(_KINDS, weights=_WEIGHTS)[0]
    match kind:
        case "sales":
            return cycles.emit_sales_cycle(b)
        case "purchase":
            return cycles.emit_purchase_cycle(b)
        case "expense":
            return cycles.emit_expense_payment(b)
        case _:
            return cycles.emit_cash_activity(b)


def _approver(b: _Builder, amount: int) -> str | None:
    """Entries above the delegation limit are approved; smaller ones need not be."""
    return b.rng.choice(coa.APPROVERS) if amount >= coa.APPROVAL_LIMIT_PAISE else None


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


#: Round figures a manufactured provision might use, and the accounts whose
#: values are otherwise irregular.
_ROUND_FIGURES: tuple[int, ...] = (2, 3, 5, 7, 10, 15, 20, 25)
_ROUND_ACCOUNTS: tuple[str, ...] = ("5900", "5500", "5600")


def _round_amount(b: _Builder) -> int:
    """A large, exactly round figure in an account whose values are normally irregular."""
    # Varied deterministically so no (account, amount) pair repeats. Planting
    # ₹2,00,000 on Professional Fees three times turns it into a retainer, and a
    # detector that ignored it would be right to.
    figure = _ROUND_FIGURES[b.occurrence("round") % len(_ROUND_FIGURES)]
    code = _ROUND_ACCOUNTS[
        (b.occurrence("round_account") // len(_ROUND_FIGURES)) % len(_ROUND_ACCOUNTS)
    ]
    amount = figure * 100_000_00
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
        posted_at=b.business_time(sunday, lag_days=0, allow_sunday=True),
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


#: Account combinations that make no business sense together. Varied rather than
#: repeated: planting one pairing eight times would make it common, and a signal
#: that "found" it would be finding an artefact of the generator.
_ODD_PAIRINGS: tuple[tuple[str, str], ...] = (
    ("5110", "1800"),  # Director Remuneration settled against Suspense
    ("1800", "1010"),  # Suspense cleared straight to bank
    ("5900", "1800"),  # Miscellaneous Expenses parked in Suspense
    ("1800", "4100"),  # Suspense released to Other Income
    ("5920", "2000"),  # Depreciation booked against a trade creditor
    ("3100", "1010"),  # Retained Earnings paid out of the bank account
    ("1500", "4000"),  # Plant & Machinery credited to Sales
    ("2500", "4100"),  # Term loan written back to Other Income
)


def _rare_pair(b: _Builder) -> int:
    """A combination of accounts that occurs almost nowhere else in the ledger."""
    debit, credit = _ODD_PAIRINGS[b.occurrence("rare_pair") % len(_ODD_PAIRINGS)]
    amount = b.amount_paise(mu=12.0)
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[(debit, amount, 0), (credit, 0, amount)],
        narration="Adjustment entry",
        document_ref=None,
        is_manual=True,
        anomalies=[AnomalyKind.RARE_ACCOUNT_PAIR],
        note=f"{coa.account(debit).name} settled against {coa.account(credit).name}",
    )
    return 1


def _threshold_adjacent(b: _Builder) -> int:
    """Just under the delegation limit, and conveniently unapproved."""
    amount = coa.APPROVAL_LIMIT_PAISE - b.rng.randint(100, 4_500_00)
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


#: Accounts with a clear regular owner, each paired with what the entry would
#: plausibly say. Varied for the same reason as the odd pairings: eight entries
#: by the same person on the same account stops being unusual and starts being
#: that person's job.
_OFF_PATCH_TARGETS: tuple[tuple[str, str], ...] = (
    ("5110", "Remuneration paid"),
    ("4000", "Sales adjustment posted"),
    ("5000", "Purchase adjustment posted"),
    ("5100", "Wages settled"),
    ("5500", "Consultant paid"),
)


def _unusual_preparer(b: _Builder) -> int:
    """Posted by someone outside their normal area of work for this account."""
    target, narration = _OFF_PATCH_TARGETS[b.occurrence("off_patch") % len(_OFF_PATCH_TARGETS)]
    codes = [target, "1010"]
    amount = b.amount_paise()
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[(target, amount, 0), ("1010", 0, amount)],
        narration=narration,
        document_ref=b.doc_ref("BP"),
        created_by=b.outsider_for(codes),
        is_manual=True,
        anomalies=[AnomalyKind.UNUSUAL_PREPARER_ACCOUNT],
        note=f"Preparer is outside their normal area of work for account {target}",
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
