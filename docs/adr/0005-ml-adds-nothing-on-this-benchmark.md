# ADR-0005 — The model adds nothing on this benchmark, and the reason matters

- **Date:** 2026-09-06
- **Status:** Accepted
- **Phase:** 3

## Context

Phase 3 added a statistical layer (Benford conformity, robust amount outliers) and an Isolation Forest. The roadmap asked for a baseline comparison. The comparison had to be set up carefully, because the obvious version of it is worthless: our planted anomalies are **rule-shaped by construction** — round amounts, off-hours postings, missing documents — so a model fed features derived from those same attributes will find them and prove nothing.

The question actually worth asking is narrower:

> Does the model surface vouchers the rules missed, and were they worth a reviewer's time?

## Result (held-out seeds 101–105, 4,000 vouchers each)

| Approach | Recall | Precision | Queue | Legitimate entries wrongly queued |
|---|---|---|---|---|
| **rules** | **100%** | 34% | 5.8% | **0** |
| statistics | 10% | 85% | 0.2% | 0 |
| model | 51% | 51% | 2.0% | **30.4** |
| statistics + model | 52% | 50% | 2.0% | 30.4 |
| all | 100% | 29% | 6.7% | 30.4 |

**The model found zero anomalies the rules missed — on every one of the five seeds.** Adding it to the rules leaves recall unchanged at 100%, drops precision from 34% to 29%, and drags 30 legitimate vouchers into the queue.

## What the model wrongly queued

Across 1,000 decoys on five seeds:

| Count | Legitimate entry |
|---|---|
| 110 | Bank charges auto-posted by the bank feed |
| 40 | Monthly rent at exactly ₹2,00,000 under a lease |
| 2 | Documented year-end accruals |

This is the finding worth keeping. **Every one of those is statistically unusual and entirely proper.** Rent is exactly round and recurs; bank charges are tiny, undocumented and system-posted. An unsupervised model correctly identifies them as outliers — and it is wrong about all of them, because what makes them legitimate is the lease, the bank mandate and the approval, none of which is in the numbers.

Statistical unusualness is not audit relevance. That distinction is the project's thesis, and this is the first direct evidence for it.

## Decision

1. **The rules remain the primary detector.** The model does not replace them and is not promoted.
2. **The model is retained, weighted low, and required to corroborate.** Its honest role is finding what the rules were not written to anticipate — which on this benchmark is nothing, because we planted only what the rules look for. Phase 4 must weight it accordingly and must not let it raise a voucher on its own.
3. **Benford stays a per-account diagnostic**, never a per-voucher flag.
4. **This result is reported in any write-up**, including the negative part.

## The honest limit of this claim

This says the model adds nothing **on our benchmark**, and our benchmark's anomalies are rule-shaped because we wrote both. It is **not** evidence that unsupervised detection is useless on real ledgers. The opposite argument is quite strong: on a real client's books, containing irregularities nobody thought to write a rule for, a model that needs no such rule could be exactly what finds them.

What the result does support is narrower and defensible:

- ML alone is **not sufficient** for audit triage — it cannot distinguish unusual from improper.
- A system that flags legitimate recurring entries will be abandoned by a practitioner in the first week.
- The evidence and approval trail, which is not statistical information, is doing the work.

Testing whether the model earns its place requires a ledger with anomalies we did **not** plant. That needs real data, and is out of scope until a privacy-safe customer-data plan exists.

## Consequences

- `tests/test_statistical_ml.py` asserts the model finds nothing the rules missed. **If that test ever fails, the model has earned its place and the write-up must change.** It is written as a tripwire, not a guard.
- Phase 4 fusion must be measured against rules-alone as the baseline to beat. Adding signals that lower precision is not progress.
