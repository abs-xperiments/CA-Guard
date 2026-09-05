# Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| Patent novelty overlaps | High | Formal prior-art search; narrow technical claim strategy; patent counsel before filing |
| Poor dataset quality | High | Use open synthetic benchmark + project-owned ground-truth generator |
| LLM hallucination | High | LLM downstream of structured findings; evidence-only prompt; fallback text |
| Privacy claim overstates reality | High | Separate local/private mode from Railway demo; document data flow |
| Scope creep | High | Three-month roadmap and explicit non-goals |
| Model false positives | Medium | Measure precision/recall; transparent signal breakdown |
| Dataset license changes | Medium | Record source/version/checksum; reverify before release |
| Railway cost/limit changes | Medium | Keep Docker self-hosted path and low-resource demo |
| Overcomplicated stack | Medium | Monolith-first; no unnecessary Kafka/vector DB/microservices |
| Hard-to-use UI | Medium | UX-first flows; test with non-technical users/faculty reviewers |
| Credentials blocked | Medium | Stop and ask founder; no invented secrets |
