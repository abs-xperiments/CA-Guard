# Usability walk-throughs

**Done:** 2026-10-08 01:18 IST, on the production build with a synthetic 1,500-voucher ledger, in a real browser. Each persona's question is the brief's: *could this person understand what happened without opening the source code?*

These are walk-throughs by the developer, not research with real users. They catch what is visible from the outside. They do not replace a practising CA trying the product, which remains the most valuable outstanding check (see `docs/ca_validation/`).

## Persona 1 — experienced CA, under time pressure

Wants speed and precision.

| Observed | Verdict |
|---|---|
| Keyboard path: `j`/`k` to move, Enter to open, `e` for an exception, `i` to investigate, `/` to search, Escape to close. Hints are visible in the toolbar. | ✅ Works end to end, and is tested in the browser. |
| Clearing a finding needs a typed reason and has no shortcut. | ✅ Deliberate: it is the judgement someone will question later. |
| Search accepts an amount in any format, an account, a narration or a preparer. | ✅ |
| Report: observed and decided are separate; it names the source file with its fingerprint. | ✅ |
| Bulk actions (e.g. clear all low-priority findings at once) | **Considered, not built.** A bulk clearance would put one reason on many entries the reviewer never opened. That is exactly what a file reviewer should be able to rely on not happening. |

## Persona 2 — junior auditor (article assistant)

Needs clarity and explanation.

| Observed | Change |
|---|---|
| ✅ W3 (done 2026-10-08): Queue rows show voucher, date and amount, but not *what the transaction is*. You have to open each one to learn it is "Miscellaneous Expenses ← Provision for Expenses". | **Phase 8:** a quiet second line under the voucher with its accounts and narration (already in the queue data). |
| ✅ W4 (done 2026-10-08): "Evidence 15%" is unexplained; the card says "1 of 3 expected items present", which is understandable. | **Phase 8:** the queue uses the card's wording. |
| ✅ W5 (done 2026-10-08): No hint of where to start. | **Phase 8:** one line, shown only while nothing has been reviewed: start with the high ones; what `e`, `i` and clearing mean. |
| ✅ W6 (done 2026-10-08): The working says "6.7 robust deviations (flagged at 6.0 or more)": accurate, but a statistician's term. | **Phase 8:** plain wording, with the measure explained beside it. |
| The card's order (why → evidence → transaction → compared with → next steps) matches the questions a junior asks. The limitation sits directly under the summary. | ✅ |

## Persona 3 — non-technical accounting professional, first day

Needs obvious navigation and minimal setup.

| Observed | Change |
|---|---|
| ✅ W1 (done 2026-10-08): A brand-new installation opens on "Sign in" with no accounts to sign in to; the way forward is a small link at the bottom. | **Phase 8:** with no accounts yet, go straight to "Create your account". |
| ✅ W2 (done 2026-10-08): "Drop a ledger here", but nothing says what file works. | **Phase 8:** one line on what a usable export contains. On the public demo, a **"Try it with a sample ledger"** button, so a reviewer without a ledger can see the product in one click. |
| Account creation explains that the first account becomes the administrator; the password hint is friendly. | ✅ |
| Upload progress names each step and opens the review on its own. | ✅ |
| A failed upload names the file, says why and that nothing was saved, and offers to retry. | ✅ (tested in the browser) |

## Follow-up (2026-10-08 01:38 IST)

All six findings are addressed in Phase 8 (see `docs/FINAL_COMPLETION_PLAN.md`). The browser tests now cover the first-run redirect and the sample ledger.
