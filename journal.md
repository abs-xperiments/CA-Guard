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

---

## 2026-09-06 04:20 IST — [PHASE 2] Ten signals working. Four bugs found, and three of them were mine.

**What happened:**
CA-Guard can now read a ledger and tell you which entries deserve a look, with a plain-English reason and the underlying facts attached to each one. Ten signals: duplicate payments, suspiciously round amounts, late-night entries, Sunday entries, undocumented year-end adjustments, odd account combinations, payments sitting just under the approval limit, material entries with no supporting document, someone posting outside their normal area of work, and entries made after the books closed.

**How it was measured.** Every signal was graded twice: did it find the irregularities planted for it, *and* did it leave alone the legitimate look-alike built to trap it. That second half is the one that matters. A tool that flags every round number and every 31 March entry would score perfectly on the first test and be thrown out by a real CA on the first morning.

The numbers below come from **five ledgers generated with seeds I never used while building the signals**. That distinction matters: I spent the session adjusting thresholds against one dataset, so any result measured on that same dataset would be worth nothing. These are from data the code had never seen.

| | |
|---|---|
| Nine of ten signals | found **100%** of what they were responsible for |
| `unusual_preparer_account` | 98% average, 88% on its worst ledger |
| Legitimate entries wrongly flagged | **zero**, on every trap, on every seed |
| Decoys reaching the queue by any route | **0 out of 1,000** |
| Review queue | **5% of the ledger**, containing essentially every planted irregularity |

In practical terms: a CA opens a 4,000-voucher ledger and gets about 200 to look at, and the ones worth finding are in there.

**Four bugs, found by measuring instead of assuming — and three were in my own benchmark, not the detectors:**

1. **The "odd account combination" signal flagged 95% of the real VynFi ledger.** That dataset has thousands of account codes, so nearly every pairing is unusual, and "unusual" stopped meaning anything. The fix follows the same principle we already use for posting times: when a signal can't actually distinguish anything on a given ledger, it should say nothing rather than flag everything. VynFi's queue went from 95.6% to 13.3%, and our benchmark was unaffected.

2. **Two of my generated patterns picked two different random dates** — one for the voucher, one for when it was "typed in" — so entries appeared to be posted months before they were dated. That falsely tripped the after-the-close signal on 26 legitimate entries.

3. **Ordinary entries could land on a Sunday**, because when I added a delay between the transaction date and the posting date I never checked what day it landed on. Eighteen perfectly normal vouchers were showing up in the Sunday signal.

4. **Planting eight identical irregularities made them normal.** A "rare" account pairing that appears eight times isn't rare, and a person who posts to the same account eight times is just doing their job. Both now vary across a set of different combinations — which is also closer to how a real ledger behaves.

I want to be straightforward that items 2 through 4 were faults in the test data I built last phase, not in the detection logic. They are exactly why the two-sided measurement exists: if I had only checked "did we find the planted items", all four would have gone unnoticed.

**One more correction:** my "just below the approval limit" band was set at ₹100. That would only catch someone hugging a ₹50,000 limit to the last rupee, which is not how a payment actually gets split. Widened to ₹5,000, or 10% of the limit.

**Why it matters:**
Every finding now carries a structured record of the facts behind it — the amount, the dates, who posted it, what was missing. That is deliberate groundwork: in Phase 5 the local AI model will be allowed to explain findings *only* from that record and nothing else. Building it into the data shape now is what will make "the AI cannot make things up" a property of the system rather than a hopeful instruction in a prompt.

The signals also physically cannot see the answer key. A test walks the code and fails the build if anything under the detection folder so much as imports the benchmark. That rule was written down in Phase 0; it is now machine-enforced with no exceptions permitted for detectors.

**Tests/checks:** ruff clean, pyright 0 errors, **205 tests passing** (203 offline, 2 against the full 667,584-line VynFi corpus). All ten signals run on that real corpus without incident, and the late-night signal correctly stays silent there because that dataset has no real posting times.

**Git commit:** see below.

**Founder decision needed:** none. Phase 2 stayed inside the approved scope.

**Credentials needed:** none. Still ₹0 — everything runs locally, CI is free.

**Still open:** the CA review pack from Phase 1 (`docs/ca_validation/`). It remains the only outside check on whether this data resembles a real Indian ledger, and three of the four bugs above were realism faults that a practitioner would have spotted faster than I did. Not blocking.

