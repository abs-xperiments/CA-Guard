"""Chart of accounts, people and transaction templates for a mid-size Indian firm.

Modelled on a trading/manufacturing private limited company with GST
registration and routine TDS obligations — the kind of client whose ledger a
practising CA actually scrutinises. Account names, tax splits and voucher types
follow Indian convention so that a CA reviewing the generated data can judge
whether it looks like a real book (the Phase 1 validation activity).

Values here are *generation* constants. No detector may read them (ADR-0003).
"""

from __future__ import annotations

from typing import NamedTuple

from caguard.schema import AccountGroup, VoucherType


class Account(NamedTuple):
    code: str
    name: str
    group: AccountGroup


# --- Chart of accounts -------------------------------------------------------
# Codes follow the common Indian convention: 1xxx assets, 2xxx liabilities,
# 3xxx equity, 4xxx income, 5xxx expenses.
ACCOUNTS: tuple[Account, ...] = (
    Account("1000", "Cash in Hand", AccountGroup.ASSET),
    Account("1010", "HDFC Bank - Current A/c", AccountGroup.ASSET),
    Account("1011", "ICICI Bank - Current A/c", AccountGroup.ASSET),
    Account("1100", "Sundry Debtors", AccountGroup.ASSET),
    Account("1200", "Inventory - Raw Material", AccountGroup.ASSET),
    Account("1210", "Inventory - Finished Goods", AccountGroup.ASSET),
    Account("1300", "GST Input Credit - CGST", AccountGroup.ASSET),
    Account("1301", "GST Input Credit - SGST", AccountGroup.ASSET),
    Account("1400", "Advance to Suppliers", AccountGroup.ASSET),
    Account("1500", "Plant & Machinery", AccountGroup.ASSET),
    # Contra-asset. Schedule II of the Companies Act expects depreciation to
    # accumulate here so gross block, depreciation and net block stay visible —
    # crediting the asset directly hides all three.
    Account("1590", "Accumulated Depreciation", AccountGroup.ASSET),
    Account("1520", "Computers", AccountGroup.ASSET),
    Account("1600", "Prepaid Expenses", AccountGroup.ASSET),
    # A suspense account is where unexplained entries go to be forgotten; it is a
    # standing audit red flag and the generator uses it in rare-pair anomalies.
    Account("1800", "Suspense Account", AccountGroup.ASSET),
    Account("2000", "Sundry Creditors", AccountGroup.LIABILITY),
    Account("2100", "GST Payable - CGST", AccountGroup.LIABILITY),
    Account("2101", "GST Payable - SGST", AccountGroup.LIABILITY),
    Account("2200", "TDS Payable - 194C Contractors", AccountGroup.LIABILITY),
    Account("2201", "TDS Payable - 194J Professional", AccountGroup.LIABILITY),
    Account("2202", "TDS Payable - 192 Salary", AccountGroup.LIABILITY),
    Account("2300", "Salaries Payable", AccountGroup.LIABILITY),
    Account("2310", "PF Payable", AccountGroup.LIABILITY),
    Account("2400", "Provision for Expenses", AccountGroup.LIABILITY),
    Account("2500", "Term Loan - HDFC Bank", AccountGroup.LIABILITY),
    Account("3000", "Share Capital", AccountGroup.EQUITY),
    Account("3100", "Retained Earnings", AccountGroup.EQUITY),
    Account("4000", "Sales - Domestic", AccountGroup.INCOME),
    Account("4010", "Sales - Export", AccountGroup.INCOME),
    Account("4100", "Other Income", AccountGroup.INCOME),
    Account("5000", "Purchases - Raw Material", AccountGroup.EXPENSE),
    Account("5100", "Salaries & Wages", AccountGroup.EXPENSE),
    Account("5110", "Director Remuneration", AccountGroup.EXPENSE),
    Account("5200", "Rent", AccountGroup.EXPENSE),
    Account("5210", "Electricity Charges", AccountGroup.EXPENSE),
    Account("5300", "Freight & Transport", AccountGroup.EXPENSE),
    Account("5400", "Repairs & Maintenance", AccountGroup.EXPENSE),
    Account("5500", "Professional Fees", AccountGroup.EXPENSE),
    Account("5600", "Travelling & Conveyance", AccountGroup.EXPENSE),
    Account("5700", "Advertisement & Marketing", AccountGroup.EXPENSE),
    Account("5800", "Bank Charges", AccountGroup.EXPENSE),
    Account("5900", "Miscellaneous Expenses", AccountGroup.EXPENSE),
    Account("5910", "Interest on Term Loan", AccountGroup.EXPENSE),
    Account("5920", "Depreciation", AccountGroup.EXPENSE),
)

