# CA Validation — Findings

**Review date:** 2026-09-06
**Reviewer:** Internal (Claude, acting as reviewer). **Not a practising Chartered Accountant.**

> **This does not close the validation.** The point of `docs/ca_validation/README.md` is an *external* check by someone who signs audit reports for a living. This review applies Indian accounting and audit knowledge rigorously and found real defects, but a practitioner will see things an internal review cannot. The pack remains outstanding.

Method: built a trial balance from a 4,000-voucher generated ledger and read it the way a reviewer opens a new client file — balances first, then the transaction cycles behind them.

---

## Verdict

**The ledger would not be accepted as a plausible set of books.** Individual vouchers are well formed — correct double entry, sensible GST and TDS mechanics, realistic narrations and document references. But the ledger as a whole has no balance-sheet logic: it is a stream of independent vouchers that balance individually and produce an impossible financial position collectively.

A CA would stop at the second line of the trial balance.

---

## Material findings

### F-1 — The bank account is overdrawn by ₹5.58 crore 🔴
`HDFC Bank - Current A/c` closes with a **credit** balance. The company paid out far more than it ever received, with no overdraft facility recorded anywhere. This is not an unusual balance; it is an impossible one.

**Cause:** receipts are generated independently of sales, and payments independently of purchases. Nothing ties cash in to cash out.

### F-2 — No opening balances at all 🔴
The ledger begins on 1 April with every account at zero: no share capital, no opening debtors or creditors, no fixed assets brought forward, no bank balance. The company apparently came into existence on the first day of the year and immediately traded ₹12.94 crore.

Every real engagement starts from the prior year's closing balances. Their absence is the first thing a reviewer notices.

### F-3 — Plant & Machinery shows a credit balance of ₹66.75 lakh 🔴
Two faults compounding. There is no opening asset cost, and depreciation is credited **directly to the asset account**. A fixed asset therefore appears as a liability.

Indian practice under Schedule II of the Companies Act, 2013 is to credit **Accumulated Depreciation** and carry the asset at cost, so that gross block, depreciation and net block are all visible.

### F-4 — Statutory dues accumulate all year and are never paid 🔴
| Liability | Closing | Statutory due date |
|---|---|---|
| TDS (192, 194C, 194J) | ₹1.13 crore | 7th of the following month |
| GST payable (CGST + SGST) | ₹2.32 crore | 20th of the following month |
| PF payable | ₹89.47 lakh | 15th of the following month |
| Salaries payable | ₹10.24 crore | monthly |

No remittance appears anywhere in the year. A reviewer would treat unpaid TDS of ₹1.13 crore as a reportable matter with interest and disallowance consequences — and would then discover the payments simply do not exist.

This also distorts the benchmark: an entire class of ordinary, high-volume transactions (statutory remittances) is missing, so "normal" is modelled wrongly.

### F-5 — The term loan has been over-repaid 🟠
`Term Loan - HDFC Bank` closes with a **debit** balance of ₹27.21 lakh. EMI principal is repaid against a loan that was never drawn.

### F-6 — Receivables and payables are implausible 🟠
Debtors of ₹9.15 crore against sales of ₹12.94 crore is roughly **258 days** outstanding. Creditors of ₹7.73 crore against purchases of ₹10.92 crore is similar. Both follow from F-1: collections and payments do not track the invoices that created them.

### F-7 — Salaries are provided but never disbursed 🟠
₹10.24 crore sits in Salaries Payable. Combined with F-4, staff have not been paid all year.

---

## Other findings

### F-8 — PF is computed on gross pay 🟠
Provident fund is 12% of **basic wages**, and the statutory ceiling is ₹15,000 of basic — a maximum of ₹1,800 per employee per month. Applying 12% to the full salary figure materially overstates the liability.

### F-9 — TDS is deducted without regard to thresholds 🟠
Section 194J applies above ₹30,000 in a year; 194C above ₹30,000 for a single payment or ₹1,00,000 in aggregate. The generator deducts on every payment, including trivial ones.

### F-10 — Depreciation posted only at year end 🟡
Monthly depreciation is the normal practice for a company preparing periodic accounts.

### F-11 — No round-off account 🟡
Effectively every Indian ledger carries one, because GST and TDS computations produce paise.

### F-12 — Missing statutory ledgers 🟡
No Professional Tax, no ESI, no IGST, and no TCS. `Sales - Export` exists in the chart of accounts but is never used, so all supply is implicitly intra-state — unrealistic for a company of this size.

