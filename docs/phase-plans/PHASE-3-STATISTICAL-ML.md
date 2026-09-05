# Phase 3 — Statistical and ML anomaly engine

**Goal:** add a statistical layer and one ML model, and answer honestly whether either finds anything the deterministic rules do not.

## The question this phase must not dodge

Our planted anomalies are **rule-shaped**: round amounts, off-hours postings, missing documents, threshold adjacency. A model trained on features derived from those same attributes will find them, and that would prove nothing — it would be a restatement of Phase 2 with more machinery.

The honest question is narrower and harder:

> **Does the model surface vouchers the rules missed, and are those vouchers worth a reviewer's time?**

If the answer is no, this phase reports no. A negative result stated plainly is a real research finding; "we added ML and the number went up" would not be.

## Design decisions

### D1 — Benford is a population diagnostic, not a per-voucher signal
Benford's law describes a *distribution*. Asking "does this one voucher violate Benford" is meaningless. It is reported per account, as a conformity statistic a reviewer can act on, and used as a feature — never as a per-voucher flag.

### D2 — The model scores, the rules explain
An Isolation Forest gives an outlier score and no reason. That is acceptable only because it sits alongside rules that do give reasons, and because its own hit carries the feature values that drove it. It must never be the sole basis for a finding.

### D3 — Deterministic, or it is not evaluable
Fixed `random_state`, sorted inputs, a pinned feature order, and a recorded model version. Two runs over the same ledger must produce the same scores.

### D4 — Features are derived from the ledger only
Same rule as Phase 2 and enforced by the same isolation test: nothing under `detect/` may import the benchmark.

### D5 — Contamination is set from the expected review budget, not from the answer
`IsolationForest(contamination=...)` is the fraction it treats as outlying. Setting it from the known planted rate would leak the answer. It is set from what a reviewer can actually work through.

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Voucher feature matrix, pinned order | `detect/features.py` |
| 2 | Benford conformity per account; robust amount outliers | `detect/statistics.py` |
| 3 | Isolation Forest with version + determinism | `detect/model.py` |
| 4 | Baseline comparison harness | `evaluation/baselines.py` |
| 5 | `caguard analyse` command | `cli.py` |

## Test plan

| Test | Asserts |
|---|---|
| `test_features` | pinned column order; no NaN; identical for identical input |
| `test_benford` | matches the expected distribution on synthetic conforming data; detects a planted skew |
| `test_amount_outlier` | fires on a within-account outlier, not on a large-but-typical amount |
| `test_model_determinism` | same ledger → identical scores, twice |
| `test_model_no_leakage` | features contain nothing derived from ground truth |
| `test_baselines` | all three baselines run and are reported per-type |
| `test_isolation` | `detect/**` still cannot import `benchmark` |

## Acceptance criteria — **all met, 2026-09-06**

- [x] Statistical layer and Isolation Forest implemented, deterministic
- [x] Benford reported per account, not per voucher
- [x] Baseline comparison run on held-out seeds: rules alone, ML alone, and the union
- [x] **The overlap analysis is reported, including if ML adds nothing**
- [x] ruff / pyright / pytest green; docs, journal, clean commit

## Out of scope
Weighted fusion into a single priority score (Phase 4), the LLM (Phase 5), UI (Phase 6).

---

## Outcome (2026-09-06)

**The model adds nothing on this benchmark, and the reason is the interesting part.** Full record in ADR-0005.

Held-out seeds 101–105, 4,000 vouchers each:

| Approach | Recall | Precision | Queue | Legitimate entries wrongly queued |
|---|---|---|---|---|
| **rules** | **100%** | 34% | 5.8% | **0** |
| statistics | 10% | 85% | 0.2% | 0 |
| model | 51% | 51% | 2.0% | **30.4** |
| all | 100% | 29% | 6.7% | 30.4 |

The model found **zero** anomalies the rules missed, on every seed. Adding it leaves recall at 100%, drops precision from 34% to 29%, and pulls 30 legitimate vouchers into the queue.

### What it wrongly queued, and why that matters

Across 1,000 decoys: 110 auto-posted bank charges, 40 monthly rent payments at exactly ₹2,00,000 under a lease, 2 documented year-end accruals.

Every one is statistically unusual and entirely proper. What makes them legitimate is the lease, the bank mandate and the approval — none of which is in the numbers. **Statistical unusualness is not audit relevance**, and this is the first direct evidence for the project's thesis.

### The honest limit

Our anomalies are rule-shaped because we wrote both the rules and the planting. This is **not** evidence that unsupervised detection is useless on real books — on a client ledger containing irregularities nobody wrote a rule for, a model that needs no such rule could be exactly what finds them. Testing that needs real data.

`tests/test_statistical_ml.py::test_the_model_finds_nothing_the_rules_missed` is written as a **tripwire**: if the model ever does surface something the rules missed, the test fails and the write-up must change.
