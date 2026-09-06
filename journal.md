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
