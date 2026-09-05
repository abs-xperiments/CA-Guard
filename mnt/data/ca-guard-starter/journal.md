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
