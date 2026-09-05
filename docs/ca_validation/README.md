# CA Validation Pack

**Purpose:** have one practising Chartered Accountant tell us whether our synthetic ledger looks like a real Indian book of accounts.

**Why this matters more than it sounds.** Phase 0 demoted the external VynFi corpus because its labels did not match its data, which leaves this project's own generated ledger as the *sole* accuracy benchmark. Every metric CA-Guard reports rests on it. If the data is not plausible, the metrics are not either — and nobody on the build team is a practising CA. This review is the only external check we have.

**Time required:** about 20 minutes. No software, no login, no NDA — the data is entirely synthetic and contains no real person or company.

---

## What to send

`sample_ledger_for_ca_review.csv` — 60 vouchers (189 lines) in the format a CA reads: voucher number, date, posting time, voucher type, ledger, debit, credit, narration, document reference, who entered it, who approved it.

It opens in Excel or Tally-style viewers directly.

## What to ask

Send these questions alongside the file.

### A. Does it look real?
1. Reading these entries cold, would you believe this came from a real mid-size Indian private limited company? If not, what gives it away first?
2. Are the **ledger names** ones you would actually see (Sundry Debtors, GST Input Credit - CGST, TDS Payable - 194J, Provision for Expenses)? Anything missing that you would expect in every ledger?
3. Are the **amounts** plausible in size and spread for a company of this scale?
4. Are the **narrations** written the way an accounts clerk writes them?
5. Do the **voucher types** (Sales, Purchase, Receipt, Payment, Journal, Contra) appear in a believable mix?

### B. Are the tax entries right?
6. GST is booked at 18% split as 9% CGST + 9% SGST on intra-state supply. Correct as shown?
7. TDS is deducted at 10% under 194J on professional fees and 2% under 194C on freight and contract work. Correct?
8. Salary vouchers deduct TDS under 192 and PF. Does the structure look right?

### C. What would actually make you look twice?
9. If you were scrutinising this ledger, **which of these 60 vouchers would you want to examine**, and why? *(Please answer before reading section D — we want your unprompted judgement.)*
10. What would you look at that our list below does not cover?

### D. Do our red flags match yours?
Only after answering Q9. We treat these as review heuristics, never as conclusions:

| What we flag | Do you agree this warrants a second look? |
|---|---|
| The same invoice settled twice within a few days | |
| A large, exactly round amount in an account whose values are normally irregular | |
| Entries posted between 01:00 and 05:00 | |
| Entries posted on a **Sunday** (we treat Saturday as a normal working day — correct?) | |
| Undocumented manual journals dated 31 March | |
| Value routed through the Suspense Account | |
| Amounts sitting just below the ₹50,000 approval limit | |
| Material manual entries with no supporting document reference | |
| An account touched by someone outside their normal area of work | |
| Entries dated in the year but posted long after the books closed | |

11. **Is ₹50,000 a realistic delegation-of-authority limit** for a company this size, or should it be higher?
12. Are any of these flags so common in practice that flagging them would just create noise?

### E. The things we deliberately made innocent
Our benchmark also contains legitimate entries that *look* suspicious, so that a detector which flags everything scores badly. Do you agree these are normally fine?

- Rent at exactly ₹2,00,000 every month under a lease
- An identical term-loan EMI every month
- Depreciation and provisions dated 31 March, documented and approved
- Bank charges auto-posted by the bank with no voucher reference
- A genuine invoice that happens to fall just under the approval limit

13. Any of these you *would* still want to see? Anything obvious we have missed?

---

## What to do with the answers

1. Record them in `docs/ca_validation/findings.md` with the date and the reviewer's role (no name needed).
2. Anything that changes the generator becomes a journal entry and a code change.
3. Anything that changes what we flag becomes a Phase 2 note.

**This review does not block engineering.** Phase 2 proceeds while it is outstanding; findings are folded in when they arrive.