**Next step:** Phase 3 — the statistical and machine-learning layer (Benford's law, deviation from account norms, an Isolation Forest), measured against the same two baselines so we can say honestly whether it adds anything the rules did not already catch.

---

## 2026-09-06 05:40 IST — [AUDIT] I reviewed the generated ledger as a CA would, and it failed.

**What happened:**
You asked for an independent audit before moving on. I did one — and I should be clear at the outset that **I am not a practising Chartered Accountant**. What I did was apply Indian accounting and audit knowledge rigorously to our own generated data. It found real, serious problems. It does not replace the external review sitting in `docs/ca_validation/`, which is still worth getting.

I started where any reviewer starts: I built a trial balance and read it.

**It failed at the second line.** The bank account was overdrawn by ₹5.58 crore, with no overdraft facility anywhere in the books. That is not an unusual balance; it is an impossible one.

It got worse from there:
- **No opening balances at all.** The company apparently came into existence on 1 April with nothing and immediately traded ₹13 crore.
- **Plant & Machinery showed a credit balance** of ₹66.75 lakh — a fixed asset appearing as a liability, because depreciation was charged straight against the asset with no opening cost.
- **A full year of unpaid statutory dues:** ₹1.13 crore of TDS, ₹2.32 crore of GST, ₹89 lakh of PF, ₹10.24 crore of unpaid salaries. In a real engagement, unremitted TDS of ₹1.13 crore is a reportable matter. Here it turned out the payments simply did not exist.
- **The term loan had been over-repaid** into a debit balance.
- **258 days of debtors** — because collections were generated independently of the sales that created them.
- **PF was computed on gross pay** rather than on basic capped at ₹15,000.

**Why the earlier tests did not catch any of it.** Every one of these is invisible when you check vouchers one at a time, and that is all the Phase 1 tests did. Each voucher balanced perfectly. The ledger as a whole was nonsense. This is a lesson worth keeping: correctness at the level of a record tells you nothing about coherence at the level of a book.

**What I changed:**
The generator was rebuilt around a ledger rather than a stream of vouchers. It now opens from a real position (share capital, bank, debtors, creditors, fixed assets, a term loan). A sale creates a receivable that is later collected; a purchase creates a payable that is later paid. Statutory dues are remitted monthly — TDS by the 7th, PF by the 15th, GST by the 20th — computed from what the ledger actually accrued rather than invented, with March left outstanding because it genuinely falls due in April. Depreciation accumulates in its own account, monthly, as Schedule II expects.

**Three more bugs surfaced while fixing those:**
1. Payroll was being drawn at random instead of monthly — about **280 payroll runs in one year**, and ₹39 crore of wages against ₹8 crore of sales.
2. Purchases were drawn from the same distribution as sales, leaving an **8% gross margin**. A trading company at 8% is losing money, and the overdrawn bank was simply the symptom.
3. The petty-cash float could go **negative** on some seeds. Balancing withdrawals against payments works on average, not on every run, so the float is now tracked explicitly and cash payments stay under the ₹10,000 disallowance threshold.

**And two bugs in the detectors, which only the more realistic ledger could expose:**
1. **The "unusual account combination" signal looked up pairings in either direction.** Dr Creditors / Cr Bank is how every vendor payment is written; the reverse is a supplier refund and is genuinely rare. Taking the rarer of the two flagged **18% of the ledger** as unusual. Pairings now have a direction.
2. **The "posted by someone outside their area" signal was unreachable on small accounts** — 5% of a thirteen-entry account is 0.65, so even a single entry failed the test. One entry on an account clearly owned by somebody else is exactly the case the signal exists for.

**A performance problem too.** Preparing a ledger for analysis took 48 seconds for 53,000 vouchers, because it looped over every voucher in Python. That is well inside the size of a real client file. Rewritten as a database-style join: **8.8 seconds**, about five and a half times faster.

**Trial balance now:** bank ₹2.96 crore in hand, cash ₹31,300, debtors ₹3.25 crore, creditors ₹2.31 crore, fixed assets at cost with depreciation accumulated separately, term loan a liability, and one month each of salaries, TDS, GST and PF outstanding — which is what a real 31 March closing looks like. Turnover ₹9.90 crore at a 34% gross margin, 120 debtor days, 129 creditor days. Trial balance nets to zero.

**Tests/checks:** ruff clean, pyright 0 errors, **270 tests passing** plus the two full-corpus tests. The audit itself is now 22 regression tests in `tests/test_ledger_coherence.py` that read the trial balance, so this class of defect cannot come back unnoticed. Detector quality was re-measured on the held-out seeds after the restructure: nine signals at 100% recall, `unusual_preparer_account` at 90%, **zero decoys wrongly queued out of 1,000**, queue 5.9%.

**Git commit:** see below.

**Founder decision needed:** none.

**Credentials needed:** none. Still ₹0.

**Left undone deliberately:** TDS threshold limits, a round-off account, Professional Tax / ESI / IGST / export sales, and GST on bank charges. These affect presentation rather than the shape of the population, and are recorded in the findings document. The company also runs at an indicative loss — unusual, but not implausible, and not an audit red flag in itself.

**The external CA review is still open.** Everything above came from an internal review. A practitioner will still see things I did not, and three of the bugs I found were realism faults a practitioner would have spotted faster.

**Next step:** Phase 3 — statistical and machine-learning detection.

---

## 2026-09-06 06:30 IST — [PHASE 3] We added machine learning. It made things worse, and that is the most useful result yet.

**What happened:**
Phase 3 added the two things the roadmap asked for: a statistical layer (Benford's law, and a robust test for amounts that are unusual *for their own account*) and a machine-learning model (an Isolation Forest). Then I compared them honestly against the rules from Phase 2.

**The model lost.** On five ledgers it had never seen:

| Approach | Found | Wasted effort | Legitimate entries wrongly flagged |
|---|---|---|---|
| **Rules** | **100%** | 66% of the queue | **0** |
| Statistics | 10% | 15% | 0 |
| Machine learning | 51% | 49% | **30** |
| Everything combined | 100% | 71% | 30 |

The model found **zero** irregularities the rules had missed — not on one ledger, on every single one. Adding it to the rules did not raise what we catch at all; it just made the queue longer and dirtier.

**But look at *what* it flagged instead.** Across 1,000 legitimate entries planted as traps, the model wrongly queued:
- **110 bank charges** auto-posted by the bank
- **40 monthly rent payments** of exactly ₹2,00,000
- **2 documented year-end accruals**

Every one of those is genuinely statistically unusual. The rent is exactly round and repeats every month. Bank charges are tiny, carry no voucher, and are posted by a machine. A statistical model is *correct* to call them outliers — and it is wrong about all of them.

**Why?** Because what makes them legitimate is the lease, the bank mandate and the approval signature. **None of that is in the numbers.** No amount of statistical sophistication can recover it, because the information simply is not there.

This is the clearest evidence yet for what this project argues: **being unusual is not the same as being wrong.** A CA does not need software that finds odd numbers — the odd numbers are mostly fine. They need software that knows which odd numbers lack an explanation. That is an evidence question, not a statistics question.

**Being fair to the model, though.** I want to be careful not to overclaim. Our test irregularities are *rule-shaped by construction* — I wrote both the rules and the things they look for, so the rules had every advantage. This is **not** proof that machine learning is useless on real books. The opposite argument is actually quite strong: on a real client ledger containing something nobody thought to write a rule for, a model that needs no rule could be exactly what finds it. We cannot test that until we have real data.

So the model stays, weighted low, and it will not be allowed to raise a voucher on its own. Its honest job is finding what we did not think to look for. On our own benchmark that is nothing, because we only planted what we were looking for.

I also left a **tripwire**: a test that fails the moment the model finds something the rules missed. If that ever goes red, the model has earned its place and I will rewrite this entry.

**Benford's law** is reported per *account*, not per entry — asking whether a single number violates a distribution is meaningless. It correctly picked out the accounts where round-number irregularities were planted.

**Tests/checks:** ruff clean, pyright 0 errors, **296 tests passing** plus the two full-corpus tests. Model scores are identical across runs, so any result can be re-checked.

**Git commit:** see below.

**Founder decision needed:** none.

**Credentials needed:** none. Still ₹0.

**Next step:** Phase 4 — combining the signals into a single review priority, with the evidence gap as a first-class input. The bar is set by this phase: rules alone give 100% recall with zero false alarms on legitimate entries. **Fusion has to beat that, not just match it.** If it cannot, I will say so.

---

## 2026-09-06 07:25 IST — [PHASE 4] Ranking is the product. And the evidence idea works — but not the way I built it.

**What happened:**
Phase 4 turns the ten independent signals into one ordered review queue, and adds the thing this project has been arguing for since the beginning: **whether a transaction can actually be supported** feeds into how urgently it needs looking at.

**The bar was set by Phase 3 and it was awkward.** The rules already find *everything* — 100% of the planted irregularities, with no false alarms on legitimate entries. There is no recall left to win. So combining signals could not be justified by "we find more". It had to be justified by something else, and the only honest candidate was: **does the reviewer see the right things first?**

That turned out to be where the whole value is.

| | First 25 items a reviewer opens | Work to find 95% of the problems |
|---|---|---|
| Same queue, in ledger order | **34% real** | 229 vouchers |
| **Ranked by priority** | **100% real** | **157 vouchers** |

In plain terms: without ranking, a CA working down the list is wrong two times out of three and slowly loses faith in the tool. With ranking, the first twenty-five items are *all* real, and finding almost everything takes about a third less work. That is the product.

**The experiment I actually cared about.** `docs/03_PATENT_AND_IP.md` singles out "evidence availability drives review priority" as the one idea our prior-art search did not find already taken. Until today that was an assertion. So I ran it as a proper experiment: build the queue with evidence information, build it without, change nothing else, measure.

**Removing evidence entirely costs 30 points of precision in the first ten items** (100% → 70%), 18 points at twenty-five, pushes the work to find 95% from 157 vouchers up to 215, and drops overall recall from 99.8% to 96%.

So the mechanism is real and load-bearing. It stays a **candidate**, not a claim — nothing about the prior-art position has changed.

**But here is the part I did not expect, and would rather report than hide.** I built the evidence idea two ways: as a rule that flags entries with nothing behind them, and as a separate adjustment that nudges every voucher's score by how complete its paperwork is. The rule does essentially all the work. **The separate adjustment adds 1.6 points at fifty items and nothing anywhere else.**

That is worth saying plainly because it sharpens what the mechanism actually is. Evidence availability matters to prioritisation — strongly. But the effective way to use it is to let a missing document *raise* a finding, not to fine-tune a score afterwards. I kept the adjustment because it costs nothing and covers partial gaps the rule cannot reach, but I am not going to pretend it is what makes the difference.

**The machine-learning layer contributed nothing. Again.** Running the queue with the model and without it produces *identical* results on every measure. The low weight and the rule that stops it raising anything on its own are doing exactly what Phase 3 concluded they should.

**How the scores combine.** Not by adding weights together — that lets three minor concerns outvote one serious one, and produces numbers above 1 that mean nothing. Instead each signal is treated as independent evidence, which keeps the score between 0 and 1 and reads sensibly as "the chance at least one of these concerns is real". Every finding carries its own arithmetic: which signals fired, how much each contributed, how complete the evidence is, and the exact ledger lines behind it. A CA who disagrees can see the working.

That completeness is also deliberate groundwork. In Phase 5 the local AI model will be allowed to explain a finding using **only** what is recorded on it. Building that record now is what turns "the AI must not make things up" into a property of the data rather than a hopeful instruction in a prompt.

**Tests/checks:** ruff clean, pyright 0 errors, **326 tests passing** plus the two full-corpus tests.

**Git commit:** see below.

**Founder decision needed:** none.

**Credentials needed:** none. Still ₹0.

**Next step:** Phase 5 — the local, private AI explanation. This is the first phase that needs a model on this machine, which means installing Ollama (free, no account, no key) and a small model that fits in 8 GB. The rule is absolute: it explains the structured finding and nothing else, and detection keeps working with the model switched off entirely.

---

## 2026-09-06 08:40 IST — [PHASE 5] The explanation layer is built and cannot lie. The model is not installed, and should not be yet.

**What happened:**
Phase 5 is the part where an AI model finally appears in CA-Guard — and the whole design is about keeping it in its place. You set the rule and I've built to it exactly: **the model rewrites a finding that has already been decided.** It does not detect anything, does not rank anything, and is never allowed to reach a conclusion.

Everything was built and tested before anything was downloaded, in the order you asked for.

**The version with no AI at all is a real product, not a fallback.** This is what a firm sees if they never install a model, and what every reviewer sees whenever the model's output is rejected. It reads like this:

> Voucher V004000 for ₹74,773.39, dated 31-03-2025, warrants attention first (priority 0.99).
> Four concerns were raised on this voucher. The strongest is this: Manual entry of ₹74,773.39 with no supporting document reference on any of its 2 lines. Alongside it: Manual entry dated 31-03-2025, at the year end, with no supporting document and no approval...
> The evidence trail is 15% complete. No supporting document and no approval.
> Drawn from ledger lines V004000-01, V004000-02.
> *This is a prioritised observation for review, not a conclusion.*

**The model can only see verified facts.** It never gets a ledger row, a customer name or a narration — only the checked facts the detectors already produced. So anything it says beyond those facts is, by construction, made up. And then it gets checked anyway.

**The guard is the reason a model is allowed near this at all.** Every generated sentence is examined before a reviewer sees it. Every number must trace back to the finding. Words like "fraudulent", "proves" or "must be" are rejected outright — CA-Guard raises observations, and claiming more than that is not ours to do. **A failure means the text is thrown away and our own wording is shown. There is no second attempt.**

I tested this by writing a deliberately dishonest model — one that invents amounts and declares things fraudulent. **Not one word of its output reached a reviewer.** Rejected every time, on every finding.

**Something the tests caught that I would have missed.** The guard initially rejected *our own* explanation, because it displayed a priority of 0.986722 as "0.99". Rounding a number so a person can read it is faithful, not invented — the guard was wrong, not the text. I only found it because I wrote a test insisting that the always-on path must satisfy its own guard. If our own writing can't pass, the guard is broken.

**An honest finding about AI prose.** I also tested a *well-behaved* model — one that stays truthful. It writes shorter, more fluent text (56 words against our 101). But it only mentioned **62% of the concerns**, against our 100%. Fluent prose summarises, and summarising means quietly dropping things a reviewer needed to see. That is a genuine trade-off, and it is the thing to watch when a real model is measured — not whether it sounds good.

**Privacy is enforced, not promised.** The adapter refuses any address that isn't this machine — and refuses it at setup, not at use, so a mistyped host stops the run rather than quietly posting a client's ledger somewhere. Our strongest claim is that data never leaves the office; it should fail loudly rather than silently.

**Tests/checks:** ruff clean, pyright 0 errors, **388 tests passing**. The whole path — prompt, generation, checking, fallback — is exercised against a scripted stub, so none of this needed a download.

---

### 🔴 [FOUNDER ACTION NEEDED] I did not install the model, and I don't think we should yet

I checked the machine the moment the tests went green, as you instructed:

| | |
|---|---|
| Total memory | 8.0 GB |
| Actually available | **~1.4 to 2.0 GB** |
| **Swap in use** | **6.9 to 7.8 GB out of 8.0 GB** |
| Qwen3 1.7B needs | about 2.0 to 2.5 GB |

**The machine is already swapping heavily** — it is borrowing from disk to pretend it has memory it doesn't. Installing now wouldn't just be slow. It would make the timing measurement **meaningless**, because I would be measuring disk paging rather than the model thinking, and it would likely make the laptop unpleasant to use while it ran.

Your instruction 12 said not to download until there is sufficient free RAM. There isn't. **So nothing was downloaded, and nothing was spent.**

**What you can do, whenever convenient:**
1. Close what you can spare — the biggest holders right now are VS Code, Chrome and a virtual machine running in the background.
2. Run `make model-check`. It will tell you in one line whether the machine can take it.
3. When it says sufficient, run `make model-install`. That checks memory again itself and refuses if things have changed. It installs Ollama and Qwen3 1.7B — free, no account, no key, about 1.4 GB.

None of this is urgent. **CA-Guard is complete and usable right now without it.** The model only makes the wording nicer.

**If Qwen3 1.7B reads badly when we do get to it,** your instruction 9 applies and I agree with it: fix the prompt first, don't reach for a bigger model. The 62% coverage figure above already points at where the trouble will be, and that is a prompt problem, not a size problem. A bigger model would come to you as a decision, not a quiet upgrade.

**Credentials needed:** none. **Cost:** ₹0. Nothing downloaded, nothing purchased.

**Next step:** Phase 6 — the interface. The ranked queue, the evidence drawer, and the reviewer's accept/reject/investigate decisions.

---

## 2026-09-06 09:30 IST — [PHASE 5 cont.] Model installed. It failed first, and the fix was the prompt — not a bigger model.

**What happened:**
You approved freeing memory, so I did, then installed and properly measured the local model.

**What was eating the machine.** Docker Desktop was **reserving 4.1 GB of your 8 GB** — more than half the laptop — to run two containers called `playground-postgres` and `playground-neon-proxy`, up for forty hours and belonging to a different project entirely. That single reservation was why the machine had been swapping so badly. Quitting it, plus Spotify, Teams and RStudio, took swap from **7.51 GB down to 3.02 GB**.

Everything I stopped is reversible in seconds. Docker restarts with `open -a Docker`, and the containers' data volume was never touched.

**Then the model failed.** First real run: **29.6 seconds, and it returned nothing at all.** The fallback worked exactly as designed — the reviewer got CA-Guard's own wording and never saw a blank — but the model itself was useless.

Rather than assume it was too small, I looked. Qwen3 *thinks before it answers* unless you tell it not to. It was spending its entire word budget reasoning privately — 1,409 characters of it — then hitting the ceiling mid-sentence, or producing nothing at all. There is nothing for it to reason about here: the finding is already decided, and its only job is to rewrite it.

Turning reasoning off: **7.4 seconds and a complete answer. Four times faster.**

**Then the real test — 20 findings, measured properly:**

| | Passed the safety check | Invented numbers | Concerns mentioned | Length | Speed |
|---|---|---|---|---|---|
| **No model (CA-Guard's own wording)** | — | 0 | **100%** | 101 words | **instant** |
| **Qwen3 1.7B** | **20 out of 20** | **0** | 93% | **76 words** | 6.3 seconds |

**Every single explanation passed the safety check.** Not one invented figure, not one word claiming fraud or certainty, across all twenty.

**The one weakness, and how it was fixed.** Coverage started at 86% — the model was quietly leaving concerns out, which matters because a reviewer only acts on what they're shown. Your instruction was explicit: fix the prompt before reaching for a bigger model. So I did, telling it plainly to mention every concern and leave nothing out:

| | Before | After |
|---|---|---|
| Concerns mentioned | 86% | **93%** |
| Length | 94 words | **76 words** |
| Speed | 6.96s | **6.29s** |

More complete, shorter *and* faster. **No bigger model was needed, and I am not proposing one.** You were right to insist on that order.

**Which one should be the default?** I don't think the AI wins outright. It writes more naturally in a quarter fewer words. But CA-Guard's own wording mentions every concern, never errs, and appears instantly. Six seconds a finding is six minutes across a fifty-item queue. **So no model stays the default**, and generated prose is something a firm switches on if they want it.

**Tests/checks:** ruff clean, pyright 0 errors, **392 tests passing** plus the two full-corpus tests. I added tests for everything the real model taught me — including one asserting the app still works with the model switched off, because installing one must not quietly make it a dependency.

**Resource use, measured honestly:** 1.4 GB on disk. Between 4.8 and 9.9 seconds per explanation. Swap still climbs from 4.6 to 5.1 GB while it runs — this laptop *can* run the model, but not comfortably alongside much else. That's a fact about the hardware, not the design.

**What the safety check still cannot catch.** It stops invented numbers and conclusive language. It cannot catch a *plausible but misleading description* of a real figure. That is the main residual risk, and it is a further reason the deterministic path stays the default.

**Git commit:** see below.

**Founder decision needed:** none.

**Credentials needed:** none. **Cost: ₹0.** Ollama and Qwen3 are free — no account, no key, no card.

**Next step:** Phase 6 — the interface. The ranked queue, the evidence drawer, and the reviewer's accept / reject / investigate decisions.

---

## 2026-09-07 — [PHASE 6] The workspace. A CA can now actually use this.

**What happened:**
Everything before now produced a good answer that only existed on a command line. Phase 6 is where it becomes something a Chartered Accountant can sit down in front of.

**The screen.** A ranked queue on the left, the evidence behind whatever is selected on the right. The highest-risk entries are at the top, each with the reasons in plain English — "No supporting document", "Year-end adjustment", "Posted after close" — a small bar showing how complete the evidence trail is, and the current review status. Amounts in proper lakh and crore grouping, dates as dd-mm-yyyy.

Open a finding and you get, in this order: **why it was flagged** (each concern with how much it contributed), **the evidence trail** (document, approval, narration — present, missing, or *not required*), **the exact ledger lines** it came from, and only then a written explanation. That order is deliberate. A reviewer should reach their own view from the facts before reading prose written for them.

Then they accept, reject, or mark it for investigation.

**Rejecting requires a reason.** Accepting a finding just says "I looked at this". Rejecting says "this is not a concern" — and that is the judgement someone will question six months later when nobody remembers the invoice. So the Reject button stays disabled until a reason is typed, and the interface says why before you click rather than after.

**Nothing is ever edited or deleted.** Every decision is a new entry. If a reviewer changes their mind, both views are kept — that sequence is often more useful than the final answer. There is a test that reads the code itself and fails the build if anyone ever adds an instruction that could overwrite the trail.

**It is built for the keyboard.** `j` and `k` to move, Enter to open, `a` to accept, `i` to investigate, Esc to close. Somebody working through a hundred findings should not have to keep reaching for the mouse. Rejecting is deliberately *not* a bare keystroke, because it needs that typed reason.

**Three real bugs I only found by using it, not by testing it:**

1. **Uploading a CSV crashed the whole analysis.** Files are read as text, so the amount columns were strings, and the comparison failed deep inside the detection code with an error meaning nothing to anyone. Fixed properly — types are restored once, at the point data comes in. And crucially: a blank cell now means *absent*, not "empty text". An empty document reference is the evidence gap this entire product is built around; treating it as a value would have quietly erased it.

2. **The progress counter never moved.** You could review a dozen findings and the header would still say "0 of 49", because it was reading a snapshot from when the page loaded. A progress bar that does not move is worse than no progress bar.

3. **The ledger fingerprint was unstable.** It sorted rows by the first two columns alphabetically, which contain repeats — so the same ledger could produce two different fingerprints depending on the order it happened to arrive in.

**And one the screenshots caught.** The statistical signal was telling a CA the finding was unusual "because of has_evidence, evidence_coverage, is_manual". That is our variable names leaking onto their screen, and it makes everything around it look unfinished. It now says "mostly because of the absence of a supporting document, how few of its lines are documented and it being a manual entry."

**A small thing I am pleased with.** Where an approval was never required — because the amount was below the firm's limit — the screen says **"not required"**, not "missing". That distinction is the difference between a queue a CA trusts and one they abandon.

**Tests/checks:** ruff clean, pyright 0 errors, **442 tests passing**. The interface was also driven end to end in a real browser: uploaded a ledger, opened a finding, generated an explanation, rejected one with a reason, accepted the next by keyboard, and watched the counter go 0 → 1 → 2 of 49.

**Git commit:** see below.

**Founder decision needed:** none.

**Credentials needed:** none. **Cost: ₹0.** Next.js, Tailwind and the icons are all free and open source, and the components are written into the repository rather than pulled from a paid library.

**Next step:** Phase 7 — the last one. Benchmark runner, security checks, the Docker self-hosted path, and the deployment story. That is where the Railway question comes back, and where I will need a decision from you about whether to deploy publicly at all.

---

## 2026-09-07 — [BUGFIX] "Internal Server Error" on upload. The cause was a missing feature, not a small fault.

**What you reported:** adding a ledger file failed with "Something went wrong — Internal Server Error".

**What was actually wrong:** CA-Guard was only able to read files that already used *its own* column names. Any real ledger — a Tally export, a spreadsheet from a client, anything with "Vch No." and "Particulars" instead of `voucher_id` and `account_name` — crashed deep inside the analysis, and the browser showed you a blank server error that told you nothing.

I reproduced it in a minute by exporting a Tally-shaped CSV. It failed exactly as you described.

**Why it happened, honestly.** Back in Phase 1 I built the column-matching logic — the part that knows "Vch No." means a voucher number — and wired it to a command-line tool. I then built the upload path in Phase 6 and never connected the two. The product specification lists "map and confirm columns" as step three of the user journey, and I skipped it. My own tests all used files CA-Guard had generated itself, so nothing caught it. That is the kind of gap that only a real user with a real file finds, which is exactly what happened.

**What I built to fix it properly:**

A file now goes through a proper intake stage that does three things and reports on all of them:

- **Recognises** the columns it knows — "Vch No.", "Voucher", "Particulars", "Ledger", "Account Head", "Txn ID", "Dr", "Cr" and many more spellings.
- **Works out** what it can. The financial year and quarter follow from the date. Line numbers come from position within the voucher. Where a file has no account codes, the ledger name is used instead so account-level checks still work.
- **Says plainly** what the file did not contain.

That last one matters most. If your file has no column for supporting-document references, then *every* entry looks undocumented — and CA-Guard would otherwise fill your queue with "no supporting document" findings about a client who documented everything properly. So before you see a single finding, the screen now says:

> **Some checks are limited by what this file contains**
> This file has no supporting-document column, so every entry looks undocumented. Evidence findings will not be meaningful until one is supplied.
> This file has no approver column, so approval cannot be checked.
> This file records no posting time, so out-of-hours entries cannot be identified.

**A limitation of the file must never be mistaken for a finding about the client.** That principle is now built into the product.

**Other things fixed along the way:**
- **Amounts.** A file gives rupees; CA-Guard works in paise. Get that wrong and every figure is out by a hundred. The two are now handled by completely separate code paths so they cannot be confused, and commas, ₹ symbols and bracketed negatives like (1,200) are all read correctly.
- **Dates.** 03-04-2025 in an Indian ledger is 3 April, not 4 March. Now read day-first.
- **Files with one signed amount column** instead of separate debit and credit are split correctly.
- **Files that record only a posting date** — SAP does this — now use it as the entry date rather than being refused.
- **No upload can produce a blank server error any more.** A file that genuinely cannot be read gets told why: *"This file does not look like a ledger CA-Guard can read: could not find a voucher number, a date. Columns recognised: Amount, Debit."* I tested it against nonsense files, wrong-shaped files, half-truncated files and empty files — every one returns a readable explanation.

**Tests/checks:** ruff clean, pyright 0 errors, **464 tests passing** (22 new ones covering exactly this). Verified end to end in the browser with a Tally-style export: 431 vouchers read, 24 findings raised, caveats displayed.

**Founder decision needed:** none. **Cost:** ₹0.

**Worth saying:** this is the second time a bug has come from testing only against data CA-Guard generated itself. The first was the ledger that did not balance. Both were found by looking at the thing the way a real user would. The outstanding CA review in `docs/ca_validation/` is the same kind of check, and still worth getting.

---

## 2026-09-07 — [PHASE 7] The last one. Every claim is now a command, and the whole thing runs in a container.

**What happened:**
Phase 7 was about making the work checkable by someone else, safe to run on a firm's machine, and installable without spending anything.

**Every number is now reproducible.** Six phases produced measurements scattered across design records and journal entries, and anyone wanting to verify them had to take my word for it. That is not good enough for something being written up. So there is now a single command:

```
uv run caguard benchmark
```

It runs the held-out test ledgers against frozen settings and prints everything: how each of the ten checks performs, whether the machine-learning layer adds anything, what ranking does to a reviewer's queue, and whether the evidence idea is actually doing work. It writes `docs/RESULTS.md` directly. **If a number in the write-up disagrees with the runner, the write-up is wrong.**

It also *refuses* to run on the ledgers I used while building. Reporting on those would be reporting on the answer sheet.

All the earlier claims held when regenerated: no check falls for its decoy, the machine-learning layer finds nothing the rules missed on any seed, ranking takes the first 25 items from 34% useful to 100% useful, and removing the evidence information costs 30 points of precision.

**Security is now part of every run, not a one-off review.** Dependency checks run alongside the tests, locally and in CI — both clean, no known vulnerabilities in anything we depend on. There are 17 security tests, including the one that matters most: **the entire analysis runs with every network call made to fail.** That is the privacy promise proven rather than asserted.

**One genuine weakness found.** Uploaded filenames were being trusted to produce a temporary filename. A Windows-style path like `..\..\windows\system32` doesn't get cleaned up the way you'd expect on a Mac — the whole thing after the first dot is treated as a file extension. Harmless here, a directory escape on Windows. File extensions are now checked against a list of what we accept rather than trusted.

**The self-hosted version works.** One command:

```
docker compose up --build
```

I built the image and tested it properly rather than just writing the file. It runs as an unprivileged user, never as root. It reaches nothing on the internet. And **the analysis engine is deliberately not exposed at all** — it only listens inside the container, so even a mistyped setting can't put a client's ledger endpoints on the office network. I uploaded a Tally file through it (24 findings from 431 vouchers), recorded a decision, restarted the container, and confirmed the decision and its note were still there.

**Tests/checks:** ruff clean, pyright 0 errors, **483 tests passing**, both dependency audits clean, container verified end to end.

---

### 🔵 [FOUNDER DECISION] The Railway question is now live

You said at C-1: keep everything at ₹0, and revisit hosting once the product actually works. **It works.** So this is now a real decision rather than a deferred one, and I have not spent anything or deployed anything.

**Option A — a local demonstration, ₹0.** Run the container, record the screen. For a faculty review, a conference or a portfolio this shows exactly the same product. It is also the more honest option, because a local install *is* what CA-Guard is designed to be.

**Option B — Railway, $5/month.** A public URL anyone can open. Three conditions I would insist on:
1. **Synthetic data only, permanently.** No client ledger ever goes near it.
2. **A password gate.** A public URL is public — without one, strangers upload files and run up the bill.
3. **Honest wording on the page.** It must say it is a demonstration on synthetic data, and that the privacy claim applies to the self-hosted version. Anything else would mislead a CA about where their data sits.

**My recommendation: Option A for now.** The product's whole argument is that it runs on your own machine — a cloud demo slightly undercuts the pitch, and a screen recording carries the same weight for an academic reviewer at no cost and no risk. Railway makes sense later if you want people trying it themselves without installing anything.

Nothing in the code needs to change for either. `docs/deploy.md` has the detail.

**Credentials needed:** none, unless you choose Option B, in which case a Railway account.

**Still outstanding:** the CA validation pack from Phase 1. It remains the only outside check on whether the synthetic ledger looks like a real book, and two of the more embarrassing bugs this project has had were realism faults a practitioner would have spotted immediately.

---

## 2026-09-09 — [PHASE 8] Accounts, and fixing the thing you reported: pressing Accept looked like nothing happened.

**What you reported:** clicking accept, reject or investigate worked, but nothing on screen told you it had. You pressed a button and the row just eventually disappeared.

**You were right, and it was worse than cosmetic.** The row vanished because the default filter hides reviewed items — so the only feedback was a row silently going away, which reads like a bug rather than a confirmation.

**What I did about it.** I looked into how consumer apps handle this, and the pattern they've converged on is consistent: **act immediately, confirm briefly, and offer an undo** — rather than asking "are you sure?" before every click. The rule of thumb is that friction should match how hard something is to reverse.

That turns out to fit CA-Guard unusually well. **Undo here isn't deletion.** The audit trail can never be edited, so undoing records a *further* decision that reopens the finding. The change of mind is preserved, which is exactly what an audit reviewer would want to see. The pleasant behaviour and the honest one are the same thing.

Pressing a decision now does four things:
1. **The button changes to a tick reading "Done"** — immediately, before anything moves.
2. **The row flashes green once** and stays put for about a second, so a decision isn't a row disappearing.
3. **A message slides up** saying what happened, what it means for the report, and offering **Undo** for six seconds.
4. **The queue moves to the next unreviewed item**, because that's what you actually want next.

Rejecting keeps its friction — it still needs a typed reason, and it's deliberately not a single keystroke, because it's the judgement someone will question later.

**Other things borrowed from the same research:**
- **Loading placeholders shaped like the content**, instead of a spinner. The page no longer jumps when the queue arrives.
- **The progress bar actually moves now**, and turns green when everything's reviewed.
- **The "all done" screen offers the report**, rather than just saying the list is empty.
- **Error messages say what did *not* happen** — "Nothing was saved" — because after a failed click your first question is whether it half-worked.
- **All animation switches off** if your system is set to reduce motion. The confirmation still works without it.

---

**And the bigger thing you asked for: proper accounts.**

Before this, the reviewer's name came from a **text box on the page**. Anyone could type anyone's name. That isn't an audit trail — it's a suggestion, and a client is entitled to better. I hadn't spotted it; you were right to ask.

There's now a sign-up and sign-in, and **the name recorded against every decision comes from who is actually signed in.** The field has been removed from the API entirely, so a request that tries to send someone else's name is rejected outright rather than quietly believed.

Everything stays local — accounts live in the same single file as the decisions, so a firm still backs up one file, and no outside service is involved. Passwords are properly hashed with a memory-hard function (deliberately using something already in Python rather than adding another dependency). Sessions are signed cookies a script can't read, and the signing key is created automatically on first run, so **you don't need to invent or give me any secret.**

**Who can sign up:** the first account on a fresh install becomes the administrator — someone has to be able to get in. After that it needs an invite code, because a public URL with open sign-up means strangers uploading files and running up the bill. The code is generated automatically for a local install, or set through a setting for a deployment.

Every page that touches a ledger now requires signing in. I checked each one individually — the test asserts a 401 on all of them, because a route someone forgets to protect is the one that leaks.

**Tests/checks:** ruff clean, pyright 0 errors, **529 tests passing** (46 new on accounts alone), TypeScript clean, web build succeeds. I verified the sign-up page and flow in a browser; I stopped short of clicking through the decision buttons there because you interrupted the browser session, so that part is verified by the build and the underlying tests rather than by me watching it happen. Worth you trying it.

**Credentials needed: none.** Everything generates itself. For the Railway deployment you'll want to set one invite code, which I've put in the steps below.

**Next:** deployment steps for you — everything else is done.

---

## 2026-10-07 21:10 IST — [AUDIT] Full re-sync before the final push. The engine is good; the shell around it is not finished.

**What happened:**
Before changing anything, I re-read the whole project. Then I actually *used* it the way a CA would: signed up, uploaded ledgers through the real screen, opened findings, asked for explanations, recorded a decision, restarted the server and came back. I also re-ran every check and the full benchmark. The complete findings and the plan are in `docs/FINAL_COMPLETION_PLAN.md`.

**What's in good shape:**
- All the checks pass: 534 tests, lint and type checks.
- The benchmark reproduced its published numbers exactly. The research result still stands: knowing whether an entry has supporting evidence is what makes the ranking useful, and the machine-learning layer adds nothing. That negative result stays in.
- The explanation layer still cannot make things up.
- Decisions survive a restart, and nobody can sign as someone else.

**What I found that a CA would hit tomorrow morning:**
1. **Any ledger over 10 MB fails when uploaded through the screen.** The analysis engine itself handles it fine (36,000 vouchers in 13 seconds), but the web layer in front silently cuts the file off. Earlier tests talked to the engine directly, so they never saw this.
2. **While one ledger is being analysed, the whole app freezes for everyone.** I measured a simple status check taking 12 seconds.
3. **After a restart, every ledger has to be uploaded again.** The app still lists it, but opening it says "upload again". This is the "where did my ledger go?" problem you described, and it exists because CA-Guard currently never keeps the uploaded file.
4. **CSV files saved by Excel on Windows are rejected**, because of the way they store characters. Old-style `.xls` files are listed as supported but cannot actually be read.
5. **The explanation shows codes, not the transaction.** It says "accounts 5700 and 2400", not their names, and it shows no narration, no party, and no debit/credit lines. The data is all there; it just isn't displayed.
6. **"Accept" is ambiguous.** In CA-Guard it means "yes, this is an exception to follow up". Most accountants would read it as "the entry is fine". That is how a wrong conclusion gets into an audit file.
7. **The "statistically unusual" badge appears on most high-priority rows**, even though it contributes about 2% and our own research says it adds nothing. The screen overstates the ML layer.

**Security:**
- **The login key was saved into Git** in the Railway commit. It has **not** left your computer (your local copy is 15 commits ahead of GitHub). I removed it from tracking and generated a fresh one, so the old one is useless even when this history is pushed.
  - Side effect: if you were signed in to a local copy, you will need to sign in again.
- **The web framework has a newly published critical security advisory.** We don't use the affected feature, but it gets patched first thing.
- Hosted logins wouldn't be marked "HTTPS only".
- There's no limit on password guessing.

**About Netlify (you asked for it):** I checked Netlify's own documentation.
- **Netlify cannot run CA-Guard's analysis engine.** It has no Python, no containers and no permanent storage.
- It could host the screens, but the engine would still need a paid host somewhere else, and the link between the two cuts off any request longer than 26 seconds.
- Details and options are in the plan as **FD-1**.

**Tests/checks:** ruff ✅ · pyright ✅ · 534 tests ✅ · TypeScript ✅ · benchmark reproduced ✅ · Python dependency audit ✅ · web dependency audit ❌ (3 advisories, fix planned in Phase 1).

**Git commit:** this audit, the plan, and the key removal.

**[FOUNDER DECISION] needed (only these three):**
- **FD-1 Hosting:** recommendation is Railway ($5/month) for the whole app. Netlify can't run it alone.
- **FD-2 How long uploaded files are kept:** recommendation is until the reviewer deletes them on a firm's own machine, and auto-deleted after 7 days on the public demo.
- **FD-3 Button wording:** recommendation is "Exception — follow up" / "Cleared — not a concern" / "Investigate".

**Credentials needed:** none yet. Only once you choose a host.

**Next step:** Phase 1, the critical fixes. None of them depend on your decisions, so they can start immediately.

---

## 2026-10-07 21:14 IST — [DECIDED] Your three answers are recorded.

- **Hosting: Railway only.** No Netlify. I'll ask for the Railway account step when we reach deployment (Phase 9). Nothing is being spent before then.
- **Uploaded files: kept until someone deletes the engagement**, both on a firm's own machine and on the demo. A firm's retention policy (seven years under the audit documentation rules) stays the firm's call.
- **Buttons:** "Exception — follow up", "Cleared — not a concern", "Investigate". Decisions already saved keep their meaning, because only the labels change.

**Next step:** Phase 1, the critical fixes.

---

## 2026-10-07 21:29 IST — [PHASE 1 of completion] The critical fixes. Every one was checked through the real screen, not just the engine.

**What happened:** the seven problems from the audit that would have hit a CA first are fixed.
1. **Large ledgers upload.** A 27 MB, 116,000-row ledger now goes through the actual workspace in about 15 seconds. Before, anything over 10 MB failed after 30 seconds.
2. **The app no longer freezes while it analyses.** The heavy work now runs in the background of the server, so other people's clicks are answered straight away.
3. **Two uploads at the same moment can't get mixed up.** Before, they shared one temporary file name. Each now gets its own, and it is always cleaned up afterwards.
4. **Windows Excel CSVs and old `.xls` files now open.** If a file wasn't standard UTF-8, the intake notice says so, so you can check that names look right.
5. **Error messages are written for people.** They name *your* file, say what went wrong and what to do, and say "Nothing was saved". An unexpected failure gives an error reference instead of computer text.
6. **Security.**
   - The web framework is patched (0 known vulnerabilities, Python and web).
   - After 5 wrong passwords an account waits 15 minutes. This is per account, so one person's typos can't lock out the firm.
   - On an HTTPS deployment the login cookie is now marked "HTTPS only".
   - The public health check no longer reveals how many ledgers are open.

**Why it matters:** these were the difference between "works in a demo" and "works at 11:30 pm on the client's real ledger".

**New safety net:** `make smoke` starts the real workspace and engine together and uploads a 27 MB ledger through the screen. The 10 MB bug went unnoticed because all our tests talked to the engine directly. This one doesn't.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **561 tests** ✅ (27 new, including one proving a failure log never contains ledger text) · TypeScript ✅ · web build ✅
- both dependency audits clean ✅
- smoke test through the workspace: 5/5 ✅

**One honest limitation:** for very large files, the size limit kicks in after the web server has received the whole file, not while it is still arriving. Nothing is held in memory twice, and the 200 MB cap still holds. A hosting-level limit is the cleaner fix, and I'll set one at deployment.

**Founder decision needed:** none.

**Next step:** Phase 2. CA-Guard keeps your uploaded files, so you can download the exact original, every finding points at its row in your file, and nothing has to be re-uploaded after a restart.

---

## 2026-10-07 21:47 IST — [PHASE 2 of completion] Your uploaded files are kept, downloadable, and every finding points at its row.

**What happened:**
- **"Where did my ledger go?" is answered.** Every engagement has a **Source** button. It lists each file uploaded to it: name, type, size, who uploaded it and when, how many rows were used, and a fingerprint.
- **Download original** gives back the exact file. I checked byte for byte, through the real screen, that the downloaded file is identical to the uploaded one.
- **"Which file, which row, did this come from?" is answered.** Opening a finding now shows the transaction itself:
  - account names (not just codes);
  - debit and credit;
  - the narration and document reference;
  - who prepared it, whether anyone approved it, and when it was entered.
  
  Under it you see *"From ledger.xlsx · rows 8,916–8,917"*. **View in file** opens the file at those exact rows, highlighted, among their neighbours. I confirmed in Excel itself that rows 8,916 and 8,917 really are those lines.
- **Restarting no longer loses anything.** CA-Guard re-opens an engagement from its stored file and gets identical findings, with your decisions intact.
- **Deleting a client's file** is available to administrators only. It takes two clicks and cannot be undone. The file is really removed from disk. The record that it existed, and every decision made on it, stay, because an audit trail must still say what a decision was made on.

**Why it matters:** this is traceability. A CA can now go from "this is flagged" to the exact line in the client's own file, which is what makes a finding checkable rather than something to take on trust.

**Privacy wording updated to match.** CA-Guard used to say files were "never stored". That is no longer true, so every screen and document now says what *is* true: the file stays on the computer running CA-Guard and is never sent to an outside service. `docs/08_SECURITY_PRIVACY.md` has a table of where client data sits at every step.

**A bug I caught while testing:** CA-Guard's keyboard shortcuts were active even while a pop-up was open. Pressing "a" with the file preview open would have quietly recorded a decision on a finding you couldn't see. Shortcuts now pause whenever a pop-up is open, and I tested it.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **591 tests** ✅ (30 new) · TypeScript ✅ · web build ✅
- browser walk-through of upload → finding → view in file → source panel → download ✅

**Existing data:** an older database upgrades itself automatically, keeping its decisions (tested). Engagements opened *before* today have no stored file, so they ask for one re-upload. The screen says exactly that.

**Founder decision needed:** none.

**Next step:** Phase 3, the Explain Finding experience. For each signal it adds the working (for example "typical for this account: ₹40,000–₹1,20,000, from 312 entries"), clearer contribution labels, "not in this file" versus "missing" evidence, similar transactions, a suggested next step, and a guard that rejects an AI explanation that leaves a concern out.

---

## 2026-10-07 22:29 IST — [PHASE 3 of completion] "Explain this finding" now answers what a CA asks. And I found a serious date bug.

**What happened:** opening a finding now shows a full explanation, in the order a reviewer thinks:

1. **One sentence on why**, e.g. *"Prioritised for review mainly because it has no supporting document, is a manual entry at the year end and was entered after the books closed."* Directly under it: *"This finding means the entry deserves review. It does not, by itself, establish an error, a misstatement or wrongdoing."*
2. **Each reason with its working.** Not just "unusual amount", but: *usual amount on Cash in Hand ₹35,000; typical range ₹20,000–₹55,000; 33 entries compared.* Each reason is labelled High, Medium or Low, and where an auditing standard names that kind of entry it says so (e.g. "Relates to SA 240, post-closing entries").
3. **Evidence in four honest states:** present, missing, not required (e.g. below the approval limit) and **not in the file**. The last one matters: if a ledger is exported without a document column, CA-Guard now says "cannot be checked" instead of telling you the client has no documents.
4. **The transaction itself**, and where it sits in your file.
5. **Similar entries from the same ledger.** In one test it showed three similar undocumented year-end entries, all by the same preparer. That is the kind of pattern that changes how you approach a review.
6. **Suggested review steps**, written as procedures, never conclusions.

**No AI is needed for any of this.** It is built entirely from CA-Guard's own calculations, so it can't make things up and never makes you wait. If a local AI model is installed, it can still write a paragraph version underneath. Its paragraph is now **rejected if it leaves out any of the reasons**, as well as if it invents a number or uses conclusion words.

**Smaller things:**
- The "Statistically unusual" badge no longer appears on most rows. It contributed about 2%, and our own research says it adds nothing on its own, so it is now listed as "also noted".
- A finding has its own web address now, so you can refresh, or send a colleague straight to it.

---

**[IMPORTANT] A serious bug, found and fixed: some dates were being read wrongly.**
- **What happened:** when an uploaded file had dates like `2024-04-01` (which is how Excel date cells and most systems export them), CA-Guard read that as **4 January** instead of 1 April. Any date with a day above 12 was thrown away along with its row, without saying so.
- **What was not affected:** CSVs with dates written as 01-04-2024 throughout (like typical Tally text exports), and all our research numbers. The benchmark regenerates identically.
- **What may have been affected:** any Excel ledger uploaded before today that went through column mapping. If you tried a real client-style Excel file earlier, its year-end and Sunday findings could have been wrong. **Please re-upload it.**
- **Now:** every date is read on its own terms. If a date can't be read at all, the intake notice says how many rows were left out and why.
- I also fixed a crash when a file in CA-Guard's own format was missing one column.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **619 tests** ✅ (28 new) · TypeScript ✅ · web build ✅
- benchmark unchanged ✅
- browser check of the full card via a deep link ✅

**Not done, and why:** I couldn't measure the installed local AI model against the stricter check, because the Mac didn't have enough free memory. CA-Guard's own safety check refused to start it, which is the right behaviour. The stricter check can only make the AI paragraph fall back to CA-Guard's wording more often, never show something less reliable.

**Something for later, not changed now:** the opening-balance entry gets flagged partly as an "unusual amount for Cash in Hand", because it compares the whole opening balance with ordinary petty-cash entries. Excluding opening balances from that comparison looks right, but detector settings are frozen until the benchmark is re-run. I've recorded it as a candidate for the research track.

**Founder decision needed:** none.

**Next step:** Phase 4, the review workflow. The new button wording you chose, a better dashboard, search, and a report that clearly separates what CA-Guard found from what the reviewer decided.

---

## 2026-10-07 22:47 IST — [PHASE 4 of completion] Your button wording, a real dashboard, search, and a report that separates CA-Guard from the reviewer.

**What happened:**
- **Your wording is in.** The buttons say **Exception — follow up**, **Cleared — not a concern** and **Investigate**, and so do the table, the pop-up messages and the report. The keyboard shortcut is now **e** for Exception. Decisions you'd already recorded keep their meaning.
- **The home page shows where each review stands:** its name, the latest file, how many of the flagged entries have been reviewed (with a progress bar), how many are high priority, and when it was last worked on.
- **You can rename an engagement.** Click its title and type, e.g. "Sharma Traders — FY 2024-25".
- **Search and filters in the queue.**
  - Type a voucher number, an amount in any format ("185530" or "1,85,530"), an account, words from the narration, or the preparer's name. Press **/** to jump to the search box.
  - Filter by reason, or show only entries with no document.
  - Large queues show 200 rows at a time, highest priority first.
- **The report now reads like a working paper.**
  - "What CA-Guard observed" and "What the reviewer decided" are visibly separate.
  - It records which file it was built from, with a fingerprint that proves it.
  - It says how the entries were picked: risk-based, not statistical sampling.
  - It names who generated it and when, and dates every decision.
  - It prints cleanly.
- **On the public demo, visitors can't see each other's work**, even if two people upload the same sample file. I checked all 12 ways into an engagement. I also broke the protection on purpose to confirm the test catches it.

**Bugs found and fixed:**
- The report's summary line would have said "investigate**ed**".
- If you filtered to high-priority items and had finished those, the screen said "Every finding has a recorded decision" even though others were still open. That could have made someone stop early.

**A correction to this journal:** the times on my previous three entries were estimates, and they were wrong by up to two hours (one even said tomorrow). I've corrected them to the real commit times. From now on every time here is read from the clock.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **628 tests** ✅ (9 new) · TypeScript ✅ · web build ✅
- dashboard, rename and search checked in a browser ✅

**Founder decision needed:** none.

**Next step:** Phase 5. Uploads become a background job with a visible progress indicator (reading → mapping → analysing → ranking), because a full year's ledger takes about 11 seconds to analyse and the screen shouldn't just sit there. Logging will cover every step without ever recording client data.

---

## 2026-10-07 23:34 IST — [PHASE 5 of completion] Uploading shows what's happening, analysis is twice as fast, and the logs can't hold client data.

**What happened:**
- **Uploading no longer just sits there.** After you choose a file the screen shows:
  - "Sending the file — 42%";
  - then each step as it happens: reading the file → recognising the columns → analysing every voucher → keeping the original;
  - then it opens the review on its own.
  
  If several people upload at once, it says it is waiting rather than looking stuck.
- **If something goes wrong**, the screen says which file wasn't opened and why, and offers **Try the same file again** without making you find it again. Before, that button only reloaded the list.
- **Analysis is more than twice as fast.** I first measured where the time actually went: almost all of it was in one routine that walked through the vouchers inefficiently. Fixing it took a 30,000-voucher ledger from about 11 seconds to under 5, with exactly the same findings. The research benchmark came out identical to the last digit.
- **CA-Guard now keeps a log** of what it does: when a file arrived and how big it was, how long each step took, how many rows and findings, explanations generated, reports produced, files downloaded or deleted. That is what you need if something goes wrong on a real install.
- **The log cannot contain client data.** It never records narrations, account names, amounts or the client's file name. This is enforced in one place, so it doesn't depend on remembering. A test runs a whole review and checks every log line for anything from the ledger. To make sure that test actually works, I planted a leak on purpose and confirmed it caught it.

**Why it matters:** a CA at 11:30 pm should see progress, not a frozen screen. And a log is the easiest place for a privacy promise to break by accident.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **639 tests** ✅ (11 new) · TypeScript ✅ · web build ✅
- benchmark identical ✅
- 26 MB upload through the browser, watched stage by stage ✅

**One deliberate difference from the plan:** a file that fails to analyse is still not kept, so "Nothing was saved" stays true. Retrying just re-sends the same file from your browser.

**Founder decision needed:** none.

**Next step:** Phase 6, the security and privacy review: browser security headers, a written threat model, and making sure no screen claims more privacy than is true (e.g. "Everything stays on this machine" on the hosted demo).

---

## 2026-10-07 23:55 IST — [PHASE 6 of completion] Security review. An independent reviewer found real problems; all the serious ones are fixed.

**What happened:** I hardened what I knew about, then asked a separate reviewer, with no stake in my earlier decisions, to try to break CA-Guard. That was worth doing.

**The good news first:** they found **no way to get in without an account, and no way to see someone else's engagement**. The access design held.

**What they found, all fixed and each pinned by a test:**
1. **The CSV report could carry hidden spreadsheet formulas.** A malicious ledger, or a reviewer's name or note, could plant a formula that runs when a CA opens the export in Excel. Every cell is now neutralised. My first fix didn't work (a pandas detail meant it checked no columns at all); re-running their proof of concept caught that.
2. **Signing out didn't really sign you out.** A copied login cookie kept working for up to 12 hours. Signing out now ends **every** session for that account, on every device. So does changing a password.
3. **Invite codes could be guessed quickly.** Wrong guesses are now limited, and CA-Guard **won't start** if the configured code is shorter than 16 characters. (When we deploy I'll give you a command that generates a proper one.)
4. **One account could overload the server.** It's now limited to 2 analyses at a time, and only 6 analysed ledgers are kept in memory (others reload from their stored file when opened).
5. **Login timing revealed which email addresses have accounts.** It no longer does.
6. Smaller fixes: memory limits on the login counter, safer creation of the key files, and clean-up of upload files left behind by a crash.

**A real bug found along the way:** findings whose voucher number contains a slash, like Tally's "JV/2024/117", **could not be opened at all**. That would have made entire Tally ledgers unusable. Fixed and tested.

**A product change:** the workspace no longer accepts **Parquet** files. No accounting software exports them, and I measured that a small Parquet file can expand roughly 10,000-fold in memory, with no way to detect it in advance. CSV and Excel (`.xlsx`, `.xls`) are unchanged, and Parquet still works from the command line for our research tools.

**Also in this phase:**
- Browser security protections on every page; I checked in a real browser that sign-in still works with them on.
- Excel "zip bombs" (tiny files that unpack to gigabytes) are refused.
- No screen says "this machine" any more (untrue on the hosted demo).
- Password managers can now fill the login form.

**One of my own mistakes:** the end-to-end check had been silently testing an old copy of the app left running from my earlier testing. It now refuses to run if that can happen, and it runs automatically in CI.

**Deliberately not done (recorded with reasons):**
- someone who knows your email can lock you out for 15 minutes;
- a stricter browser policy needs extra machinery;
- container packaging fixes belong to the deployment phase.

**Tests/checks:**
- ruff ✅ · pyright 0 errors ✅ · **670 tests** ✅ (31 new) · TypeScript ✅ · web build ✅
- both dependency audits clean ✅ · smoke test 6/6 ✅

**Founder decision needed:** none. (Dropping Parquet uploads is recorded as D-065; tell me if you disagree.)

**Next step:** Phase 7, a full test sweep. Browser-driven end-to-end tests of the whole workflow, the remaining awkward inputs, restart in the middle of a review, and three walk-throughs as different kinds of user.

