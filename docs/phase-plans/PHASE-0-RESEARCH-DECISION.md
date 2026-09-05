# Phase 0 — Research and Decision Gate (COMPLETED)

**Run date:** 2026-09-06 02:09 IST
**Status:** Research complete. Awaiting founder sign-off before Phase 1.
**Method:** Primary sources only (official APIs, patent full text, vendor pricing pages, direct download and statistical analysis of the candidate dataset). Where a claim could not be verified from a primary source it is marked UNVERIFIED.

---

## 0. Executive summary

Four findings materially change the plan:

1. **The primary external dataset is not usable as an accuracy benchmark.** `VynFi/vynfi-journal-entries-1m` is real, Apache-2.0, ungated and well-shaped — but its `is_fraud` / `anomaly_type` labels do **not** correspond to patterns present in the observable fields. Rows labelled `DuplicatePayment` duplicate *less* often than baseline; rows labelled `RoundDollarManipulation` are *less* round than baseline. Measured, not assumed (§2).
2. **The hybrid-fusion hypothesis is already a shipped commercial product.** MindBridge "Ensemble AI" is explicitly rules + statistics + ML fused into a transparent per-transaction risk score. "Hybrid fusion" cannot be the novelty claim (§3).
3. **A direct India-specific competitor exists and is not in our docs: CORAA (coraa.ai).** India-hosted, DPDPA-compliant, SA 240 journal-entry testing, ledger scrutiny, evidence-linked findings, Tally ingestion, ₹3,000/audit, 50+ Indian audit firms, and self-described **"patent-pending deterministic LLM architecture"** (§3, §4).
4. **`CLAUDE.md` mis-states the 2026 IP India guidance.** The 7 August 2026 guidelines govern *examiners using AI to examine patents*. They say nothing about whether AI inventions are patentable. Patentability is still governed by the **CRI Guidelines 2025** (29 July 2025) (§4).

None of these kill the project. Together they force a narrower, more honest positioning: CA-Guard's defensible ground is **genuinely local/on-premise processing + an open, reproducible, label-honest Indian audit benchmark**, not "hybrid AI for accounting".

---

## 1. Repository and environment state

Repo `b9ce148` contains only documentation, and **all of it sits under `mnt/data/ca-guard-starter/` rather than the repository root** — an upload artifact. Recommended first action of Phase 1: `git mv` the tree to root. Reversible, no content change. Not done in Phase 0 because Phase 0 forbids changes before sign-off.

Verified toolchain on this machine:

| Tool | Version | Note |
|---|---|---|
| Python | 3.14.3 | system |
| uv | 0.11.24 | ✅ |
| Node | 26.0.0 | ✅ Next.js 16 OK |
| npm | 11.17.0 | pnpm absent |
| Docker | 29.7.2 | ✅ |
| Railway CLI | 4.66.0 | ✅ already installed |
| gh | 2.93.0 | ✅ |
| ruff | 0.15.9 | ✅ |
| pyright | — | **absent** (install via npm/uv in Phase 1) |
| ollama / llama.cpp / LM Studio | — | **absent** — no local LLM runtime yet |

**Hardware constraint (decision-relevant): 8 GB unified memory, arm64, macOS 26.1.** This is the binding constraint on the local-LLM choice. A 7B model at Q4 (~4.5 GB) plus Next.js, Python, Docker and a browser will thrash on 8 GB. The explanation model must be **3–4B class**.

I verified the analytics stack actually installs and imports — not just that the metadata claims support:

```
py 3.13.1  sklearn 1.9.0  pandas 3.0.5  fastapi 0.141.1  pydantic 2.13.5  pyarrow 25.0.1   ✅
py 3.14.3  same set                                                                        ✅
```

---

## 2. Dataset gate — the central finding

### 2.1 VynFi is real, free and clean. Verified from the HF API, not the card.

| Property | Verified value |
|---|---|
| License | `apache-2.0` (repo `cardData.license`) |
| Gated / private | `False` / `False` |
| Rows | **667,584** lines (≈160k documents) — *not* 1M, despite the name |
| Columns | 48 |
| Download size | **34 MB** (3 parquet shards) — trivially manageable |
| Last modified | 2026-06-06 |
| Extras | `chart_of_accounts`, `cost_centers`, `trial_balances`, `je_network`, star-schema CSVs |

