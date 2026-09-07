# Decision Log

| ID | Decision | Status | Reason |
|---|---|---|---|
| D-001 | CA-Guard is the 3-month scope; CA-OS is future vision only. | Decided | Prevent scope explosion. |
| D-002 | LLM explains structured findings; it does not solely determine anomaly risk. | Decided | Reliability and research clarity. |
| D-003 | ~~Primary external benchmark is VynFi.~~ **Superseded by D-007.** | Superseded | Licence verified clean, but labels are not recoverable from the data. See ADR-0001. |
| D-004 | Create a project-owned seeded Indian-style synthetic benchmark. | Decided | India relevance + ground truth. |
| D-005 | Railway is demo-only; private path is self-hosted. | Decided | Avoid contradictory privacy claims. |
| D-006 | Neon is optional metadata storage only. | Decided | Keep private mode independent of cloud DB. |
| D-007 | VynFi is an ingestion/scale/demo corpus only; the project-owned seeded Indian generator is the sole accuracy benchmark. | **Decided** (founder, 2026-09-06) | Measured label lift of 0.31×–1.0× against the patterns the labels name. ADR-0001. |
| D-008 | Drop "hybrid fusion" as the novelty claim; reposition on open-source + on-premise + reproducible Indian benchmark. | **Decided** (founder, 2026-09-06) | MindBridge Ensemble AI ships rules+stats+ML fusion; CORAA occupies the Indian wedge. |
| D-009 | Benchmark integrity rules are binding: separation of generator/detector, mandatory confounders, 1–3% base rates, held-out seeds, per-type recall. | **Decided** (founder, 2026-09-06) | Prevents the circular "we detect what we planted" criticism. ADR-0003. |
| D-010 | Stack frozen: Next.js 16.3.4, Python 3.13, pandas (not Polars), scikit-learn, SQLite, Ollama with a 3–4B model. | **Decided** (founder, 2026-09-06) | Verified by install. 8 GB RAM caps the model size. ADR-0002. |
| D-011 | The only mechanism worth a patent attorney's time is evidence-*gap*-driven review prioritization. | **Decided** (founder, 2026-09-06) | Five of six original candidates are covered by HighRadius/PwC/Wells Fargo art. |
| D-012 | Money is stored as integer paise; the Pydantic contract exposes Decimal rupees. | Decided | Float rupees force a balance tolerance, and a tolerance is where a real imbalance hides. VynFi's own float amounts leave 599 vouchers unbalanced. |
| D-013 | Generator/detector isolation is enforced by an AST test with a bounded allowlist, not by convention. | Decided | It caught a real violation on its first run. ADR-0003 rule 1. |
| D-014 | Patent language stays cautious; evidence-gap prioritization remains a hypothesis, not a novelty claim, pending formal prior-art and claim analysis. | Decided (founder F-2/F-3) | CORAA's unpublished filing cannot be cleared by any search today. |
| D-015 | A signal that cannot discriminate on a given ledger abstains rather than flagging everything. | Decided | `rare_account_pair` flagged 95% of VynFi; `off_hours_posting` would flag 100% of it. ADR-0004. |
| D-016 | Detector thresholds frozen in ADR-0004 and reported only on held-out seeds 101-105. | Decided | ADR-0003 rule 4. Thresholds were developed against seed 20250906 over several iterations. |
| D-017 | Signals stay independent in Phase 2; no fusion or scoring until Phase 4. | Decided | A reviewer must see which concern fired, not an opaque number. |
| D-018 | The generator models a ledger with an opening position and linked transaction cycles, not a stream of independent vouchers. | Decided | An internal CA review found the bank overdrawn by Rs 5.58 crore, fixed assets in credit and a year of unpaid TDS. docs/ca_validation/findings.md. |
| D-019 | Balance-sheet coherence is enforced by tests that read the trial balance, not only per-voucher tests. | Decided | None of the Phase 1 tests could see a defect that only appears in aggregate. |
| D-020 | Rules remain the primary detector. The model is retained but weighted low and must corroborate; it may not raise a voucher alone. | Decided | On held-out seeds it found 0 anomalies the rules missed and queued 30 legitimate vouchers. ADR-0005. |
| D-021 | Benford's law is reported per account as a diagnostic, never as a per-voucher flag. | Decided | A single number has no distribution. |
| D-022 | Phase 4 fusion is measured against rules-alone as the baseline to beat. | Decided | Adding signals that lower precision is not progress. |
| D-023 | Priority is fused with noisy-OR, not a weighted sum, and every finding carries its per-signal contributions. | Decided | A sum lets weak concerns outvote a decisive one and exceeds 1 meaninglessly. ADR-0006. |
| D-024 | Evidence availability is used as a detection signal, with the score uplift retained but recognised as near-redundant. | Decided | Removing evidence entirely costs 30pp at p@10; the uplift alone adds 1.6pp at p@50. ADR-0006. |
| D-025 | Phase 4 is judged on ordering, not recall. | Decided | Rules already reached 100% recall in Phase 2. Ranking took p@25 from 34% to 100%. |
| D-026 | The LLM renders an already-computed Finding. It never detects, ranks, or concludes. | Decided (founder) | The queue is identical with the model absent, broken or rejected. ADR-0007. |
| D-027 | Generated text is discarded if any number is untraceable or any conclusive phrase appears. No retry. | Decided | A fabricated figure reads exactly like a real one. 0% of a hallucinating stub reached a reviewer. |
| D-028 | First local model is Qwen3 1.7B Q4_K_M, not 4B. Larger models only via a Founder Decision Gate. | Decided (founder) | 8 GB machine. Prompt design is investigated before parameter count. |
| D-029 | The Ollama adapter refuses non-loopback hosts at construction. | Decided | Client data must never leave the machine; a config mistake must fail closed. |
| D-030 | Model installation is gated on measured free memory and swap pressure. | Decided (founder instr. 12) | Downloading onto a swapping machine measures page faults, not inference. |
| D-031 | Reasoning mode is disabled for thinking-capable models. | Decided | Qwen3 spent its whole token budget reasoning: 24.7s and truncated or empty output, versus 7.4s and complete with it off. |
| D-032 | No model remains the default; generated prose is opt-in. | Decided | 6.3s per finding is ~6 minutes across a 50-item queue, for 93% coverage against the deterministic 100%. |
| D-033 | Qwen3 1.7B Q4_K_M is sufficient; no larger model proposed. | Decided | The one weakness (coverage 0.858) was fixed by the prompt, reaching 0.925 while getting shorter and faster. Founder instruction 9 upheld. |
| D-034 | Review decisions are append-only; the trail is never edited or deleted. | Decided | A record that can be changed is not a review record. Enforced by a test that reads the source. |
| D-035 | Rejecting a finding requires a reason of at least three words. | Decided | Accepting says "I looked"; rejecting is the judgement someone will later question. |
| D-036 | Findings are recomputed, never stored; the engagement stores the ledger hash instead. | Decided | A stored copy would drift from what the code now says, and nobody would know which was right. |
| D-037 | The workspace is keyboard-first, and rejection is deliberately not a bare keystroke. | Decided | A CA working a long queue should not need the mouse, but a dismissal needs a typed reason. |
| D-038 | The UI derives its counters from the findings on screen, not from a server snapshot. | Decided | The snapshot never updated as decisions were recorded, so the progress bar was a lie. |
| D-039 | Uploaded files are mapped and normalised into the canonical schema; the upload path never assumes canonical column names. | Decided | A Tally export crashed with a bare 500. The mapping existed since Phase 1 but was never wired to the upload. |
| D-040 | The intake report is shown to the reviewer before any finding. | Decided | A file with no document column makes every entry look undocumented; a limitation of the file must not read as a finding about the client. |
| D-041 | Rupee and paise amounts are handled by separate code paths that never mix. | Decided | Confusing them is a hundred-fold error and would be invisible. |