### F-13 — Cash in hand of ₹1.21 crore 🟡
A company holding this much physical cash is implausible, and cash payments above ₹10,000 attract disallowance under section 40A(3). Contra withdrawals of lakhs into cash should not be routine.

### F-14 — GST computed by floor division 🟡
`taxable * 9 // 100` truncates. GST is computed to the rupee with normal rounding, which is part of why F-11 exists.

### F-15 — Bank charges carry no GST 🟡
Banks levy 18% GST on charges, and the input credit is claimed.

---

## What this means for the project

Findings F-1 to F-7 are **structural**: the generator produces vouchers, not a ledger. That matters beyond appearances, because the benchmark's whole value rests on the data being plausible (the Phase 0 finding that started this project). It also risks confounding the detectors — the absence of statutory remittances changes what the "normal" population looks like.

**Fixing F-1 to F-7 and F-8 is in scope now.** F-9 to F-15 are recorded for later; they affect presentation more than the shape of the population.

---

# Remediation (same day)

All material findings fixed. The generator was restructured from a stream of independent vouchers into a ledger with a balance-sheet position and linked transaction cycles. Ordinary business now lives in `benchmark/cycles.py`, separate from the planted irregularities.

## What changed

| Finding | Fix |
|---|---|
| **F-1** Bank overdrawn ₹5.58 cr | Sales create receivables that are later collected; purchases create payables that are later paid. Cash in now tracks cash out. |
| **F-2** No opening balances | A brought-forward position dated 1 April: share capital, bank, debtors, creditors, inventory, fixed assets, term loan. Retained earnings is the balancing figure, so it balances by construction. |
| **F-3** Fixed assets in credit | New **Accumulated Depreciation** account (1590). The asset stays at cost; depreciation accumulates against it and is charged monthly. |
| **F-4** Statutory dues never paid | Monthly remittances: TDS by the 7th, PF by the 15th, net GST by the 20th. Computed from what the ledger actually accrued, not invented. March dues stay outstanding — they fall due in April. |
| **F-5** Term loan over-repaid | Opening loan of ₹2.40 crore, against which the EMIs are repaid. |
| **F-6** 258 debtor days | Follows from F-1. Now ~120 days, with 15% of invoices legitimately unsettled at the year end. |
| **F-7** Salaries never disbursed | Payroll is provided at month end and disbursed within days. |
| **F-8** PF on gross pay | 12% of basic, per employee, against the ₹15,000 basic ceiling. |
| **F-10** Depreciation only at year end | Charged monthly. |
| **F-13** Cash of ₹1.21 crore | The petty-cash float is tracked, cannot go negative, and cash payments are held under the ₹10,000 section 40A(3) threshold. |

## Three further bugs the fix work exposed

1. **Payroll was drawn at random** instead of monthly — about 280 payroll runs in a single year and ₹39 crore of wages against ₹8 crore of sales.
2. **Purchases were drawn from the same distribution as sales**, leaving an 8% gross margin. A trading company at 8% is losing money, and the overdrawn bank was the symptom.
3. **The petty-cash float could go negative** on some seeds. Weighting withdrawals against payments balances them on average, not on every run; the float is now tracked explicitly.

## Trial balance after remediation

| | |
|---|---|
| Bank | ₹2,95,88,464 Dr |
| Cash in hand | ₹31,300 Dr |
| Sundry debtors | ₹3,25,24,868 Dr |
| Sundry creditors | ₹2,30,57,585 Cr |
| Plant & machinery / accumulated depreciation | ₹6,21,00,353 Dr / ₹2,41,15,721 Cr |
| Term loan | ₹2,14,77,615 Cr |
| Salaries, TDS, GST, PF payable | one month each |
| Turnover | ₹9,89,66,540, gross margin 34% |
| Debtor / creditor days | 120 / 129 |
| **Trial balance** | **nets to zero** |

## Encoded as tests

`tests/test_ledger_coherence.py` — 22 tests across three seeds, reading the ledger the way a reviewer opens a client file: balances first. None of this was visible to the Phase 1 tests, which checked vouchers one at a time.

## Not fixed — recorded for later

F-9 (TDS thresholds), F-11 (round-off account), F-12 (Professional Tax, ESI, IGST, export sales), F-14 (GST floor division), F-15 (GST on bank charges). These affect presentation rather than the shape of the population.

**Residual:** the company runs at an indicative loss. That is unusual but not implausible for a mid-size firm, and it is not an audit red flag in itself. Left as is.

**The external CA review remains outstanding.** This remediation came from an internal review. A practitioner will still see things it did not.
