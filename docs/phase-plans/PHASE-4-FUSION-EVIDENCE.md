# Phase 4 — Risk fusion and evidence

**Goal:** turn independent signals into one prioritised review queue, with the **evidence gap as a first-class input**, and every finding able to show exactly why it ranks where it does.

## What "beating the baseline" means here

Phase 3 set the bar: rules alone already reach **100% recall with zero legitimate entries queued**. Fusion cannot improve recall — there is nothing left to find.

So the honest measure is not recall. It is **ordering**:

1. **Precision@K** — a reviewer works down a finite list. Of the first 25 items, how many deserved the attention?
2. **Queue compression** — at a priority threshold that still retains ~95% of the anomalies, how much smaller is the queue than the 5.8% rules-alone flags?
3. **Rows to first find** — how far down before the reviewer sees something real?

If fusion does not improve these, this phase reports that.

## The experiment that matters: does the evidence gap help?

`docs/03_PATENT_AND_IP.md` identifies **evidence-gap-driven prioritisation** as the one candidate mechanism the prior-art search did not find occupied. Phase 4 is where it becomes testable.

An ablation, on held-out seeds:

| Variant | |
|---|---|
| A | Fusion **without** any evidence term |
| B | Fusion **with** the evidence-completeness term |

Same weights, same signals, same seeds — one difference. If B does not beat A, the mechanism does not work and the IP discussion must be revised accordingly. **This is a genuine experiment and may fail.**

## Design decisions

### D1 — Noisy-OR, not a weighted sum
A sum lets three weak signals outrank one decisive one, and can exceed 1 without meaning anything. Noisy-OR — `1 − Π(1 − wₖ·sₖ)` — treats each signal as independent evidence, stays bounded in [0, 1], and has an ordinary reading: the chance that at least one concern is real.

### D2 — Weights are frozen before the held-out run
Recorded in ADR-0006, committed before any held-out seed is scored (ADR-0003 rule 4). Set from Phase 2 and 3 evidence — `threshold_adjacent` scores lowest because its precision was ~5%; `ml_anomaly` lowest of all per D-020.

### D3 — The model may not raise a voucher on its own
D-020, enforced in code, not in prose: an ML score contributes only when a non-ML signal is already present. Phase 3 showed it queues legitimate entries it cannot distinguish from real ones.

### D4 — Evidence completeness is composite and context-aware
Not merely "is there a document". An approver is only expected above the delegation limit, so a small unapproved payment is not an evidence gap — that distinction is exactly what kept the decoys out of the queue in Phase 2.

### D5 — Every finding carries its own arithmetic
`Finding.contributions` gives the per-signal contribution to the final score. A reviewer who disagrees must be able to see the working, and Phase 5's model may explain only from it.

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Evidence completeness scoring | `review/evidence.py` |
| 2 | Finding schema, risk bands, source-row linkage | `review/finding.py` |
| 3 | Transparent noisy-OR fusion | `review/fusion.py` |
| 4 | Ablation harness | `evaluation/ablation.py` |
| 5 | `caguard review` command | `cli.py` |

## Test plan

| Test | Asserts |
|---|---|
| `test_evidence` | a documented, approved voucher scores 1.0; a bare manual entry scores low; a small unapproved payment is not penalised |
| `test_fusion_bounds` | priority stays in [0, 1]; more signals never lower it |
| `test_fusion_transparency` | contributions sum consistently and name every contributing signal |
| `test_ml_cannot_raise_alone` | a voucher with only an ML hit stays out of the high band |
| `test_finding_links_to_source_rows` | every finding names the ledger lines behind it |
| `test_ranking_beats_unranked` | precision@25 improves over the rules-alone queue |
| `test_evidence_ablation` | the evidence term is measured, and the result recorded either way |

## Acceptance criteria — **all met, 2026-09-06**

- [x] Evidence completeness implemented, context-aware
- [x] Findings carry signals, contributions, evidence and source rows
- [x] Fusion transparent, bounded, deterministic
- [x] ML cannot raise a voucher alone
- [x] Precision@K and queue compression measured on held-out seeds
- [x] **Evidence ablation run and reported, including if it fails**
- [x] ruff / pyright / pytest green; docs, journal, clean commit

## Out of scope
The LLM (Phase 5), the UI (Phase 6), reviewer decisions and audit trail (Phase 6).

---

## Outcome (2026-09-06)

Held-out seeds 101–105, 4,000 vouchers each, 80 planted. Full record in ADR-0006.

| Variant | Queue | p@10 | p@25 | p@50 | Items to reach 95% | Recall |
|---|---|---|---|---|---|---|
| **fusion (full)** | 233 | **1.00** | **1.00** | **0.88** | **157** | 0.998 |
| no evidence uplift | 233 | 1.00 | 1.00 | 0.87 | 157 | 0.998 |
| **no evidence at all** | 230 | 0.70 | 0.82 | 0.82 | 215 | 0.960 |
| no model | 233 | 1.00 | 1.00 | 0.88 | 157 | 0.998 |
| **unranked (ledger order)** | 233 | 0.44 | 0.34 | 0.32 | 229 | 0.998 |

**Ranking clears the bar, decisively.** Against the same queue in ledger order, precision in the first 25 items goes from **34% to 100%**, and reaching 95% of the findings takes 157 items instead of 229 — **31% less work**.

**The evidence gap is load-bearing.** Removing evidence entirely costs 30 points at p@10, 18 at p@25, and drops recall from 99.8% to 96%. This is the first real support for the mechanism `docs/03_PATENT_AND_IP.md` singles out — still a *candidate*, not a novelty claim.

**But the separate uplift term is nearly redundant** (+1.6 points at p@50, nothing elsewhere). The work is done by evidence as a **detection signal**, not as a score adjustment. Worth stating plainly, because it sharpens what the mechanism actually is.

**The model contributes nothing**, again — "no model" is identical to full on every measure. The low weight and the corroboration rule are keeping it harmless, as ADR-0005 intended.
