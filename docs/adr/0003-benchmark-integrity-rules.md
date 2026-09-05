# ADR-0003 — Benchmark integrity rules for the project-owned generator

- **Date:** 2026-09-06
- **Status:** Proposed
- **Driven by:** ADR-0001

## Context
Once ADR-0001 makes our own generator the sole accuracy benchmark, the project faces an obvious and fatal criticism: *"you detect what you planted."* Any faculty reviewer or examiner will raise it. Circularity would invalidate the research contribution regardless of how good the code is.

## Decision
These rules are binding from Phase 1 and are enforced in code review and CI where testable.

1. **Separation of powers.** The generator and the detectors are separate modules sharing no constants, thresholds or helper functions. No detector imports from the generator package. Ground truth is written to a separate artefact the detectors never read.
2. **Confounders are mandatory.** Every planted anomaly class ships with legitimate look-alikes: genuinely round contract values, legitimate weekend postings, legitimate year-end accruals, legitimate recurring entries that resemble duplicates. Flagging a confounder counts as a false positive.
3. **Realistic base rates.** ~1–3% of documents carry a planted anomaly, matching audit reality — not a convenient 20%.
4. **Held-out seeds.** Thresholds and fusion weights are tuned only on seeds 1–3. Reported results come only from unseen seeds (100+). Thresholds are committed to git *before* the held-out run.
5. **Report per-type recall.** No single headline F1. A number that hides which anomaly classes fail is not a result.
6. **Run-once discipline.** The held-out evaluation is run once per release. Re-tuning after seeing held-out results requires a new seed set and a journal entry saying so.
7. **Stated external-validity limit.** Every write-up states plainly: results are on synthetic data; no real Indian ledger has been evaluated.

## Consequences
- Metrics will be lower and less flattering than a naive setup would produce. That is the intent.
- Rule 4 costs real time — thresholds cannot be nudged after seeing the final numbers.
- Rule 2 makes the generator meaningfully harder to write. It is the difference between a benchmark and a demo.

## Additional mitigation (recommended, not binding)
Show generated samples to one practising CA during Phase 1. Cheap, and it is the only available check on whether the "Indian-style" data is actually plausible.
