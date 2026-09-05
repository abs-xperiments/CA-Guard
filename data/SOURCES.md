# Data Sources Registry

Verified during Phase 0 on **2026-09-06**. Every entry below was checked against a primary source (the HuggingFace API and a direct download), not against a README.

---

## 1. VynFi/vynfi-journal-entries-1m — RETAINED FOR INGESTION/SCALE ONLY

| Field | Value |
|---|---|
| Name | `VynFi/vynfi-journal-entries-1m` |
| URL | https://huggingface.co/datasets/VynFi/vynfi-journal-entries-1m |
| Version accessed | `lastModified` 2026-06-06; accessed 2026-09-06 |
| License | **Apache-2.0** — confirmed via `cardData.license` on the HF repo API |
| Gated / private | `False` / `False` |
| Size | 667,584 lines, 48 columns, 34 MB across 3 parquet shards (name says 1M; actual is 668k) |
| Extras in repo | `chart_of_accounts`, `cost_centers`, `trial_balances`, `je_network`, star-schema CSVs |
| Bundling | **Downloaded at setup — never committed.** |

### Allowed usage
✅ Ingestion and schema-mapping target · ✅ throughput/scale testing · ✅ unlabelled amount distributions for Benford/statistical baselining · ✅ redistributable synthetic data for the public Railway demo.

### NOT allowed usage
❌ **Any precision / recall / F1 / PR-AUC figure.** The labels are not recoverable from the data — see ADR-0001. Measured label lift against the pattern each label names:

| Label | Test | Lift vs baseline |
|---|---|---|
| `DuplicatePayment` | duplicate on (company, account, amount, currency) | 0.35× |
| `DuplicateEntry` | same | 0.69× |
| `RoundDollarManipulation` | amount % 1000 == 0 | 0.31× |
| `RoundingError` | amount % 1000 == 0 | 0.2× |
| `LatePosting` / `WrongPeriod` / `UnusualTiming` | `is_post_close` | 0.0× |
| `MissingDocumentation` | null `reference` | 1.0× |
| `VagueDescription` | null `line_text` | **3.3×** (only real signal) |

### Known structural limits
- `posting_date` is `00:00:00` for **every** row → off-hours/posting-time detection is unevaluable here.
- Labels are document-level, replicated to every line (20.9% line-level vs 7.6% document-level) → **evaluate at document level only.**
- `tax_code` 100% null, `trading_partner` 99.9% null, `cost_center` 70% null → do not build features on these.
- SAP/European shape (`lettrage`, `company_code`, doc types DR/KR/SA/HR/AA), currencies USD/EUR/CAD/GBP/AUD. **No INR, no Indian voucher types, no GST fields.**

### Preprocessing performed in Phase 0
Read-only statistical profiling of shard `train-00000-of-00003.parquet`. No derived data retained.

---

## 2. Project-owned Indian synthetic ledger — PRIMARY ACCURACY BENCHMARK

To be built in Phase 1. Generated in-repo from a fixed seed; the generator is committed, the output is **not**.

Ground truth is written by the generator to a separate artefact and is never read by any detector. Binding integrity rules in **ADR-0003**: mandatory confounders, ~1–3% base rates, held-out seeds (tune on 1–3, report on 100+), per-anomaly-type recall.

License: MIT, same as this repository. Fully redistributable. No real person's or company's data.

---

## 3. Rejected

| Source | Reason |
|---|---|
| SSRN 2026, *Generating Synthetic Journal Entries for Audit Analytics* (abstract 7211804) | All-rights-reserved; the page states reuse is not permitted. **Must not become a project dependency.** Academically citable only. |
| Any real client ledger | Prohibited until a formal privacy-safe customer-data plan exists (CLAUDE.md constraint 8). |
