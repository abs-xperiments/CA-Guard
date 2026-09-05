# Dataset Strategy

## Goal
Use only free/publicly usable data for development and evaluation, with licensing documented in the repository.

## Recommended benchmark stack

### A. External benchmark candidate
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
