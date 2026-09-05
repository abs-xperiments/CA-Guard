# Decision Log

| ID | Decision | Status | Reason |
|---|---|---|---|
| D-001 | CA-Guard is the 3-month scope; CA-OS is future vision only. | Decided | Prevent scope explosion. |
| D-002 | LLM explains structured findings; it does not solely determine anomaly risk. | Decided | Reliability and research clarity. |
| D-003 | ~~Primary external benchmark is VynFi.~~ **Superseded by D-007.** | Superseded | Licence verified clean, but labels are not recoverable from the data. See ADR-0001. |
| D-004 | Create a project-owned seeded Indian-style synthetic benchmark. | Decided | India relevance + ground truth. |
| D-005 | Railway is demo-only; private path is self-hosted. | Decided | Avoid contradictory privacy claims. |
| D-006 | Neon is optional metadata storage only. | Decided | Keep private mode independent of cloud DB. |
| D-007 | VynFi is an ingestion/scale/demo corpus only; the project-owned seeded Indian generator is the sole accuracy benchmark. | Proposed (founder F-1) | Measured label lift of 0.31×–1.0× against the patterns the labels name. ADR-0001. |
| D-008 | Drop "hybrid fusion" as the novelty claim; reposition on open-source + on-premise + reproducible Indian benchmark. | Proposed (founder F-2) | MindBridge Ensemble AI ships rules+stats+ML fusion; CORAA occupies the Indian wedge. |
| D-009 | Benchmark integrity rules are binding: separation of generator/detector, mandatory confounders, 1–3% base rates, held-out seeds, per-type recall. | Proposed | Prevents the circular "we detect what we planted" criticism. ADR-0003. |
| D-010 | Stack frozen: Next.js 16.3.4, Python 3.13, pandas (not Polars), scikit-learn, SQLite, Ollama with a 3–4B model. | Proposed | Verified by install. 8 GB RAM caps the model size. ADR-0002. |
| D-011 | The only mechanism worth a patent attorney's time is evidence-*gap*-driven review prioritization. | Proposed | Five of six original candidates are covered by HighRadius/PwC/Wells Fargo art. |