Licensing and accessibility therefore **pass**. The problem is elsewhere.

### 2.2 The labels are not grounded in the data

I downloaded a 200,000-line shard and tested whether each label's name corresponds to a pattern actually present in the observable fields. A valid benchmark should show lift ≫ 1.0. Measured lift:

| Label | n | Test | Lift vs baseline | Verdict |
|---|---|---|---|---|
| `DuplicatePayment` | 405 | duplicate on (company, account, amount, currency) | **0.35×** | inverted |
| `DuplicateEntry` | 249 | same | **0.69×** | inverted |
| `RoundDollarManipulation` | 329 | amount % 1000 == 0 | **0.31×** | inverted |
| `RoundingError` | 751 | amount % 1000 == 0 | **0.2×** | inverted |
| `MissingDocumentation` | 281 | `reference` is null | **1.0×** | no signal |
| `LatePosting` / `WrongPeriod` / `UnusualTiming` | 1,097 | `is_post_close` | **0.0×** | inverted |
| `SelfApproval`, `SegregationOfDutiesViolation` | 386 | preparer distribution | ≈ baseline | no signal |
| `BenfordViolation` | 233 | first-digit distribution | ≈ Benford | no signal |
| `VagueDescription` | 656 | `line_text` is null | **3.3×** | ✅ only real signal |

I re-tested round-number labels across **every** amount column (`local_amount`, `debit_amount`, `credit_amount`, `transaction_amount`) and moduli (10/100/1000) before concluding — this is not a single unlucky interpretation. Fraud-labelled documents are also *smaller* (₹123k vs ₹153k mean) and *less* manual (0.21 vs 0.28) than clean ones, i.e. the labels run against the audit intuition.

**Conclusion: the anomaly/fraud labels are decorative generation metadata; the corresponding patterns were largely not injected into the observable fields.** Any precision/recall figure we publish against them would be near-random noise and would read as *our detector failing*.

### 2.3 Two further structural limits

- **`posting_date` has no time-of-day component** — 200,000/200,000 rows are exactly `00:00:00`. Off-hours/posting-time detection, an explicit SA 240 characteristic and a planned Phase 2 signal, **cannot be evaluated on this dataset at all.** (Weekend-by-date is possible; ~2.5% of rows.)
- **Labels are document-level, replicated to every line.** Line-level anomaly rate 20.9% vs document-level 7.6%. Evaluating per line would trebly count the same finding. **All evaluation must be at document level.**
- `tax_code` 100% null, `trading_partner` 99.9% null, `cost_center` 70% null — do not build features on these.
- Schema is SAP/European (`lettrage`, `company_code`, doc types DR/KR/SA/HR/AA), currencies USD/EUR/CAD/GBP/AUD. **No INR, no Indian voucher types, no GST fields.**

### 2.4 Decision

**D-003 is overturned.** VynFi is **demoted from primary benchmark to ingestion/scale corpus.**

| Use | Verdict |
|---|---|
| Accuracy / precision / recall benchmark | ❌ **Rejected** — labels not recoverable |
| Realistic-shape ingestion + schema-mapping target (proves the canonical schema survives a foreign SAP export) | ✅ Keep |
| Volume/performance testing (667k lines) | ✅ Keep |
| Realistic amount distributions for Benford/statistical baselining | ✅ Keep (unlabelled) |
| Public-demo dataset on Railway (synthetic, Apache-2.0, redistributable) | ✅ Keep |

**The project-owned seeded Indian generator becomes the sole accuracy benchmark.** SSRN 2026 remains rejected (all-rights-reserved), unchanged.

### 2.5 The honesty problem this creates, and the mitigation

If we plant anomalies *and* detect them, "we found what we planted" is circular and a faculty reviewer will say so. Binding mitigations, to be enforced in Phase 1:

1. **Generator and detector are separately owned modules** with no shared constants. Ground truth is written by the generator and never read by a detector.
2. **Plant confounders and distractors**: legitimately round numbers, legitimate weekend postings, legitimate year-end concentration, legitimate duplicate-looking recurring entries. A detector that flags these is penalised.
3. **Realistic base rates** (~1–3% of documents), not the convenient 20%.
4. **Held-out seeds.** Thresholds are tuned on seeds 1–3 and reported only on unseen seeds 100+. Reported once, at the end.
5. **Report per-anomaly-type recall**, never a single headline F1.
6. Ship an **external-validity caveat** in the paper: results are on synthetic data; no real Indian ledger has been tested.

