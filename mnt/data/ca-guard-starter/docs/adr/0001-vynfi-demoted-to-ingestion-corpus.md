# ADR-0001 — Demote VynFi from accuracy benchmark to ingestion/scale corpus

- **Date:** 2026-09-06
- **Status:** Proposed (blocks on founder decision F-1)
- **Supersedes:** D-003 in `DECISION_LOG.md`

## Context
`VynFi/vynfi-journal-entries-1m` was the designated primary external benchmark. Phase 0 required re-verifying its licence and accessibility. Licence and access pass cleanly: `apache-2.0`, ungated, public, 667,584 lines, 34 MB.

We went further and tested whether the ground-truth labels are *recoverable from the data*, which is the only property that makes a benchmark a benchmark. They are not.

Measured on a 200,000-line shard, lift of each label against the pattern its own name describes:

| Label | Test | Lift |
|---|---|---|
| `DuplicatePayment` | duplicate key | 0.35× |
| `RoundDollarManipulation` | amount % 1000 | 0.31× |
| `LatePosting`/`WrongPeriod`/`UnusualTiming` | `is_post_close` | 0.0× |
| `MissingDocumentation` | null `reference` | 1.0× |
| `VagueDescription` | null `line_text` | 3.3× |

Round-number labels were re-tested across all four amount columns and moduli 10/100/1000 before concluding. Fraud-labelled documents are also smaller and less manual than clean ones.

Two structural limits compound this: `posting_date` is `00:00:00` for every row (off-hours detection is unevaluable), and labels are document-level but replicated to every line (20.9% line-level vs 7.6% document-level).

## Decision
VynFi is **retained** as an ingestion, schema-mapping and throughput corpus, and as redistributable synthetic data for the public demo. It is **rejected** as a source of precision/recall/F1 figures. The project-owned seeded Indian generator becomes the sole accuracy benchmark.

## Consequences
- Positive: we avoid publishing near-random metrics that would read as detector failure; ingestion is still exercised against a genuinely foreign SAP-shaped export, which is a real robustness test.
- Negative: we lose external validity. The only labelled data is data we generated. This is a real weakness of the research and must be stated in the paper, not hidden.
- Mitigation is binding and lives in ADR-0003.

## Alternatives rejected
- *Use VynFi labels anyway* — would produce meaningless metrics.
- *Repair the labels ourselves* — we would be inventing ground truth for someone else's data, with no more validity than our own generator and less transparency.
- *SSRN 2026 dataset* — all-rights-reserved, no reuse permitted. Unchanged rejection.
