# Dataset Strategy

## Goal
Use only free/publicly usable data for development and evaluation, with licensing documented in the repository.

## Recommended benchmark stack

### A. External corpus — DEMOTED 2026-09-06 (see ADR-0001)
> **Verified and demoted.** Licence and access pass: `apache-2.0`, ungated, public, **667,584 lines** (not 1M), 48 columns, 34 MB. But the `is_fraud`/`anomaly_type` labels are **not recoverable from the observable fields** — `DuplicatePayment` rows duplicate at 0.35× baseline, `RoundDollarManipulation` rows are round at 0.31× baseline, `LatePosting` rows show `is_post_close` at 0.0×. Only `VagueDescription` shows real signal (3.3×). Additionally `posting_date` is `00:00:00` for **every** row, so off-hours detection is unevaluable, and labels are document-level but replicated to every line.
>
> **VynFi is retained for ingestion, schema-mapping, throughput and demo data. It is rejected as a source of precision/recall/F1.**

**VynFi/vynfi-journal-entries-1m**
- synthetic journal-entry data;
- published with Apache License 2.0 by the associated open-source DataSynth project;
- intended for audit analytics;
- includes fraud-related labels and an accounting-oriented schema according to the project README.

Sources:
- https://github.com/mivertowski/SyntheticData
- https://huggingface.co/datasets/VynFi/vynfi-journal-entries-1m

Use a manageable subset during development. Do not pull the full dataset into the git repository.

### B. Project-owned benchmark
Generate an **Indian-style synthetic general ledger** in this repo using a fixed seed. It should imitate realistic accounting fields (date, voucher type, ledger/account, debit, credit, amount, user, narration, cost centre, approval status, document reference) without using any real person's or company's data.

Plant controlled anomalies with explicit ground truth, for example:
- duplicates;
- round-number spikes;
- unusual posting time;
- weekend/holiday entries;
- rare account-pair combinations;
- threshold-adjacent entries;
- unusual preparer/account combinations;
- missing supporting-document references;
- period-end concentration.

The generator must store the anomaly reason separately from the detector so evaluation is honest.

## Benchmark integrity rules (binding — see ADR-0003)
Because the project-owned generator is now the **sole** accuracy benchmark, "we detect what we planted" is the obvious criticism. Binding mitigations:
1. Generator and detectors are separate modules sharing no constants; ground truth is never read by a detector.
2. Confounders are mandatory — legitimate round numbers, legitimate weekend postings, legitimate year-end accruals, legitimate recurring near-duplicates. Flagging one is a false positive.
3. Realistic base rates (~1–3% of documents), not a convenient 20%.
4. Held-out seeds: tune on seeds 1–3, report only on unseen seeds 100+, with thresholds committed to git before the held-out run.
5. Report per-anomaly-type recall, never a single headline F1.
6. State the external-validity limit in every write-up: synthetic data only; no real Indian ledger evaluated.

## Rejected candidate
The 2026 SSRN paper “Generating Synthetic Journal Entries for Audit Analytics: Method and Dataset” is academically relevant, but the SSRN page says the copyright holder granted an all-rights-reserved license with no reuse allowed. It must not be treated as a redistributable project dependency without written permission.

Source:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7211804

## Data integrity rules
- No real personal financial data.
- Record source and license in `data/SOURCES.md`.
- Check dataset checksum/version where practical.
- Never commit large raw datasets.
- Keep generated data reproducible by seed.
- Separate train/dev/test at the entity/company level where applicable to reduce leakage.
