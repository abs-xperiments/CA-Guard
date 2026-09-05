# Phase 1 — Foundation

**Authorized:** 2026-09-06 (founder approval of F-1…F-4, C-1 = no spend)
**Goal:** A clean, typed, tested repository that can ingest real-shaped financial data into one canonical schema, and can generate a reproducible Indian benchmark whose ground truth is produced independently of any detector.

No detection logic ships in this phase. Phase 1 builds the *substrate* the research depends on.

---

## Design decisions taken in this phase

### D1 — Money is stored as integer paise
Floating-point rupees make debit/credit balance checks fail by ±0.01 and would force a fudge tolerance into the core of an *accounting* tool. The canonical Pydantic contract exposes `Decimal` rupees; the DataFrame layer stores `int64` paise. Balance checks are then exact, with no tolerance constant. Conversion is centralised in `caguard.money`.

### D2 — The canonical unit is the line; the unit of *review* is the voucher
VynFi taught us this: labels replicated across lines inflate line-level rates ~3×. `JournalLine` carries `voucher_id`; every finding and every metric is aggregated to the voucher.

### D3 — Posting timestamp carries time-of-day
VynFi's `posting_date` is `00:00:00` on every row, making off-hours detection unevaluable. Our schema separates `voucher_date` (the accounting date) from `posted_at` (a real timestamp). The Indian generator populates the time; the VynFi adapter records that it is unavailable rather than faking midnight as a real posting time.

### D4 — Indian fiscal year, not calendar year
Periods run April→March. Period 1 = April, period 12 = March. `FY2024-25`. Year-end concentration means **31 March**, not 31 December. This is not cosmetic — it is the axis the period-end signal will use in Phase 2.

### D5 — Generator/detector isolation is enforced by a test, not by discipline
ADR-0003 rule 1 is only real if CI fails when it is broken. `tests/test_isolation.py` walks the AST of every module outside `caguard.benchmark` and fails on any import of it.

---

## Deliverables

| # | Deliverable | Module |
|---|---|---|
| 1 | Repo at root, `.gitignore`, `pyproject.toml`, pinned Python 3.13 | — |
| 2 | Money conversion (rupees ↔ paise) | `caguard/money.py` |
| 3 | Canonical schema + enums + voucher aggregate | `caguard/schema.py` |
| 4 | CSV/XLSX readers with size/type limits | `caguard/intake/readers.py` |
| 5 | Column mapping (heuristic + explicit) to canonical | `caguard/intake/mapping.py` |
| 6 | Row-level validation with a structured error report | `caguard/intake/validation.py` |
| 7 | VynFi (SAP-shaped) adapter | `caguard/adapters/vynfi.py` |
| 8 | Indian chart of accounts + entity profile | `caguard/benchmark/coa.py` |
| 9 | Deterministic seeded generator | `caguard/benchmark/generator.py` |
| 10 | Planted anomalies (10 classes) | `caguard/benchmark/anomalies.py` |
| 11 | **Decoys** — legitimate look-alikes | `caguard/benchmark/decoys.py` |
| 12 | Ground-truth artefact writer | `caguard/benchmark/ground_truth.py` |
| 13 | CLI (`generate`, `ingest`, `profile`) | `caguard/cli.py` |
| 14 | CI: ruff + pyright + pytest | `.github/workflows/ci.yml` |
| 15 | CA validation pack (non-blocking) | `docs/ca_validation/` |

## Test plan (written alongside, not after)

| Test | Asserts |
|---|---|
| `test_money` | rupee↔paise round-trips exactly; rejects >2dp silently-lossy input |
| `test_schema` | debit XOR credit; non-negative; voucher balances to zero paise exactly; FY/period consistency |
| `test_mapping` | Indian, SAP and messy headers all map; ambiguous headers raise rather than guess |
| `test_validation` | bad rows are reported with row number and reason, and do not abort the file |
| `test_vynfi_adapter` | maps the real 48-column schema; marks `posted_at` time as unavailable; never invents labels |
| `test_generator_determinism` | same seed → byte-identical parquet; different seed → different data |
| `test_generator_balance` | **every** generated voucher balances exactly, anomalous ones included |
| `test_ground_truth` | truth file covers every planted anomaly and every decoy; base rate within 1–3% |
| `test_decoys` | each decoy class is present and is *not* marked anomalous |
| `test_isolation` | **no module outside `caguard.benchmark` imports it** (ADR-0003 rule 1) |
| `test_indian_realism` | INR only, FY Apr–Mar, Indian voucher types, GST/TDS ledgers present, posting times populated |

## Acceptance criteria — **all met, 2026-09-06**

- [x] Files at repo root; history preserved via `git mv`
- [x] `ruff check` + `ruff format --check` clean
- [x] `pyright` 0 errors
- [x] `pytest` green, no known failures carried forward
- [x] VynFi's 667,584 lines ingest through the canonical schema
- [x] Generator is byte-reproducible for a fixed seed
- [x] Ground truth is written to a separate artefact no detector reads
- [x] Decoys present; isolation test enforces ADR-0003
- [x] Docs + journal updated; clean tree; Conventional Commit
- [x] CA validation pack prepared (review itself is non-blocking)

## Out of scope (Phase 2+)
Any detector, scoring, fusion, LLM, API or UI. If it decides whether something is anomalous, it does not belong in Phase 1.

---

## Outcome (2026-09-06 03:05 IST)

| Criterion | Result |
|---|---|
| Repo at root | 33 files moved with tracked renames |
| ruff / ruff format | clean |
| pyright | 0 errors |
| pytest | **95 passed** (94 offline + 1 slow corpus test) |
| VynFi ingest | **667,584 lines in 28s**; 667,129 accepted (99.93%); 599 of 143,602 vouchers (0.42%) reported as unbalanced |
| Generator reproducibility | same seed → same SHA-256 content hash |
| Planted anomalies grounded | **lift 61×–500×** on every kind (VynFi was 0.31×–1.0×) |
| Decoys | 6 kinds; rent is exactly as round as the planted anomaly, separated only by evidence and approval |
| Isolation | enforced by AST test; caught one real violation on first run |

### Two things found by checking rather than assuming
1. **VynFi's own vouchers do not balance.** 599 vouchers are off, some by crores — its float amounts and all-debit opening balances. This vindicates D-012 and is reported, never silently repaired.
2. **The first generated sample had four rent payments on 1 April.** Caught by reading the CA validation sample as a practitioner would. Recurring decoys are now capped at one per month, with a regression test.
