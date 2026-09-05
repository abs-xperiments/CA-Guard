"""Ordinary business: opening balances, trading cycles, and statutory remittances.

Split out from the planted irregularities because this is where the *ledger*
lives. An internal review of the first version found that the generator produced
vouchers rather than books: each one balanced, but collectively they left the
bank overdrawn by ₹5.58 crore, fixed assets in credit, and a year of unpaid TDS
(``docs/ca_validation/findings.md``). A CA would have stopped at the second line
of the trial balance.

Three ideas fix that.

**Opening balances.** A company does not come into existence on 1 April with
nothing and immediately trade ₹13 crore. The year starts from a position.

**Linked cycles.** A sale creates a receivable that is later collected; a
purchase creates a payable that is later paid. Generating receipts independently
of sales is what drove debtors to 258 days and the bank into overdraft.

**Statutory remittances.** TDS by the 7th, PF by the 15th, GST by the 20th.
Beyond realism this matters to the benchmark: without them an entire class of
ordinary high-volume transactions is missing, so "normal" is modelled wrongly.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from caguard.benchmark import coa
from caguard.benchmark.generator import Leg, _Builder
from caguard.schema import VoucherType

# --- opening position --------------------------------------------------------

#: Brought-forward balances for a mid-size Indian manufacturer. Retained
#: earnings is the balancing figure, so the opening entry is balanced by
#: construction rather than by a hand-tuned number that could drift.
OPENING_DEBITS: tuple[tuple[str, int], ...] = (
    ("1000", 2_50_000_00),  # Cash in hand
    ("1010", 4_50_00_000_00),  # HDFC current account
    ("1100", 1_80_00_000_00),  # Sundry debtors
    ("1200", 95_00_000_00),  # Raw material inventory
    ("1500", 6_20_00_000_00),  # Plant & machinery, at cost
    ("1600", 12_00_000_00),  # Prepaid expenses
)
OPENING_CREDITS: tuple[tuple[str, int], ...] = (
    ("1590", 1_85_00_000_00),  # Accumulated depreciation
    ("2000", 1_45_00_000_00),  # Sundry creditors
    ("2500", 2_40_00_000_00),  # Term loan
    ("3000", 5_00_00_000_00),  # Share capital
)

#: Share of invoices that get settled within the year. The remainder is what
#: legitimately sits in debtors and creditors at the close.
SETTLEMENT_RATE = 0.85

#: Provident fund is 12% of *basic*, and basic is capped at ₹15,000 for the
#: statutory contribution — ₹1,800 per employee per month. The first version
#: applied 12% to the whole salary figure and overstated the liability.
PF_CEILING_BASIC_PAISE = 15_000_00
BASIC_SHARE_OF_GROSS = 0.5


def emit_opening_balances(b: _Builder) -> int:
    """The brought-forward position, dated the first day of the year."""
    debit_total = sum(amount for _, amount in OPENING_DEBITS)
    credit_total = sum(amount for _, amount in OPENING_CREDITS)
    retained = debit_total - credit_total
    if retained <= 0:
        raise AssertionError("opening credits exceed debits; retained earnings would be negative")

    legs: list[Leg] = [(code, amount, 0) for code, amount in OPENING_DEBITS]
    legs += [(code, 0, amount) for code, amount in OPENING_CREDITS]
    legs.append(("3100", 0, retained))

    b.cash_paise = _opening_amount("1000")
    b.add(
        voucher_type=VoucherType.OPENING_BALANCE,
        voucher_date=b.cfg.fy_start,
        posted_at=b.business_time(b.cfg.fy_start, lag_days=0),
        legs=legs,
        narration="Opening balances brought forward from the previous year",
        document_ref=b.doc_ref("OB"),
        created_by=coa.SYSTEM_USER,
        approved_by=b.rng.choice(coa.APPROVERS),
    )
    return 1


# --- trading cycles ----------------------------------------------------------


def emit_sales_cycle(b: _Builder) -> int:
    """A sales invoice and, usually, the collection that follows it."""
    day = b.working_day()
    customer = b.rng.choice(coa.CUSTOMERS)
    taxable = b.amount_paise()
    legs = b.sales_legs(taxable)
    invoice_total = sum(d for _, d, _ in legs)
    ref = b.doc_ref("INV")

    b.add(
        voucher_type=VoucherType.SALES,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=legs,
        narration=f"Sales to {customer} vide invoice {ref}",
        document_ref=ref,
        approved_by=_approver(b, invoice_total),
    )
    collected = _later(b, day, 15, 60)
    if collected is None or b.rng.random() > SETTLEMENT_RATE:
        return 1  # still outstanding at the year end, which is normal

    b.add(
        voucher_type=VoucherType.RECEIPT,
        voucher_date=collected,
        posted_at=b.business_time(collected),
        legs=[("1010", invoice_total, 0), ("1100", 0, invoice_total)],
        narration=f"Receipt from {customer} against invoice {ref}",
        document_ref=b.doc_ref("RCPT"),
    )
    return 2


#: Purchases run at roughly 70% of the sales scale, giving a gross margin near
#: 30%. Drawing both from the same distribution left an 8% margin — a company
#: that would be losing money, which duly showed up as an overdrawn bank.
PURCHASE_SCALE_MU = 10.95


def emit_purchase_cycle(b: _Builder) -> int:
    """A vendor bill and, usually, the payment that settles it."""
    day = b.working_day()
    vendor = b.rng.choice(coa.VENDORS)
    taxable = b.amount_paise(mu=PURCHASE_SCALE_MU)
    legs = b.purchase_legs(taxable)
    bill_total = sum(c for _, _, c in legs)
    ref = b.doc_ref("PINV")

    b.add(
        voucher_type=VoucherType.PURCHASE,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=legs,
        narration=f"Purchase from {vendor} vide bill {ref}",
        document_ref=ref,
        approved_by=_approver(b, bill_total),
    )
    paid = _later(b, day, 20, 60)
    if paid is None or b.rng.random() > SETTLEMENT_RATE:
        return 1

    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=paid,
        posted_at=b.business_time(paid),
        legs=[("2000", bill_total, 0), ("1010", 0, bill_total)],
        narration=f"Payment to {vendor} against bill {ref}",
        document_ref=b.doc_ref("BP"),
        approved_by=_approver(b, bill_total),
    )
    return 2


def emit_expense_payment(b: _Builder) -> int:
    """An operating expense settled from the bank, with TDS where it applies."""
    code, tds_pct, tds_account = b.rng.choice(_EXPENSE_MIX)
    gross = b.amount_paise(mu=10.1)
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=b.expense_legs(code, gross, tds_pct, tds_account),
        narration=f"{coa.account(code).name} paid, TDS deducted at source",
        document_ref=b.doc_ref("BP"),
        approved_by=_approver(b, gross),
    )
    return 1


def emit_payroll(b: _Builder, month_index: int, *, directors: bool = False) -> int:
    """Salary or director remuneration: provided at month end, then disbursed."""
    month_end = month_end_of(_month_start(b, month_index))
    disbursed = _later(b, month_end, 1, 5)
    gross = b.amount_paise(mu=12.4 if directors else 13.0)

    if directors:
        tds = gross * coa.TDS_192_PCT // 100
        legs: list[Leg] = [("5110", gross, 0), ("2202", 0, tds), ("2300", 0, gross - tds)]
        narration = "Director remuneration for the month, TDS deducted"
        payable = gross - tds
        author = "avarma"
    else:
        legs = b.salary_legs(gross)
        narration = "Salary payable for the month"
        payable = sum(c for code, _, c in legs if code == "2300")
        author = "avarma"

    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=month_end,
        posted_at=b.business_time(month_end, lag_days=1),
        legs=legs,
        narration=narration,
        document_ref=b.doc_ref("PAY"),
        approved_by=b.rng.choice(coa.APPROVERS),
        created_by=author,
        is_manual=True,
    )
    if disbursed is None:
        return 1

    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=disbursed,
        posted_at=b.business_time(disbursed),
        legs=[("2300", payable, 0), ("1010", 0, payable)],
        narration="Salaries disbursed for the month",
        document_ref=b.doc_ref("BP"),
        created_by=author,
        approved_by=b.rng.choice(coa.APPROVERS),
    )
    return 2


def emit_depreciation(b: _Builder, month_index: int) -> int:
    """Monthly depreciation, accumulated rather than charged against the asset."""
    day = month_end_of(_month_start(b, month_index))
    amount = b.amount_paise(mu=11.9)
    b.add(
        voucher_type=VoucherType.JOURNAL,
        voucher_date=day,
        posted_at=b.business_time(day, lag_days=1),
        legs=[("5920", amount, 0), ("1590", 0, amount)],
        narration="Depreciation charged for the month as per Schedule II",
        document_ref=b.doc_ref("JV"),
        approved_by=b.rng.choice(coa.APPROVERS),
        created_by="nreddy",
        is_manual=True,
    )
    return 1


def emit_contra(b: _Builder) -> int:
    """Cash drawn for petty office expenses. Deliberately small — a company
    withdrawing lakhs in cash would attract section 40A(3) attention."""
    day = b.working_day()
    amount = b.rng.randrange(20_000_00, 60_000_00, 5_000_00)
    b.cash_paise += amount
    b.add(
        voucher_type=VoucherType.CONTRA,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("1000", amount, 0), ("1010", 0, amount)],
        narration="Cash withdrawn from bank for petty office expenses",
        document_ref=b.doc_ref("CTR"),
    )
    return 1


#: Keep at least this much in hand before paying anything out of cash.
CASH_FLOAT_FLOOR = 5_000_00


def emit_cash_activity(b: _Builder) -> int:
    """Either draw cash or spend it, depending on what is in hand."""
    if b.cash_paise < CASH_FLOAT_FLOOR:
        return emit_contra(b)
    return emit_cash_expense(b)


def emit_cash_expense(b: _Builder) -> int:
    """A small expense settled in cash.

    Kept under ₹10,000 deliberately: cash payments above that threshold are
    disallowed under section 40A(3), so a company routinely paying more than
    this in cash would itself be a finding.
    """
    code = b.rng.choice(("5600", "5900", "5400"))
    ceiling = min(9_500_00, b.cash_paise)
    if ceiling < 500_00:
        return emit_contra(b)
    amount = b.rng.randrange(500_00, ceiling + 1, 100_00)
    b.cash_paise -= amount
    day = b.working_day()
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[(code, amount, 0), ("1000", 0, amount)],
        narration=f"{coa.account(code).name} paid in cash",
        document_ref=b.doc_ref("CP"),
    )
    return 1


def emit_opening_settlements(b: _Builder) -> int:
    """Collect the opening debtors and pay the opening creditors.

    Without this the brought-forward balances sit untouched all year and inflate
    debtor and creditor days, which is exactly what a reviewer computes first.
    """
    added = 0
    for code, total, contra, narration, ref in (
        ("1100", _opening_amount("1100"), "1010", "Receipt against opening debtors", "RCPT"),
        ("2000", _opening_amount("2000"), "1010", "Payment against opening creditors", "BP"),
    ):
        instalments = 4
        chunk = total // instalments
        for n in range(instalments):
            day = b.cfg.fy_start + timedelta(days=18 * (n + 1))
            while day.weekday() == 6:
                day += timedelta(days=1)
            legs: list[Leg] = (
                [(contra, chunk, 0), (code, 0, chunk)]
                if code == "1100"
                else [(code, chunk, 0), (contra, 0, chunk)]
            )
            b.add(
                voucher_type=VoucherType.RECEIPT if code == "1100" else VoucherType.PAYMENT,
                voucher_date=day,
                posted_at=b.business_time(day),
                legs=legs,
                narration=f"{narration} — instalment {n + 1} of {instalments}",
                document_ref=b.doc_ref(ref),
                created_by="pnair",
                approved_by=b.rng.choice(coa.APPROVERS),
            )
            added += 1
    return added


def _opening_amount(code: str) -> int:
    for account, amount in (*OPENING_DEBITS, *OPENING_CREDITS):
        if account == code:
            return amount
    raise KeyError(code)


def emit_loan_instalment(b: _Builder, month_index: int) -> int:
    """The monthly term-loan EMI: principal against the loan, interest to P&L."""
    day = _month_start(b, month_index)
    interest, principal = 47_318_00, 2_00_000_00
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day),
        legs=[("2500", principal, 0), ("5910", interest, 0), ("1010", 0, principal + interest)],
        narration="Term loan EMI debited by HDFC Bank",
        document_ref=b.doc_ref("EMI"),
        created_by="pnair",
        approved_by=b.rng.choice(coa.APPROVERS),
    )
    return 1


# --- statutory remittances ---------------------------------------------------


def emit_statutory_settlements(b: _Builder) -> int:
    """Discharge the month's TDS, PF and net GST in the following month.

    Runs last and reads what the rest of the ledger actually accrued, so the
    payments match the liabilities instead of being invented. March dues are
    deliberately left outstanding — they fall due in April, after the year end,
    which is what a real closing balance looks like.
    """
    accrued = _monthly_movement(b)
    months = sorted(accrued)
    added = 0

    for month in months[:-1] if len(months) > 1 else []:
        due = _next_month(month)
        movement = accrued[month]

        tds_legs = [
            (code, movement.get(code, 0), 0)
            for code in ("2202", "2200", "2201")
            if movement.get(code, 0) > 0
        ]
        tds_total = sum(d for _, d, _ in tds_legs)
        if tds_total > 0:
            added += _remit(
                b,
                due,
                7,
                [*tds_legs, ("1010", 0, tds_total)],
                "TDS remitted for the month under Chapter XVII-B",
                "TDSC",
            )

        pf = movement.get("2310", 0)
        if pf > 0:
            added += _remit(
                b,
                due,
                15,
                [("2310", pf, 0), ("1010", 0, pf)],
                "Provident fund contribution remitted for the month",
                "PFCH",
            )

        output = movement.get("2100", 0) + movement.get("2101", 0)
        credit = -(movement.get("1300", 0) + movement.get("1301", 0))
        net = output - credit
        if output > 0 and credit >= 0 and net > 0:
            added += _remit(
                b,
                due,
                20,
                [
                    ("2100", movement.get("2100", 0), 0),
                    ("2101", movement.get("2101", 0), 0),
                    ("1300", 0, -movement.get("1300", 0)),
                    ("1301", 0, -movement.get("1301", 0)),
                    ("1010", 0, net),
                ],
                "GST discharged for the month after set-off of input tax credit",
                "GSTC",
            )
    return added


def _remit(
    b: _Builder,
    month: tuple[int, int],
    day_of_month: int,
    legs: list[Leg],
    narration: str,
    ref_kind: str,
) -> int:
    year, mon = month
    day = date(year, mon, min(day_of_month, 28))
    while day.weekday() == 6:
        day += timedelta(days=1)
    b.add(
        voucher_type=VoucherType.PAYMENT,
        voucher_date=day,
        posted_at=b.business_time(day, lag_days=0),
        legs=legs,
        narration=narration,
        document_ref=b.doc_ref(ref_kind),
        created_by="pnair",
        approved_by=b.rng.choice(coa.APPROVERS),
    )
    return 1


def _monthly_movement(b: _Builder) -> dict[tuple[int, int], dict[str, int]]:
    """Net credit per statutory account per month, taken from the rows generated."""
    watched = {"2100", "2101", "1300", "1301", "2200", "2201", "2202", "2310"}
    movement: dict[tuple[int, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in b.rows:
        code = str(row["account_code"])
        if code not in watched:
            continue
        day = row["voucher_date"]
        assert isinstance(day, date)
        movement[(day.year, day.month)][code] += (
            int(row["credit_paise"]) - int(row["debit_paise"])  # pyright: ignore[reportArgumentType]
        )
    return {k: dict(v) for k, v in movement.items()}


def _next_month(month: tuple[int, int]) -> tuple[int, int]:
    year, mon = month
    return (year + 1, 1) if mon == 12 else (year, mon + 1)


# --- shared helpers ----------------------------------------------------------

_EXPENSE_MIX: tuple[tuple[str, int, str], ...] = (
    ("5500", coa.TDS_194J_PCT, "2201"),
    ("5300", coa.TDS_194C_PCT, "2200"),
    ("5400", coa.TDS_194C_PCT, "2200"),
    ("5700", coa.TDS_194C_PCT, "2200"),
)


def _approver(b: _Builder, amount: int) -> str | None:
    """Entries above the delegation limit are approved; smaller ones need not be."""
    return b.rng.choice(coa.APPROVERS) if amount >= coa.APPROVAL_LIMIT_PAISE else None


def _later(b: _Builder, day: date, low: int, high: int) -> date | None:
    """A working day between ``low`` and ``high`` days on, or None if past year end."""
    settled = day + timedelta(days=b.rng.randint(low, high))
    while settled.weekday() == 6:
        settled += timedelta(days=1)
    return None if settled > b.cfg.fy_end else settled


def month_end_of(day: date) -> date:
    nxt = date(day.year + (day.month == 12), day.month % 12 + 1, 1)
    return nxt - timedelta(days=1)


def _month_start(b: _Builder, month_index: int) -> date:
    """First working day of month ``month_index`` of the fiscal year (0 = April)."""
    month = (3 + month_index % 12) % 12 + 1
    year = b.cfg.fy_start_year + (1 if month < 4 else 0)
    day = date(year, month, 1)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day
