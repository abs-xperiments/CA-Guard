# Phase 2 — Deterministic audit-review signals

**Authorized:** 2026-09-06
**Goal:** Ten deterministic signals that surface the planted irregularities **and leave the decoys alone**, each producing structured evidence a human (and later an LLM) can read.

## The two-sided bar

Phase 1 built decoys precisely so this phase cannot be graded on recall alone. A detector that flags every round number and every 31 March entry scores 100% recall and is useless: a CA drowns in false alarms on day one.

So every signal is measured twice:

1. **Recall** — of the vouchers where this kind was planted, how many did we surface?
2. **Decoy false-positive rate** — of the legitimate look-alikes built to trap this exact signal, how many did we wrongly flag?

Reported per signal. Never a single headline number (ADR-0003 rule 5).

## Design decisions

### D1 — Signals are named for what they observe, not for what was planted
`AnomalyKind.ROUND_AMOUNT` is ground truth; `SignalKind.ROUND_AMOUNT` is an observation. They are separate enums in separate packages that never import each other. The evaluation harness joins them; nothing else may.

### D2 — Detectors derive "normal" from the ledger in front of them
Rarity of an account pair, and whether a preparer usually touches an account, are computed from the uploaded data — never from the generator's constants. This is what makes the signals work on a real client ledger, and it is also what keeps ADR-0003 rule 1 honest.

### D3 — The approval limit is firm configuration, not a constant
Delegation limits differ by firm. `DetectorConfig.approval_limit_paise` defaults to ₹50,000 and is meant to be overridden. A detector that hardcoded the generator's limit would be cheating.

### D4 — Time-of-day signals must ask whether the time is real
`TimeFidelity.DATE_ONLY` means the source has no posting time. The off-hours signal returns nothing rather than flagging all 667,584 VynFi rows as midnight entries. This is the Phase 0 finding turned into code.

### D5 — Every hit carries structured evidence, not just a score
`SignalHit.evidence` is a dict of the actual facts behind the flag. Phase 5's LLM explains *from* this dict and may state nothing else. Building it now is what makes the grounded-explanation guarantee possible later.

### D6 — Thresholds are frozen before the held-out run
All thresholds live in one `DetectorConfig` and are recorded in ADR-0004, committed before any held-out seed is evaluated (ADR-0003 rule 4).

## How each signal avoids its decoy

| Signal | Its trap | How it escapes |
|---|---|---|
| Duplicate entry | Identical monthly EMI | Only fires inside a short window (≤7 days); a 30-day cadence is recurrence, not duplication |
| Round amount | Rent, round because the lease says so | Ignores an (account, amount) pair that repeats across the year — routine, not manufactured |
| Off-hours | — | Requires a real posting time |
| Weekend | Saturday working | Fires on Sunday only |
| Period-end concentration | Documented 31 March depreciation | Requires manual **and** missing document or approver |
| Threshold adjacent | A genuine invoice under the limit | Requires the approver to be absent |
| Missing evidence | Auto-posted bank charges | Requires materiality **and** a human preparer |
| Rare account pair | — | Rarity measured within the ledger |
| Unusual preparer | — | Compares against that preparer's own history |
| Post-close | — | Flag or a long posting lag |

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Signal kinds, hit record, config | `detect/types.py` |
| 2 | Precomputed ledger context (voucher view, frequency tables) | `detect/context.py` |
| 3 | The ten detectors | `detect/rules.py` |
| 4 | Runner over all enabled signals | `detect/runner.py` |
| 5 | Set-based metrics (recall, FPR, precision@K) | `evaluation/metrics.py` |
| 6 | `caguard detect` command | `cli.py` |
| 7 | Frozen thresholds recorded | `docs/adr/0004-*` |

## Test plan

| Test | Asserts |
|---|---|
| `test_rules` | each signal fires on a hand-built positive and stays silent on a hand-built negative |
| `test_signal_recall` | **per signal**, recall on planted anomalies meets its floor |
| `test_decoy_false_positives` | **per signal**, the decoy built to trap it is not flagged |
| `test_off_hours_respects_fidelity` | returns nothing for a `DATE_ONLY` ledger |
| `test_determinism` | same input → identical hits, twice |
| `test_evidence_is_structured` | every hit carries the facts behind its reason |
| `test_isolation` | **`detect/**` imports nothing from `benchmark`** — strict, no allowlist |
| `test_runs_on_vynfi` | signals execute on the real corpus without crashing (slow) |

## Acceptance criteria — **all met, 2026-09-06**

- [x] Ten signals implemented, each with structured evidence
- [x] Per-signal recall ≥ its documented floor on planted anomalies
- [x] Zero decoy false positives on the trap built for each signal
- [x] Off-hours silent on date-only sources
- [x] `detect/**` provably cannot import `benchmark`
- [x] Deterministic; runs on the full VynFi corpus
- [x] ruff / pyright / pytest green; docs, journal, clean commit

## Out of scope
Risk fusion and weighting (Phase 4), ML anomaly models (Phase 3), any LLM (Phase 5), UI (Phase 6). This phase produces independent signals, not a combined score.

---

## Outcome (2026-09-06)

Ten signals, measured on **seeds 101–105 which were never used while developing the thresholds**. Full table in ADR-0004.

- **Recall:** 100% on nine signals; 98% (min 88%) on `unusual_preparer_account`, which depends on the surrounding population.
- **Decoy false positives:** **0**, on every trap, on every seed — and **0 of 1,000 decoys** reached the queue by any route.
- **Queue:** 5.0% of vouchers, holding 100% of planted anomalies.
- **VynFi:** all signals run on the real 667,584-line corpus; `off_hours_posting` correctly stays silent.

### Four bugs found by measuring rather than assuming

1. **`rare_account_pair` flagged 95% of VynFi.** A chart of thousands of GL codes makes every pairing rare, so rarity stops distinguishing anything. It now abstains when most pairings fall under the ceiling — the same principle that keeps off-hours quiet on date-only data. VynFi queue: 95.6% → 13.3%.
2. **Two generator patterns computed `posted_at` from a *different* random day than `voucher_date`**, so vouchers appeared to be posted months before they were dated, spuriously tripping the post-close signal on 26 decoys.
3. **Ordinary postings could land on a Sunday**, because the posting lag never checked the weekday. That put 18 untouched vouchers into the weekend signal.
4. **Planting eight identical anomalies made them common.** A rare pairing repeated eight times is not rare, and one preparer posting to the same account eight times is doing their job. Both now vary across a set of combinations — which is also what a real ledger looks like.

Items 2–4 were faults in the benchmark, not the detectors. They are the reason the two-sided measurement exists.

### Also corrected
`threshold_band_paise` was ₹100 — narrow enough that only someone hugging the limit to the last rupee would be caught. Now ₹5,000 (10% of the limit), with the generator's planted spread widened to match.
