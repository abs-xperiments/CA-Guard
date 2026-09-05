# CA-Guard

**Design and Development of a Privacy-Preserving On-Premise Hybrid AI Framework for Evidence-Grounded Financial Anomaly Detection and Human-in-the-Loop Audit Review**

CA-Guard is a three-month academic prototype for Chartered Accountants and accountants. It reviews financial journal/transaction data, prioritises unusual items, explains why they were flagged, retrieves supporting evidence, and leaves the final decision to the professional.

## Product sentence
> A private AI second-hand that tells a CA what deserves attention.

## Scope
CA-Guard is limited to financial anomaly review and audit-oriented triage. It is **not** an autonomous auditor, tax filer, GST filer, ERP, or Tally replacement, and it does not determine fraud.

## Research hypothesis
Fusing deterministic audit-review rules, statistical deviations, ML anomaly signals **and evidence availability** produces a more useful review queue than a single detector, while evidence-grounded explanations make results easier for a professional to review.

Signal fusion itself is an engineering technique, not our novelty — commercial products already ship it. What this project contributes is the combination of **on-premise processing, open source, and a reproducible benchmark whose ground truth is inspectable**. See `docs/02_MARKET_AND_COMPETITIVE.md`.

## Status

| Phase | State |
|---|---|
| 0 — Research and decision gate | ✅ Complete (`docs/phase-plans/PHASE-0-RESEARCH-DECISION.md`) |
| 1 — Foundation: schema, intake, benchmark generator | ✅ Complete |
| 2 — Deterministic audit-review signals | ✅ Complete |
| 3 — Statistical + ML anomaly engine | ✅ Complete |
| 4 — Risk fusion + evidence | Next |
| 5–7 | Planned (`docs/11_IMPLEMENTATION_ROADMAP.md`) |

Ten deterministic signals now produce a review queue with structured evidence behind every finding. No scoring or fusion yet — signals stay independent so a reviewer sees *which* concern fired.

### Phase 2 result (seeds 101–105, never used while developing the thresholds)

| | |
|---|---|
| Per-signal recall | 100% on nine signals; 98% on `unusual_preparer_account` |
| Decoy false positives | **0** on every trap, and 0 of 1,000 decoys reached the queue |
| Queue size | 5.0% of vouchers, holding 100% of planted anomalies |

Full table and frozen thresholds in `docs/adr/0004-frozen-signal-thresholds.md`.

### Phase 3 result — the model adds nothing here, and that is the finding

| Approach | Recall | Precision | Legitimate entries wrongly queued |
|---|---|---|---|
| **rules** | **100%** | 34% | **0** |
| model (Isolation Forest) | 51% | 51% | 30 |
| all combined | 100% | 29% | 30 |

The model surfaced **zero** anomalies the rules missed, on every held-out seed, and queued legitimate entries instead: auto-posted bank charges, rent that is round because a lease fixed it, documented year-end accruals. All statistically unusual; all entirely proper. What makes them legitimate is the lease, the mandate and the approval — none of which is in the numbers.

**Statistical unusualness is not audit relevance.** That is the project's thesis and this is the first direct evidence for it. It is *not* a claim that ML is useless on real books — see `docs/adr/0005-ml-adds-nothing-on-this-benchmark.md` for the honest limits.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) and Python 3.13. Everything below runs locally and costs nothing.

```bash
make install        # create the venv and install dependencies
make check          # lint + type-check + tests — the gate every phase must pass
make generate       # write a reproducible synthetic Indian ledger
```

Generate a benchmark ledger and inspect a real corpus:

```bash
uv run caguard generate --vouchers 4000        # ledger + ground truth + manifest
uv run caguard columns  ledger.csv             # how do these headers map?
uv run caguard ingest   ledger.csv             # convert and report data quality
uv run caguard detect   ledger.csv             # run the signals, print the review queue
uv run caguard analyse  ledger.csv             # rules vs statistics vs model, side by side

make data                                       # fetch the VynFi corpus (~34 MB)
uv run caguard ingest data/external/shard0.parquet --vynfi
```

## Data

Two datasets, with deliberately different jobs (`data/SOURCES.md`, `docs/adr/0001-*`):

- **`VynFi/vynfi-journal-entries-1m`** (Apache-2.0, 667,584 lines) — used **only** for ingestion, schema mapping and throughput. Its fraud/anomaly labels are not recoverable from its data, so it is never used for accuracy metrics.
- **The project's own seeded Indian ledger** — the sole accuracy benchmark. Reproducible from a fixed seed, with ground truth written to a separate file that no detector may read, and with legitimate look-alike "decoys" that a careless detector will wrongly flag.

Generated and downloaded data is never committed.

## Privacy

The private path is self-hosted: sensitive data stays on the firm's machine and no external model is called. A future Railway demo would be a **public demonstration environment using synthetic data only** — it is not the private product. See `docs/08_SECURITY_PRIVACY.md`.

## Repository

```
src/caguard/
  money.py            integer paise, so vouchers balance exactly
  schema.py           the canonical journal-entry schema
  intake/             readers, column mapping, validation
  adapters/vynfi.py   the SAP-shaped external corpus
  detect/             signals, statistics and the model — cannot import benchmark/
  evaluation/         set metrics and the baseline comparison
  benchmark/          the generator — importable by nothing else (ADR-0003)
  cli.py
tests/                298 tests: integrity guards, ledger coherence, signal quality
docs/                 the method: charter, research, ADRs, phase plans
journal.md            the running record, in plain language
```

## Project rules
`CLAUDE.md` is the project constitution. Decisions live in `docs/DECISION_LOG.md` and `docs/adr/`.

## Licence
MIT. The generated benchmark contains no real person's or company's data.