---

## 3. Market and competitive — materially changed

| Competitor | Verified capability (2026) | What it means for us |
|---|---|---|
| **CORAA** (coraa.ai) 🔴 **new** | India-hosted, DPDPA/ISO 27001/SOC 2. SA 240 journal-entry testing, ledger scrutiny, anomaly detection, OCR vouching, evidence-linked findings, Tally/SAP/Zoho/Excel ingest, 60+ working papers. ₹30,000 / 10 audits. 50+ Indian firms. NVIDIA Inception. **"patent-pending deterministic LLM architecture."** No external funding raised. | **This is CA-Guard's thesis, already in market in India.** Their one structural gap: SaaS-only, no on-premise path. |
| **MindBridge** | "Ensemble AI" = rules + statistics + ML compared simultaneously, producing transparent per-transaction risk scores over 100% of the population. June 2026 release expanded risk assessment. | **Kills "hybrid fusion" as the novelty.** Our hypothesis is their shipped architecture. |
| **Caseware Verity** | Launched May 2026. Workflow-native agentic AI, citation-backed answers, Risk Suggestion / Disclosure Checklist / Document Intelligence agents. 94% on golden set, −85% review time. | Enterprise assurance. Confirms "citation-backed / evidence-grounded" is table stakes, not differentiation. |
| **TallyPrime** | 7.0 already ships an **Audit Feature** detecting errors, inconsistencies and suspicious entries, plus Edit Log audit trail. 7.1 expected with AI anomaly detection. | The incumbent ledger is moving into our wedge from below. |
| **ClearTax / Winman** | Tax/GST/reconciliation and CA-ERP workflow respectively. Not anomaly-triage products. | Adjacent, not competing. |

**Revised positioning.** Drop "hybrid detection" as the headline. The honest, defensible claim is:

> An **open-source, on-premise** audit-review assistant for Indian CAs, published together with a **reproducible, label-honest Indian journal-entry benchmark** — where the anomaly signals, the fusion weights and the evaluation are fully inspectable, and no client data leaves the firm.

Every commercial competitor above is closed-source SaaS. That is the gap, and it is also exactly what makes this a credible *academic* contribution.

---

## 4. Patent and IP — risk summary

**Status: patent candidate. Not patentable-as-guaranteed. This search is non-exhaustive and is not legal advice.**

### 4.1 Correction to CLAUDE.md
The IP India guidance published **7 August 2026** covers *examiners' and controllers' use of AI during examination* — search, classification, translation, drafting support. It **does not change what is patentable.** Eligibility for CA-Guard is governed by the **CRI Guidelines 2025 (29 July 2025)**, which retain §3(k) and make demonstrable **"technical effect"** the gateway. `CLAUDE.md` currently implies the 2026 document is AI-patentability guidance; corrected in `docs/03_PATENT_AND_IP.md`.

### 4.2 Prior art actually read (claim text, not abstracts)

| Reference | Status | Relevance |
|---|---|---|
| **US12293420B2** — HighRadius, *Autonomous accounting anomaly detection engine* | **Granted** 2025-05-06, active to 2043 | Claim 1: receive GL entries → ML correlate against historical baselines → deviations beyond threshold → **prioritized** recommendations → display in real time. **Closest granted art to our core loop.** Differs in: real-time-at-entry, correction recommendations, no deterministic audit-rule layer, no evidence-completeness input, no LLM explanation. |
| **US20230005075A1** — PwC, *AI-augmented auditing platform … automated assessment of vouching evidence* | **Pending** (filed 2022-06-30) | Covers extracting document data and scoring whether it constitutes valid vouching evidence, with confidence scores linked to ERP line items. **Occupies "evidence sufficiency scoring" directly.** |
| **US11694460B1** — Wells Fargo, *NLP … audit testing with documentation prioritization* | Granted 2023 | Prioritises documents by **semantic similarity** to audit terms — *not* by presence/absence of supporting evidence. **Distant from our mechanism.** |
| **CORAA** "patent-pending deterministic LLM architecture" | Unknown / likely unpublished | 🔴 **Highest India-specific risk.** Indian applications publish at 18 months; if filed recently it is invisible to any search today. Genuinely unsearchable submarine risk. |

