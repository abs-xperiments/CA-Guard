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
