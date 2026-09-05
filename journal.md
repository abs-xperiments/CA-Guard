# CA-Guard Journal

This journal is intentionally written so a founder/student can understand what is happening without reading the code.

## 2026-09-06 — Project bootstrap
**Status:** Research/design ready for Claude validation.

**What we are building:** A private AI second-hand for CAs/accountants that finds unusual financial transactions, explains why they matter, shows evidence, and leaves the final decision to the professional.

**What we are deliberately NOT building:** a complete CA ERP, tax/GST filing system, autonomous audit opinion engine, or Tally replacement.

**Important design decision:** The numerical detection logic should be deterministic/statistical/ML and testable. The LLM is mainly for explaining structured findings. This keeps the system more reliable and easier to evaluate.

**Privacy decision:** The real product must have a self-hosted/on-premise path. Railway is only for a synthetic-data public demo. This prevents us from making a misleading “nothing leaves the office” claim about a cloud-hosted demo.

**Dataset direction:** Use a public synthetic journal-entry benchmark after license verification, plus a project-owned seeded Indian-style dataset with planted anomalies and ground truth.

**Patent status:** This is a patent candidate, not a guaranteed patent. Existing prior art already covers general financial anomaly detection and AI-assisted audit/evidence tasks. The project will investigate a narrower technical mechanism and a formal claim strategy later.

**Next step:** Claude Code must run Phase 0 research and validation before implementation.

---

## Journal entry template
### YYYY-MM-DD HH:MM IST — [PHASE]
**What happened:**
**Why it matters:**
**Tests/checks:**
**Git commit:**
**Founder decision needed:**
**Credentials needed:**
**Next step:**

---

## 2026-09-06 02:09 IST — [PHASE 0] Research gate complete. Two assumptions failed.

**What happened:**
I read every project document, inspected the machine, and then checked the project's core external assumptions against primary sources instead of taking them on trust. Four things came back different from what the docs assumed.

*1. The main dataset can't be used the way we planned.* `VynFi/vynfi-journal-entries-1m` is real, genuinely Apache-2.0, free and open — the licence question passes cleanly. But I downloaded it and tested whether its "fraud" and "anomaly" labels actually match anything in the data. They mostly don't. Rows labelled "DuplicatePayment" are *less* likely to be duplicates than an average row. Rows labelled "RoundDollarManipulation" are *less* likely to be round numbers. Rows labelled "LatePosting" have zero late-posting flags. In plain terms: somebody attached anomaly names during generation but never actually put the anomalies into the data. If we published accuracy scores against those labels, the numbers would be close to random — and they would look like *our detector* had failed. I re-tested the round-number labels against every amount column before concluding, so this isn't one unlucky reading.

I also found the dataset has no time-of-day on any transaction — every single row is timestamped midnight. So "unusual posting hour", which was a planned Phase 2 signal and an SA 240 characteristic, simply cannot be measured on it.

*2. Our core research idea is already a shipped product.* MindBridge sells "Ensemble AI", which is explicitly rules plus statistics plus machine learning combined into a transparent per-transaction risk score. That is our hybrid-fusion hypothesis, in market, today. We cannot claim it as new.

*3. There is a direct Indian competitor nobody had listed: CORAA (coraa.ai).* India-hosted, DPDPA-compliant, does SA 240 journal-entry testing, ledger scrutiny, evidence-linked findings and Tally imports, charges ₹3,000 per audit, and is used by 50-plus Indian audit firms. They also describe themselves as having a patent pending. This is the closest thing to CA-Guard that exists.

*4. A factual correction to CLAUDE.md.* The IP India guidance from August 2026 is about patent *examiners* using AI to do their job. It has nothing to do with whether AI inventions can be patented. That is still governed by the 2025 CRI Guidelines. The constitution currently implies otherwise.

**Why it matters:**
None of this kills the project, but it forces an honest narrowing. We can no longer say "hybrid AI detection for accounting" is the novelty, because two companies ship it. What is genuinely left, and what nobody in this list offers, is: **actually on-premise, open source, and published with a benchmark whose ground truth is real and inspectable.** Every competitor found is closed-source cloud software. That gap is real, and it happens to be exactly what makes this credible as academic work rather than a weaker copy of CORAA.

The dataset finding also creates a new risk I want to name rather than bury: if we generate our own test data *and* write the detector, "you found what you planted" is the obvious criticism, and it would be fair. So I wrote binding rules (ADR-0003) — the generator and the detector must not share code, we must plant realistic decoys the detector is penalised for flagging, and the final numbers must come from random seeds we've never tuned against.

**Tests/checks:**
No code written — Phase 0 forbids implementation before sign-off. Verification done: HuggingFace API queried directly for licence and schema; one 200,000-row shard downloaded and statistically profiled; patent claim text read in full for three references; Railway and Neon pricing pages read; the full Python analytics stack installed and imported successfully on both Python 3.13.1 and 3.14.3 to confirm it actually builds.

**Also found:** this machine has **8 GB of RAM**, which decides the AI model size for us — a 4-billion-parameter model, not a 7-billion one, or the laptop will crawl. And all the project files are sitting in `mnt/data/ca-guard-starter/` instead of the repository root, which looks like an upload accident and should be moved.

**Git commit:** none yet — holding for founder sign-off on the decisions below.