### 4.3 Clearly already known — do not claim
Financial anomaly detection with ML; risk scoring transactions; rules+statistics+ML ensembles (MindBridge, shipped); AI-assisted vouching and evidence matching (PwC); citation-grounded audit explanation (Caseware, shipped); AI reconciliation.

### 4.4 The one mechanism worth a professional's time
Of the six candidates in `03_PATENT_AND_IP.md`, five are covered by the art above. The surviving one is narrower and, on this search, unoccupied:

> **Using the *absence or incompleteness of linked supporting evidence* as a first-class weighted input into the anomaly-review priority ranking** — such that an otherwise-ordinary transaction is promoted specifically because its evidence trail is missing, and the ranking degrades gracefully and deterministically when the explanation model is unavailable.

Why it may be arguable: PwC scores evidence *that exists*; Wells Fargo ranks by *semantic content*; HighRadius ranks by *statistical deviation*. Ranking driven by an **evidence gap** is a different input. Under CRI 2025 the technical-effect argument would have to rest on the deterministic, offline-capable ranking pipeline, not on "AI finds fraud".

**This is a lead for a patent attorney, not a conclusion. Do not represent it as novel to any third party.** Recommended: keep an invention record with dates, and **consult an Indian patent attorney before any public disclosure, poster, demo day or preprint** — publication before filing destroys novelty.

---

## 5. Stack decision (frozen, pending sign-off)

| Layer | Decision | Verification |
|---|---|---|
| Frontend | **Next.js 16.3.4** + TypeScript + Tailwind v4 + **shadcn/ui** | 16.3.4 released 2026-08-31; v16 is Active LTS to **2027-10-22**. Node 26 present. shadcn MIT, own-the-code. |
| UI inspiration | **21st.dev** — MIT, free tier, browse only | No paid dependency enters the repo. Patterns copied and owned locally, per the UI rule. |
| Backend | **Python 3.13** + FastAPI + Pydantic v2 | Full stack installed and imported cleanly on both 3.13.1 and 3.14.3. 3.13 pinned for Docker/CI wheel breadth; 3.14 is a verified fallback. |
| Dataframes | **pandas 3.0.5 — not Polars** | 34 MB / 667k rows does not justify a second engine. Polars has no 3.14 classifier. Fewer moving parts. |
| ML | scikit-learn 1.9.0 (Isolation Forest) | Verified. |
| Storage | **SQLite** local/private; Postgres only if the demo needs it | Keeps private mode cloud-free. |
| Local LLM | **Ollama + a 3–4B instruct model** (Qwen3.5-4B / Phi-4-mini / Gemma-4-E4B) | **Forced by 8 GB RAM.** Not 7B. Ollama not yet installed — free, no credential. |
| Deploy | Docker Compose (private) + Railway (demo) | Railway CLI already installed. |

**Railway cost reality — founder-visible.** Free plan is **1 vCPU / 0.5 GB RAM / 1 replica, $1 monthly credit**. That will not hold Next.js + Python analytics. A working public demo realistically needs **Hobby, $5/month** (48 GB/service ceiling, $5 credits). Neon free tier is genuine and permanent (0.5 GB storage, 100 CU-hours, auto-suspend after 5 min) and is sufficient *if* we need it — but per D-006 the private path must not depend on it.

---

## 6. Evaluation protocol (revised for the label finding)

- **Unit of evaluation: the document/voucher**, never the line.
- **Primary benchmark:** project-owned Indian generator, held-out seeds, ~1–3% base rate, with confounders.
- **Secondary (unlabelled):** VynFi — used only for ingestion robustness, throughput, and distributional sanity.
- **Baselines:** (1) single deterministic rule set, (2) Isolation Forest alone, (3) hybrid fusion. Same split, same seeds.
- **Metrics:** precision@K (K = 25/50/100, matching a real review budget), recall per anomaly type, MRR, PR-AUC, plus rows-inspected-to-first-true-positive.
- **Explanation metrics:** evidence-coverage rate and unsupported-claim rate, scored against the structured findings the detector actually emitted.
- **System:** latency, peak memory, byte-identical repeatability for a fixed seed and version, and a hard no-network assertion in private mode.
- **Anti-gaming rule:** thresholds frozen and committed before the held-out seeds are ever run.

---

## 7. Three-month plan (revised)