BY_CODE: dict[str, Account] = {a.code: a for a in ACCOUNTS}


def account(code: str) -> Account:
    return BY_CODE[code]


# --- People ------------------------------------------------------------------
# Accounts-team preparers. Kept small so that "this preparer never touches this
# account" is a meaningful statement in a one-year ledger.
PREPARERS: tuple[str, ...] = (
    "rmehta",
    "skulkarni",
    "pnair",
    "avarma",
    "dshah",
    "nreddy",
)
APPROVERS: tuple[str, ...] = ("iyer.cfo", "bose.mgr", "menon.fc")
SYSTEM_USER = "SYSTEM"

# Which preparers normally handle which account codes. The generator draws from
# this map for ordinary vouchers, so an off-map combination is genuinely unusual.
PREPARER_SCOPE: dict[str, frozenset[str]] = {
    "rmehta": frozenset({"4000", "4010", "1100", "2100", "2101"}),  # sales & GST output
    "skulkarni": frozenset({"5000", "2000", "1300", "1301", "1200"}),  # purchases & input GST
    "pnair": frozenset({"1010", "1011", "1000", "5800", "2500", "5910"}),  # banking & treasury
    "avarma": frozenset({"5100", "5110", "2300", "2310", "2202"}),  # payroll
    "dshah": frozenset({"5200", "5210", "5300", "5400", "5600", "5700", "5900"}),  # opex
    # professional fees, TDS and fixed assets
    "nreddy": frozenset({"5500", "2201", "2200", "1500", "1520", "5920", "1600"}),
}

# Vendor and customer names used in narrations and document references.
VENDORS: tuple[str, ...] = (
    "Shree Balaji Traders",
    "Ganesh Engineering Works",
    "Sunrise Polymers Pvt Ltd",
    "Kaveri Logistics",
    "Meridian Office Supplies",
    "Deccan Power Solutions",
    "Anand Associates",
    "Nova Industrial Spares",
)
CUSTOMERS: tuple[str, ...] = (
    "Vikram Auto Components Ltd",
    "Sahyadri Retail Pvt Ltd",
    "Trident Manufacturing Co",
    "Pinnacle Distributors",
    "Orchid Enterprises",
    "Rajdhani Marketing",
)

# --- Business rules the generator honours ------------------------------------
GST_RATE_PCT = 18  # split 9% CGST + 9% SGST for intra-state supply
TDS_194J_PCT = 10  # professional fees
TDS_194C_PCT = 2  # contractors
TDS_192_PCT = 8  # salary, approximated as an average slab deduction
PF_PCT = 12
#: Provident fund is 12% of *basic*, and basic is capped at ₹15,000 for the
#: statutory contribution — ₹1,800 per employee per month. Applying 12% to the
#: whole payroll figure overstates the liability materially.
PF_CEILING_BASIC_PAISE = 15_000_00
BASIC_SHARE_OF_GROSS = 0.5
#: Headcount behind a monthly payroll voucher, so the PF ceiling can be applied
#: per employee rather than to the aggregate.
EMPLOYEE_COUNT = 45

# Delegation-of-authority limit. Entries just under it are what the
# threshold-adjacency signal looks for in Phase 2.
APPROVAL_LIMIT_PAISE = 50_000_00

BUSINESS_HOURS = (9, 19)  # 09:00–19:00, ordinary posting window
AFTER_HOURS = (1, 5)  # 01:00–05:00, the anomalous window

VOUCHER_TYPES_IN_USE: tuple[VoucherType, ...] = (
    VoucherType.SALES,
    VoucherType.PURCHASE,
    VoucherType.RECEIPT,
    VoucherType.PAYMENT,
    VoucherType.JOURNAL,
    VoucherType.CONTRA,
)