**Founder decision needed:**
- **F-1** Accept demoting the VynFi dataset to ingestion/testing only, making our own generator the sole accuracy benchmark.
- **F-2** Accept the repositioning away from "hybrid detection" toward open-source + on-premise + reproducible benchmark, and acknowledging CORAA in the write-up.
- **F-3** Confirm you'll speak to an Indian patent attorney *before* any public demo, poster or preprint — publishing first destroys the ability to file.
- **F-4** Approve moving the files to the repository root.

**Credentials needed:**
- **C-1 (not yet — Phase 7 only)** Railway's free plan gives 0.5 GB of RAM, which cannot run this application. A working public demo needs the **$5/month Hobby plan**. Either approve that spend later, or we do a local-only demo with a screen recording for zero cost. **Phases 1 through 6 need no credentials and no money at all.**

**Next step:** Await sign-off on F-1 to F-4, then begin Phase 1 — move the repo to root, set up tooling and CI, define the canonical journal-entry schema, and build the seeded Indian ledger generator with its decoys.

---

## 2026-09-06 03:05 IST — [PHASE 1] Foundation built. The benchmark works, and two bugs got caught by checking.

**What happened:**
Phase 1 is done and green. This phase deliberately contains **no detection logic at all** — it builds the ground the research stands on: one shared data format, a way to get real files into it, and the synthetic Indian ledger that everything will be measured against.

*The repository is now a repository.* The starter files moved out of `mnt/data/ca-guard-starter/` to the root with their history intact, and the project has proper tooling: dependency pinning, linting, type checking, a test suite, a `Makefile`, and free GitHub Actions CI.

*Money is now stored as whole paise, not rupees-with-decimals.* This sounds like a technicality and is not. If you store money as a decimal fraction, a few thousand entries drift by tiny amounts and vouchers stop balancing by a paisa here and there. The usual fix is to allow a small "close enough" margin — but in an audit tool, that margin is exactly where a genuine imbalance would hide. Storing whole paise means a voucher either balances perfectly or it does not, with no judgement call.

*The canonical schema is built around Indian reality:* the financial year runs April to March, so year-end means 31 March; vouchers are Journal/Payment/Receipt/Contra/Sales/Purchase; amounts are in rupees and display in the lakh/crore grouping a CA reads. It separates the *date on the voucher* from the *time it was actually typed in*, and it records whether that time is real — because the VynFi corpus has no real posting times, and treating midnight as fact would make all 667,584 of its rows look like suspicious after-hours entries.

*The Indian ledger generator is the important deliverable.* It produces a year of book-keeping for a mid-size Indian company — GST split into CGST and SGST, TDS under 194J/194C/192, PF, realistic vendor and customer names, staff who each have their own area of work. Into that it plants ten kinds of irregularity, and — more importantly — six kinds of **decoy**: entries that look suspicious but are completely legitimate. Rent that is a round ₹2,00,000 every month because the lease says so. An identical loan EMI every month. Depreciation dated 31 March, properly documented and approved. Bank charges auto-posted with no voucher.

The decoys are the point. Without them, a detector that flagged every round number and every 31 March entry would score beautifully and be useless in practice — a CA would drown in false alarms on the first day.

**Why it matters:**
Phase 0 rejected the VynFi dataset because its "fraud" labels didn't match its data. The obvious risk was that we'd make the same mistake in our own generator and not notice. So the test suite now runs **the exact measurement that exposed VynFi against our own data**, every time. VynFi's labels scored 0.31x–1.0x, meaning no signal. Ours score **61x to 500x**. If that ever slips, the build fails.

There is also now a test that physically prevents the detector code (coming in Phase 2) from importing the generator or its answer key. That rule was written down in Phase 0; it is now enforced by a machine rather than by memory. It caught a real violation the first time it ran.

**Two things found by checking instead of assuming:**

1. **The VynFi ledger doesn't balance.** 599 of its 143,602 vouchers have debits and credits that don't match — some by crores, because of how it was generated. We report this rather than quietly patching it. It also confirms the decision to store whole paise was right.

2. **My first generated ledger had four rent payments on 1 April.** I only caught this by opening the sample and reading it the way a CA would. Rent is monthly; four in one day is something a practitioner would spot in seconds and would have discredited the whole dataset. Recurring entries are now capped at one per month, with a test so it cannot come back.

**Tests/checks:** `ruff` clean, `ruff format` clean, `pyright` 0 errors, **95 tests passing**. The full VynFi corpus — 667,584 lines — ingests end to end in 28 seconds on this 8 GB laptop, with 99.93% of rows accepted and everything rejected explained. Generation is reproducible: same seed, same content hash.

**Git commit:** see below.

**Founder decision needed:** none. Phase 1 stayed inside the approved scope.

**Credentials needed:** none. Nothing was purchased and nothing needs to be. Per your instruction, the whole build runs locally at ₹0, and CI is free.

**Prepared for you — the CA review:** `docs/ca_validation/` now contains a 60-voucher sample formatted the way a CA reads a ledger, plus a 13-question sheet. It takes about 20 minutes and needs no software. The important question is #9: *which of these would you want to examine, and why* — asked before showing them our list, so we get their unprompted judgement rather than agreement with ours. As you directed, this does not block Phase 2.

**Next step:** Phase 2 — the deterministic audit-review signals (duplicates, round numbers, off-hours, period-end, rare account pairs, threshold adjacency, missing evidence). Success is measured two ways: does it find the planted anomalies, and does it leave the decoys alone.