| Phase | Weeks | Content | Acceptance |
|---|---|---|---|
| **1 — Foundation** | 1–2 | `git mv` to root; uv+ruff+pyright+pytest+CI; canonical Pydantic schema; CSV/XLSX intake; VynFi adapter; **Indian seeded generator with confounders** | VynFi ingests; generator is byte-reproducible by seed; ground truth stored separately from data |
| **2 — Deterministic signals** | 3–4 | Duplicates, round numbers, off-hours/weekend, period-end concentration, rare account pairs, threshold-adjacency, missing-evidence-reference | Per-rule recall on planted truth; confounders **not** flagged |
| **3 — Statistical + ML** | 5–6 | Benford, z-score/robust deviation, Isolation Forest, versioned feature pipeline | Deterministic re-runs; baselines 1 & 2 measured |
| **4 — Fusion + evidence** | 7–8 | Transparent weighted fusion, **evidence-completeness score**, finding schema, source-row linkage | Every finding shows its contributing signals; baseline 3 beats 1 & 2 *or* we report that honestly |
| **5 — Local explanation** | 9 | Ollama adapter, evidence-only prompt, deterministic fallback text, unsupported-claim guard | Explanations pass evidence-coverage tests; **network-off test passes** |
| **6 — UI** | 10–11 | Workspace, findings table, risk prioritisation, evidence drawer, review decisions, empty/loading/error, keyboard nav, subtle motion | Upload → queue → evidence → decision → export, end to end |
| **7 — Eval + deploy** | 12–13 | Benchmark runner, report export, security checks, Docker Compose, Railway demo, paper-ready results | Held-out seeds run **once**; clean repo; reproducible deploy |

Cut first if time runs short: report export polish, multi-user auth, XLSX edge formats. Never cut: the evaluation harness and the network-off guarantee — they are the research contribution.

---

## 8. Founder decisions required (blocking Phase 1)

**[FOUNDER DECISION] F-1 — Accept the dataset demotion.** VynFi becomes ingestion/scale only; the project-owned Indian generator becomes the sole accuracy benchmark. Overturns D-003.

**[FOUNDER DECISION] F-2 — Accept the repositioning.** Headline claim moves from "hybrid AI detection" (MindBridge ships it) to "open-source, on-premise, reproducibly benchmarked, India-first". Requires acknowledging CORAA in the paper's related work.

**[FOUNDER DECISION] F-3 — Patent disclosure timing.** Consult an Indian patent attorney before any public demo, poster, preprint or demo-day pitch. Confirm you accept that publishing first forfeits novelty.

**[FOUNDER DECISION] F-4 — Repo layout.** Approve `git mv mnt/data/ca-guard-starter/* .` as the first Phase 1 action.

**[CREDENTIALS NEEDED] C-1 — Railway plan.** A usable public demo needs **Hobby, $5/month**; the $0 plan's 0.5 GB will not run the stack. Approve the spend and provide account access when we reach Phase 7, or accept a local-only demo (Docker Compose + screen recording) at zero cost.

**No credentials are required for Phases 1–6.** Everything through the UI phase runs locally and free.

---

## 9. Exit criteria — met

- [x] Market map refreshed; CORAA and MindBridge Ensemble AI added
- [x] Dataset licence **and label integrity** verified empirically, not assumed
- [x] Prior-art claims read in full text; narrow mechanism identified; risks named
- [x] Stack frozen and verified by actual install, not metadata
- [x] Evaluation protocol revised to survive the label finding
- [x] Three-month sequence with acceptance criteria
- [x] Founder decisions and credentials listed
- [x] Remaining uncertainty documented, not silently assumed (§10)

## 10. Known remaining uncertainty

1. **CORAA's patent application is very likely unpublished.** No search can clear it today. Structural, not fixable.
2. **Indian patent databases were not searched exhaustively** — US full text was read; InPASS was not systematically mined. A professional search is required before filing.
3. **SA 240 (Revised)** is effective for periods beginning on/after **15 Dec 2026**; ICAI's Indian adoption date and final text were not confirmed from an ICAI primary source. Treat all rules as *audit-review heuristics*, never as compliance assertions — unchanged from the charter.
4. **No real Indian ledger has been seen.** Every claim about Indian data realism is an assumption until a CA reviews the generator's output. Recommend showing generated samples to one practising CA in Phase 1 — cheap, and it de-risks the entire benchmark.
